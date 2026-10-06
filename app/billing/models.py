from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
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
