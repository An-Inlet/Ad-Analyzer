# Owned V3 Bridge And Feedback Storage

## Implemented Read-Only Bridge

`app/outcomes/owned_v3.py` adds `assess_owned_v3`, using an owned short-lived session
factory. It acquires workspace, actual latest receipt/account, source/publication and
current confirmed goal fences, calls fresh authorization, returns detached typed
facts and **closes its own session**. Only then may the registered independent
producer run. A second owned session reacquires the fences and fresh authorization,
checks unchanged latest receipt, publication/context and policy, and performs the
pure comparison before a final authorization check. It never commits or closes a
caller-owned transaction because no caller session is accepted. Registry lookups
are local/pure; only producer calls may perform IO.

The pure bridge requires verified action effect and an authoritative delivery interval,
closed equal-length local-day windows wholly before/after that interval, identical
current owned scope/policy and qualified independent observations with equal latest
as-of/freshness. Exact Decimal totals and differences describe an association in store
sales, not causal lift or ad attribution. Zero/negative baseline yields an undefined
relative difference with a reason. No washout period is silently invented; future
policy may require an additional explicit delay, but this package makes no causal
claim or recommendation from these values.

Both producer and maturity policy registries remain None by default. Actual current
provider receipts lack authoritative timing. Existing v2 assessments/history remain
unchanged and insufficient. V3 is not persisted or exposed by an endpoint. No schema
migration or customer proof fields are added.

## Strict Document Union Before Persistence

Proposed future serializer is a Pydantic discriminated union on `schema_version`:
`OwnedAssessment` (`inlet.owned-outcome-assessment.v2`) or `OwnedV3Assessment`
(`inlet.owned-outcome-assessment.v3`). Extra fields are forbidden; both retain their
own semantic validators. Never reinterpret a v2 row as v3 or relax v2's null values.
V3 binds normalized immutable receipt/sequence, owned current context, publication,
policy/evidence/context digests for both windows, exact window semantics and warnings.
The server recomputes the outer document digest. Customer history gets a separate
least-privilege projection rather than automatically exposing the full normalized
internal receipt with native resource identifiers.

The existing single-publication `ActionOutcomeAssessment` FK is insufficient for a
future independent producer whose evidence spans several publications. Do not store
v3 there by changing only JSON. Agree a bounded multi-evidence dependency schema,
erasure and latest-receipt checks first. This package reserves no migration.

## Proposed Feedback Schema And Ports — Not Implemented Or Enabled

Three normalized structures are proposed for root review:

- **Feedback record:** workspace-scoped ID, environment, original attempt/action key,
  exact receipt ID/sequence/digest, assessment ID/digest/version, immutable decision
  policy family/version/digest, source generation/privacy epoch, created time,
  status (`eligible`, `superseded`, `retracted`), fixed reason codes and bounded
  explanation projection. Unique `(workspace, environment, assessment_digest,
  decision_policy_digest)` makes exact reevaluation idempotent. Eligibility requires
  current owned evidence and a separately registered decision policy; neither an
  operational association nor positive sales alone supplies a causal direction.
- **Contribution slot:** unique `(workspace, environment, original_attempt,
  decision_policy_family, recommendation_scope_digest)`, active feedback foreign key,
  optimistic revision and bounded policy-specific contribution. Replacing the slot
  supersedes the prior contribution atomically; retrying the same feedback changes
  nothing. Recommendation recomputation uses active contributions only, never repeated
  additive updates that compound on retry. No contribution may authorize execution,
  raise the overall mandate or bypass new campaign/creative review.
- **Evidence dependencies:** bounded rows connecting feedback to every used source,
  generation/privacy epoch, publication/completion digest, receipt sequence and
  policy version. Composite owned foreign keys and indexes support exact-source and
  exact-attempt invalidation. Maximum dependencies follows the supported producer's
  bounded evidence contract, not arbitrary customer JSON.

Suggested server-only ports: `prepare_feedback(owned_assessment, current_evidence,
registered_decision_policy)`, `apply_feedback(db, prepared, expected_slot_revision)`,
`retract_source(db, workspace, store)`, `retract_attempt(db, workspace, attempt)` and
`erase_workspace_feedback(db, workspace)`. Preparation grants no write authority.
Apply/retract callers hold the shared workspace fence; operations add no network
calls or nested commits. They recheck the latest source/privacy/receipt and decision
policy before an atomic slot update and idempotent recommendation recomputation.

Coordinate with candidate invalidation helpers `erase_workspace_candidates`,
`erase_source_candidates`, and `erase_attempt_candidates` in
`app/optimization_candidates/invalidation.py`. Current candidate erasure deletes only
candidate jobs/results, not financial history. Feedback requires additional dependency
cleanup and contribution recomputation; calling those helpers alone is not sufficient.
On privacy erasure, delete derived numeric payloads, their evidence digests and
identifying dependencies, and remove the contribution rather than retaining sensitive
assessment data inside a tombstone. Retain only permitted minimal non-derived audit
reason metadata; immutable financial reservations/settlements/provider receipts are
handled by their existing retention rules and are not deleted by feedback invalidation.

## Implemented Offline Persistence And Retraction

Migration `20261006_0064` follows `20261006_0062`. The new
`app/outcome_feedback` package persists strict v3 documents separately from v2,
with 1–33 exact owned publication dependencies, composite ownership foreign keys,
feedback records and contribution slots. Storage rechecks current receipt, source,
privacy, goal, session and installed maturity policy under the workspace fence.
Registered policies remain disabled by default. No customer endpoint or numeric
production policy is added.

`app/outcomes/feedback.py` implements required-parameter association scoring and
active-set recomputation. Replacement compares slot ID, revision and current feedback
digest; exact replay is idempotent. The service bounds active recomputation to 64
contributions and rejects excess rather than truncating. There is no aggregate cache
or repeated compounding. Association scores confer no spending or execution authority.

Deleting or changing any dependency deletes the entire numeric parent and sibling
lineage. Parent, feedback or slot retraction erases all candidate jobs/results in that
workspace, including caches anchored to another publication. Slot replacement also
invalidates those caches. Triggers advance the workspace export privacy revision so
an already-open export snapshot cannot release erased numeric data. Source/privacy/
receipt/closure invalidation composes through existing candidate helpers. Financial
receipts, reservations and settlement history remain untouched.

PostgreSQL BEFORE triggers acquire the workspace fence with `FOR UPDATE NOWAIT`.
Workspace-first service callers retain normal behavior. A raw derived-row mutation
contending with an existing workspace fence fails immediately and rolls back rather
than waiting in inverted lock order; this package adds no automatic retry. An explicit
new transaction may retry after acquiring the workspace fence. SQLite uses its existing
single-writer transaction behavior. The migration and metadata-created schemas have
the same triggers. Actual PostgreSQL contention, populated downgrade/reupgrade and
SQLite/PostgreSQL repeatable export-snapshot races are covered offline.

## Remaining Engineering And Decisions

Still missing: qualified independently complete source reconciliation, authoritative
provider delivery timing, customer v3 history projection and a separately qualified
decision policy. Current actual inputs remain insufficient and install no contribution.
Synthetic contract fixtures exercise the qualified branch without claiming live facts.
Policy values remain uninstalled; owner parameter approval cannot substitute for
missing producer code, calibration or live qualification. No numeric production
maturity default or causal decision policy is proposed.
