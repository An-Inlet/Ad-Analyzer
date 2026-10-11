"""Private original-session selector binding after ordinary target receipt resolution."""

from app.customers.access import CustomerPrincipal
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.context import PlanInputRevision
from app.planning_documents.google_budget_input_bindings import (
    validate_google_daily_budget_input_bindings,
)
from app.planning_documents.google_budget_intents import (
    GoogleDailyBudgetIntentV1,
    ResolvedGoogleDailyBudgetIntentV1,
)
from app.planning_documents.google_budget_owner_contracts import (
    GoogleBudgetOwnerUnavailable,
    _catalog,
    derive_google_daily_budget_owner,
    resolve_google_daily_budget_intent,
)
from app.planning_documents.google_budget_owner_selection import original_owner_selection_id
from app.planning_documents.source_contracts import SourceFence


def resolve_google_daily_budget_inputs(
    *,
    inputs: PlanInputRevision,
    intents: tuple[GoogleDailyBudgetIntentV1, ...],
    catalogs: tuple[CatalogEvidence, ...],
    sources: tuple[SourceFence, ...],
    principal: CustomerPrincipal,
    privacy_revision: int,
) -> tuple[ResolvedGoogleDailyBudgetIntentV1, ...]:
    inputs = PlanInputRevision.model_validate(inputs)
    checked = tuple(GoogleDailyBudgetIntentV1.model_validate(i) for i in intents)
    catalogs = tuple(_catalog(c) for c in catalogs)
    sources = tuple(SourceFence.model_validate(s) for s in sources)
    by_account = {
        c.reference.account.account_id: c for c in catalogs if c.reference.account is not None
    }
    fences = {s.account.account_id: s for s in sources}
    if len(by_account) != len(catalogs) or len(fences) != len(sources):
        raise ValueError("ambiguous original owner catalogs")
    resolved = []
    for intent in checked:
        catalog, source = by_account.get(intent.account_id), fences.get(intent.account_id)
        if catalog is None or source is None:
            raise ValueError("owner scenario requires original selected catalog")
        matches = []
        for owner in sorted(
            {
                t.budget_owner_key
                for t in catalog.catalog.native_observation.targets
                if t.kind == "campaign" and t.budget_owner_key is not None
            }
        ):
            try:
                witness = derive_google_daily_budget_owner(catalog, owner)
            except GoogleBudgetOwnerUnavailable:
                continue
            selection = original_owner_selection_id(
                actor_id=principal.user.id,
                session_digest=principal.session.digest,
                authenticated_at=principal.session.authenticated_at,
                source=source,
                witness=witness,
            )
            if selection == intent.owner_selection_id:
                matches.append(witness)
        if len(matches) != 1:
            raise ValueError("original owner selection is unavailable")
        resolved.append(resolve_google_daily_budget_intent(intent, matches[0]))
    result = tuple(resolved)
    values = inputs.model_dump(mode="python")
    values["google_daily_budget_intents"] = result
    complete = PlanInputRevision.model_validate(values)
    validate_google_daily_budget_input_bindings(
        inputs=complete,
        intents=result,
        catalogs=catalogs,
        sources=sources,
        privacy_revision=privacy_revision,
    )
    return result
