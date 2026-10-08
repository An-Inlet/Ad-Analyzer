"""Full pytest includes the exact frozen historical assertions, separately labeled."""

from pathlib import Path

import pytest

from tests.retired_execution_harness import BATCHES, qualify


@pytest.mark.historical_execution_snapshot
@pytest.mark.parametrize("batch", tuple(BATCHES))
def test_pinned_pre0086_execution_contracts(tmp_path: Path, batch: str) -> None:
    qualify(Path(__file__).resolve().parents[1], tmp_path / "retired-execution", batch)


def test_every_retired_invocation_has_explicit_historical_and_current_coverage() -> None:
    import ast
    import json

    from tests.retired_execution_harness import MANIFEST
    from tests.retired_snapshot import PIN, git

    root = Path(__file__).resolve().parents[1]
    records = json.loads((MANIFEST.parent / "coverage-map.json").read_text())
    nodes = [node for manifest, _ in BATCHES.values()
             for node in json.loads(manifest.read_text())]
    mapped = [node for record in records for node in record["historical_nodes"]]
    assert sorted(mapped) == sorted(nodes) and len(set(mapped)) == len(nodes)
    for record in records:
        assert record["reason"] and record["current_coverage"]
        path, name = record["preserved_local_callable"].split("::")
        definitions = {item.name for item in ast.parse((root / path).read_text()).body
                       if isinstance(item, ast.FunctionDef)}
        assert name in definitions
        original_path, original_name = record["original_function"].split("::")
        frozen = ast.parse(git(root, "show", f"{PIN}:{original_path}"))
        old_function = next(item for item in frozen.body
                            if isinstance(item, ast.FunctionDef) and item.name == original_name)
        current_function = next(item for item in ast.parse((root / path).read_text()).body
                                if isinstance(item, ast.FunctionDef) and item.name == name)
        current_function.name = original_name
        assert ast.dump(current_function) == ast.dump(old_function), record["original_function"]
        assert record["original_function"].split("::")[1] not in definitions
        for current in record["current_coverage"]:
            filename, function = current.split("::")
            names = {item.name for item in ast.parse((root / filename).read_text()).body
                     if isinstance(item, ast.FunctionDef)}
            assert function in names
