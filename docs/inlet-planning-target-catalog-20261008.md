# P02 Planning Target Catalog — 2026-10-08

Branch: `codex/inlet-planning-target-catalog`, base `23ef525`. Shared contract frozen in `111c55c`, tightened after root review in `166048b`; implementation follows that reviewed contract.

Implemented `POST /api/customer/v1/workspaces/{workspace_id}/planning/target-catalog` with strict past reporting window and owned account. Reuses real NativeDiagnosticService HTTP readers for Google, Meta and TikTok without financial runtime or mandate. Preserves original session/CSRF, current account/connection generation, paid entitlement, read control and expiry gates before/around/after IO. No API transaction remains open across native IO. No provider write or capability bypass was added.

Projection exposes bounded provider-specific settings, source generation/digests and original observation expiry, exact parent graph, explicit per-kind coverage and unavailable fields. Shared Google budgets remain visible. Missing names stay null; Meta/TikTok native units remain unqualified. No new deadline or TTL. Keys identify an observed source only and never confer authority.

Checks actually run after final code:

- `pytest tests/test_planning_target_catalog_contracts.py tests/test_planning_target_catalog_api.py` with approved disposable PostgreSQL configuration: **79 passed in 52.22s**, no skips. Seven contract cases plus 36 API cases per SQLite/PostgreSQL. Each PG fixture creates/removes its own isolated schema; no shared database reset.
- `ruff check .`: passed.
- `mypy`: passed, 992 source files.
- `git diff --check`: passed.

Actual MockHTTP collectors are exercised for all three providers. Minimal fixture creates identity, ownership and connected source records only, without execution mandates, qualifications or capability monkeypatches. Cases include original-session revocation, connection-generation change, role change, missing credentials, OAuth revocation, source observation expiry, sync control, billing denial, disabled profile and invalid periods. Every API case checks CSRF and foreign-user denial before any transport construction. Positive coverage checks actual campaign/child relationships, source identity and two Google campaigns sharing the same observed budget.

Initial exploratory test failures came from reusing the old diagnostics fixture, which created execution mandates now correctly denied by the planning artifact. It was replaced with the minimal planning fixture. A shared-budget fixture with reference count two but only one campaign correctly projected partial; final fixture includes both campaigns. These were fixture corrections, not weakened source checks.

Raw check logs: `/workspace/inlet-evidence/20261008/planning-target-catalog/`. No live-provider, hosted or production behavior verified; no deployment/merge performed. Root integration and independent review remain pending at this package boundary.

Remaining P02 usability work: Google adgroups are explicitly unavailable/not collected; Meta coverage is limited to known effective statuses; TikTok coverage is limited to regular campaign families. Native names and provider-identifiable references are required before customers can locate targets for manual application. No customer UI, comprehensive scenarios, manual implementation briefs or completed-plan claim is included in this package. Next package should complete the catalog usability fields/Google child collection under the same read-only boundary, then connect reviewed planning consumers.
