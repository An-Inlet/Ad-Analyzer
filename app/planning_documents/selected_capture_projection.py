"""Adjacent pure projections share validation, never a stored trust capability."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import cast
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from pydantic_core import TzInfo

from app.campaign_performance.capture_settings import CaptureSettingsV1, RequestedAttributionV1
from app.campaign_performance.presence_contracts import (
    AttributionBasisV1,
    CountCellV1,
    MoneyCellV1,
)
from app.campaign_performance.selected_contracts import (
    AggregateDependencyV1,
    CustomerEventSelectionV1,
    ReportingScopeV1,
    SelectedCampaignDayV1,
    SelectedCaptureRequestV1,
    SelectedCaptureV1,
    _selected_capture_digest_checked,
)
from app.planning_documents.selected_observation_provenance import (
    SelectedObservationProvenanceV1,
    _selected_observation_provenance_checked,
    selected_observation_provenance,
)

_MODELS = (
    SelectedCaptureV1,
    SelectedCaptureRequestV1,
    AggregateDependencyV1,
    CustomerEventSelectionV1,
    ReportingScopeV1,
    SelectedCampaignDayV1,
    CountCellV1,
    MoneyCellV1,
    AttributionBasisV1,
    CaptureSettingsV1,
    RequestedAttributionV1,
)
_VALUES = BaseModel.__dict__["__dict__"]
_PRIVATE = BaseModel.__dict__["__pydantic_private__"]
_EXTRA = BaseModel.__dict__["__pydantic_extra__"]
_FIELDS: dict[type[object], frozenset[str]] = {
    model: frozenset(model.model_fields) for model in _MODELS
}
_ZONE = datetime.__dict__["tzinfo"]
_LIMIT = 100_000


def _inert_capture(value: object) -> bool:
    """Callback-free bounded eligibility only; malformed values still require validation."""
    pending = [value]
    seen: set[int] = set()
    visited = 0
    while pending:
        visited += 1
        if visited > _LIMIT or len(pending) > _LIMIT:
            return False
        item = pending.pop()
        kind = type(item)
        if item is None or any(kind is scalar for scalar in (str, int, bool, Decimal, date)):
            continue
        if kind is datetime:
            zone = type(_ZONE.__get__(item))
            if not any(zone is built_in for built_in in (timezone, ZoneInfo, TzInfo)):
                return False
            continue
        if kind is tuple:
            if not item:
                continue
            children = cast(tuple[object, ...], item)
        elif any(kind is model for model in _MODELS):
            resident = _VALUES.__get__(item)
            if (
                type(resident) is not dict
                or len(resident) > _LIMIT - len(pending)
                or any(type(key) is not str for key in resident)
                or set(resident) != _FIELDS[kind]
            ):
                return False
            for descriptor in (_PRIVATE, _EXTRA):
                try:
                    state = descriptor.__get__(item)
                except AttributeError:
                    return False
                if state is not None and (type(state) is not dict or state):
                    return False
            children = tuple(resident.values())
        else:
            return False
        marker = id(item)
        if marker in seen:
            return False
        seen.add(marker)
        if len(pending) + len(children) > _LIMIT:
            return False
        pending.extend(children)
    return True


def selected_capture_projection(
    capture: SelectedCaptureV1,
) -> tuple[str, SelectedObservationProvenanceV1]:
    """Preserve digest-before-provenance order and custom input's original second validation."""
    eligible = _inert_capture(capture)
    checked = SelectedCaptureV1.model_validate(capture)
    digest = _selected_capture_digest_checked(checked)
    if eligible and _inert_capture(checked):
        provenance = _selected_observation_provenance_checked(checked)
    else:
        provenance = selected_observation_provenance(capture)
    return digest, provenance
