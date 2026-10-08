"""Consuming runtime ports; legacy evidence definitions remain independent."""

from typing import Protocol

from app.planning_documents.ports import EvidenceBundle, GenerationTicket
from app.planning_documents.window_evidence import WindowEvidenceBundleV1

GenerationEvidence = EvidenceBundle | WindowEvidenceBundleV1


class GenerationEvidenceReader(Protocol):
    def collect(self, ticket: GenerationTicket) -> GenerationEvidence: ...
