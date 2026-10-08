"""Current sales bound to one retained plan, not an assessment of plan effectiveness."""

from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, computed_field, field_validator, model_validator

from app.goals.progress_contracts import GoalSalesProgressV1
from app.planning_documents.common import Digest, Id, NoAuthority, Positive
from app.planning_documents.context import ConfirmedGoalRef
from app.planning_documents.documents import PlanVersion
from app.publication.contracts import fingerprint

BindingReason = Literal["goal_changed", "goal_unavailable"]


class PlanSalesProgressV1(NoAuthority):
    schema_version: Literal["inlet.plan-sales-progress.v1"] = "inlet.plan-sales-progress.v1"
    workspace_id: Positive
    plan_id: Id
    version: Positive
    document_digest: Digest
    goal: ConfirmedGoalRef
    binding_status: Literal["matched", "unavailable"]
    binding_reason: BindingReason | None
    sales: GoalSalesProgressV1 | None
    as_of: AwareDatetime
    manual_application: Literal["not_assessed"] = "not_assessed"
    attribution: Literal["unavailable"] = "unavailable"

    @field_validator("sales", mode="before")
    @classmethod
    def reparse_sales(cls, value: Any) -> Any:
        # Legacy goal contracts do not revalidate existing nested model instances.
        return value.model_dump(mode="python") if isinstance(value, GoalSalesProgressV1) else value

    @model_validator(mode="after")
    def bound(self) -> "PlanSalesProgressV1":
        if self.goal.workspace_id != self.workspace_id:
            raise ValueError("progress goal workspace changed")
        if self.binding_status == "unavailable":
            if self.binding_reason is None or self.sales is not None:
                raise ValueError("unavailable goal binding cannot carry sales")
            return self
        sales = self.sales
        if sales is None or self.binding_reason is not None:
            raise ValueError("matched goal binding requires sales projection")
        definition = self.goal.definition
        if (
            (sales.workspace_id, sales.goal_id, sales.revision)
            != (self.workspace_id, self.goal.goal_id, self.goal.revision)
            or sales.store_id != definition.store_id
            or sales.target_micros != definition.target_micros
            or sales.target_window != definition.target_window
            or (sales.currency, sales.time_zone)
            != (definition.target_window.currency, definition.target_window.time_zone)
            or sales.definition_digest
            != fingerprint("inlet.goal-progress-definition.v1", definition.model_dump(mode="json"))
            or sales.as_of != self.as_of
        ):
            raise ValueError("exact confirmed goal sales binding required")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def net_sales_micros_exact(self) -> str | None:
        # Never use the JSON numeric field in a JavaScript consumer: it can round.
        sales = self.sales
        if self.binding_status != "matched" or sales is None or sales.net_sales_micros is None:
            return None
        checked = GoalSalesProgressV1.model_validate(sales.model_dump(mode="python"))
        return str(checked.net_sales_micros)


def project_sales_progress(
    document: PlanVersion,
    *,
    sales: GoalSalesProgressV1 | None,
    reason: BindingReason | None,
    as_of: datetime,
) -> PlanSalesProgressV1:
    """Internal projection from an owned canonical document; not an ownership resolver."""
    document = PlanVersion.model_validate(document)
    return PlanSalesProgressV1(
        workspace_id=document.inputs.workspace_id,
        plan_id=document.inputs.plan_id,
        version=document.version,
        document_digest=document.digest(),
        goal=document.inputs.goal,
        binding_status="unavailable" if reason is not None else "matched",
        binding_reason=reason,
        sales=sales,
        as_of=as_of,
    )
