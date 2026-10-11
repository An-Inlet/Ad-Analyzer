# Q11 Same-Advertiser Fresh-Consent API Qualification Proposal

Read-only proposal against root `27ccf40` and
`docs/design/q11-reconnect-lifecycle-review-v1.md`. No code, test execution,
network access, retention change, schema change or default activation in this task.

## Recommended bounded gate

Add one new test module with one scenario parameterized only by the existing
SQLite/PostgreSQL `customer_engine`: genuine private V5 V1 + an accepted manual
review decision → actual fresh Google consent for the same advertiser → existing
workspace-wide semantic erasure and no resurrection. Use V5 to avoid unnecessary
owner-review computation; this is a lifecycle join, not a V6 owner feature test.
Do not run both versions or add a browser journey to this gate.

The proposed primary fixture is unchanged
`tests.creative_runtime_fixture.configured(engine, config, replicas, patch, path,
platform="google_ads", images=1) -> (f, root, body, calls, reader, store)`.
It already supplies genuine aggregate/selected API acquisitions, confirmed goal,
owned uploaded image and actual private service factory. Its initial native source
is existing test bootstrap, not a claim that the original consent was itself HTTP;
the *new consent transition under test* must traverse all actual customer routes.
No seeded PlanVersion, accepted-event row, fake ticket, direct privacy bump,
generation UPDATE, reconstructed historical capsule or clock override is allowed.

## Exact primary journey and seam

1. Actual POST `root` with `body`, then POST `/{plan_id}/generate` using
   `tests.test_creative_runtime_api.generation()`; require201/200 and strict
   PlanVersion. GET current, select an actual action/key/digest and POST decisions
   with expected_version1, expected_event_sequence0, exact document/action digests,
   decision `accepted_for_manual_application`, explicit reason, null supersession,
   and a new bounded request key. Require200/event_sequence1 and actual event plus
   `decide` receipt. This is a recorded manual decision, never reported execution.
2. GET V1/export/events and lookup the generate/decide receipts; preserve exact
   originals locally. Prepare an export Authority through existing
   `lifecycle.service.begin`, `Authority.claim`, and test `build`/`unpack` pattern
   from `test_creative_runtime_lifecycle`. Build before reconnect to capture the
   real privacy fence, verify its planning version/event entries and successful
   `Authority.check()`. Keep the archive local and close it in finally. This is
   internal prepared-export qualification, not a new public-download route claim.
3. Include `customer_google.router` on the same existing authenticated client.
   Override **only** `google_connections.contracts.get_transport` with explicit
   `GoogleHTTPRead(..., api_version="v24", transport=httpx.MockTransport(...))`
   using its actual positional constructor. Do not replace `start`, `finish`,
   `choose`, Vault, authorization or privacy functions. Keep existing encryption
   key/client configuration; never regenerate the key or relogin the principal.
4. POST `/api/customer/v1/workspaces/{wid}/google/authorize`, parse state from
   returned URL in memory; POST `/api/customer/v1/google/callback` with that new
   state and synthetic code; POST `/api/customer/v1/workspaces/{wid}/google/select`
   with same state and the **original persisted** external_account_id. Use existing
   `headers(alice)` Origin/CSRF on every mutation, original session throughout.
   Require200 at each route and callback listing the exact same nonmanager account.
5. MockHTTP permits only the actual authorization-code token exchange, accessible
   customer list and customer metadata search used by `GoogleHTTPRead.exchange`.
   Return original account currency/timezone/name, with a distinct synthetic refresh
   grant. Match exact host/path/method/query and reject unexpected calls; do not log
   grants, code, state, cookies, headers or raw HTTP response payloads. Reuse response
   shape from `test_google_http_runtime.py::test_manager_discovery_and_token_exchange`
   but use a direct advertiser (no manager traversal). No page/import/ad mutation.
   A valid grant is not simulated by calling FixtureTransport.choose directly.

## Required state assertions

Before/after snapshots are scoped by workspace with exact row values, not only
aggregate counts. Capture before new consent (not after authorize) and distinguish
expected GoogleAuthorization changes from protected records. In-memory encrypted
values may be compared through Boolean-only checks; they must not enter artifacts.

- Same GoogleCustomerConnection id/account_id/integration_id/external advertiser;
  generation increases exactly1 and workspace export_privacy_revision exactly1;
  status connected, new grant present, staged/cursor reset. No manual state edit.
- Workspace `PlanRequestRow`, `PlanEventRow`, `InputCatalogReceiptRow`,
  `PlanDependencyRow`, `PlanVersionRow`, `PlanInputRow`, `PlanRow`,
  `CatalogReceiptSelectionRow`, `CatalogReceiptRow` are empty after selection.
  Verify nonzero primary plan/version/event/generate+decide receipts beforehand.
- Also assert actual previously present range receipt, selected capture/selection,
  presence/header/fact rows are gone, using their real scoped models already
  exercised by `test_selected_runtime_lifecycle` / creative lifecycle tests.
  No fabricated empty initial presence allows a vacuous assertion.
- Current, versions/1, events and export routes for the old plan refuse404;
  request lookups for original generate/decide return404
  `planning request not found`. Old generate POST refuses404, not another version.
  Original input POST replay may fail at deleted selected-capture admission rather
  than a plan404; do not use that ambiguous status as the primary no-resurrection
  oracle. If included, pin the actual expected admission error during source review
  and require zero recreated planning rows rather than broad status acceptance.
- The already prepared Authority.check refuses409 on its privacy fence. Retained
  local artifact bytes are test evidence, not a server-supported old export.
- Replay *this now consumed selection* once through actual `/google/select`:
  same source/generation/privacy revision, graph still absent, no new exchange.
  This confirms idempotency cannot resurrect erased graph; it is NOT the fresh
  reconnect stimulus. No new import/selection/generation after erasure in this gate.

## Workspace-wide effect and unaffected control

Do not merely show deletion of two plans that both reference the reconsented
Google source. Add one same-workspace **Meta-only ungenerated draft through actual
plan POST** before consent, with distinct request key, its own real account,
selected_reporting=[], empty target/scenario constraints, same confirmed goal and
creative input with no images. Existing `_social_account` fixture bootstrap (owned
native account, no provider write) is reusable; it must not create a PlanRow itself.
Require its saved AccountRefs exclude the Google account and its head/version0.
This draft must also disappear, demonstrating workspace-wide scope without a
second costly generation. Keep V5 policy genuine and unchanged.

For another workspace, use `test_customer_goals.seed(..., slug="q11-other")` for
nonempty commerce/goal provenance and existing goal service preview/confirm with an
owned membership. Create one similarly non-Google actual HTTP draft using a local
setup section, separate account and confirmed goal. Compare exact draft/input/
receipt/goal/commerce/workspace privacy rows before/after and GET that draft200.
Do not call the entire primary configured fixture twice: it resets shared Vault
keys and its bootstrap names/session, so that is not a safe reusable composition.
No shared helper signature change is required; source-review this small local
control setup (membership/billing prerequisites) before execution. If genuine
control draft admission cannot be composed without new fixture authority, stop
and freeze the missing seam rather than seed a fake retained plan or weaken gates.

## Protected goals and financial limits: avoid vacuous claims

Snapshot all primary Goal/GoalRevision/GoalConfirmation rows and their existing
confirmed baseline/commerce monetary entries before consent, requiring nonempty
rows. They must remain byte/value-identical, as must imported raw campaign/metric
rows that are outside semantic derived erasure. The control workspace's nonempty
corresponding rows must also remain unchanged. Compare scoped rows, not foreign
workspace hashes treated as access authority.

The existing planning fixture's six `financial_counts` values are zero. Preserve
that check as **no new advertising execution/approval/reservation effect**, not
proof that outstanding protected holds or liabilities survived. The proposed
small gate can additionally snapshot any existing protected financial/audit tables
without modifying them, but must report whether each is empty. Nonempty advertising
hold/period-ledger retention needs a separately reviewed compatible retained-source
fixture if required; do not import a historical financial capsule, enable the
optimizer, insert arbitrary obligations, or expand this reconnect gate silently.
This is an explicit coverage limitation, not permission to release a hold. Existing
financial archive qualification remains separate evidence until a real joined
fixture exists. Nonempty commerce monetary records/goals are covered here.

## Minimal files, source review and execution proposal

Own only new `tests/test_planning_google_reconsent_lifecycle.py` plus a package
ledger; prefer local fixture setup/functions in that module over shared changes.
No production, migration, policy, portal, default or current source helper edits.
Frozen existing callable dependencies: creative `configured`, `generation`, actual
login headers, GoogleHTTPRead+MockTransport, lifecycle begin/Authority/build/unpack,
and existing goal/account fixture primitives. Explicit injected transport only.

Before run, review exact two collected nodes, route expectations, original-session
and mock query allowlist, nonempty control setup, source hashes and fresh evidence
paths. SQLite first then PG under explicit parent sequencing, normal clocks/all
five-second gates, stop first failure, preserve unrun list; no pass-chasing retry.
Whole Ruff/configured mypy required. Keep artifact/event snapshots and fixed route
status/detail summaries locally; no auth/private grant fields in evidence. No tests
or collection are authorized or executed by this proposal.

## Acceptance status and owner decision

A pass qualifies the *implemented privacy erasure on same-advertiser fresh consent*
joined to genuine V5/manual-decision history, scoped controls and no resurrection.
It does not qualify reconnect as a correction, produce V2, or satisfy frozen Q11's
requirement that V1 and its decision remain historical after a reconnect with new
generation. That preserved-history criterion remains unresolved pending owner
requirements/retention review. Ordinary corrections with immutable history are a
separate already existing path. No retention weakening or owner decision is needed
to test current behavior, but any later history-preserving reconsent behavior needs
its own explicit authority/privacy design decision.


## First Execution And Control Freshness Repair

Reconsent01 stopped on its first SQLite case before fresh consent: zero passes,
one failure, PostgreSQL unrun. The primary real V5 plan, accepted decision and
same-workspace Meta draft succeeded. The second-workspace goal preview refused
`baseline_unavailable` with `stale_source`: its existing seed had October 5
commerce provenance. Original exit1 and all evidence are retained in
`/workspace/inlet-evidence/20261011/q11-google-reconsent/reconsent01-failure-summary.json`
(SHA256 `9fb7fd6bc5c63a692418c1ed6938e76bc486b486005b2a03250d5c1220dcb459`).
No reconnect outcome or authority-expiry cause was observed.

The bounded fixture repair uses an actual `CommerceSyncService.page` import with
existing synthetic `FakeMeasurement` source data and current observation time
before the control preview. It must complete normally, without directly editing
last_sync, backdating clocks, extending freshness limits or changing primary
sources. Revised source and execution evidence remain separately reviewed.
