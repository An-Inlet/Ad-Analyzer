"""scope execution idempotency keys to recommendations

Revision ID: 20260720_0006
Revises: 20260720_0005
Create Date: 2026-07-20
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260720_0006"
down_revision: str | None = "20260720_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_UNIQUE = "uq_execution_audits_idempotency_key"
NEW_UNIQUE = "uq_execution_audits_recommendation_idempotency_key"


def upgrade() -> None:
    op.drop_constraint(OLD_UNIQUE, "execution_audits", type_="unique")
    op.create_unique_constraint(
        NEW_UNIQUE,
        "execution_audits",
        ["recommendation_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(NEW_UNIQUE, "execution_audits", type_="unique")
    op.create_unique_constraint(OLD_UNIQUE, "execution_audits", ["idempotency_key"])
