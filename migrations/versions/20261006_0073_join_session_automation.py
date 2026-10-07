"""Join owned customer foundations and original-session automation."""

from collections.abc import Sequence

revision: str = "20261006_0073"
down_revision: str | Sequence[str] | None = ("20261006_0071", "20261006_0072")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
