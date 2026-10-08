# Requested Window Evidence Contract — Frozen Private Package

Freeze base `748c215` plus reviewed proposal `a2248d5`. This authorizes only the
contracts-only portion of [the phase-two proposal](planning-window-reader-phase2-proposal.md):
new `app/planning_documents/policy_capabilities.py`,
`app/planning_documents/window_evidence.py`, focused pure tests and a package ledger.
The proposal's reader/adapter/composer/retained-source changes remain future work.
Existing runtime policy, ports, models, routes, source formulas and fixtures stay
unchanged in this package. No migration or provider call is involved.

The proposal's closed policy table, exact canonical ticket digest lookup, private
evidence/gap fields, deterministic UTC-normalized entry keys and exact campaign ×
window slot coverage are frozen. Use its import ownership: new modules may import
ports; ports must not import them at runtime. Registering a recognized v3 contract
does not enable it in the application. Do not add ticket fields or weaken old-policy
validation to make this package fit.

## Exact Validation Requirements

- Revalidate nested/copy inputs before deriving fingerprints or comparing them.
  Strict frozen models reject extra fields, numeric authority and coercive IDs.
- Each metric reference binds the original report's workspace, account, connection,
  platform, native campaign, manifest, generation, privacy and completion time;
  its schema/digest/window bind the requested projection. Retain existing source
  revision conventions. The reference key binds local campaign ID and normalized
  window; the target binds the actual native catalog row, including selection,
  parent identity, display name, budget owner and catalog evidence key.
- `reported_rows_only` requires at least one selected campaign-day row, not merely
  rows elsewhere in the original import. Coverage is partial at most. Selected
  qualification requires explicit selection and a non-null selected count summary;
  missing and generic conversions cannot qualify. Complete selected zero uses the
  frozen projection predicate only.
- Bundle source/context/commerce/freshness checks preserve the existing rules in
  `EvidenceBundle.assert_ticket` without constructing a fake legacy bundle or
  changing an old DTO to fit. Shared helpers may be proposed later; do not refactor
  old validation in this package.
- Exact account pins, catalog-or-gap exclusivity and campaign × window successes
  or gaps are mandatory. Catalog-only gaps require target null; reader reasons
  require the exact catalog campaign. A gap never substitutes for malformed data.
  Reject duplicate slots, extra windows, omitted campaigns, foreign accounts,
  conflicting catalog coverage, changed selectors and mismatched pin digests.
- Keep `MAX_EVIDENCE=400` for combined window successes and window gaps and the
  existing per-field limits. Enforce the 32 MiB UTF-8 serialized collection bound
  on the new bundle, including originals and all other fields, without truncation.
  This capacity is operational, not a recommendation or customer spending limit.

## Focused Acceptance

Test all three closed policy pairs; mixed/unknown versions and mutated ticket
policy digests; unchanged canonical v1/v2 policy digests; v3 runtime remains
rejected by the unchanged composer. Test one/two windows, success/gap mixtures,
empty/absent catalog cases, exact target matching and all rejected slot mutations.
Test UTC-equivalent key identity, nested unsafe copies, expiry equality, privacy,
source, goal/context bindings, exact count capacity and serialized byte bound.
Include positive 100 clicks/10 conversions/USD100, true selected zero and missing
selected data. Existing pure projection and old bundle/composer contract suites
form the focused compatibility cohort. Run whole Ruff, bare mypy and diff checks.
No DB, API, customer-window feature, whole-graph authenticity, aggregate, quality-case
completion or live qualification is established by this private package.
