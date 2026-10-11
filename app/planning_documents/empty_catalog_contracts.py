"""Retained empty declared-query observation, never provider-wide emptiness."""

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, model_validator

from app.planning_documents.catalog_evidence import CatalogEvidence
from app.planning_documents.common import Frozen, Key, fingerprint

MAX_EMPTY_CATALOG_BYTES = 262_144
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


def _instant(value: Any) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware original catalog instant required")
    return value.astimezone(UTC)


def _strict_originals(value: Any) -> None:
    if isinstance(value, BaseModel):
        value = value.__dict__
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _TIME_FIELDS:
                _instant(item)
            elif key in {"advertising_writes_enabled", "atomic_snapshot"} and item is not False:
                raise ValueError("catalog authority flags must be exactly false")
            _strict_originals(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _strict_originals(item)


class EmptyDeclaredCatalogWitnessV1(Frozen):
    schema_version: Literal["inlet.empty-declared-catalog-witness.v1"] = (
        "inlet.empty-declared-catalog-witness.v1"
    )
    catalog_evidence: CatalogEvidence
    prerequisite_action_key: Key

    @model_validator(mode="before")
    @classmethod
    def strict_originals(cls, value: Any) -> Any:
        _strict_originals(value)
        return value

    @model_validator(mode="after")
    def coherent(self) -> "EmptyDeclaredCatalogWitnessV1":
        evidence = self.catalog_evidence
        ref, catalog = evidence.reference, evidence.catalog
        native, metadata = catalog.native_observation, catalog.metadata_observation
        if (
            ref.account is None
            or ref.account.platform != "meta_ads"
            or native.platform != "meta_ads"
            or metadata.platform != "meta_ads"
            or native.targets
            or metadata.entities
            or catalog.targets
            or self.prerequisite_action_key != f"review:account_{ref.account.account_id}"
            or ref.coverage != "partial"
        ):
            raise ValueError("exact empty Meta declared-query observation required")
        if {(c.kind, c.status, c.scope, c.observed_count, c.reasons) for c in native.coverage} != {
            (
                kind,
                "partial",
                "sdk_known_effective_statuses",
                0,
                ("effective_status_scope_limited",),
            )
            for kind in ("campaign", "adset")
        } or {(c.kind, c.status, c.scope, c.count, c.reasons) for c in metadata.coverage} != {
            (kind, "partial", "sdk_known_effective_statuses", 0, ("native_scope_limited",))
            for kind in ("campaign", "adset")
        }:
            raise ValueError("unrecognized empty declared-query scope")
        for observation in (native, metadata):
            if not (
                _instant(observation.reporting_starts_at)
                < _instant(observation.reporting_ends_at)
                <= _instant(observation.observation_started_at)
                <= _instant(observation.observed_at)
                < _instant(observation.expires_at)
            ):
                raise ValueError("catalog observation instants reversed")
        if (
            ref.reporting_window is None
            or _instant(ref.reporting_window.starts_at) != _instant(metadata.reporting_starts_at)
            or _instant(ref.reporting_window.ends_at_exclusive)
            != _instant(metadata.reporting_ends_at)
            or _instant(native.reporting_starts_at) != _instant(metadata.reporting_starts_at)
            or _instant(native.reporting_ends_at) != _instant(metadata.reporting_ends_at)
        ):
            raise ValueError("catalog reporting window instant mismatch")
        if (
            _instant(ref.observation_started_at)
            != min(
                _instant(native.observation_started_at), _instant(metadata.observation_started_at)
            )
            or _instant(ref.observed_at)
            != max(_instant(native.observed_at), _instant(metadata.observed_at))
            or _instant(ref.expires_at) != _instant(catalog.expires_at)
            or _instant(catalog.expires_at)
            != min(_instant(native.expires_at), _instant(metadata.expires_at))
        ):
            raise ValueError("catalog envelope instant mismatch")
        if len(self.model_dump_json().encode()) > MAX_EMPTY_CATALOG_BYTES:
            raise ValueError("empty catalog witness exceeds document bound")
        return self

    def digest(self) -> str:
        checked = type(self).model_validate(self)
        return fingerprint(self.schema_version, checked.model_dump(mode="json"))
