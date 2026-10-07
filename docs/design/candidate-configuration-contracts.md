# Candidate Configuration Contracts

Local pure-contract package based on root2bc857b and proposal08192aa. No runtime,
API, scheduler, schema, settings or producer is installed by this package.

## Frozen Callables

`production_runtime.candidate_configuration`:

- `load_candidate_configuration(manifest_path, expected_manifest_digest, policy_path,
  *, optimization_manifest, source_descriptor=None) -> (CandidateAssemblyManifestV1,
  CandidatePolicyBundleV1) | None`.
- `validate_candidate_source(manifest, bundle, descriptor) -> None`.

All three file configuration values unset returns None. Partial, malformed,
duplicate-key, oversized or incorrectly pinned configuration raises sanitized
`CandidateConfigurationError`. The loader reads at most16KiB+1 manifest bytes and
64KiB+1 bundle bytes, parses JSON without duplicate keys or nonfinite values,
validates exact optimization manifest/environment and bundle digest, and rejects
session policies in candidates_only mode. Automatic operations must be among the
configured optimization providers. No native/provider construction occurs.

A returned document pair is **parsed configuration only**. If source_descriptor is
None, no source has been checked and assembly MUST remain unavailable until an
actual registration is found and validate_candidate_source succeeds. A supplied
false descriptor pin fails closed; the loader never substitutes a default source.

Bundle environment is explicit. At most64 candidate and64 automatic policies are
retained; duplicate workspace/policy/revision identities, cross-environment or
cross-workspace references, missing references and wrong exact candidate digests
fail. Engineering capacities are not product policy. Existing candidate optional
numbers remain None; parsing an automatic policy does not make those numbers
configured or permit automatic capability. Existing policy_for/compiler gates stay.

`FrozenCandidatePolicy.as_policy()` and `FrozenAutomaticPolicy.as_policy()` return
fresh existing policy objects for each consumer. New frozen copies preserve the
existing JSON fields, defaults, array representation and digest domains. Nested
automatic references and operation/family collections are immutable. New bundle
and manifest use their own versioned digest domains; no old bytes are rewritten.

## Trusted Source Port

`production_runtime.candidate_sources` exposes:

- `RegisteredCandidateEvidenceSource(descriptor, build)`; descriptor is validated
  and defensively copied.
- `build(candidate_base, bound_principal, identity, clock) -> CandidateEvidenceBinding`.
- `validate_candidate_binding(descriptor, binding) -> None`.
- `registered_candidate_source(source_id) -> RegisteredCandidateEvidenceSource | None`,
  currently always None; no mutable global registry or dynamic import mechanism.

Descriptor fields pin source ID, environment, source schema, kind, bundle digest,
feedback dependence, exact qualified profiles and semantic producer families.
Kinds are unqualified_observation, contract_scenario and qualified_learning.
Scenario/live combinations are invalid. Known raw association/reconciliation
schemas cannot be promoted by a descriptor. Qualification profiles are exact
schema/name/revision/digest commitments, with conflicting identities rejected.
They declare expected evidence; they are not factual evidence themselves.

A binding exposes only authorized evidence transform, authorized final-current
check and optional existing semantic epoch producers. Non-unqualified sources
require both callbacks. Unqualified sources cannot supply callbacks or epochs.
Producer family/schema/environment must exactly match the descriptor, and each
producer requires the principal-aware authorized_read callback. No timestamp,
refresh revision or first-action epoch is generated here.

These structural checks do not establish the scientific or provider guarantees of
a callback. Future request-owned assembly must preserve existing compiler/profile
allowlists, final authority/session checks, and real-HTTP contract-test rejection.
It must never treat reported operational comparisons as qualified learning or
bypass financial qualification. No real callback or numerical policy ships enabled.

## Validation

Focused tests verify legacy canonical JSON/digest preservation, unset numeric
inputs, fresh consumer copies, nested immutability, both manifest modes, exact pins,
references, environments, duplicate JSON keys, bounded files, malformed numerics,
source absence, prohibited evidence promotion and mandatory authenticated callbacks.
No database, provider request, Full or remote operation is needed for these pure
configuration checks. Exact terminal results are recorded in the package handoff.

Frozen validation: **33 passed in0.41s** for the candidate configuration and existing
optimization runtime contract suites; whole-repository Ruff, focused mypy for the
two new production modules and their test module (3 files), and diff checks passed.
Two fresh Python subprocesses imported configuration-first and sources-first
successfully, without test bootstrap. FrozenCandidatePolicy contains only strings,
integers, literals and optional integers; the separate automatic-policy wrapper
freezes its nested reference and tuple collections. Mutation/roundtrip tests cover
both legacy policy forms. No source registration was added.
