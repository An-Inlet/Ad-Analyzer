# Customer Meta Count Reporting — 2026-10-12

Baseline `8c51d923e2827bfd0c2d7fe6ebe739730d2a37c4`; local branch
`codex/inlet-w1-followup`. This package implements the customer-facing selection,
read-only capture and explicit Planning handoff for one Meta website-purchase count
profile. Runtime injection defaults to unavailable. No live reporting is activated.

## Implemented Behavior

The [shared contract](design/meta-customer-count-flow-v1.md) separates imported-range
review from provider acquisition. Customers review a closed date range inside an
owned completed import, explicitly select Website Purchases — Count Only, and
request a capture. Reviewing the range makes no new aggregate provider request.
The service admits only exact `offsite_conversion.fb_pixel_purchase` actions from
the previously qualified Meta v26 campaign/day count producer.

Selection uses current owner/session/account evidence and an expected-selection
comparison. The reviewed basis binds the owned import, scope, grant fingerprint,
query profile and dates. A capture-preparation endpoint returns a server-derived
HMAC ID that commits the original session, workspace/account, selection, basis,
dates and nonce. Capture validates that commitment before replay or provider IO;
changed grants, bases and sessions cannot reuse an old capture ID. Retries preserve
the exact intent. Original authority is checked again before atomic persistence.
Invalidation remains available without a reporting runtime or paid read entitlement.

Reporting displays explicit zero separately from missing counts and omitted days.
Money and ROAS are unsupported; effective attribution remains unknown. The UI clears
stale state on account/workspace/session changes, prevents repeated active writes,
and retains exact requests after lost responses. Google keeps its original direct
capture route and request shape.

Customers may explicitly apply a Meta capture to a new plan through the existing
Reporting-to-Planning handoff. The exact validated Meta profile now projects count
windows in the selected planner; older unverified Meta and TikTok profiles remain
unsupported. Native campaign mapping still applies. Captures outside that mapping
remain gaps. Traffic, spend and monetary values are not inferred from counts.
Coverage remains partial or unavailable with attribution limitations. Historical
pin validation and document wire versions are unchanged. This package changes no
stored-schema model or schema inventory; the new support gate affects new generation.

## Verification

75 unique exact cases passed: 23 component, 26 SQLite and 26 PostgreSQL, with no
failures, errors or skips in the accepted case set. Whole-repository Ruff, configured
no-path mypy (1,529 files), exact collection, whitespace checks and seven JavaScript
syntax checks passed. Final evidence is under
`/workspace/inlet-evidence/20261012/meta-customer-attempt09/`; `completion.json`
records every accepted original result/XML and six retained journey artifacts.

All 52 database cases and final static checks ran in attempt 09. Twenty unchanged
controller/legacy cases are retained from attempt 05, and three pure profile cases
from attempt 07. The independently checked carry boundaries contain only the new
fixture corrections, with no production changes. `retained-components.json` records
exact source deltas and original manifest hashes. `completion-freeze.json` binds the
source and evidence; final independent review and local commit binding are recorded
alongside it. One heavy slot, resource floors, bounded process cleanup,
SQLite-before-PostgreSQL and first-failure stops were maintained. No broad suite or
unchanged failure was rerun.

The Meta customer journey uses actual customer APIs, owned SQL, import/capture
services and plan generation/history/export with synthetic Meta wire responses.
Its browser checks drive the real controllers with controlled fetch responses;
they do not claim a hosted Meta browser-to-provider run. Existing Google coverage
includes its actual local TLS browser/API capture flow. No live-account verification
or advertising mutation is claimed.

Original attempts and failures remain preserved. Attempt 01 stopped on two Literal
DTO type errors. Attempts 02–04 passed static/controller checks before the Planning
support expansion and Google button repair. Attempt 05 stopped on a new graph
fixture's numeric connection revision; attempt 06 then stopped on the negative
TikTok fixture's incorrectly formatted provider reference. Attempt 07 stopped at
SQLite's binding trigger because the new fixture omitted FK enforcement; attempt 08
correctly produced unmapped-campaign gaps because the fixture reported campaign `1`
while the native catalog contained `5` and `7`. Repairs correct the fixtures and retain
production validation. Final synthetic reporting uses mapped campaign `5`; campaign `7`
remains unreported. No failure was retried unchanged or overwritten.

## Remaining Work And Holds

Next bounded work: explicit opt-in Meta runtime composition and an assembled Meta
browser/API journey, while maintaining unavailable defaults and all live gates.
TikTok's exact report metric/dimension/data-level combination remains unqualified.
Custom events/pixel identity, money, verified effective attribution and deleted-object
completeness remain separate gaps. The public webpage remains independently tracked;
this package adds no public live-product claim.

Owner retention/artifact-sharing decisions, six human quality judgments, Q13
independent provider verification and historical R01–R03 uncertainty remain open.
No push, PR, hosted CI, merge, deployment, real credentials, live provider/model
call, advertising write or spend occurred. Planning remains manual-action-only.
This is implemented, fixture-qualified software, not a purchasable live release.
