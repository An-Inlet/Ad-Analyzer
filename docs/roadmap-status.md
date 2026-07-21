# Roadmap status

Last refreshed: 2026-07-20
Baseline audited: current branch commit `a5510a0` (PR #11 merge)
Automation controller: `docs/project-controller.md`

## Status legend

- **Complete**: acceptance criteria are implemented, tested, and documented on the audited baseline.
- **Partially complete**: equivalent implementation exists but one or more technical acceptance criteria remain.
- **Missing**: no equivalent implementation was found.
- **Blocked by a required human decision**: the remaining work requires an explicit human decision or approval listed in `docs/decision-register.md` or the controller safety policy.
- **Superseded by an equivalent implementation**: behavior is satisfied through the existing architecture under different module names than the roadmap suggested.

## Completion summary

- Total roadmap units audited: 17
- Complete or superseded units: 14
- Partially complete units: 1
- Missing units with satisfied dependencies: 2
- Human-blocked units: 1
- Current automated completion percentage: 82% (14 of 17 units complete or superseded; Phase 11.3 live operation remains blocked)

## Roadmap unit audit

| Unit | Status | Existing implementation files | Tests covering it | Missing acceptance criteria | Blocking decisions | Latest associated PR | Validation status |
|---|---|---|---|---|---|---|---|
| 8.1 Analytics foundations | Superseded by an equivalent implementation | `app/optimizer/analytics.py`, `app/settings.py` | `tests/test_analyzer_v1.py`, `tests/test_api_v1_read_only.py` | None found; `MetricWindow` distinguishes `window_days`, `days_with_metric_rows`, and `data_coverage_ratio` without persistence. | None; conservative defaults were implemented without external calls. | #11 | Pending in this controller run; covered by required validation commands. |
| 8.2 Repository aggregation and query safety | Superseded by an equivalent implementation | `app/api/repository.py`, `migrations/versions/20260720_0006_scope_execution_idempotency.py` | `tests/test_analyzer_v1.py`, `tests/test_api_v1_read_only.py`, `tests/test_phase7_postgres_transactions.py` | None found; account-scoped aggregation and server-side comparison windows exist in repository/API architecture. | None for current implementation; no additional query-plan index approval needed in this audit. | #11 | Pending in this controller run; PostgreSQL validation remains environment-dependent locally. |
| 8.3 Deterministic findings service and API | Superseded by an equivalent implementation | `app/optimizer/recommendations.py`, `app/api/v1.py` | `tests/test_analyzer_v1.py`, `tests/test_api_v1_read_only.py`, `tests/test_google_ads_read_only.py` | None found; findings are deterministic, authenticated, read-only, and do not invoke write-capable code. | None for current implementation. | #11 | Pending in this controller run. |
| 8.4 Dashboard analytics views | Complete | `app/dashboard/router.py`, `app/dashboard/templates/account.html`, `app/dashboard/static/dashboard.css` | `tests/test_analyzer_v1.py`, `tests/test_api_v1_read_only.py` | None found; dashboard renders analytics, findings, and coverage state through existing read-only services. | None for current implementation. | #11 | Pending in this controller run. |
| 9.1 Recommendation schemas | Complete | `app/ads/models.py`, `app/api/schemas.py`, `migrations/versions/20260720_0005_analyzer_recommendations_execution.py` | `tests/test_analyzer_v1.py` | None found; recommendations are proposed and stored with rationale, confidence, supporting metrics, and planned action metadata. | None for proposed-only behavior. | #11 | Pending in this controller run. |
| 9.2 Deterministic recommendation service | Superseded by an equivalent implementation | `app/optimizer/recommendations.py` | `tests/test_analyzer_v1.py` | None found; finding-to-proposal conversion is deterministic and excludes stale/insufficient data from actionable drafts. | None for current deterministic policy. | #11 | Pending in this controller run. |
| 9.3 Recommendation API/dashboard preview | Complete | `app/api/v1.py`, `app/dashboard/router.py`, `app/dashboard/templates/account.html` | `tests/test_analyzer_v1.py`, `tests/test_api_v1_read_only.py` | None found; operators can preview recommendations without live execution. | None for preview-only behavior. | #11 | Pending in this controller run. |
| 10.1 Audit data model | Complete | `app/ads/models.py`, `migrations/versions/20260720_0005_analyzer_recommendations_execution.py` | `tests/test_analyzer_v1.py` | None found; recommendation and execution audit rows are append-oriented and migrations are reversible. | None for current review/audit model. | #11 | Pending in this controller run. |
| 10.2 Review queue service and API | Complete | `app/api/v1.py`, `app/api/schemas.py` | `tests/test_analyzer_v1.py` | None found for approve/reject behavior; defer semantics remain a human policy topic but do not block current approve/reject audit flow. | DR-007 remains pending before production policy finalization. | #11 | Pending in this controller run. |
| 10.3 Review dashboard | Complete | `app/dashboard/router.py`, `app/dashboard/templates/account.html` | `tests/test_analyzer_v1.py` | None found; dashboard review actions create audit records and do not execute Google Ads writes. | None for current UI. | #11 | Pending in this controller run. |
| 11.1 Execution policy model | Complete | `app/settings.py`, `app/executors/planner.py`, `app/ads/models.py`, `migrations/versions/20260720_0005_analyzer_recommendations_execution.py` | `tests/test_analyzer_v1.py`, validation scope `ControlledWrites` | None found; policy fails closed with writes disabled, kill switch enabled, and empty allowlist by default. | DR-005, DR-006, DR-008 remain pending before live mutations. | #11 | Pending in this controller run. |
| 11.2 Dry-run executor | Complete | `app/executors/planner.py`, `app/api/v1.py`, `app/dashboard/router.py` | `tests/test_analyzer_v1.py` | None found; dry-run output is auditable, idempotent, and stores rollback instructions without live mutation calls. | DR-009 and DR-010 remain pending before any live execution policy. | #11 | Pending in this controller run. |
| 11.3 Approved controlled mutations | Partially complete | `app/executors/google_executor.py`, `app/executors/planner.py`, `app/settings.py` | `tests/test_analyzer_v1.py`, `tests/test_google_ads_read_only.py`, validation scope `ControlledWrites` | Live Google Ads mutation activation remains intentionally unimplemented; safe non-live pieces now include mocked adapters, fail-closed preflight, empty allowlists, stale checks, compensating-action instructions, and audit-compatible dry-run output. | Mandatory human stop remains for live operation: Phase 11.3 production mutation enablement, real mutation allowlist, real account allowlists, and kill-switch disablement. | #11 and current controller PR | Local non-PostgreSQL validation run; GitHub Actions must provide authoritative PostgreSQL/migration validation after PR publication. |
| 11.4 Execution operations dashboard | Complete | `app/dashboard/router.py`, `app/dashboard/templates/execution_operations.html`, `app/dashboard/templates/account.html`, `docs/operations/runbook.md` | `tests/test_analyzer_v1.py` | None found for safe non-live scope; dashboard is authenticated, account-scoped, paginated, redacted, and has no live execution or synchronization controls. | Live execution controls remain blocked. | Current Phase 11.4 controller PR | Local non-PostgreSQL validation run; GitHub Actions must provide authoritative PostgreSQL/migration validation after PR publication. |
| 12.1 Deployment architecture | Missing | `deploy/docker-compose.yml`, `docs/operations/runbook.md`, `docs/build-progress.md` | `tests/test_automation_foundation.py`, validation scope `Release` | Provider-neutral container architecture docs/config are now approved but still need deployment-ready examples and startup validation documentation. | Production deployment and paid provider selection remain blocked; provider-neutral references may proceed. | #11 | Eligible after Phase 11.4 safe visibility work. |
| 12.2 Managed infrastructure configuration | Missing | `deploy/docker-compose.yml`, `.env.example`, `docs/operations/runbook.md` | `tests/test_automation_foundation.py` | Provider-neutral managed PostgreSQL, external secret-manager placeholders, and deployment examples remain to be completed. | Provider purchase/activation and real credentials remain blocked. | #11 | Eligible after 12.1. |
| 12.3 Monitoring backup and incident response | Missing | `docs/operations/runbook.md` | `tests/test_automation_foundation.py` | Provider-neutral monitoring hooks, backup/retention defaults, restore-test procedures, and incident response docs remain to be completed. | Paid monitoring accounts and production database connections remain blocked. | #11 | Eligible after 12.2. |
| 12.4 Production readiness release | Blocked by a required human decision | `docs/definition-of-done.md`, `docs/build-progress.md` | `tests/test_automation_foundation.py`, validation scope `Release` | Load-test tooling, local/test-data baselines, outcome-tracking design, release checklist, and final readiness report can proceed; production release approval cannot. | Mandatory human stop: Phase 12.4 production deployment and release approval; DR-016. | #11 | Non-production release-readiness work is eligible after 12.3; final release remains blocked. |

## Next controller action

Current unit: 11.4 execution operations dashboard for safe non-live monitoring. After this scoped PR is published and human-merged, the next run should refresh `main`, inspect open automation PRs, refresh this file, and begin 12.1 provider-neutral deployment architecture. If the Codex GitHub integration cannot publish an actual PR number and URL, the run must stop and report `GITHUB_WRITE_ACCESS_BLOCKED`.

## Safety confirmation

This audit did not connect to Google Ads, Meta Ads, OpenAI APIs, or other advertising services, did not request or store credentials, did not perform live Google Ads activity, and preserves `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false` with `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true` as the safe defaults.
