# Customer Comparison Period Form — Frozen Interface

W1 form package uses existing PlanInputRevision reporting_window/comparison_window
fields; no new API/schema or policy activation. Keep explicit UTC entry. Optional
comparison must precede or meet primary start, be positive, and use completed past
times; source-local calendar qualification still belongs to the owned reader. Do
not silently round or align entered dates, invent missing rows, or infer comparable
attribution from two periods.

Add an explicit comparison checkbox with start/end controls. New plans default to
no comparison. Editing loads both saved windows and preserves exact original aware
timestamp strings when their displayed minute value is unchanged, including saved
fractional seconds and offsets. Disabling comparison explicitly submits null;
signout/cancel/new/workspace changes clear all remembered period state.

Primary/goal/account changes invalidate native target receipts exactly as today.
Comparison-only changes do not change the native primary catalog request and may
retain its unexpired selection; the server still binds the new exact plan input and
rechecks all reporting evidence. Do not add comparison to the native endpoint or
reuse targets after primary scope/session/expiry changes. Review replacement rules
for saved target choices remain unchanged.

Use a small pure period parser/projection module with exact UTC-instant ordering
at microsecond precision. Preserve server strings; render minute controls in UTC.
Do not change the generic manual-application timestamp helper. Actual form save,
request recovery, guarded operation/cookie checks and history/export paths stay
unchanged. Primary/comparison evidence output uses the existing document renderer;
version comparison remains separately named and behaves as before.

Focused acceptance: pure parser invalid dates/order/missing comparison/timezones/
precision; actual authenticated browser create/edit/remove comparison and exact saved
precision, primary target invalidation versus comparison-only preservation, session
change/late response and unchanged request scope. Use real API responses, no ready
bundle/controller stubs. Existing target/scenario/progress browser checks remain in
W1 aggregate; focused tests should exercise changed paths. Actual v3 import-to-plan
comparison output is a separate required W1 integration case, not credited here.
