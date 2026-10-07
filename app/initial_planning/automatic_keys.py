"""Stable initial opportunity identity; refresh and policy revisions cannot reset it."""

from app.optimization_candidates.contracts import CandidateScope
from app.publication.contracts import fingerprint


def native_identity(scope: CandidateScope) -> str:
    return fingerprint(
        "inlet.automatic-native-account.v1",
        {
            "platform": scope.account.account.platform,
            "external_advertiser_id": scope.account.external_advertiser_id,
        },
    )


def owner_identity(scope: CandidateScope) -> str:
    return fingerprint("inlet.initial-rule-native-owner.v1", {"key": scope.budget_owner_key})


def opportunity_key(scope: CandidateScope) -> str:
    return fingerprint(
        "inlet.initial-rule-opportunity.v1",
        {
            "workspace_id": scope.account.workspace_id,
            "environment": scope.mandate.environment,
            "ledger_id": scope.mandate.ledger_id,
            "native_account_identity_digest": native_identity(scope),
            "budget_owner_identity_digest": owner_identity(scope),
        },
    )
