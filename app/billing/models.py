from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class WorkspaceBilling(Base):
    __tablename__ = "customer_workspace_billing"
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), primary_key=True
    )
    customer_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    customer_request_key: Mapped[str] = mapped_column(String(64), unique=True)
    checkout_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    checkout_price: Mapped[str | None] = mapped_column(String(160))
    checkout_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    checkout_url: Mapped[str | None] = mapped_column(Text)
    checkout_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    subscription_id: Mapped[str | None] = mapped_column(String(160), unique=True)
    price_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="unconfigured")
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingEvent(Base):
    __tablename__ = "customer_billing_events"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    body_hash: Mapped[str] = mapped_column(String(64))
    customer_id: Mapped[str] = mapped_column(String(160), index=True)
    subscription_id: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="pending")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
