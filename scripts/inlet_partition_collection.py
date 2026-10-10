"""Opt-in collection evidence only; never run tests or modify collected items."""

import ast
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

import pytest
from _pytest.junitxml import bin_xml_escape, mangle_test_address

MAX_BYTES = 32 * 1024 * 1024
MAX_NODES = 20_000


def compact(value: str) -> dict[str, object]:
    raw = value.encode("utf-8")
    return dict(
        sha256=hashlib.sha256(raw).hexdigest(),
        utf8_bytes=len(raw),
        display=raw[:256].decode("utf-8", errors="ignore"),
        exact_text=value if len(raw) <= 16 * 1024 else None,
    )


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, timeout=30).strip()


HISTORICAL_PATHS = (
    "tests/fixtures/retired_execution/nodes-archive-financial-social-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-supplement-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-forward-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-initial-native-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-configured-api-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-runtime-api-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-configured-candidates-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-google-completion-api-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-initial-dom-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-financial-period-api-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-tiktok-linked-shell-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-plan-review-owner-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-highwater-api-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-social-execution-api-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-feedback-claimed-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-configured-reported-rule-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-fresh-planning-pilot-2155ff3.json",
    "tests/fixtures/retired_execution/nodes-two-brand-pilot-2155ff3.json",
)
SNAPSHOT_PATH = "tests/retired_snapshot.py"


def tracked_bytes(root: Path, relative: str) -> bytes:
    committed = subprocess.run(
        ["git", "-C", str(root), "cat-file", "blob", f"HEAD:{relative}"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if committed.returncode or committed.stdout != (root / relative).read_bytes():
        raise pytest.UsageError("Evidence file must match a tracked HEAD blob")
    return committed.stdout


def historical_provenance(root: Path) -> dict[str, object] | None:
    paths = (*HISTORICAL_PATHS, SNAPSHOT_PATH)
    present = [(root / path).exists() for path in paths]
    if not any(present):
        return None
    if not all(present):
        raise pytest.UsageError("Incomplete historical provenance files")
    source = tracked_bytes(root, SNAPSHOT_PATH)
    pins = [
        node.value.value
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "PIN"
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(pins) != 1 or len(pins[0]) != 40 or any(c not in "0123456789abcdef" for c in pins[0]):
        raise pytest.UsageError("Exact historical PIN literal required")
    return dict(
        pin=pins[0],
        retired_snapshot_sha256=hashlib.sha256(source).hexdigest(),
        manifests={
            path: hashlib.sha256(tracked_bytes(root, path)).hexdigest() for path in HISTORICAL_PATHS
        },
    )


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--partition-manifest", type=Path)


def pytest_configure(config: pytest.Config) -> None:
    args = list(config.invocation_params.args)
    found_plugin = False
    while args:
        arg = args.pop(0)
        if arg in {"--collect-only", "-q", "-qq"}:
            continue
        if arg in {"-p", "--partition-manifest"} and args:
            value = args.pop(0)
            if arg == "-p":
                if value != "inlet_partition_collection" or found_plugin:
                    raise pytest.UsageError("Only the collection evidence plugin is allowed")
                found_plugin = True
            continue
        raise pytest.UsageError("Noncanonical collection invocation")
    if (
        not config.option.collectonly
        or not found_plugin
        or os.environ.get("PYTEST_ADDOPTS", "").strip()
        or config.option.inifilename
        or config.option.noconftest
        or config.option.confcutdir
        or getattr(config.option, "lf", False)
        or config.getoption("junitprefix", default=None)
    ):
        raise pytest.UsageError("Only unfiltered collect-only evidence is permitted")
    configured_addopts = shlex.split(str(config.inicfg.get("addopts", "")))
    if set(configured_addopts) - {"-q", "--strict-markers"}:
        raise pytest.UsageError("Noncanonical configured addopts")
    scope = config.getini("testpaths")
    if not scope or list(config.args) != scope:
        raise pytest.UsageError("Full configured testpaths required")
    root = config.rootpath.resolve()
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise pytest.UsageError("Configuration must belong to the Git root")
    if config.inipath is None or not config.inipath.resolve().is_relative_to(root):
        raise pytest.UsageError("Owned configuration required")
    relative_config = str(config.inipath.resolve().relative_to(root))
    committed = subprocess.run(
        ["git", "-C", str(root), "cat-file", "blob", f"HEAD:{relative_config}"],
        capture_output=True,
        timeout=30,
        check=False,
    )
    if committed.returncode or committed.stdout != config.inipath.read_bytes():
        raise pytest.UsageError("Active configuration must match a tracked HEAD blob")
    # Pytest normalizes the tracked --strict-markers addopt into this override.
    # Explicit CLI overrides have already failed the invocation allowlist above.
    if config.option.override_ini and not (
        config.option.override_ini == ["strict_markers=true"]
        and "--strict-markers" in configured_addopts
    ):
        raise pytest.UsageError("Unapproved configuration overrides")
    output = config.getoption("partition_manifest")
    if (
        not isinstance(output, Path)
        or not output.is_absolute()
        or output.resolve().is_relative_to(root)
    ):
        raise pytest.UsageError("An absolute output outside the checkout is required")
    if output.exists() or git(root, "status", "--porcelain"):
        raise pytest.UsageError("Fresh output and clean checkout required")
    config.stash[STATE] = (git(root, "rev-parse", "HEAD"), False)


STATE = pytest.StashKey[tuple[str, bool]]()


def pytest_deselected(items: list[pytest.Item]) -> None:
    if items:
        config = items[0].config
        commit, _ = config.stash[STATE]
        config.stash[STATE] = (commit, True)
        raise pytest.UsageError("Deselection is forbidden for collection evidence")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    config = session.config
    if STATE not in config.stash:
        return
    commit, deselected = config.stash[STATE]
    if exitstatus != 0 or deselected or not session.items:
        return
    root = config.rootpath.resolve()
    if git(root, "status", "--porcelain") or git(root, "rev-parse", "HEAD") != commit:
        raise pytest.UsageError("Checkout changed during collection")
    if len(session.items) > MAX_NODES or len(session.items) != session.testscollected:
        raise pytest.UsageError("Collection bounds or completeness invalid")
    items = []
    nodes: set[str] = set()
    identities: set[tuple[str, str]] = set()
    for item in session.items:
        node = item.nodeid
        names = mangle_test_address(node)
        identity = (".".join(names[:-1]), bin_xml_escape(names[-1]))
        file = node.split("::", 1)[0]
        node_identity = compact(node)
        name_identity = compact(identity[1])
        compact_identity = (identity[0], str(name_identity["sha256"]))
        if (
            len(file.encode()) > 16 * 1024
            or len(identity[0].encode()) > 16 * 1024
            or str(node_identity["sha256"]) in nodes
            or compact_identity in identities
            or Path(file).is_absolute()
            or ".." in Path(file).parts
            or not file.endswith(".py")
        ):
            raise pytest.UsageError("Invalid or ambiguous collected identity")
        nodes.add(str(node_identity["sha256"]))
        identities.add(compact_identity)
        items.append(
            dict(
                node=node_identity, file=file, junit_classname=identity[0], junit_name=name_identity
            )
        )
    assert config.inipath is not None
    payload = dict(
        schema_version="inlet.partition-collection.v2",
        commit=commit,
        pytest_version=pytest.__version__,
        config_path=str(config.inipath.resolve().relative_to(root)),
        config_sha256=hashlib.sha256(config.inipath.read_bytes()).hexdigest(),
        historical_provenance=historical_provenance(root),
        collection_scope=config.getini("testpaths"),
        items=items,
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_BYTES:
        raise pytest.UsageError("Collection manifest exceeds bound")
    with config.getoption("partition_manifest").open("xb") as output:
        output.write(encoded)
