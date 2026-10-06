"""Persisted Google/Meta/TikTok optimization survives strict owned export."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from app.campaign_review.storage import LocalMediaStore
from app.lifecycle.export_serializers import serialize
from app.publication import optimization as o
from app.settings import Settings
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_exports import build, unpack
from tests.test_customer_exports import export_engine as export_engine
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_durable_optimization import ready
from tests.test_export_owned_domains import authorize_export
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize("provider", ["google_ads", "meta_ads", "tiktok_ads"])
def test_actual_optimization_then_archive(
    export_engine: Engine, configuration: Settings, tmp_path: Path, provider: str
) -> None:
    with Session(export_engine) as db:
        wid, actor, binding, scope, target, action, runtime, server = ready(
            db, configuration, tmp_path, provider
        )
        review = o.prepare_optimization(
            db, wid, binding, scope, target, action, "a" * 64, actor, runtime, lambda: NOW
        )
        o.approve_optimization(
            db, wid, review.id, review.digest, review.plan_digest, actor, runtime, lambda: NOW
        )
        run = o.create_run(db, wid, review.id, actor, runtime, lambda: NOW)
        claim = o.claim_step(db, wid, run.id, actor, runtime, lambda: NOW)
        assert claim is not None
        receipt = o.execute_claim(db, claim, actor, runtime, lambda: NOW)
        assert receipt.outcome == "verified_target_state"
        assert len(server.writes if provider == "google_ads" else server.posts) == 1
        authority = authorize_export(db, export_engine, wid)
    authority.claim()
    file, manifest = build(export_engine, authority, LocalMediaStore(tmp_path))
    try:
        _, entries = unpack(file)
        assert manifest["supported_customer_data_complete"], [
            item for item in manifest["sections"] if not item["complete"]
        ]
        for table, field in [
            ("provider_execution_reviews", "document"),
            ("provider_execution_attempts", "request"),
            ("provider_execution_responses", "response"),
            ("provider_execution_receipts", "receipt"),
        ]:
            rows = [json.loads(line) for line in entries[f"data/{table}.jsonl"].splitlines()]
            assert len(rows) == 1
            row = rows[0]
            assert row[field]
            invalid = deepcopy(row)
            invalid[field]["raw_provider_body"] = {"unreviewed": True}
            projected, missing = serialize(table, invalid)
            assert field in missing and field not in projected
            invalid = deepcopy(row)
            if field == "response":
                invalid["digest"] = "f" * 64
            else:
                invalid["workspace_id"] += 100
            projected, missing = serialize(table, invalid)
            assert field in missing and field not in projected
            mutations: dict[str, dict[str, str | int]] = {
                "document": {
                    "digest": "f" * 64,
                    "plan_digest": "f" * 64,
                    "account_id": 99999,
                    "integration_id": 99999,
                    "source_revision": 1,
                    "consent_id": "f" * 32,
                },
                "request": {"run_id": "f" * 32, "id": "f" * 32, "step_id": "create"},
                "response": {"digest": "f" * 64},
                "receipt": {"digest": "f" * 64, "attempt_id": "f" * 32},
            }
            for scalar_field, changed in mutations[field].items():
                invalid = deepcopy(row)
                invalid[scalar_field] = changed
                projected, missing = serialize(table, invalid)
                assert field in missing and field not in projected
        assert b"existing_campaign_optimize" in entries["data/provider_execution_receipts.jsonl"]
        assert b"access_token" not in b"".join(entries.values())
    finally:
        file.close()
