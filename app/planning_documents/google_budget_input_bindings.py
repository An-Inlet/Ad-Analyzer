"""Pure original-receipt intent binding; no SQL, selector authority or current TTL."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.context import AccountRef, PlanInputRevision, TargetRef
from app.planning_documents.google_budget_intents import (
    GoogleDailyBudgetIntentV1,
    ResolvedGoogleDailyBudgetIntentV1,
)
from app.planning_documents.google_budget_owner_contracts import (
    GoogleDailyBudgetOwnerWitnessV1,
    _originals,
    derive_google_daily_budget_owner,
    resolve_google_daily_budget_intent,
)
from app.planning_documents.source_contracts import SourceFence

_TIME_FIELDS = frozenset(
    {
        "created_at",
        "recorded_at",
        "starts_at",
        "ends_at_exclusive",
        "reporting_starts_at",
        "reporting_ends_at",
        "observation_started_at",
        "observed_at",
        "expires_at",
    }
)


def _instant(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware original input instant required")
    return value.astimezone(UTC)


def _times(value: Any) -> None:
    if isinstance(value, BaseModel):
        value = value.__dict__
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _TIME_FIELDS:
                _instant(item)
            _times(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _times(item)


def _targets(catalog: CatalogEvidence) -> tuple[TargetRef, ...]:
    account = catalog.reference.account
    if account is None:
        raise ValueError("owned catalog account required")
    return tuple(
        TargetRef(
            account=account,
            provider_reference=row.entity.reference,
            canonical_entity_key=row.canonical_entity_key,
            selection_key=row.selection_key,
            catalog_evidence_key=catalog.reference.key,
            kind=row.entity.kind,
            display_name=row.entity.name,
            budget_owner_key=row.budget_owner_key,
        )
        for row in catalog.catalog.targets
    )


def validate_google_daily_budget_input_bindings(
    *,
    inputs: PlanInputRevision,
    intents: tuple[ResolvedGoogleDailyBudgetIntentV1, ...],
    catalogs: tuple[CatalogEvidence, ...],
    sources: tuple[SourceFence, ...],
    privacy_revision: int,
) -> tuple[GoogleDailyBudgetOwnerWitnessV1, ...]:
    """Validate at immutable input.created_at; callers separately enforce current authority/TTL."""
    if type(privacy_revision) is not int or privacy_revision < 0:
        raise ValueError("strict original privacy revision required")
    if any(
        type(values) is not tuple or len(values) > 20 for values in (intents, catalogs, sources)
    ):
        raise ValueError("bounded tuple input graph required")
    for value in (inputs, catalogs):
        _times(value)
    inputs = PlanInputRevision.model_validate(inputs)
    intents = tuple(ResolvedGoogleDailyBudgetIntentV1.model_validate(v) for v in intents)
    _originals(catalogs)
    catalogs = tuple(CatalogEvidence.model_validate(v) for v in catalogs)
    sources = tuple(SourceFence.model_validate(v) for v in sources)
    accounts = {a.account_id: a for a in inputs.accounts}
    if len(accounts) != len(inputs.accounts):
        raise ValueError("duplicate input account identity")
    source_map = {s.account.account_id: s for s in sources}
    if len(source_map) != len(sources) or set(source_map) != set(accounts):
        raise ValueError("exact full source set required")
    for sid, source in source_map.items():
        if (
            source.account != accounts[sid]
            or source.source_revision != source.account.connection_version
            or source.privacy_revision != privacy_revision
        ):
            raise ValueError("source account generation/privacy differs")
    catalog_map, target_map = _catalog_context(inputs, catalogs, source_map, privacy_revision)
    return _bind_owners(inputs, intents, catalog_map, target_map)


def _catalog_context(
    inputs: PlanInputRevision,
    catalogs: tuple[CatalogEvidence, ...],
    source_map: dict[int, SourceFence],
    privacy_revision: int,
) -> tuple[dict[int, CatalogEvidence], dict[str, TargetRef]]:
    accounts = {a.account_id: a for a in inputs.accounts}
    catalog_map: dict[int, CatalogEvidence] = {}
    target_map: dict[str, TargetRef] = {}
    admitted = _instant(inputs.created_at)
    window = (
        _instant(inputs.reporting_window.starts_at),
        _instant(inputs.reporting_window.ends_at_exclusive),
    )
    if window[0] >= window[1] or window[1] > admitted:
        raise ValueError("original closed input window required")
    for catalog in catalogs:
        ref = catalog.reference
        if (
            ref.account is None
            or ref.account.account_id not in accounts
            or ref.account.account_id in catalog_map
        ):
            raise ValueError("foreign or duplicate catalog account")
        source = source_map[ref.account.account_id]
        if (
            ref.account != source.account
            or ref.source_revision != source.source_revision
            or ref.source_binding_digest != source.source_binding_digest
            or ref.privacy_revision != privacy_revision
            or ref.reporting_window is None
        ):
            raise ValueError("catalog source/privacy differs")
        native, metadata = catalog.catalog.native_observation, catalog.catalog.metadata_observation
        for observed in (native, metadata):
            if (
                _instant(observed.reporting_starts_at),
                _instant(observed.reporting_ends_at),
            ) != window:
                raise ValueError("catalog reporting window differs")
            if not (
                window[1]
                <= _instant(observed.observation_started_at)
                <= _instant(observed.observed_at)
                <= admitted
                < _instant(observed.expires_at)
            ):
                raise ValueError("original catalog admission chronology differs")
        if (
            (
                _instant(ref.reporting_window.starts_at),
                _instant(ref.reporting_window.ends_at_exclusive),
            )
            != window
            or _instant(ref.observation_started_at)
            != min(
                _instant(native.observation_started_at), _instant(metadata.observation_started_at)
            )
            or _instant(ref.observed_at)
            != max(_instant(native.observed_at), _instant(metadata.observed_at))
            or _instant(ref.expires_at)
            != min(_instant(native.expires_at), _instant(metadata.expires_at))
            or _instant(catalog.catalog.expires_at) != _instant(ref.expires_at)
        ):
            raise ValueError("original catalog envelope differs")
        catalog_map[ref.account.account_id] = catalog
        for target in _targets(catalog):
            if target.canonical_entity_key in target_map:
                raise ValueError("duplicate catalog canonical target")
            target_map[target.canonical_entity_key] = target
    return catalog_map, target_map


def _bind_owners(
    inputs: PlanInputRevision,
    intents: tuple[ResolvedGoogleDailyBudgetIntentV1, ...],
    catalog_map: dict[int, CatalogEvidence],
    target_map: dict[str, TargetRef],
) -> tuple[GoogleDailyBudgetOwnerWitnessV1, ...]:
    if intents and inputs.constraints:
        raise ValueError("freeform constraints require clarification")
    if intents and any(key not in target_map for key in inputs.excluded_entity_keys):
        raise ValueError("excluded target cannot be resolved")
    seen: set[tuple[int, str]] = set()
    result: list[GoogleDailyBudgetOwnerWitnessV1] = []
    for intent in intents:
        intent_catalog = catalog_map.get(intent.account_id)
        if intent_catalog is None:
            raise ValueError("intent original catalog missing")
        identity = (intent.account_id, intent.owner_key)
        if identity in seen:
            raise ValueError("duplicate account owner intent")
        seen.add(identity)
        witness = derive_google_daily_budget_owner(intent_catalog, intent.owner_key)
        request = GoogleDailyBudgetIntentV1.model_validate(
            {
                key: value
                for key, value in intent.model_dump(mode="python").items()
                if key in GoogleDailyBudgetIntentV1.model_fields
            }
        )
        rebound = resolve_google_daily_budget_intent(request, witness)
        if rebound.model_dump_json() != intent.model_dump_json():
            raise ValueError("resolved intent differs from original owner witness")
        if intent.currency != inputs.budget_period.currency or (
            inputs.total_ceiling_micros == 0 and intent.requested_amount_micros > 0
        ):
            raise ValueError("intent currency or zero ceiling differs")
        scenario = next((s for s in inputs.scenario_intents if s.key == intent.scenario_key), None)
        if scenario is None:
            raise ValueError("named customer scenario required")
        represented = {
            (t.provider_reference.advertiser_id, t.provider_reference.entity_id)
            for t in target_map.values()
            if t.account == witness.representative.account
            and t.kind == "campaign"
            and t.budget_owner_key == intent.owner_key
        }
        affected = {t.canonical_entity_key for t in witness.affected_campaigns}

        def child_of_owner(
            target: TargetRef,
            account: AccountRef = witness.representative.account,
            owner_members: set[tuple[str, str]] = represented,
        ) -> bool:
            if target.account != account or target.kind == "campaign":
                return False
            ref = target.provider_reference
            parent = (ref.advertiser_id, ref.parent_campaign_id)
            parents = [
                t
                for t in target_map.values()
                if t.account == target.account
                and t.kind == "campaign"
                and (t.provider_reference.advertiser_id, t.provider_reference.entity_id) == parent
            ]
            if len(parents) != 1:
                raise ValueError("child parent cannot be resolved")
            return parent in owner_members

        for key in inputs.excluded_entity_keys:
            target = target_map[key]
            if key in affected or child_of_owner(target):
                raise ValueError("affected campaign or child is excluded")
        allocations = []
        for allocation in scenario.allocations:
            allocated_target = target_map.get(allocation.target.canonical_entity_key)
            if (
                allocated_target is None
                or allocated_target.model_dump_json() != allocation.target.model_dump_json()
            ):
                raise ValueError("scenario target differs from exact catalog")
            if child_of_owner(allocated_target):
                raise ValueError("child allocation duplicates native owner pool")
            if allocated_target.canonical_entity_key in affected:
                allocations.append(allocation)
        if len(allocations) != 1:
            raise ValueError("exactly one affected owner campaign allocation required")
        result.append(witness)
    return tuple(result)


def validate_retained_google_daily_budget_input_bindings(
    *,
    inputs: PlanInputRevision,
    intents: tuple[ResolvedGoogleDailyBudgetIntentV1, ...],
    catalogs: tuple[CatalogEvidence, ...],
    sources: tuple[SourceFence, ...],
) -> tuple[GoogleDailyBudgetOwnerWitnessV1, ...]:
    """Bind original linked receipts only; SQL separately verifies links and opaque IDs."""
    if any(
        type(values) is not tuple or len(values) > 20 for values in (intents, catalogs, sources)
    ):
        raise ValueError("bounded tuple input graph required")
    _times(inputs)
    _originals(catalogs)
    inputs = PlanInputRevision.model_validate(inputs)
    intents = tuple(ResolvedGoogleDailyBudgetIntentV1.model_validate(v) for v in intents)
    catalogs = tuple(CatalogEvidence.model_validate(v) for v in catalogs)
    sources = tuple(SourceFence.model_validate(v) for v in sources)
    accounts = {a.account_id: a for a in inputs.accounts}
    if len(accounts) != len(inputs.accounts):
        raise ValueError("duplicate input account identity")
    source_map = {source.account.account_id: source for source in sources}
    catalog_accounts = [catalog.reference.account for catalog in catalogs]
    if any(account is None for account in catalog_accounts):
        raise ValueError("owned retained catalog required")
    catalog_ids = {account.account_id for account in catalog_accounts if account is not None}
    if (
        len(source_map) != len(sources)
        or len(catalog_ids) != len(catalogs)
        or set(source_map) != catalog_ids
    ):
        raise ValueError("exact original linked source set required")
    for account_id, source in source_map.items():
        if (
            source.account != accounts.get(account_id)
            or source.source_revision != source.account.connection_version
        ):
            raise ValueError("retained source account generation differs")
    if not catalogs:
        if not (
            _instant(inputs.reporting_window.starts_at)
            < _instant(inputs.reporting_window.ends_at_exclusive)
            <= _instant(inputs.created_at)
        ):
            raise ValueError("original closed input window required")
        if (
            intents
            or sources
            or inputs.fixed_allocations
            or inputs.excluded_entity_keys
            or any(s.allocations for s in inputs.scenario_intents)
        ):
            raise ValueError("no-receipt history cannot contain selected targets or owner evidence")
        return ()
    epochs = {source.privacy_revision for source in sources}
    if len(epochs) != 1:
        raise ValueError("retained linked privacy must be unanimous")
    catalog_map, target_map = _catalog_context(inputs, catalogs, source_map, next(iter(epochs)))
    return _bind_owners(inputs, intents, catalog_map, target_map)
