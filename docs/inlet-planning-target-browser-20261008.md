# Customer Planning Target Selection — 2026-10-08

Local branch `codex/inlet-planning-target-browser` from95a9ec1, reviewed receipt
runtime5c0252e. Picker authorbf543ba, cherry62c8436. Independent combined review
requested; this ledger does not imply a reviewed/integrated completion yet.

The customer editor explicitly reads retained V2 native targets for selected owned
accounts and the exact reporting period. It submits only server-issued selectors,
customer exclusions and exact integer-micro budget hypotheses. Fixed allocations
sum across all selected accounts within the confirmed goal ceiling. No native
budget write, forecast, currency conversion or spending permission is inferred.

Target-bearing revisions require fresh reads, explicit reselection and confirmation
of replacement, including removal. No old target is remapped to a new observation.
Scope changes and expiry revoke displayed handles; an invalidated read cannot
silently become an empty selection on save. Session replacement clears native data.
The original expiry is checked again on submission. Original edit head is captured
when opening the editor; later rereads do not advance its compare-and-swap check.
Generation and customer reports are blocked while an input editor is open.

Actual local HTTPS Chromium drives session/CSRF, customer routes, SQL and the real
planning composer; only provider HTTP is mocked. Initial **8 passed in49.185s**:
existing account-level lost-response/manual-history/version flow onboth databases,
plus Google/Meta/TikTok target flows onboth databases. Target cases save1micro exact
allocation, generate, refuse silent replacement, explicitly reselect exclusion,
reject scope invalidation and browser-clock expiry before saving, and clear after
same-owner session replacement. Browser-clock expiry tests client enforcement;
actual server expiry races are qualified separately. No provider execution attempts.
Evidence:`/workspace/inlet-evidence/20261008/planning-target-browser-initial.{log,xml}`.

Final focused run includes these8 journeys plus pickerDOM after edit-head pinning.
Result and reviewed integrated commit will be appended after completion. Whole Ruff,
configured mypy1065 and JavaScript syntax checks passed before that final run.

Not Full-suite validation. Not live verification. Advanced independent scenario and
comparison-window editing remain refused rather than discarded. Quality cases,
read-observed feedback, final historical test partition and the single aggregate
validation remain separate packages. No remote push, merge or deployment performed.

Final focused qualification: **9 passed,0 skips in53.489s**.
Whole Ruff/mypy1065, Node syntax and diff checks passed. Evidence:
`/workspace/inlet-evidence/20261008/planning-target-browser-final.{log,xml}`.
Independent review remains pending; no Full-suite or live result inferred.
