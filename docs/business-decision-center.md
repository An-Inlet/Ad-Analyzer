# Business decision center

Open a workspace and select **Open decision center**. The page combines company plans with the existing Google Ads, web analytics, and CRM outcome pipeline. It evaluates recorded evidence locally and never calls an advertising executor or a paid AI model.

## Feature coverage

| Capability | Implemented behavior | Evidence or operator input needed |
| --- | --- | --- |
| Company goals and strategy | Versioned goal, target, dates, approved budget, margin assumption, CAC ceiling, capacity, audience, positioning, offer, constraints | Workspace owner/admin enters the actual business plan; the system does not invent approved budgets |
| Customer and business value | Campaign customer acquisition cost, observed CRM revenue, cancellations through the existing outcome contract, and contribution after advertising | Approved measurement contract and linked CRM lifecycle/value events; this is observed cohort value, not predicted lifetime value |
| Measurement health | Source freshness, per-account sync checks, unmapped CRM events, attribution coverage, currency conflicts and planning completeness | Existing collected data; missing evidence is shown explicitly |
| Funnel diagnosis | Comparable mature 28-day cohorts, equal follow-up time, stage rates and investigation prompts | Sufficient denominators and valid source mapping; rate changes are not proven causes |
| Budget planning | Completed-day pacing, reservations, overspend/shortfall alerts, custom and 80/100/120% scenarios, bounded campaign allocation preview | Matching currency, complete account-day spend, minimum mature outcomes and operator-selected response assumptions |
| Business events | Launch/promotion/conference/seasonal/inventory/capacity plans, preparation dates, active phase, follow-up and reserved money | Confirmed events reserve remaining funds; edit dates to recalculate the plan |
| Creative and audience learning | Campaign-linked audience, hook, promise, style, format, offer, landing path, possible fatigue and next-test brief | Current connector provides campaign context; it cannot isolate an individual ad or demographic segment |
| Explainable actions | Ranked recommendation queue with evidence, goal, next step, expected result, budget implication, confidence and review date | Evidence fingerprint checked before acceptance; stored snapshots cannot be edited |
| Experiments | Predefined two-arm design, locked after start, aggregate counts, maturity/sample checks, lift and a 95% difference interval | Unique independent units and declared randomization; operator supplies results with an evidence reference |
| Decisions and outcomes | Planned/accepted/rejected/completed decisions, reasons, expected/observed results, business changes, review reminders, revision history and strategy restore | Observed results remain separate from approval preferences; records are not automatically treated as causal evidence |
| Understandable reporting | Responsive workspace page, authorized portfolio, numerical topic-based answers, CSV action brief and saved nightly/weekly strategy briefs | Questions cover budget, goals, funnel, events, creative and experiments; answers use deterministic evidence lookup |
| Controlled operation and costs | Existing automation switches and ad review/execution controls retained; manual costs/estimates separated by currency; increases marked for financial review | No billing connector, conversion upload, new paid service or live advertising mutation is enabled |

## First use

1. Confirm the workspace's existing advertising, web analytics, CRM and measurement settings.
2. Set the company goal, planning period and approved budget. The configured optimization and customer stage keys appear beside the funnel; confirm these match the business meaning intended.
3. Add upcoming events, remaining event reservations, creative concepts and experiment plans. Keep experiment and event reservations mutually exclusive to avoid reserving the same money twice.
4. Review measurement warnings and the action queue. Inspect budget assumptions before recording any decision.
5. Record observed results on the chosen review date. Enabled nightly and weekly analysis jobs save a strategy brief without adding another scheduler or service.

## Calculation boundaries

- Advertising spending sums canonical campaign rows only. Ad-group, keyword and search-term rows are not added to their parent campaign totals.
- Planning uses UTC and completed advertising dates; today's incomplete spending is excluded. Per-account day coverage is required for forecasts. Absent days are not assumed to be zero spend, and complete account days cannot prove that every individual campaign row arrived.
- Currencies are never combined or silently converted. Recorded operating costs and estimates remain separate and include only records fully contained in the strategy period.
- Outcomes follow the existing approved cohort attribution and maturity rules. The previous cohort receives the same follow-up horizon. Platform conversions are not equated with CRM customers or incremental sales. Goal pace assumes a linear target across the plan period.
- Contribution uses the operator's entered margin before advertising, then subtracts advertising costs. It is not accounting net profit and excludes the separately recorded operating costs. Profit scenarios apply the response assumption to contribution before ads and then subtract the entire proposed advertising spend.
- Budget scenarios estimate future results from remaining unreserved funds. The default elasticity is 0.7; the sensitivity band is assumed, not fitted or a statistical confidence interval. Revenue/customer value beyond observed CRM evidence, retention, repeat purchases and lifetime value are not invented.
- Allocation baseline shares follow historical spending among enabled campaigns, not their current live budgets. A preview requires comparable evidence, sufficient outcomes in the donor and recipient, and a greater than 25% observed return gap. Each side changes by at most 10% of its baseline allocation. This is a test hypothesis, not an assertion about marginal returns or guaranteed improvement.
- Experiment results use Wilson intervals for each proportion and a Newcombe difference interval. A completed, mature, sufficiently sampled, declared randomized test can be marked promising only when the interval clears the predefined meaningful difference. There is no early winner while a test is running. Assignment is not independently verified.
- Topic answers report the saved plan and available figures. They are not an unrestricted AI chat interface and cannot answer questions requiring data outside the connected sources.

## Storage, access and APIs

Migration `20260906_0017` adds versioned business records, append-only application revisions and a nullable aggregate decision brief on existing analysis runs. Each record belongs to a workspace; revision references use a composite workspace foreign key. Updates use compare-and-swap versions to reject stale edits. Repeated decisions on identical evidence conflict instead of creating duplicates.

Dashboard reads use existing per-request identity and membership checks. Workspace owners/admins and platform admins can edit; viewers cannot. All form POSTs validate the existing CSRF token. Production IAP authentication and the script-free content security policy remain in place. The existing operator bearer API remains an all-workspace operator interface.

API root: `/api/v1/workspaces/{workspace_slug}/intelligence`.

- `GET` root: composed report, current evidence, actions and bounded recent history.
- `GET /records/{kind}`: paginated records, with `limit` and `offset`.
- `POST /records/{kind}` / `PUT /records/{kind}/{record_id}`: validated `{expected_version, payload}` commands.
- `POST /scenario`: `{proposed_budget_micros, response_elasticity, uncertainty_bps}`; preview only.
- `POST /ask`: `{question}`; bounded numerical evidence lookup.

Kinds are `strategy`, `event`, `creative`, `experiment`, `cost`, `change`, and `decision`. Money uses integer millionths in the API and currency units in dashboard forms. User-defined percentages use basis points internally. Free text is length-bounded and HTML-escaped; do not enter customer-level personal information in business planning notes. CSV cells protect against formula injection. Raw click IDs, CRM lead IDs, credentials and event payloads are not included in decision reports or exports.

The dashboard composes up to 200 records per category, displays 100 recent revisions and eight scheduled briefs, and reports a blocking issue when category coverage is exceeded. Record APIs provide pagination. There is no destructive deletion endpoint.

## Release and validation

Run pytest, Ruff, mypy, diff checks and the repository's PostgreSQL migration, privacy, security, isolation and read-only gates. Unit tests use disposable SQLite for schema creation/upgrade; downgrade/re-upgrade checks run only on the disposable PostgreSQL CI service.

Release remains subject to the human gate in `docs/automation-policy.md`. Apply the additive migration before serving the new application image and verify an authorized workspace, a viewer, a portfolio page and an enabled scheduled analysis. No secrets or new external subscriptions are needed. A rollback should restore the prior application image while retaining the additive schema; do not downgrade a production database to undo this feature.

Live conversion feedback, additional advertising-platform collectors, individual-ad metrics and billing integrations remain dependent on separately configured and approved integrations. The decision center surfaces those evidence limits rather than simulating successful connections or changing paid services.
