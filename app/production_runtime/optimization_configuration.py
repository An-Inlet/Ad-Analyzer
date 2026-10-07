"""Pinned nonsecret optimization configuration, never executable evidence."""

import hmac
import json
import re
from pathlib import Path

from app.planning_reporting.configuration import _unique_object
from app.production_runtime.optimization_contracts import OptimizationExecutionManifestV1
from app.production_runtime.optimization_policy_contracts import OptimizationOperatingPolicyV1


class OptimizationRuntimeConfigurationError(ValueError):
    pass


def load_optimization_execution_configuration(
    manifest_path: str | None,
    expected_manifest_digest: str | None,
    policy_path: str | None,
) -> tuple[OptimizationExecutionManifestV1, OptimizationOperatingPolicyV1] | None:
    if manifest_path is None and expected_manifest_digest is None and policy_path is None:
        return None
    if (
        not manifest_path
        or not policy_path
        or not expected_manifest_digest
        or not re.fullmatch(r"[a-f0-9]{64}", expected_manifest_digest)
    ):
        raise OptimizationRuntimeConfigurationError("optimization_configuration_invalid")

    def read(path: str) -> object:
        with Path(path).open("rb") as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            raise ValueError("capacity")
        return json.loads(raw, object_pairs_hook=_unique_object)

    try:
        manifest = OptimizationExecutionManifestV1.model_validate(read(manifest_path))
        policy = OptimizationOperatingPolicyV1.model_validate(read(policy_path))
        if (
            not hmac.compare_digest(manifest.digest(), expected_manifest_digest)
            or not hmac.compare_digest(manifest.operating_policy_digest, policy.digest())
            or policy.environment != manifest.environment
            or policy.evidence_profile_digest != manifest.evidence_profile_digest
        ):
            raise ValueError("binding")
    except (OSError, ValueError, RecursionError):
        raise OptimizationRuntimeConfigurationError("optimization_configuration_invalid") from None
    # Rules are frozen primitive-only models in a tuple, not mutable nested containers.
    # Parse a second canonical copy so no source object can retain mutable aliases.
    return (
        OptimizationExecutionManifestV1.model_validate_json(manifest.model_dump_json()),
        OptimizationOperatingPolicyV1.model_validate_json(policy.model_dump_json()),
    )
