"""Closed original prepare/approve/consent phases; current parent owns all DDL."""

import json
import os
import re
import sys
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from app import advertising_capabilities
from app.campaign_review.storage import LocalMediaStore
from app.publication import customer_intents, execution_mandates, provider_service
from app.publication.provider_contracts import ProviderPublishPlan
from app.publication.provider_models import (
    ProviderQualificationRecord,
    ProviderReviewApproval,
)
from scripts.inlet_producer_source_lifetime import SourceLifetime
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.financial_origin_retained_fixture import SourceIds, current_policy
from tests.provider_ddl_boundary import (
    Mode,
    before_phase,
    canonical,
    digest,
    directory,
    owned,
    read,
    shape,
    snapshot,
)
from tests.retired_snapshot import PIN, extract, run_bounded
from tests.test_commerce_measurement import NOW


@dataclass(frozen=True)
class QualificationIds:
    mode: str
    workspace_id: int
    actor_id: str
    source_draft_id: str
    source_revision: int
    qualification_id: str
    review_id: str
    review_digest: str
    plan_digest: str


@dataclass(frozen=True)
class ConsentIds:
    mode: str
    workspace_id: int
    actor_id: str
    provider_mandate_id: str
    revision: int
    provider_policy_digest: str
    provider_consent_id: str
    ledger_id: str


def validate_output(raw: dict[str, Any], mode: Mode) -> QualificationIds | ConsentIds:
    cls = ConsentIds if mode == "execution_consent" else QualificationIds
    assert set(raw) == set(cls.__dataclass_fields__) and raw["mode"] == mode
    for key, value in raw.items():
        if key == "mode":
            continue
        if key in {"workspace_id", "revision", "source_revision"}:
            assert type(value) is int and value > 0
            if key != "workspace_id":
                assert value == 1
        else:
            assert type(value) is str and re.fullmatch(
                r"[a-f0-9]{64}" if key.endswith("digest") else r"[a-f0-9]{32}", value
            )
    return cls(**raw)


def qualification_rows(
    source: SourceIds,
    result: QualificationIds,
    plan: ProviderPublishPlan,
    approved: bool,
) -> dict[str, list[dict[str, Any]]]:
    review = plan.review
    evidence = review.qualification
    assert evidence is not None
    assert evidence.observed_at == NOW and evidence.expires_at == NOW + timedelta(minutes=5)
    assert review.scope.workspace_id == source.workspace_id
    assert review.scope.account.account_id == source.account_id
    assert review.source.draft_id == source.source_draft_id
    assert review.source.revision == source.source_draft_revision
    return dict(
        provider_qualifications=[
            dict(
                id=result.qualification_id,
                workspace_id=source.workspace_id,
                account_id=source.account_id,
                integration_id=review.scope.account.connection_id,
                draft_id=source.source_draft_id,
                source_revision=source.source_draft_revision,
                provider="google_ads",
                api_version="v25",
                binding_digest=review.configuration_binding(),
                evidence=evidence.model_dump(mode="json"),
                observed_at=NOW,
                expires_at=NOW + timedelta(minutes=5),
                created_by=source.actor_id,
            )
        ],
        provider_reviews=[
            dict(
                id=result.review_id,
                workspace_id=source.workspace_id,
                qualification_id=result.qualification_id,
                draft_id=source.source_draft_id,
                source_revision=source.source_draft_revision,
                review_digest=review.digest(),
                plan_digest=plan.digest(),
                review=review.model_dump(mode="json"),
                plan=plan.model_dump(mode="json"),
                created_by=source.actor_id,
                created_at=NOW,
            )
        ],
        provider_review_approvals=[
            dict(
                review_id=result.review_id,
                workspace_id=source.workspace_id,
                review_digest=review.digest(),
                plan_digest=plan.digest(),
                actor=source.actor_id,
                approved_at=NOW,
            )
        ]
        if approved
        else [],
    )


def checked_qualification_rows(
    actual: dict[str, list[dict[str, Any]]],
    source: SourceIds,
    result: QualificationIds,
    plan: ProviderPublishPlan,
    approved: bool,
) -> dict[str, list[dict[str, Any]]]:
    expected = qualification_rows(source, result, plan, approved)
    for table, rows in expected.items():
        assert actual[table] == rows
    return expected


def phase(
    engine: Engine,
    source_ids: SourceIds,
    source_artifacts: Path,
    artifacts: Path,
    mode: Mode,
    *,
    provider_mandate_id: str | None = None,
) -> QualificationIds | ConsentIds:
    assert not advertising_capabilities.advertising_writes_enabled()
    directory(artifacts)
    directory(source_artifacts)
    assert source_artifacts == artifacts.parent / "original"
    raw_source = asdict(source_ids)
    assert read(source_artifacts / "ids.json") == raw_source
    directory(source_artifacts / "media")
    root = Path(__file__).resolve().parents[1]
    schema = owned(engine, mode, root)
    with Session(engine) as db:
        current_policy(db, source_ids)
    before = snapshot(engine)
    before_phase(before, raw_source, mode, provider_mandate_id, schema)
    physical = shape(engine)
    artifacts.mkdir()
    (artifacts / "input.json").write_text(
        json.dumps(
            dict(
                mode=mode,
                source=raw_source,
                mandate_id=provider_mandate_id,
                schema_digest=physical,
                rows_digest=digest(before),
            )
        )
    )
    with SourceLifetime.open("provider_ddl", artifacts) as lifetime:
        extract(root, lifetime.source)
        lifetime.extracted()
        lifetime.child_started()
        log = artifacts / "producer.log"
        code = run_bounded(
            [
                sys.executable,
                str(root / "tests/fixtures/retired_execution/provider_ddl_seed_driver.py"),
                schema,
                str(artifacts),
            ],
            lifetime.source,
            dict(os.environ, INLET_RETIRED_EXECUTION_CHILD=PIN, PYTHONPATH=str(lifetime.source)),
            log,
            180,
        )
        lifetime.after_reaped(code)
    assert code == 0, log.read_text()[-6000:]
    assert owned(engine, mode, root) == schema and shape(engine) == physical
    result = validate_output(read(artifacts / "ids.json"), mode)
    assert result.workspace_id == source_ids.workspace_id and result.actor_id == source_ids.actor_id
    after = snapshot(engine)
    expected = deepcopy(before)
    with Session(engine) as db:
        current_policy(db, source_ids)
        if isinstance(result, QualificationIds):
            row, plan = provider_service.checked_review(
                db,
                source_ids.workspace_id,
                result.review_id,
                source_ids.actor_id,
                LocalMediaStore(source_artifacts / "media"),
                lambda: NOW,
            )
            assert row.source_revision == result.source_revision == source_ids.source_draft_revision
            assert row.draft_id == result.source_draft_id == source_ids.source_draft_id
            assert row.review_digest == result.review_digest and plan.digest() == result.plan_digest
            assert (
                row.qualification_id == result.qualification_id
                and row.created_by == source_ids.actor_id
            )
            qualification = db.get(ProviderQualificationRecord, result.qualification_id)
            assert qualification and qualification.created_by == source_ids.actor_id
            approval = db.get(ProviderReviewApproval, row.id)
            if mode == "qualification_approved":
                assert approval and approval.actor == source_ids.actor_id
                assert approval.workspace_id == source_ids.workspace_id
                assert approval.review_digest == result.review_digest
                assert approval.plan_digest == result.plan_digest and approval.approved_at == NOW
            else:
                assert approval is None
            expected.update(
                checked_qualification_rows(
                    after,
                    source_ids,
                    result,
                    plan,
                    mode == "qualification_approved",
                )
            )
        else:
            assert result.provider_mandate_id == provider_mandate_id
            assert result.provider_policy_digest == source_ids.provider_policy_digest
            binding = customer_intents.binding(
                db, source_ids.workspace_id, result.provider_mandate_id, 1
            )
            assert (
                binding.consent_id == result.provider_consent_id
                and binding.ledger_id == result.ledger_id
            )
            execution_mandates.checked(
                db, source_ids.workspace_id, binding, source_ids.actor_id, lambda: NOW
            )
            consents = after["provider_execution_consents"]
            assert len(consents) == 1
            assert consents[0] == dict(
                id=result.provider_consent_id,
                workspace_id=source_ids.workspace_id,
                mandate_id=result.provider_mandate_id,
                revision=1,
                policy_digest=source_ids.provider_policy_digest,
                actor=source_ids.actor_id,
                approved_at=NOW,
            )
            expected["provider_execution_consents"] = consents
            expected["provider_execution_mandates"][0]["state"] = "active"
    assert canonical(after) == canonical(expected)
    return result
