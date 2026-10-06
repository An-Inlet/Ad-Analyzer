# B17 Owned Comparison Qualification Plan

Investigation base: `b05085422cab6ce2a9d5c92c200c865204ae6e9d`.
Retained audit acceptance: **“Comparable mature windows update bounded
recommendations with an explanation.”** Dependencies: B05, B09, B12, B16.
The following is an engineering decomposition, not replacement acceptance criteria.

## What The Installed Backend Actually Proves

| Existing Contract | Proven Fact | Not Proven |
|---|---|---|
| `commerce.evidence.publish/read_publication` | Terminal aggregate publication, exact per-day complete/zero/missing/suppressed state, source window/watermark, definition/currency/time zone, source revision, generation/privacy fence and digest | Refund finality, approved maturity horizon, repeated reconciliation stability or future correction impossibility |
| `publication.coordinator.read_owned_outcome_receipt` and activation reader | Current owner, original attempt/request/review/consent/goal lineage, latest receipt supersession, exact effect or target-state readback where available | Advertising delivery start or cessation time. Dispatch and observed ENABLED state are not proof of treatment time |
| `outcomes.owned.create/read` | Owned receipt plus owned publication, immutable assessment digest, fresh authorization, privacy/retention revalidation, source values and insufficiency reasons | A qualifying comparison. `POLICY` and `OwnedAssessment` v2 force insufficient/null; `current_comparison_available` is always false |
| Pure `outcomes.evaluator.evaluate` | Deterministic comparison and scope/window/maturity/error checks on supplied frozen evidence, including zero/negative baseline behavior | Owned producer qualification; successful fixtures are explicitly synthetic comparable |
| Legacy unified measurement maturity cutoff | A configured GA4/CRM cohort horizon under its own measurement contract | Authority to reuse its default 90 days for Shopify store-total refund maturity |

The currently installed normalized receipt contract permits an authoritative
interval, but this is a type capability, not a factual producer. Creation remains
paused; activation HTTP evidence is target-state-only and does not fill that interval.
Later optimization integration must be evaluated against the same distinction.

## Missing Factual Producers Versus Policy

**Engineering facts that can be produced without inventing policy:**

1. Read two retained terminal publications under the existing workspace/store fence;
   independently validate both hashes, owned source identity, generation, privacy
   epoch, definition, currency and time zone. Prove chronological publication/source
   watermarks and that both cover each requested local day completely.
2. Compare the same day partitions across those publications. Report unchanged,
   revised or unavailable with aggregate revision/digest lineage. Unchanged values
   prove only observed stability between two reconciliations. They do not prove
   finality or maturity. Same publication replay is not independent reconciliation.
3. Produce a separately named descriptive **as-of** comparison of equal local-day,
   closed nonoverlapping windows in one qualified retained publication. It may report
   exact monetary differences and a ratio only for positive baselines, with explicit
   store-total/noncausal/no-maturity interpretation. This is not an action-outcome
   comparison and cannot update recommendations or claim B17 completion.
4. Detect factual overlapping owned dispatches and receipt supersession in a bounded
   observation interval. Absence in owned history is not absence of external edits,
   promotions, prices, stock changes, seasonality or other confounders.

**Policy decisions that facts alone cannot supply:**

- What operational maturity means for Shopify processing-date net sales, including
  acceptable lag, required reconciliation count/separation, observed correction
  tolerance and invalidation/reassessment rules. A time cutoff alone is insufficient.
- Whether action comparison requires actual delivery evidence or a precisely named
  alternative state-observation estimand. A status receipt must not silently become
  an action-delivery interval.
- Which bounded recommendation changes a descriptive comparison may support,
  minimum evidence requirements and how warnings alter recommendations. Nothing
  here grants execution authority or increases a spending mandate.

## Narrow Owner Decision

Choose the meaning of **mature** before enabling a maturity label:

- **Operational maturity:** approved lag plus independently completed source
  reconciliations, complete stable partitions, current privacy/generation/revision
  checks and explicit reopening on corrections. It is qualified as-of evidence,
  never a promise that future corrections cannot occur.
- **Authoritative finalization:** require a supported source finalization guarantee.
  The current Shopify producer provides none, so it would remain unavailable.

Recommendation: operational maturity is the practical product direction, but first
approve the actual lag and stability/correction criteria for the target stores.
No 7-, 30- or 90-day value is assumed by this plan. An owner selecting a label alone
is not sufficient to fill the required numeric criteria. Independent descriptive
and reconciliation-stability work can proceed while this is decided.

## Implemented Independent Descriptive Interface

Owned action-assessment v2 remains unchanged. The separately approved frozen
`inlet.descriptive-comparison.v1` interface is a read-only POST at
`/api/customer/v1/workspaces/{workspace_id}/descriptive-comparisons`, requiring an
owner session and same-origin CSRF. It never commits or persists a comparison.

- Request: owned goal ID, expected current goal revision, publication ID and
  half-open local windows (combined span at most 400 days). Optional
  prior publication ID selects factual stability evidence. Never accept values,
  mature flags, delivery timestamps or provider envelopes from the client.
- Response: schema/version, exact source/publication digests, generation/privacy
  epoch, evaluated-as-of, local and UTC windows, scalar values or null, fixed reasons,
  `description_status=available_as_of|insufficient`, absolute/relative difference,
  `maturity=unqualified`, `action_attribution=unavailable`, `causal_lift=null`,
  `recommendation_update=null`, `spending_authority=none`.
- Stability: `not_requested|unchanged_observed|revised_observed|unavailable`, exact
  prior/current publication lineage and examined day count. No `mature_through`.
- Use existing retained-publication authority/retention gates; no new persistence
  required for a read projection. If durable comparison storage is later required,
  reserve the migration and both publication foreign keys/privacy cascade first.
- Future mature action-assessment schema must carry approved policy digest,
  authoritative effective interval, separate maturity evidence, current receipt
  lineage and an explained bounded recommendation. It cannot inherit qualification
  from this descriptive result.

No current UI should render positive sales, elapsed time, stable values or ENABLED
readback as mature/comparable. UI owner has been informed; dependent UI changes are separate work. New migration, live provider calls and policy activation are not
part of this investigation.

## Focused Acceptance Plan For Implementation

Use actual terminal commerce publications and persisted MockTransport coordinator
receipts on SQLite/PostgreSQL. Cover complete/zero/missing/suppressed partitions;
positive, zero and negative baselines; equal local days across DST; unequal periods;
currency/zone/definition/generation changes; old/replayed/future publication;
reconciliation revisions; receipt success superseded by unknown; privacy erasure
and a reader waiting behind its fence; owner/session revocation; bounded response.
Assert all as-of comparisons retain unqualified maturity and null recommendation,
causal lift and spending authority. Tests must not invent a mature production case
until its producer and approved policy exist.

## Implementation And Verification Checkpoint

Implemented types: `app/outcomes/descriptive_contracts.py`; factual projection:
`app/outcomes/descriptive.py`; owner route: `app/api/customer_descriptive.py`.
Current revision is read under the workspace/store/goal fences, source publication
metadata is checked against its hashed manifest, and PostgreSQL statements use a
transaction-local two-second timeout. Authorization is refreshed after blocking
locks and before returning. Dependency teardown rolls back the read transaction;
there is no explicit commit, stored comparison, new table or export serializer.

Observed stability requires a different retained publication with increasing
publication revision, published time and terminal source watermark, matching
source/basis/privacy, and complete settled-as-of requested partitions. A replayed
publication cannot establish stability. Day-by-day values, state and entry counts
are compared; equal totals hiding changed daily partitions do not imply stability.
The comparison requires current latest publication/source revision; old or in-flight
source views cannot produce qualified current arithmetic. Privacy-invalidated or
expired references fail closed rather than reconstructing retained values.

Focused validation: **78 passed, 2 skipped** across descriptive comparisons, owned
assessments, existing pure outcome evidence and assembled route boundary inventory.
Both skips are SQLite-only row-lock concurrency cases; their PostgreSQL variants
passed. Tests include actual terminal importer publications, revisions/refunds,
zero/negative ratios, rehashed metadata mismatch, foreign prior source, real owner
sessions/CSRF/logout, goal changes and erasure while a reader waits. Existing pure
window cases cover DST/calendar invariants. Ruff passed; configured mypy passed
442 files; diff check passed. No Full/CI dispatch or live environment was used.

Remaining decision is still the numeric operational maturity and correction policy,
plus authoritative action-time evidence and bounded recommendation rules. This
package adds independent factual utility; it does not complete B17.
