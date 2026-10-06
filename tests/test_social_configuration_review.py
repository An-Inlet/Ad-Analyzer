from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from app.customers.models import CustomerMembership
from app.lifecycle.export_serializers import serialize
from app.publication import coordinator
from app.publication.coordinator_contracts import CreationRuntime
from app.publication.execution_authorization import owner_authorizer
from app.publication.social_catalog import MetaConfigurationProfile
from app.publication.social_compiler import compile_social
from app.publication.social_contracts import SocialConfigurationApprovalRef
from app.publication.social_customer_producer import SocialPlanProducer
from app.publication.social_review_contracts import (
    LegacySocialConfigurationDocumentV1,
    MetaNoDSAAnswer,
    SocialConfigurationDocument,
    SocialRequirements,
    TikTokCoverAnswer,
)
from app.publication.social_review_service import (
    confirm,
    meta_declaration,
    prepare,
    read_confirmed,
    selection,
    verify_plan,
)
from app.settings import Settings
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_campaign_video import encoded as encoded
from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_shopify_sales import configuration as configuration
from tests.test_social_customer_producer import fixture


@pytest.mark.parametrize("provider", ["meta_ads", "tiktok_ads"])
def test_exact_configuration_confirmation(
    customer_engine: Engine,
    configuration: Settings,
    tmp_path: Path,
    encoded: Any,
    provider: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with Session(customer_engine) as db:
        captured: list[CreationRuntime] = []
        original_prepare = coordinator.prepare_creation

        def observe(*args: Any, **kwargs: Any) -> Any:
            captured.append(args[6])
            return original_prepare(*args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(coordinator, "prepare_creation", observe)
            original, account, catalog, producer, actor, store, cover, _ = fixture(
                db,
                configuration,
                tmp_path,
                provider,
                encoded() if provider == "tiktok_ads" else None,
            )
        profile = next(iter(producer.profiles.values()))
        if isinstance(profile, MetaConfigurationProfile):
            profile = profile.model_copy(update={"dsa_required": False})
        option = catalog.options[0].model_copy(update={"profile_digest": profile.digest()})
        catalog = catalog.model_copy(update={"options": [option]})
        requirements = SocialRequirements(
            profile_digest=profile.digest(),
            requirements_digest="a" * 64,
            wording_version="explicit-test-rule-v1",
            verified=True,
            dsa_required=False,
            wording="Offline Test: Review This No-DSA Profile And Its Exact Media.",
        )
        document = selection(
            db,
            account.workspace_id,
            actor,
            account,
            catalog,
            option.identifier(catalog.request),
            profile,
            requirements,
            MetaNoDSAAnswer(special_category_answer="none_applicable")
            if provider == "meta_ads"
            else TikTokCoverAnswer(reviewed_pair=True),
            cover,
            "contract_test",
            store,
            lambda: NOW,
            owner_authorizer,
        )
        row = prepare(db, account.workspace_id, actor, document, lambda: NOW, owner_authorizer)
        approval = confirm(
            db,
            account.workspace_id,
            row.id,
            row.digest,
            actor,
            document,
            lambda: NOW,
            owner_authorizer,
        )
        db.commit()
        mapping = {column.name: getattr(row, column.name) for column in row.__table__.columns}
        exported, missing = serialize(row.__tablename__, mapping)
        assert not missing and exported["document"] == row.document
        _, missing = serialize(row.__tablename__, {**mapping, "workspace_id": 987654})
        assert missing == ["document"]
        same = confirm(
            db,
            account.workspace_id,
            row.id,
            row.digest,
            actor,
            document,
            lambda: NOW,
            owner_authorizer,
        )
        assert same.digest == approval.digest
        assert (
            read_confirmed(
                db, account.workspace_id, row.id, row.digest, actor, document, owner_authorizer
            ).digest
            == approval.digest
        )
        assert document.request.source_digest == original.review.source.fingerprint()
        with pytest.raises(HTTPException, match="exact configuration digest"):
            confirm(
                db,
                account.workspace_id,
                row.id,
                "f" * 64,
                actor,
                document,
                lambda: NOW,
                owner_authorizer,
            )
        changed = document.model_copy(update={"option_id": "b" * 64})
        with pytest.raises(HTTPException, match="current exact"):
            confirm(
                db,
                account.workspace_id,
                row.id,
                row.digest,
                actor,
                changed,
                lambda: NOW,
                owner_authorizer,
            )
        assert "configuration_review" not in original.review.model_dump(mode="json")
        confirmed_producer = SocialPlanProducer(
            [profile],
            declarations=lambda request, now: meta_declaration(
                db,
                account.workspace_id,
                row.id,
                row.digest,
                actor,
                document,
                owner_authorizer,
            ),
        )
        plan = confirmed_producer.produce(
            db,
            original.review.source,
            account,
            option.identifier(catalog.request),
            catalog,
            store,
            NOW,
            actor=actor,
            cover_media_id=cover,
            configuration_review=SocialConfigurationApprovalRef(
                review_id=row.id, review_digest=row.digest, approval_digest=approval.digest
            ),
        )
        assert verify_plan(db, account.workspace_id, plan, actor) == document
        with pytest.raises(HTTPException, match="validator unavailable"):
            coordinator.gate(captured[0], "contract_test", plan)
        with pytest.raises(HTTPException, match="confirmation required"):
            coordinator.gate(
                replace(captured[0], environment="live", live_enabled=True), "live", original
            )
        seen: list[str] = []
        current_runtime = replace(
            captured[0], social_configuration_current=lambda d, now: seen.append(d.digest())
        )
        coordinator.social_configuration_current(
            db, account.workspace_id, plan, actor, current_runtime, lambda: NOW
        )
        assert seen == [document.digest()]

        def stale_profile(d: SocialConfigurationDocument, now: Any) -> None:
            raise HTTPException(409, "current profile changed")

        with pytest.raises(HTTPException, match="current profile changed"):
            coordinator.social_configuration_current(
                db,
                account.workspace_id,
                plan,
                actor,
                replace(current_runtime, social_configuration_current=stale_profile),
                lambda: NOW,
            )
        altered_fields = plan.review.configuration.model_copy(
            update={"account_timezone": "Europe/London"}
        )
        altered = compile_social(plan.review.model_copy(update={"configuration": altered_fields}))
        with pytest.raises(HTTPException, match="exact confirmed"):
            verify_plan(db, account.workspace_id, altered, actor)
        saved = row.document
        row.document = {
            key: value
            for key, value in saved.items()
            if key not in {"configuration_digest", "configuration"}
        }
        db.flush()
        with pytest.raises(HTTPException, match="new exact configuration"):
            verify_plan(db, account.workspace_id, plan, actor)
        legacy = LegacySocialConfigurationDocumentV1.model_validate(
            {
                **{
                    key: value
                    for key, value in saved.items()
                    if key not in {"configuration_digest", "configuration"}
                },
                "schema_version": "inlet.social-configuration-review.v1",
                "requirements": {k: v for k, v in saved["requirements"].items() if k != "wording"},
            }
        )
        historical, missing = serialize(
            row.__tablename__,
            {
                **mapping,
                "document": legacy.model_dump(mode="json"),
                "digest": legacy.digest(),
            },
        )
        assert not missing and historical["document"]["schema_version"].endswith(".v1")
        row.document = legacy.model_dump(mode="json")
        row.digest = legacy.digest()
        db.flush()
        with pytest.raises(HTTPException, match="new exact configuration"):
            verify_plan(db, account.workspace_id, plan, actor)
        row.document = saved
        row.digest = document.digest()
        db.flush()
        raw = document.model_dump()
        raw["answer"]["dsa_beneficiary"] = "Must never persist"
        with pytest.raises(ValidationError):
            SocialConfigurationDocument.model_validate(raw)
        if provider == "meta_ads":
            blocked = document.model_copy(
                update={
                    "answer": MetaNoDSAAnswer(special_category_answer="unsure"),
                }
            )
            blocked_row = prepare(
                db, account.workspace_id, actor, blocked, lambda: NOW, owner_authorizer
            )
            with pytest.raises(HTTPException, match="current exact"):
                confirm(
                    db,
                    account.workspace_id,
                    blocked_row.id,
                    blocked_row.digest,
                    actor,
                    blocked,
                    lambda: NOW,
                    owner_authorizer,
                )
            with pytest.raises(HTTPException, match="verified non-DSA"):
                selection(
                    db,
                    account.workspace_id,
                    actor,
                    account,
                    catalog,
                    option.identifier(catalog.request),
                    profile.model_copy(update={"dsa_required": True}),
                    requirements,
                    document.answer,
                    cover,
                    "contract_test",
                    store,
                    lambda: NOW,
                    owner_authorizer,
                )

        member = db.get(CustomerMembership, (actor, account.workspace_id))
        assert member is not None
        member.status = "suspended"
        db.commit()
        with pytest.raises(HTTPException):
            confirm(
                db,
                account.workspace_id,
                row.id,
                row.digest,
                actor,
                document,
                lambda: NOW,
                owner_authorizer,
            )


def test_no_personal_declaration_or_default_answer_port() -> None:
    with pytest.raises(ValidationError):
        MetaNoDSAAnswer.model_validate({})
    with pytest.raises(ValidationError):
        MetaNoDSAAnswer.model_validate(
            {"special_category_answer": "none_applicable", "dsa_payor": "Rejected"}
        )
    with pytest.raises(ValidationError):
        TikTokCoverAnswer.model_validate({"reviewed_pair": False})
