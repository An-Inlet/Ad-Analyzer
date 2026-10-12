"""Real retained readers and explicit new-writer/old-reader boundaries."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from app.planning_documents.documents import PlanVersion
from app.planning_documents.storage import (
    canonical,
    document_for_row,
    export_row,
    plan_version_storage_pair,
)

FIXTURES = Path("tests/fixtures/selected_provenance")


def interim() -> dict[str, Any]:
    raw = (FIXTURES / "interim-enriched-v1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        "766bf3925c3c1b9e3efacccd780d6fcec581fc257692263b552c6eef598bd73b"
    )
    return json.loads(raw)  # type: ignore[no-any-return]


def version_two() -> PlanVersion:
    return PlanVersion.model_validate({**interim(), "schema_version": "inlet.plan-version.v2"})


def row(document: PlanVersion) -> dict[str, Any]:
    return dict(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=document.version,
        input_revision=document.inputs.revision,
        parent_digest=document.parent_digest,
        digest=document.digest(),
        canonical_json=canonical(document),
        generator_version=document.generator_version,
        policy_version=document.policy_version,
        actor_id=document.generated_by,
        generated_at=document.generated_at,
        valid_until=document.valid_until,
        privacy_revision=document.evidence[0].privacy_revision,
    )


@pytest.mark.parametrize("kind", ["original", "interim", "v2"])
def test_actual_storage_and_row_export_reader_preserves_supported_documents(kind: str) -> None:
    payload = (
        json.loads((FIXTURES / "prechange-v5.json").read_text())
        if kind == "original"
        else interim()
    )
    if kind == "v2":
        payload["schema_version"] = "inlet.plan-version.v2"
    document = PlanVersion.model_validate(payload)
    stored = row(document)
    assert document_for_row("planning_document_versions", stored) == document
    assert export_row("planning_document_versions", stored)["document"] == payload
    assert (
        canonical(document_for_row("planning_document_versions", stored))
        == stored["canonical_json"]
    )
    if kind == "interim":
        assert (
            document.digest() == "a8b52c7cda6f3de5a812100238c36b2def9459f25610c5f4cea005f97ec49ae2"
        )
        with pytest.raises(ValueError, match="requires plan-version.v2"):
            plan_version_storage_pair(document)
    else:
        assert plan_version_storage_pair(document) == (stored["canonical_json"], stored["digest"])
    bad = {**stored, "digest": "f" * 64}
    with pytest.raises(ValueError, match="digest mismatch"):
        document_for_row("planning_document_versions", bad)
    with pytest.raises(ValueError, match="ownership/content mismatch"):
        document_for_row("planning_document_versions", {**stored, "workspace_id": 999})


@pytest.mark.parametrize("attack", ["unknown", "missing", "none"])
def test_unknown_or_incomplete_new_schema_is_refused(attack: str) -> None:
    payload = version_two().model_dump(mode="json")
    if attack == "unknown":
        payload["schema_version"] = "inlet.plan-version.v99"
    elif attack == "none":
        payload["selected_reporting_proof"] = None
    else:
        next(
            a["capture_pin"]
            for a in payload["selected_reporting_proof"]["accounts"]
            if a["capture_pin"]
        ).pop("observation_provenance")
    with pytest.raises(ValueError):
        PlanVersion.model_validate(payload)


def test_prior_strict_dto_reader_accepts_original_and_refuses_enrichment(tmp_path: Path) -> None:
    # Exact prior DTO definitions, isolated module graph; unchanged transitive helpers.
    # This is not a deployment rollback drill or a claim about a complete old image.
    for name, digest in (
        (
            "prechange-documents.py.txt",
            "c153a02ac1fd898097ef3e7b8d440a12166c667ca9ce86943cdffaadfa0ed7ce",
        ),
        (
            "prechange-selected-plan-contracts.py.txt",
            "451c212c45ceb79a720e1e15b756ff3c27e85575e9153dc8a3f3c8f0cc743da3",
        ),
    ):
        assert hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() == digest
    script = tmp_path / "prior_reader.py"
    script.write_text("""
import importlib.util,json,sys,types
from pathlib import Path
from pydantic import ValidationError
root=Path(sys.argv[1]); fixtures=root/'tests/fixtures/selected_provenance'
sources=[
 ('app.planning_documents.selected_plan_contracts','prechange-selected-plan-contracts.py.txt'),
 ('app.planning_documents.documents','prechange-documents.py.txt'),
]
for module,name in sources:
    value=types.ModuleType(module);value.__file__=str(fixtures/name);sys.modules[module]=value
    exec(compile((fixtures/name).read_text(),str(fixtures/name),'exec'),value.__dict__)
PlanVersion=sys.modules['app.planning_documents.documents'].PlanVersion
original=json.loads((fixtures/'prechange-v5.json').read_text())
assert PlanVersion.model_validate(original).model_dump(mode='json')==original
interim=json.loads((fixtures/'interim-enriched-v1.json').read_text())
for payload in (interim,{**interim,'schema_version':'inlet.plan-version.v2'}):
    try:PlanVersion.model_validate(payload)
    except ValidationError:pass
    else:raise AssertionError('unsupported prior reader accepted enriched document')
print('PASS original accepted; interim/v2 refused')
""")
    result = subprocess.run(
        [sys.executable, str(script), str(Path.cwd())],
        env={**os.environ, "PYTHONPATH": str(Path.cwd())},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS original accepted; interim/v2 refused"
