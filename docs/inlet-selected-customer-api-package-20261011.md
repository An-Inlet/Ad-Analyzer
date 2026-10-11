# Selected Event Customer API — 2026-10-11

Local branch `codex/inlet-selected-customer`, reused clean worktree
`/workspace/inlet-selected-storage`, base `c47e5ce`. Interface commit `fbfe751`;
resolver dependencies are original commits `5574f28`, `eaf12e9`, and corrected
identity-IO successor `bf0dc5d`, copied locally. Parent integrates dependencies in
order; the final customer implementation commit does not duplicate resolver files.

## Implemented Boundary

New default-unavailable customer reporting dependency and four Google routes expose
owned event choices, explicit confirmation, current state and explicit invalidation.
No native account/action resources, private context, token or client-authored scope
is exposed/accepted. The selection ID/digest are deliberately exposed immutable CAS
receipts, not authority. Both metric families remain explicit customer choices.

Each confirmation obtains a fresh complete owned v24 catalog, validates its opaque
option under the original session, checks exact head CAS and actual current aggregate
completion/full manifest, and commits only after source/privacy/auth/clock checks.
Same-choice replay retains the original selection only for its confirming actor.
Another owner must explicitly invalidate/reconfirm, not claim somebody else's old
confirmation time. Changes require separate idempotent invalidation, genuine aggregate
refresh at the resulting privacy revision, then explicit new confirmation.

Identity snapshot precedes request-transaction rollback. `service.open(account_id,
read=True)` refreshes external identity BEFORE opening SQL, binds a five-second fact
to the exact Session/root transaction, and uses only local lock/final checks thereafter.
No provider callback is made while these service transactions are open. Mutators
check again after flush before commit; context exit does not reauthorize or start SQL
after a successful commit. The pre-existing Principal dependency is not globally
rewritten by this package. State/invalidation require original owner auth but work
without a configured reporting runtime or paid/sync availability.

API supplies its actual request-engine session factory, including to the owned
resolver; no cross-engine runtime session substitution is used. Main customer
security middleware supplies no-store on errors and successes. Route JSON rejects
unknown fields/coerced IDs/incomplete CAS pairs. Default runtime is None: no live
factory, background continuation, provider writes or spending authority is enabled.

## Evidence And Qualification Limits

All evidence is retained in `/workspace/inlet-evidence/20261011/selected-customer/`.
Tests use HTTPS-origin FastAPI TestClient (ASGI, not a browser or live TLS socket),
real application session creation/cookies/CSRF, persisted owner membership, actual
Google authorization/connect and encrypted Vault, injected GoogleHTTPRead OAuth and
catalog MockTransport, and actual two-page aggregate import. No selection/financial
record or high-level service is seeded/overridden. Runtime dependency injection
supplies only explicit test infrastructure. Every outgoing provider fixture request
must be OAuth or Google read search; ad mutations are rejected by the fixture.

- contracts01: seven strict public DTO cases passed.
- api02: retained fixture failures from adding middleware after TestClient's first
  request. Fixture was corrected to install actual main middleware before login.
- api03: 14 actual API cases passed both databases in 28.694s, before the identity
  under-lock issue was independently found. This result alone does not qualify the
  corrected authority implementation.
- extra04: four additional owner/paused-control cases passed before that correction.
- Final corrected cohort and static results are appended below.

SQLite has explicit FK enforcement. PostgreSQL uses the existing local disposable
`customer_engine` random-schema fixture; no root schema or prior evidence database
is reset. Each pytest invocation uses a unique durable basetemp/JUnit/run.log and
`--durations=20`. No Full, hosted, remote, credential or live-provider operation.

Remaining: root's separate selected capture route/orchestration and customer UI,
real provider capability/configuration qualification and live configuration. No
claim of runtime activation, Q01/Q02 completion or purchasable release follows.

Final corrected run `final05`: **27 passed, zero skips/failures**, 30.181s:
20 actual API cases across SQLite/PostgreSQL plus seven strict DTO cases. Includes
SQL transaction begin/commit/rollback instrumentation proving original-identity
refresh runs with no active SQL transaction in the composed service/resolver flow.
Owner replay, paused controls, original session/role/source/privacy/time changes,
unchanged retry and real-refresh reconfirmation remain passing after the fix.
Whole `ruff check .` passed, whole `mypy` passed **1,301 source files**, and
`git diff --check` passed. Logs: `ruff-final06.log`, `mypy-final06.log`.

Exact final pytest shape (using the established disposable fixture environment):
`pytest -q tests/test_selected_customer_api.py tests/test_selected_customer_contracts.py
--durations=20 --basetemp=<new durable directory>/tmp
--junitxml=<new durable directory>/results.xml`; redirect to that directory's run.log.
Never reuse an evidence directory. No broad aggregate validation was invoked.
