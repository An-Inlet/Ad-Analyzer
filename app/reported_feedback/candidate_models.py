"""Erasable rule lineage. Deleting evidence retracts suggestions, never obligations."""

from sqlalchemy import DDL, ForeignKeyConstraint, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class ReportedRuleCandidateDependency(Base):
    __tablename__ = "reported_rule_candidate_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["candidate_job_id", "workspace_id"],
            ["optimization_candidate_jobs.id", "optimization_candidate_jobs.workspace_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["comparison_id", "workspace_id", "account_id", "campaign_id"],
            [
                "reported_action_comparisons.id",
                "reported_action_comparisons.workspace_id",
                "reported_action_comparisons.account_id",
                "reported_action_comparisons.campaign_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["acquisition_job_id", "workspace_id", "account_id", "campaign_id"],
            [
                "reported_feedback_jobs.id",
                "reported_feedback_jobs.workspace_id",
                "reported_feedback_jobs.account_id",
                "reported_feedback_jobs.campaign_id",
            ],
            ondelete="CASCADE",
        ),
    )
    candidate_job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[int] = mapped_column(Integer)
    campaign_id: Mapped[int] = mapped_column(Integer)
    comparison_id: Mapped[str] = mapped_column(String(32), index=True)
    acquisition_job_id: Mapped[str] = mapped_column(String(32), index=True)


def statements(dialect: str) -> tuple[str, ...]:
    deletion = (
        "DELETE FROM optimization_candidate_jobs WHERE id=OLD.candidate_job_id "
        "AND workspace_id=OLD.workspace_id;"
    )
    owned = (
        "EXISTS(SELECT 1 FROM reported_action_comparisons c "
        "JOIN reported_feedback_jobs r ON r.id=c.job_id "
        "JOIN optimization_candidate_jobs j ON j.id=NEW.candidate_job_id "
        "WHERE c.id=NEW.comparison_id AND c.job_id=NEW.acquisition_job_id "
        "AND c.workspace_id=NEW.workspace_id AND c.account_id=NEW.account_id "
        "AND c.campaign_id=NEW.campaign_id AND j.workspace_id=c.workspace_id "
        "AND j.environment=c.environment AND j.actor_id=r.original_actor_id "
        "AND j.auth_session_digest=r.original_session_digest "
        "AND j.attempt_id=c.original_attempt_id)"
    )
    if dialect == "sqlite":
        return (
            "CREATE TRIGGER reported_rule_dependency_owner BEFORE INSERT ON "
            "reported_rule_candidate_dependencies WHEN NOT "
            + owned
            + " BEGIN SELECT RAISE(ABORT, 'owned reported rule lineage required'); END",
            "CREATE TRIGGER reported_rule_dependency_immutable BEFORE UPDATE ON "
            "reported_rule_candidate_dependencies BEGIN SELECT RAISE(ABORT, "
            "'immutable reported rule lineage'); END",
            "CREATE TRIGGER reported_rule_dependency_erase AFTER DELETE ON "
            f"reported_rule_candidate_dependencies BEGIN {deletion} END",
        )
    return (
        "CREATE FUNCTION reported_rule_dependency_owner_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN IF NOT "
        + owned
        + " THEN RAISE EXCEPTION 'owned reported rule lineage required'; END IF; "
        "RETURN NEW; END; $$",
        "CREATE TRIGGER reported_rule_dependency_owner BEFORE INSERT ON "
        "reported_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION "
        "reported_rule_dependency_owner_fn()",
        "CREATE FUNCTION reported_rule_dependency_immutable_fn() RETURNS trigger LANGUAGE "
        "plpgsql AS $$ BEGIN RAISE EXCEPTION 'immutable reported rule lineage'; END; $$",
        "CREATE TRIGGER reported_rule_dependency_immutable BEFORE UPDATE ON "
        "reported_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION "
        "reported_rule_dependency_immutable_fn()",
        "CREATE FUNCTION reported_rule_dependency_erase_fn() RETURNS trigger LANGUAGE "
        f"plpgsql AS $$ BEGIN {deletion} RETURN NULL; END; $$",
        "CREATE TRIGGER reported_rule_dependency_erase AFTER DELETE ON "
        "reported_rule_candidate_dependencies FOR EACH ROW EXECUTE FUNCTION "
        "reported_rule_dependency_erase_fn()",
    )


for _dialect in ("sqlite", "postgresql"):
    for _statement in statements(_dialect):
        event.listen(
            ReportedRuleCandidateDependency.__table__,
            "after_create",
            DDL(_statement).execute_if(dialect=_dialect),  # type: ignore[no-untyped-call]
        )
