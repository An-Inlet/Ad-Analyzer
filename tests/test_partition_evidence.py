"""Pure timing/coverage evidence and tiny genuine collect-only plugin contracts."""

import json
import os
import subprocess
import sys
from decimal import Context, localcontext
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pytest
from _pytest.junitxml import bin_xml_escape, mangle_test_address

from tests.partition_evidence import (
    WRAPPER,
    Collection,
    CompactText,
    HistoricalProvenance,
    Timing,
    build_candidate,
    canonical,
    digest,
    historical,
    parse_report,
)
from tests.retired_execution_harness import BATCHES
from tests.retired_snapshot import PIN


def evidence() -> tuple[dict[str, Any], ET.Element]:
    nodes = [f"{WRAPPER}[{name}]" for name in BATCHES] + [
        "tests/test_alpha.py::TestGroup::test_x[part::one.two]",
        "tests/test_alpha.py::TestOther::test_x[part::one.two]",
        "tests/test_beta.py::test_beta[0]",
    ]
    items = []
    root = ET.Element("testsuites")
    suite = ET.SubElement(
        root, "testsuite", tests=str(len(nodes)), failures="0", errors="0", skipped="0"
    )
    for node in nodes:
        names = mangle_test_address(node)
        item = dict(
            node=CompactText.capture(node).model_dump(),
            file=node.split("::", 1)[0],
            junit_classname=".".join(names[:-1]),
            junit_name=CompactText.capture(bin_xml_escape(names[-1])).model_dump(),
        )
        items.append(item)
        ET.SubElement(
            suite,
            "testcase",
            classname=".".join(names[:-1]),
            name=bin_xml_escape(names[-1]),
            time="1.250",
        )
    return dict(
        schema_version="inlet.partition-collection.v2",
        commit="a" * 40,
        pytest_version=pytest.__version__,
        config_path="pyproject.toml",
        config_sha256="b" * 64,
        historical_provenance=dict(
            pin=PIN,
            retired_snapshot_sha256=digest(
                Path(__file__).with_name("retired_snapshot.py").read_bytes()
            ),
            manifests={
                str(path.relative_to(Path(__file__).resolve().parents[1])): digest(
                    path.read_bytes()
                )
                for path, _ in BATCHES.values()
            },
        ),
        collection_scope=["tests"],
        items=items,
    ), root


def candidate(raw: dict[str, Any], root: ET.Element, **changes: Any) -> dict[str, Any]:
    collection = Collection.model_validate(raw)
    report = ET.tostring(root)
    timing = dict(
        schema_version="inlet.partition-timing.v2",
        commit=collection.commit,
        collection_sha256=digest(canonical(collection)),
        junit_sha256=digest(report),
        exit_code=0,
    )
    timing.update(changes)
    return build_candidate(collection, Timing.model_validate(timing), report, shard_count=2)


def test_exact_class_parameter_mapping_disjoint_file_balance() -> None:
    raw, root = evidence()
    result = candidate(raw, root)
    with localcontext(Context(prec=2)):
        assert candidate(raw, root) == result
    assert result["candidate_only"] and not result["capacity_qualified"]
    assert not result["pass_qualified"]
    groups = [set(s["node_refs"]) for s in result["current_shards"]]
    groups.append({x["wrapper_ref"] for x in result["historical"]})
    assert set.union(*groups) == {CompactText.model_validate(i["node"]).ref for i in raw["items"]}
    assert sum(map(len, groups)) == len(set.union(*groups))
    assert result["current_shards"][0]["files"] == ["tests/test_alpha.py"]
    assert len(result["current_shards"][0]["node_refs"]) == 2
    assert len(result["historical"]) == 18
    assert sum(x["child_count"] for x in result["historical"]) == 405


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "unknown",
        "ambiguous",
        "extra_field",
        "bad_file",
        "summary",
        "wrapper",
        "time",
        "nan",
        "precision",
    ],
)
def test_invalid_evidence_fails_closed(change: str) -> None:
    raw, root = evidence()
    suite = root[0]
    if change == "missing":
        suite.remove(suite[-1])
        suite.set("tests", "5")
    elif change == "duplicate":
        suite[-1].set("classname", suite[-2].get("classname", ""))
        suite[-1].set("name", suite[-2].get("name", ""))
    elif change == "unknown":
        suite[-1].set("classname", "unknown")
    elif change == "ambiguous":
        raw["items"][-1] = raw["items"][-2]
    elif change == "extra_field":
        raw["extra"] = True
    elif change == "bad_file":
        raw["items"][-1]["file"] = "../bad.py"
    elif change == "summary":
        suite.set("tests", "999")
    elif change == "wrapper":
        raw["items"].pop(0)
        suite.remove(suite[0])
        suite.set("tests", "5")
    else:
        suite[-1].set("time", {"time": "-1", "nan": "NaN", "precision": "1e-50"}[change])
    with pytest.raises(ValueError):
        candidate(raw, root)


@pytest.mark.parametrize("field", ["commit", "collection_sha256", "junit_sha256", "exit_code"])
def test_timing_provenance_and_terminal_exit(field: str) -> None:
    raw, root = evidence()
    with pytest.raises(ValueError):
        candidate(
            raw,
            root,
            **{field: 1 if field == "exit_code" else "c" * (40 if field == "commit" else 64)},
        )


def test_failed_skipped_missing_time_are_not_passing_forecasts() -> None:
    raw, root = evidence()
    suite = root[0]
    suite.set("failures", "1")
    suite.set("skipped", "1")
    ET.SubElement(suite[-1], "failure")
    ET.SubElement(suite[-2], "skipped")
    suite[-3].attrib.pop("time")
    result = candidate(raw, root, exit_code=1)
    observations = list(result["observations"].values())[-3:]
    assert all(not o["passing_runtime_estimate"] for o in observations)
    assert observations[0]["seconds"] is None
    assert sum(s["unknown_count"] for s in result["current_shards"]) == 1
    assert sum(s["nonpassing_count"] for s in result["current_shards"]) == 2


@pytest.mark.parametrize("bad", ["count", "cross_duplicate", "missing_batch"])
def test_child_manifest_contract(tmp_path: Path, bad: str) -> None:
    copied = {}
    for name, (path, count) in BATCHES.items():
        target = tmp_path / path.name
        target.write_bytes(path.read_bytes())
        copied[name] = (target, count)
    if bad == "missing_batch":
        del copied["original"]
    else:
        path, count = copied["ui_supplement"]
        values = json.loads(path.read_text())
        if bad == "count":
            values.pop()
        else:
            values[0] = json.loads(copied["original"][0].read_text())[0]
        path.write_text(json.dumps(values))
    with pytest.raises(ValueError):
        raw, _ = evidence()
        historical(copied, HistoricalProvenance.model_validate(raw["historical_provenance"]))


@pytest.mark.parametrize(
    "mode",
    [
        "valid",
        "execute",
        "filter",
        "override",
        "config",
        "env",
        "noconftest",
        "lastfailed",
        "deselect",
        "ignored_config",
        "historical",
        "ignored_historical",
        "partial_historical",
        "strict_markers",
        "strict_override",
        "strict_long_override",
        "oversized",
    ],
)
def test_genuine_collect_only_plugin(tmp_path: Path, mode: str) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "tests").mkdir()
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    (repo / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")
    (repo / "tests/test_small.py").write_text(
        "import pytest\nfrom pathlib import Path\n"
        "@pytest.fixture(autouse=True)\ndef no_run():\n Path('EXECUTED').touch()\n"
        "class TestGroup:\n @pytest.mark.parametrize('x',[1,2],ids=['a::b.c','d'])\n"
        " def test_case(self,x):\n  assert x\n"
    )
    if mode == "oversized":
        (repo / "tests/test_small.py").write_text(
            "import pytest\nfrom pathlib import Path\n"
            "@pytest.fixture(autouse=True)\ndef no_run():\n Path('EXECUTED').touch()\n"
            "@pytest.mark.parametrize('x',[1],ids=['x'*(8*1024*1024+1)])\n"
            "def test_big(x):\n assert x\n"
        )
    if mode.startswith("strict_"):
        (repo / "pytest.ini").unlink()
        (repo / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\naddopts = "-q --strict-markers"\ntestpaths = ["tests"]\n'
        )
    if mode == "ignored_config":
        (repo / "pytest.ini").unlink()
        (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\npytest.ini\n")
        (repo / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')
    if mode in {"historical", "ignored_historical", "partial_historical"}:
        for index, (path, _) in enumerate(BATCHES.values()):
            if mode == "partial_historical" and index:
                break
            target = repo / path.relative_to(Path(__file__).resolve().parents[1])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
        (repo / "tests/retired_snapshot.py").write_bytes(
            Path(__file__).with_name("retired_snapshot.py").read_bytes()
        )
        if mode == "ignored_historical":
            with (repo / ".gitignore").open("a") as stream:
                stream.write("tests/fixtures/retired_execution/nodes-2155ff3.json\n")
    if mode == "deselect":
        (repo / "conftest.py").write_text(
            "def pytest_collection_modifyitems(config,items):\n"
            " config.hook.pytest_deselected(items=items[:1])\n del items[:1]\n"
        )
    for git_args in [
        ("init", "-q"),
        ("add", "."),
        (
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ),
    ]:
        subprocess.run(["git", *git_args], cwd=repo, check=True, capture_output=True)
    if mode == "ignored_config":
        (repo / "pytest.ini").write_text(
            "[pytest]\ntestpaths = tests\npython_files = test_small.py\n"
        )
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo)
        assert status == b""
    output = tmp_path / "collection.json"
    args = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "inlet_partition_collection",
        "--partition-manifest",
        str(output),
    ]
    if mode != "execute":
        args.append("--collect-only")
    additions = {
        "filter": ["-k", "case"],
        "override": ["-o", "testpaths=tests"],
        "strict_override": ["-o", "strict_markers=true"],
        "strict_long_override": ["--override-ini", "strict_markers=true"],
        "config": ["-c", "pytest.ini"],
        "noconftest": ["--noconftest"],
        "lastfailed": ["--lf"],
    }
    args.extend(additions.get(mode, []))
    env = dict(
        os.environ,
        PYTHONPATH=str(Path(__file__).resolve().parents[1] / "scripts"),
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
    )
    env.pop("PYTEST_ADDOPTS", None)
    if mode == "env":
        env["PYTEST_ADDOPTS"] = "-k case"
    run = subprocess.run(args, cwd=repo, env=env, capture_output=True, text=True, timeout=30)
    assert not (repo / "EXECUTED").exists()
    if mode in {"valid", "historical", "strict_markers", "oversized"}:
        assert run.returncode == 0, run.stdout + run.stderr
        manifest = Collection.model_validate_json(output.read_bytes())
        if mode == "historical":
            expected, _ = evidence()
            assert manifest.historical_provenance == HistoricalProvenance.model_validate(
                expected["historical_provenance"]
            )
        else:
            assert manifest.historical_provenance is None
        if mode == "oversized":
            expected_node = "tests/test_small.py::test_big[" + "x" * (8 * 1024 * 1024 + 1) + "]"
            assert len(output.read_bytes()) < 4096
            assert len(manifest.items) == 1
            assert manifest.items[0].node == CompactText.capture(expected_node)
            assert manifest.items[0].node.exact_text is None
            assert manifest.items[0].file == "tests/test_small.py"
            return
        assert [i.node.exact_text for i in manifest.items] == [
            "tests/test_small.py::TestGroup::test_case[a::b.c]",
            "tests/test_small.py::TestGroup::test_case[d]",
        ]
    else:
        assert run.returncode != 0
        assert not output.exists()
        if mode == "ignored_config":
            assert "tracked HEAD blob" in run.stderr


@pytest.mark.parametrize("change", ["truncated", "entity", "ambiguous_outcome", "nested"])
def test_report_structure_rejected(change: str) -> None:
    raw, root = evidence()
    collection = Collection.model_validate(raw)
    if change == "ambiguous_outcome":
        ET.SubElement(root[0][-1], "failure")
        ET.SubElement(root[0][-1], "skipped")
    if change == "nested":
        ET.SubElement(root[0], "testsuite")
    report = ET.tostring(root)
    if change == "truncated":
        report = report[:-10]
    elif change == "entity":
        report = b'<!DOCTYPE testsuites [<!ENTITY x "bad">]>' + report
    timing = Timing(
        schema_version="inlet.partition-timing.v2",
        commit=collection.commit,
        collection_sha256=digest(canonical(collection)),
        junit_sha256=digest(report),
        exit_code=0,
    )
    with pytest.raises((ValueError, ET.ParseError)):
        parse_report(collection, timing, report)


def test_distinct_nodes_with_same_xml_identity_reject() -> None:
    raw, _ = evidence()
    raw["items"][-1]["junit_classname"] = raw["items"][-2]["junit_classname"]
    raw["items"][-1]["junit_name"] = raw["items"][-2]["junit_name"]
    with pytest.raises(ValueError, match="ambiguous"):
        Collection.model_validate(raw)


@pytest.mark.parametrize("count", [0, 3, 33, True])
def test_invalid_or_empty_partition_rejected(count: int) -> None:
    raw, root = evidence()
    collection = Collection.model_validate(raw)
    report = ET.tostring(root)
    timing = Timing(
        schema_version="inlet.partition-timing.v2",
        commit=collection.commit,
        collection_sha256=digest(canonical(collection)),
        junit_sha256=digest(report),
        exit_code=0,
    )
    with pytest.raises(ValueError):
        build_candidate(collection, timing, report, shard_count=count)


def test_zero_and_unknown_duration_files_stay_disjoint() -> None:
    raw, root = evidence()
    for case in root[0]:
        case.attrib.pop("time")
    result = candidate(raw, root)
    assert all(
        s["node_refs"] and s["unknown_count"] == len(s["node_refs"])
        for s in result["current_shards"]
    )


@pytest.mark.parametrize("field", ["tests", "failures", "errors", "skipped"])
def test_contradictory_root_totals_reject(field: str) -> None:
    raw, root = evidence()
    root.set(field, "99")
    with pytest.raises(ValueError, match="root summary"):
        candidate(raw, root)


def test_matching_optional_root_totals_accept() -> None:
    raw, root = evidence()
    root.attrib.update(tests=str(len(raw["items"])), failures="0", errors="0", skipped="0")
    assert candidate(raw, root)["candidate_only"]


@pytest.mark.parametrize("change", ["absent", "pin", "source", "paths", "same_count"])
def test_historical_capture_binding_rejects_substitution(tmp_path: Path, change: str) -> None:
    raw, root = evidence()
    if change == "same_count":
        batches = dict(BATCHES)
        old, count = batches["original"]
        nodes = json.loads(old.read_text())
        nodes[0] = "tests/test_other.py::test_substituted[sqlite]"
        altered = tmp_path / old.name
        altered.write_text(json.dumps(nodes))
        batches["original"] = (altered, count)
        with pytest.raises(ValueError, match="manifest provenance"):
            historical(batches, HistoricalProvenance.model_validate(raw["historical_provenance"]))
        return
    if change == "absent":
        raw["historical_provenance"] = None
    elif change == "pin":
        raw["historical_provenance"]["pin"] = "c" * 40
    elif change == "source":
        raw["historical_provenance"]["retired_snapshot_sha256"] = "c" * 64
    else:
        raw["historical_provenance"]["manifests"]["unknown.json"] = "c" * 64
    with pytest.raises(ValueError, match="historical source"):
        candidate(raw, root)


def large_evidence() -> tuple[dict[str, Any], ET.Element]:
    raw, root = evidence()
    prefix = "tests/test_alpha.py::TestGroup::test_large[" + "x" * (8 * 1024 * 1024 + 1)
    for index, suffix in ((-2, "a]"), (-1, "b]")):
        node = prefix + suffix
        names = mangle_test_address(node)
        raw["items"][index] = dict(
            node=CompactText.capture(node).model_dump(),
            file="tests/test_alpha.py",
            junit_classname=".".join(names[:-1]),
            junit_name=CompactText.capture(bin_xml_escape(names[-1])).model_dump(),
        )
        root[0][index].set("classname", ".".join(names[:-1]))
        root[0][index].set("name", bin_xml_escape(names[-1]))
    # Preserve two distinct current files for the two-group candidate.
    node = "tests/test_beta.py::test_unicode[é::a.b]"
    names = mangle_test_address(node)
    raw["items"][-3] = dict(
        node=CompactText.capture(node).model_dump(),
        file="tests/test_beta.py",
        junit_classname=".".join(names[:-1]),
        junit_name=CompactText.capture(bin_xml_escape(names[-1])).model_dump(),
    )
    root[0][-3].set("classname", ".".join(names[:-1]))
    root[0][-3].set("name", bin_xml_escape(names[-1]))
    return raw, root


def test_oversized_same_display_distinct_suffix_maps_compactly() -> None:
    raw, root = large_evidence()
    assert raw["items"][-1]["node"]["display"] == raw["items"][-2]["node"]["display"]
    assert raw["items"][-1]["node"]["utf8_bytes"] == raw["items"][-2]["node"]["utf8_bytes"]
    result = candidate(raw, root)
    assert len(result["observations"]) == 21
    assert len(json.dumps(result).encode()) < 20_000
    refs = [n for group in result["current_shards"] for n in group["node_refs"]]
    assert len(refs) == len(set(refs)) == 3
    assert len(result["identity_index"]) == 21


@pytest.mark.parametrize("change", ["digest", "length", "same_digest", "duplicate", "class"])
def test_large_mapping_corruption_rejected(change: str) -> None:
    raw, root = large_evidence()
    if change == "digest":
        raw["items"][-1]["junit_name"]["sha256"] = "c" * 64
    elif change == "length":
        raw["items"][-1]["junit_name"]["utf8_bytes"] += 1
    elif change == "same_digest":
        raw["items"][-1]["node"]["sha256"] = raw["items"][-2]["junit_name"]["sha256"]
    elif change == "duplicate":
        raw["items"][-1]["node"] = raw["items"][-2]["node"]
    else:
        root[0][-1].set("classname", "foreign.Class")
    with pytest.raises(ValueError):
        candidate(raw, root)


@pytest.mark.parametrize("size", [16 * 1024, 16 * 1024 + 1])
def test_exact_text_threshold_and_unicode_display(size: int) -> None:
    value = "é" * (size // 2) + "x" * (size % 2)
    compact = CompactText.capture(value)
    assert compact.utf8_bytes == size
    assert len(compact.display.encode()) == 256
    assert (compact.exact_text is not None) == (size <= 16 * 1024)
    odd = CompactText.capture("a" + value)
    assert len(odd.display.encode()) == 255


@pytest.mark.parametrize("field", ["sha256", "utf8_bytes", "display", "exact_text"])
def test_compact_short_integrity(field: str) -> None:
    raw = CompactText.capture("abc").model_dump()
    raw[field] = {"sha256": "c" * 64, "utf8_bytes": 4, "display": "ab", "exact_text": None}[field]
    with pytest.raises(ValueError):
        CompactText.model_validate(raw)


def test_legacy_manifest_version_is_not_silently_converted() -> None:
    raw, root = evidence()
    raw["schema_version"] = "inlet.partition-collection.v1"
    with pytest.raises(ValueError):
        candidate(raw, root)


@pytest.mark.parametrize("change", ["missing_fifth", "substituted_fifth"])
def test_fifth_manifest_requires_exact_captured_provenance(tmp_path: Path, change: str) -> None:
    raw, root = evidence()
    path, count = BATCHES["configured_api"]
    assert count == 34
    relative = str(path.relative_to(Path(__file__).resolve().parents[1]))
    if change == "missing_fifth":
        del raw["historical_provenance"]["manifests"][relative]
        with pytest.raises(ValueError, match="historical source provenance"):
            candidate(raw, root)
    else:
        nodes = json.loads(path.read_text())
        nodes[0] = "tests/test_substituted.py::test_other[sqlite]"
        replaced = tmp_path / path.name
        replaced.write_text(json.dumps(nodes))
        batches = {**BATCHES, "configured_api": (replaced, count)}
        with pytest.raises(ValueError, match="historical manifest provenance"):
            historical(batches, HistoricalProvenance.model_validate(raw["historical_provenance"]))

@pytest.mark.parametrize("change", ["missing_sixth", "substituted_sixth"])
def test_sixth_manifest_requires_exact_captured_provenance(tmp_path: Path, change: str) -> None:
    raw, root = evidence()
    path, count = BATCHES["runtime_api"]
    assert count == 40
    relative = str(path.relative_to(Path(__file__).resolve().parents[1]))
    if change == "missing_sixth":
        del raw["historical_provenance"]["manifests"][relative]
        with pytest.raises(ValueError, match="historical source provenance"):
            candidate(raw, root)
    else:
        nodes = json.loads(path.read_text())
        nodes[0] = "tests/test_substituted.py::test_other[sqlite]"
        replaced = tmp_path / path.name
        replaced.write_text(json.dumps(nodes))
        batches = {**BATCHES, "runtime_api": (replaced, count)}
        with pytest.raises(ValueError, match="historical manifest provenance"):
            historical(batches, HistoricalProvenance.model_validate(raw["historical_provenance"]))


@pytest.mark.parametrize("change", ["missing", "substituted"])
def test_reported_api_manifest_requires_exact_provenance(tmp_path: Path, change: str) -> None:
    raw, root = evidence()
    path, count = BATCHES["configured_reported_api"]
    assert count == 14
    relative = str(path.relative_to(Path(__file__).resolve().parents[1]))
    if change == "missing":
        del raw["historical_provenance"]["manifests"][relative]
        with pytest.raises(ValueError, match="historical source provenance"):
            candidate(raw, root)
    else:
        nodes = json.loads(path.read_text())
        nodes[0] = "tests/test_substituted.py::test_other[sqlite]"
        replaced = tmp_path / path.name
        replaced.write_text(json.dumps(nodes))
        batches = {**BATCHES, "configured_reported_api": (replaced, count)}
        with pytest.raises(ValueError, match="historical manifest provenance"):
            historical(batches, HistoricalProvenance.model_validate(raw["historical_provenance"]))
