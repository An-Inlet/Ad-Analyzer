# Planning Composition Ports V1 — Concrete Review Candidate

Source: `app/planning_documents/ports.py`. No persistence/API/provider adapter included.

- `GenerationTicket`: server-only operation/actor/session binding, exact immutable inputs,
  expected head/parent, selected SourceFence tuples, privacy revision and policy version.
- `PlanningEvidenceReader.collect(ticket) -> EvidenceBundle`: trusted bounded reads,
  outside any DB transaction. Ticket is never a client request DTO or permission token.
- `EvidenceBundle`: actual reviewed TargetCatalogV2, existing CampaignPerformanceV1/V2,
  GoalSalesProgressV1 documents plus references, explicit gaps and exact customer/policy
  context documents. `assert_ticket` is mandatory: reparse objects, exact generation/input,
  selected accounts/source fences, privacy/window/expiry, actual catalog target mapping,
  duplicate campaign/window denial, no silently missing selected catalog accounts.
- `PlanningCompositionPolicy`: explicit generator/version, no imputation, no forecast,
  no native writes. No elasticity, transfer or aggressiveness percentage defaults.
- `PlanComposer.compose(*, inputs, evidence, policy, version, parent_digest, generated_by,
  generated_at) -> PlanVersion`: pure deterministic consumer; no DB, authority callbacks,
  provider clients or I/O. Service supplies stamps/current versions and validates/rebinds
  output independently; accepting a composer output does not make its references true.

Catalog reference summaries derive actual schema/composite digest/owned source, min start,
max observation, min expiry, exact reporting window and bounded coverage. Performance
references preserve original event/semantics/reporting basis/currency/timezone/window;
no cross-platform conversion equivalence or attribution qualification. V1 is Meta selected-
event reporting; V2 retains Google aggregate or TikTok generic meaning. Missing and actual
zero remain distinct raw values. Existing collectors sometimes default absent conversions
into zero, so zero cannot be promoted to qualified no-conversion evidence by this port:
only positive explicit Meta selected-event values may be `reported_only`, still with
attribution unavailable and reported-row coverage only. Google/TikTok raw values remain
visible, with conversion qualification unavailable. Composer must not call zero qualified
when absence provenance is unproven. Source adapters prove local campaign/native mapping
and persisted manifest contents; schemas alone cannot prove a provider emitted a field.

Performance/commerce documents lack native TTLs: reference expiry is bounded by earliest
actual gathered native catalog deadline, plus final local source/goal/privacy rechecks.
No independent source lifetime is invented. If no actual catalog deadline exists, these
sections are unavailable. Catalog read periods currently max366days; longer input periods
must return an explicit unsupported gap, never silently truncate.

`ContextEvidence` deterministically binds exact persisted PlanInputRevision (customer
product/offer/assumption provenance) or exact configured PlanningCompositionPolicy. Context
expiry cannot exceed actual source evidence; no native catalog can substantiate product
claims. Composer must cite context for customer statements and label hypotheses; policy
reference may support rules only. Claim-level quality remains fixed-case acceptance work.

Customer alternatives are explicit `CustomerScenarioIntent` values in PlanInputRevision:
key/title, exact resolved targets and micros allocations plus unallocated amount. They use
confirmed goal currency/period/ceiling, preserve fixed allocations and are independently
reconciled. BudgetScenario output labels generated vs customer-supplied provenance and
references its input intent; every input alternative is represented unchanged exactly once.
Create/Edit API will accept owned selectors for server resolution, never complete documents.

Final service must additionally verify every candidate target/field/current amount and
reference against actual bundle data, every source against live local ownership/generation,
and exact context/policy artifacts. Those resolvers are not implemented by these ports.
The external identity check's private one-shot fact is not in EvidenceBundle and cannot
become source evidence. Fixed five-second final authority algorithm remains in persistence
interface;0087 reserved to this lane after root ports review.

Customer `maximum_creative_assets` is an optional strict integer0..30 (operational
brief bound); absent means unknown capacity, not unlimited asserted ability. Total
required asset items across briefs may not exceed an explicit capacity. No generated
media references or production capacity is inferred from freeform constraints.

## Port Review Repairs

GenerationTicket now pins the exact configured `policy_digest`, not only its version.
Performance windows must be exactly the requested primary or comparison window; a
valid unrelated historical report is insufficient. Reported-row coverage is partial,
never complete. TikTok generic conversion strings must be finite and nonnegative;
invalid timezone names become validation errors. Commerce reference schema/as-of/
coverage/status/reasons/revision/reporting window derive from actual progress, and
bundle binding compares exact confirmed store/target/window/currency/timezone and the
existing `inlet.goal-progress-definition.v1` fingerprint domain.

Native source fences and reported performance source manifests are distinct domains;
no equality between them is invented. Adapter and final DB-only resolver must pin actual
owned CurrentPerformance completion ID, generation, manifest, window and native campaign
mapping, independently of the native catalog fence. Commerce requires exact owned goal/
store/source revision/watermark/privacy plus fresh time-dependent coverage/staleness
checks. Private service signature agreed with adapter lane:
`recheck_local_sources(db, *, principal, ticket, bundle, now) -> None`. It performs no
provider IO, commit or rollback; every mismatch aborts the transaction. Caller invokes
it under current authority/source locks, then checks final five-second authority age
before atomic writes. Bare payload hashes never replace this resolver.
