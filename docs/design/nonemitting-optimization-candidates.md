# Nonemitting Optimization Candidates

This package adds server-owned read work and bounded budget suggestions. It does
not add autonomous advertising authority, spending reservations, provider writes,
customer approvals, a scheduled production job, or a live runtime factory.
`get_candidate_runtime()` returns `None`. Numeric policy inputs default to unset.
The existing customer exact-review workflow remains separate.

## Trusted Interfaces

`CandidateWork` binds the exact owned account/generation, consented mandate,
confirmed goal, target and complete native budget-owner target set, plus a current
commerce publication/source/privacy revision. Optional original-attempt lineage
binds the latest normalized receipt ID, sequence and digests. Work and policy are
server inputs, never an endpoint accepting browser-supplied qualification.

`CandidateRuntime.reader(db, scope, now)` reads a typed `CandidateObservation`;
`policy_reader` resolves the current server policy. The default learning profile
registry is empty. Current owned v2/v3 assessment and reconciliation-observation
schemas cannot be registered as measured learning: association or operational
maturity is not an attributed directional recommendation. Controlled contract
scenarios are accepted only in the explicit `contract_test` environment.

`enqueue(db, principal, work, runtime)` requires a current owner, original real
customer session, paid/current mandate and account ownership. The worker reloads
that same session and all source/policy fences before and after source I/O.
Logging out therefore stops this read job from saving suggestions. A future
logout-independent worker needs a separate explicit delegation; no old human
approval is silently converted into worker authority.

`run_candidate_reads(engine, factory, limit=10)` selects one due read per workspace
in bounded batches, isolates failures and uses capped exponential backoff. Lease
reclamation applies only to this non-emitting read queue. It never reclaims an
advertising attempt, substitutes a provider fence or retries a mutation.

`compile_candidate` requires explicit numeric settings and qualified evidence,
checks the exact currency/period/mandate, preserves the total spending limit, and
bounds increases by approved aggressiveness and remaining cumulative positive
change allowance. It generates an existing typed budget suggestion only. It does
not infer exposure from daily budgets or claim that a suggested operation is
ready to execute. Every output says `spending_authority=none`,
`dispatch_ready=false`, and `requires_new_execution_admission=true`.

## Erasure And Ownership

Migration `20261006_0062` follows `0060` and creates only
`optimization_candidate_jobs` and `optimization_candidate_results`. Composite
workspace foreign keys bind publications, optional original attempts, jobs and
results. Results are inserted once; changing sources deletes derived work.
Downgrade removes these disposable derived suggestions, preserving all provider
receipts, mandates, ledgers, reservations and replacement audits.

The separate invalidation module exposes:

- `erase_workspace_candidates(db, workspace_id)`
- `erase_source_candidates(db, workspace_id, store_id)`
- `erase_attempt_candidates(db, workspace_id, attempt_id)`

Callers already hold the workspace lock. Helpers acquire no new locks, commit
nothing and never erase financial history. Transactional hooks run on workspace
privacy revision, commerce correction and publication replacement, closure, and
new creation/activation/optimization receipt append. Repeated identical receipts
do not erase work. Publication deletion also cascades. Fresh reads reject changed
ownership, generation, policy, receipt or expired evidence. Strict customer export
includes typed owned documents; session digests and lease/fence details are
excluded. The model and local-work registries explicitly classify both tables.

Historical migration fixtures intentionally use current complex producer helpers
against pre-0062 schemas. A test-only adapter first asserts candidate tables are
absent, then replaces only the three newly introduced candidate-erasure hooks.
It does not bypass runtime checks or old financial/source behavior. Current-head
and populated0062 tests exercise the real hooks without this adapter. There is
no production missing-table fallback.

## Remaining Engineering And Decisions

A genuine attributed mature-learning producer and configured numerical decision
policy remain missing. Native exposure, terminal original-attempt closure and
transition proofs remain unavailable; diagnostics and current target status do
not qualify them. Production provider qualification plumbing, automatic target
selection, emitting scheduler assembly and worker delegation are still missing
code. This queue does not close those acceptance criteria.

Recommended future delegation contract: fresh owner-session consent to an
explicit `automated_existing_campaign` grant, exact mandate version/account and
target set, allowed budget/pause actions, currency, expiry and revocation rules.
Revocation, workspace closure, owner-role loss, mandate revocation or source
change must block worker admission. Creation and creative remain exact customer
review only. Active logout-independent semantics require the owner's explicit
choice before enabling such grants; this package implements no grant.
