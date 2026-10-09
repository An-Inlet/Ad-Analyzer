# Next Planning Quality Acceptance — Proposal V1

Docs-only proposal from frozen W1 `6a3b0f1`. No implementation, test run, source
activation, migration or new public claim accompanies this document. Root review is
required before dependent work. W1's existing validation checkout/database/run must
remain untouched. The frozen [Q01–Q16 cases and six criteria](comprehensive-planning-quality-cases.md)
are unchanged; this proposal specifies a reproducible Q16 fixture rather than
weakening or renaming that case.

## Decision And Dependency Order

**Recommend the exact assembled Q16 privacy/progress package next.** Existing
current API, lifecycle erasure, retained proofs, immutable history and exact sales
projection already provide its required interfaces. What is missing is the frozen
common-basis assembled acceptance, particularly later-closed-day browser evidence
and post-erasure non-resurrection across all plan endpoints. This is a bounded
acceptance/evidence package; any discovered product defect is reported with a
minimal proposed repair before expanding the contract.

Google/TikTok selected-event producers are necessary for later Q01/Q02/Q09 evidence,
but are not prerequisites for Q16. They require separate provider-specific capture,
publication and completion contracts. Doing them first would add production work
without closing Q16's existing testable gap. Neither order can replace the separate
human expert assessments or turn descriptive advice into comprehensive quality.

1. Freeze the Q16 fixture and endpoint/assertion matrix below.
2. Implement its actual service/API cases on both database backends, with current
   policies/guards unpatched. Freeze reusable setup before dependent browser work.
3. Add actual HTTPS/Chromium progress and privacy branches against that setup;
   record exact observed results and omissions. Do not infer a full Q16 pass from
   independent component cohorts.
4. In a separate reviewed package, freeze Google selected-event producer semantics,
   then implement raw import→immutable sidecar→requested-window customer API Q01/Q02.
   TikTok's corresponding producer remains a distinct subsequent seam. These must
   retain unknown attribution/coverage where the provider response does not prove it.
5. Keep W1 aggregate disposition, substantive recommendation work, expert evaluation
   and commercial/release gates separately tracked.

## Frozen Synthetic Fixture Proposed For Q16

Use the existing public workflow, never insert a precomposed PlanVersion or fake
success receipt. Start with current owner/session, paid read entitlement and owned
Shopify source. Confirm an actual GoalDefinition and persisted preview/confirmation:

- Currency USD; time zone `America/New_York`; target and baseline use the supported
  `calendar_month` basis. Baseline September2026 is complete and exactly
  **8,000,000,000 micros**. Target November2026 is **12,000,000,000 micros**;
  deadline November30. November budget ceiling **1,000,000,000 micros**, balanced.
- Primary reporting window September1 local midnight to October1 local midnight;
  comparison August1 local midnight to September1 local midnight. Submit exact
  offset-bearing server-supported timestamps. No substitution of seven-day UTC
  examples for these frozen periods.
- Customer facts: reusable travel mug, $25 list price, one owned product image,
  no approved health claims/testimonials. The image is an actual offline fixture
  asset with owned provenance, not an invented uploaded provider asset.
- One genuinely owned Google account/campaign/ad group is sufficient for Q16,
  which does not prescribe a platform count or selected-conversion values. Use
  current actual native MockHTTP acquisition and exact IDs. Its unsupported
  selected-event evidence remains an explicit gap; never seed qualified sidecars
  to make the case look complete. The comparison remains requested even when
  its reporting facts are unavailable. No native budget qualification is invented.
- Use two independent owned workspaces for the two branches below, plus an
  unrelated foreign workspace. Q16 explicitly says progress is tested separately;
  do not recreate an erased graph to continue a progress demonstration.
- Explicit synthetic time: initial progress as-of November3,2026 00:05 New York;
  later as-of November4 00:05. Initial target net sales is known0 across the actual
  covered closed prefix. A real imported November3 order for the $25 mug makes
  later sales **25,000,000 micros**. A real correction/refund of $5 on that same
  order makes it **20,000,000 micros**. These are test facts, not predicted lift.
  Assert the exact source-local closed-day prefix grows by one. Use genuine
  CommerceSync imports and coverage/watermark publication, not direct amount edits.

The fixture must establish coherent fresh identity/session, paid snapshot, native
receipt deadlines and source clocks at each test stage. Use explicit synthetic
clock/input configuration, actual login/paid reconciliation where required and new
native observations for new generation. Do not extend production TTLs, roll clocks
back, suppress final freshness checks or reuse a pre-expiry authority fact across
waits. If the existing harness cannot represent these fixed dates, report that
fixture limitation before changing a frozen date or asserting acceptance.

## Reused Shared Interfaces — No New DTO Or Runtime Contract

| Boundary | Exact existing seam and caller obligation |
|---|---|
| Goal | Existing create/edit→preview→confirm API and exact ConfirmedGoalRef; preserve the original definition and confirmation through every read. Imported baseline proves $8,000, not copied narrative. |
| Customer plan | Current `/api/customer/v1/workspaces/{wid}/planning/plans` create and `/{plan_id}/generate`; actual default canonical V3 reader/composer/repository. No client-supplied complete PlanVersion proof. |
| Read/history/export | `/{plan_id}`, `/{plan_id}/versions`, `/{plan_id}/versions/{version}`, `/{plan_id}/events`, `/{plan_id}/export?version=N`; preserve actual owned permission and historical artifact semantics. Artifact export is not a promise of complete workspace event history. |
| Request replay | Existing `/requests/{operation}/{request_key}` and exact create/generate replay; operation remains the current closed type. An erased graph cannot be returned from an old success receipt or reconstructed by replay. |
| Manual report | Existing decisions/assertions endpoints with server document/action digests and exact event CAS. Record an unverified customer report; neither report nor retraction changes measured sales. |
| Progress | `PlanningDocumentService.sales_progress(principal,wid,plan_id,version)` and required-version GET `/{plan_id}/progress?version=N`; existing `PlanSalesProgressV1`, `Cache-Control:no-store`, exact `net_sales_micros_exact` string. No percentage, causal attribution, achieved-target state or new history row. |
| Authority/read session | Existing API detach/rollback and hardened `_read_session`; identity refresh outside SQL, current locked owner/read permissions and unchanged final five-second authority fence. Preserve401/403 rather than converting auth failure to unavailable sales. |
| Erasure | Existing current lifecycle operation under its workspace/source locks, using `bump_workspace_export_revision` as the established semantic-erasure seam where appropriate. Assert actual complete plan graph and scoped dependent evidence removal; ordinary source correction must not be substituted for semantic erasure. |
| Workspace archive | Existing authorized archive creation/delivery and scoped serializers with their real snapshot/byte/privacy gates. An archive begun before erasure must fail current delivery privacy checks; a new archive must contain no removed graph. No custom test-only export serializer. |

Implementation should freeze a **test-only** fixture result before parallel browser
work: owned `workspace_id`, `plan_id`, saved version/digest, confirmed goal identity,
owned source IDs, exact request keys and controlled raw commerce response queue.
Do not export ORM sessions, mutable authority facts, composition callbacks or ready-
made documents as positive inputs. API responses may be retained as expected
historical bytes for comparison, not reused as authority.

## Acceptance Matrix

### A. Privacy Branch

Create/generate V1 and its real decision/report through authenticated routes. Capture
its exact immutable artifact and independent event history. Create an export using
the existing archive workflow, retaining its actual pending/delivery reference.
Perform scoped semantic erasure through the existing lifecycle path.

- Fresh current/history/version/event/artifact/progress requests for removed graph
  return the actual owned-unavailable result (normally404); lists exclude it.
  Replay lookup cannot disclose the old input/version/event payload. Mutation or
  refresh attempts referencing erased IDs fail with a controlled404/409 and no
  new plan/input/version/dependency/event/request-receipt rows. Do not pin an
  incorrect response code instead of inspecting the existing intended contract.
  This does not prohibit an explicit fresh create with a complete client-retained
  payload: that operation has a new plan UUID and must pass current validation.
  Erased receipts do not create a permanent ban on reusing a request key. No
  tombstone policy or blanket no-new-create-row assertion is introduced; see the
  [clock/fixture feasibility clarification](q16-fixture-feasibility-20261009.md).
- Verify complete scoped graph counts, including receipt/input links and relevant
  retained-source/evidence dependencies. Preserve unrelated workspace rows and
  protected financial records according to existing lifecycle rules; erasure
  is not permission to delete unrelated finance. No new financial records exist.
- Deliver the pre-erasure archive through its real current privacy authorization:
  no stale private payload is released. A post-erasure archive explicitly omits
  removed graph data; an incomplete/failed archive is never called complete.
- Browser refresh/history/export/progress cannot repopulate the removed version
  from a late response or old request receipt. A copy already downloaded before
  erasure is outside server revocation; do not claim remote deletion of that copy.
- Preserve current foreign-workspace and revoked-session denial while testing
  erased IDs. No full-table teardown or shared-database reset.

### B. Separate Progress Branch

Generate one immutable V1 at the fixed common basis. Record one actual unverified
manual application report. Read exact saved-version sales at initial known0, then
perform the later closed-day import and the same-order correction described above.

- Customer API and visible browser show0→$25→$20 with exact micros strings,
  source-local coverage, as-of time and corrected source identity. Do not round
  through JavaScript Number or infer zero when measurement becomes unavailable.
- The original V1 document/digest and artifact remain byte-for-byte unchanged;
  reads create no new plan version, snapshot, event or request receipt. Report
  history remains independent; sales changes do not auto-complete tasks and a
  report does not produce a provider-observed match or causal claim.
- Confirmed-goal revision change yields the existing controlled unavailable binding
  for the original version, preserving its original goal. Same-owner session
  replacement rejects a late response. These checks reuse, rather than weaken,
  the current authority and UI epoch mechanisms.
- Assert no additional native provider calls/imports during progress-only reads,
  no advertising mutation requests, and no execution mandate/consent/admission/
  attempt/financial obligation produced by the planning journey.

Record an exact assertion-to-case matrix, both database results, browser trace/log
and every skip/failure. Preserve the existing signed/unsafe-integer regressions;
this bounded positive Q16 arithmetic does not replace them. Human expert assessment
and the other fifteen cases remain separate even if this package passes.

## Deferred Selected-Event Producer Interface Requirements

No production interface is frozen here. Before Google or TikTok implementation,
review each mapping against actual owned collectors and raw response contracts:

- Explicit event identity and requested/actual date, account, currency/time-zone,
  attribution and native campaign bindings. Unknown identity/attribution is not a
  provider-default assumption. Absent field and explicit0 remain distinct.
- New immutable presence facts must fit the reviewed `presence_contracts.py`
  domains/bounds and completed-source publication rules. Derive count/value
  presence from original raw input before legacy normalizers can default it to0.
- Exactly one finalized header/fact graph per real completion with actual manifest,
  source generation, privacy and row mapping. Staging/retry/atomicity must match
  that provider's existing importer; Meta0090 mechanics are not a generic contract.
- Requested-window readers consume the real completed graph and preserve full-source
  invalidation outside the requested slice. No fake header-date replacement,
  legacy digest rewrite or fabricated selected-event capsule.
- First Google acceptance uses exact frozen Q01 positive100clicks/10selected/$100
  and Q02 explicit0 versus absent under September/New_York plus August comparison.
  TikTok requires its own explicit selected-event raw evidence; generic counts
  remain separate. Missing support stays visible until those paths actually pass.

This work can be investigated separately while Q16 acceptance runs, but its code
must not enter frozen W1. No recommendation thresholds, elasticities, cross-provider
ranking, spend transfers or new advertising writes are proposed.
