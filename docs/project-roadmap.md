# Master Project Roadmap

This roadmap is based on the current repository shape: a FastAPI app, SQLAlchemy/Alembic PostgreSQL schema, read-only Google Ads collection/synchronization support, dashboard views, reliability jobs, collectors, executors reserved for controlled mutations, and tests. It defines the remaining work from current `main` to production-ready v1. Only one dependent implementation PR may be open at a time; each branch starts from latest `main` after its dependency is merged.

## Phase 8 — Read-only analytics

Required capabilities: calculations and account-local windows; PostgreSQL aggregation; deterministic findings; analytics API; read-only dashboard. Phase 8 findings are calculated live unless a later human decision explicitly approves persistence.

### 8.1 — Analytics foundations

- identifier: 8.1
- objective: Analytics foundations
- branch name: codex/phase8-analytics-foundations
- PR title: Add read-only analytics foundations
- dependencies: none
- exact scope: calculations, schemas, account-local windows, settings, and tests
- explicit exclusions: database migrations, PostgreSQL aggregation, findings, API endpoints, dashboard views, recommendations, approval workflow, and writes
- expected files: app/analytics/calculations.py, app/analytics/schemas.py, app/settings.py if needed, tests/test_phase8_analytics_foundations.py
- migrations: none; do not add read-only tables in PR 8.1
- focused tests: calculation, schema, settings, account-local window, Decimal/integer micros, observed-zero versus unavailable metrics
- full validation: validate Full, ReadOnly, Privacy
- security gates: no external calls; no collector, executor, sync-trigger, token, conversion upload, or mutation imports
- privacy gates: no sensitive search-term output or logs
- rollback requirements: remove analytics-only modules and tests
- human decisions: threshold defaults and metric availability matrix
- acceptance criteria: window_days, days_with_metric_rows, and data_coverage_ratio are distinct and correct without persistence

### 8.2 — Repository aggregation and query safety

- identifier: 8.2
- objective: Repository aggregation and query safety
- branch name: codex/phase8-repository-aggregation-query-safety
- PR title: Add PostgreSQL analytics aggregation and query safety
- dependencies: 8.1 merged
- exact scope: PostgreSQL aggregation, account isolation, pagination, query-plan review, and query safety tests
- explicit exclusions: deterministic finding rules, API endpoints, dashboard views, recommendations, approval workflow, and writes
- expected files: app/analytics/repository.py, tests/test_phase8_repository_aggregation.py, optional Alembic migration only for query-plan-justified indexes
- migrations: query-plan-justified index migration only; no persistence tables unless a later human decision approves them
- focused tests: PostgreSQL aggregation, account isolation, pagination, server-side comparison windows, unavailable metrics, unsafe query rejection
- full validation: validate Full, PostgreSQL, Migrations, ReadOnly
- security gates: migration downgrade tests only on disposable PostgreSQL; no mutation imports
- privacy gates: no sensitive query logs or search-term dumps
- rollback requirements: reversible index migration if added; remove repository module and tests
- human decisions: index approval based on actual query plans
- acceptance criteria: aggregations are account-scoped, paginated safely, and comparison windows are derived server-side

### 8.3 — Deterministic findings service and API

- identifier: 8.3
- objective: Deterministic findings service and API
- branch name: codex/phase8-deterministic-findings-api
- PR title: Add deterministic analytics findings service and API
- dependencies: 8.2 merged
- exact scope: finding rules, service layer, API endpoints, authorization, deterministic sorting, pagination after sorting, and no-write tests
- explicit exclusions: dashboard routes, templates, CSS, recommendations, approval workflow, persistence, and Google Ads writes
- expected files: app/analytics/findings.py, app/analytics/service.py, app/api/*, tests/test_phase8_findings_api.py
- migrations: none unless a human decision explicitly approves persistence before this PR starts
- focused tests: deterministic rule tests, API authorization, account isolation, no-write boundary, sanitized errors, stable sorting before pagination
- full validation: validate Full, ReadOnly, Security, Privacy
- security gates: authenticated API access; no executor, collector, sync-trigger, token, conversion upload, or mutation invocation
- privacy gates: sensitive search-term text redacted or excluded according to approved display decision
- rollback requirements: remove findings service, API routes, and tests
- human decisions: severity thresholds, display/redaction policy, and whether persistence is explicitly approved
- acceptance criteria: API returns deterministic read-only findings without invoking write-capable code

### 8.4 — Dashboard analytics views

- identifier: 8.4
- objective: Dashboard analytics views
- branch name: codex/phase8-dashboard-analytics-views
- PR title: Add read-only dashboard analytics views
- dependencies: 8.3 merged
- exact scope: dashboard route, templates, CSS, navigation, and dashboard tests only
- explicit exclusions: new API endpoints, recommendation generation, approval workflow, execution, collectors, sync triggers, and Google Ads writes
- expected files: app/dashboard/router.py, app/dashboard/templates/*, app/dashboard/static/dashboard.css, tests/test_phase8_dashboard_analytics.py
- migrations: none expected
- focused tests: dashboard auth, route rendering, account isolation, redacted display, no synchronization or mutation trigger
- full validation: validate Full, ReadOnly, Privacy
- security gates: authenticated read-only dashboard access
- privacy gates: no sensitive search-term text in logs, screenshots, or broad rendered dumps
- rollback requirements: remove dashboard route, templates, CSS changes, and tests
- human decisions: dashboard UX and redaction policy
- acceptance criteria: dashboard renders read-only analytics views backed by existing API/service behavior only

## Phase 9 — Recommendation generation

Required capabilities: convert findings into proposed actions; deterministic recommendations first; rationale, confidence, estimated impact; no Google Ads mutations.

### 9.1 — Recommendation schemas

- identifier: 9.1
- objective: Recommendation schemas
- branch name: codex/phase9-recommendation-schemas
- PR title: Add recommendation proposal schemas
- dependencies: Phase 8 merged
- exact scope: proposal models with rationale/confidence/impact
- explicit exclusions: execution or approval queue
- expected files: app/recommendations/*, migrations, tests
- migrations: proposal storage if approved
- focused tests: schema/repository tests
- full validation: validate Full, ReadOnly
- security gates: no Google Ads mutations
- privacy gates: no sensitive rationale output
- rollback requirements: reversible migration
- human decisions: executable type candidates
- acceptance criteria: recommendations remain proposed only

### 9.2 — Deterministic recommendation service

- identifier: 9.2
- objective: Deterministic recommendation service
- branch name: codex/phase9-deterministic-recommendations
- PR title: Generate deterministic recommendations from findings
- dependencies: 9.1 merged
- exact scope: finding-to-proposal conversion
- explicit exclusions: approval workflow and writes
- expected files: app/recommendations/service.py, tests
- migrations: none
- focused tests: service tests
- full validation: validate Full, ReadOnly
- security gates: no live API calls
- privacy gates: redacted terms
- rollback requirements: remove service
- human decisions: severity/confidence policy
- acceptance criteria: deterministic output

### 9.3 — Recommendation API/dashboard preview

- identifier: 9.3
- objective: Recommendation API/dashboard preview
- branch name: codex/phase9-recommendation-preview
- PR title: Add read-only recommendation preview
- dependencies: 9.2 merged
- exact scope: read-only preview endpoints/views
- explicit exclusions: approve/reject/defer/execution
- expected files: app/api/*, app/dashboard/*, tests
- migrations: none
- focused tests: API/UI tests
- full validation: validate Full, ReadOnly, Privacy
- security gates: read-only only
- privacy gates: safe display
- rollback requirements: remove routes/views
- human decisions: operator display decisions
- acceptance criteria: operators can review proposals

## Phase 10 — Approval and audit workflow

Required capabilities: recommendation review queue; approve, reject, and defer states; authenticated operator identity; timestamps and immutable audit events; no execution without approval.

### 10.1 — Audit data model

- identifier: 10.1
- objective: Audit data model
- branch name: codex/phase10-audit-model
- PR title: Add approval audit data model
- dependencies: Phase 9 merged
- exact scope: review states and immutable audit events
- explicit exclusions: execution
- expected files: app/approvals/*, migrations, tests
- migrations: approval and audit tables
- focused tests: migration/model tests
- full validation: validate Full, Migrations
- security gates: operator identity required
- privacy gates: no sensitive payloads
- rollback requirements: reversible migration
- human decisions: approval state policy
- acceptance criteria: audit events immutable

### 10.2 — Review queue service and API

- identifier: 10.2
- objective: Review queue service and API
- branch name: codex/phase10-review-queue
- PR title: Add recommendation review queue
- dependencies: 10.1 merged
- exact scope: approve/reject/defer APIs with auth identity
- explicit exclusions: Google Ads execution
- expected files: app/api/*, app/approvals/*, tests
- migrations: none
- focused tests: state transition tests
- full validation: validate Full, Security, Privacy
- security gates: auth required
- privacy gates: minimal event details
- rollback requirements: remove API/service
- human decisions: defer semantics
- acceptance criteria: no execution without approval

### 10.3 — Review dashboard

- identifier: 10.3
- objective: Review dashboard
- branch name: codex/phase10-review-dashboard
- PR title: Add approval dashboard
- dependencies: 10.2 merged
- exact scope: operator queue UI
- explicit exclusions: execution buttons that write Google Ads
- expected files: app/dashboard/*, tests
- migrations: none
- focused tests: dashboard auth tests
- full validation: validate Full, Security, Privacy
- security gates: authenticated operators
- privacy gates: redacted display
- rollback requirements: remove views
- human decisions: operator UX
- acceptance criteria: review actions audited

## Phase 11 — Controlled Google Ads execution

Required capabilities: dry-run execution; account-level allowlists; allowlisted mutation types; idempotency; stale recommendation checks; explicit human approval; compensating or rollback actions; execution audit history; emergency kill switch.

### 11.1 — Execution policy model

- identifier: 11.1
- objective: Execution policy model
- branch name: codex/phase11-execution-policy
- PR title: Add controlled execution policy foundation
- dependencies: Phase 10 merged
- exact scope: dry-run policy, allowlists, kill switch config
- explicit exclusions: live mutations
- expected files: app/execution/*, migrations, tests
- migrations: policy/audit tables
- focused tests: policy tests
- full validation: validate Full, ControlledWrites with approved placeholder update
- security gates: no live writes yet
- privacy gates: no secrets
- rollback requirements: disable policy
- human decisions: mutation allowlist decisions
- acceptance criteria: policy fails closed

### 11.2 — Dry-run executor

- identifier: 11.2
- objective: Dry-run executor
- branch name: codex/phase11-dry-run-executor
- PR title: Add Google Ads dry-run execution planning
- dependencies: 11.1 merged
- exact scope: dry-run plans and idempotency keys
- explicit exclusions: live mutate calls
- expected files: app/execution/*, tests
- migrations: execution plan tables
- focused tests: dry-run tests
- full validation: validate Full, Security
- security gates: no live writes
- privacy gates: redacted plans
- rollback requirements: remove executor
- human decisions: idempotency policy
- acceptance criteria: dry-run output auditable

### 11.3 — Approved controlled mutations

- identifier: 11.3
- objective: Approved controlled mutations
- branch name: codex/phase11-controlled-mutations
- PR title: Enable allowlisted approved Google Ads execution
- dependencies: 11.2 merged and human mutation approval
- exact scope: allowlisted mutation calls, stale checks, rollback/compensation, audit history
- explicit exclusions: non-allowlisted writes
- expected files: app/executors/google_executor.py, app/execution/*, tests
- migrations: execution audit migrations
- focused tests: mocked mutation tests only
- full validation: validate Full, ControlledWrites
- security gates: explicit approval and kill switch
- privacy gates: no sensitive raw responses
- rollback requirements: disable kill switch/revert
- human decisions: allowlist and rollback decisions
- acceptance criteria: live writes require approval

### 11.4 — Execution operations dashboard

- identifier: 11.4
- objective: Execution operations dashboard
- branch name: codex/phase11-execution-dashboard
- PR title: Add execution monitoring dashboard
- dependencies: 11.3 merged
- exact scope: execution history, kill switch visibility
- explicit exclusions: new mutation types
- expected files: app/dashboard/*, tests
- migrations: none
- focused tests: dashboard tests
- full validation: validate Full, Security, Privacy
- security gates: operator-only access
- privacy gates: no raw API dumps
- rollback requirements: remove views
- human decisions: incident UX
- acceptance criteria: audit history visible

## Phase 12 — Production hardening

Required capabilities: deployment architecture; managed PostgreSQL; secrets management; worker and web process deployment; monitoring; alerting; backups and restore testing; rate limiting; incident response; performance and load testing; outcome tracking; release checklist.

### 12.1 — Deployment architecture

- identifier: 12.1
- objective: Deployment architecture
- branch name: codex/phase12-deployment-architecture
- PR title: Document production deployment architecture
- dependencies: Phase 11 merged
- exact scope: web/worker topology and release plan
- explicit exclusions: actual production deploy
- expected files: docs/*, config examples
- migrations: none
- focused tests: documentation tests
- full validation: validate Full, Release (expected fail until approved)
- security gates: no secrets
- privacy gates: no prod URLs
- rollback requirements: doc revert
- human decisions: hosting decisions
- acceptance criteria: architecture approved

### 12.2 — Managed infrastructure configuration

- identifier: 12.2
- objective: Managed infrastructure configuration
- branch name: codex/phase12-managed-infrastructure
- PR title: Add production infrastructure configuration
- dependencies: 12.1 merged
- exact scope: managed PostgreSQL, secrets, worker/web deployment config
- explicit exclusions: manual secret values
- expected files: deployment files, docs, tests
- migrations: none or config migrations
- focused tests: config tests
- full validation: validate Full, Security
- security gates: external secrets only
- privacy gates: no sensitive output
- rollback requirements: remove config
- human decisions: provider decisions
- acceptance criteria: deploy config safe

### 12.3 — Monitoring backup and incident response

- identifier: 12.3
- objective: Monitoring backup and incident response
- branch name: codex/phase12-operations
- PR title: Add monitoring, backups, restore, and incident response
- dependencies: 12.2 merged
- exact scope: alerts, backups, restore tests, runbooks
- explicit exclusions: live release
- expected files: docs/*, tests
- migrations: none
- focused tests: runbook/checklist tests
- full validation: validate Full, Release
- security gates: human release gate
- privacy gates: safe logs
- rollback requirements: revert docs/config
- human decisions: alert/retention decisions
- acceptance criteria: restore procedure tested

### 12.4 — Production readiness release

- identifier: 12.4
- objective: Production readiness release
- branch name: codex/phase12-production-readiness
- PR title: Complete production-ready v1 checklist
- dependencies: 12.3 merged and release approval
- exact scope: performance/load, outcome tracking, final report
- explicit exclusions: new product features
- expected files: docs/*, tests
- migrations: none
- focused tests: release checklist tests
- full validation: validate Full, Release after implementation
- security gates: human release approval
- privacy gates: privacy review complete
- rollback requirements: hold release
- human decisions: release criteria
- acceptance criteria: production-ready v1 recorded
