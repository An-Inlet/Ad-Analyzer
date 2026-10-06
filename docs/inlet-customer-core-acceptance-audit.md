# Customer Core Acceptance Audit And Analysis Attention

Reviewed root `1c82e03` on isolated `codex/inlet-customer-acceptance-audit`.
Current reference is `docs/inlet-candidate-acceptance.md`; earlier per-package
matrices are historical, not evidence that later APIs/connectors remain missing.
Frozen Full/CI candidates and manual dispatch were not touched.

## Present Customer Paths

`app/portal/static/index.html` exposes self-service sign-in, provisioning, supported
connection flows, goals, campaign review, billing management, activity, exports,
measurement and closure. Native execution/catalog/qualification factories remain
explicitly unavailable without approved server runtime bindings. Their existence
is not proof that a fresh customer can purchase or run live optimization.

Recent offline API/browser suites cover these paths independently. PR178 adds real
owned archive/closure APIs over populated replacement/social evidence and continues
a second brand through the execution facade. That is not a fresh-user/live-purchase
pilot and should not be advertised as one. No blanket missing-API claim is retained.

## Offline Engineering Versus External Gates

| Area | Concrete current boundary | Next work classification |
| --- | --- | --- |
| Billing | contracts force livemode=False, StripeBilling requires sk_test_, factory selects stripe_test only, webhook rejects live events; storage is not environment-scoped | Environment-separated production code is missing offline engineering, not merely waiting for keys. Shared proposal in `/workspace/inlet-design/BILLING-ENVIRONMENT-PROPOSAL.md`; schema reservation pending root review |
| Local analysis monitoring | Persisted AnalysisRun states were explicitly excluded from attention | Implemented by this package using existing rows; no migration or heartbeat inference |
| Operational gaps | No durable storage-failure records, scheduler heartbeat, never-started-work evidence or external alert delivery | First three are additional instrumentation/recovery engineering; intended destination/escalation and actual delivery are deployment/owner gates |
| Provisioning/identity | Owned idempotent provisioning and revocable sessions, real browser module available | Intended IdP/project configuration and deployed redirect/session behavior need qualification; routine offline retry/isolation already covered, not a request for new tenant operator setup |
| Account connections | Customer OAuth/selection/disconnect and real mocked provider adapters exist | Actual app/scopes/permissions/history and unrelated accounts require external qualification; do not collapse existing runtime tests into a live claim |
| Closure/export | Owned bounded archive, privacy revisions and local fencing/receipts exist; external ads/billing unchanged | Uniform writer deployment qualification and actual external disposition remain explicit; audit/media retention terms are owner policy, not permission to release unknown exposure |
| B20 | Recent API/browser/component and two-brand archive/closure compositions exist | Final assembled Full/hosted checks plus coherent fresh-customer purchase/onboarding acceptance and unrelated live pilots remain; historical service-only test passes are not substituted |

No native exposure/repeat/mature-learning implementation was re-reviewed or changed;
those packages have separate owners. Commercial price/tier/currency/trial/tax/refund
and external cancellation decisions remain unset. Missing production billing code
cannot be hidden behind those genuine decisions.

## Delivered Bounded Monitoring Gap

Before implementation, four focused tests failed across SQLite and PostgreSQL:
local failed/running analyses produced no observation, and analysis truncation was
not surfaced. Add `analysis_failed` and `analysis_running_overdue` to the existing
sanitized operator signal schema. Query only workspace/cadence/account/status/start
scalars for active workspaces, bounded to500rows plus a truncation probe. Existing
PostgreSQL statement timeout remains in force; signal bound increases19→21.

Latest terminal success suppresses a terminal failure only for the same workspace,
cadence and account. A distinct running analysis remains overdue even if another run
succeeded: neither elapsed time nor a later success establishes physical termination.
No error text, decision brief, retry payload, customer identifiers or advice is
returned. Operator action stays `inspect_local_job`, never automatic rerun.

Validation: combined operations/provider-attention tests35passed in22.14s with
SQLite/PostgreSQL; Ruff app/tests, configured mypy501files, diffcheck passed.
Logs `/tmp/inlet-analysis-attention-before.log`,
`/tmp/inlet-analysis-attention-final.log`, `/tmp/inlet-analysis-attention-mypy-final.log`.
An intermediate run exposed the new signal's action mapping and bounded-query count
assertion; both were corrected before final pass. No Full, live calls, alerts,
provisioning, billing change or deployment occurred.
