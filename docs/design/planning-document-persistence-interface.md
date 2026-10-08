# Planning Document Persistence And Service Interface — Review Candidate

Based on independently closed pure contracts `31a55de` and reviewed catalog V2 in
root `382895e`. Documentation only. **0087 is proposed, not reserved or implemented.**
No execution mandate, admission, ledger, executor or provider write is a dependency.

## Storage (Proposed 0087)

All new tables have nonnullable `workspace_id`, direct workspace ownership and scoped
composite foreign keys; never resolve an object by an unscoped opaque ID.

| Table | Keys and important columns | Mutation rule |
|---|---|---|
| `planning_documents` | PK `(workspace_id,id)`; `input_head`, `version_head`, `event_sequence`, `created_by`, `created_at` | Heads/sequence updated by compare-and-swap only; delete allowed |
| `planning_input_revisions` | PK `(workspace_id,plan_id,revision)` → document; `goal_id`, `goal_revision`, `confirmed_preview_id`, `definition_digest`, `canonical_json`, `digest`, actor/time | INSERT/DELETE only |
| `planning_document_versions` | PK `(workspace_id,plan_id,version)` → document; exact composite FK input revision; `parent_digest`, `digest`, canonical JSON, generator/policy versions, generated/valid-until times, privacy revision | INSERT/DELETE only |
| `planning_document_dependencies` | PK `(workspace_id,plan_id,version,evidence_key)` → version; nullable owned account/connection/store scope, typed source kind, source/document/binding digests, revision, observation/expiry, privacy revision | INSERT/DELETE only |
| `planning_document_events` | PK `(workspace_id,plan_id,sequence)` → document; unique `(workspace_id,event_id)`; exact composite FK version; action key/digest, kind, actor/time, prior event ID, canonical JSON/digest | INSERT/DELETE only |
| `planning_document_requests` | PK `(workspace_id,actor_id,operation,request_key)`; request digest, plan ID, result kind and exact revision/version/event sequence | INSERT/DELETE only; successful transaction receipt |

Canonical JSON uses the existing contract's sorted compact UTF-8 JSON serialization;
digest includes model/domain version. Store canonical text and validate parsing/digest
on every load, not a mutable ORM dict as authority. Enforce immutable rows in both
SQLite/PostgreSQL DDL plus ORM tests. Version row scalar bindings must equal JSON.
No generic status column conflates decisions, customer assertions and observations.
`version_head=0` means not generated; `input_head>=1`. Parent version must be current
head at generation commit. Dependency rows are derived by trusted server resolver,
not client input. Composite account/connection/store FKs use actual existing unique
ownership keys; migration review must confirm these rather than adding duplicate IDs.

Goal reference uses `(goal_id,workspace_id)` existing unique goal owner constraint;
revision FK references existing `(goal_id,revision)`, with workspace equality checked
under the owned parent lock. Do not invent a composite unique constraint absent from
existing goal revision schema. `confirmed_preview_id` identifies `GoalPreview`, not
`GoalConfirmation` (whose key is goal/request-key). Deletion ordering avoids cycles:
events/requests/dependencies → versions → input revisions → document.

## Trusted Service Seams

Signatures below are the proposed shared interface, not callable code yet:

```python
create_plan(db, authority, workspace_id, body: CreatePlanInput, request_key) -> PlanSummary
revise_inputs(db, authority, workspace_id, plan_id, body: EditPlanInput,
              expected_input_revision, request_key) -> PlanInputRevision
prepare_generation(db, authority, workspace_id, plan_id,
                   expected_input_revision, expected_version) -> GenerationTicket
collect_evidence(ticket, readers: PlanningEvidenceReader) -> EvidenceBundle
compose_plan(inputs: PlanInputRevision, evidence: EvidenceBundle,
             policy: PlanningCompositionPolicy) -> PlanVersion
commit_generation(db, authority, ticket, evidence, candidate,
                  request_key) -> PlanVersion
record_decision(db, authority, plan_id, expected_version, expected_event_sequence,
                body: DecisionInput, request_key) -> CustomerDecision
record_assertion(db, authority, plan_id, expected_version, expected_event_sequence,
                 body: AssertionInput, request_key) -> ManualAssertion
prepare_observation(...) -> ObservationTicket
collect_observation(ticket, readers) -> ObservationBundle
commit_observation(db, authority, ticket, bundle, request_key) -> ReadObservedStatus
read_version(db, read_authority, workspace_id, plan_id, version) -> PlanReadResult
export_version(db, read_authority, workspace_id, plan_id, version, format) -> bytes
```

`authority` is a request-bound server object holding current principal/provider, never
payload/cookie material passed to a composer. A `GenerationTicket` is private immutable
same-operation data: actor/current session identity, owned IDs, exact input/head tuple,
goal confirmation tuple, privacy revision, account/source-generation tuples, requested
reporting windows, and policy version. It grants no access and cannot be supplied by
HTTP. Reader/composer interfaces receive immutable scoped values, no Session, callbacks
that can commit, credentials, financial runtime or arbitrary URLs.

`PlanningEvidenceReader` exposes bounded `read_catalog_v2(owned_account, window)` and
server-owned commerce/reported-measurement reads. Each implementation returns full
validated native/catalog/measurement documents plus normalized dependency candidates,
not client `EvidenceRef`s. Catalog bindings compare exact provider reference, canonical
key, snapshot selection key, source generation/digest, native owner and settings link.
Empty/partial/unsupported coverage is explicit. No fake unit/owner/amount/forecast.
`PlanningCompositionPolicy` requires an explicit version; no fallback elasticity,
transfer, confidence or numeric aggressiveness defaults. Composer is pure and cannot
self-attest source availability. Final service rebuilds/compares all refs against bundle.

Public `CreatePlanInput`/`EditPlanInput` contain goal ID/expected confirmed revision,
selected owned account IDs, reporting windows and editable customer context/fixed
allocations/exclusions only. Server assigns IDs, actor/time, exact goal snapshot and
all evidence. Generation HTTP input is expected input/version plus request key; it
**never accepts a complete client PlanVersion as owned proof**. Decision/assertion input
contains exact displayed document/action digest plus bounded intent/text; server stamps
actor/time/sequence and verifies referenced prior event belongs to this plan/action.

## Authority And Transaction Boundaries

1. Route uses existing HTTPS `Principal` or `MutationPrincipal` (Origin/CSRF). Mutations
   and read refresh are owner-only. List/read/export use current roles owner/admin/
   analyst/viewer already accepted by `customer_goals.access`; no original creator or
   original-login requirement. Set no-store. Existing paid entitlement gates apply to
   generation and provider read refresh via `billing.entitlements.paid_work`.
2. Planning-specific adapter refreshes `IdentityProvider.check_active` outside row locks,
   then inside each short transaction uses `guard_customer_mutation(...allowed_roles)`
   for fresh workspace/user/session/membership checks. It also compares current issuer,
   subject and authentication tuple to the identity just checked. No authorization cache.
   **Review point:** existing `lock_customer_mutation` performs identity-provider IO after
   acquiring locks; this proposal splits that sequence locally, not globally. A stale
   external result is never reused across evidence IO. Final provider check occurs again
   before the commit transaction, with expiry checked after waiting for locks.
3. Prepare locks canonical workspace→user/session/membership→plan→goal→owned source
   order, verifies active workspace, entitlement, expected heads and exact current goal:
   `goals.owned/current/expect`, `goal.confirmed_preview_id`, preview goal/revision,
   revision.confirmed_at, and `goals.assessment(...) == 'confirmed'`. Capture source
   generation and `workspace_export_revision`. Commit/release read transaction before
   native/identity/model IO. No pending durable generation job or worker is introduced.
4. Collect native reads and pure compose outside transaction. Do not carry SQLAlchemy
   objects or authority caches across this boundary. Failed reads yield explicit bounded
   unavailable sections only where the generator can produce honest useful output;
   authentication/source-integrity failures fail the operation, not downgrade to a guess.
5. Final fresh identity check, then new locked transaction redoes current owner/session,
   entitlement, goal confirmation/assessment, input/version heads, privacy/source bindings,
   owned accounts/integrations and fresh wallclock against every evidence deadline.
   Revalidate candidate and exact evidence mapping. Any drift returns409 and persists no
   version/dependency/event/receipt. CAS updates the head and inserts immutable version,
   dependencies and request receipt atomically. No refreshed input substitution mid-commit.
6. Concurrent same-key requests: scope+operation+body digest uniquely arbitrate; winner
   commits one result, loser rereads authorized receipt and returns exact result. Changed
   body under same key409. Different-key stale-head409. SQLite uses explicit transaction
   before savepoints as `goals.create` does; PostgreSQL locks/CAS/uniques tested. Failures
   roll back all product rows. No session-level auto replay after unknown HTTP response;
   client may explicitly query request receipt and choose to retry the same key.

Read/exports validate current read access and privacy revision before any bytes leave.
Historical goal/source revisions are labeled stale/superseded, not rewritten or hidden
as current. Semantically erased source-derived payloads must be deleted, not merely
marked stale. A new current owner can read legitimate history. Observation updates use
new immutable evidence and events, never mutate old plan facts; they assert state only,
not who applied it or causal success. Changed goal/input blocks acceptance of stale
recommendations; historical decisions remain readable. Retraction/correction is an event,
not overwriting customer reports.

## Lifecycle, API And Implementation Gates

Register all six tables in `lifecycle.registry.TABLES` as workspace-owned, **unprotected**,
with explicit safe fields; canonical JSON is explicit in `export_serializers.JSON_FIELDS`
and bounded serializer validation. Dependency rows are not jobs: no WORK_FAMILIES entry.
Add scoped predicates and deletion ordering to inventory/archive paths. Add planning
payload invalidation to `bump_workspace_export_revision`'s semantic erasure path;
ordinary source corrections use a revision fence and stale read projection, preserving
honest historical-as-observed data. All export/download checks recheck privacy before
return; no old cached artifact survives erasure. Proposed downgrade refuses populated
new tables. Model/migration registry, raw immutable DDL, export and scoped-delete tests
must pass both databases; do not equate scoped deletion with full erasure-workflow proof.

API family after review: `/planning/plans` create/list; `/{id}/inputs`, `/generate`,
`/versions/{version}`, `/decisions`, `/assertions`, `/observations/refresh`, `/export` and
request-result lookup. No activation/publication/apply endpoint. Export formats initial
JSON plus rendered text/HTML without raw active HTML from evidence. Service API/adapter
and generator contracts must freeze before parallel consumers begin.

Acceptance before persistence freeze: both-DB same/different-key races, CAS rollback,
foreign workspace/account/source, revoked session/member, changed goal confirmation,
source/privacy revision during IO, expiry while waiting for locks, exact typed evidence
binding, repeated read/exports after correction/erasure, immutable history and event
chain scopes. Browser/generation quality follows root's fixed synthetic cases; structural
schema/DB success is not quality, expert, pilot or production qualification.
