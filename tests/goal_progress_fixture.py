"""Confirmed goal plus actual normalized sales/refund and completed import."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.api import customer_goals
from app.commerce.models import CommerceStore
from app.commerce.sync import CommerceSyncService
from app.customers.access import SESSION_COOKIE, CustomerPrincipal, digest
from app.customers.models import CustomerMembership, CustomerSession, CustomerUser
from app.goals import service
from app.goals.schemas import ConfirmInput, GoalDefinition
from sqlalchemy.orm import Session

from tests.test_commerce_measurement import NOW, FakeMeasurement, agreement, source, window
from tests.test_customer_goals import seed
from tests.test_customer_identity import login


def ready(
    engine: Any,
    configuration: Any,
    replicas: Any,
    *,
    as_of: datetime | None = None,
    refund: bool = True,
) -> Any:
    alice, _, provider = replicas
    actor = login(alice, "goal-progress:1")
    now = as_of or datetime.now(UTC)
    with Session(engine) as db:
        goal = seed(db, configuration)
        definition = GoalDefinition.model_validate(service.current(db, goal).definition)
        definition = definition.model_copy(
            update={
                "target_window": window(date(2026, 10, 1), date(2026, 11, 1)),
                "deadline": date(2026, 10, 31),
            }
        )
        service.revise(db, goal, definition, actor, NOW)
        db.add(CustomerMembership(user_id=actor, workspace_id=goal.workspace_id, role="owner"))
        preview = service.preview(db, goal, NOW)
        service.confirm(
            db,
            goal,
            ConfirmInput(
                expected_revision=goal.revision,
                preview_id=preview.id,
                idempotency_key="progress-confirm",
            ),
            NOW,
            actor_id=actor,
        )
        db.commit()
        # Refund processing is October; original purchase remains September.
        client = FakeMeasurement(
            configuration, [([source(updated=now - timedelta(seconds=2))], None)]
        )
        client.facts = [
            agreement(),
            agreement(2, "-11", "-1", "RETURN", datetime(2026, 10, 2, 12, tzinfo=UTC)),
        ]
        if not refund:
            client.facts = [agreement()]
        imported = CommerceSyncService(db, configuration, client).page(
            goal.workspace_id, now=now - timedelta(seconds=1)
        )
        assert imported["status"] == "complete", imported
        db.commit()
        store = db.get(CommerceStore, definition.store_id)
        assert store is not None
        user = db.get(CustomerUser, actor)
        session = db.get(CustomerSession, digest(alice.cookies[SESSION_COOKIE]))
        assert user and session
        result = (
            alice,
            provider,
            goal.workspace_id,
            goal.id,
            goal.revision,
            store.id,
            CustomerPrincipal(user, session),
            now,
        )
    alice.app.include_router(customer_goals.router)
    return result
