"""Owned terminal commerce publications and privacy/generation fences."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0051"
down_revision: str | Sequence[str] | None = "20261006_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "commerce_evidence_states",
        sa.Column("store_id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("privacy_epoch", sa.Integer(), nullable=False),
        sa.Column("publication_revision", sa.Integer(), nullable=False),
        sa.Column("history_from", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_stores.id", "commerce_stores.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("store_id", "workspace_id", name="uq_commerce_evidence_owner"),
        sa.CheckConstraint(
            "generation > 0 AND privacy_epoch > 0 AND publication_revision >= 0",
            name="ck_commerce_evidence_fence",
        ),
    )
    op.create_table(
        "commerce_measurement_publications",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.String(32), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("privacy_epoch", sa.Integer(), nullable=False),
        sa.Column("publication_revision", sa.Integer(), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("source_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("earliest_source_day", sa.Date(), nullable=False),
        sa.Column("completion_digest", sa.String(64), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["store_id", "workspace_id"],
            ["commerce_evidence_states.store_id", "commerce_evidence_states.workspace_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("id", "workspace_id", name="uq_commerce_publication_owner"),
        sa.UniqueConstraint(
            "store_id",
            "generation",
            "publication_revision",
            name="uq_commerce_publication_revision",
        ),
        sa.UniqueConstraint(
            "store_id", "completion_digest", name="uq_commerce_publication_completion"
        ),
        sa.CheckConstraint(
            "generation > 0 AND privacy_epoch > 0 "
            "AND publication_revision > 0 AND source_revision >= 0",
            name="ck_commerce_publication_revision",
        ),
        sa.CheckConstraint(
            "source_window_start <= source_window_end", name="ck_commerce_publication_window"
        ),
    )


def downgrade() -> None:
    op.drop_table("commerce_measurement_publications")
    op.drop_table("commerce_evidence_states")
