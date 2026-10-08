"""Explicit legacy policy selection only for historical V2 pipeline acceptance."""

from typing import Any

import pytest
from app.api import customer_planning_documents as api
from app.planning_documents.composer import GENERATOR_VERSION, POLICY_VERSION
from app.planning_documents.ports import PlanningCompositionPolicy
from app.planning_documents.service import PlanningDocumentService


def legacy_v2_policy() -> PlanningCompositionPolicy:
    return PlanningCompositionPolicy(version=POLICY_VERSION, generator_version=GENERATOR_VERSION)


def configure_legacy_v2_api(monkeypatch: pytest.MonkeyPatch) -> None:
    class LegacyV2Service(PlanningDocumentService):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.policy = legacy_v2_policy()

    monkeypatch.setattr(api, "PlanningDocumentService", LegacyV2Service)
