# Planning MVP Customer Boundary

Base: `1c7e30d` (immutable shared capability interface). Branch:
`codex/inlet-planning-customer`; worktree `/workspace/inlet-planning-customer`.
This package is offline implementation and focused verification, not deployment
or live-provider verification. No spending or provider writes were authorized.

## Route And UI Decisions

Customer creation/activation review, execution approval/admission/advance,
optimization initial/repeat review and execution spending consent, candidate
execution review, initial preview execution handoff and automatic Start deny via
`advertising_capabilities.require_advertising_write()` before retained execution
implementation. Legacy mandate action review/claim/dispatch also deny. Existing
customer authentication/CSRF dependencies and owner scope remain. Approval and
runtime injection cannot enable the product capability.

Execution and optimization capabilities are false even for injected live-enabled
runtimes. Automatic capabilities return no policies or mandates. Authenticated
history/status/receipts, local Stop/revoke and read-only retained-outcome
reconciliation remain. Reconciliation is not permission to claim, dispatch,
replace an attempt or release an outstanding obligation; root owns service-level
and sink-level enforcement independently.

Local goal/draft/simulation/plan confirmation and initial planning-limit consent
remain planning operations. They do not grant execution approval. The existing
initial budget storage uses ProviderExecutionMandate/Consent records, but its
producer and response explicitly remain non-authorizing for execution; no schema
or authority semantics were broadened here.

`/planning/accounts` now owns the bounded local account catalog with original
session `bind_authority`, owner checks, exact account/connection generation checks,
active source filtering and no-store responses. The old account route delegates
to it for compatibility. Plan Review, Account Diagnostics and TikTok discovery
use the planning path. This preserves local catalog semantics (no new paid gate
on listing locally owned names). Configured native Meta reads retain their existing
`paid_work` production/live billing gate, goal/revision/cohort, original-session,
connection ownership and before/after external-read checks. No billing gate was
removed. Initial runtime fallback no longer builds an execution runtime.

Initial planning no longer imports automatic/execution components, renders
execution controls or requests an execution-review handoff. Execution,
optimization, social-configuration and TikTok-linked pages now serve the
read-only advertising history shell. Their directly served HTML assets likewise
have no mutation controls. Existing execution JS/engine source is retained but
not loaded by those pages. History supports owner-scoped run lists and original
run URLs; it displays server data as text. History shell has syntax checks and
API coverage; it has not received a dedicated browser test in this package.

## Focused Verification

Commands use `/workspace/inlet-venv/bin/python`, with cwd the worktree. Both-DB
invocations set `AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true` and the approved existing
localhost disposable `inlet_oct07_next_integration_ci` database. Fixtures create
isolated schemas; no existing database was reset. The existing stopped
`inlet-b01-postgres` container was started with permission, without configuration
or credential changes.

- `python -m pytest tests/test_planning_customer_boundary.py tests/test_budget_mandate_api.py::test_first_customer_mandate_and_preview tests/test_initial_budget_mandate_browser.py -k sqlite --durations=5`: initial cohort **5 passed, 5 deselected, 14.75s**.
- After adding source/membership coverage and browser no-execution-request assertions,
  the same command without `-k sqlite`: **8 passed, 4 setup errors, 31.35s**.
  PostgreSQL was still starting up for the first four PG cases. Both real TLS
  browser PG cases passed after it became ready. No product test failed.
- After `docker exec inlet-b01-postgres pg_isready -U postgres` confirmed readiness:
  `python -m pytest tests/test_planning_customer_boundary.py tests/test_budget_mandate_api.py::test_first_customer_mandate_and_preview -k postgres --durations=5`:
  **4 passed, 4 deselected, 16.82s**. All 12 distinct final focused cases passed.
- Final injected-live-capability negative assertion followup:
  `python -m pytest tests/test_planning_customer_boundary.py::test_direct_route_intents_stop_before_runtime_or_financial_effects --durations=3`:
  **2 passed, 2.23s**, SQLite and PostgreSQL, actual capability guard unpatched.
- `ruff check .`: passed. `mypy`: passed, **984 source files**.
- `node --check` on advertising-history, initial-planning, plan-review,
  account-diagnostics, tiktok-discovery and the initial-budget browser driver:
  passed. `git diff --check`: passed.

Actual HTTPS Chromium uses real customer APIs/session cookies and the actual
configured native Meta reader with MockTransport. It captures reports, calibrates,
reads native budgets, prepares/confirms explicit planning limits and produces the
non-authorizing native preview. It asserts absence of execution controls and
execution/review requests, provider GET-only traffic, zero provider mutation
POSTs, zero execution attempts/holds. An unavailable budget policy is also tested.

## Remaining Work And Test Partition

P02: generalized provider-native target inventory for Google/Meta/TikTok remains
unavailable on the history page. Local account names and configured Meta native
budget reads do not complete comprehensive planning acceptance. Build a separate
owned read-only runtime with pinned read policy and retained tenant/session,
source/goal freshness and provider/environment billing checks; do not construct
CustomerOptimizationRuntime or require financial execution source registration.
Preserve the three-platform product scope and show honest unsupported states.

No historical execution test bypass was added, globally or otherwise. Old
execution API/browser tests that expect these retired production controls to work
are intentionally incompatible with this product scope. A broader partition of
historical engine tests needs explicit per-module test-only opt-in and separate
planning-artifact tests. This package does not claim a Full pass or assembled
service/sink integration acceptance. Independent review and root assembly remain.
