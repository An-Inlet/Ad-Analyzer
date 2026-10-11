"""Erasable selected reporting; no financial or customer-session authority."""

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.campaign_performance.selected_triggers import register
from app.database.session import Base


def scope_fk() -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["account_id", "workspace_id", "connection_id"],
        [
            "advertising_accounts.id",
            "advertising_accounts.workspace_id",
            "advertising_accounts.connection_id",
        ],
        ondelete="CASCADE",
    )


class Scope:
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    connection_id: Mapped[int] = mapped_column(Integer)


class Payload:
    canonical_json: Mapped[str] = mapped_column(Text)
    payload_digest: Mapped[str] = mapped_column(String(64))
    payload_bytes: Mapped[int] = mapped_column(Integer)


class EventSelectionRow(Scope, Payload, Base):
    __tablename__ = "customer_event_selections"
    __table_args__ = (
        scope_fk(),
        UniqueConstraint(
            "id", "account_id", "workspace_id", "payload_digest", name="uq_selected_selection_scope"
        ),
        ForeignKeyConstraint(
            ["confirmed_by_customer_id"], ["customer_users.id"], ondelete="CASCADE"
        ),
        CheckConstraint("payload_bytes > 0 AND payload_bytes <= 8192", name="ck_selection_bytes"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    confirmed_by_customer_id: Mapped[str] = mapped_column(String(32))


class CurrentEventSelectionRow(Scope, Base):
    __tablename__ = "customer_event_selection_current"
    __table_args__ = (
        scope_fk(),
        ForeignKeyConstraint(
            ["selection_id", "account_id", "workspace_id", "selection_digest"],
            [
                "customer_event_selections.id",
                "customer_event_selections.account_id",
                "customer_event_selections.workspace_id",
                "customer_event_selections.payload_digest",
            ],
            ondelete="CASCADE",
        ),
    )
    invalidated: Mapped[bool] = mapped_column(
        Boolean(create_constraint=True, name="ck_selected_head_boolean"),
        nullable=False,
        server_default=false(),
    )
    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    selection_id: Mapped[str] = mapped_column(String(32))
    selection_digest: Mapped[str] = mapped_column(String(64))


class SelectedCaptureRow(Scope, Payload, Base):
    __tablename__ = "selected_reporting_captures"
    __table_args__ = (
        scope_fk(),
        UniqueConstraint("id", "account_id", "workspace_id", name="uq_selected_capture_scope"),
        ForeignKeyConstraint(
            ["selection_id", "account_id", "workspace_id", "selection_digest"],
            [
                "customer_event_selections.id",
                "customer_event_selections.account_id",
                "customer_event_selections.workspace_id",
                "customer_event_selections.payload_digest",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["completion_id", "account_id", "workspace_id"],
            [
                "campaign_performance_completions.id",
                "campaign_performance_completions.account_id",
                "campaign_performance_completions.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        CheckConstraint("fact_count >= 0 AND fact_count <= 50000", name="ck_selected_count"),
        CheckConstraint(
            "payload_bytes > 0 AND payload_bytes <= 16384", name="ck_selected_header_bytes"
        ),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    selection_id: Mapped[str] = mapped_column(String(32))
    selection_digest: Mapped[str] = mapped_column(String(64))
    completion_id: Mapped[str] = mapped_column(String(32))
    request_digest: Mapped[str] = mapped_column(String(64))
    fact_count: Mapped[int] = mapped_column(Integer)


class SelectedFactRow(Payload, Base):
    __tablename__ = "selected_reporting_facts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["capture_id", "account_id", "workspace_id"],
            [
                "selected_reporting_captures.id",
                "selected_reporting_captures.account_id",
                "selected_reporting_captures.workspace_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["campaign_id", "account_id"],
            ["campaigns.id", "campaigns.account_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "capture_id", "native_campaign_id", "metric_date", name="uq_selected_native_day"
        ),
        CheckConstraint(
            "payload_bytes > 0 AND payload_bytes <= 4096", name="ck_selected_fact_bytes"
        ),
    )
    capture_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    campaign_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_date: Mapped[date] = mapped_column(Date, primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    native_campaign_id: Mapped[str] = mapped_column(String(32))


for model in (EventSelectionRow, CurrentEventSelectionRow, SelectedCaptureRow, SelectedFactRow):
    register(Base.metadata.tables[model.__tablename__])
