# Comprehensive Planning Contracts V1

Concrete review candidate implementing the approved 49484c4 direction. Pure Pydantic
contracts in `app/planning_documents`; no persistence, API, provider adapter,
recommendation composer, execution mandate, admission or migration is added.
Migration 0087 remains unallocated until persistence design review.

## Role And Boundary Matrix

Owner-only: generate, edit inputs, decide on recommendations, record/retract manual
assertions, and refresh provider evidence. Existing current-workspace read permissions:
list, read, export. These are requirements for the future service, not authorization
implemented by these pure models. Native refresh does not broaden existing account,
connection, subscription, session or source ownership gates.

## Frozen Data Interfaces

- `PlanInputRevision` nests the existing `GoalDefinition`, confirmed goal revision,
  confirmation reference, and domain-separated definition digest. Budget ceiling,
  currency, timezone, period and aggressiveness must equal that definition. Customer
  fixed allocations and exclusions are explicit. Assumptions identify customer provenance.
- `EvidenceRef` declares owned source/document revisions, privacy revision, coverage,
  reporting basis and observation/expiry times. `TargetRef` uses the actual V2 catalog's
  canonical entity, selection and budget-owner keys, but no unfinished catalog consumer
  is imported. `AccountTarget` supports new-brand prerequisite and creative tasks without
  fabricating a campaign. Reference presence is not proof of an actual owned source:
  the future resolver must compare the complete current persisted source/catalog tuple.
- `ManualAction` binds target, priority, dependencies, reciprocal conflicts, evidence,
  assumptions, manual steps, measurement criterion, expected effect and limitations.
  Declarative typed status/country/landing-page before/after values have field-specific
  validation; bidding is explicitly unavailable rather than a invented parameter.
  Budget proposals require exact owner, unit, currency, cadence and arithmetic.
  V1 native amounts support integer micros/minor units only. Decimal major-unit native
  proposals, including TikTok major-unit settings, must be unavailable with a reason.
  No rounding or conversion is supplied. Customer planning allocations still support
  all three platforms; allocation is not a native budget mutation or pacing forecast.
- `BudgetScenario` is an independent alternative, with allocations plus unallocated
  budget exactly equal to the confirmed ceiling. Shared native owners cannot be counted
  twice. Every alternative preserves fixed allocations. Scenarios are never cumulative.
  Zero budget and entirely unallocated budget remain valid. Forecast is null and native
  conversion is not assessed; daily/lifetime values are not converted to period totals.
- `CreativeBrief` binds a creative action and distinguishes product facts from hypotheses;
  it includes evidence, assumptions, placement, format, asset gaps, landing-page constraints,
  hooks, copy/visual directions, required assets, review checklist and measurement plan.
- `PlanVersion` binds exact inputs, ancestry, generator/policy versions, readiness and
  section limitations. It checks ownership consistency, references, DAG dependencies,
  fixed allocations, evidence validity and artifact bounds. Runtime source correction,
  revocation, stale revisions, and current-session checks remain future service gates.
- `CustomerDecision` and `ManualAssertion` bind exact version/document/action digests.
  Acceptance means manual application only. Assertions are customer reports, never
  verification. Corrections/retractions reference prior events; future persistence must
  enforce same owned event chain and CAS/idempotency. `ReadObservedStatus` separately
  compares bounded typed proposed values with observed values and paired evidence refs.
  `assert_document` is mandatory before accepting an event: it validates exact binding
  and compares every supported proposal. No comparison can identify who changed a
  provider setting or infer causal lift. Native budget read-comparison adapters remain
  unavailable in this first structural version; do not claim complete application proof.

## Validation And Limits

Models forbid extra keys, freeze their own fields, and revalidate nested model instances.
The reused legacy goal object is reparsed on entry and on digest validation; it is not
retrofitted with global mutability changes. Store/export canonical JSON, not mutable
in-memory objects, at the future persistence boundary. Domain-separated SHA-256 digests
identify contents; they are not signatures, authorization tokens or evidence verification.

Operational ceilings (20 accounts, 400 evidence refs, 100 actions/allocations, 8 scenarios,
30 briefs, 1 MiB aggregate JSON and bounded field text) limit parsing, human review and
export size. They impose no numeric recommendation, elasticity, expected-return,
aggressiveness percentage or freshness lifetime policy. Expiry is supplied by actual
source evidence; no production default is invented.

Readiness is separate from `quality_status=not_expert_qualified`. A schema-valid document
can still be a poor recommendation. Fixed root quality cases at 25eb733 must evaluate the
future composer unchanged; expert/pilot quality and customer usability remain unqualified.
No persistence/API work should begin before this concrete contract review closes.
