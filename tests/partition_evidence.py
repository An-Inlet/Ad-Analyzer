"""Offline exhaustive partition proposals; never execute or deselect tests."""

import argparse
import hashlib
import json
from decimal import Context, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Annotated, Any, Literal
from xml.etree import ElementTree as ET

from _pytest.junitxml import bin_xml_escape, mangle_test_address
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from tests.retired_execution_harness import BATCHES
from tests.retired_snapshot import PIN

Hex40 = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
Hex64 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
WRAPPER = "tests/test_retired_execution_snapshot.py::test_pinned_pre0086_execution_contracts"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class CompactText(Strict):
    sha256: Hex64
    utf8_bytes: Annotated[int, Field(gt=0)]
    display: str
    exact_text: str | None

    @classmethod
    def capture(cls, text: str) -> "CompactText":
        raw = text.encode("utf-8")
        return cls(
            sha256=hashlib.sha256(raw).hexdigest(),
            utf8_bytes=len(raw),
            display=raw[:256].decode("utf-8", errors="ignore"),
            exact_text=text if len(raw) <= 16 * 1024 else None,
        )

    @property
    def ref(self) -> str:
        return f"sha256:{self.sha256}:{self.utf8_bytes}"

    @model_validator(mode="after")
    def consistent(self) -> "CompactText":
        if len(self.display.encode()) > min(256, self.utf8_bytes):
            raise ValueError("invalid compact display")
        if (self.exact_text is not None) != (self.utf8_bytes <= 16 * 1024):
            raise ValueError("compact exact-text threshold mismatch")
        if self.exact_text is not None:
            raw = self.exact_text.encode()
            if (
                len(raw) != self.utf8_bytes
                or hashlib.sha256(raw).hexdigest() != self.sha256
                or raw[:256].decode("utf-8", errors="ignore") != self.display
            ):
                raise ValueError("compact exact-text integrity mismatch")
        return self


class Item(Strict):
    node: CompactText
    file: str
    junit_classname: str
    junit_name: CompactText

    @property
    def ref(self) -> str:
        return self.node.ref

    @model_validator(mode="after")
    def valid_file(self) -> "Item":
        if (
            not self.file.endswith(".py")
            or Path(self.file).is_absolute()
            or ".." in Path(self.file).parts
            or not self.junit_classname
            or len(self.file.encode()) > 16 * 1024
            or len(self.junit_classname.encode()) > 16 * 1024
        ):
            raise ValueError("invalid node/file/JUnit identity")
        if self.node.exact_text is not None:
            names = mangle_test_address(self.node.exact_text)
            if (
                self.file != self.node.exact_text.split("::", 1)[0]
                or self.junit_classname != ".".join(names[:-1])
                or self.junit_name != CompactText.capture(bin_xml_escape(names[-1]))
            ):
                raise ValueError("ambiguous or invalid exact node mapping")
        return self


class HistoricalProvenance(Strict):
    pin: Hex40
    retired_snapshot_sha256: Hex64
    manifests: dict[str, Hex64]


class Collection(Strict):
    schema_version: Literal["inlet.partition-collection.v2"]
    commit: Hex40
    pytest_version: str
    config_path: str
    config_sha256: Hex64
    historical_provenance: HistoricalProvenance | None
    collection_scope: Annotated[list[str], Field(min_length=1)]
    items: Annotated[list[Item], Field(min_length=1, max_length=20_000)]

    @model_validator(mode="after")
    def unique(self) -> "Collection":
        if len({i.node.sha256 for i in self.items}) != len(self.items):
            raise ValueError("duplicate node")
        if len({(i.junit_classname, i.junit_name.sha256) for i in self.items}) != len(self.items):
            raise ValueError("ambiguous JUnit identity")
        lengths: dict[str, int] = {}
        for item in self.items:
            for text in (item.node, item.junit_name):
                if text.sha256 in lengths and lengths[text.sha256] != text.utf8_bytes:
                    raise ValueError("inconsistent digest length")
                lengths[text.sha256] = text.utf8_bytes
        if Path(self.config_path).is_absolute() or ".." in Path(self.config_path).parts:
            raise ValueError("invalid configuration path")
        return self


class Timing(Strict):
    schema_version: Literal["inlet.partition-timing.v2"]
    commit: Hex40
    collection_sha256: Hex64
    junit_sha256: Hex64
    exit_code: Literal[0, 1]

    @field_validator("exit_code", mode="before")
    @classmethod
    def integer_exit(cls, value: Any) -> Any:
        if type(value) is not int:
            raise ValueError("integer terminal exit required")
        return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: BaseModel) -> bytes:
    return json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()


def bounded(path: Path, maximum: int) -> bytes:
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("input exceeds bound")
    return data


def parse_report(
    collection: Collection, timing: Timing, report: bytes
) -> dict[str, dict[str, Any]]:
    if (
        timing.commit != collection.commit
        or timing.collection_sha256 != digest(canonical(collection))
        or timing.junit_sha256 != digest(report)
        or len(report) > 64 * 1024 * 1024
    ):
        raise ValueError("timing provenance mismatch or report bound")
    if b"<!DOCTYPE" in report or b"<!ENTITY" in report:
        raise ValueError("XML declarations forbidden")
    root = ET.fromstring(report)
    if root.tag != "testsuites" or not list(root) or any(x.tag != "testsuite" for x in root):
        raise ValueError("complete testsuites report required")
    identities = {
        (i.junit_classname, i.junit_name.sha256, i.junit_name.utf8_bytes): i.ref
        for i in collection.items
    }
    result: dict[str, dict[str, Any]] = {}
    failures = 0
    aggregate = dict(tests=0, failures=0, errors=0, skipped=0)
    for suite in root:
        counts = dict(tests=0, failures=0, errors=0, skipped=0)
        for case in suite:
            if case.tag in {"properties", "system-out", "system-err"}:
                continue
            if case.tag != "testcase":
                raise ValueError("unsupported nested suite content")
            name = case.get("name", "").encode("utf-8")
            identity = (case.get("classname", ""), hashlib.sha256(name).hexdigest(), len(name))
            node = identities.get(identity)
            if node is None or node in result:
                raise ValueError("unknown or duplicate JUnit case")
            statuses = [x.tag for x in case if x.tag in {"failure", "error", "skipped"}]
            if len(statuses) > 1:
                raise ValueError("ambiguous testcase outcome")
            status = statuses[0] if statuses else "passed"
            counts["tests"] += 1
            if status != "passed":
                counts[
                    {"failure": "failures", "error": "errors", "skipped": "skipped"}[status]
                ] += 1
            raw = case.get("time")
            seconds = None
            if raw is not None:
                try:
                    seconds = Decimal(raw)
                except InvalidOperation as exc:
                    raise ValueError("invalid duration") from exc
                if (
                    not seconds.is_finite()
                    or seconds < 0
                    or seconds > Decimal("1000000000")
                    or len(seconds.as_tuple().digits) > 32
                    or int(str(seconds.as_tuple().exponent)) < -9
                ):
                    raise ValueError("invalid duration")
            result[node] = dict(
                status=status,
                seconds=str(seconds) if seconds is not None else None,
                passing_runtime_estimate=status == "passed" and seconds is not None,
            )
        for key, count in counts.items():
            if suite.get(key) != str(count):
                raise ValueError("JUnit summary mismatch")
        for key, count in counts.items():
            aggregate[key] += count
        failures += counts["failures"] + counts["errors"]
    for key, count in aggregate.items():
        if key in root.attrib and root.get(key) != str(count):
            raise ValueError("JUnit root summary mismatch")
    if set(result) != {i.ref for i in collection.items}:
        raise ValueError("missing JUnit case")
    if (timing.exit_code == 0) != (failures == 0):
        raise ValueError("terminal exit/outcome mismatch")
    return result


def historical(
    batches: dict[str, tuple[Path, int]],
    provenance: HistoricalProvenance | None,
) -> list[dict[str, Any]]:
    expected_paths = {
        name: str(path.relative_to(Path(__file__).resolve().parents[1]))
        for name, (path, _) in BATCHES.items()
    }
    if (
        provenance is None
        or set(provenance.manifests) != set(expected_paths.values())
        or provenance.pin != PIN
        or provenance.retired_snapshot_sha256
        != digest(bounded(Path(__file__).with_name("retired_snapshot.py"), 1024 * 1024))
    ):
        raise ValueError("historical source provenance mismatch")
    if {name: count for name, (_, count) in batches.items()} != {
        "original": 142,
        "ui_supplement": 19,
        "initial_forward": 88,
        "initial_native": 10,
        "configured_api": 34,
        "runtime_api": 40,
    }:
        raise ValueError("historical batch contract mismatch")
    seen: set[str] = set()
    entries = []
    for name, (path, expected) in batches.items():
        raw = bounded(path, 32 * 1024 * 1024)
        if digest(raw) != provenance.manifests[expected_paths[name]]:
            raise ValueError("historical manifest provenance mismatch")
        nodes = json.loads(raw)
        if (
            not isinstance(nodes, list)
            or len(nodes) != expected
            or any(not isinstance(n, str) or "::" not in n for n in nodes)
            or len(set(nodes)) != len(nodes)
            or seen.intersection(nodes)
        ):
            raise ValueError("historical node manifest mismatch")
        seen.update(nodes)
        entries.append(
            dict(
                batch=name,
                wrapper=f"{WRAPPER}[{name}]",
                child_count=expected,
                child_manifest_sha256=digest(raw),
                pin=PIN,
            )
        )
    if len(seen) != 333:
        raise ValueError("historical union mismatch")
    return entries


def build_candidate(
    collection: Collection,
    timing: Timing,
    report: bytes,
    *,
    shard_count: int,
    batches: dict[str, tuple[Path, int]] = BATCHES,
) -> dict[str, Any]:
    if type(shard_count) is not int or not 1 <= shard_count <= 32:
        raise ValueError("shard count outside bound")
    with localcontext(Context(prec=80)):
        return _build(collection, timing, report, shard_count=shard_count, batches=batches)


def _build(
    collection: Collection,
    timing: Timing,
    report: bytes,
    *,
    shard_count: int,
    batches: dict[str, tuple[Path, int]],
) -> dict[str, Any]:
    observations = parse_report(collection, timing, report)
    old = historical(batches, collection.historical_provenance)
    for entry in old:
        entry["wrapper_ref"] = CompactText.capture(entry["wrapper"]).ref
    wrappers = {entry["wrapper_ref"] for entry in old}
    actual = {
        i.ref
        for i in collection.items
        if i.node.exact_text is not None and i.node.exact_text.startswith(WRAPPER)
    }
    if actual != wrappers:
        raise ValueError("historical wrapper mismatch")
    files: dict[str, list[str]] = {}
    for item in collection.items:
        if item.ref not in wrappers:
            files.setdefault(item.file, []).append(item.ref)
    if len(files) < shard_count:
        raise ValueError("empty shards forbidden")
    costs = {
        file: sum((Decimal(observations[n]["seconds"] or "0") for n in nodes), Decimal(0))
        for file, nodes in files.items()
    }
    shards: list[dict[str, Any]] = [
        dict(index=i, files=[], node_refs=[]) for i in range(shard_count)
    ]
    totals = [Decimal(0)] * shard_count
    for file in sorted(files, key=lambda f: (-costs[f], f)):
        index = min(range(shard_count), key=lambda i: (totals[i], len(shards[i]["files"]), i))
        shards[index]["files"].append(file)
        shards[index]["node_refs"].extend(files[file])
        totals[index] += costs[file]
    order = {item.ref: i for i, item in enumerate(collection.items)}
    union = set(wrappers)
    for shard, total in zip(shards, totals, strict=True):
        nodes = shard["node_refs"]
        if not nodes or union.intersection(nodes):
            raise ValueError("nonexhaustive or overlapping partition")
        union.update(nodes)
        nodes.sort(key=order.__getitem__)
        shard.update(
            failed_count=sum(observations[n]["status"] == "failure" for n in nodes),
            error_count=sum(observations[n]["status"] == "error" for n in nodes),
            skipped_count=sum(observations[n]["status"] == "skipped" for n in nodes),
            measured_subtotal_seconds=str(total),
            unknown_count=sum(observations[n]["seconds"] is None for n in nodes),
            nonpassing_count=sum(observations[n]["status"] != "passed" for n in nodes),
        )
    if union != set(order):
        raise ValueError("partition union mismatch")
    return dict(
        schema_version="inlet.partition-candidate.v2",
        candidate_only=True,
        capacity_qualified=False,
        pass_qualified=False,
        commit=collection.commit,
        collection_sha256=timing.collection_sha256,
        junit_sha256=timing.junit_sha256,
        historical=old,
        current_shards=shards,
        observations=observations,
        identity_index={
            i.ref: dict(order=n, file=i.file, display=i.node.display)
            for n, i in enumerate(collection.items)
        },
        warning="Measured failed/skipped/unknown paths are not passing runtime forecasts",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("collection", "timing", "junit", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--shards", type=int, required=True)
    args = parser.parse_args()
    collection = Collection.model_validate_json(bounded(args.collection, 32 * 1024 * 1024))
    timing = Timing.model_validate_json(bounded(args.timing, 16 * 1024))
    candidate = build_candidate(
        collection, timing, bounded(args.junit, 64 * 1024 * 1024), shard_count=args.shards
    )
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(candidate, output, sort_keys=True, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
