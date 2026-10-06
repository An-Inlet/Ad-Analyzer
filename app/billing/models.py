from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, Mapper, mapped_column

from app.database.session import Base


class WorkspaceBilling(Base):
    __tablename__ = "customer_workspace_billing"
    __table_args__ = (
        *(
            ForeignKeyConstraint(
                [field, "workspace_id", "provider", "environment", "merchant_account_id"],
                [
                    "customer_billing_offer_bindings." + column
                    for column in (
                        "id",
                        "workspace_id",
                        "provider",
                        "environment",
                        "merchant_account_id",
                    )
                ],
                name="fk_billing_" + field,
                ondelete="RESTRICT",
            )
            for field in ("checkout_offer_binding_id", "subscription_offer_binding_id")
        ),
        CheckConstraint(
            "provider = 'stripe' AND environment IN ('test','live') "
            "AND (environment <> 'live' OR merchant_account_id <> 'legacy_unqualified')",
            name="ck_billing_scope",
        ),
        *(
            UniqueConstraint(
                "provider",
                "environment",
                "merchant_account_id",
                column,
                name="uq_billing_scope_" + column,
            )
            for column in (
                "customer_id",
                "customer_request_key",
                "checkout_key",
                "checkout_id",
                "subscription_id",
            )
        ),
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), primary_key=True
    )

    provider: Mapped[str] = mapped_column(String(16), primary_key=True, default="stripe")
    environment: Mapped[str] = mapped_column(String(16), primary_key=True, default="test")
    merchant_account_id: Mapped[str] = mapped_column(
        String(160), primary_key=True, default="legacy_unqualified"
    )
    checkout_offer_binding_id: Mapped[str | None] = mapped_column(String(32))
    subscription_offer_binding_id: Mapped[str | None] = mapped_column(String(32))
    qualification: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    qualification_digest: Mapped[str | None] = mapped_column(String(64))
    customer_id: Mapped[str | None] = mapped_column(String(160))
    customer_request_key: Mapped[str] = mapped_column(String(64))
    checkout_key: Mapped[str | None] = mapped_column(String(64))
    checkout_price: Mapped[str | None] = mapped_column(String(160))
    checkout_id: Mapped[str | None] = mapped_column(String(160))
    checkout_url: Mapped[str | None] = mapped_column(Text)
    checkout_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subscription_id: Mapped[str | None] = mapped_column(String(160))
    price_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="unconfigured")
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingEvent(Base):
    __tablename__ = "customer_billing_events"
    __table_args__ = (
        CheckConstraint(
            "provider = 'stripe' AND environment IN ('test','live') "
            "AND (environment <> 'live' OR merchant_account_id <> 'legacy_unqualified')",
            name="ck_billing_event_scope",
        ),
    )
    id: Mapped[str] = mapped_column(String(160), primary_key=True)

    provider: Mapped[str] = mapped_column(String(16), primary_key=True, default="stripe")
    environment: Mapped[str] = mapped_column(String(16), primary_key=True, default="test")
    merchant_account_id: Mapped[str] = mapped_column(
        String(160), primary_key=True, default="legacy_unqualified"
    )
    body_hash: Mapped[str] = mapped_column(String(64))
    customer_id: Mapped[str] = mapped_column(String(160), index=True)
    subscription_id: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="pending")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


@event.listens_for(WorkspaceBilling, "before_update")
@event.listens_for(BillingEvent, "before_update")
def immutable_scope(mapper: Mapper[object], connection: Connection, target: object) -> None:
    state = inspect(target)
    assert state is not None
    if any(
        state.attrs[name].history.has_changes()
        for name in ("provider", "environment", "merchant_account_id")
    ):
        raise ValueError("billing scope is immutable")


class BillingOfferBinding(Base):
    __tablename__ = "customer_billing_offer_bindings"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "environment",
            "merchant_account_id",
            "checkout_key",
            name="uq_billing_offer_request",
        ),
        UniqueConstraint(
            "id",
            "workspace_id",
            "provider",
            "environment",
            "merchant_account_id",
            name="uq_billing_offer_owner",
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    provider: Mapped[str] = mapped_column(String(16))
    environment: Mapped[str] = mapped_column(String(16))
    merchant_account_id: Mapped[str] = mapped_column(String(160))
    checkout_key: Mapped[str] = mapped_column(String(64))
    profile: Mapped[dict[str, Any]] = mapped_column(JSON)
    profile_digest: Mapped[str] = mapped_column(String(64))
    binding_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@event.listens_for(BillingOfferBinding, "before_update")
@event.listens_for(BillingOfferBinding, "before_delete")
def immutable_offer(mapper: Mapper[object], connection: Connection, target: object) -> None:
    raise ValueError("billing offer binding is immutable")
