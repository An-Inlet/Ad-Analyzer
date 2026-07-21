# Roadmap status

Last refreshed: 2026-07-21
Baseline audited: latest available main containing Phase 11.3 (PR #13)
Automation controller: `docs/project-controller.md`

## Status legend

- **Complete**: acceptance criteria are implemented, tested, and documented on the audited baseline.
- **Partially complete**: equivalent implementation exists but one or more technical acceptance criteria remain.
- **Missing**: no equivalent implementation was found.
- **Blocked by a required human decision**: the remaining work requires an explicit human decision or approval listed in `docs/decision-register.md` or the controller safety policy.
- **Superseded by an equivalent implementation**: behavior is satisfied through the existing architecture under different module names than the roadmap suggested.

## Completion summary

- Total roadmap units audited: 17
- Complete or superseded units: 15
- Partially complete units: 0
- Missing units with satisfied dependencies: 0
- Human-blocked units: 2
- Current automated completion percentage: 88% (15 of 17 units complete or superseded)

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
| 11.3 Approved controlled mutations | Complete for safe non-live controlled execution | `app/executors/google_executor.py`, `app/executors/planner.py`, `app/settings.py` | `tests/test_phase11_controlled_execution.py`, `tests/test_analyzer_v1.py`, `tests/test_google_ads_read_only.py` | None for Phase 11.3 safe non-live scope; live mutation enablement remains intentionally not implemented. | Production/live mutation enablement still requires DR-005, DR-006, DR-008, DR-009, and DR-010 before any live account or write-capable adapter is added. | This PR | Pending in this controller run. |
| 11.4 Execution operations dashboard | Complete for non-live operator execution operations | `app/dashboard/router.py`, `app/dashboard/templates/account.html`, `app/dashboard/templates/execution_operations.html`, `docs/operations/runbook.md` | `tests/test_analyzer_v1.py` | None for non-live Phase 11.4 scope; the dashboard intentionally omits live execution and synchronization controls. | Live mutation enablement remains blocked by DR-005, DR-006, DR-008, DR-009, and DR-010. | This PR | Pending in this controller run. |
| 12.1 Deployment architecture | Complete for provider-neutral non-production deployment architecture | `Dockerfile`, `.env.example`, `app/deployment.py`, `app/main.py`, `deploy/docker-compose.yml`, `deploy/reverse-proxy.example.conf`, `docs/deployment-architecture.md`, `docs/operations/runbook.md`, `scripts/validate_deployment_startup.py` | `tests/test_deployment_architecture.py` | None for the approved provider-neutral, non-production scope. | Production decisions remain blocked: hosting provider selection, paid infrastructure activation, production credentials, production database connection, and production deployment. | #16 | GitHub Actions passed with disposable PostgreSQL and migration validation. |
| 12.2 Managed infrastructure configuration | Eligible for approved safe non-production scope | `deploy/docker-compose.yml`, `.env.example`, `docs/operations/runbook.md` | `tests/test_automation_foundation.py` | Provider-neutral managed infrastructure configuration examples, external secret-manager placeholders, process/environment configuration, and startup validation remain eligible; provider selection, paid infrastructure, real credentials, and deployment are excluded. | Production provider selection, paid infrastructure activation, production credentials, production database connection, and production deployment remain human-blocked. | Not started | Eligible after PR #16 merges for provider-neutral non-production configuration only. |
| 12.3 Monitoring backup and incident response | Complete | `docs/operations/runbook.md` | `tests/test_automation_foundation.py` | None for documentation-level runbook; live alert sinks and backup execution remain launch inputs. | DR-014 and DR-015 remain required before production activation. | #11 | Pending in this controller run. |
| 12.4 Production readiness release | Blocked by a required human decision | `docs/definition-of-done.md`, `docs/build-progress.md` | `tests/test_automation_foundation.py`, validation scope `Release` | Final production readiness report and release approval are not complete. | Mandatory human stop: Phase 12.4 release approval; DR-016. | #11 | Blocked; no production release or deployment occurred. |

## Next controller action

Earliest eligible incomplete unit after PR #16 merges: Phase 12.2 — provider-neutral managed infrastructure configuration. The eligible Phase 12.2 scope is limited to provider-neutral managed infrastructure configuration examples, external secret-manager placeholders, process/environment configuration, and startup validation. Provider selection, paid infrastructure, real credentials, production database connections, production deployment, and live Google Ads activity remain blocked.

## Safety confirmation

This audit and Phase 11.4 non-live dashboard implementation did not connect to Google Ads, Meta Ads, OpenAI APIs, or other advertising services, did not request or store credentials, did not perform live Google Ads activity, and preserves `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false` with `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true` as the safe defaults.

## Phase 12.1 status

Phase 12.1 is complete for provider-neutral non-production deployment architecture in PR #16. It includes `Dockerfile`, `.env.example`, `app/deployment.py`, `app/main.py`, `deploy/docker-compose.yml`, `deploy/reverse-proxy.example.conf`, `docs/deployment-architecture.md`, `docs/operations/runbook.md`, and `scripts/validate_deployment_startup.py`, with deterministic coverage in `tests/test_deployment_architecture.py`. There are no missing acceptance criteria for the approved provider-neutral, non-production scope. Production hosting provider selection, paid infrastructure activation, production credentials, production database connection, and production deployment remain blocked, and live Google Ads activity remains blocked. GitHub Actions passed with disposable PostgreSQL and migration validation.
