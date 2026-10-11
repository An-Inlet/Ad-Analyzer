"""Consuming runtime ports; legacy evidence definitions remain independent."""

from typing import Protocol

from app.planning_documents.creative_plan_bundle import CreativePairedEvidenceV1
from app.planning_documents.ports import EvidenceBundle, GenerationTicket
from app.planning_documents.selected_paired_evidence import SelectedPairedEvidenceV1
from app.planning_documents.window_evidence import WindowEvidenceBundleV1

GenerationEvidence = (
    EvidenceBundle | WindowEvidenceBundleV1 | SelectedPairedEvidenceV1 | CreativePairedEvidenceV1
)


class GenerationEvidenceReader(Protocol):
    def collect(self, ticket: GenerationTicket) -> GenerationEvidence: ...
