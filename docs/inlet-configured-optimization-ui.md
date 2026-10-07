# Configured Existing-Campaign Customer Flow

This frontend package consumes the frozen simple optimization API at `2356077`
and the actual configured backend at `c418bc4`. It changes no runtime registry,
financial qualification, schema, settings, live gate or provider transport.

The existing Existing Campaigns page now uses a named owned campaign, confirmed
goal budget and named aggressiveness. Customers review the returned exact currency,
period instants/time zone, total cap and derived per-plan/positive-change caps,
then separately consent to the exact policy and preparation digests. The page does
not submit technical period, cooldown, action-count or percentage controls. Goal
values are editable starting inputs, never implicit consent. Only USD cents are
accepted by this configured policy contract; no FX or spending headroom is inferred.

Saving edits clears acknowledgement and prevents another action until the exact
revision is saved and consented. Goal/account/target changes clear prior draft and
amounts. The immutable consent response must retain mandate/revision/digests and
selection. Unknown mutation responses block further forward actions; no mutation
is automatically retried. A conflict also checks the current session read-only,
because late revocation may be sanitized by the backend as a conflict. Revoked
sessions clear owned data. Epoch guards discard late responses after workspace
changes.

The existing exact budget/pause review, explicit approval, execution, repeat,
original-request reconciliation, receipt and retained-exposure views remain.
Saved legacy authority is readable; the page no longer writes through its old
technical mandate endpoint. Existing fixtures exercise legacy recovery with their
already consented mandate. New configured acceptance covers the replacement
customer budget/edit/consent flow.

## Verification Boundaries

New TLS browser tests use actual configured API dependencies, private OAuth vault
contexts, native catalogs, admission, mutation and readback through MockHTTP on
SQLite and PostgreSQL. No optimization runtime getter is overridden and execution
reviews/attempts/receipts/reservations start empty. Test identity and synthetic
server qualification remain explicit offline fixtures. No live qualification or
operational success is claimed.

Cases cover Google budget change, Meta pause, both providers' unknown request
recovery without replay or exposure release, and revocation during native HTTP.
The browser verifies exact edits, consent and selection, USD precision, scope
clearing, named options, original-session clearing and no old technical writes.
The retained legacy browser tests cover initial/repeat/pause, lost response,
workspace-stale response discard, owner-role loss and recovery. Pure JavaScript
contract tests reject mismatched projections and strip untrusted extra inputs.

Final combined checks: **18 passed in 81.48 seconds** (12 configured TLS, four
legacy/automation browser cases and two contract tests). Whole-repository Ruff,
scoped mypy (two test files), Node syntax/contract checks and `git diff --check`
passed. Initial test-fixture corrections selected the exact owned Meta account
from multiple connections and made timeout-with-no-observed-effect explicit; the
revocation case led to the frontend session-clearing fix described above.

No Full, remote/hosted action,
live account operation, preview recording or artifact generation is performed.
