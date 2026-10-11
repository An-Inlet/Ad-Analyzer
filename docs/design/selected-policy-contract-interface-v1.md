# Shared Selected Policy Contract V1

Pure preparatory refactor only. Recognize exact canonical selected-reporting v4
and reserved creative v5 without registering v5 in reporting_capability, changing
the default v3, accepting creative documents, or changing any existing consumer.

Add `selected_policy_contract.py` with:

- `SelectedPolicyContractV1`: frozen strict descriptor containing policy_version,
  generator_version, requires_creative:boolean, and fixed
  reporting_witness_kind=local_reporting_v3. Its validator admits exactly the two
  canonical descriptors; copied/tampered/mixed values fail revalidation.
- `selected_policy_contract(policy_version,generator_version)`: exact strings only;
  returns the v4 descriptor (requires_creative=false) or v5 descriptor (true).
- `assert_selected_ticket_policy(policy_version,policy_digest)`: reconstructs the
  complete canonical PlanningCompositionPolicy for the matching version and
  compares its full digest; no prefix matching, digest coercion or altered fields.
- `assert_selected_composition_policy(policy,*,ticket_policy_version,
  ticket_policy_digest)`: revalidates supplied policy, exact canonical value/digest
  and genuine ticket binding; returns the same descriptor.

Keep the module safe to import from document DTOs: no runtime top-level import of
ports, documents, composition or persistence. Use local imports for policy
construction and TYPE_CHECKING for annotations. No schema/policy relocation is
necessary for this package. Parsing a descriptor confers no generation authority.

This package must not refactor consumer gates yet. Later reviewed work can use the
contract below existing entry validation, preserving v4 bytes and the existing
local_reporting_v3 hashes/witnesses. Genuine v5 requires separate creative basis,
proof, source dependencies and atomic currentness/history integration. Do not
create fake v4 tickets or retag old documents; keep PlanVersion's temporary
creative rejection until those boundaries exist.

Tests cover both complete canonical policies; unknown/mixed/non-string pairs;
wrong/altered digests; altered valid policy options and unsafe copied models;
descriptor tampering; import-cycle safety; and unchanged v4/v5 registration state.
Whole Ruff/configured mypy required. No SQL, runtime, API or default changes.
