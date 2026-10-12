# Provenance Wire Version And Rollback Boundary — 2026-10-12

Baseline: local `a9c4bc34ce8269e56a5326a5c999e73bff8ec5af` on
`codex/inlet-w1-followup`. This corrects the preceding compatibility conclusion.

## Decision And Implemented Behavior

The existing V6 contract calls the v1 envelope extensible, but binds its extensions
to distinct exact policy/generator pairs. The preceding provenance package changed
neither and made old strict readers reject documents with the same recognized tags.
Backward reading alone was insufficient to define a safe writer/rollback contract.

New plans with typed selected provenance now use `inlet.plan-version.v2`. V2 requires
at least one retained capture and typed metadata for every retained capture. Plans
without typed captures remain v1. Policy/generator pairs and their private activation
rules stay unchanged; default V3 is unchanged. This is a wire-format boundary, not
new planning behavior or runtime authorization. The tag participates in the existing
canonical PlanVersion digest domain; no data migration or digest re-signing occurs.

`plan_version_storage_pair`, the repository's insertion boundary, refuses new enriched
v1 after validating canonical content. Shared `canonical`, `document_for_row`, API
current/history/export/replay and workspace archive readers continue to read original
v1 and interim enriched-v1 artifacts byte/digest-exactly. This is an explicit read-only
compatibility bridge for the unreleased intermediate format. Browser and backend
recognize only v1/v2 and reject missing v2 metadata or unknown tags. No fields are stripped.

[Design and investigated paths](design/plan-provenance-version-boundary-v1.md).

## Supported Upgrade And Rollback Contract

1. Keep generation suspended while updating readers. Deploy a reader-capable build
   consistently across API, worker/export/restore processes and frontend assets before
   allowing v2 creation. Default V3 and all existing private policy gates remain in force.
2. Original v1 rows need no migration. Interim enriched v1 requires a provenance-aware
   reader. Once a v2 row exists, every reader of that database must understand v2.
3. Rollback may only target a reader-capable build that preserves the same historical
   validation and export behavior. Keep generation suspended during the change. An old
   strict reader/image is not a supported rollback target for enriched data.
4. Do not delete rows, strip metadata, rewrite tags/digests, silently skip archive rows,
   or downgrade the database to make an old binary appear compatible. Recovery uses a
   reader-capable roll-forward or separately approved full consistent restoration.

This is a release prerequisite/runbook, not a deployed capability negotiation system,
rolling-upgrade drill, full old-image restoration test, or authorization to deploy.
No live enriched records have been inspected; all qualification uses synthetic local data.

## Checks Actually Run

Final frozen attempt: whole Ruff exit 0; configured no-path mypy exit 0 (1,511 files);
exact pytest collection exit 0. Thirty exact passing tests:

- Seven boundary cases: original/interim/v2 real storage parser and row export, exact
  old/interim digests, writer refusal, scalar/digest tamper, unknown/incomplete v2, and
  actual pre-change strict DTO reader acceptance/refusal in an isolated Python process.
  Copied prior DTO source files are fixed-hash checked. Transitive helpers are current
  unchanged validation helpers; this is not a complete old deployment image.
- Fifteen existing storage-pair cases spanning policy V1–V6, unsafe copies, canonical
  bounds and single serialization; two reviewed schema/config/source inventory cases.
- Existing reporting renderer and private V5/V6 browser checks, including unknown-tag
  and missing-v2-provenance refusal with cleared UI.
- Two SQLite and two PostgreSQL API/database/browser cases, typed v2 and legacy v1:
  current, exact version read, export, replay and actual workspace archive serializer.
  Legacy cases then generate v2 with the exact v1 parent digest and preserve original
  v1 export/replay. Typed v2 and legacy currentness remain explicitly tested.

All final original exits 0, exact ordered XML identities, no skips/errors/interruption
or remaining process groups; source hashes verified. No full-suite run or live calls.
The original attempt01 Ruff E501 in the prior-reader test script, and attempt02 mypy
errors for `os.sys` and SQL RowMapping typing, are preserved with failed source snapshots
and unrun lists. Concrete test-only fixes preceded attempt03. No test ran in either
static-failure attempt; these failures are not hidden by the final result.

Evidence: `/workspace/inlet-evidence/20261012/provenance-version-boundary-attempt03/`.
Manifest SHA256 `dd9cc6425f0a944fc3c7612b2a439099b29e6b3b84ebf1ed96712fb4e6929e5a`.
Completion freeze SHA256 `5be922ee906b8faa7974d3703f596c90566756b175b5dc1cbdfc62adcd2b1558`
binds 124 evidence files across all three attempts and 1,724 application/test sources.
Four API and two mixed-schema lineage artifacts retain complete payloads/digests.
Post-commit binding remains separate from this immutable freeze.

## Official Social Semantics Research

Repository targets are Meta v26.0 and TikTok v1.3. Meta's current Insights/action-breakdown
pages were inaccessible; TikTok's synchronous-report, supported-metric and supported-
dimension portal pages returned titles but no readable body. A direct public document
fetch was denied by the network tunnel (403); no alternate access or credentials used.
[Official Meta SDK fields](https://raw.githubusercontent.com/facebook/facebook-python-business-sdk/main/facebook_business/adobjects/adsinsights.py)
and [TikTok reporting interface](https://raw.githubusercontent.com/tiktok/tiktok-business-api-sdk/main/python_sdk/docs/ReportingApi.md)
are readable, but neither supplies the missing semantic proof. No third-party search
results or field names are used as event/attribution evidence.

Before producers, obtain readable authoritative documentation for: Meta v26.0 selected
`actions.action_type` count/absence behavior, exact attribution-window/report-time
semantics at campaign/day grain; TikTok v1.3 selected website-purchase metric/event
mapping, supported grain/date basis, absence behavior and attribution provenance.
Unknown settings may remain unknown, but generic conversion totals cannot be relabeled
selected observations. Retrieval status is recorded at
`/workspace/inlet-evidence/20261012/social-semantics-research/retrieval-status.json`.

No dependent producer implementation. Full Q09, actual live source verification,
retention/sharing decisions, six human judgments and historical R01–R03 causal uncertainty
remain open. No push/hosted CI/main merge/deployment/credentials/live provider/model
calls/advertising changes/spending occurred.

Independent completion review CLOSED: all124 evidence and1724source hashes, 30exact
XML passes/original exits and static logs verified. Four API sets have independently
recomputed payload digests; both mixed-lineage artifacts bind v2 to the exact v1 parent
and preserve old export/replay/archive payloads. Typed v2 archive serialization is
assertion-backed in passing API tests, not a separately copied artifact. No blocker
to local commit; rollout limits and all unresolved owner/live/source gates remain.
