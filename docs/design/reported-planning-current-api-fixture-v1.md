# Actual Current API Session Handoff

Follow-up fixture seam for the reviewed reported planning-consent repair. No
production or authentication changes are needed; no historical session secret is
invented or passed across the child boundary.

The coherent original DTO retains its exact original session ID and financial IDs.
For HTTP acceptance, use the existing real TestClient login with token subject equal
to the original user's existing subject (the scalar actor UUID), FakeProvider, and
normal current session/CSRF issuance. Do not edit the original user/session or seed
a usable cookie for the historical dummy session.

Build the server-owned ReportedFeedbackRuntime with the existing explicit window
policy and current clock. POST the actual `/reported-feedback/comparisons` endpoint
with original attempt/goal/revision and existing100m objective. Read its actual
ComparisonProgress response and original current principal from persisted login
rows. Construct PreparedReportedRead from those actual values, with unchanged
original scalar DTO. No hidden preliminary service request/job is created.

One narrow shared acquisition helper refinement is required:
`prepare_reported_acquisition` must check `job.original_session_digest` against
`prepared.principal.session.digest`, and explicitly require that principal.user.id
is the original scalar actor and session.user_id matches it. Its actual request
still binds the same original attempt/source/goal/account/campaign. The current
request session can legitimately differ from the historical fixture session: the
current customer API already permits the same owner to start a new request after
login, and `_owned_job` scopes reads to that requesting session. Default existing
callers still supply the original principal and retain exactly their prior check.
No optional arbitrary session string, modified DTO IDs, job rewrite or guard bypass.

Then reuse actual current acquisition, coherent profile/native GET and real planning
preparation/confirmation, using the fresh requesting principal throughout. Construct
the initial V2 preview through the actual authenticated initial-planning endpoint,
and POST reported-feedback preview through its actual route. Runtime dependency
injection supplies only the genuine server-owned configured runtime, never a
principal, amount, fabricated preview or proof. Real auth/owner/CSRF/session checks
remain active. Verify no-store,46m baseline→47m reported nominal amount, no new
execution consent for that reference, unchanged original effect/ledger and zero
current native POST. Revoked fresh session and stale configured planning policy
must reject without a new slot/pointer. Exact native/cap tests remain at actual
service boundary unless additionally exercised over HTTP; report distinction.

This seam is proposed for review before shared-helper/API implementation. The
coherent source and direct-service reproduction remain independently qualified;
no API claim follows from those prior tests alone.

## Reviewed Due-Time HTTP Clock Input

The first actual ordinary login/request on October9 returns the real acquisition
due time October13. Its ordinary session expires before that due time; preserve
this observed denial rather than extending expiry. For explicitly simulated due-time
requests, use a scoped module-local `app.customers.access.time` namespace reading
that same scenario clock. Assert the first session is rejected then issue a fresh
ordinary-TTL session through the actual login route at the returned due time.
Only during issuance replace `app.api.customer.time` with that timestamp and give
FakeProvider coherent claims through actual `verified_identity`. This is the already
reviewed Q16 clock-input technique, not a replacement guard/provider-active decision.

Global `time.time` stays untouched. All namespaces/provider verify functions restore
on context exit. Runtime source/acquisition clock and request authentication use the
same simulated instant, then normal prescribed acquisition spacing; no future-issued
session is accepted merely because real wallclock lags. POST a new actual comparison
under the fresh session; old job remains legitimately superseded, not rewritten.
Native clocks, DB freshness floor and ordinary TTL remain unchanged. Report this
as simulated-time authenticated HTTP qualification, not real-time browser evidence.
