# Opt-In Meta Count Runtime V1

Baseline bb79dbf. Local implementation only; no live activation or new credentials.
`INLET_CUSTOMER_META_REPORTING_ENABLED` defaults false independently of Meta imports
and native diagnostics. The actual `app.main.app` already includes the reporting
router and static assets; it is a module-level application, not an app factory.

The reporting dependency lazily composes the existing customer service and Meta
Vault. Disabled Meta/reporting flags or missing/invalid existing encryption key or
app secret produce the existing fixed unavailable response before any transport is
constructed. Existing customer-owned encrypted grants remain the only token source.
No consent, scope expansion, credential provisioning or write client is introduced.

A production availability callback is mandatory in this composition. Explicit test
injection retains its earlier optional callback for compatibility. The callback is
side-effect-free and checks local flags/configuration before reads/replays, around
provider IO, under the final write transaction and immediately before commit.
Existing authority, grant, aggregate, selection and deadline guards remain in place.
State/invalidation do not require a reporting runtime. A failed read or late disable
must leave no capture/fact rows.

The transport is lazy and caller-owned, with zero automatic retries, environment
proxy settings ignored and no redirects. It permits only HTTPS GET requests to
`graph.facebook.com` at the fixed v26 account metadata and Insights paths. The
existing producer retains page/byte/time limits and its exact purchase-count profile.
Money/ROAS and effective attribution remain unsupported/unknown respectively.

Qualification uses the actual application, middleware, static assets and routes,
with disposable SQL, existing fake identity and fixture HTTP transport. The unchanged
production planner defaults to v3, which must advertise no selected-reporting
capability. Complete handoff coverage explicitly configures the existing canonical
private v4 constructor in the fixture; it never replaces service or authority logic
and does not activate a production policy. Browser actions perform selection,
capture, explicit handoff, editor save and generation; actual same-session APIs
supply current/history/export artifacts. SQLite precedes PostgreSQL; exact bounded
cases, original failures, source freeze and independent review remain required.
