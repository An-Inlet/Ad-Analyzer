"""Immutable, scoped catalog observations and their exact planning input links."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.planning_documents.catalog_receipt_triggers import register as _register


class CatalogReceiptRow(Base):
    __tablename__ = "planning_catalog_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["account_id", "workspace_id", "connection_id"],
            [
                "advertising_accounts.id",
                "advertising_accounts.workspace_id",
                "advertising_accounts.connection_id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "workspace_id",
            "id",
            "account_id",
            "connection_id",
            name="uq_catalog_receipt_owned_source",
        ),
        UniqueConstraint(
            "workspace_id",
            "actor_id",
            "session_digest",
            "account_id",
            "composite_digest",
            name="uq_catalog_receipt_exact_read",
        ),
        CheckConstraint("privacy_revision >= 0", name="ck_catalog_receipt_privacy"),
        CheckConstraint(
            "payload_bytes >= 1 AND payload_bytes <= 1048576", name="ck_catalog_receipt_bytes"
        ),
        CheckConstraint(
            "target_count >= 0 AND target_count <= 400", name="ck_catalog_receipt_targets"
        ),
        CheckConstraint(
            "payload_schema = 'inlet.planning-catalog-receipt.v1'", name="ck_catalog_receipt_schema"
        ),
        CheckConstraint(
            "reporting_starts_at < reporting_ends_at "
            "AND reporting_ends_at <= observation_started_at "
            "AND observation_started_at <= observed_at AND observed_at < expires_at "
            "AND created_at >= observed_at AND created_at < expires_at",
            name="ck_catalog_receipt_times",
        ),
        Index("ix_catalog_receipts_expiry", "workspace_id", "expires_at", "id"),
    )
    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer)
    connection_id: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(String(32))
    session_digest: Mapped[str] = mapped_column(String(64))
    authenticated_at: Mapped[int] = mapped_column(BigInteger)
    privacy_revision: Mapped[int] = mapped_column(Integer)
    source_revision: Mapped[str] = mapped_column(String(2000))
    source_binding_digest: Mapped[str] = mapped_column(String(64))
    payload_schema: Mapped[str] = mapped_column(String(64))
    canonical_json: Mapped[str] = mapped_column(Text)
    payload_digest: Mapped[str] = mapped_column(String(64))
    payload_bytes: Mapped[int] = mapped_column(Integer)
    composite_digest: Mapped[str] = mapped_column(String(64))
    target_count: Mapped[int] = mapped_column(Integer)
    reporting_starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reporting_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observation_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CatalogReceiptSelectionRow(Base):
    __tablename__ = "planning_catalog_receipt_selections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "receipt_id", "account_id", "connection_id"],
            [
                "planning_catalog_receipts.workspace_id",
                "planning_catalog_receipts.id",
                "planning_catalog_receipts.account_id",
                "planning_catalog_receipts.connection_id",
            ],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "workspace_id",
            "receipt_id",
            "canonical_entity_key",
            name="uq_catalog_receipt_canonical",
        ),
    )
    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    selection_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    receipt_id: Mapped[str] = mapped_column(String(32))
    connection_id: Mapped[int] = mapped_column(Integer)
    canonical_entity_key: Mapped[str] = mapped_column(String(64))


class InputCatalogReceiptRow(Base):
    __tablename__ = "planning_input_catalog_receipts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["workspace_id", "plan_id", "input_revision"],
            [
                "planning_input_revisions.workspace_id",
                "planning_input_revisions.plan_id",
                "planning_input_revisions.revision",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["workspace_id", "receipt_id", "account_id", "connection_id"],
            [
                "planning_catalog_receipts.workspace_id",
                "planning_catalog_receipts.id",
                "planning_catalog_receipts.account_id",
                "planning_catalog_receipts.connection_id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "selected_count >= 1 AND selected_count <= 400", name="ck_input_catalog_receipt_count"
        ),
    )
    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    input_revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    receipt_id: Mapped[str] = mapped_column(String(32))
    connection_id: Mapped[int] = mapped_column(Integer)
    composite_digest: Mapped[str] = mapped_column(String(64))
    input_digest: Mapped[str] = mapped_column(String(64))
    selected_keys_digest: Mapped[str] = mapped_column(String(64))
    selected_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


for _model in (CatalogReceiptRow, CatalogReceiptSelectionRow, InputCatalogReceiptRow):
    _register(Base.metadata.tables[_model.__tablename__])
