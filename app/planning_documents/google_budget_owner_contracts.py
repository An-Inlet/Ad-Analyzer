"""Retained projected Google owner facts; no authenticity, total cap or write authority."""

from datetime import UTC, datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, model_validator

from app.planning_catalog.contracts import MetaSettingsV1
from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.common import Amount, Currency, Digest, NoAuthority, fingerprint
from app.planning_documents.context import TargetRef
from app.planning_documents.google_budget_intents import (
    GoogleDailyBudgetIntentV1,
    ResolvedGoogleDailyBudgetIntentV1,
)

MAX_OWNER_WITNESS_BYTES = 262_144
_TIME_FIELDS = frozenset(
    {
        "reporting_starts_at",
        "reporting_ends_at",
        "observation_started_at",
        "observed_at",
        "expires_at",
        "starts_at",
        "ends_at_exclusive",
    }
)


_WITNESS_FIELDS = frozenset(
    {
        "schema_version",
        "advertising_writes_enabled",
        "spending_authority",
        "catalog_evidence",
        "owner_key",
        "representative",
        "affected_campaigns",
        "current_amount_micros",
        "currency",
        "cadence",
        "unit",
        "reference_count",
        "explicitly_shared",
        "budget_status",
        "budget_type",
        "atomic_snapshot",
    }
)
_INTENT_FIELDS = frozenset(
    {
        "schema_version",
        "account_id",
        "owner_selection_id",
        "expected_observation_digest",
        "expected_owner_facts_digest",
        "scenario_key",
        "currency",
        "cadence",
        "unit",
        "requested_amount_micros",
    }
)


def _exact_model_graph(value: BaseModel, expected: type[BaseModel]) -> bool:
    """Reject subtype-specific validation/serialization from checked lexical paths."""
    if type(value) is not expected:
        return False
    declared: set[type[BaseModel]] = set()

    def schema(annotation: Any) -> None:
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            if annotation in declared:
                return
            declared.add(annotation)
            for field in annotation.model_fields.values():
                schema(field.annotation)
        else:
            for arg in get_args(annotation):
                schema(arg)

    schema(expected)

    def exact(item: Any) -> bool:
        if isinstance(item, BaseModel):
            return (
                type(item) in declared
                and set(item.__dict__) == set(type(item).model_fields)
                and all(exact(child) for child in item.__dict__.values())
            )
        if isinstance(item, dict):
            return all(exact(child) for child in item.values())
        if isinstance(item, (tuple, list)):
            return all(exact(child) for child in item)
        return True

    return exact(value)


def _checked_witness_eligible(witness: "GoogleDailyBudgetOwnerWitnessV1") -> bool:
    return frozenset(
        GoogleDailyBudgetOwnerWitnessV1.model_fields
    ) == _WITNESS_FIELDS and _exact_model_graph(witness, GoogleDailyBudgetOwnerWitnessV1)


class GoogleBudgetOwnerUnavailable(RuntimeError):
    """Well-formed observation outside the narrow supported owner profile."""


def _instant(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware original catalog instant required")
    return value.astimezone(UTC)


def _meta_schedule_node(value: dict[str, Any]) -> bool:
    # Native schedule absence is distinct from required observation/report times.
    # Exact fields prevent a report envelope with a forged platform discriminator
    # from obtaining this exception; the owning model is still validated afterward.
    return value.get("platform") == "meta_ads" and set(value) == set(MetaSettingsV1.model_fields)


def _originals(value: Any) -> None:
    if isinstance(value, BaseModel):
        value = value.__dict__
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"starts_at", "ends_at"} and _meta_schedule_node(value):
                if item is not None:
                    _instant(item)
            elif key in _TIME_FIELDS:
                _instant(item)
            if key in {"atomic_snapshot", "advertising_writes_enabled"} and item is not False:
                raise ValueError("exact false authority flag required")
            if (
                key in {"explicitly_shared", "budget_explicitly_shared"}
                and item is not None
                and type(item) is not bool
            ):
                raise ValueError("strict boolean sharing flag required")
            _originals(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _originals(item)
    elif isinstance(value, bytes):
        raise ValueError("coerced bytes are not catalog primitives")


def _catalog(value: Any) -> CatalogEvidence:
    _originals(value)
    result = CatalogEvidence.model_validate(value)
    ref, catalog = result.reference, result.catalog
    native, metadata = catalog.native_observation, catalog.metadata_observation
    if ref.account is None or ref.source_revision != ref.account.connection_version:
        raise ValueError("catalog source revision differs from owned generation")
    for observed in (native, metadata):
        if not (
            _instant(observed.reporting_starts_at)
            < _instant(observed.reporting_ends_at)
            <= _instant(observed.observation_started_at)
            <= _instant(observed.observed_at)
            < _instant(observed.expires_at)
        ):
            raise ValueError("catalog real chronology invalid")
    if (
        ref.reporting_window is None
        or (_instant(native.reporting_starts_at), _instant(native.reporting_ends_at))
        != (_instant(metadata.reporting_starts_at), _instant(metadata.reporting_ends_at))
        or (
            _instant(ref.reporting_window.starts_at),
            _instant(ref.reporting_window.ends_at_exclusive),
        )
        != (_instant(metadata.reporting_starts_at), _instant(metadata.reporting_ends_at))
    ):
        raise ValueError("catalog reporting instants differ")
    if (
        _instant(ref.observation_started_at)
        != min(_instant(native.observation_started_at), _instant(metadata.observation_started_at))
        or _instant(ref.observed_at)
        != max(_instant(native.observed_at), _instant(metadata.observed_at))
        or _instant(ref.expires_at) != _instant(catalog.expires_at)
        or _instant(catalog.expires_at)
        != min(_instant(native.expires_at), _instant(metadata.expires_at))
    ):
        raise ValueError("catalog original envelope differs")
    return result


def _parts(
    catalog: CatalogEvidence, owner_key: str
) -> tuple[tuple[TargetRef, ...], dict[str, Any], list[dict[str, Any]]]:
    ref, composite = catalog.reference, catalog.catalog
    native, metadata = composite.native_observation, composite.metadata_observation
    if ref.account is None or ref.account.platform != "google_ads":
        raise GoogleBudgetOwnerUnavailable("google_budget_owner_profile_unavailable")
    campaigns = [t for t in native.targets if t.kind == "campaign"]
    names = [t for t in composite.targets if t.entity.kind == "campaign"]
    for rows, count_field, expected in (
        (native.coverage, "observed_count", len(campaigns)),
        (metadata.coverage, "count", len(names)),
    ):
        coverage = [c for c in rows if c.kind == "campaign"]
        if len(coverage) != 1 or (
            coverage[0].status,
            coverage[0].scope,
            coverage[0].reasons,
            getattr(coverage[0], count_field),
        ) != ("complete", "provider_campaigns", (), expected):
            raise GoogleBudgetOwnerUnavailable("google_budget_owner_coverage_unavailable")
    members = [t for t in campaigns if t.budget_owner_key == owner_key]
    if not members:
        raise GoogleBudgetOwnerUnavailable("google_budget_owner_missing")
    bound = {t.native_settings_key: t for t in names}
    active: list[TargetRef] = []
    facts: list[dict[str, Any]] = []
    settings: dict[str, Any] | None = None
    advertisers: set[str] = set()
    identities: set[tuple[str, str]] = set()
    for row in members:
        target = bound.get(row.selection_key)
        if target is None or target.budget_owner_key != owner_key:
            raise ValueError("owner native/metadata join differs")
        value = row.settings.model_dump(mode="json")
        status = value["status"]
        if status not in {"ENABLED", "PAUSED", "REMOVED"} or target.entity.status != status:
            raise GoogleBudgetOwnerUnavailable("google_budget_owner_status_unavailable")
        budget = {
            key: value[key]
            for key in (
                "budget_amount_micros",
                "budget_total_amount_micros",
                "budget_period",
                "budget_status",
                "budget_type",
                "budget_explicitly_shared",
                "budget_reference_count",
            )
        }
        if settings is not None and budget != settings:
            raise GoogleBudgetOwnerUnavailable("google_budget_owner_settings_disagree")
        settings = budget
        if (
            budget["budget_amount_micros"] is None
            or budget["budget_total_amount_micros"] is not None
            or (
                budget["budget_period"],
                budget["budget_status"],
                budget["budget_type"],
                budget["budget_explicitly_shared"],
            )
            != ("DAILY", "ENABLED", "STANDARD", True)
        ):
            raise GoogleBudgetOwnerUnavailable("google_budget_owner_profile_unavailable")
        reference = target.entity.reference
        advertisers.add(reference.advertiser_id)
        ident = (reference.advertiser_id, reference.entity_id)
        if ident in identities:
            raise ValueError("duplicate owner campaign identity")
        identities.add(ident)
        facts.append(
            dict(
                canonical_entity_key=target.canonical_entity_key,
                entity=target.entity.model_dump(mode="json"),
                settings=value,
            )
        )
        if status != "REMOVED":
            active.append(
                TargetRef(
                    account=ref.account,
                    provider_reference=reference,
                    canonical_entity_key=target.canonical_entity_key,
                    selection_key=target.selection_key,
                    catalog_evidence_key=ref.key,
                    kind="campaign",
                    display_name=target.entity.name,
                    budget_owner_key=owner_key,
                )
            )
    assert settings is not None
    if (
        len(advertisers) != 1
        or not 2 <= len(active) <= 200
        or settings["budget_reference_count"] != len(active)
    ):
        raise GoogleBudgetOwnerUnavailable("google_budget_owner_membership_unavailable")
    return (
        tuple(sorted(active, key=lambda t: t.canonical_entity_key)),
        settings,
        sorted(facts, key=lambda f: f["canonical_entity_key"]),
    )


class GoogleDailyBudgetOwnerWitnessV1(NoAuthority):
    schema_version: Literal["inlet.google-daily-budget-owner-witness.v1"] = (
        "inlet.google-daily-budget-owner-witness.v1"
    )
    catalog_evidence: CatalogEvidence
    owner_key: Digest
    representative: TargetRef
    affected_campaigns: tuple[TargetRef, ...] = Field(min_length=2, max_length=200)
    current_amount_micros: Amount
    currency: Currency
    cadence: Literal["daily"]
    unit: Literal["micros"]
    reference_count: int = Field(strict=True, ge=2, le=200)
    explicitly_shared: Literal[True]
    budget_status: Literal["ENABLED"]
    budget_type: Literal["STANDARD"]
    atomic_snapshot: Literal[False] = False

    @model_validator(mode="before")
    @classmethod
    def strict_originals(cls, value: Any) -> Any:
        _originals(value)
        return value

    @model_validator(mode="after")
    def exact(self) -> "GoogleDailyBudgetOwnerWitnessV1":
        catalog = _catalog(self.catalog_evidence)
        try:
            members, settings, _ = _parts(catalog, self.owner_key)
        except GoogleBudgetOwnerUnavailable as error:
            raise ValueError(str(error)) from error
        if (
            self.representative.model_dump_json() != members[0].model_dump_json()
            or tuple(t.model_dump_json() for t in self.affected_campaigns)
            != tuple(t.model_dump_json() for t in members)
            or self.current_amount_micros != settings["budget_amount_micros"]
            or self.currency != catalog.catalog.native_observation.currency
            or self.reference_count != len(members)
        ):
            raise ValueError("exact derived owner facts required")
        if len(self.model_dump_json().encode()) > MAX_OWNER_WITNESS_BYTES:
            raise ValueError("owner witness exceeds byte bound")
        return self

    def digest(self) -> str:
        checked = type(self).model_validate(self)
        return fingerprint(self.schema_version, checked.model_dump(mode="json"))


def derive_google_daily_budget_owner(
    catalog: CatalogEvidence, owner_key: str
) -> GoogleDailyBudgetOwnerWitnessV1:
    catalog = _catalog(catalog)
    # Validate strict digest even before an unavailable owner lookup.
    from pydantic import TypeAdapter

    owner_key = TypeAdapter(Digest).validate_python(owner_key)
    members, settings, _ = _parts(catalog, owner_key)
    return GoogleDailyBudgetOwnerWitnessV1(
        catalog_evidence=catalog,
        owner_key=owner_key,
        representative=members[0],
        affected_campaigns=members,
        current_amount_micros=settings["budget_amount_micros"],
        currency=catalog.catalog.native_observation.currency,
        cadence="daily",
        unit="micros",
        reference_count=len(members),
        explicitly_shared=True,
        budget_status="ENABLED",
        budget_type="STANDARD",
    )


def owner_facts_digest(witness: GoogleDailyBudgetOwnerWitnessV1) -> str:
    current = GoogleDailyBudgetOwnerWitnessV1.model_validate(witness)
    return _owner_facts_digest_checked(current)


def _owner_witness_digest_checked(witness: GoogleDailyBudgetOwnerWitnessV1) -> str:
    return fingerprint(witness.schema_version, witness.model_dump(mode="json"))


def _owner_facts_digest_checked(current: GoogleDailyBudgetOwnerWitnessV1) -> str:
    catalog = current.catalog_evidence
    native, metadata = catalog.catalog.native_observation, catalog.catalog.metadata_observation
    _, settings, rows = _parts(catalog, current.owner_key)
    assert catalog.reference.account is not None
    value = dict(
        schema_version="inlet.google-daily-budget-owner-facts.v1",
        account=catalog.reference.account.model_dump(mode="json"),
        source_binding_digest=catalog.reference.source_binding_digest,
        owner_key=current.owner_key,
        currency=current.currency,
        time_zone=native.time_zone,
        settings=settings,
        represented_campaigns=rows,
        affected_campaigns=[t.canonical_entity_key for t in current.affected_campaigns],
        removed_policy="collector_status_not_removed_v1",
        native_campaign_coverage=[
            c.model_dump(mode="json") for c in native.coverage if c.kind == "campaign"
        ],
        metadata_campaign_coverage=[
            c.model_dump(mode="json") for c in metadata.coverage if c.kind == "campaign"
        ],
    )
    return fingerprint("inlet.google-daily-budget-owner-facts.v1", value)


def resolve_google_daily_budget_intent(
    intent: GoogleDailyBudgetIntentV1,
    witness: GoogleDailyBudgetOwnerWitnessV1,
) -> ResolvedGoogleDailyBudgetIntentV1:
    """Pure value binding only; opaque selection needs independent owned-session resolution."""
    intent = GoogleDailyBudgetIntentV1.model_validate(intent)
    witness = GoogleDailyBudgetOwnerWitnessV1.model_validate(witness)
    if (
        type(intent) is GoogleDailyBudgetIntentV1
        and frozenset(GoogleDailyBudgetIntentV1.model_fields) == _INTENT_FIELDS
        and _checked_witness_eligible(witness)
    ):
        return _resolve_owner_intent_checked(intent, witness)
    account = witness.representative.account
    if (
        intent.account_id != account.account_id
        or intent.currency != witness.currency
        or intent.expected_observation_digest != witness.digest()
        or intent.expected_owner_facts_digest != owner_facts_digest(witness)
    ):
        raise ValueError("intent requires exact owner observation and currency")
    return ResolvedGoogleDailyBudgetIntentV1(
        **intent.model_dump(mode="python"),
        owner_key=witness.owner_key,
        representative_canonical_key=witness.representative.canonical_entity_key,
        observed_amount_micros=witness.current_amount_micros,
        source_binding_digest=witness.catalog_evidence.reference.source_binding_digest,
    )


def _resolve_owner_intent_checked(
    intent: GoogleDailyBudgetIntentV1, witness: GoogleDailyBudgetOwnerWitnessV1
) -> ResolvedGoogleDailyBudgetIntentV1:
    account = witness.representative.account
    if (
        intent.account_id != account.account_id
        or intent.currency != witness.currency
        or intent.expected_observation_digest != _owner_witness_digest_checked(witness)
        or intent.expected_owner_facts_digest != _owner_facts_digest_checked(witness)
    ):
        raise ValueError("intent requires exact owner observation and currency")
    return ResolvedGoogleDailyBudgetIntentV1(
        **intent.model_dump(mode="python"),
        owner_key=witness.owner_key,
        representative_canonical_key=witness.representative.canonical_entity_key,
        observed_amount_micros=witness.current_amount_micros,
        source_binding_digest=witness.catalog_evidence.reference.source_binding_digest,
    )
