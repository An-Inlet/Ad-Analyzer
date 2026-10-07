"""Protected scalar customer Start, with an erasable candidate reference (0085)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class InitialRuleSessionStart(Base):
    __tablename__ = "initial_rule_session_starts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["session_run_id", "workspace_id"],
            ["session_automation_runs.id", "session_automation_runs.workspace_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["candidate_job_id", "candidate_workspace_id"],
            ["optimization_candidate_jobs.id", "optimization_candidate_jobs.workspace_id"],
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "(candidate_job_id IS NULL AND candidate_workspace_id IS NULL) OR "
            "(candidate_job_id IS NOT NULL AND candidate_workspace_id = workspace_id "
            "AND candidate_workspace_id IS NOT NULL)",
            name="ck_initial_start_optional_scope",
        ),
        CheckConstraint("expires_at > created_at", name="ck_initial_start_lifetime"),
    )
    session_run_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    candidate_job_id: Mapped[str | None] = mapped_column(String(32))
    candidate_workspace_id: Mapped[int | None] = mapped_column(Integer)
    input_digest: Mapped[str] = mapped_column(String(64))
    preview_digest: Mapped[str] = mapped_column(String(64))
    semantic_key_digest: Mapped[str] = mapped_column(String(64))
    policy_digest: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


from app.initial_planning.start_triggers import register  # noqa: E402

register(Base.metadata.tables[InitialRuleSessionStart.__tablename__])
