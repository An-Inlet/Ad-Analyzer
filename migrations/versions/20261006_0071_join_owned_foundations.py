"""Join billing, feedback, Google completion, review and observation foundations."""

from collections.abc import Sequence

revision: str = "20261006_0071"
down_revision: str | Sequence[str] | None = (
    "20261006_0063",
    "20261006_0064",
    "20261006_0066",
    "20261006_0068",
    "20261006_0070",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
