# Inlet Build Progress

Last updated: 2026-10-05. Product: **Inlet**. Company: **An Inlet**.

## Baseline And Working Rules

- Fetched current `origin/main`: `ea3591c5086fbf2cee8038bf9208ac7f0050de75`.
  It exactly matches the audit baseline; no newer main functionality to reconcile.
- Read `AGENTS.md`, automation policy, definition of done, PR template, CI and
  deployment workflow. No additional local skill instructions were found.
- Preserve architecture and independent-source behavior. Launch scope remains
  Shopify ecommerce with Google, Meta and TikTok Ads; planned customer-data
  integrations are Klaviyo, HubSpot and Omnisend.
- No production deployment, merge, advertising spend or customer-account changes
  are authorized by this development assignment. No such actions were performed.
- Only one dependent product PR at a time under the current repository policy.

## B01 — Conversion Diagnostics

Branch: `codex/inlet-b01-conversion-diagnostics`.

Draft PR: [#64](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/64).
Implementation commits: `91fe009` (diagnostics), `afe2cd9` (required-check fixes).

Reproduced before editing the rule: 100 clicks, 10 conversions and 100,000,000
cost micros incorrectly generated `spend_without_conversions`. Fractional positive
conversions also reproduced the error. A zero-spend input exposed another false
positive. Initial focused regression run: **3 failed, 5 passed**, as expected.

Implemented: require available conversions, sufficient coverage, at least 20
clicks, positive spend and exactly zero conversions. Include actual conversion
count in supporting metrics. Preserve separate comparison-based CPA regression;
do not invent an absolute CPA goal. Correct two old API/dashboard expectations
that mislabeled a fixture containing 2.5 conversions. No historical production
findings have been rewritten; the fix applies when diagnostics are recomputed.

Focused regressions cover the required 100/10/$100 case, fractional conversions,
true zero conversions, positive-spend boundary, zero spend, low clicks, missing
metrics, insufficient coverage and generated recommendations. Existing API and
dashboard tests verify presentation and preserved CPA regression. Campaign scope
is prepared for owner review in [the proposed matrix](inlet-campaign-scope.md);
live action eligibility is still empty.

### Validation

Python 3.12.14; isolated virtual environment at `/workspace/inlet-venv`; PostgreSQL
16 in disposable local container `inlet-b01-postgres`, database `inlet_ci`.

Before baseline maintenance, reproduced **four mypy errors on untouched main**
with SQLAlchemy 2.1.3, and the Shopify rolling-window test also failed on untouched
main because its September fixture aged out of the real clock's current window.
Constrained SQLAlchemy to `>=2.0.32,<2.1` (resolved 2.0.54), and injected the fixture
clock into the test's report calls. These changes address actual required-check
failures without changing customer reporting behavior.

- `python -m pytest tests/test_analyzer_v1.py tests/test_analysis_cadences.py`:
  **38 passed** after the diagnostic fix.
- `scripts/validate.sh Full` with guarded disposable PostgreSQL: **exit 0**;
  primary pytest result **600 passed, 6 skipped**. The six skips require
  PowerShell, which is unavailable on this Linux environment.
- Ruff: passed. Mypy: passed, 159 source files. Whitespace diff check: passed.
- PostgreSQL integration tests and migration upgrade/downgrade/upgrade: passed.
- ReadOnly: **75 passed**. Security: **98 passed, 1 skipped** (PowerShell).
- Privacy: **14 passed**. Final Focused gate: **38 passed, 6 skipped**, including
  successful repeated-full validation on the same disposable database.
- Full log: `/tmp/inlet-validation-full.log` in this execution environment.

Remote CI pending at PR creation; local required validation is complete. Nothing
is live-verified or deployed. No new migration is introduced by B01. Git fetch
and push work; GitHub CLI API requests returned Forbidden, so the authorized
GitHub connector was used to create the draft PR.

## B02–B04 — Customer Foundation

Investigation confirms audit findings still apply:

- `app/dashboard/auth.py`: process-local session map.
- `app/api/auth.py`: global operator bearer authentication.
- `app/workspaces/access.py`: email membership and development admin shortcut.
- `app/ads/repository.py`: job creation defaults workspace to 1.
- `app/crm/worker.py`: defaults workspace to 1 and selects first active connection.

Prepared [shared interfaces and acceptance plan](inlet-foundation-contract.md) for
verified identity, revocable database sessions, customer-scoped access, atomic
idempotent signup, explicit connections and job ownership. This is design work,
not an implemented customer foundation.

Next package: B02 implementation and two-user/two-replica PostgreSQL acceptance,
then B03 provisioning and B04 ownership. Provider-specific security architecture
and subsequent dependent PR are gated as described in the contract. Recommended
owner decisions: Google Cloud Identity Platform plus PostgreSQL-backed sessions;
review B01, then approve one foundation integration branch with sequential
B02–B04 commits. Do not self-approve or merge.

## Public Webpage — Separate Delivery

Resolved source files:

- `Inlet-One-Page-Package-v2.zip` — Library ID
  `libfile_c7511cbe70a8819186e74f5ad8cc5b19`.
- `Inlet-MVP-Audit-and-Build-Plan.docx` — Library ID
  `libfile_284a9e8240288191afc99820dc4bc6b8`.

The complete audit was read through Library. Materialization of both attachments
to this executor failed, including the single bounded retry. No webpage source
bytes were available for safe reuse or visual inspection. Needed: make the
existing ZIP accessible to this executor through the supported Library flow, or
provide its two original source files. Do not recreate the established design
from memory. Next edit is Salesforce to Omnisend and associated accurate copy,
preserving Squarespace compatibility, logo, typography, green palette, Title Case,
graphics, illustrative demo, FAQs and email early-access buttons.

The owner will publish on Aninlet.com. Do not publish on their behalf. The source
reports the page unpublished; current live publication has not been verified.
Signup, billing, connections and advertising functionality remain separate from
the public demonstration and must not be described as working SaaS capabilities.

## Remaining Backlog

Follow audit dependencies after B02–B04: B05 Shopify identity/metrics; B06 editable
goals and usage; B07 mandate/action state; B08 Google connection; B09 Google actions;
B10 granular Meta data; B11 TikTok; B12 Klaviyo/HubSpot/Omnisend; B13 subscriptions;
B14 media/review; B15 Google publication; B16 Meta/TikTok actions/publication;
B17 measured feedback; B18 onboarding/portal plus existing page reuse;
B19 operations; B20 unrelated pilot businesses. Track implementation tests
separately from provider approval and live pilot evidence throughout.

## Approved Foundation Continuation — 2026-10-05

The owner explicitly approved Google Cloud Identity Platform with PostgreSQL-backed
revocable sessions and the B02–B04 sequential-commit exception in existing draft
PR #64. Main remains `ea3591c`; B01 remains preserved. The scoped exception is
recorded in `docs/automation-policy.md`. No merge, deployment, provider setup,
credential creation, IAM expansion or advertising mutation is authorized. Website
work is now left entirely to the owner; earlier website-next-step notes are stale.

B02 implementation adds a distinct customer API, immutable provider identities,
shared eight-hour revocable sessions, one-time token exchange, CSRF/origin checks,
and active customer-only membership enforcement. See `inlet-customer-auth.md`.
Focused acceptance: **33 passed**, including real PostgreSQL, cross-user and
cross-replica revocation, concurrent replay, provider/project changes and suspended
memberships. Ruff and mypy passed (165 files). Full validation (`scripts/validate.sh Full`) completed with exit 0: **633 passed,
6 PowerShell skips**; PostgreSQL/migration upgrade-downgrade-upgrade passed;
ReadOnly 75 passed, Security 98 passed/1 PowerShell skip, Privacy 14 passed,
Focused 38 passed/6 PowerShell skips. Log: `/tmp/inlet-b02-full.log`.
Remote exact-head CI will be recorded in PR #64 after push.
Provider calls in acceptance use a fake; no live identity setup or login verified.

## B03 — Atomic Customer Workspace Provisioning

Implementation adds authenticated `POST /api/customer/v1/workspaces`, requiring
CSRF/origin checks and an owner-scoped idempotency key. Workspace/configuration/
owner/receipt commit atomically, with PostgreSQL user-row serialization. Replays
return the original active owner workspace, conflicting input/slug fails, and
suspended ownership cannot be restored through signup. Client owner IDs are
rejected. Migration `20261005_0021` introduces signup receipts only.

Focused identity/provisioning acceptance initially **41 passed**; final validation
adds two backend cases rejecting missing keys and injected owner IDs. Ruff and
mypy pass (167 files). Full required validation (`scripts/validate.sh Full`) completed with exit 0:
**643 passed, 6 PowerShell skips**; PostgreSQL/migrations, lint/type checks and
all required safety gates passed. Log: `/tmp/inlet-b03-full.log`. Provider, UI and
live customer signup remain unverified; no external configuration changed.

## B02/B03 Hosted Verification

B02 commit `bebe01a6946839824ff3798c63b3db8435241c6d`: hosted workflow
[37285028501](https://github.com/Konner-An-Inlet/Ad-Analyzer/actions/runs/37285028501)
completed successfully. B03 commit `ba27903ffa04010e8b3909a7b1aa86df7f574645`:
[37285937918](https://github.com/Konner-An-Inlet/Ad-Analyzer/actions/runs/37285937918)
completed successfully. These verify repository checks, not live provider behavior.

## B04 — Explicit Import Ownership

Implemented the shared canonical connection registry, scoped Google account/jobs,
Meta/Shopify native bindings, version 2 CRM ingress and worker ownership, scoped
signatures/deduplication, and sanitized rejection records. Removed implicit workspace
1 defaults from import models and job creation. Migration 0022 preserves historical
unbound Google rows; native backfill replay preserves connection identity/revocation.
See [rollout requirements](inlet-import-ownership.md). Legacy unscoped CRM ingress and
messages fail closed. Missing Google ownership blocks before collection.

Focused new acceptance: **34 passed**, including PostgreSQL, actual CRM ingress/push
worker, Google worker boundaries and migration downgrade/re-upgrade. No external
provider calls, customer ad changes or deployment occurred. Full validation results
will be appended before committing this package.

Next package is B05 Shopify identity/metrics. The owner-approved sequential-commit
exception ends at B04. Prepare B05 acceptance/review independently; starting its
next dependent implementation PR awaits normal predecessor review/merge or an
explicit extension. Do not infer merge/deployment authority from development approval.
Website delivery is now the owner's responsibility and is outside this work package.

B04 full-suite rerun: **678 passed, 6 PowerShell skips**; Ruff and mypy passed
(176 files), whitespace clean, PostgreSQL checks **3 passed**, migration
upgrade/downgrade/upgrade passed. ReadOnly **75 passed**, Security **98 passed/1
PowerShell skip**, Privacy **14 passed**. The initial run caught fixture whitespace
in nested validation; it was corrected before this successful suite rerun.
Final Focused validation and exact-head hosted CI are recorded in PR #64 when complete.
Local log: `/tmp/inlet-b04-full.log` (ephemeral); this ledger and PR retain results.

Full B04 validation finished with **exit 0**. Final Focused gate: **38 passed,
6 PowerShell skips**. B04 is ready for its separate commit and hosted verification
on `codex/inlet-b01-conversion-diagnostics`, draft PR #64. No merge or deployment.

## Independent Review Repairs — B01–B04 Scope

Review of `c670f508` reproduced a B02 replay defect with locally generated RSA JWTs
and the actual Firebase/Google verifier: alternate signature padding was accepted,
and exchange after logout returned 200. Canonical unpadded Base64url validation now
rejects padding and nonzero unused pad bits before verification. Receipt hashes for
valid tokens stay unchanged. Regression covers actual signatures, logout/replay,
fresh tokens and distinct users on SQLite and PostgreSQL; only external certificate
and user transports are replaced. No provider credentials or network calls.

Nine failures against the original native-import code reproduced Shopify reconnect,
uninstall/shop-redact registry state, failed Meta job provenance, and concurrent
canonical revocation defects. Repairs allow only verified reconnect to restore the
same owned registry record, revoke on verified removal, include connection IDs on
failed Meta jobs, and refresh/lock native ownership in native→workspace→connection
order through the existing bounded page transaction. PostgreSQL verifies an
in-flight import serializes with revocation and later imports are rejected.

Focused review acceptance: **44 passed**, including migration of an existing
`reconnect_required` Shopify installation followed by synthetic verified OAuth.
Ruff, mypy (179 files), and whitespace pass. Full/hosted verification follows.

CRM OpenAPI now exposes the actual scoped v2 path. Missing explicit database
configuration returns a clear 503; the former development-default SQL fallback is
not used by ingress. **CRM deployment remains blocked:** the original Terraform
is publish-only and lacks ownership SQL access/per-connection secret grants.
No IAM or live infrastructure was changed. Prepared least-privilege alternatives
are in `inlet-import-ownership.md`; an owner security decision precedes provisioning.
This is an acceptance repair within B02–B04, not an extension to B05 implementation.

Repair reproduction used installed `firebase-admin 7.7.0` and `google-auth 2.59.1`.
The full-suite rerun passed **690 tests, 6 PowerShell skips**; lint, mypy (179 files),
whitespace, PostgreSQL (3), reversible migrations, ReadOnly (75), Security (98/1
PowerShell skip), and Privacy (14) passed. The first full run identified the old
public-route allowlist expectation; it now requires scoped ingress while still
excluding internal push endpoints. Final Focused/hosted results follow below/in PR64.

Full repair validation completed with **exit 0**; final Focused gate **38 passed,
6 PowerShell skips**. Log: `/tmp/inlet-review-full.log`. All current B01–B04 tests
pass; the CRM permission/lookup architecture is still explicitly decision-gated.

## B04 Rereview — Concurrent First Meta Connections

At head `9fd19c568`, a real PostgreSQL test synchronized two actors with separate
pending grants after distinct advertising-account inserts. It reproduced
`psycopg.errors.DeadlockDetected` during the workspace/native uniqueness lock cycle.
The workspace lock now uses `FOR NO KEY UPDATE`, preserving suspension protection
while remaining compatible with FK `KEY SHARE` locks. Integrity handling now spans
account creation through binding/commit, so a losing request returns the existing
connection-conflict error and rolls back all partial records.

Focused acceptance: **30 passed**, including synchronized first connection,
PostgreSQL suspension/revocation during an import, migrated Shopify reauthorization,
privacy lifecycle and Meta import regressions. One complete connection/account/
registry and one unconsumed losing grant remain after the concurrent test. Ruff,
mypy (180 files), and whitespace pass. Full validation follows. No gateway
architecture/configuration, IAM, website, or live provider change was made.

Deadlock-correction Full validation completed with **exit 0**: **694 passed,
6 PowerShell skips**; Ruff, mypy (180 files), whitespace, PostgreSQL (3), reversible
migrations, ReadOnly (75), Security (98/1 PowerShell skip), Privacy (14), and Focused
(38/6 PowerShell skips) all passed. Log: `/tmp/inlet-meta-lock-full.log`.
Exact corrective-head CI is recorded in PR #64 after push.

## B05 — Canonical Commerce Measurement (Implementation)

Owner approval received 2026-10-05 15:46:40 UTC extends the PR64 exception through
B05 only and confirms merchandise sales net discounts/refunds excluding tax and
shipping, refund processing dates, store-local calendar months, and 13 months of
minimal measurement history. The earlier CRM gateway architecture decision remains
open. Main remains audit baseline `ea3591c`; previous PR head `f1793d99` passed hosted
CI run 37296556343 with 700 tests and no skips.

Implemented the versioned contract in `inlet-commerce-contract.md`: stable scoped
HMAC identities, Shopify-authoritative merchandise events, verified-source linkage,
distinct known customers, explicit calendar/cumulative windows, revisioned daily
facts and immutable ordinary snapshots. Added customer-scoped preview/snapshot
endpoints, optional default-off history importer, migration 0023, extended privacy
exports, 13-month retention and persistent erasure suppression across reconnects.
Privacy deletion removes snapshots/history and prevents reporting remaining facts
as complete zero. Existing raw 59-day cash-collected functionality is preserved.

Initial focused run: 60 cases passed for commerce plus existing Shopify. Additional
OAuth and transaction rollback regressions added afterward. Mypy currently covers
190 files; required Full validation and exact-head CI results will be recorded below.
Schema-only Shopify validation passed all three queries; no live provider calls.
Standalone documentation helper unavailable; pinned-version/live reconciliation
and Shopify history/customer access approval remain release gates. B06 goal editing,
B12 real customer-data adapters and CRM deployment are not implemented by this package.

B05 focused acceptance now passes **35 cases** including populated PostgreSQL
upgrade/downgrade/re-upgrade, optional OAuth scopes, retry backoff and atomic failed
pages. The first Full attempt found the older migration test loading today's ORM
at schema 0022; it now migrates through head while preserving its B04 backfill and
revocation assertions, and verifies existing Shopify connections remain unbound.
That attempt reported 726 passed, 6 skips, and the migration failure plus its nested
Full-run failure. Ruff and mypy (190 files) pass after correction.
An extra SQLite migration experiment stops at pre-existing migration 0002's unsupported
constraint alteration; the required migration acceptance target is PostgreSQL.

B05 final local `scripts/validate.sh Full` completed with **exit 0**: **728 passed,
6 PowerShell skips**. Ruff, mypy (190 files), whitespace, PostgreSQL (3), reversible
migrations, ReadOnly (75), Security (98/1 PowerShell skip), Privacy (14), and Focused
(38/6 PowerShell skips) all passed. Full log: `/tmp/inlet-b05-full.log`. The final
Focused gate also verifies repeated validation on the same disposable database.
The earlier standalone SQLite experiment is not a supported full migration result.

B05 is implemented and fixture/PostgreSQL-verified, not live-verified. Exact pushed
commit and hosted CI evidence are recorded in draft PR64. No merge, deployment,
provider grant, live import, advertising change, gateway configuration or website
edit occurred. B06 is the next package: persist an editable, customer-confirmed goal
with an explicit metric/source, currency, timezone, calendar-versus-cumulative
window and baseline snapshot. Goal confirmation must not authorize campaign
publication or increase a spending mandate. B06 implementation follows predecessor
review/merge or a new explicit extension under `docs/automation-policy.md`; the
approved integration exception currently ends at B05. CRM gateway architecture
remains a separate unresolved owner decision.

### B05 Delayed Privacy Delivery Review

After initial B05 commit `929e747`, a review found that delayed erasure addressed to
an old domain could miss a reconnected canonical store. The new regression failed
on both SQLite and PostgreSQL before the repair. Verified merchant-domain aliases
now resolve privacy delivery to retained measurement data and the current native
connection. Migration 0024 backfills current domains; reconnect preserves prior
verified domains. Stale uninstall events still cannot erase newer authorization.
The focused commerce/legacy Shopify/migration suite passes after correction. A new
Full run and corrective-head hosted CI are required; the earlier CI run covers only
`929e747` and is not evidence for this follow-up.

Initial B05 hosted CI **37341160941** passed at `929e747acaa0fa87abcc0111f7582a65fee1af94`:
**734 passed, zero skips**, all gates succeeded. The alias-only local Full run also
exited 0 (730 passed/6 PowerShell skips), but does not cover the later fixes below.

Further privacy regressions reproduced on SQLite and PostgreSQL: customer-level
export omitted linked legacy facts, erasure could leave/replay the legacy copy,
and reconnect with measurement disabled discarded the canonical privacy binding.
The correction adds a minimal canonical key to legacy facts, backfills known links,
applies export/erasure across both layers, and retains verified privacy identity
on baseline-scope reconnect. Legacy imports pause before provider reads when source
suppression prevents safe reconciliation; reports cannot mark the remaining data
complete. Verified-domain aliases preserve delivery across domain changes.

Corrective focused acceptance: **73 passed**, including the populated PostgreSQL
0024 downgrade/upgrade and all existing Shopify tests. Ruff, mypy (190 files) and
whitespace pass. Final corrective Full and hosted results are pending at this commit;
PR64 records the exact corrective SHA and terminal results. No live provider or
infrastructure action occurred. This remains B05 acceptance repair, not B06 work.

B05 retention rereview reproduced an old order with a recent unallocated adjustment
losing its `unreconciled` marker during cleanup, making a report incorrectly return
zero. Expiry now requires both creation and latest source update to predate the
retention floor. A focused regression verifies unavailable stays unavailable and
that the minimal marker eventually expires. This is a B05 correctness repair;
current-head Full/CI evidence remains in PR64.

### B05 Independent Review Repairs

Review of `22a9aa0` reproduced four defects on SQLite and PostgreSQL: an open return
could be counted before refund processing; pre-enable erasure could replay after
binding measurement; ten paused/revoked stores could starve an eligible eleventh;
and a customer-only privacy request could be reported complete while unclassified
legacy facts remained. These are B05 acceptance repairs, with no B06 work.

Refund normalization now requires agreement type/reason and uses refund.processedAt;
unsupported return/exchange workflows remain unavailable rather than double-counted.
Pagination retains that metadata. Durable workspace/domain HMAC erasure guards
survive pre-enable requests, disconnect and reconnect. Migration 0025 copies available
legacy tombstones and marks open requests pending where retained facts cannot yet
be classified. Missing old identity cannot be invented or recovered retroactively.
Canonical backfill bridges legacy facts before suppression; customer exports and
delivery return 409 until identity reconciliation completes, without deleting
unrelated facts. Legacy imports pause when customer identity is required. Scheduler
eligibility is filtered before the batch limit, preserving pause/revocation semantics.

Combined focused suite: **93 passed**, including populated PostgreSQL 0025 migration
and both database dialects. Ruff, mypy (**192 files**) and whitespace pass. An added
export/delivery 409 assertion is separately rerun before commit. Prior-head hosted
CI 37345161957 succeeded at `22a9aa0`; it does not cover these repairs. Corrective
head Full and hosted CI are pending; exact SHA and terminal evidence belong in
PR64 to avoid a documentation-only commit invalidating the checked head.

### B05 Migrated Privacy Export Replay

Bounded rereview of `4885645` found two remaining migrated-request gaps. Both were
reproduced on the unchanged commit using populated disposable PostgreSQL 0024/0025
round trips: authenticated request replay returned an empty measurement export after
identity reconciliation, and canonical-only unknown-customer history did not set
pending during migration. The first fixture initially hit timestamp validation;
a corrected clock then reproduced the actual empty-export defect.

Authenticated replay now unions newly resolved legacy/canonical order keys into the
existing request before clearing pending. Migration 0025 checks unknown customer
identity in retained canonical facts even when no 59-day raw copy remains. Regression
coverage checks pending export rejection, verified backfill, repeated authenticated
replay, and exact legacy/canonical export counts for both history layouts. No B06
implementation or external provider action is included. Current-head Full/CI evidence
will be recorded in PR64; prior CI at `4885645` does not cover this follow-up.

## B06 — Editable Goals And Offline Interpretation

Owner approval at 2026-10-05 22:20:59 UTC extends the existing PR64 exception through
B06 only. Rechecked remote main (`ea3591c`) and PR branch (`f8b1c203`), clean and
unchanged from B05; PR64 remains an unmerged draft. Website, live providers, IAM,
credentials, advertising changes and CRM gateway configuration remain outside scope.

Implemented scoped customer goal APIs, immutable numbered definitions, exact preview/
revision confirmation and confirming customer/time. Historical baselines reference B05
snapshots without copied financial facts; stale/partial/changed/revoked/privacy-erased
sources cannot produce a valid confirmation. Future target windows remain separate
from completed baseline windows. Editing clears current confirmation. Monthly versus
cumulative dates, source/currency/timezone, deadline and budget period stay explicit.
Budget/aggressiveness are intent only and cannot authorize any advertising spend.

Added an injected offline interpreter interface and strict output schemas. The default
adapter asks for structured clarification rather than claiming natural-language
understanding. No provider SDK or network adapter was added. Durable zero-cost usage
reservations enforce workspace/global/day and user/hour limits across replicas, reject
duplicate calls and keep uncertain outcomes reserved. Manual editing works when
interpretation is unavailable, including retained goals for disconnected sources.
Database constraints reject nonzero model spending. Migration 0026 adds only B06 tables
and seeds the offline global cap; generated unrelated schema differences were removed
before any migration was executed.

Acceptance covers CSRF/roles/revoked identity, source/preview isolation, immutable edits,
confirmation idempotency/concurrency, stale/future/changed/deleted baselines, strict
schema and unsupported output, global/workspace quota and duplicate reservation races,
uncertain/timeout handling, external/paid rejection and populated PostgreSQL migration.
Combined foundation/commerce run: 131 passed. Latest B06 tests and required Full/CI
results are recorded at the package head in PR64. Ruff and mypy (199 files) pass.
Contract and release limits: `docs/inlet-goals-contract.md`.

B06 is API/persistence plus offline acceptance, not a live model service or customer
portal and not a purchasable SaaS release. B07 mandate/action state is next, subject to
predecessor review/merge or a further explicit exception. Live model/data-processing/
cost approval, Shopify live reconciliation, deployment and CRM gateway architecture
remain separate unresolved gates. No such approval is inferred from B06 authorization.

### B06 Independent Review Repairs

Review of `9628c1fa` found two defects, reproduced on both SQLite and PostgreSQL:
a new idempotency key for an already confirmed preview overwrote the original
confirming customer/time, and the usage endpoint omitted prior-day outstanding
reservations while the interpreter correctly continued blocking them. The regression
run failed all four affected cases before correction.

Reconfirming the same preview now only records another replay receipt; the original
revision's customer/time remain immutable. PostgreSQL races cover different actors
using both shared and different request keys. Daily usage and all-age outstanding
counts are separate; reserved and uncertain requests remain visible across UTC-day
rollover and continue blocking unsafe retries. No reservations are reset/released by
this display correction. Required checks and exact-head CI evidence are recorded in
PR64. These are B06 acceptance repairs, not B07 implementation.

## B07 — Offline Mandates And Durable Actions

The owner extended authorization across the remaining offline MVP at 23:33:14 UTC
on 2026-10-05. Dependent draft PRs may precede predecessor merge; package-by-package
approval is no longer required. Main remains `ea3591c`; B01–B06 predecessor PR64
head `ff694f93e32b13f188b646cc3f2db0e854c36fcc` passed hosted CI run 37385671768
(806 passed, zero skipped). Its local Full passed (800 passed, six PowerShell skips).

B07 is on `codex/inlet-b07-mandates`, based on that verified predecessor. It adds
versioned fixed-period, single-currency simulation mandates, explicit owned account
scope, cumulative consumption/reservations/change/count caps, exact new campaign/
creative review, durable fenced claims, dispatch rechecks and uncertain-outcome
reconciliation. Customer APIs preserve current role/CSRF/workspace isolation. Pause,
revoke and cancellation do not claim to stop live ads or reverse spent money.
Migration 0027 adds only mandate/revision/action/audit tables. No live executor exists.

Focused SQLite/PostgreSQL coverage initially passed 16 tests; the final suite adds a
concurrent stop/dispatch test. Canonical action hashing prevents JSON key order from
bypassing draft deduplication. Ruff and mypy pass (205 files). Required Full and hosted
CI are pending at this entry; exact committed-head results will be recorded in the PR.
The CI pull-request base filter now includes dependent `codex/inlet-*` branches so
stacked draft PRs run the same checks; no checks or release restrictions are weakened.

Next: B08 customer Google OAuth/account selection and scoped backfill, with an
injected offline transport and live integration disabled. The remaining backlog follows
the audit dependency order. Website work remains owner-managed; pricing, live provider
setup/validation, deployment, pilot operations and the unanswered CRM gateway proposal
remain separate gates, not reasons to stop independent offline implementation.

## B08 — Google Customer Lifecycle Preparation

Branch `codex/inlet-b08-google-connection` stacks on B07 `7e31642` / draft PR66.
Added session-bound, single-use OAuth state, account selection limited to authorized
leaf-account metadata, context-bound encrypted grants, explicit customer/connection/
account jobs, reconnect generations and local disconnect revocation. Staged windows
publish atomically; recent seven-day coverage precedes bounded 90-day backfill. Analysis
completion has an independent durable outbox so its failure never repeats a good import.
Eight fixture tests passed on SQLite/PostgreSQL before final scheduler refinements;
final focused/Full/CI evidence is recorded at the package head in its PR. Migration0028
adds only Google customer authorization/connection/completion tables; unrelated generated
CRM drops and enum differences were removed before execution.

This is offline lifecycle preparation, not full B08 live acceptance: runtime transport
fails closed and provider runtime selection and live refresh/read reconciliation remain unimplemented.
A fixed token-exchange request and bounded SDK manager traversal/paging adapter are
tested with injected offline IO; nine focused tests pass. The operator collector is preserved. Customer UI
selection is B18; live grants, deployment and provider-account setup are separate gates.
See `inlet-google-connection-contract.md` for the exact boundary. Continue independent
backlog work and retain this gap in the launch checklist; do not call the product ready.

B07 local Full at `7e31642` passed: 818 tests, six PowerShell skips; migration round-trip,
Ruff, mypy and boundary gates pass. Hosted run37390420054 remains pending here.

## B09 — Bounded Google Search Action Preparation

Branch `codex/inlet-b09-google-actions` follows B08 `aa4dcff` / draft PR67. Added typed
current-resource state and budget/status/negative-keyword changes, server-derived
validate-only request previews and exact review for negative-keyword additions. The
concrete fixture executor uses B07 durable claims/dispatch/reconciliation, checks B08
connection generation and never retries uncertain submission. Matching resulting settings
retains modeled exposure until the mandate period closes. No migration or live writer.
The existing fail-closed live Google boundary remains unchanged.

Focused acceptance covers SQLite/PostgreSQL and runs alongside B07 races. Exact checks
and hosted CI results belong to the package PR. This is offline action preparation,
not B09 live verification. Campaign matrix approval, provider-specific bound validation
and real authorized read-back remain launch gates. Next independent package: B10 Meta
child metric/state detail and aggregation correctness, then TikTok and customer-data
adapters. `inlet-google-actions-contract.md` records the shared action boundary.

## B10 — Meta Child Detail And Common Metric Grains

Branch `codex/inlet-b10-meta-detail` follows B09 `36c0155` / draft PR68. Common metrics
now represent ad sets and ads with compound parent/platform constraints. Added current
ad/creative identity metadata, bounded Meta detail read collection, atomic publication
and customer-scoped reporting. Campaign totals remain authoritative; child grains are
compared, never summed into account spend. Historical creative attribution is marked
unavailable rather than inferred from today's creative assignment. Detail collection
is disabled by default and is not silently scheduled.

25 focused Meta/detail tests pass, including populated PostgreSQL migration0029,
parent-FK rejection, atomic failed imports, duplicate rows, cursor/partial failures,
customer scope and revocation. Ruff/mypy (219 files) and Full/CI results are recorded
at the final package head. Only documented child-metric/schema changes remain in the
migration; unrelated generated changes were removed before execution. No live calls.

B07 hosted CI37390420054 at7e31642 passed824 tests with zero skips and all gates. B08
local Full ataa4dcff passed827 tests with six PowerShell skips and all gates; hosted CI
is tracked in PR67. B09 checks continue independently on its immutable commit. Main
was rechecked and remains ea3591c. Next package: B11 TikTok using the common owned
account and ad-group/ad grain contracts. Live release/pilot gates remain open.

## B11 — TikTok And Shared Customer Source Lifecycle

Branch `codex/inlet-b11-tiktok` follows B10 `6f12be8` / draft PR69. Added bounded,
session-bound source authorization, encrypted owned grants, reconnect generations,
disconnect, staged atomic TikTok imports and scoped coverage-aware reporting. The wire
adapter uses injected fixture IO and fixed read endpoints. Runtime source transport is
unavailable. TikTok conversions/value stay unqualified for optimization; campaign and
child grains cannot multiply reported spend. B08's customer callback query logging is
also corrected and its relay shared with the source lifecycle.

17 focused tests pass; Ruff and mypy (231 files) pass. Full and exact-head hosted checks
are tracked in the package PR. Migration0030 is limited to customer-source tables and
blocks downgrade with existing TikTok accounts. See `inlet-source-contract.md` for
interfaces, preservation and remaining live/runtime acceptance. No provider calls,
credentials, website changes, merge, deployment or spend occurred.

Earlier package terminal evidence: B08 hosted CI37391397871 passed833 tests, zero skips,
all gates. B09 local Full passed837 tests with six PowerShell skips; hosted CI37391760028
passed843 tests with zero skips and all gates at36c0155 (PR68 updated). B10 local Full
passed845 tests with six PowerShell skips and all gates at6f12be8; hosted CI37392693269
is pending final account-isolation gate. Next: B12 read-only customer-data context using
these explicit source identities; canonical Shopify revenue must remain unduplicated.

## B12 — Initial Transient Customer Context Adapters

Branch `codex/inlet-b12-customer-context` follows B11 `5900e69` / draft PR70.
Prepared fixed read-request/projection adapters for Klaviyo profiles, HubSpot contact
lifecycle and Omnisend contact channel status, plus transient canonical-customer
enrichment. This is an initial B12 slice, not completed provider onboarding or full B12
acceptance. No new schema, contact history, revenue ingress, identity guesses or private
CRM gateway access. The concrete fixture mapping is intentionally unusable as live
identity proof. Runtime OAuth/refresh/provider mapping, scheduler/UI integration and
retained enrichment policy remain unfinished; see `inlet-customer-context-contract.md`.

Eight focused tests initially passed across SQLite/PostgreSQL. Expanded Shopify
regressions, Full and exact-head hosted evidence are recorded in the package PR. Ruff
and mypy (236 files) pass. The parser drops personal/custom/revenue fields and rejects
untrusted continuation URLs. Canonical joins recheck active ownership, current generation,
existing customer facts and privacy suppression. Partial/cyclic reads cannot publish
a partial result. Current source observations are not permission for targeting.

B10 hosted CI37392693269 completed successfully: 851 tests, zero skips, all gates;
PR69 has the terminal evidence. B11 Full/CI remain tracked in PR70. Next independent
offline package: B13 checkout/subscription webhook and entitlement preparation with
commercial configuration disabled pending owner pricing decisions. B12 live/retained
context gaps remain open rather than being represented as working connections.

## B13 — Initial Billing Lifecycle And Entitlement Preparation

Branch `codex/inlet-b13-billing` follows B12 `7495f68` / draft PR71. Prepared durable
checkout idempotency, owner/CSRF-protected checkout, signed minimal webhook receipts,
concurrent deduplication, canonical subscription-state reconciliation, stale-state
refresh and an explicit entitlement guard. Initial billing tests pass across SQLite
and PostgreSQL; exact final checks belong to the package PR. Pricing is unset and
runtime transport unavailable. No charge, payment account, credentials or live call.

This is an initial B13 slice, not completed purchasing/billing acceptance. See
`inlet-billing-contract.md` for current worker guard coverage and remaining legacy job,
portal/cancellation/replacement-subscription/runtime requirements. Migration0031 adds
only two billing tables and refuses downgrade with preserved billing references or
receipts; unrelated generated CRM drops/enum changes were removed before execution.

B11 terminal evidence at5900e69: local Full854 passed with six PowerShell skips;
hosted CI37394058700 passed860 tests with zero skips and all gates (PR70 updated).
B12 local main suite862 passed with six PowerShell skips; Full final gate and hosted
CI37394563656 remain tracked in PR71. Next independent package: B14 supplied media and
versioned customer review, using B07 immutable action/review boundaries. Outstanding
B12/B13 live and product acceptance remain explicit backlog items.

## Independent Review Repairs — Candidate Follow-up

Branch `codex/inlet-acceptance-followups` follows PR72 `4d1506a`. The review reproduced
rejected spend-observation rollback, Google payload/accounting binding and stale-session
reservation defects, documented-page size rejection, TikTok dispatch starvation, Klaviyo
suppression conflation and checkout expiry/replacement issues. Candidate repairs have
101 passing focused/regression tests; baseline reproduction produced19 failures/3 passes
before billing additions. Full/CI for the new repair head remain required. No B14 code
expansion occurred while these repairs were prioritized. See `inlet-review-repairs.md`.

`inlet-acceptance-matrix.md` identifies implemented surfaces, acceptance evidence, missing
code and live gates separately. Hosted CI tested synthetic merge commits, not literal
branch SHAs; fetched refs prove their trees equal the corresponding tested heads. PR66–72
descriptions now record this correction. B12 Full862+6/hosted868+0 and B13 Full876+6/hosted
882+0 completed with all gates; these baseline passes do not resolve new review findings.
Next: verify repair package, complete actual provider transport/runtime code with mocked
HTTP/SDK tests and disabled defaults, then customer purchasing/onboarding and B14 onward.

## Provider runtime candidate (2026-10-06)

Started real Stripe HTTP adapter/runtime selection on `codex/inlet-provider-runtime`
from PR73. Disabled by default; no live calls. See `docs/inlet-billing-runtime.md`
for actual implementation and missing code. Mock HTTP suite: 16 passed. Combined
billing/review/initial HTTP tests with disposable PostgreSQL: 63 passed, no skips
(before three additional HTTP error cases, separately passed). Ruff, mypy and
`git diff --check` pass. Full validation has not run for this runtime candidate.
Not a completed B13 acceptance or live payment result.

### Customer scheduler runtime (2026-10-06)

- Branch `codex/inlet-scheduler-runtime`, based on PR79 Google lifecycle repair
  `24ad1ae86300a32f3f28b60e8402aeaacc471ccf` (itself based on PR75).
- Added explicit disabled-by-default shipped scheduler invocation of customer Google,
  TikTok, billing reconciliation, and lifecycle/entitlement-guarded analysis outbox.
- Added durable outbox retry timing and lifecycle fencing; see
  `docs/inlet-customer-scheduler.md` for configuration, locking and remaining work.
- Focused PostgreSQL + SQLite tests: **78 passed**, two existing Alembic configuration
  deprecation warnings, `/tmp/inlet-scheduler-final-focused.log`.
- Ruff passed; mypy passed across 253 source files; `git diff --check` passed.
- Disposable PostgreSQL migration upgrade through `20261006_0034` passed.
  Optional `alembic check` still reports pre-existing legacy CRM metadata removals
  and analysis VARCHAR/enum drift; no unrelated schema changes were applied.
- Full validation and hosted CI pending. No live provider calls, activation, merge
  or deployment. Independent portal migration0032 requires merge revision when combined.

#### Failed analysis retry completion

- Added coordinator-only opt-in retry of authoritatively FAILED local analysis runs,
  retaining source/account/window binding and the same run ID/key. Row locks prevent
  concurrent reclaim; ambiguous RUNNING and successful runs are not reclaimed.
- Preserved post-commit success when acknowledgement/refresh fails; retry cannot
  turn already-committed recommendations into duplicate work.
- Migration0035 stores total retries and the latest32 sanitized failed attempts.
- Expanded focused suite: **106 passed**, two existing Alembic deprecation warnings,
  `/tmp/inlet-scheduler-all-focused.log`; Ruff and mypy253 files passed.
- Disposable PostgreSQL upgrade plus0035→0034→0035 roundtrip passed.
- Full and hosted CI still pending for the final scheduler head. No external calls.
### TikTok Deleted History Review Repair (2026-10-06)

Dependent branch `codex/inlet-tiktok-history` from PR75 head01aa869 adds explicit
all-status inventory and dimension-specific report filters. Actual HTTP mock →
page staging → database publication tests reproduce the former deleted-history
loss, then verify retained spend across deletion, pagination and workspace isolation.
49 focused tests pass on SQLite/disposable PostgreSQL; Ruff/mypy/diff checks pass.
Full/CI pending. See `docs/inlet-tiktok-history-repair.md` for precise primary-source
verification limits and live qualification gate. No live calls, merge or deployment.

## CRM HTTP Runtime Preparation — 2026-10-06

Branch `codex/inlet-crm-runtime` from PR75 head
`01aa869b7df73bcdf1dca5fc25391a43f0af4efc`. Implemented disabled-default Klaviyo
PKCE/read/refresh/revoke and HubSpot OAuth v3/introspection/read/refresh HTTP paths.
Provider account identity precedes every profile page; no new profile persistence or
canonical matching shortcut. Explicit PKCE arguments and encrypted per-attempt state
survive replicas without mutable adapter context. Omnisend current contacts[] and
hasMore projection fixed against official docs; its factory remains blocked pending
verified brand-response identity and OAuth scope parameter. Detailed code/live gaps
and sources: `docs/inlet-crm-http-runtime.md`. Focused suite 85 passed with SQLite and
PostgreSQL; Ruff/mypy255/diff-check pass. Full/CI pending root review. No live calls.

### Source Status Follow-Up For TikTok Lifecycle

At the parallel TikTok lifecycle package's request, shared source views now provide
safe customer-facing status_label/next_action fields for provider_error and
reconnect_required. Provider rejection asks the owner to review provider access or
configuration and reconnect; it is not mislabeled as proved revocation. No tokens or
raw provider message is exposed. Other provider/status responses are unchanged.
Focused status test passed; Ruff/mypy256/diff-check passed. This small follow-up can
be cherry-picked independently of the CRM transport package.

### TikTok Lifecycle And Typed Provider Failures

Branch `codex/inlet-tiktok-lifecycle`, base PR80 head
`392d08672a718f1d6450441a6fa141943862abb9`: terminal HTTP authorization and local
expiry require reconnect; unknown valid numeric provider rejection pauses reads
with a distinct review label; transient failures preserve staging/backoff. Terminal
transitions fence generations and discard only scoped pending analysis, preserving
published data. Unused unqualified refresh material is no longer retained.
105 focused tests passed with disposable PostgreSQL enabled; Ruff, mypy253 and
diff-check passed. Full/hosted checks pending. See `inlet-tiktok-lifecycle.md` for
primary-source evidence limits and remaining advertiser renewal/revoke qualification.
No live API calls, activation, merge or deployment occurred.
## Customer Portal Preparation — 2026-10-06

Branch `codex/inlet-customer-portal`, base billing-management
`a8a35fccf871cf2870336a0850eebf58346df409`. Added separate `/app` customer shell,
functional workspace creation/selection, monthly goal save/edit/baseline review and
exact-revision confirmation, scoped status/mandate review, and owner test-billing
handoffs. Public website unchanged. Existing sessions required; no invented signup
or production purchase claim. Details, test evidence and explicit gaps are in
`docs/inlet-customer-portal.md`. Focused pytest: 6 passed (actual Chromium mocked-API
journey plus 5 Node contracts); Ruff/mypy253/diff-check pass. Root owns Full/CI.
Next: browser identity journey, connections setup, mandate lifecycle UI, readable
progress; provider/runtime preparation is still independent work.

### Customer Portal Readable Review Refinement

Merged billing-management `275e0ee179c2b6d84f1b2a14b3048b44b123c5ae`. Replaced
raw data panels with labeled goal/baseline/budget summaries, connection tables and
simulation mandate reviews. Baseline history/import warnings are human readable;
missing data is distinct from zero. Internal review IDs and revisions remain in
API requests only. Current sales progress is explicitly unavailable. Focused
pytest: 6 passed including Chromium readable-review assertions and six Node
contracts; Ruff/mypy253/diff-check pass. Full remains assigned to root.

### Portal CI Dependency Enforcement

Google Chrome binaries are now supported alongside Chromium. Hosted CI sets up
Node 22 and requires an installed compatible browser; missing dependencies fail
explicitly instead of skipping. Local missing-dependency skips remain documented.
Focused portal tests: 9 passed, including CI failure-policy tests and real local
Chromium execution. Ruff/mypy253/diff-check pass. No external provider access.

## Verified review repairs and runtime continuation (2026-10-06 01:36 UTC)

Main fetched again:ea3591c5086fbf2cee8038bf9208ac7f0050de75, unchanged.

- PR73 head7b7ab2963b79e23d99f945dc83624da6584cab93, basePR72
  (4d1506ac60f4f68556383c709755fc4d3067a0c4): Full exit0,914 passed+6 local
  PowerShell-only skips; all required gates passed. HostedCI37398286003 succeeded,
  920 passed/zero skips. Actual merge checkout73fa85711a7c98bef8c8362a3ace8c686063e532,
  treeeced2e4a3a064ccb3c13dcbe9c50661cca19ea4f equals head tree. Five original action
  safety findings plus source starvation/suppression/checkout repairs and second
  review retry sequences are regression-covered. See checkpoint file for mapping.
- PR76 actual Stripe HTTP runtime head7ff793fb62959a3818f25a9a07ee69979d407914,
  basePR73: Full exit0,932 passed+6 PowerShell-only skips; all required gates passed.
  Hosted CI pending. Original implementation694e338 remains in ancestry;7ff793f
  adds repaired base. Disabled default, test mode only; no live calls or charges.
- PR74 Google runtime headf92d0ab30707554b1b85c6798f2c70d4ab6a137a, basePR76:
  real REST exchange/refresh/paging plus90day delayed-conversion refresh.73 focused
  tests passed. Main Full suite956+6 passed; final gate/hostedCI pending at checkpoint.
- PR75 TikTok runtime head01aa869b7df73bcdf1dca5fc25391a43f0af4efc, basePR74:
  real HTTP exchange/advertiser/inventory/report reads,89 focusedtests passed.
  Full/CI pending. Conversion/revenue qualification and token lifecycle remain code.
- Billing management branch head275e0ee179c2b6d84f1b2a14b3048b44b123c5ae,
  basePR76: owner/CSRF management handoff and retired-subscription reconciliation;
  80 focusedtests passed. Main Full suite942+6 passed, final gate pending; noPR yet.
- Customer portal code8fa0714d9cb95b54749bb54ff62e19a2c286caf9 includes billing
  management. Workspace/monthly-goal review-confirm/status/test billing journeys;
  9 focused tests passed including Chromium, Node and CI dependency policy. Full
  not yet run. Signup, connection setup and mandate editing remain implementation.

No merge, deployment, live/provider calls, credentials, purchasing or advertising
changes occurred. All new transports default disabled. Real HTTP code is mock-tested,
not live-qualified. Upcoming packages:finish these validation runs and independent
review; provider token renewal/revocation, old unknown billing-attempt recovery,
Meta per-child performance and CRM actual transports, customer authentication/setup
journeys, then remaining reviewed campaign/creative/publication/operational backlog.
Prices/currency/catalog and live enablement remain owner decisions; no approvals
needed for continuing authorized offline engineering. Public webpage remains owner-managed.

## PR78 Review Repairs — Candidate

Branch `codex/inlet-portal-repairs` starts from PR78 head
`8b4b727c926b06baa1b68b2a3c40dcf144c55ff6`. See
[repair behavior and evidence](inlet-portal-review-repairs.md).
Customer DOM and memory are erased on session changes, logout, expired sessions
and workspace reload; stale asynchronous replies cannot restore prior data.
Goal creation now requires a customer/workspace-scoped, input-bound idempotency
key with atomic receipt/goal/revision persistence and concurrency protection.
The portal reuses uncertain save keys within the current session/workspace.
Cross-reload discovery remains via the goal list, not persisted browser payloads.
Focused checks: 54 passed (SQLite, PostgreSQL and Chromium), no skips; Ruff,
mypy (250 files), and diff whitespace check passed.
Full validation/CI pending; no live calls, purchase, merge or deployment.
### 2026-10-06 Billing Recovery Review Package

PR77-based `codex/inlet-billing-recovery` fixes the reproduced PostgreSQL replacement
checkout race and adds read-only reconciliation of expired uncertain Stripe attempts.
95 focused SQLite/PostgreSQL tests passed, one SQLite row-lock skip; Ruff/mypy249/
format/diff passed. Full/CI pending. See `inlet-billing-recovery.md` for exact scope,
primary contract references and legacy-key limitation. No live requests or activation.

Earlier runtime validation is now terminal: PR75 Full989+6 local PowerShell skips,
CI995; PR76 Full932+6, CI938; PR77 Full942+6, CI948; all gates passed. PR78 Full951+6
passed, CI still finishing. Known subsequent findings are tracked in PR79–84 and
this billing repair; these green baseline checks do not close newer findings.

#### PR83 TikTok outbox review repair

The provider-neutral completion table also receives TikTok jobs; the initial
coordinator incorrectly required a Google connection for every delivery. The
coordinator now branches on the persisted job platform and locks the matching
owned Google or TikTok connection. TikTok reconnect/disconnect atomically retires
only that source's pending jobs under the same workspace/connection locks.
Real fixture TikTok imports now complete local analysis exactly once. Tests cover
reconnect/disconnect stale selections, another tenant surviving retirement, and a
foreign workspace connection being unable to authorize an unbound source job.

Checks:67 focused SQLite/PostgreSQL tests passed (two existing Alembic warnings),
Ruff/mypy253 files/diffcheck passed. Log:/tmp/inlet-scheduler-tiktok-final.log.
The prior head96cca816 Full remains running in its untouched worktree; this repair
was made in isolated/workspace/inlet-scheduler-repair so old validation is not
silently attributed to the new code. Final-head Full/CI remain pending.
### Klaviyo Nullable Channel Regression — 2026-10-06

Isolated branch `codex/inlet-crm-nullable-fix` from PR82 head
`6080164d7f2ca66d0d8599ff9faa4346de64c425` preserves the ongoing Full run's tree.
The pinned 2026-07-15 schema permits null email/SMS subscription channels:
https://raw.githubusercontent.com/klaviyo/openapi/main/openapi/stable/apis/get_profiles.json
A mixed page with subscribed email and null SMS reproduced
`crm_profile_response_invalid` before the fix. Nullable channels now project unknown
consent and suppression, retaining valid neighboring channels and profiles. The HTTP
regression covers both channel directions, both null, nullable marketing and ordinary
subscribed/unsubscribed data. Focused CRM/context/status suite: 39 passed with disposable
PostgreSQL, no skips. Ruff, mypy and diff checks pass. Full validation at the parent
head remains separate evidence; this correction has not independently run Full or
called a live provider.

## Customer Browser Sign-In Package (2026-10-06)

Branch `codex/inlet-customer-signin` from integrated `8ae5ab798eadd8835749f9ed03844fcf8280c25f`.
Disabled-by-default Google browser signup/sign-in now exchanges a fresh provider identity
once into the existing revocable server session. Confirmed CSRF logout precedes account
switching; unknown exchange results clear customer DOM and require an explicit session
check. Firebase Auth 12.19.0 uses in-memory persistence and SDK cleanup in `finally`.
Self-hosted asset and exact dependency lock rebuild reproducibly; CI enforces the diff.
Enabled-only CSP contains fixed Google bootstrap/API origins and derived project iframe.

Focused validation: 53 pytest cases (SQLite, PostgreSQL and actual Chromium), including
8 Node subtests, plus Ruff, mypy (272 source files), whitespace checks and a clean npm-ci
rebuild with an identical asset SHA. No live provider calls, grants, merge or deployment.
Full remains queued with the integrating agent to avoid duplicating active validation.
See `docs/inlet-customer-signin.md` for boundaries and real-provider qualification gates.
### B19 Readiness HTTP Status Repair (2026-10-06)

Invalid startup configuration previously returned /ready HTTP200 withnot_ready.
It now returns503 and Cache-Control:no-store; valid startup configuration returns200,
while /health remains200 liveness.17 deployment/configuration tests passed, Ruff/mypy270
passed. This remains configuration readiness, not live DB/dependency health or a
restore/release qualification. See inlet-audit-status.md for B01–B20 status.
## Durable Klaviyo Page Pacing — 2026-10-06

Branch `codex/inlet-crm-pacing` from integration `8ae5ab7`. Added a real internal
one-page consumer and explicit receipt acknowledgement, preserving account proof on
every page and the canonical mapping gate. Durable global opaque quota coordinates
same-account/app connections across replicas; encrypted checkpoints retain cursors,
not profiles. Typed 429 responses persist Retry-After cooldown without sleeps or
revocation misclassification. No scheduler enrollment or live requests.

Focused SQLite/PostgreSQL CRM pacing/HTTP/context run: 57 passed, 1 intentional SQLite
skip for the real PostgreSQL concurrent-lock case (that PostgreSQL case passed).
Ruff, mypy app/tests (269 files), and diff checks passed. Disposable PostgreSQL
migration upgrade to0038, downgrade to0036, and re-upgrade passed. Full and hosted CI
for this new package remain pending. PR82 validation remains a separate unchanged
head. Remaining boundaries and official limits: `docs/inlet-crm-pacing.md`.

### CRM Pacing Lifecycle Review

Disconnect/reconnect now delete scoped checkpoint cursor/receipt material under the
existing source locks. In-flight completion cannot resurrect it. Bounded opportunistic
quota cleanup preserves active leases/cooldowns. Retry-After is measured from response
time and successful responses after lease expiry are rejected. Expanded CRM and
source-lifecycle suite: 73 passed, 1 intentional SQLite lock-case skip, 2 existing
Alembic configuration deprecation warnings; actual PostgreSQL replica cases pass.
Ruff/mypy269/diff-check pass. Migration unchanged from the tested roundtrip.
### B14 Campaign Review Core — 2026-10-06

Isolated `codex/inlet-campaign-review` from integration
`3417bc22d986aefc6abb08905dea89495b20ce53`; migration 0037 follows 0036. Added private
scoped immutable development JPEG/PNG storage (disabled default), typed campaign
revision/preview/exact approval APIs, current ownership/mandate/entitlement/generation
bindings, and explicit Meta generation on verified reauthorization. Edits append an
unapproved revision. Offline review approval is distinct from publication eligibility;
provider publication remains disabled. Core ports and remaining design copied to
`docs/inlet-campaign-review-contract.md`; implemented behavior and limitations in
`docs/inlet-campaign-review-core.md`.

Checks: 61 focused SQLite/PostgreSQL/mock tests passed, 1 intentional SQLite-only skip
for the PostgreSQL row-lock race; Ruff passed; mypy 276 files passed; diff check passed.
New disposable `inlet_b14_migration_ci`: upgrade head and 0037→0036→head passed.
Additional `alembic check` found existing CRM import/analysis enum drift, no B14 drift;
not claimed clean. Full and hosted CI pending. No provider calls or live verification.

Remaining: TikTok video validation, customer review UI, production private storage and
media lifecycle, B15/B16 compiler/publication/reconciliation and spend/freshness gates.
The first package does not claim all B14 acceptance criteria complete.
