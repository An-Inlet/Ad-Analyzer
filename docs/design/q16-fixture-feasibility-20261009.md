# Q16 Fixture Clock Feasibility And Proposed Shared Contract

Successor of `55bc389`, isolated branch `codex/inlet-q16-fixture-feasibility`.
Root-approved bounded investigation; W1 `6a3b0f1` source, validation checkout and
aggregate database were not touched. This is **not** exact Q16, browser or human
quality acceptance. No production file changes.

## Observed Boundary And Feasible Approach

An actual October login remains valid according to current wall time, but its
ordinary session expires before November3. With only planning's `utc_now` set to
November3, actual create returns401 at `catalog_receipts._fresh`: session expiry
is compared to `max(app clock, database clock)`. Current goal progress also compares
session expiry to its effective measurement clock. A confirmed November goal alone
cannot make that October session authorize November reads. Both denials are correct.

The approved test-only issuance seam works: replace **only the module reference**
`app.api.customer.time` during the actual login request with an object exposing
`time() -> int(stage.timestamp())`. Do not replace global `time.time`, any access/
authority guard, monotonic clock, DB clock or session row. Restore the module binding
immediately after login. A fixture provider validates coherent synthetic issuer,
audience, subject, verified email, auth_time/iat/exp using production
`verified_identity(..., now=stage)`. Its current suspension/revocation checks remain.
This is synthetic identity issuance, not live identity-provider qualification.

The unmodified login route sets `created_at=stage`, `expires_at=stage+TTL_SECONDS`,
rotates the presented old session and writes its actual exchange receipt. On each
later stage, first prove the previous session is rejected by the effective-clock
consumer, then perform a fresh ordinary login. No TTL extension or grandfathered
session is permitted. Real wall/monotonic guards remain active throughout. Fixed
future dates cease to be a valid future-clock probe once real time reaches Nov3;
the probe explicitly asserts this precondition rather than silently changing dates.
It is intentionally **not default-collected**: the filename does not match the
repository's `test_*.py` convention. Invoke it explicitly for this dated experiment;
no skip/xfail or permanent default-suite date timebomb is introduced. A future exact
fixed-date Q16 lane needs the same explicit invocation unless a separately reviewed
coherent clock isolation makes it durable.

## Actual Minimal Workflow Evidence

`tests/q16_clock_feasibility_probe.py` ran on isolated SQLite/PostgreSQL fixtures:
**2 passed in 9.29s**, no skips (`issuance.log/xml`). It proves:

1. Real initial login and actual source fixture; actual CommerceSync reimport
   produces the $8,000 September baseline. The goals service revises/previews/confirms
   a $12,000 November target with $1,000 November budget. Confirmation is in October
   at a supported explicit service time one configured sync interval after setup.
2. Real checkout plus signed webhook reconciliation at Nov3 enables the paid gate;
   actual CommerceSync refresh at Nov3 preserves the September baseline. Original
   real-October session receives401 and leaves zero PlanRows, despite `/session`
   succeeding on real wall time. Current goal-progress service also returns401.
3. Narrow synthetic Nov3 issuance via actual login; asserted normal TTL and no
   original-session timestamp edits. Actual default-V3 customer create/generate
   succeeds, and saved-version progress returns exact string `"0"`.
4. Actual Nov4 CommerceSync adds a $25 November3 agreement. Fresh signed billing
   reconciliation succeeds; no second checkout is attempted. Before re-login,
   progress returns401. Fresh ordinary-TTL Nov4 login permits progress `"25000000"`,
   one additional closed day, the same V1 document digest and unchanged October
   goal revision/confirmation. Zero provider execution attempts are present.

This minimal probe deliberately reuses the existing **UTC** store/account/report
fixture and its current reporting dates. It does not qualify New_York, exact
September/August inputs, product-image provenance, refunds, privacy/export/browser
or no-additional-native-read assertions. It does not manufacture a PlanVersion or
qualified selected-event graph. Goal/billing **service** calls accept explicit
`now`; their HTTP handlers still call wall `datetime.now` directly. Their full
frozen-date HTTP journey is not claimed by this proof.

Artifacts: `/workspace/inlet-evidence/20261009/q16-feasibility/`.
Initial positive expectation failed correctly at401 (`probe.log/xml`); diagnostic
attempt1 had an incorrect test import (`diagnosis.log`), then diagnostic2 captured
the exact receipt freshness denial (`diagnosis2.log`). An intermediate negative
probe reached a second-checkout409 (`final.log/xml`); the final fixture correctly
uses only reconciliation for the existing subscription. These are development
observations, not aggregate results or product regressions. No failure was hidden
with a skip, expiry edit or guard change.

## Shared Fixture Contract Proposed For Root Review

No dependent browser implementation begins until this contract is reviewed.
Proposed test-only module `tests/q16_fixture.py`:

```python
@dataclass(frozen=True)
class Q16Ids:
    workspace_id: int
    goal_id: str
    goal_revision: int
    confirmation_id: str
    store_id: str
    account_id: int
    plan_id: str
    version: int
    document_digest: str
    create_request_key: str
    generate_request_key: str

# These operations use actual routes/services and assert their results.
def issue_customer_at(client, provider, *, subject: str, at: datetime) -> None: ...
def prepare_q16_case(engine, clients, *, branch: Literal["privacy", "progress"]) -> Q16Ids: ...
def import_progress_stage(engine, ids: Q16Ids,
    *, stage: Literal["later_day", "refund_correction"]) -> None: ...
```

Only IDs and expected response bytes cross preparation to browser/controller code;
no live ORM/session objects, cached authority facts or positive evidence bundle.
Test HTTP/native/commerce/provider adapters remain private to the fixture context,
with strict deterministic response queues and no network fallback.

| Boundary | Required clock/input contract |
|---|---|
| October goal confirmation | Build a **fresh** store from actual synthetic Shopify metadata declaring USD/New_York, perform first real $8,000 baseline import, then actual goal create/preview/confirm in October. This avoids rebasing the goal later. The minimal proof used core calls, not HTTP; prove HTTP setup separately. |
| Session issuance | The exact narrow login-only module clock adapter above at Nov3/Nov4; coherent fixture claims, normal TTL, real rotation and exchange receipt, restore immediately. Fresh login before subsequent authorized stages; first assert prior session expiration where meaningful. |
| Current identity/local authority | Current real provider fake suspension checks, real wall time and monotonic five-second fence. No changes to `access`, `authority`, DB time or TTL constants. No already-refreshed fact crosses operations. |
| Planning API/native catalog | Existing API `utc_now` factory seam set to stage; actual default service passes that clock to native readers. Fresh catalog observations get their unchanged configured lifetime, never inherited future timestamps or extended receipts. Exact full fixture native TTL still needs qualification. |
| Commerce imports | Supported `CommerceSyncService.page(now=stage)` with real normalized raw September/November facts and actual source publication. No direct amount, coverage or watermark edits to meet assertions. Respect sync cadence for refund stage; specify later same-day time beyond that cadence and refresh authority/billing normally. |
| Paid entitlement | Actual fixture checkout once plus signed receive/reconcile using each explicit stage. Existing subscription uses reconciliation, not repeat checkout. No paid row seeding or bypass. Full billing HTTP clock seam is not proven; supported service boundary is the proposed test setup. |
| Progress | Required-version actual customer GET; exact immutable November goal, New_York local-day prefix, canonical signed micros, unchanged plan digest. Measurement time must not be confused with native-evidence expiry or current authority. |
| Archive/privacy | Existing lifecycle/archive API/service controls and current delivery privacy recheck. No synthetic completion or manually deleted request receipt substitutes for real erasure. |

Freeze exact source facts/dates/UTC offsets from the preceding proposal without
changing the common case. In particular: Nov3 00:05 New_York is05:05Z; Nov4 is05:05Z;
September/August local reporting bounds have04:00Z offsets. A later refund stage
must explicitly name its later time and fresh login if needed; do not roll back a
clock to preserve a session or native receipt. Clock adapters are scoped to this
fixture only, never autouse or suite-wide.

Remaining before a positive exact-case fixture freeze: New_York source metadata
and first baseline import/goal HTTP setup; full frozen reporting windows/product
facts; exact private image provenance; true native expiry under synthetic stage;
refund stage and archive/privacy workflow. The existing minimal probe is reusable
clock evidence, not a replacement for these missing assertions.

## Erased IDs Versus Intentional New Input

`erase_workspace_plans` removes the complete graph including PlanRequestRow.
Therefore lookup of old successful request results, old-ID generation/revision,
history/export/progress and automatic refresh must not disclose or reconstruct
that erased graph. A controlled404/409 with no old-ID graph resurrection is the
appropriate assertion.

A subsequent explicit `CreatePlan` with a full client-retained input payload is a
**new submission**: the service allocates a fresh UUID and revalidates current
owned goal, accounts, sources and customer authority. With the old receipt erased,
reuse of its request key is not inherently a replay of deleted data. Q16 does not
establish a ban on all intentional future submissions, nor authorize tombstones
retaining deleted inputs/keys. Do not assert zero new rows for every fresh create.
If permitted current inputs yield a new plan, verify fresh identity/lineage and no
old document/event restoration. Whether to prohibit that product behavior is a
separate owner policy decision; this acceptance package proposes no such change.

## Final Explicit Invocation And Checks

After root review, the dated experiment was moved out of default collection and a
mypy-only attribute access was corrected. Explicit renamed-file run:
**2 passed in 11.40s**, no skips (`explicit.log/xml`). It repeats the same two
backend scenarios; do not add it to the earlier two passes as unique coverage.

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_oct07_next_integration_ci \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true \
/workspace/inlet-venv/bin/pytest -q -o addopts='' tests/q16_clock_feasibility_probe.py \
  --junitxml=/workspace/inlet-evidence/20261009/q16-feasibility/explicit.xml
/workspace/inlet-venv/bin/ruff check .
/workspace/inlet-venv/bin/mypy
git diff --check
```

Whole Ruff passed; bare mypy passed **1118 source files** (`ruff.log`, `mypy.log`).
An earlier mypy check rejected direct access to the imported module's non-exported
`time` attribute; final assertion uses `getattr` without changing clock behavior.
Diff check passed. No aggregate, browser, external provider or W1 database action
was performed. The proposed shared fixture remains awaiting root review; exact
Q16 positive acceptance is still outstanding.
