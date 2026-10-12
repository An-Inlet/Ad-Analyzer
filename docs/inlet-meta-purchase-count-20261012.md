# Meta Website Purchase Count Producer — 2026-10-12

Baseline `b4633835f9c14dda1443405813c095bba1ccf2ff`; local branch
`codex/inlet-w1-followup`. This package replaces the broad Meta count-producer hold
with one narrowly documented, offline-qualified report. It does not activate a
customer connection picker or live runtime.

## Evidence And Behavior

[The reviewed contract](design/meta-purchase-count-producer-v1.md) records official
Meta SDK 26.0.2 sources and the previously verified primary-source action reference.
The SDK establishes the GET Insights building blocks; combining them into this
campaign/day reader is an explicitly labelled engineering inference. Meta's primary
documentation endpoints still returned 429/fetch errors here. No access restriction
was bypassed. Full tool results are retained under
`/workspace/inlet-evidence/20261012/meta-count-research/official-web-results.json`.

The new `meta.website-purchase-count.campaign-day.v1` profile reads only exact
`offsite_conversion.fb_pixel_purchase` counts from `actions`. Generic purchase,
app purchase, lead, or optimization-conversion totals cannot substitute. Explicit
zero remains present; missing rows/actions/values remain missing. Invalid numeric
cells, duplicate JSON keys/actions/rows, foreign scope, unexpected grain, cursor
cycles and incomplete pagination fail closed. Money is always unsupported.

Requested attribution overrides are not sent. Effective windows, report time,
counting mode and campaign-status completeness remain unknown. These unknowns do
not prevent retaining an exact reported count; they still prevent unsupported
comparison, monetary or business-equivalence claims. Prior unverified social
profiles, historical payloads and digests remain unchanged.

The injected HTTP reader uses a fixed origin and never follows provider next URLs
or redirects. Page/body/cursor/time limits and original authority checks surround
IO. Its caller owns the underlying transport; page clients borrow it and close all
response streams. No default network factory was added.

The internal acquisition wrapper derives campaign mapping from owned SQL records,
pins the original customer session, source generation, encrypted grant, selection,
aggregate and privacy revision, and revalidates before atomic storage. No database
transaction crosses provider IO. The new write context performs final authorization
and deadline checks before commit; its physical SQLite transaction encloses nested
savepoints. Existing read contexts are unchanged. Stored results support exact
idempotent replay and the existing customer export serializer.

## Qualification

Final evidence: `/workspace/inlet-evidence/20261012/meta-count-attempt09/`.
102 unique exact cases passed: 84 component cases, nine SQLite cases and nine
PostgreSQL cases. This includes malformed/missing/zero, profile/request/effective
contradictions, bounded pagination, injected HTTP scope/errors, transport and stream
lifetime, actual original-session/grant/generation/selection/sync invalidation,
foreign report scope, no partial persistence, exact final-guard rollback,
storage/export/replay, legacy commitments, schema inventories and browser display.
Browser Meta variants are presentation-only DTOs; SQL captures use the actual new
producer and synthetic wire responses. No live-account coverage is claimed.

Whole-repository Ruff, configured no-path mypy (1,523 files), exact collection,
`git diff --check` and three JavaScript syntax checks passed. Final 49 changed
component cases and all 18 database cases ran in attempt09. Thirty-five unaffected
legacy/schema/browser cases are retained from attempt04 with the precise source
boundary recorded in the completion evidence. Static checks ran on the final source
in attempt08. No aggregate suite rerun occurred. One heavy slot, bounded process
cleanup, resource floors, SQLite-before-PostgreSQL and first-failure stops were used.

All original attempts remain available:

- 01: Ruff stopped on one overlong new-test comment.
- 02: mypy stopped on a missing callback-list annotation in the new test.
- 03–04: static and 82 component cases passed before the SQL assertion refinement.
- 05: launcher rejected already-existing carried component paths before starting
  any subprocess; its manifest and stop explanation remain intact.
- 06–07: refreshed static checks passed; eight SQLite cases passed, then the exact
  final-guard test found a real SQLite savepoint durability defect. PostgreSQL was
  not started. Explicit physical BEGIN fixes the concrete mechanism.
- 08–09: final static and affected cases passed after that fix and the independently
  reviewed transport-lifetime correction. Original failures were not rerun unchanged.

Independent source review closed the transaction and transport fixes. Final evidence
review and commit binding are recorded in the external completion manifest.

## Next Package And Remaining Holds

Next: the customer-owned Meta event selection/acquisition service and route can use
this exact internal producer, after defining its interface and preserving explicit
confirmation, quota, original-session and grant boundaries. No public route/default
network activation is part of this delivery. Other independent offline work remains
available.

TikTok still needs a documented exact website-payment metric/dimension/data-level
combination before a corresponding producer. The [earlier source map](inlet-capture-settings-retention-20261012.md#source-gaps-and-holds)
retains the official URLs. Money scaling, custom-event/pixel identity, effective
attribution settings and deleted-object completeness remain separate deferred
features, not prerequisites retroactively imposed on this bounded Meta count reader.

Owner retention/artifact-sharing decisions, six human quality judgments, Q13
independent provider verification and incompletely explained historical R01–R03
causes remain open. No push, PR, hosted CI, merge, deployment, live provider/model
call, real credential operation, advertising write or spend occurred. Planning
remains manual-action-only; this is implemented and fixture-qualified software,
not a purchasable live release.
