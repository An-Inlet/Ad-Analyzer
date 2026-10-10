# Financial Budget Period API4: Current Goal Flow And Retired Route Ordering

Proposal only from `971d0fc`. No implementation or tests run. Scope is the four
SQLite/PostgreSQL × Havana/Apia invocations of
`tests/test_financial_budget_period_api.py::test_invalid_budget_midnight_returns409_without_authority`.

## Actual Failure And Semantic Split

All four original W1 traces stop in `configured` → original Google setup →
`test_mandates.seed` → guarded legacy approve, before the HTTP goal flow. Their
trace is not evidence the financial converter or current goal API is broken.

The source file is byte-identical to literal2155 (SHA256
`78135d5d77c58e87215b65fb6e1ad68b7af651dac1ca90d6327bff919546879e`).
Its body really does GET/edit/preview/confirm a goal, then expects the retired
budget-mandate route to reach `financial_budget_period_unavailable` before provider
IO. Current `customer_optimization.prepare_customer_budget` has the authenticated
`deny_advertising_mutation` dependency and an entry guard before binding a runtime.
Its current exact outcome is `409 advertising_writes_disabled_in_planning_mvp`.
Changing that assertion to an unspecified409 would lose the original converter
obligation. Enabling the current route just for this test would misrepresent the
planning-only artifact.

Preserve both meanings explicitly:

1. Keep the complete original function/decorators/body locally with a renamed,
   non-collected preserved callable, and run its exact four original node IDs in
   a new bounded literal2155 historical batch. No original assertion or asset edit.
2. Add four substantive current cases with the same zone/date parameters. Run
   actual current goal GET/edit/preview/confirm, assert the exact current route
   guard, and separately feed the **actual persisted confirmed definition** into
   the unchanged current financial converter and its optimization wrapper. Both
   must reject with the original exact financial-period reason, with no authority
   rows or provider IO. This is current pure converter qualification, not a claim
   that the blocked HTTP route reached it.

## Reuse Existing Source, No New Producer

Use unchanged `retained_configured_draft_fixture(...,"google_ads")`, which invokes
untouched original `configured_customer` before any provider financial mandate or
execution. Its exact actor/account/approved-draft scalar DTO and source lifetime
are already qualified. Rebind replica apps to the yielded current engine, including
file-backed SQLite. Use unchanged `configured_google_read_fixture.configured_customer`
for ordinary current login (`configured-google:current-read`), require the returned
actor equals the retained actor, and retain its actual MockHTTP request/counter
proof. No current issuer/subject/session rewrite and no capability patch.

Load exactly the owned current Goal and AdvertisingAccount as original
`configured_optimization_fixture.configured` does. Its initial current
`goals.revise`/preview/confirm sequence setting budget_start=NOW.date() can be
reused verbatim in the new current fixture, using the genuine freshly logged-in
actor. This preserves the original baseline/query rather than synthesizing a
confirmed revision. Then retain the original HTTP goal flow and fixed
`customer_goals.datetime` test seam unchanged. The explicit commerce-store zone
edit remains exactly the existing fixture basis; no financial converter override.

Do **not** use `retained_configured_candidate`: it already contains a provider
mandate/consent/ledger and would violate these tests' original zero-authority
assertions. Likewise `configured_current_optimization` expects those source
commitments and is unnecessary here. No extension of either helper is proposed.
The configured-draft read fixture already provides the closer original source.

## Current Assertions And Dependency Boundary

Register the actual current goals and optimization routers. Keep real ownership,
CSRF, identity/session and request parsing. An explicit dependency sentinel on
`get_configured_customer_optimization_runtime` records any construction and raises;
it must never be entered because the real authenticated route guard runs first.
This does not override the guard, financial converter, goal service or response.
Keep read-fixture native request list and actual server POST/activation counters
zero; no fake financial evidence registration or optimization coordinator needed.

Preserve each original goal HTTP200 assertion and request payload, including
confirmed revision, selected account and option ID. After confirmation, read the
actual current goal revision/definition in a fresh Session and verify ownership,
revision, confirmed status and exact supplied budget dates and zone. Call both
`app.publication.budget_period.financial_budget_period` and
`app.production_runtime.optimization_assembly.period` with that typed definition:
each raises HTTPException409 with `financial_budget_period_unavailable`. Havana
is an ambiguous local midnight; Apia is a missing civil date. Do not choose a fold,
normalize the gap, or substitute hand-built pure inputs for persisted HTTP output.

The actual POST keeps the original intent payload but expects only the exact
current planning-write reason. Require sentinel count0, native request count0,
server writes0, and all original four financial tables empty:
ProviderExecutionMandate, ProviderExecutionRevision, ProviderPeriodLedger,
OptimizationMandatePreparationRow. Snapshot the provider/financial graph before
and after the attempted POST/converter reads to show no hidden effects. Goal
revision/preview/confirmation changes occur before that baseline and are legitimate.
Keep the unchanged configured-draft helper's final zero-effect guards.

## Historical Mapping And Bounded Qualification

The four exact historical nodes are:

- `tests/test_financial_budget_period_api.py::test_invalid_budget_midnight_returns409_without_authority[sqlite-America/Havana-start0-end0]`
- `tests/test_financial_budget_period_api.py::test_invalid_budget_midnight_returns409_without_authority[sqlite-Pacific/Apia-start1-end1]`
- `tests/test_financial_budget_period_api.py::test_invalid_budget_midnight_returns409_without_authority[postgres-America/Havana-start0-end0]`
- `tests/test_financial_budget_period_api.py::test_invalid_budget_midnight_returns409_without_authority[postgres-Pacific/Apia-start1-end1]`

At proposal base the harness has9 batches/364 nodes. Only add a separately named
four-node budget-period batch, becoming10/368 after exact mapping/AST verification.
Run only that new historical batch, not the existing364. Each mapping points to
the new current counterpart as well as the unchanged original callable; preserve
original function AST after normalizing its name only. No skips or xfails added.

Probe one current SQLite case and one PG case before all four, stopping on actual
source/goal-flow mismatches. Final bounded cohort: current4, existing unchanged
financial converter module7, default planning execution/transport boundaries86,
plus only directly reused source guards as appropriate; qualify the historical4
separately. Use unique explicit basetemps, durable copied IDs/media/source proofs,
raw logs/XML, whole Ruff/bare mypy/diff. No aggregate, live provider, production
change, blanket retained marker or broader execution activation is authorized.
