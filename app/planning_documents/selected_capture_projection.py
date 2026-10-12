"""Adjacent pure projections share validation, never a stored trust capability."""

from app.campaign_performance.selected_contracts import (
    SelectedCaptureV1,
    _selected_capture_digest_checked,
)
from app.campaign_performance.selected_inert import _inert_capture as _inert_capture
from app.planning_documents.selected_observation_provenance import (
    SelectedObservationProvenanceV1,
    _selected_observation_provenance_checked,
    selected_observation_provenance,
)


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
