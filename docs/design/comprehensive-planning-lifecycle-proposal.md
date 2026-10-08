# Comprehensive Customer Plan And Lifecycle — Proposal For Review

Status: research/interface proposal only, 2026-10-08. No schema, product code,
provider/model calls or tests added. Source inventory read at `c736d40`; proposal
branch starts at preserved root `bc31821`. Metadata catalog V2 is owned by the
separate catalog lane. References below describe semantic requirements, not guessed
V2 field names. Root review must freeze the contracts before dependent implementation.

## Product Outcome And Journey

A Shopify brand signs in, connects the supported tools it already uses, describes
a milestone, edits/confirms its measured goal, supplies its budget/period and
aggressiveness, and receives a useful versioned advertising plan. The plan contains
prioritized campaign-specific changes, allocations and alternative scenarios,
creative briefs, evidence/rationale/assumptions and manual application steps. The
customer decides what to do, applies changes outside Inlet and monitors fresh
observations and sales progress. Inlet never publishes, activates, pauses or changes
advertising. Plan acceptance is not provider approval or permission to spend.

Keep Google Ads, Meta Ads and TikTok Ads in the plan contract and representative
acceptance from the start. A brand with one supported connected platform can obtain
a useful scoped plan; absence of another platform/CRM does not block it. Shopify is
the commerce basis. Klaviyo, HubSpot and Omnisend remain planned optional customer
context connections: unavailable context is explicit, never invented or mandatory.
The public illustrative demo is a separate asset, not this customer application.

## Reuse Inventory And Limits

| Existing source | Reuse | Required change or boundary |
|---|---|---|
| `app/goals/schemas.py`, models/service, customer_goals API | Editable Shopify net-sales goal, revision/confirmation, budget period, aggressiveness, history and idempotency | Keep confirmed goal as input reference. Milestone interpreter currently returns clarification; do not claim arbitrary text understanding or call a model. No automatic confirmation. |
| `app/goals/progress.py`, progress_contracts | Closed imported-day progress, source revision/watermark and unavailable reasons | This is observed store progress, not ad attribution, causal lift or proof that a plan worked. |
| `app/planning_catalog/*`, target-catalog API; V2 successor | Owned provider inventory and future exact names/references, per-kind coverage and observation lineage | Consume through an owned evidence resolver once V2 freezes. Old native observation schemas/digests stay unchanged. A catalog is prerequisite evidence, not a plan. |
| `app/analysis/granular.py`, platform_evidence, optimizer findings | Scoped current/comparison metrics, missing-conversion semantics and diagnostics | Recompute from qualified selected sources/windows; severity and legacy fixed confidence are not proof of recommendation impact. Keep B01 positive-conversion behavior. |
| `app/recommendations/service.py` | Bounded ordering/dedup ideas, reason codes | Existing diagnostic-to-review_action rows are not a comprehensive plan; do not inherit execution-ish statuses, fixed confidence or "none without approval" semantics. |
| `app/campaign_review/contracts.py`, service, models/storage | Exact three-provider copy/media validators, hashes, owned asset access, draft/revision/digest patterns | `RevisionInput` currently requires a simulation mandate and `binding()` requires its approval. Do not route the new planning journey through that coupling. Reuse content/media components behind a new plan context; preserve old artifacts. |
| `app/intelligence/schemas.py`, models/repository | Structured strategy, event, creative/experiment/change/decision inputs; optimistic version history pattern | Operator records are not a customer plan aggregate. Their freeform evidence_snapshot and completed status cannot become verified application facts. Customer adapters need explicit scope/role checks. |
| `app/intelligence/calculations.py` | Arithmetic ideas and explicit uncertainty presentation | Do not port mature-cohort assumptions, default elasticity/uncertainty, hardcoded10% transfer or1.25 efficiency gate as validated planning policy. No automatic forecast when inputs/qualification are absent. |
| `initial_planning` previews and planning consent0086 | Non-authorizing evidence/limit checks and explicit numeric preview reasoning | These remain optional referenced previews, not the new plan's mandatory creation path. The new aggregate must not depend on an execution mandate, ledger, admission or ProviderExecutionConsent. |
| `app/outcomes/descriptive*`, measurement history | Source-bound before/after store observations and corrected-publication comparison | Do not import action-effect/settlement/receipt prerequisites or describe association as uplift. |
| `app/lifecycle/archive.py`, exports, registry | Owned bounded export, snapshot/privacy checks and secret exclusion | Add explicit plan dispositions at migration time; plan-specific readable export is new work, not satisfied by a full workspace archive alone. |

## Shared Aggregate Contract — Names Proposed, Not Implemented

Introduce a dedicated customer planning domain, separate from publication/execution.
Strict frozen discriminated documents reject extra fields, revalidate nested values,
use exact integer/decimal money semantics and carry explicit schema/digest domains.
No loose executable payload, arbitrary URL fetch, provider credentials or hidden
permission field belongs in these documents. Bound row/text/byte counts through a
reviewed planning configuration; do not silently truncate or invent launch defaults.

**PlanInputRevision** captures an exact confirmed goal ID/revision/digest, selected
owned accounts, reporting/comparison windows distinct from the future planning
period, plan currency/timezone, user budget ceiling and explicit exclusions/reserve,
aggressiveness, product/offer/audience/creative constraints and customer assumptions.
User-supplied facts have author/time and provenance `customer_supplied`; native and
commerce facts must come from owned source resolvers. Missing clarification fields
are explicit. No model output can supply owned IDs, baseline facts or approval.

**PlanVersion** identifies workspace/plan/version, parent version, input revision,
created actor/time, document digest, generator/policy version and exact evidence
references. It contains an executive summary, campaign action list, alternatives,
budget scenarios, creative briefs, dependencies, measurement/review checklist,
limitations and provider coverage. `advertising_writes_enabled=false` and
`spending_authority=none` are invariant, including exports. Partial/unavailable
sections must explain their limits; plan readiness cannot be inferred from nonempty
text or a successful request.

**EvidenceReference** is a plan-owned immutable reference plus bounded display
projection: provider/source kind, owned account/scope identity, exact observation or
completion/document digest, source revision/generation and privacy revision where
applicable, reporting window, read interval/as-of/expiry, coverage and semantic
metric/unit basis. Catalog V2's exact shape is not assumed. A server-owned adapter
resolves and validates its frozen contract, including stable target identity versus
observation-specific selection identity. Client hashes/names/native IDs are selection
requests only. Never join native targets to metrics by display name. New source
formats get new discriminators; old persisted source evidence is not rewritten.

**PlanAction** has a stable plan-local action identity across versions plus its
version-specific digest; exact owned target reference; type (budget scenario,
status-change suggestion, targeting/query change, bidding-review suggestion,
creative/landing-page task, tracking/data repair, or maintain/no-change);
current/proposed typed values when supportable; ordered priority and rationale;
evidence refs; assumptions; prerequisites/conflicts/dependent action IDs; explicit
expected mechanism and risk/tradeoff; manual steps and verification criteria.
One action cannot stand for conflicting simultaneous settings. Rank can be ordinal
with an explicit policy explanation; do not manufacture measured confidence,
financial return or lift. A generic "review targeting" sentence alone is not an
actionable campaign plan. Supported no-change is a valid recommendation with reasons.

**CreativeBrief** is an independent planning artifact linked to one or more plan
actions: objective, product/offer and permitted claims with source, intended audience,
message angle/hook, copy/storyboard variants, channel/placement/format requirements,
owned media references or explicit asset gaps, landing-page destination, production
checklist and proposed test/measurement plan. Distinguish customer-supplied facts,
observed performance and creative hypotheses. No invented product claims/testimonials.
Reuse Google text and Meta/TikTok media validators for relevant format checks;
passing a format check is not provider review or publication eligibility.

## Budget Scenarios And Native Settings

Represent each scenario as an alternative allocation, not cumulative authority.
Every scenario declares its currency, exact period, total customer ceiling, fixed
allocations, movable allocations, unallocated/reserved-for-planning remainder and
assumptions. Exact totals must reconcile and remain within the confirmed ceiling;
negative amounts, overflow, silent rounding loss and mixed-currency sums fail.
A proposed higher total requires an edited/reconfirmed customer goal/input version;
aggressiveness never raises the ceiling. 5/10/20% remain policy inputs to validate,
not automatic permissions or an unreviewed transfer formula.

Separate three concepts in schema/UI: reported historical spend, an intended plan
allocation over a period, and a current/proposed provider setting. None substitutes
for the others. Do not call a planning remainder "verified remaining spend" when
current coverage, today's spend or another account is unknown. A user-entered
allocation can be a labeled hypothetical scenario without claiming it is a native
campaign amount or a remaining financial balance.

Budget-owner grouping is mandatory for specific native edits. Google shared budgets
appear once with all affected campaigns; child allocations are not added again as
independent spend. Meta campaign/adset and TikTok campaign/adgroup ownership require
qualified hierarchy evidence. Unknown owner, native unit/exponent, schedule, currency
or affected target set means proposed native amount/delta is null with a reason and
manual-discovery prerequisite. Do not infer social micros from a numeric string.
Do not divide lifetime amounts into a supposed daily cap or promise that configured
caps equal delivered/charged spend. Qualified native conversions and ownership are
separate evidence requirements, not something a language model can supply.

Provide baseline/maintain plus customer-selected alternatives when evidence allows;
explicit assumptions determine any modeled outcome range. No elasticity, uncertainty
band, response curve or benefit default is inherited from operator calculations.
An unqualified scenario may compare allocations and tradeoffs without forecasting
sales. Do not rank platforms by noncomparable conversion definitions/windows or sum
platform-reported conversions into unique Shopify customers.

## Persistence, Versioning And Decisions

Proposed entities (migration IDs/schema details reserved only after review): plan
identity/current-head; immutable input revisions; immutable plan versions; normalized
version/action/evidence links for ownership and invalidation; append-only customer
decisions; append-only manual-application assertions; append-only read-observation
results. Use composite workspace ownership for every relation. A plan version's
content and digest never change after save; mutable current-head is CAS-protected.
All writes have scoped idempotency and expected-version checks. Duplicate same intent
returns the original result; changed reuse conflicts. No durable execution/financial
obligation is created by generation, acceptance, export or application tracking.

Keep independent axes instead of one misleading status enum:

| Axis | Proposed semantics |
|---|---|
| Content lifecycle | Draft input → generated version → customer reviewed; later generation/edit creates a successor; archive is local organization. Old versions remain identifiable. |
| Evidence readiness | Ready for manual review / partial / needs clarification / stale / unavailable. Derived from current referenced evidence, not a mutable historical claim. |
| Customer decision | Per exact version/action: undecided, accepted for manual application, rejected, deferred; actor/time/reason. Editing invalidates decision carryover. |
| Customer application assertion | Not reported / customer reports applied / customer retracts or corrects report. Exact version/action, claimed time, optional notes and declared exceptions; never provider verified. |
| Read observation | Not checked / exact proposed fields observed / partially observed / conflict / unavailable, with exact evidence and observation time. This is current-state matching, not proof who applied it or that it caused performance. |

Plan acceptance may record selected action decisions atomically against one exact
version. Skipped actions stay explicitly undecided/deferred. Proposed customer edits
create a new version and re-run validation; do not silently change an accepted plan.
A generation failure leaves the current head untouched. Independent simultaneous
edits conflict cleanly. No automatic decision inheritance into changed scenarios.

Use existing role policy conventions deliberately: owner confirmation/decisions;
explicitly scoped draft editing for permitted collaborator roles, read/export only
where current workspace access allows it. Root must freeze the exact role matrix
before API work; do not broaden current owner-only native reads. Every operation
checks current session/membership/tenant/entitlement as appropriate, before resolving
external storage/reads, after blocking I/O and before persistence. A later legitimate
session can read a plan; do not bind ordinary planning documents forever to one login.

## Corrections, Refresh And Manual Application

Generation consumes explicit owned evidence, with no DB locks held across provider
reads. Recheck source ownership/generation, goal/input version, privacy/retention,
coverage and minimum evidence expiry before committing a review-ready version.
Sources are not an atomic multi-provider snapshot; preserve read intervals and
mismatched-window limitations. Reconnect/renaming must not cross-wire accounts or
silently transfer previous decisions to changed targets.

A source correction, goal/budget edit, native setting drift, privacy erasure or
expiry marks affected current recommendations stale/unavailable via dependency
links. Keep historical content distinguishable from current advice, and redact or
remove derived payload where privacy/retention requires it. Refresh creates a new
version with a field-level diff and reasons; it never overwrites old evidence or
replays an advertising action. A customer may acknowledge historical content but
cannot mark stale advice current by accepting it. Application reports remain
historical assertions; later corrections supersede assertions append-only.

Optional verification performs bounded READS of named expected fields only. It
compares owned current evidence to exact proposed values and records a fresh result;
unsupported fields, target disappearance, unknown units, partial scope or expired
reads yield unavailable/partial, not applied. A matching current state does not prove
causation, change time or customer action. Newly created campaigns cannot be matched
by name alone; bind a separately selected owned target, validate structure, and keep
ambiguous matches unverified. Never use execution receipts/admissions as prerequisites.

Manual steps identify platform/account/campaign and actual known native labels/IDs,
expected old/new value and scope, dependencies, prerequisites and how to check the
result. If V2 metadata or UI navigation is unavailable, say what must be located;
do not fabricate native names/management URLs or pretend the instructions are exact.
Steps may explain how the customer could undo their own change, but Inlet never
sends the forward or reversal mutation. User-reported exceptions are recorded.

Progress links the unchanged confirmed Shopify goal to available closed-day sales
and separately displays ad metrics with their event/window/attribution semantics.
Show completion of customer tasks separately from measured business progress.
Before/after observations and corrections can inform a revised hypothesis, not an
unearned claim that a plan produced causal lift or reached the goal. Optional CRM
context carries its own source/coverage and does not upgrade ad attribution.

## Version History And Export

Expose version list, exact version read, parent/diff and attached decisions/assertions/
observation records. A bounded readable HTML/PDF-style export and structured JSON
export identify plan/version/digest, as-of/expiry, coverage, scenario and budget units,
action-specific manual steps, assumptions and current versus historical status.
Do not export tokens/raw secrets or silently omit unavailable sections. Escape all
text and spreadsheet-formula-sensitive CSV fields if CSV is added. Export is an
owned snapshot with current authorization/privacy checks, not renewed freshness or
permission to spend. Add all new records/evidence projections to lifecycle registry,
export validation, scoped erasure and retention tests before release; these records
are not protected financial obligations.

## Recommendation-Quality Acceptance

Freeze a representative anonymized/synthetic evaluation set before tuning rules.
A reviewer must be able to locate the campaign, understand why each action is
prioritized, inspect its evidence/assumptions, see exact constraints and manually
apply or knowingly defer it. Evaluate the whole useful plan, not just schema validity
or diagnostics counts. All quantitative thresholds/formulas require explicit
versioned policy and rationale; neither legacy severity-confidence mappings nor
model fluency qualifies quality.

| Case family | Required assessment |
|---|---|
| One connected Google, Meta or TikTok brand | Each independently gets campaign-specific priorities, concrete supported changes, alternatives and creative briefs; no requirement to connect every tool. |
| All three connected with comparable evidence | One coherent plan reconciles the customer budget, distinguishes platform metrics and handles cross-platform tradeoffs without duplicate spend or invented attribution. |
| Google shared budget / social ownership ambiguous | Shared owner counted once; affected targets visible; unknown social owner blocks exact native budget edits while allowing evidence-backed nonbudget work. |
| Missing units/FX/schedule or incomparable events | No fabricated amount, delta, combined total, CPA comparison or forecast. Specific missing facts and recovery steps are supplied. |
| Zero events versus positive events | True zero is distinct from unavailable; 100 clicks,10conversions,$100spend cannot trigger no-conversion advice. Small/partial samples cannot justify fabricated certainty. |
| High spend, low return; strong campaign; saturated/unstable campaign | Priorities/tradeoffs trace to actual evidence and policy; preserve defensible no-change and investigation outcomes rather than always moving budget. |
| New brand/sparse data/creative-only request | Useful bounded launch/learning/creative plan with explicit unknowns; no unsupported performance promise. |
| Corrected conversions/refunds, late imports or source reconnect | Dependent recommendations invalidate; refreshed version identifies changed evidence/amounts, original decisions remain historical. |
| Real customer constraints | Inventory/offer/asset capacity, excluded campaigns, fixed allocations and zero budget are respected without inventing assets or commercial claims. |
| Conflicting actions, stale decision, concurrent edit | No contradictory simultaneous plan; CAS/idempotency clean; stale version cannot gain current acceptance. |
| Applied assertion versus native read | Customer assertion never sets verified status; exact read matching cannot claim causation. Partial/conflicting/unknown reads remain labeled. |
| Foreign scope/revocation/privacy/malicious text | No cross-tenant data or target binding, current-session checks hold, exports redact correctly and rendered content is escaped. Every provider mutation remains denied. |

Use deterministic fixture assertions for amounts, ownership, dependencies, factual
claims, evidence lineage and zero writes; actual API/HTTPS journeys for goal→plan→
version edit→decision→manual report→read observation→export→progress. Add a
case-by-case expert rubric: correct scope/facts, specific usefulness, coherent budget,
credible rationale/uncertainty, feasible creative brief, clear manual steps and
honest outcomes. Each critical criterion must pass; a numeric average cannot hide
an invented budget, unsupported effect claim or unusable action. Human expert review
and separately authorized real customer pilots remain outstanding qualification;
offline test success does not substitute for them. No external model/provider call
is part of this proposal.

## Suggested Implementation Order And Review Decisions

1. Freeze aggregate/evidence/action/scenario/brief/decision interfaces together with
   catalog V2 resolver semantics. Confirm role matrix and versioned planning-policy
   source; reserve migration only after review.
2. Implement owned inputs and version persistence/decision history/export, independent
   of execution mandates. Migrate/reuse content/media validators through a new
   planning-context adapter; retain historical campaign artifacts unchanged.
3. Build deterministic comprehensive plan composition over current evidence for all
   three providers, including campaign priorities, bounded budget scenarios and
   creative briefs. Unknown evidence produces precise limits and useful safe work,
   not a thin catalog page marked "complete".
4. Implement manual assertion/correction and read-only field verification, then
   progress/correction-driven successor plans and field-level diffs.
5. Run the frozen quality cases and integrated customer journeys, obtain expert
   review, then authorized read-only pilots and release qualification.

Recommended defaults for review are conceptual, not new numeric policy: separate
new plan aggregate; owner-confirmed exact versions; no automatic amount when native
units/ownership are unknown; no forecast without explicit qualified assumptions;
keep user reports and observed native state independent; permit useful plans from
one supported connected advertising platform. There is no request for execution
permission and no permission bypass in this proposal.
