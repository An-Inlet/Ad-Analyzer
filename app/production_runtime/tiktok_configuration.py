"""Bounded nonsecret TikTok files; immutable snapshots, no executable configuration."""

import hmac
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.initial_planning.contracts import Frozen
from app.planning_reporting.configuration import _unique_object
from app.production_runtime.tiktok_contracts import TikTokExecutionManifestV1
from app.publication.contracts import fingerprint
from app.publication.social_catalog import TikTokConfigurationProfile
from app.publication.social_review_contracts import SocialRequirements


class TikTokRuntimeConfigurationError(ValueError):
    """Fixed sanitized code; never include file paths or payloads."""


class _BundleDocument(Frozen):
    schema_version: Literal["inlet.tiktok-configuration-bundle.v1"] = (
        "inlet.tiktok-configuration-bundle.v1"
    )
    cover_review_required: Literal[True]
    profiles: tuple[TikTokConfigurationProfile, ...] = Field(min_length=1, max_length=10)
    requirements: tuple[SocialRequirements, ...] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def exact_rules(self) -> "_BundleDocument":
        profiles = [p.digest() for p in self.profiles]
        rules = [r.profile_digest for r in self.requirements]
        if len(set(profiles)) != len(profiles) or len(set(rules)) != len(rules):
            raise ValueError("duplicate profile or rule")
        if set(profiles) != set(rules):
            raise ValueError("exact rules for every profile required")
        if any(p.currency != "USD" or p.currency_exponent != 2 for p in self.profiles):
            raise ValueError("only USD exponent two supported")
        if any(r.wording is None or not r.wording.strip() for r in self.requirements):
            raise ValueError("explicit reviewed wording required")
        return self


@dataclass(frozen=True)
class TikTokConfigurationBundleV1:
    """Canonical bytes own the snapshot; accessors return defensive typed copies.

    Existing social profile/rule models contain mutable nested lists/maps. Keeping
    those objects inside a frozen outer model would not freeze the pinned policy.
    """

    _canonical: bytes

    def __post_init__(self) -> None:
        document = _BundleDocument.model_validate(
            json.loads(self._canonical, object_pairs_hook=_unique_object)
        )
        object.__setattr__(self, "_canonical", document.model_dump_json().encode())

    @classmethod
    def from_document(cls, value: object) -> "TikTokConfigurationBundleV1":
        return cls(_BundleDocument.model_validate(value).model_dump_json().encode())

    @property
    def profiles(self) -> tuple[TikTokConfigurationProfile, ...]:
        return _BundleDocument.model_validate_json(self._canonical).profiles

    @property
    def requirements(self) -> tuple[SocialRequirements, ...]:
        return _BundleDocument.model_validate_json(self._canonical).requirements

    def digest(self) -> str:
        document = _BundleDocument.model_validate_json(self._canonical)
        return fingerprint(document.schema_version, document.model_dump(mode="json"))


def _read(path: str, maximum: int) -> object:
    with Path(path).open("rb") as stream:
        payload = stream.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError("capacity")
    return json.loads(payload, object_pairs_hook=_unique_object)


def load_tiktok_execution_configuration(
    manifest_path: str | None,
    expected_manifest_digest: str | None,
    bundle_path: str | None,
) -> tuple[TikTokExecutionManifestV1, TikTokConfigurationBundleV1] | None:
    """Manifest digest pins bundle digest transitively; all-or-none explicit inputs."""
    if manifest_path is None and expected_manifest_digest is None and bundle_path is None:
        return None
    if (
        not manifest_path
        or not bundle_path
        or not expected_manifest_digest
        or not re.fullmatch(r"[a-f0-9]{64}", expected_manifest_digest)
    ):
        raise TikTokRuntimeConfigurationError("tiktok_execution_configuration_invalid")
    try:
        manifest = TikTokExecutionManifestV1.model_validate(_read(manifest_path, 16384))
        bundle = TikTokConfigurationBundleV1.from_document(_read(bundle_path, 65536))
        if not hmac.compare_digest(manifest.digest(), expected_manifest_digest):
            raise ValueError("manifest digest")
        if not hmac.compare_digest(bundle.digest(), manifest.configuration_bundle_digest):
            raise ValueError("bundle digest")
    except (OSError, ValueError, RecursionError):
        raise TikTokRuntimeConfigurationError("tiktok_execution_configuration_invalid") from None
    return manifest, bundle
