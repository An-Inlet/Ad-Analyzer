"""Untrusted exact capture selectors; reserved v4 identifiers grant no capability."""

from app.planning_documents.common import Frozen, Id, Positive, unique

SELECTED_POLICY_VERSION = "inlet.descriptive-review.v4"
SELECTED_GENERATOR_VERSION = "inlet.descriptive-planning.v4"


class SelectedCaptureSelectorV1(Frozen):
    account_id: Positive
    capture_id: Id


def validate_selected_accounts(
    selectors: tuple[SelectedCaptureSelectorV1, ...] | None, accounts: tuple[int, ...]
) -> None:
    if selectors is None:
        return
    unique(tuple(s.account_id for s in selectors), "selected capture account")
    if any(s.account_id not in accounts for s in selectors):
        raise ValueError("selected capture account must be included")


def reject_legacy_selected(
    selectors: tuple[SelectedCaptureSelectorV1, ...] | None,
    policy_version: str,
    generator_version: str,
) -> None:
    if selectors is not None and (policy_version, generator_version) in {
        (f"inlet.descriptive-review.v{v}", f"inlet.descriptive-planning.v{v}") for v in (1, 2, 3)
    }:
        raise ValueError("selected reporting requires an available selected-reporting policy")
