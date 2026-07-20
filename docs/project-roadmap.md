# Master Project Roadmap

This roadmap is based on the current repository shape: a FastAPI app, SQLAlchemy/Alembic PostgreSQL schema, read-only Google Ads collection/synchronization support, dashboard views, reliability jobs, collectors, executors reserved for controlled mutations, and tests. It defines the remaining work from current `main` to production-ready v1. Only one dependent implementation PR may be open at a time; each branch starts from latest `main` after its dependency is merged.

## Phase 8 — Read-only analytics

Required capabilities: calculations and account-local windows; PostgreSQL aggregation; deterministic findings; analytics API; read-only dashboard.

### 8.1 — Analytics foundations

- identifier: 8.1
- objective: Analytics foundations
- branch name: codex/phase8-analytics-foundations
- PR title: Add read-only analytics foundations
- dependencies: none
- exact scope: schemas, calculators, account-local windows
- explicit exclusions: dashboard, recommendations, writes
- expected files: app/analytics/*, tests/test_phase8_*.py
- migrations: new read-only tables only if required
- focused tests: calculator/window tests plus account isolation
- full validation: validate Full, PostgreSQL, ReadOnly
- security gates: no external calls; read-only imports
- privacy gates: redact search terms
- rollback requirements: drop new artifacts before merge or reversible migration
- human decisions: threshold defaults, metric availability
- acceptance criteria: window_days/days_with_metric_rows/data_coverage_ratio correct

### 8.2 — PostgreSQL aggregation

- identifier: 8.2
- objective: PostgreSQL aggregation
- branch name: codex/phase8-postgres-aggregation
- PR title: Add PostgreSQL analytics aggregation
- dependencies: 8.1 merged
- exact scope: repository aggregation and query safety
- explicit exclusions: findings/API/dashboard/writes
- expected files: app/analytics/repository.py, migrations, tests
- migrations: aggregation indexes only after query plans
- focused tests: SQL aggregation tests
- full validation: validate Full, PostgreSQL, Migrations
- security gates: disposable DB migrations only
- privacy gates: no sensitive query logs
- rollback requirements: reversible migration
- human decisions: index approval if plans require
- acceptance criteria: server-side comparison windows

### 8.3 — Deterministic findings

- identifier: 8.3
- objective: Deterministic findings
- branch name: codex/phase8-findings-service
- PR title: Add deterministic analytics findings
- dependencies: 8.2 merged
- exact scope: deterministic rules, sorting before pagination
- explicit exclusions: recommendations and writes
- expected files: app/analytics/findings.py, app/api/*, tests
- migrations: none unless persistence approved
- focused tests: finding rule tests
- full validation: validate Full, ReadOnly
- security gates: no mutation imports
- privacy gates: no raw search terms
- rollback requirements: remove service/API
- human decisions: severity thresholds
- acceptance criteria: stable sorted findings

### 8.4 — Analytics API and dashboard

- identifier: 8.4
- objective: Analytics API and dashboard
- branch name: codex/phase8-dashboard-analytics
- PR title: Add read-only analytics API and dashboard
- dependencies: 8.3 merged
- exact scope: API routes and read-only dashboard views
- explicit exclusions: recommendations and execution
- expected files: app/api/*, app/dashboard/*, tests
- migrations: none expected
- focused tests: API/dashboard tests
- full validation: validate Full, ReadOnly, Privacy
- security gates: authenticated read-only access
- privacy gates: redacted UI/logs
- rollback requirements: remove views/routes
- human decisions: display policy
- acceptance criteria: dashboard reads synchronized data

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
