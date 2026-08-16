"""Deterministic, human-review-only recommendation generation."""

from app.recommendations.service import (
    RecommendationCandidate,
    RecommendationGenerationResult,
    RecommendationGenerationService,
    RecommendationScopeType,
)

__all__ = [
    "RecommendationCandidate",
    "RecommendationGenerationResult",
    "RecommendationGenerationService",
    "RecommendationScopeType",
]
