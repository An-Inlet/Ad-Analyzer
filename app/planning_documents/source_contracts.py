"""Shared immutable planning source fence; construction grants no authority."""

from pydantic import Field

from app.planning_documents.common import Digest, Frozen, Text
from app.planning_documents.context import AccountRef


class SourceFence(Frozen):
    """Private owned local source tuple, checked again after all external reads."""

    account: AccountRef
    source_binding_digest: Digest
    source_revision: Text
    privacy_revision: int = Field(strict=True, ge=0)

