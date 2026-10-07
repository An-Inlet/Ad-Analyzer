"""Original job identity reaches local derivation; evidence cannot replace native state."""

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest
from app.optimization_candidates import service as s
from app.optimization_candidates.models import CandidateResult
from app.settings import Settings
from fastapi import HTTPException
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW
from tests.test_customer_identity import customer_engine as customer_engine
from tests.test_optimization_candidates import fixture
from tests.test_shopify_sales import configuration as configuration


@pytest.mark.parametrize(
    "mode", ["current", "missing", "scope", "state", "profile", "session", "retracted", "lease"]
)
def test_original_principal_and_final_evidence_boundary(
    customer_engine: Engine, configuration: Settings, tmp_path: Path, mode: str
) -> None:
    calls: list[str] = []
    clock = [NOW]
    with Session(customer_engine) as db:
        principal, work, _, _, runtime, _ = fixture(db, configuration, tmp_path)
        expected = (principal.user.id, principal.session.digest)

        def transform(db, principal, work, observation, now):  # type: ignore[no-untyped-def]
            assert (principal.user.id, principal.session.digest) == expected
            assert db.in_transaction() and now == NOW
            calls.append("transform")
            evidence = observation.evidence.model_copy(
                update={"source_schema": "test.authorized-local-evidence.v1"}
            )
            result = observation.model_copy(update={"evidence": evidence})
            if mode == "scope":
                scope = work.scope.model_copy(update={"goal_digest": "f" * 64})
                result = result.model_copy(
                    update={
                        "scope": scope,
                        "evidence": evidence.model_copy(update={"scope_digest": scope.digest()}),
                    }
                )
            elif mode == "state":
                result = result.model_copy(
                    update={
                        "state": observation.state.model_copy(
                            update={
                                "budget_amount_micros": observation.state.budget_amount_micros + 1
                            }
                        )
                    }
                )
            elif mode == "profile":
                result = result.model_copy(
                    update={
                        "evidence": evidence.model_copy(
                            update={
                                "qualification": "qualified_learning",
                                "qualification_profile": "unregistered",
                                "qualification_revision": 1,
                                "qualification_digest": "c" * 64,
                            }
                        )
                    }
                )
            elif mode == "session":
                # Models a revocation visible at the final guard, not an allowed
                # mutation by a production read-only transform.
                principal.session.revoked_at = int(NOW.timestamp())
                db.flush()
            elif mode == "lease":
                clock[0] = NOW + timedelta(minutes=3)
            return result

        def check(db, principal, work, observation):  # type: ignore[no-untyped-def]
            assert (principal.user.id, principal.session.digest) == expected
            assert observation.scope == work.scope
            assert db.scalar(select(func.count()).select_from(CandidateResult)) == 0
            calls.append("check")
            if mode == "retracted":
                raise HTTPException(409, "current dependency unavailable")

        runtime = replace(
            runtime,
            clock=lambda: clock[0],
            authorized_evidence_transform=transform,
            authorized_final_evidence_current=None if mode == "missing" else check,
            feedback_dependent_schemas=frozenset({"test.authorized-local-evidence.v1"}),
        )
        row = s.enqueue(db, principal, work, runtime)
        wid, identifier = row.workspace_id, row.id
    assert s.process(customer_engine, wid, identifier, runtime) == (
        "completed" if mode == "current" else "superseded" if mode == "lease" else "blocked"
    )
    assert calls == (
        ["transform", "check"] if mode in {"current", "retracted", "lease"} else ["transform"]
    )
    with Session(customer_engine) as db:
        assert db.scalar(select(func.count()).select_from(CandidateResult)) == (mode == "current")
