# Resumable Shopify Acquisition

This offline-tested path acquires a requested store-local date window by enumerating
all accessible orders and their agreements/sales. It preserves the existing
independent collector's normalization, including refunds on their processing date
when the original order predates the requested window. It does not filter order
creation or update dates and does not assert a transactional Shopify snapshot,
settlement, finality, causal effect, or spending authority. Completed publications
remain the existing immutable v2 format: unresolved and unqualified.

## Entry Points

`POST /api/customer/v1/workspaces/{workspace_id}/commerce/acquisitions` accepts only
`goal_id`, `expected_goal_revision`, `start`, and exclusive `end`. The original
customer owner/session, confirmed goal, current native Shopify connection,
integration, store generation/privacy state and accessible retention window are
resolved locally. Repeating the same active request in that original session
returns its existing job. A conflicting active store request requires cancellation
or completion. GET `/{job_id}` reads status; CSRF-protected POST `/{job_id}/cancel`
cancels and removes staging. No caller-supplied source facts or completeness flags
are accepted.

`python -m app.jobs.commerce_acquisition_worker` runs the dedicated bounded worker.
The existing hourly advertising scheduler cadence is unchanged. Required server
configuration is `customer_independent_acquisition_enabled`,
`independent_acquisition_profile_path`, and `independent_acquisition_environment`.
The feature defaults off. The strict, size-bounded profile contains all fields of
`AcquisitionProfile`; no customer technical knobs are introduced. A missing
profile does not create a runtime. The shipped real HTTP transport refuses
`contract_test` before constructing its transport; tests explicitly replace that
lower-level transport with MockTransport. No account or credentials were used in
acceptance tests. Production PostgreSQL is the intended database; SQLite requires
foreign keys enabled on each connection, with service and insertion guards denying
new jobs when enforcement is off.

## Transactions And Capacity

Each claim performs at most one GraphQL request. Canonical workspace/principal/
source guards precede the job lock. Private database sessions close before provider
IO, then fresh authority, lease token, checkpoint sequence and fixed deadline are
checked before saving results. Publication and terminal job state commit together;
existing publication bytes and historical v1 behavior are unchanged.

An active lease excludes the job before per-workspace selection. Each round serves
one job per workspace, then repeats within the tick's request, distinct-workspace
and monotonic time budgets. Durable last-served ordering and bounded failure
backoff prevent a failed transport factory from monopolizing a one-workspace tick.
Retries retain the original acquisition ID, first dispatch timestamp, source
identity and deadline. No retry grants advertising authority. A charged maximum
response reservation survives an uncertain/failed request; successful response
bytes are separately recorded, so crash-budget accounting is not mislabeled as
received bytes. The final publication completion time is the successful final
Shopify authority read, not a later local publication tick.

The maximum supported order count is a safety cap, not a completion promise. Slow
or large stores can reach their fixed deadline or request/byte/identity/nested-page
limits and remain unavailable. No partial window is published and no deadline is
extended. A cooperative time budget is not proof that a process terminated.

## Private Staging And Erasure

Migration 0082 adds three owned leaf tables without rebuilding existing parents:
job, checkpoint and HMAC seen-key rows. Scope and original request/profile/deadline
are immutable. Checkpoints contain bounded normalized daily totals and HMAC
identities; native IDs/cursors are encrypted through the existing Shopify Vault,
with workspace/store/job/request/phase/sequence/checkpoint digest/deadline in the
purpose binding. A mismatched order handle or phase is denied before HTTP.

Handle opening rejects the persisted deadline immediately. This is application
unreadability, not cryptographic destruction of the Vault key. Terminal operations
remove private staging; source/privacy/session/owner/goal changes have portable
invalidation triggers. The dedicated runner performs bounded local cleanup even
when acquisition is disabled (30-second idle polling); existing Shopify privacy
maintenance also invokes cleanup. Physical deletion depends on a running worker
or maintenance process and batch capacity; there is no unconditional exact
30-minute physical-erasure claim. Terminal job metadata is eligible for removal
24 hours later. Protected advertising holds and receipts are untouched.

Job export contains only selected progress metadata. Original session/identity,
request/profile JSON, lease and native handles are excluded. Checkpoint and seen
rows are explicitly omitted from archives as private acquisition staging. Aggregate
results continue through the existing strict v2 publication serializer. Downgrade
refuses nonempty acquisition tables instead of silently discarding jobs or staging.

The source documentation and capacity rationale are retained in
[the acquisition reassessment](design/shopify-independent-acquisition-reassessment-20261007.md)
and [the approved storage proposal](design/shopify-resumable-acquisition-storage.md).
This package does not register a mature feedback producer or qualify automatic
advertising decisions.
