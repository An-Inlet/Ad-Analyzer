# Configured V2 Preview To Exact Review

Design only; reviewed base `c7c54f3c887d3297ae732a087d7650f3259a909a`.
No implementation, migration reservation, runtime registration or live activation.

## Current Acceptance And Concrete Gap

Configured Google/Meta/TikTok creation and separate activation now have request-owned
runtime composition. Google/Meta existing-campaign catalog, explicit marked budget
consent and manual optimization also have configured composition. The legacy getters
returning `None` do not mean those API paths lack assembly anymore.

Planning/reporting has a pinned configuration loader, actual owned Meta native-budget
reader, fixed-window worker acquisition, operational-as-of comparison, bounded
explained feedback and immutable current/history revisions. These are implemented
operational reported comparisons; they are not universal finality or causal lift.

Three precise integration gaps prevent configured planning handoff:

1. `app/api/customer_initial_planning.py::ReviewOptimizationRuntime` still depends on
   the legacy `get_customer_optimization_runtime`; ordinary configured optimization
   uses `app/api/customer_optimization_runtime.py::get_configured_customer_optimization_runtime`.
2. `review_status` and `app/initial_planning/review_bridge.py::current_preview` accept
   only `InitialPreviewV1`. The configured reporting path produces `InitialPreviewV2`,
   whose original immutable bytes deliberately say native financial qualification is
   unavailable. `ConfiguredOptimization.runtime` also leaves `initial_planning` unset.
3. The v2 preview's planning mandate comes from 0079
   `initial_budget_mandate_preparations`. Configured optimization explicitly requires
   0080 `optimization_mandate_preparations`/`origin_kind=optimization_customer_v1`.
   Attaching a runtime or casting native observation types cannot solve this mismatch.

## Scope And Authority

First slice: Meta campaign-owned DAILY USD budget previews only, within the currently
supported configured optimization profile. No new provider, campaign type, currency,
policy numbers or financial evidence source. Hold/insufficient previews cannot hand off.

Preserve all v1/v2 preview bytes and hashes. The stored v2 remains a non-authorizing
recommendation. A NEW handoff proof records that a separately consented execution
mandate and fresh native/financial qualification support an exact reviewed action.
This proof is not qualified learning, independent reconciliation or provider finality.

Do not promote/relabel 0079 mandates or reuse their consent as 0080 consent. The customer
selects an independently prepared, explicitly consented current 0080 mandate via the
existing configured optimization page/API. The handoff checks its goal, source,
campaign owner/topology, environment, currency, exact period and total limit against
the original preview's still-current planning mandate. For this first slice require
identical overall period/currency/account set/total cap, and execution positive-change
and per-plan limits no greater than the planning mandate's reviewed limits.

`execution_mandates.revise` already reuses the overlapping `ProviderPeriodLedger` and
checks exact period/currency/account scope. Require the two bindings to use that SAME
ledger; never create a second spending allowance, reset action count/high water, or
revise the planning mandate silently. If no eligible independently consented mandate
exists, show a concrete unavailable reason and link to Existing Campaigns. No implicit
consent or automatic mandate creation. A future consolidated consent UX is separate.

## API And Request-Owned Wiring

Retain existing v1 endpoints and response bytes. Add explicit typed v2 routes beneath
`/api/customer/v1/workspaces/{wid}/initial-planning/previews/{preview_id}`:

- `GET /execution-review-options`: current original-session-owned v2 projection with
  preview digest and bounded eligible 0080 mandate choices (opaque mandate ID/revision,
  exact money/period, account/target labels). Availability means a request can be made,
  not that financial qualification has succeeded. Use actual configured optimization
  dependency and the same caller engine; no global principal or getter override.
- `POST /execution-review`: strict `InitialPreviewExecutionIntentV1` with only
  `expected_preview_digest`, `mandate_id`, `mandate_revision`. Resolve the native target
  from retained owned preview/cohort and the fresh admitted catalog on the server.
  No customer native IDs, proof, policy fields or proposed amounts.
- Return new `InitialPreviewExecutionPreparedV1` with preview/review/plan digests and
  exact execution mandate binding, `status=review_required`, `spending_authority=none`.
  Existing generic review/approval/run/reconcile UI remains the consumer.

Proposed modules/callables:

- `review_v2_contracts.py`: immutable request, response and proof schemas.
- `review_v2_bridge.py::prepare_preview_execution(runtime, principal, identity_provider,
  workspace_id, preview_id, intent) -> InitialPreviewExecutionPreparedV1`.
- `review_v2_projection.py::native_review_match(observation: NativeBudgetObservationV1,
  current: MetaCurrentState) -> NativeReviewMatchV1`: pure exact comparison, not a cast.
- `review_v2_bridge.py::guard_for(planning, principal, identity_provider)` implements
  the existing `InitialPreviewReviewGuard` signature for the v2 proof.

Bind configured planning context into request-local optimization for ALL generic
forward routes, not just the prepare route. Existing forward provenance dispatch must
select v1 vs v2 from strict retained preview/proof schema; missing or contradictory
proof never falls through to ordinary manual execution. Candidate/automatic markers
remain mutually exclusive. Default absent planning/source/profile remains unavailable.

## Native And Financial Comparison

Fresh catalog admission and actual `MetaOptimizationTransport.read_current` supply
`MetaCurrentState`; v2 `NativeBudgetObservationV1` supplies no authority. Compare:
owned scope including generation, campaign target and budget owner, complete affected
children/topology, USD exponent/timezone, daily mode and exact before amount, account/
configured/effective statuses, schedule bounds, sharing/rebalance flags and unaffected
settings digest. The native reader already derives those fields from the same actual
Meta snapshot codec (`collectors/meta_budget.py`). Observation timestamps/digests have
different schema domains and must NOT be equated wholesale.

Store both original observation digest and fresh qualified state digest plus a
versioned semantic-match digest. Use the actual qualification/exposure readers again
through the normal optimization coordinator. Descriptor, named profile, old snapshot
or preview delta never substitutes for these facts. Exact action amount comes only
from the retained preview. Recheck fresh state at the existing dispatch boundary.

## Durable Storage And Retraction

Reuse existing protected review marker/origin uniqueness:
`ProviderExecutionReview.initial_preview_provenance_required` and immutable
`initial_preview_origin_id`, unique per workspace. Reuse `InitialPreviewReviewLink`'s
owned nullable preview FK; `native_state_digest` means the newly qualified full state
for the v2 branch, while v1 retains its original interpretation/bytes unchanged.

Propose one additive table `initial_preview_execution_proofs` (migration number to
be reserved by root): PK review_id, workspace_id, strict versioned document, digest;
composite owned FK to the existing link (add owned unique key if required). The proof
contains only hashes/opaque financial bindings: preview/profile/intent/native-observation
and semantic-match digests, original planning mandate binding, separately consented
execution mandate binding, qualified state/qualification/plan digests, expiry. Do not
retain metric bodies or duplicate original-session secrets. The existing link retains
the original session digest privately. Proof rows immutable; deleting a link may erase
its proof, but the protected parent origin remains and prohibits a replacement review.

Record parent marker, link and proof atomically with the exact coordinator review;
never attach provenance to an already committed manual review. Lost-response retry
finds the protected parent origin, validates its existing link/proof/current source,
and returns the same review. Deleted/retracted proof returns conflict, never creates
another review. Expiry is the minimum of preview, calibration/observations, native
facts and session lifetimes; fresh financial checks can impose shorter availability.

Correction/privacy/source erasure and expiry follow the existing preview dependency
chain. Nullable pointer loss, missing proof, changed report/goal/profile/source,
changed either mandate, or session loss denies approval, admission, claims, dispatch,
retry and replacement-forward work, including already claimed work. The guard checks
fresh rows under workspace-first locks, never cached ORM values. Original receipts,
reservations, review/attempt records and settlement remain retained. Historical
reconciliation and settlement never require a surviving preview/proof.

Register the new hash-only table and strict serializer in lifecycle/export inventory;
never export original_session_digest. Retraction/export revision and archive-delivery
expiry semantics remain unchanged. Refuse lossy downgrade when retained proof exists;
populated SQLite/PostgreSQL roundtrips must preserve protected reviews and financial IDs.

## Transactions And Acceptance

Preparation: original session/owner snapshot in short owned session; release database
locks before native/provider I/O; reauthorize original session and current same scope
with fresh clock under workspace-first fence; validate preview and BOTH mandate
bindings, then coordinator financial qualification and atomic writer. Never commit the
caller's unrelated transaction to release locks. Final forward checks resample clock
and authorization after I/O and before financial mutation; registered factories remain
empty unless an explicit tested/qualified source is provided.

Required acceptance uses ordinary configured dependencies and actual Meta MockHTTP:

- Actual capture/calibration/v2 preview + separate 0080 prepare/consent → exact review
  → explicit approval/run/one write/readback, both databases; no runtime getter overrides,
  seeded execution records, native-type casts or fabricated qualification.
- Fail before financial review on 0079-only consent, different ledger/period/cap/scope,
  changed topology/budget, expired source/session, missing qualification/profile.
- Lost response/concurrent prepare → one protected review. Delete link/proof/preview →
  same origin retry conflicts; no new review. Existing manual endpoint cannot bypass.
- Correction, expiry, privacy, disconnect, goal change and revocation after preparation
  and after claim block the final write; unrelated workspace survives.
- Previously attempted unknown request remains held and can reconcile after erasure;
  no retry or inferred release. Old v1 bridges, bytes, exports and hashes unchanged.

After this slice, financial evidence producer implementation/qualification and
candidate/session automatic runtime composition remain separate work. Operational
reported comparison output is not silently registered as qualified directional learning.
