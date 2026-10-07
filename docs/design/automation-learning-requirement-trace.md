# Usable Automation And Learning: Requirement Trace And Next Package

Read-only proposal, 2026-10-07. Source pinned to `ba1e920` (product includes
candidate9580, Shopify512, and customer candidate/measurement interfaces). No
runtime, policy, qualification, financial guard or registry is changed here.
The original attached audit is still not available as a readable local artifact;
this is not a claim to have independently verified its detailed B17 criteria.

## Requirement Versus Chosen Evidence Model

The user's instruction is to optimize existing campaigns within an approved
spending mandate, accept editable confirmed goals, budgets/aggressiveness, review
plans and monitor progress; new campaigns/creative require separate customer
review. The recorded assignment also calls for usable automation and learning,
not just contracts. It does not expressly require causal attribution, a proven
instant of ad delivery, or a universal statistical confidence threshold for every
budget recommendation. Conversely, it does not authorize inventing numerical
rules or presenting reported association as causal or predictive success.

The financial distinction already accepted in
[mandate requirement traceability](mandate-requirement-traceability.md) also applies
here: implementation-selected proof conditions must be described accurately,
without silently removing the user's autonomous optimization objective. This
proposal does not revive the pending recommendation-only product scope change.

The existing directional model chooses a specific, stronger input domain:
`app/directional_feedback/contracts.py::QualifiedDirectionalFactsV1` requires
independent full-window completions; `evaluator.py::evaluate_directional_association`
also requires settled-as-of corrections and authoritative delivery intervals.
`app/outcomes/owned_v3.py::compare_owned_v3` requires timing to interpret action-
associated windows. Those are legitimate conditions for those existing types and
claims, not evidence that all useful operational rules require causal timing.
Keep these types and checks unchanged. In particular, synchronous API completion,
configuration readback time and repeated Meta reports cannot populate them.

## Actual Current Path

| Stage | Existing concrete code | Honest boundary |
|---|---|---|
| Owned campaign reporting | Meta fixed-window acquisition; `reported_feedback/service.py::request_comparison`, `read_comparison`, `reobserve_comparison` | Genuine completed report capsules, exact current source/original request, correction and expiry guards; configuration-observation bracket, not delivery onset. |
| Operational feedback | `reported_feedback/evaluator.py::summarize`, `compare`; service `apply_feedback_preview` and `read_feedback_preview` | Closed-window reported CPA, missing days, repeat spacing/revision checks and explicit policy produce an explained adjusted preview. Existing policy supports one original opportunity; no broad multi-action learning claim. |
| Independent commerce | `commerce/acquisition_service.py`, `acquisition_worker.py`, `independent_owned.py` | Resumable genuine full-window Shopify acquisition with owned encrypted staging and publication. Completion itself remains maturity-unqualified; not ad-account attribution or delivery timing. |
| Association learning | `outcomes/maturity.py`, `owned_v3.py`, `outcome_feedback/snapshot.py`, `directional_feedback/reader.py` and `adapter.py` | Typed pure/local pipeline exists. No genuine authoritative timing/qualified count/calibration producer is registered. New Shopify scans do not automatically fill those gaps. |
| Candidate customer/worker | `production_runtime/candidate_assembly.py`, `candidate_sources.py`, `api/customer_candidates.py` | Real owned native reads, per-original-session jobs, review bridge and customer controls exist. Source registry returns None; base observations are unqualified. Source descriptor is not evidence. |
| Automatic decision | `session_automation/runtime.py`, `worker.py`, service/admission | Original-session Start/status/Stop and durable semantic-epoch admission exist. Getter returns None; configured candidate assembly explicitly supports candidates-only. Missing composition is code, not merely credentials. |
| Financial execution | Existing candidate review/optimization/mandate/ledger | Still independently requires exact consent, native state, qualified exposure and, for repeats, original closure/transition proof. Reported direction cannot manufacture any of these. |

`optimization_candidates/contracts.py::CandidateEvidence` currently has only
unqualified, contract_scenario and qualified_learning. The compiler rejects the
first; service independently checks the latter's registered profile. Therefore
wiring operational feedback into this pipeline by changing a label is invalid.
The customer preview works today; it is not already an automatic candidate source.

## Recommended Next Coherent Package (Requires Interface Review)

Implement a separately versioned **reported-efficiency rule candidate source**
for the already supported Meta existing-campaign budget scope, connected to the
existing customer candidate request/status/review flow and its real worker. This
is an operational, explicitly policy-based recommendation, not mature learning.
Reuse actual current comparison capsules; do not introduce another acquisition
engine, score store or abstract factory with no consumer.

Proposed implementation boundary:

1. A server-owned reader takes the actual original principal, candidate work and
   current owned comparison reference. Call the existing comparison reader and
   dependency validator under the final workspace/session fence. Bind exact
   campaign/native budget owner, complete approved target set, goal revision,
   currency/event/timezone/source generation, original attempt/request and current
   policy. A supplied ID is only a lookup key, never evidence. Reject foreign,
   superseded, incomplete, expired or retracted comparisons.
2. Reuse the existing explicit reported-feedback calculation; do not borrow its
   observation count as independent completion count. A new discriminated evidence
   document names its basis `operational_reported_efficiency_rule`, preserves both
   windows, actual completion commitments, revision checks, policy digest and
   noncausal interpretation. Existing v1 evidence bytes and qualified-learning
   parser behavior stay unchanged. The exact numeric mapping must be registered
   explicitly; no 5/10/20 defaults or best-backtest selection.
3. The candidate compiler uses this separate approved rule type to construct a
   bounded nominal budget suggestion under the same existing mandate/action/
   positive-change/quantum limits. Original semantic opportunity is the immutable
   original attempt/request + native owner/ledger, not report refresh, new policy
   version, a corrected capsule or clock time. Corrections can retract a suggestion
   but cannot mint another admitted action for the same opportunity.
4. Wire the real customer request/status/exact-review consumer first, with a clear
   “reported-efficiency rule” explanation. Preserve deletion-to-candidate erasure
   and review forward denial while retaining attempts/receipts/holds. No adjusted
   preview can bypass this provenance by being copied into a manual action.
5. Then compose the same source into the existing original-session automatic
   admission/worker, as a distinct policy basis explicitly covered by Start consent.
   This is a concrete follow-on, not completed by a candidates-only getter. No
   logout-independent grant, new creative, new campaign or pause override is added.
   Financial qualification remains separate and can truthfully block dispatch.

This is a proposed semantic extension, not permission to weaken the current
qualified-learning gate. Root must approve the exact versioned evidence/admission
union and UI wording before code. The frozen prototype acceptance should use
ordinary configured APIs, genuine fixed-window HTTP fixtures and worker advancement,
not runtime-getter overrides or seeded candidate/results/admissions.

## Acceptance And Real Dependencies

Meaningful tests: actual original optimization/report acquisition to current
comparison to candidate to exact review; zero conversions/missing days/revised
reports block; same opportunity after reobserve or policy revision cannot repeat;
retraction after claim blocks forward work but preserves obligations; session,
source, goal and owner changes during IO deny; neither observation count nor
reported delta becomes an exposure bound; absent policy returns unavailable.
SQLite/PostgreSQL and actual customer HTTPS verify the route, not live performance.

There is no justified universal numerical default. Production registration needs
an explicitly selected rule/profile and evidence supporting its use on the named
scope (conversion event, reporting lag/revision tolerance, minimum data, step and
cooldown). Existing parameterized calibration/sensitivity reports can inform this
choice; they are not prospective validation. The precise owner-facing choice is
whether to permit a clearly described operational reported-efficiency rule under
the existing mandate, versus requiring the stronger mature-action learning basis
before automatic changes. This is narrower than choosing recommendation-only as
the product. Prepare the concrete registered policy and supporting evaluation for
that decision; do not ask for an abstract blank approval.

A first-ever automatic action remains a distinct gap: this repeat-comparison
source requires an original action. Existing initial-planning reported objective/
calibration/native preview can support a separately reviewed first-rule proposal,
but cannot be disguised as prior feedback. Neither package solves missing native
financial/replacement proofs. Genuine live effectiveness remains unverified until
an authorized bounded pilot; no live account action or evidence promotion is
included in this proposal.
