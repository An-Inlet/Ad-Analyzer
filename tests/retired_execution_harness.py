"""Pinned historical regressions in a separate interpreter; never current capabilities."""

import hashlib
import json
import os
import sys
from pathlib import Path
from xml.etree import ElementTree

from tests.retired_snapshot import PIN, TREES, extract, run_bounded

MANIFEST = Path(__file__).parent / "fixtures/retired_execution/nodes-2155ff3.json"
SUPPLEMENT = MANIFEST.parent / "nodes-supplement-2155ff3.json"
FORWARD = MANIFEST.parent / "nodes-forward-2155ff3.json"
BATCHES = {"original": (MANIFEST, 142), "ui_supplement": (SUPPLEMENT, 19),
           "initial_forward": (FORWARD, 88),
           "initial_native": (MANIFEST.parent / "nodes-initial-native-2155ff3.json", 10),
           "configured_api": (MANIFEST.parent / "nodes-configured-api-2155ff3.json", 34),
           "runtime_api": (MANIFEST.parent / "nodes-runtime-api-2155ff3.json", 40),
           "configured_candidates": (
               MANIFEST.parent / "nodes-configured-candidates-2155ff3.json", 16),
           "google_completion_api": (
               MANIFEST.parent / "nodes-google-completion-api-2155ff3.json", 12)}


def qualify(root: Path, artifacts: Path, batch: str) -> None:
    if os.environ.get("INLET_RETIRED_EXECUTION_CHILD"):
        raise AssertionError("Historical harness recursion forbidden")
    if not os.environ.get("AD_ANALYZER_TEST_POSTGRES_URL") or os.environ.get(
        "AD_ANALYZER_CI_DISPOSABLE_POSTGRES"
    ) != "true":
        raise AssertionError("Historical qualification requires disposable PostgreSQL")
    artifacts.mkdir(parents=True, exist_ok=True)
    snapshot = artifacts / "source"
    extract(root, snapshot)
    manifest, expected_count = BATCHES[batch]
    nodes = json.loads(manifest.read_text())
    if (not isinstance(nodes, list) or len(nodes) != expected_count
            or len(set(nodes)) != expected_count):
        raise AssertionError("Exact historical case manifest required")
    plugin = MANIFEST.parent / "inlet_retired_browser_assets_plugin.py"
    env = dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN,
               PYTHONPATH=os.pathsep.join((str(snapshot), str(plugin.parent))))
    env.pop("PYTEST_ADDOPTS", None)
    command = [sys.executable, "-m", "pytest", "-p", "inlet_retired_browser_assets_plugin",
               "-o", "addopts=", "-q"]
    collection_log = artifacts / "collection.log"
    code = run_bounded(command + ["--collect-only", *nodes], snapshot, env, collection_log, 90)
    collected = [line for line in collection_log.read_text().splitlines()
                 if line.startswith("tests/") and "::" in line]
    if code or sorted(collected) != sorted(nodes):
        raise AssertionError(f"Historical collection differs; see {collection_log}")
    (artifacts / "provenance.json").write_text(json.dumps(
        {"commit": PIN, "trees": TREES, "batch": batch, "nodes": nodes,
         "fixture_asset_plugin": {
             "path": str(plugin.relative_to(root)),
             "sha256": hashlib.sha256(plugin.read_bytes()).hexdigest(),
             "nodes": [node for node in nodes if node in {
                 "tests/test_v2_execution_browser.py::test_v2_execution_review_browser[sqlite-False]",
                 "tests/test_v2_execution_browser.py::test_v2_execution_review_browser[postgres-False]",
             }],
             "asset": "app/portal/static/reported-rule-view.mjs",
             "asset_sha256": "5c9b6722b2717c9f38afc347ff9cd1b0b03fa50397ddd89e9588e3262f4e72a2",
         },
         "python": sys.executable, "scope": "historical runtime only; not deployed policy"},
        indent=2,
    ) + "\n")
    junit = artifacts / "historical.xml"
    log = artifacts / "historical.log"
    code = run_bounded(
        command + ["-ra", "--basetemp", str(artifacts / "pytest"),
                   "--junitxml", str(junit), *nodes], snapshot, env, log,
    )
    if not junit.is_file():
        raise AssertionError(f"Historical result missing; exit {code}; see {log}")
    results = ElementTree.parse(junit).getroot().findall(".//testcase")
    if len(results) != len(nodes):
        raise AssertionError(f"Historical results incomplete; see {junit}")
    unexpected = [case for case in results if case.find("failure") is not None
                  or case.find("error") is not None]
    # Only original SQLite row-lock limitations are allowed; no new skip is introduced.
    skipped = [case for case in results if case.find("skipped") is not None]
    allowed_skips = {
        "test_concurrent_handoffs_share_protected_origin[sqlite]",
        "test_initial_start_admission_boundaries[sqlite-competing]",
        "test_concurrent_exact_initial_start[sqlite]",
    }
    if any(case.attrib.get("name") not in allowed_skips for case in skipped):
        raise AssertionError(f"Unexpected historical skip; see {junit}")
    if code or unexpected:
        raise AssertionError(f"Historical cohort failed ({len(unexpected)} cases); see {log}")
