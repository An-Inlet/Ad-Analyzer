# Account Diagnostics Customer Page

`/app/account-diagnostics` is a separate read-only customer journey linked from
Existing Campaigns. It uses the existing owned advertising-account list and the
frozen `AccountDiagnosticIntentV1`/`AccountDiagnosticViewV1` interface at177edff.
No spending mandate or campaign review is constructed by the page.

A customer explicitly chooses an account and UTC start/end times, then selects
Read Account Diagnostics. Dates have no defaults; the requested past window is
bounded to366days and the server remains authoritative. No native read occurs on
sign-in or account selection. Results show the owned account name/platform,
requested period, read/refresh timestamps, bounded item counts and fixed readable
findings. Missing inventory counts are not manufactured as zero. The page never
renders native monetary counters, provider resource IDs, proof payloads or raw JSON.
Optimization remains explicitly unavailable, with no safe-spend or causal claim.

Workspace/account/date changes invalidate in-flight results. Original session and
CSRF-cookie changes, logout and owner denial clear owned state; late success or
failure from A→B→A cannot restore it. Lost responses are not automatically retried.
Only explicit same-origin CSRF-protected diagnostic POSTs are made; all output is
textContent and no browser storage is added.

The browser qualification harness uses real HTTPS sign-in/API/vault/service paths
and all three actual collectors with MockTransport at the fixed HTTP transport seam.
Only clock and low-level transport are injected; the service/factory are not replaced.
A failing mandate-check sentinel verifies that reads do not depend on spending
consent. Backend445616f is merged. All six actual browser/provider/database journeys pass.
Combined browser/shell/contracts/route-boundary validation: **18 passed**, no skips,
in26.49s. Whole Ruff, clean mypy609 files, node syntax and diff checks pass.
Logs: `/tmp/inlet-account-diagnostics-ui-integrated.log` and
`/tmp/inlet-account-diagnostics-ui-final-types.log`.

Each journey confirms explicit read only, bounded valid periods, current owned
names, fixed findings, no money/resource/secret rendering, successful late A→B→A
invalidation, lost-response no automatic retry, disabled factory zero native calls,
transport closure, logout and owner-role denial. The first social fixtures included
an additional valid Google account; the test now selects the intended owned account
instead of assuming the account list has exactly one entry.

No live access, provider credentials, execution runtime or optimization policy is
enabled by this page. Backend deployment/provider configuration and intended-
environment qualification remain separate gates.
