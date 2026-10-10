# Plan Review Authority10: Current Locks/Roles And Retired Owner Approval

Proposal only from `9b5b0a0`; no implementation or new tests. Scope is the ten
remaining original failures in `tests/test_plan_review_authority.py`: two actual
PostgreSQL workspace-lock races and eight SQLite/PostgreSQL role cases. The18
already explicitly retained simulation ceiling cases and their shared original
fixture remain unchanged.

## Concrete Current Semantics

All ten original traces fail during `fixture` → `seeded` → legacy simulation
approve before the intended assertions. Current `customer_mandates.approve` still
calls `mutation_access`/`lock_customer_mutation` before current `s.approve`.
The latter unconditionally raises AdvertisingWritesDisabled. Therefore:

- The **two real PostgreSQL races remain current tests**, including the actual
  workspace FOR UPDATE blocker, before_cursor_execute event, backend PID,
  pg_blocking_pids proof, post-wait session revocation or lost-owner mutation,
  expected401/403 and unchanged draft/unapproved revision assertions. No historical
  replacement of these security tests is warranted.
- Current role semantics remain: default mutation guard permits owner/admin;
  HTTP draft edit permits owner/admin/analyst; pause permits owner/admin.
  Nonowner approval still denies403. Only owner approval changes from original200
  to exact409 advertising_writes_disabled_in_planning_mvp.
- Preserve the original eight-param role function as a name-only renamed local
  callable. Run only its **two owner invocations** historically because those are
  the genuinely retired success expectation. Add a current eight-param role
  function retaining all existing default-guard/edit/pause assertions and exact
  nonowner403 assertions, plus precise owner409 and no-approval-effects checks.
  Do not archive all eight just because the function includes one retired branch.

## Reuse Original Source Without Identity Rewrite

Use unchanged `retained_financial_source(...,"source_only")` and its existing
financial_source_engine adapter. It runs untouched original
`test_provider_execution_mandates.setup`, which calls the exact same seeded source
as the original fixture plus pure provider policy construction. No provider
mandate, consent, ledger, review, attempt, receipt or hold is produced. No new
child mode, source profile, arbitrary callback or setup fallback is needed.

A small current test fixture owns a fresh temporary directory and, for SQLite,
an exclusive regular nonsymlink `financial.sqlite` under it. Validate absolute
paths/all ancestors and absence before touching; the existing adapter creates
current metadata on that file. PostgreSQL uses only the existing owned UUID
inlet_test schema, unchanged source helper URL/schema/freshness guards. Rebind
current replica applications to the yielded engine; close both clients in finally
before source/file-engine teardown. Current schema fingerprints remain equal.

Load the exact SourceIds actor and simulation mandate in current SQL. Run current
`current_policy` validation before any intentional role changes, but use current
`simulation.policy` (MandateDefinition) for the edit—not the separate provider
policy. Run the same current simulation.edit as the old fixture, at JourneyClock,
then commit. This creates a legitimate next draft revision; no contradictory
approved-and-draft row is manufactured. Read the real owned confirmed-goal ceiling
as the old fixture did.

The source actor's actual issuer is `mock`, subject equals actor ID. Do **not**
rewrite it to the old test's `review-owner` identity. Configure the private
FakeProvider instance to the persisted issuer and exact existing email, then
perform the real session endpoint login using `<actor_id>:current-review`. Require
returned actor ID equality, a newly persisted session digest matching the actual
cookie, correct owner and unchanged stored issuer/subject/email. This follows the
already qualified social_api_replicas pattern. Only provider test inputs change;
no session or identity row is fabricated or overwritten. API policy clock remains
the original JourneyClock; authentication retains its ordinary current clock.

The old fixture function remains byte/AST unchanged for the18 retained ceiling
cases and original historical role callable. Only the two current consumer paths
use the new source fixture.

## Exact Source And Intentional Mutation Boundaries

Capture current physical schema and complete provider graph plus simulation
mandate/revision/action/audit rows after genuine original source. Preserve every
preexisting row exactly except the specific current simulation edit's mandate
revision/state/paused fields. Require one appended revision with same policy,
actor, original JourneyClock timestamp and null approval, and one exact
`revised_simulation` audit (generated ID shape, actual model fields). No deletion
or change to earlier approved revisions/source campaigns is permitted. Compare
current SQL rows, not cached ORM objects.

For current role cases, separately baseline before each HTTP action:

- Successful edit: one revision increment and exactly one same-policy unapproved
  revision plus revised audit; state draft/paused true; all other financial fields
  and preexisting rows exact. Viewer403 changes none.
- Approval: every role changes **no financial/simulation rows**; owner409 exact
  planning reason, others403 exact role boundary. No approve audit or stamp.
- Pause: owner/admin permit only paused=true and one exact paused audit; all
  counters, revisions, definitions and approval stamps remain unchanged.
  Analyst/viewer403 changes none. No provider execution graph change in any case.

For the two PG races, after initial current draft edit and actual login the only
adversarial writes are the original current session revoked_at or membership.role
mutation in the blocking transaction. The pending current approval must return the
original401/403 and leave the simulation/provider graph exact. Retain the actual
lock/PID assertions unchanged. These prove post-wait authorization, not merely a
planning guard rejection. SQLite's existing two row-lock skips remain explicit.

Fixture input selection is closed to these two current functions and their known
role/change cases. No scope broadening to other lifecycle or execution tests.
No source capture, provider transport or financial coordinator is patched.

## Historical And Qualification Scope

After reviewed financial-period4 integration, historical baseline is10/368. Add
only these two exact untouched original nodes as one new batch (11/370):

- `tests/test_plan_review_authority.py::test_existing_role_permissions_and_guard_default[sqlite-owner]`
- `tests/test_plan_review_authority.py::test_existing_role_permissions_and_guard_default[postgres-owner]`

Validate entire original role function AST after name normalization, including
all four role decorators and assertions; selecting only owner nodes changes no
original bytes. Map those two to current owner cases. The six other original role
identities have direct current-equivalent behavior and stay represented in the
successor coverage ledger, not an unnecessary historical rerun. Exact actual PG
race nodes retain their original names and assertions.

Gate first on the two actual PG races and current owner SQLite/PG probes. Stop
and preserve any unexpected source, lock or exact-row delta. Then qualify current
roles8 + races2 (and2 existing SQLite skips), unchanged86 default write boundaries,
exact map/AST and directly reused source guards. Execute only the new historical2;
do not rerun prior368. Whole Ruff/bare mypy/diff, explicit unique basetemps and
durable source IDs/media/provenance/raw failure copies required. No aggregate or
live calls. Production guards/routes/identity/schema remain untouched.
