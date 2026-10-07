"""Immutable hash-only v2 handoff provenance, owned by the retained review link."""

from typing import Any

from sqlalchemy import JSON, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.initial_planning.review_v2_triggers import register


class InitialPreviewExecutionProofRow(Base):
    __tablename__ = "initial_preview_execution_proofs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["review_id", "workspace_id"],
            ["initial_preview_reviews.review_id", "initial_preview_reviews.workspace_id"],
            ondelete="CASCADE",
            name="fk_initial_execution_proof_link",
        ),
    )
    review_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, Any]] = mapped_column(JSON)


register(Base.metadata.tables["initial_preview_execution_proofs"])


# SQL constraints bind owned rows. ORM insert additionally verifies canonical hashes,
# which portable SQLite/PostgreSQL SQL cannot compute without installing extensions.
from sqlalchemy import Connection, event, select  # noqa: E402
from sqlalchemy.orm import Mapper  # noqa: E402

from app.initial_planning.review_v2_export import bind_execution_proof  # noqa: E402


@event.listens_for(InitialPreviewExecutionProofRow, "before_insert")
def validate_insert(
    mapper: Mapper[InitialPreviewExecutionProofRow],
    connection: Connection,
    target: InitialPreviewExecutionProofRow,
) -> None:
    tables = Base.metadata.tables
    link_table = tables["initial_preview_reviews"]
    link = (
        connection.execute(
            select(link_table).where(
                link_table.c.review_id == target.review_id,
                link_table.c.workspace_id == target.workspace_id,
            )
        )
        .mappings()
        .one()
    )
    preview_table = tables["initial_plan_previews"]
    preview = (
        connection.execute(
            select(preview_table).where(
                preview_table.c.id == link["preview_id"],
                preview_table.c.workspace_id == target.workspace_id,
            )
        )
        .mappings()
        .one()
    )
    review_table = tables["provider_execution_reviews"]
    review = (
        connection.execute(
            select(review_table).where(
                review_table.c.id == target.review_id,
                review_table.c.workspace_id == target.workspace_id,
            )
        )
        .mappings()
        .one()
    )
    bind_execution_proof(
        {
            "review_id": target.review_id,
            "workspace_id": target.workspace_id,
            "digest": target.digest,
            "document": target.document,
        },
        dict(link),
        dict(preview),
        dict(review),
    )
