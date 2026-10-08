# Planning Consent 0086 Interface

Root approved on 2026-10-08 before implementation. Base is root `beb761d`
(worker/admission guards and explicit historical test partition) plus customer
package `fea1cf6`. The executable planning product cannot obtain advertising-write
permission through this record. Existing preparation/revision policy storage stays
as draft data; no ProviderExecutionConsent is inserted and the execution mandate
is never activated by planning confirmation.

Add `initial_planning_consents`, keyed by exact `(mandate_id, mandate_revision)`
with a composite foreign key to immutable `initial_budget_mandate_preparations`.
Fields: workspace_id, policy_digest, preparation_digest, actor, confirmed_at and
consent digest. No credentials, session secrets or provider response payloads.
Insertion validates the exact preparation workspace/digests and existing revision.
UPDATE is prohibited; DELETE is permitted for workspace erasure. Reconfirming the
same exact revision is idempotent and retains the original confirmer/time.
Migration0086 descends from0085 and refuses downgrade with populated planning rows.

`checked_planning_limits(db, principal, provider, workspace_id, mandate_id,
revision, runtime)` returns `ProviderMandatePolicy` strictly as limits data. It
never constructs an execution binding. It validates the current original request's
session/owner, active recorded confirmer, preparation/digests, pinned profile,
current exact draft revision, goal/revision/definition/assessment, owned active
account/connection generation, and current time inside the planning period. No
financial admission/exposure/accounting/settlement gates. A legitimate later login
may read a current plan; no requirement to reuse the confirmation login is added.
There is no fallback to legacy execution consent.

Planning budget confirmation retains current native reads/goal/profile/expiry and
before/after authority checks, then inserts only this planning record in the same
transaction. API response state becomes `confirmed`, with explicit planning-only
and no-spending-authority fields. Native-options lists planning confirmations;
preview.py amount/final-read and preview_v2_service.py amount consume this checker.
Execution review/Start bridges remain blocked, not migrated to planning authority.

Lifecycle: workspace-owned scalar export, erasable record, no financial retention
or WORK_FAMILIES classification. Exact-key/digest raw SQL and migration checks,
confirmation rollback/idempotency, stale ownership/goal/source/profile/revision,
zero execution consent/activation and actual integrated API/TLS browser evidence
are required. Older execution-backed previews fail closed in planning consumers.

Separately fix customer denial ordering with authenticated scoped route-level
Depends, before any Runtime/Store dependency. POST/PUT retain CSRF enforcement;
GET execution-option denial retains session/owner checks. Function-body guards
remain for direct invocation defense. History/read-only reconciliation unchanged.
