# Customer Worker Runtime Wiring

Baseline inspected: PR75 `01aa869b7df73bcdf1dca5fc25391a43f0af4efc`.
Production reference search found Google `run_imports` / `deliver_analysis`, TikTok
`run_tiktok`, and billing dispatcher `run` had no shipped scheduler callers. The
standalone `app.jobs.google_ads_scheduler` invoked legacy collectors, Shopify,
Meta, privacy, and analysis cadence only.

The standalone scheduler now also calls a bounded customer coordinator. Each new
stage is separately disabled by default:

- `AD_ANALYZER_CUSTOMER_GOOGLE_SCHEDULER_ENABLED`
- `AD_ANALYZER_CUSTOMER_TIKTOK_SCHEDULER_ENABLED`
- `AD_ANALYZER_CUSTOMER_BILLING_SCHEDULER_ENABLED`
- `AD_ANALYZER_CUSTOMER_ANALYSIS_OUTBOX_ENABLED`

These flags do not configure provider grants, enable legacy collectors, authorize
mutations, or activate deployed services. Provider factories retain their own
explicit runtime mode/configuration gates. Tests inject offline transports.
No deployment or live activation was performed.

Google and TikTok obey the existing master `ALL_DATA_SYNCS` control. Their existing
dispatchers revalidate active workspace, integration, account ownership, current
generation, and optional billing entitlement. There is no invented workspace-level
ALL_DATA_SYNCS switch: the existing control is master-only. Billing reconciliation
runs independently of the ad import kill switch so cancellation remains observable.
Analysis retains its own workspace control and cadence policy.

Each stage catches failures independently without logging provider payloads.
Analysis outbox delivery rechecks current source ownership, active lifecycle,
workspace control, cadence and entitlement. Workspace then connection locks fence
reconnect/disconnect through the local analysis execution; completion is reloaded
after those locks. The Google lifecycle dependency atomically retires pending
completions on reconnect/disconnect/authentication failure. Disabled or failed
analysis remains pending with a durable five-minute retry delay; an ineligible
first row cannot starve a later healthy tenant at a batch limit of one.

Migration `20261006_0034` adds nullable outbox retry time, descending from `0031`;
`0035` adds bounded retry audit fields.
When integrating the independent portal `0032` branch, add an explicit Alembic
merge revision; do not silently rewrite migration lineage.

Focused checks include actual coordinator→Google/TikTok imports, coordinator→billing
refresh, shipped scheduler invocation, default-off factories, kill switch, failed
stage isolation, blocked-first outbox fairness, disconnect/reconnect stale selection,
and actual local analysis persistence on SQLite and disposable PostgreSQL.
Full validation and hosted CI remain pending for this package.

Remaining limitations: source stages return aggregate dispatcher outcomes; the
coordinator's completed marker means invocation finished, not every tenant succeeded.
Existing analysis run keys deduplicate execution. The customer outbox explicitly
permits reclaiming only durably FAILED local runs with matching immutable source,
account, policy and metric/outcome windows. FAILED follows rollback of local analysis
and recommendation writes; no advertising mutation runs here. A row lock serializes
reclaims. RUNNING is never reclaimed on elapsed time alone. Successful rows remain
deduplicated, including when commit acknowledgement is lost. Migration0035 records
a total retry count and the most recent32 sanitized failure attempts (older detail
is intentionally bounded). Failed retryable runs back off through the outbox;
changed scope/windows fail closed instead of silently rewriting the original run. No live transport, grant, billing, or customer
journey is qualified by these offline checks.

## Provider-Neutral Outbox Review Repair

Although named GoogleImportCompletion historically, TikTok also writes this table.
Delivery now validates the persisted JobRun platform, selects that provider's owned
connection, then rechecks pending completion and tenant/account/entitlement scope.
TikTok lifecycle retirement shares the same lock order and leaves unrelated tenants'
pending work intact. Fixture TikTok import-to-analysis execution and replay are
verified on SQLite and PostgreSQL; no live provider requests were used.
