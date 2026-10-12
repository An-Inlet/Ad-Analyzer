"""Explicit canonical customer planning selection; no provider or write authority."""

from fastapi import HTTPException

from app.planning_documents.ports import PlanningCompositionPolicy
from app.settings import Settings


def configured_policy(config: Settings) -> PlanningCompositionPolicy | None:
    value = config.customer_planning_policy
    if type(value) is not str or value not in ("v3", "v4", "v5", "v6", "v7"):
        raise HTTPException(503, "Customer planning policy is not configured.")
    # Preserve the established service default and historical injected readers.
    if value == "v3":
        return None
    return PlanningCompositionPolicy(
        version=f"inlet.descriptive-review.{value}",
        generator_version=f"inlet.descriptive-planning.{value}",
    )
