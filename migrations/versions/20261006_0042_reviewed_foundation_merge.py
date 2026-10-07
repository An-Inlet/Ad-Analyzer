"""Merge durable publication and Meta child reporting histories."""

from collections.abc import Sequence

revision: str = "20261006_0042"
down_revision: str | Sequence[str] | None = ("20261006_0040", "20261006_0041")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
