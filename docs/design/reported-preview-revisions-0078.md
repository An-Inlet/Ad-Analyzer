# 0078 Reported Preview Revision Interfaces — Approved Contract

Base9396839; isolated `/workspace/inlet-feedback-revisions`, branch
`codex/inlet-feedback-revisions`. Approved for implementation. Migration
`20261007_0078` down`20261006_0077`.

## Persisted Model Delta

Keep `ReportedFeedbackSlot` / `reported_feedback_slots` as immutable revision rows.
Preserve every existing ID, JSON byte representation, document digest, existing
revision value and expiry. Replace `uq_rf_original_contribution` with unique
(workspace_id, environment, original_attempt_id, policy_family, cohort_digest,
revision). Retain existing owned comparison/baseline FKs and immutable triggers.
Add a composite unique key covering(id, workspace/account/campaign, environment,
original_attempt_id, policy_family, cohort_digest, opportunity_digest, revision)
for pointer ownership enforcement. No second result domain or duplicate document.

Add `ReportedFeedbackCurrent` / `reported_feedback_current` with:
- id:String32; workspace/account/campaign IDs; environment;
- original_attempt_id:String32, policy_family:String32, cohort_digest:String64,
  opportunity_digest:String64;
- slot_id:String32, revision:positiveInteger.

Unique current group is existing(workspace,environment,original,policyfamily,cohort).
Exact composite FK(slot_id plus all owner/group fields and revision) references the
slot unique key, ON DELETE CASCADE. Cross-account/environment/opportunity pointer
substitution fails in the database. Immutable pointer identity/group fields;
application updates only(slot_id,revision), under workspace-first authority lock.
DB trigger rejects backwards/same-number pointer changes; a valid advance is +1.
No clock-based ordering. A missing pointer never selects max(oldrevision).

## Existing Service/API Semantics

No new public request/response fields. `apply_feedback_preview` retains the exact
IDs-only intent and immutable `ReportedFeedbackPreviewV1` response. `read_feedback_preview`
is **current-only**: it requires an exact pointer→owned row match, current original
session, runtime policy, source, comparison, baseline and final fresh checks.
Superseded ID receives controlled409; other-owner/session still404. Existing v1
documents do not gain an is_current field or changed hash.

Internal local helpers (concrete consumer is apply/read/export):
- `current_slot(db, group) -> ReportedFeedbackSlot|None`: exact composite join,
  reject corrupt pointer; if pointer missing but retained group rows exist,
  reject unavailable, never revive them.
- `require_current_slot(db, row) -> None`: exact pointer ownership/revision check.
- `validate_preview_dependencies` remains the existing strict as-of dependency
  validator for immutable exports; current-only public reads additionally require
  pointer. Historical numeric values still need all original dependencies alive,
  original authority/freshness and original policy commitment. No historical API
  is introduced in this package.

Apply sequence under existing workspace/session fence: validate inputs and compute
active set; load exact current pointer; full current validation and same-input
replay returns same ID/expiry with no mutation; otherwise bound retained revisions
at128 per group (expired unswept included), insert immutable next revision, flush,
advance pointer, final original session/source/baseline/dependency recheck, caller
commits. A new group requires no retained prior rows. Any exception rolls back
both insert and pointer. Numeric/profile defaults remain unavailable. No adjusted
result is an initial baseline or reviewed/executable authority.

## Privacy, Exports, Retention

Appending a retained revision does not delete evidence or advance source privacy
revision. Existing `numeric_dependency_stamp` already hashes all slot IDs/digests:
append changes stamp and rejects an older prepared export without modifying source
completions. Add current-pointer identity/revision/slot commitments to this stamp,
so deletion or substitution cannot leave an archive with a stale current pointer.
Explicit strict export serializer for current table scalars, no session digest.
Slot exports remain immutable as-of documents; pointer exports identify snapshot
currentness, never pretend exported history is a live current recommendation.

All existing true erasure triggers/cascades remain: correction/privacy/comparison
loss erases all potentially dependent slots, pointer cascades, prepared exports
revoke, source privacy fences remain untouched. Deleting a current revision deletes
its pointer; retained older revisions cannot become current. Deleting a superseded
revision leaves current pointer intact but still invokes genuine export erasure
fence. This may conservatively stale current reporting after explicit erasure;
no promise to preserve derived usability through privacy deletion.

Retention removes expired rows as before; pointer cascades if its current row
expires. No fallback. Explicit erase/session/source/receipt hooks and financial
history retain their previous behavior. New table receives canonical registry,
lifecycle classification and owner-export fields; financial tables untouched.

## Migration And Acceptance

0078 upgrades existing rows in place, removes old uniqueness, creates exact pointer
for each existing row preserving its actualrevision (not forced1), no document
rewrite. Downgrade refuses when more than one revision exists in a group or any
retained history/current-pointer situation cannot be represented losslessly by0077.
Historical fixtures at0077 assert newtable absence; no production missing-table
fallback. Both SQLite batch-rebuild FK preservation and PostgreSQL exactconstraints
need populated roundtrip tests.

Tests: genuine acquisition/calibration/nativebaseline then changedpolicy/changed
baseline→append; oldbytes/IDs preserved; currentread works; oldpublicread409;
exactreplay sameID; two concurrent identical requests oneappend; distinct concurrent
inputs serialize; expiry/role/session/source afterblocking denies atomicwrites;
128bound and crossscopeFK; deletedcurrent nofallback; correction/delete/closure
cascades + preparedexport revocation; original financial rows/counts unchanged;
actual HTTPS repeatedapply/session-response coverage remains.
