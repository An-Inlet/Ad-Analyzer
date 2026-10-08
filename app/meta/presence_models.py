"""Ephemeral original-window provenance; never exported as customer evidence."""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class MetaPresenceStageContext(Base):
    __tablename__ = "meta_presence_stage_contexts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["connection_id", "workspace_id"],
            ["meta_connections.id", "meta_connections.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["account_id", "workspace_id", "integration_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint("connection_id", "window_token", name="uq_meta_presence_token"),
        CheckConstraint(
            "generation > 0 AND privacy_revision >= 0", name="ck_meta_presence_revision"
        ),
        CheckConstraint("starts_on <= ends_on", name="ck_meta_presence_dates"),
        CheckConstraint("length(window_token) = 32", name="ck_meta_presence_token_length"),
        CheckConstraint(
            "payload_bytes > 0 AND payload_bytes <= 8192", name="ck_meta_presence_bytes"
        ),
    )
    connection_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    window_token: Mapped[str] = mapped_column(String(32))
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    integration_id: Mapped[int] = mapped_column(Integer)
    native_advertiser_id: Mapped[str] = mapped_column(String(32))
    generation: Mapped[int] = mapped_column(Integer)
    privacy_revision: Mapped[int] = mapped_column(Integer)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    canonical_json: Mapped[str] = mapped_column(Text)
    payload_digest: Mapped[str] = mapped_column(String(64))
    payload_bytes: Mapped[int] = mapped_column(Integer)


from app.meta.presence_triggers import register  # noqa: E402

register(Base.metadata.tables[MetaPresenceStageContext.__tablename__])
register(Base.metadata.tables["meta_staged_metrics"])
