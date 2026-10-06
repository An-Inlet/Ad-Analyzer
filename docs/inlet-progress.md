# Inlet Build Progress

Last updated: 2026-10-06. Product: **Inlet**. Company: **An Inlet**.

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
- The original single-dependent-PR policy is superseded for this offline assignment
  by the owner-approved exception in `docs/automation-policy.md`; merge and live
  release gates remain.

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

### Customer Shopify Connection API (2026-10-06)

Added disabled-by-default customer Shopify authorize/callback/list/disconnect routes,
revocable session and owner/admin CSRF checks, signed-query-preserving static relay,
and workspace/session/state transaction locks that serialize callbacks/disconnect.
The existing read-only Shopify client, verified shop/scope binding, canonical store
identity and privacy purge are reused. Operator callback configuration is unchanged.
Focused customer cases:18 passed,2 SQLite lock-test skips; combined Shopify/privacy
nonmigration regression suite:64 passed,2 skips,6 migration cases deselected because
starting integrationbasec86beb3 had two migrationheads. Ruff/mypy266files/diff passed.
Merge current integration's0036 before migration-wide checks. NoFull/providercalls,
credentials, merge-to-main or deployment. See docs/inlet-customer-shopify.md.
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
Customer Shopify follow-up: merged integration8ae5ab798eadd8835749f9ed03844fcf8280c25f,
resolving inherited migrationheads. Aligned legacy operator persistence and importer
workspace-before-connection locks with customer callbacks. Final combined customer
Shopify/legacy Shopify/privacy/integrated migration suite:73 passed,3 SQLite-only
lock-semantics skips; PostgreSQL concurrency and populated migration roundtrip pass.
Ruff, mypy268files and diff checks pass. Full and hosted CI remain pending.

PR87 cross-path review reproduced privacy-handler connection-before-workspace locking.
Fixed privacy owner fences plus nonce-before-store retention/uninstall cleanup; added
PostgreSQL callback-vs-uninstall and expiry-sweep tests. Preserved native importer
suspended-workspace status after original CI exposed regression. Expanded suite
including native ownership:85 passed,5 SQLite lock-only skips. Original CI37403352872
failed (importer status and nested browser20sdeadline); fresh head validation required.

B14 integrated validation: merged PR86 head
`ea4871b472c119dbe7e4a13d7958c315882eefd9` without conflicts, preserving migration0037
and both progress records. At code head `17b21cd32d4a079b121638a3934f1482e5ceff36`,
B14/Meta/customer journey/portal focused suite:72 passed,1 intentional SQLite race
skip; Ruff/mypy277 and wheel build passed. Draft PR91:
https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/91. Full/CI remain pending.

Predecessor validation: unchanged PR84 `68c9bc58f9d337296d1421e966f7867027239c36`
local Full finished exit0 (1,021 passed/6 unavailable-PowerShell skips; final automation
38 passed/6 same skips). Hosted CI37401780500/job112070362703 passed1,027 tests and
all gates; actual checkout3e700ed48e4b841d9fe2b493e3158c5cb2cb2ee2 tree equals head.
PR79 hosted CI37401087556/job112068198895 passed1,022 tests/all gates; actual checkout
040a5b424712203c90ea9e39b972445cb46ad42e tree equals head24ad1ae. PR79 local Full
was not run. Both PR bodies record terminal CI evidence; no live qualification.
PR87 login rotation follow-up: actual PostgreSQL concurrent email-refresh login and
customer callback reproduced DeadlockDetected at ef0aaab. Guard now locks User before
Session, matching login; callback observes rotated/revoked oldsession and performs no
Shopify exchange. Bounded review found logout Session-only and provisioning User then
fresh-workspace/replay-read compatible. CustomerShopify/identity/provisioning/native
ownership suite:75 passed,6 SQLite-only lock skips; Ruff/mypy268files/diffpass.
Prior ef0 Full/CI are superseded by this lock repair, not acceptance of repairedhead.

## Omnisend Runtime Contract And Adapter (2026-10-06)

Branch `codex/inlet-omnisend-runtime`, based on CRM pacing/lifecycle PR89 head
`e566a20502f178385a3f508f6c20278b7a900d80`. First-party Omnisend SDK commit
`fdfc72021e90d3fb333e7c1b2d77017dc69f850d` resolves the prior authorization and
current-brand contract blockers: singular `scope`, authenticated top-level `brandID`.
Actual disabled-default OAuth/code/refresh/brand/contact HTTP adapter now follows
those contracts. Repeated account proof blocks foreign brands; unknown expiry remains
unknown; null/missing channel context remains unknown; no profile PII is persisted.
No provider revocation endpoint was invented. Source ownership/encryption/generation
interfaces are reused, with no migration or live provider request.

Checks: combined Omnisend/CRM/context/pacing/source suite **110 passed, 1 intentional
SQLite row-lock skip**, with the PostgreSQL counterpart executed; two existing Alembic
configuration deprecation warnings. Final exact RFC3986 authorization encoding change:
**37 Omnisend tests passed**, including SQLite/PostgreSQL ownership flow. Ruff passed,
mypy passed (274 source files), git diff --check passed. Logs:
`/tmp/inlet-omnisend-final.log` and `/tmp/inlet-omnisend-encoding.log`.
Full intentionally queued with root; hosted CI pending draft PR creation. Remaining
CRM scheduling/automatic refresh, verified Shopify identity matching/retention and
live qualification are explicit in `docs/inlet-omnisend-runtime.md`.

### Publication coordinator foundation (offline fixture only)

Base:b3035a8e2df2d86fa38b91d5d717b76d71056aa5; branch codex/inlet-publication-core.
Implemented strict review_v2/plan/DAG/request/receipt contracts, registered fixture
compiler, current DB authority, one B07 simulation reservation, durable step fences,
immutable receipt/request history, uncertainty reconciliation, cancellation and
separate activation-review receipt. No production adapter or live activation exists.
See docs/inlet-publication-core.md for precise remaining code and boundaries.

Core checks:33 passed,1 SQLite skip for PostgreSQL-only concurrency; Ruff passed,
mypy289 files passed. Broader B14/B07/B09 regression suite:102 passed,2 SQLite
concurrency skips (both PostgreSQL cases passed), /tmp/inlet-publication-regression.log.
Migration0040 upgrade and0039→0040→0039→0040 roundtrip passed, recorded in
/tmp/inlet-publication-roundtrip.log. Full/CI pending.
## Combined Customer Foundation Candidate (2026-10-06)

Branch `codex/inlet-release-foundation`, based on frozen PR86 ea4871b, integrates
Shopify customer OAuth/session locks (PR87), readiness status (PR88), CRM pacing
(PR89), browser Google sign-in (PR90), offline media/review (PR91), real HTTPS
browser/API/DB tests (PR92), and verified Omnisend HTTP contracts (PR93).
Migration0039 merges0037/0038. Populated round trips verify existing rows survive
and new tables downgrade/recreate correctly.

Code head b3035a8: combined customer/sign-in/Shopify/review/CRM/Omnisend/migration/
ownership/commerce/readiness suite **214 passed, 8 intentional SQLite concurrency
skips**, PostgreSQL counterparts executed; 20 existing Alembic deprecation warnings.
Ruff and mypy287 passed; focused log `/tmp/inlet-release-focused.log`. A first
invocation named a nonexistent test file and exited4 without executing tests; the
corrected complete invocation produced the results above. Full/CI pending finalhead.

Predecessor final-head evidence: PR83 ad4e9f2 local Full1048passed6PowerShellskips,
CI1054passed0skips; PR84 68c9bc5 local Full1021passed6PowerShellskips, CI1027passed;
PR85 eefc7fe local Full957passed7skips, CI963passed1intentionalSQLite-onlyskip;
PR82 c2e09c1 local Full1020passed6PowerShellskips, CI1026passed. All listed Full
runs ended exit0 and all hosted gates succeeded with actual checkout trees equal
to their PR heads. These are offline results, not live qualification or deployment.

Next packages: paced CRM rotating-token renewal; actual customer Shopify browser
journey; publication coordinator with fixture-only authority. B07 simulation mandates
remain simulation and B14 review does not grant publication permission. No provider
mutations, live credentials, merge or deployment were performed.

## Customer Media And Review Authorization Races (2026-10-06)

Branch `codex/inlet-review-authorization`, based on PR94 5f9a0d0. A paused actual
ASGI upload reproduced successful200 after session revocation, membership removal
or provider suspension on both SQLite and PostgreSQL (six failing regressions).
PostgreSQL approval requests blocked behind the workspace lock also reproduced200
following committed session/membership revocation (two failing regressions).
Initial reproduction attempts had fixture/barrier mistakes, corrected before claiming
these results: missing synthetic workspace client_name, then a barrier that did not
recognize FOR NO KEY UPDATE. Corrected logs are `/tmp/inlet-review-auth-before-corrected.log`
and `/tmp/inlet-review-approval-before-corrected.log`.

Writes now recheck current workspace/user/session/membership and provider identity
under canonical workspace→user→session→membership locks before product locks. Upload
receives at most8MiB within30seconds before acquiring those locks; timeout408 leaves
no media row/object. Create/edit/approval use the same guard. Local revocations are
fenced through commit; remote provider revocation remains a point-in-time check.
Session expiry is checked again after membership/provider waits because time cannot
be fenced with row locks. Independent review confirmed lock-order compatibility and
identified that final expiry check, now covered by regression tests.

Combined authorization/media/Shopify/identity suite:108passed,9 SQLite-only concurrency
skips; PostgreSQL counterparts ran. Ruff and mypy288 passed. Final focused rerun:12passed,2 SQLite-only lock skips. HostedCI pending; no Full or live provider calls. No migration or deployment.
### B14 Rendered Review UI — 2026-10-06

Branch `codex/inlet-campaign-review-ui` from PR94
`5f9a0d0d4d1d016135c54d3360b16e0800b6f6b6` adds the actual rendered customer review
at `/app/campaign-review`, scoped recent-draft listing, exact-digest acknowledgment/
approval, supplied-copy editing into a new unapproved revision, and explicit media
and publication states. Static images must load successfully before approval; no
arbitrary URL fetch, provider publication, new migration or live call is introduced.

Focused review/UI/portal checks: 53 passed, 1 intentional SQLite race skip; Ruff,
mypy (288 files), and diff check passed. Real HTTPS Chromium/API journeys passed on
SQLite and PostgreSQL, including failed image reads, stale approval and revoked role.
See `docs/inlet-campaign-review-ui.md` for behavior and remaining gaps. Full/CI pending.
Next packages remain bounded video validation/private media lifecycle and concrete
PublishPlan ports before dependent B15/B16 provider publication adapters.

Review UI draft PR: https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/99.
Implementation and focused checks are at `b420478b5906e2183f1b36e8317506a239f9e119`;
the following documentation-only commit records this PR link.

### Shopify Portal Consent Navigation — 2026-10-06

`codex/inlet-shopify-consent-ui` starts from PR99 head
`292ac8d4cfa2d52b15d76d1dc8edce78b61f0c95` and includes PR95 browser coverage
`54587ec`. Owner/admin Shopify domain controls now navigate through consent and the
GET callback bridge, with verified workspace return, explicit scoped nonce cancellation,
and safe Back/retry/session-change handling. Existing callback ownership/HMAC/session
fences remain. No migration, scope expansion, provider calls, merge or deployment.

Checks: 37 passed, 6 intentional SQLite variants of PostgreSQL-only checks skipped;
Ruff, mypy (289 files), and diff check passed. Real Chromium/HTTPS/API/DB navigation
passed on SQLite and PostgreSQL; provider consent HTTP and token/metadata transport are
mocked. Full/CI pending. See `docs/inlet-shopify-consent-ui.md` for exact evidence and
remaining disconnect UI/live qualification gaps.

Consent-navigation draft PR: https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/104.
Implementation/checks are at `c6f32cfd11f56923ad34d0d0195d0493a1d7b4f5`; the following
documentation-only commit records the PR link. Shopify toolkit search could not fetch
its service; official Shopify OAuth documentation was verified through web retrieval.
Toolkit telemetry was disabled; no user prompt was sent to its telemetry service.
## Durable CRM Renewal Package (2026-10-06)

Branch `codex/inlet-crm-renewal` from PR93 head
`a64cc424d52bb9de18e63bb0c129a91611ae33aa`. Existing pacing now orchestrates all three
CRM adapters through committed token-issuance, encrypted-unverified-candidate and
separately paced account-proof phases. A proved renewal preserves generation and cursor;
a stale worker cannot replace reconnect state. Proof transient failures retry the pending
candidate, never the rotating token. Token issuance uncertainty fails closed to attention;
known invalid grants and terminal read authorization failures require reconnect. No schema
migration, live grant, automatic profile enrollment or provider revoke was introduced.

Checks: **148 passed, 3 SQLite-only concurrency skips**; corresponding PostgreSQL races
ran. Two existing Alembic warnings. Ruff, mypy (275 files), diff check passed.
Log `/tmp/inlet-renewal-final.log`. Full and hosted CI pending; root owns validation-slot
coordination. Detailed state, scopes, backoff and remaining work are recorded in
`docs/inlet-crm-renewal.md`.

### CRM Renewal Review Repairs (2026-10-06)

Branch `codex/inlet-crm-quota-race` starts from PR96 `501310829e3796598f374bcc4a68790ca3632d64`;
PR96 remains immutable. Reproduced lost Retry-After during concurrent reconnect:
a same-account peer incorrectly received a page at +126s despite a 3600s cooldown
(`/tmp/inlet-crm-quota-race-before.log`). Reproduced six mixed Omnisend known/unknown
identifier failures (`/tmp/inlet-omni-null-before.log`).

Repairs: persist account cooldown independently before stale connection acceptance;
retain successor leases; encrypt issuing-client/quota binding with pending renewal
candidates; preserve unknown typed email/SMS identifiers; honor bounded Omnisend
problem `retryAfter`; scope Omnisend quotas to brand across clients. All mocked and
disposable-database only. No migrations, credentials, provider calls, live grants,
merge or deployment. See `docs/inlet-crm-renewal.md` for first-party contracts and
mandatory quiescent upgrade/cooldown gate for legacy Omnisend quota namespaces.

Final frozen focused validation and draft PR evidence follow below. Full remains
coordinated by the integrating agent. Private Google Cloud Storage work is paused
behind these review repairs; untouched worktree `/workspace/inlet-gcs-media` starts
at `5f9a0d0` on `codex/inlet-gcs-media`.

Frozen validation: `pytest tests/test_crm_quota_lifecycle.py tests/test_crm_renewal.py
tests/test_crm_pacing.py tests/test_omnisend_http_runtime.py tests/test_crm_http_runtime.py
tests/test_customer_context.py` with disposable PostgreSQL enabled: **193 passed,
15 skipped**, 60.46s (`/tmp/inlet-crm-repair-frozen.log`). All skips are SQLite-only
row-lock/concurrency cases; PostgreSQL counterparts ran. Ruff passed; mypy passed
(272 source files); `git diff --check` passed. Hosted CI and local Full pending.
## B19 Database Dependency Readiness (2026-10-06)

Branch `codex/inlet-dependency-readiness`, based on PR94 5f9a0d0. A configured but
unreachable database now yields503/not_ready on /ready; invalid configuration skips
the connection entirely. A fresh NullPool read-only SELECT1 avoids waiting on the
application pool; connection and statement timeouts are independently limited to2s
and1s (not an absolute DNS/network wall-clock promise). Responses reveal no driver
errors, address or credentials. /health stays liveness, with no dependency probe.

Focused dependency/deployment/managed-configuration suite:23passed, including a real
connection to explicitly guarded disposable PostgreSQL and sanitized failure/resource
cleanup assertions. Ruff and mypy passed. Full/hostedCI pending. This does not prove
schema compatibility, live production health, capacity or release readiness.
## B19 Synthetic Restore Drill — 2026-10-06

Branch `codex/inlet-restore-drill` from frozen PR94 head `5f9a0d0`. Added a guarded
native PostgreSQL logical restore drill for a generated private schema containing two
synthetic workspaces and tenant/session/goal/provider metadata, never grants or real
customer data. Server/database identity is checked before schema mutation; arbitrary
archives/source schemas are unsupported. ACLs, constraints/indexes, sequence state and
all rows compare after restore; customer membership and provider FK isolation are
exercised. Temporary schema cleanup succeeds on invalid archive and restore failure.

Actual local PostgreSQL16.15 run: 82 tables,44 rows,two tenants restored; native archive
348330bytes. Focused suite19passed,5existingAlembicwarnings; Ruff/mypy284/diff-check pass.
No broad Full run, live backup configuration, intended-environment restore, PITR,
key/media recovery, or post-snapshot privacy/revocation reconciliation claimed.
Instructions and remaining operational qualification: `docs/inlet-restore-drill.md`.
### Publication base synchronization

Merged release-foundation5f9a0d0 into the publication branch, retaining both progress
ledger sections. Only the ledger conflicted. Superseded local Full session63859
was canceled (exit137), not passed; its wrapper and nested pytest/validation children
were stopped together. No replacement Full started pending root coordination.

## Provider Publication Shared Contracts — 2026-10-06

- Branch `codex/inlet-google-publication` from PR98 merge `bc3aadc`.
- Separate strict provider review/plan/request/receipt types and deterministic Google
  Search paused DAG compiler. Original fixture hashes and simulation mandate remain
  untouched. Real HTTP adapter and provider coordinator integration still pending.
- Focused contract tests: 10 passed; Ruff passed; mypy three changed files passed;
  `git diff --check` passed. No Full requested or started for this new branch.
- Current Google v25 primary API references pinned in `inlet-provider-publication.md`.
  No live provider calls or publication authorization.

## Actual Google Publication HTTP Adapter — 2026-10-06

- Added fixed-endpoint v25 Google executor with validate-only, one-shot typed
  mutations, exact readback and no-replay reconciliation. MockTransport graph tests
  use the actual serializer/client path; no fixture adapter substitution.
- Validation: provider/compiler/HTTP focused tests 27 passed; whole-tree Ruff passed;
  whole-tree mypy 298 source files passed. Full remains unrun pending coordinated
  validation. No migration or runtime activation in this package.
- Unacknowledged timeout stays unknown, preserving the coordinator's unresolved
  exposure requirement. Provider runtime factory stays unavailable. Production
  authority, qualification reads, persisted provider review/coordinator/UI, separate
  activation and settlement remain implementation work; B15 is not complete.
## PR98 CI Migration Checkpoint Repair — 2026-10-06

- CI37406849242/job112086207972 failed (3 failed, 1333 passed, 10 skipped): release
  migration tests incorrectly treated0039 as the permanent latest head; nested Full
  repeated the same two failures. No CI pass is claimed for that head.
- Release branch roundtrip now explicitly targets0039, while the graph test requires
  one current head descending through the exact0037/0038→0039 merge. This preserves
  populated checkpoint coverage as future migrations are added.
- Focused disposable PostgreSQL migration tests: 2 passed. Changed-file Ruff/mypy and
  diff check passed. No replacement local Full started; coordinated validation pending.
## B14 — Bounded Offline Video Validation (2026-10-06)

Branch: `codex/inlet-video-validation`, based on release foundation `5f9a0d0`.
Actual MP4/H.264 and optional AAC are fully decoded with bounded byte-only worker
processes. TikTok video drafts can be reviewed and approved offline; Meta remains
image-only. Provider publication remains disabled. Media max is 64 MiB, images
remain 8 MiB, and workspace library remains 128 MiB. No migration or provider calls.
See `docs/inlet-video-validation.md` for exact controls and qualification gaps.

Focused validation: 58 passed, one expected SQLite row-lock race skip; the same
race and review flows run against disposable PostgreSQL. Real FFmpeg/FFprobe 7.1.5
synthetic clips exercised valid silent/AAC videos, codecs, corruption/truncation,
dimensions, pixels, rate, duration, both MIME mismatches, decoder absence/startup,
output/time limits and process reaping. Ruff lint and strict mypy (290 files) pass.
Whole-repository Ruff formatting check reports 32 pre-existing unformatted files;
no unrelated formatting was changed. Root coordinates broad Full and CI evidence.

Remaining integration: combine the separately reviewed authorization fix with a
serial worker-thread upload service boundary (decoder can consume up to 44 seconds),
and add customer video playback preview. Deployment image, load/concurrency,
decoder isolation/patching, provider acceptance, and live behavior are unqualified.
No claim that resource limits constitute an OS sandbox.
## Provider Publication Shared Contracts — 2026-10-06

- Branch `codex/inlet-google-publication` from PR98 merge `bc3aadc`.
- Separate strict provider review/plan/request/receipt types and deterministic Google
  Search paused DAG compiler. Original fixture hashes and simulation mandate remain
  untouched. Real HTTP adapter and provider coordinator integration still pending.
- Focused contract tests: 10 passed; Ruff passed; mypy three changed files passed;
  `git diff --check` passed. No Full requested or started for this new branch.
- Current Google v25 primary API references pinned in `inlet-provider-publication.md`.
  No live provider calls or publication authorization.

## Actual Google Publication HTTP Adapter — 2026-10-06

- Added fixed-endpoint v25 Google executor with validate-only, one-shot typed
  mutations, exact readback and no-replay reconciliation. MockTransport graph tests
  use the actual serializer/client path; no fixture adapter substitution.
- Validation: provider/compiler/HTTP focused tests 27 passed; whole-tree Ruff passed;
  whole-tree mypy 298 source files passed. Full remains unrun pending coordinated
  validation. No migration or runtime activation in this package.
- Unacknowledged timeout stays unknown, preserving the coordinator's unresolved
  exposure requirement. Provider runtime factory stays unavailable. Production
  authority, qualification reads, persisted provider review/coordinator/UI, separate
  activation and settlement remain implementation work; B15 is not complete.

### B15–B20 Acceptance Evidence Matrix (2026-10-06)

Documentation-only branch `codex/inlet-acceptance-matrix` starts from frozen PR94
`5f9a0d0d4d1d016135c54d3360b16e0800b6f6b6`. Added
[retained audit criteria and detailed engineering decomposition](inlet-b15-b20-acceptance.md)
with exact candidate heads for PR95/97–100. Inspected relevant implementation,
publication adapter proposal, real-browser harness and restore/learning tests.
Distinguishes missing code from provider/operations qualification and owner decisions;
credits neither fixture publication nor browser-origin API helpers as completed core
customer journeys. Existing legacy learning remains recognized as reusable work.

No application code, schema or settings changed. Validation is Markdown structure,
local referenced-path inspection and `git diff --check`; no pytest/Full rerun or new
provider call. Quoted acceptance wording comes from the integrating agent's retained
Library audit read; original attachment bytes were not materialized here. Next: finish
shared provider publication contracts/actual adapters and core task UI, then stable
B17 evidence contracts and final integrated operational/pilot acceptance.


Acceptance-matrix refresh before integration freeze: PR101 `8835340`, PR102
`2508a75`, PR103 `d4c78c5`, PR104 `fa70d8b`, PR107 `a6de6e9`, PR108 `e4c1392`
and PR109 `e12f11b` are now recorded with exact full heads and focused counts in
`inlet-b15-b20-acceptance.md`. Shopify consent navigation and the concrete Google
compiler/HTTP adapter receive implementation credit; durable qualified publication
coordination/activation, storage deletion, video UI and intended-environment evidence
remain open. No new Full or provider call; documentation checks only.

## Reviewed Foundation Integration Candidate (2026-10-06)

Branch `codex/inlet-reviewed-foundation` preserves frozen PR94 and combines PR95–109
where dependencies apply: CRM renewal and all reviewed repairs, Meta lock ordering
and resumable detail imports, exact campaign-review UI, actual Shopify consent
navigation, private GCS storage, bounded video validation, database readiness,
synthetic restore drill, durable publication core, actual typed Google HTTP adapter,
authorization fencing, and the remaining B15–B20 acceptance matrix.

Migration0042 explicitly joins0040/0041. Populated0039→0042→0039→0042 verifies old
rows, new publication/Meta checkpoint records and compound ownership constraints.
Upload now receives a bounded body, then executes authorization, decoder/storage and
response serialization serially on one worker thread; a focused responsiveness test
checks the event loop advances while the service is blocked. GCS imports use a
precise untyped-SDK import boundary rather than suppressing repository type checks.

Combined focused validation:309 passed,23 skipped,13 existing Alembic warnings.
Twenty skips are SQLite-only concurrency/constraint cases whose PostgreSQL variants
ran; three restore cases lacked explicit local container selection. The restore suite was then rerun with the guarded PostgreSQL container:19 passed,
no skips (five existing Alembic warnings). Ruff and mypy317 passed. Full and
hosted CI must run on the final committed head; no production acceptance is inferred.

Prior frozen PR94 is now terminal: local Full main1297 passed,15 skips (nine SQLite
concurrency plus six unavailable PowerShell), final automation38 passed/six PowerShell
skips; all gates passed. Hosted CI37405580011/job112082298281 passed1303/nine SQLite
skips. Actual checkoutd0fcf31c7b1565671028242e20c3a13edb2d53ea tree
46bfb87a1e5eb3090ccb10d12ee21db42f3ea872 equals5f9a0d0. Session handles were lost at
environment restart; preserved processes finished and logs contain terminal gates.

No live provider requests, credentials, spend, merge to main or deployment occurred.
Provider qualification/review persistence, full provider coordination/activation,
Meta/TikTok adapters, measured feedback, customer lifecycle and release/pilots remain
active backlog, with code gaps distinguished from external qualification.

### Publication commit-gap and absent-readback repair — 2026-10-06

Parent review identified two coordinator races in PR112 `3a3cca8`. A controlled
PostgreSQL barrier after the mandate dispatch commit reproduced cancellation
returning successfully while the worker still created the first fixture resource.
The pause/revoke variants already rejected correctly; all three remain regressions.
The worker now rechecks plan/action cancellation, dispatch state, exact request,
approving owner and mandate preconditions under reacquired locks before claiming a
step. The previously committed reservation remains held; this repair does not invent
settlement or change already-submitted receipt reconciliation.

A synchronized delayed original worker also reproduced a replacement claim from an
empty fixture readback. Absence is now `unknown`, never authoritative no-effect;
the original fence stays current and its eventual receipt remains reconcilable.
A crashed/unsubmitted worker cannot be automatically retried without additional
terminal/no-effect evidence. No provider capability or production authority is
inferred from the offline fixture.

Validation: initial corrected commit-gap harness 1 failed / 2 passed / 3 SQLite
concurrency skips; adding delayed-worker regression produced 3 failed / 2 passed / 3 skips
(SQLite and PostgreSQL both reproduced absent-readback retry). Repair combined suite
38 passed / 4 SQLite concurrency skips. Final race/storage suite 40 passed / 3
SQLite concurrency skips. Ruff and mypy (318 files) passed. Removed an obsolete GCS
test import suppression exposed by clean mypy after integration. Full/hosted CI must
run against the assembled successor; none is claimed by these focused results.


### Reviewed foundation validation successor — 2026-10-06

PR112 predecessor `3a3cca8` completed local Full with exit 1: 1,572 passed,
35 skipped and 2 failures. The failures were the obsolete Meta first-connection
Barrier(2) and the nested Full that encountered it. Hosted run 37408397594 failed
before tests because FFmpeg was absent. Neither is reported as successful validation.

The successor installs FFmpeg before retaining required tool checks. The Meta
regression now holds the winning transaction, observes the losing PostgreSQL backend
blocked by the winner with pg_blocking_pids, then releases it. It asserts exactly one
connection/account/integration, the safe existing-account conflict, and the losing
actor's pending grant. Focused first-connection/review-lock checks: 4 passed, 2 SQLite
lock skips. Publication commit-gap and absent-readback repairs are included from
PR113 `7ae1d0d`. Full and hosted CI are being rerun against this assembled successor;
results must be attributed to its exact head, not the predecessor.

Successor combined focused verification: 9 passed, 5 SQLite concurrency skips;
PostgreSQL cases ran. Whole-tree Ruff, mypy (318 files) and diff check passed before
freezing the successor for Full/CI.

## Customer Connections: Shopify Disconnect And Google Account Selection

Branch `codex/inlet-customer-connections`, based on PR104 head
`fa70d8b5aa7d3f14c08a83cc622ba53409279591`. Shopify now has an explicit data-effects
confirmation and disconnect control, tested against real API/database deletion and
retained goal history. Google now has a configured consent button, same-window GET
callback bridge, authorized non-manager selection and verified workspace return.
Current session/role guards also run after provider exchange and before selection;
retry is limited to current session/workspace attempts. No provider calls, advertising
changes, activation, migration, merge or deployment occurred.

Focused SQLite/PostgreSQL/API/Chromium checks: **56 passed, 6 intentional SQLite
concurrency skips**. Node helpers **8 passed**; Ruff/mypy **290 files** and diff checks
pass. Full/CI pending. Details, exact command and remaining engineering/live gates are
in `docs/inlet-customer-connections-ui.md`. Google disconnect and other provider
connection controls remain separate customer-facing engineering work.

Connections UI draft PR: https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/111.
Implementation/checks at `b4f886f0a2f8aa6db2d1e6606cb142f5a0ba29f5`; the following
commit only records this PR link. Final Google browser rerun also passed both database
variants (**2 passed**) after the restored-page restart safeguard. Full/CI pending.
### B18 Visible Test Billing Journey (2026-10-06)

Branch `codex/inlet-billing-browser`, isolated from frozen PR112 `3a3cca8`, adds safe
server billing availability/status flags, owned-workspace return URLs, visible
checkout/resume/status refresh/management and post-provider owner/session rechecks.
Actual Chromium/API/DB journeys on SQLite/PostgreSQL use the real Stripe HTTP adapter
with mocked provider responses and intercepted provider navigation. No real charges,
price decisions, credentials, live requests, migration, merge or deployment.

A delayed management response plus workspace switch reproduced controls permanently
disabled by overlapping portal guards; a shared busy counter/original-state map now
restores controls only once all tasks settle, with epoch/no-navigation coverage.
Final focused billing/portal/Shopify/browser checks: **78 passed, 1 SQLite-only skip**;
PostgreSQL counterpart ran. Whole-tree Ruff/diff checks pass; targeted strict mypy
passes 220 files. Whole-tree mypy has only the inherited GCS unused-ignore already
fixed independently by root PR113 `7ae1d0d`; left untouched here. Full not started.
See [billing journey evidence and limits](inlet-billing-browser.md) and
`/tmp/inlet-billing-browser-final.log`. Next: final integration validation and remaining
core-task/account controls; live purchasing stays a separate commercial/release gate.
## B14 — Customer Draft Creation And Private Video Playback (2026-10-06)

Branch `codex/inlet-draft-ui`, isolated child of PR112 `3a3cca8`. Narrow CI prerequisite
`98e2b0e` installs FFmpeg before retained decoder checks; root integrated that commit
separately. No changes were made to the frozen Full worktree.

Customer campaign review now creates all three supported offline draft types from
existing simulation mandates, uploads supplied media through the authorized API,
reuses private validated media, and plays bounded private MP4 blobs. Saving never
approves; playback failures block approval. Object URLs and form state are cleared
on workspace/revision changes. See `docs/inlet-campaign-creation-ui.md`.

Focused validation: 71 passed, one expected SQLite concurrency skip with PostgreSQL
variant passing. Includes real HTTPS browser journey on both databases, actual
synthetic MP4 upload/decode, Google/Meta/TikTok creation, exact revision approval,
role/stale failures and media bounds. Ruff passes; scoped mypy passes. Whole mypy
on the frozen parent reports its known unused GCS test ignore, already repaired by
root on the next integration head. Broad Full and hosted CI remain root-owned.
### Import-order-independent migration regression — 2026-10-06

The missing-application-tables validation test depended on whatever ORM models
pytest collection had imported. A focused invocation reproduced PostgreSQL
DependentObjectsStillExist: web_analytics_events still referenced ad_groups, absent
from the partial drop graph. The test now reflects the actual migration-created
schema and drops its application tables in dependency order while retaining
alembic_version. The existing guarded disposable-database validation remains first;
no production reset behavior or validation gate is relaxed.

Exact isolated regression before: 1 failed. After: 1 passed, running real PostgreSQL
upgrade/downgrade/recreate. Whole-tree Ruff, mypy318 and diff check passed. Full and
hosted successor results remain separate and must be recorded after assembly.

### Customer journey integration — 2026-10-06

Child of PR112 `73725be`, preserving its active validation head. Combines PR111
`960de15` connection consent/account selection/Shopify disconnect, PR114 `f151a80`
visible test checkout/recovery/management, and PR116 `d217dba` supplied draft creation,
private media upload and decoded video preview. Shared customer mutation locking
converges on the same workspace/user/session/membership guard, with the stronger
provider-aware wrapper retaining issuer, remote-active and post-wait expiry checks.
The combined portal preserves both Google setup state and overlapping-task control
restoration. No automatic campaign approval or live purchase/publication is enabled.

Combined billing/connections/Shopify/authorization tests: 70 passed, 8 SQLite lock
skips, PostgreSQL counterparts ran. Combined creation/review/video/threadpool/auth
checks: 34 passed, 2 SQLite lock skips. Node portal suite: 9 passed. Ruff, mypy321
and diff check passed. Initial test command used an incorrect connection-browser
filename and collected no tests; the corrected command produced the 70-pass result.
The independently reproduced migration reflection repair `1624b18` is included.
Full/hosted CI are separate pending gates at the final integration head. Google
 disconnect follow-up and closure/lifecycle packages remain separate candidates.
PR112 `73725be` local Full60224 terminated exit1: **1,578 passed, 38 skipped,
1 failed**. Its nested Full failed the missing-application-tables test because the
focused gate's partial ORM registry omitted publication dependencies on
mandate_actions. The isolated reproduction omitted measurement dependencies on
ad_groups; both demonstrate the same import-dependent drop graph. Reflection repair
`1624b18` preserves the test's missing-table/rebuild behavior and Alembic stamp.
Hosted37409558917 remains in progress at this record; its outcome is not inferred
from the local run. A fresh local Full will validate the repaired head separately.

### Shared ORM metadata bootstrap — 2026-10-06

Added one explicit model-module registry used by Alembic, web startup, scheduler
runtime loading, CRM worker startup and pytest bootstrap. Registration declares
metadata only and performs no database connection, schema mutation or provider IO.
A coverage test requires every domain models.py module to be registered, including
future lifecycle/provider modules when integrated. Cross-domain foreign-key checks
cover the publication and measurement dependencies behind the earlier partial-registry
failures. The migration reflection repair remains: the actual migrated schema is
still authoritative when intentionally removing application tables on a guarded
 disposable database.

Checks: 11 focused tests passed, including the real PostgreSQL missing-table/rebuild
regression and CRM push tests. Ruff, mypy321 and diff check passed. This package is
separate from frozen PR112/PR118 validation; Full/CI evidence remains pending.
## B14 — FFmpeg 6.1 Progress Clock Compatibility (2026-10-06)

Isolated branch `codex/inlet-video-clock-fix`, parent `73725be`; frozen integration
Full worktrees were not edited. Hosted Ubuntu's FFmpeg 6.1.1-3ubuntu5 reports the
final frame start for silent MP4 null-muxer progress, while local 7.1.5 reports its
end. Reproduced using identical real synthetic bytes in a disposable Ubuntu 24.04
container. Recognize only the exact decoded final-frame timestamp within one
microsecond for silent media; full frame-count/duration/decode checks remain.

Actual FFmpeg 6.1 matrix: 10 cases passed, including valid silent/AAC and malformed
codec/size/rate/duration/corrupt/truncated rejections. Logs:
`/tmp/inlet-video61-before.log`, `/tmp/inlet-video61-after.log`,
`/tmp/inlet-video61-matrix.log`. Application focused checks and full static results
are recorded in the branch/PR handoff. No broader Full rerun is started here.
### B19 Application Authentication For CRM Push — 2026-10-06

Branch `codex/inlet-worker-auth`, isolated from PR112 frozen `73725be8c3ce8165d236f998cc850b41cea1f10c`.
Added disabled-default expected push audience/service account configuration and a
router dependency using actual Google signature verification. Customer/operator/IAP
identities cannot substitute for worker identity. Strict bounded single-header JWT
parsing, exact verified email/time/audience checks and bounded fixed certificate
transport fail closed without exposing claims. Terraform requires an explicit
nonsecret audience input before release and retains the existing subscription
worker-URI audience without a resource self-reference.

Focused worker/ingress/IAP/API/Terraform tests: **102 passed, zero skipped**, including
SQLite and PostgreSQL customer-login denial and actual Google verifier tests with
in-memory synthetic signing material/mocked HTTP. Whole-tree Ruff, mypy (316 files)
and diff check passed. No Full, deployment, credentials, live provider requests or
real push/IAM qualification. Terraform CLI unavailable; static tests do not establish
plan/apply readiness. See `docs/inlet-worker-push-auth.md` for the compatibility gate,
protocol source and remaining intended-environment verification.

Draft review: https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/119. Implementation
commit `2e34c92d607538b740a12c5a5a793040a9fe1e15`; subsequent ledger-only commit
records the assigned PR. Next gate is assembled exact-head Full/CI, followed by
explicit release configuration and intended-environment push verification.

## Google Disconnect Customer Controls

Branch `codex/inlet-google-disconnect` is an isolated child of frozen PR111 head
`960de15cee97de54b88e3cb2bc33e59217c60915`. Owners/admins now select a connected Google
account and acknowledge concrete data/advertising effects before disconnecting. Current
session and role are revalidated transactionally. Imports stop and the local grant is
removed; historical metrics remain and Google campaigns/spending are unchanged.

Verification: focused SQLite/PostgreSQL/API/Chromium **55 passed**; final Google API
regression rerun **17 passed**; Node helpers **8 passed**; Ruff, mypy **290 files** and
diff checks pass. Browser verification includes retained imported metrics, removed
local authorization, blocked role loss and an untouched sibling connection. No live
provider operations, migrations, merge or deployment. Full/CI pending.

Next recommended package is TikTok customer consent/selection/disconnect, after freezing
shared source post-exchange guard and retry/lock interfaces with CRM ownership. Remaining
source/Meta UI gaps and concrete ports are documented in `docs/inlet-google-disconnect-ui.md`.

Google disconnect draft PR: https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/120.
Tested implementation: `7571ed2052f475b9235de6d94d09453b31921b2e`; the following commit
only records this PR link. Parent subsequently selected Meta customer connections as
the next isolated interface proposal, before TikTok/CRM implementation.
## Shared Meta/TikTok Publication Types — 2026-10-06

- Isolated `codex/inlet-social-contracts` from PR108 e4c1392. Additive social contracts
  leave existing Google and fixture schemas/hashes unchanged. Frozen typed operations,
  media binding, resource-kind namespaces, review/plan/request/receipt and transport ports.
- Contract/compiler/Google adapter focused regression: 41 passed. Whole-tree Ruff
  passed; mypy passed (300 source files). No Full started; adapters remain dependent work.
- No live factory or production permission. Unknown provider combination eligibility
  remains explicit qualification work, and B16 is not complete.
## B17 — First Pure Outcome-Evidence Consumer (2026-10-06)

Isolated branch `codex/inlet-outcome-evidence`, based on reviewed foundation
`73725be`. Implements frozen nested consumer inputs, deterministic canonical
hashing/comparison, strict scope/metric/window/coverage/maturity gates, observational
deltas only, and no percentage from zero/negative baselines. Invalidated or unknown
privacy and foreign scopes redact values. Actual existing CommerceSnapshot rows
project to conservative store-total context, explicitly missing historical manifest,
source generation and refund maturity qualification.

There are no routes, DB writes/migrations, scheduler methods, provider requests,
production receipt adapters or new retention. Scheduler confirmed its normalized
production projection is forthcoming; committed shared types are required before
integration. This first module is not B17 completion or a fixture replacement for
real lineage. Concrete next producer contract and proposal are under `docs/design`.

Validation includes pure deterministic scope/maturity/currency/attribution/DST/
correction/privacy cases and actual persisted commerce snapshots plus disconnect
invalidation on SQLite and isolated disposable PostgreSQL: **31 passed**. Ruff,
strict mypy (324 files), and diff checks passed. The earlier broad commerce subset
also exposed the known predecessor reflection test failure, already separately
repaired by root at `f698dea`; frozen root worktrees were not changed.


## Meta Customer Consent, Selection And Disconnect

Branch `codex/inlet-meta-customer-ui`, isolated child of PR118 `216fda2` plus PR120
`a4a66d5`, implements customer Meta consent/GET callback/account pagination/conversion
choice/scoped selection and disconnect. Migration0045 down0042 adds explicit flow
phase and pending-grant nonce binding. Default customer setup is disabled. Current
session/role/flow/generation are rechecked after provider IO; stale callbacks cannot
overwrite completed retries. Operator signatures and nullable legacy grants remain
compatible, while customer routes reject unbound grants.

Checks: focused **57 passed, 2 intentional SQLite concurrency skips**; final customer
API **22 passed**; Node **10 passed**; Ruff/mypy **325 files**/diff pass. Disposable PG
migration upgrade/down0042/up0045 passed. Optional whole-schema Alembic check found
unrelated CRM metadata and analysis enum differences (parent integrating separate
registry repair), not a0045 mismatch. Full/CI pending. No live provider traffic,
activation, advertising operations, merge or deployment. Evidence and remaining
engineering/live gates: `docs/inlet-meta-customer-ui.md`; shared interface proposal:
`docs/inlet-meta-customer-contract.md`.

Meta customer controls draft PR: https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/125.
Implementation and checks: `aa05f66acf5b70c00e43389f874ac1ab669828c7`; the following
commit only records this PR link. Frozen PR118/PR120 heads were preserved.

### Billing Browser Startup Race Repair — 2026-10-06

Isolated branch `codex/inlet-billing-browser-repair` from PR118 `216fda2` preserves
the frozen validation head. Its Full failed in nested validation while waiting for
the workspace options after the billing test's initial login. The test waited only
for the Retry DOM node, then clicked while the initial session probe could still
hold that control disabled. Chromium silently ignores a disabled button's click.

A test-only ASGI wrapper now deliberately holds the initial unauthenticated session
GET through successful login. Before the repair this reproduced the exact original
workspace-options timeout: **1 failed**. The repaired harness releases the probe,
waits for Retry's handler and enabled state, then clicks exactly once. The forced
overlap remains in both SQLite and PostgreSQL journeys. Product logic, assertions,
wait deadlines and provider boundaries are unchanged; no blind retries were added.

Final billing-browser/API/recovery/portal checks: **54 passed, 1 SQLite-only lock skip**;
PostgreSQL counterpart ran. Whole-tree Ruff, mypy (317 files) and diff check passed.
The earlier isolated case, prefix-order subset and full-collection selection passed
without the forced overlap, so they did not establish a fix. No successful Full is
claimed for this repair; the assembled successor needs exact-head Full/CI.

## Google Qualification And Immutable Provider Review — 2026-10-06

- Isolated `codex/inlet-provider-review` from PR108e4c1392, with actual merge of core
  migration-test repairb8afc00. Migration0043 follows0040; root reserves later merge
  with0042. Separate provider qualification/review/approval tables and scoped FKs.
- Actual read qualifier, DB-derived prepare/recheck, exact review+plan approval and
  renderable documents implemented. Network reads happen outside locks; current
  source/owner/entitlement/generation are rechecked before immutable persistence.
- Focused qualification/compiler/HTTP checks: 53 passed, 1 SQLite-only FK skip;
  includes PostgreSQL populated0040→0043→0040→0043 roundtrip and reconnect-during-read
  rejection. Whole-tree Ruff/mypy302 and diff check passed. No new Full started.
- Explicitly missing next code: production mandate consent/authority, durable provider
  claim/receipt projection, exact activation and uncertainty-aware settlement. Existing
  simulation approval never supplies production authority. No live operations enabled.

## Shared Meta/TikTok Publication Types — 2026-10-06

- Isolated `codex/inlet-social-contracts` from PR108 e4c1392. Additive social contracts
  leave existing Google and fixture schemas/hashes unchanged. Frozen typed operations,
  media binding, resource-kind namespaces, review/plan/request/receipt and transport ports.
- Contract/compiler/Google adapter focused regression: 41 passed. Whole-tree Ruff
  passed; mypy passed (300 source files). No Full started; adapters remain dependent work.
- No live factory or production permission. Unknown provider combination eligibility
  remains explicit qualification work, and B16 is not complete.
## PR121 Qualification Expiry After Lock Wait — 2026-10-06

- Isolated repair `codex/inlet-review-clock` from frozen PR121 `46c7adf`; predecessor
  head preserved. Prepare and approval now sample their injected clock after blocking
  lifecycle/review reads and immediately before persistence. Approval timestamps use
  the fresh decision time. Checked-review and approval APIs require clock callables.
- Six real PostgreSQL barriers cover prepare/approve while workspace, mandate, or
  native connection locks cross qualification expiry. All reject expired artifacts;
  a controlled stale-entry-clock mutation made all six fail, then was removed.
- Focused qualification/compiler/HTTP suite: **61 passed, 7 SQLite-only skips**.
  Includes six PostgreSQL barriers and populated migration roundtrip. Whole-tree
  Ruff and mypy (298 files), plus diff check, passed. No new Full run.
- No live provider access or production authority enabled. Production coordinator,
  activation, and durable settlement remain the next package on a separate branch.

## Provider Execution Consent And Ledger Foundation — 2026-10-06

- Branch `codex/inlet-publication-execution` merges actual social adapters PR117 and
  review-clock repair PR127, preserving ancestor commits. Shared optimization and
  normalized receipt contracts frozen at17aefff for dependent adapters/evaluator.
- Separate production-consent service now checks exact policy revision/digest and
  current goal/owner/entitlement/account/native generation. Immutable environment and
  shared exact period ledger prevent revision/new-consent accounting resets.
- Migration0046 follows0043, adding12 scoped audit tables for consent, exact review,
  exposure, run/step/original attempt, response, receipt and supersession lineage.
  Held budget-owner uniqueness spans periods within the same environment/workspace.
- This is a foundation checkpoint. Durable claims, exposure qualification, actual
  adapter orchestration, separate activation, settlement and receipt projection query
  remain implementation work. No live gate, provider access, merge or deployment.
- Checks: 59 focused tests passed,7 SQLite-only skips; includes shared policy/receipt
  contracts, consent isolation/accounting, cross-period held-owner uniqueness,
  six PostgreSQL review-expiry lock barriers and populated0043↔0046 roundtrip.
  Whole-tree Ruff and mypy311, plus diff check, passed. No Full run started.
## Integrated Candidate — 2026-10-06

Branch `codex/inlet-mvp-candidate` assembles the reviewed foundation, customer
journeys, canonical ORM registration, video decoder compatibility, worker push
authentication, Google disconnect, local closure quiescing, social adapters,
measurement comparison, customer Meta connections, billing browser regression,
and provider qualification with fresh post-lock expiry checks. Migration 0047
joins provider review, lifecycle, and Meta customer schema histories. Registry
coverage discovers every direct declarative Base subclass, including provider_models.

Checks actually run on this assembly: Ruff passed; whole mypy passed (359 files);
focused SQLite/PostgreSQL/customer browser/video suite **87 passed, 7 SQLite-only
skips**; portal Node tests **10 passed**; PostgreSQL migration upgrade to0047,
downgrade tobase, and upgrade to0047 passed. Logs are executor-local
`/tmp/inlet-candidate-focused.log`, `/tmp/inlet-candidate-node.log`, and
`/tmp/inlet-candidate-migration.log`. Full and hosted candidate checks remain pending.

Predecessor112 f698dea Full failed (1578 passed,38 skipped,1 nested failure),
with a Shopify browser initial-session readiness race. Its hosted run37410847813
failed four tests (1581 passed,32 skipped), three decoder cases plus nestedFull;
actual checkout bcc4c6fba40d0160aea59255c77e52feecc2950e has the same tree asf698dea.
Predecessor118216fda2 Full failed the nested billing readiness test (1597 passed,
38 skipped,1 failure); hosted37410393272 failed seven (1597 passed,32 skipped):
video/review upload cases, nestedFull, and a Google DevTools target startup race.
Actual checkout33568e75e68d8408c167cfadb83f785934f87a58 matches216fda2's tree.
The decoder and billing fixes are integrated; further browser startup repairs
remain separate reviewable packages until qualified. These failures are not green
release evidence. Production execution coordinator, complete export/closure,
measured action outcomes, live provider qualification, operations and pilots
remain incomplete. No merge, deployment, provider mutation or spend occurred.
### Shopify And Google Browser Startup Synchronization — 2026-10-06

Branch `codex/inlet-shopify-browser-repair` is an isolated child of billing repair
PR126 `fa31c11`. The frozen PR112 Full nested Shopify SQLite journey failed at its
initial workspace-options wait. A test-only ASGI wrapper holding the first session
GET through login reproduced that precise failure: **1 failed**. The copied Google
journey independently reproduced the same dropped Retry click under the same
controlled overlap: **1 failed, 1 deselected**.

Both tests now release the initial probe, wait for the bound and enabled Retry
control, then click once. The forced startup overlap remains in SQLite/PostgreSQL
journeys, and cleanup always releases the probe. No product behavior, deadlines,
acceptance assertions or provider boundaries changed. This is separate from the
browser target-discovery repair coordinated in another branch.

Final combined Shopify consent/customer API, Google connection, billing browser and
portal suite: **39 passed, 6 SQLite-only lock skips**; PostgreSQL counterparts ran.
Whole-tree Ruff, mypy (317 source files) and diff check passed. No Full or hosted CI
success claimed. Frozen parent heads remain unchanged; the assembled successor
requires exact-head validation with both synchronization and target-discovery fixes.

## B18 — Customer Closure Confirmation And Recoverable Status (2026-10-06)

Isolated branch `codex/inlet-closure-ui` combines PR122 `9088dbd` and required PR118
`216fda2`. Added a Settings link, separate closure shell/module and dedicated receipt
route. Named workspace confirmation binds the exact revision/inventory digest;
status stays owner-authorized after the workspace disappears from active choices.
Truthful local effects, retained data, unverified work and unchanged external
advertising/billing are explicit. Global session and other workspaces survive
closure; explicit logout clears data and revokes the session normally.

Focused parent/API/browser suites: 54 passed and one expected SQLite race skip,
with PostgreSQL race coverage. Added Node receipt/version/path contract checks and
reran actual HTTPS browser recovery after the final guard changes. Ruff and strict
mypy (334 files) passed. No backend/schema edits beyond composing the inherited
Google lock-order conflict; no production closure, data erasure or provider call.
See `docs/inlet-closure-ui.md`. Export implementation remains separate.
## Hosted Browser Target Discovery Repair

Independent child of frozen PR125 `512cadc`: `codex/inlet-browser-target-repair`.
Fetched hosted PR118 workflow run37410393272/job112097300707 logs through the GitHub
connector. The Google SQLite failure was `IndexError` at
`GoogleBrowser(tabs()[0]["webSocketDebuggerUrl"], origin)` before application navigation:
DevToolsActivePort existed, but Chromium's `/json` response was still empty.

Shared bounded `wait_for_page_target` now waits for a page with a usable WebSocket URL,
ignores workers/incomplete targets and supports exact IDs for second-tab creation.
Google/Shopify/Meta/billing harnesses use it; no production code or assertion weakening.
Deterministic regressions reproduce the original empty-response indexing failure and
cover delayed readiness, transient connection failure, exact target selection and timeout.

Initial affected-browser run: **10 passed, 1 failed**. The failure was the distinct billing
PostgreSQL initial-login/Retry workspace-options timeout, not target discovery. Parent
and the session-harness repair owner were notified; that unrelated failure is not hidden.
The deterministic helper rerun passed **3 tests**. Ruff/mypy **327 files** and diff checks
pass. Parent owns Full; frozen PR118/PR125 were preserved. No live requests.

Focused discovery + Google/Shopify/Meta Chromium journeys on SQLite/PostgreSQL:
**9 passed** (`tests/test_browser_targets.py`, `tests/test_google_connections_browser.py`,
`tests/test_shopify_consent_browser.py`, `tests/test_meta_customer_browser.py`). The
billing startup failure remains reported separately for its dedicated repair.

### Integrated Lifecycle Registry Repair And Browser Qualification

Independent review found the newly registered provider qualification/review/approval
models absent from the lifecycle table allowlist. The first combined browser run
reproduced broken closure on both SQLite and PostgreSQL: 2 failed,13 passed
(`/tmp/inlet-candidate-browser.log`). Added explicit workspace-scoped protected
scalar projections for those tables; raw evidence/review/plan JSON stays omitted.
A canonical-registry regression prevents this integration omission recurring.

After repair, the lifecycle/model registry plus closure/Google/Shopify/Meta/billing
browser and target-discovery suite passed **36 tests with one SQLite-only row-lock
skip**; its PostgreSQL counterpart ran. Ruff, whole mypy (362 files), and diff
checks passed. Exact log: `/tmp/inlet-candidate-lifecycle-browser.log`. This also
qualifies the combined PR126/128 session-readiness and PR131 target-discovery
repairs without timing retries or weakened product assertions. See the current
`docs/inlet-candidate-acceptance.md`; the new frozen Full/CI remains pending.

### B19 Packaged Schema Revision Readiness

A reachable database previously satisfied readiness regardless of its migration
revision. The successor candidate now requires its recorded Alembic heads to match
the heads packaged with the running artifact. Missing, older, unknown or extra
heads return503 while liveness remains200. `database_available` remains separate
from the additive `schema_revision_current` field. Read-only probes use fresh
connections and existing connection/statement/lock limits; no migrations are run.
This checks revision compatibility, not arbitrary schema drift, capacity or provider
availability. The deployment image already packages the migrations directory.

Focused readiness/deployment suite:21passed including actual disposable PostgreSQL
missing/current/older/extra revision cases. Ruff, whole mypy362files and diffchecks
passed. The frozen1300cf6706 Full/CI does not cover this successor change.
## Retained Meta Account Ownership Race

Independent child `codex/inlet-meta-ownership-repair` of frozen PR125 `512cadc` closes
confirmed customer selection TOCTOU. Existing active MetaConnection uniqueness was
insufficient after another workspace connected then disconnected during provider IO:
the retained AdvertisingAccount remained. Repeat post-IO ownership validation plus
Meta-only database uniqueness now enforces the existing ownership policy across writers.
Migration0049 down0045 refuses legacy duplicates without rewriting or deleting data.

Checks: ownership/customer/operator **49 passed, 1 SQLite concurrency skip**;
ownership/import/workspace **48 passed, 1 SQLite concurrency skip**; populated SQLite/PG
migration roundtrips and conflict refusal included. Actual two-writer PG test asserts
the named partial-index conflict and rollback, not only a query recheck. Ruff/mypy
**326 files**/diff pass. Full/CI pending. No live provider/customer data access,
advertising actions, merge or deployment. See `docs/inlet-meta-ownership-repair.md`.

Retained Meta ownership draft PR: https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/133.
Tested implementation: `d6a98b54aebed24416700638a675700a7d765e43`; final ownership-only
rerun **7 passed, 1 intentional SQLite concurrency skip**. Following commit only records
this PR link. Parent will join migration0049 with the next unfrozen candidate.
### B19 Assembled Route Boundary Matrix — 2026-10-06

Branch `codex/inlet-route-boundaries`, isolated from frozen PR130
`0cf6706ca9e12e8ccdba77f10c2247fd976e3593`. Inventoried all 79 protected method/path
combinations in the assembled app: 41 operator API, 37 dashboard and one worker.
The exact inventory is `docs/inlet-route-boundaries.md`. Tests enumerate effective
FastAPI lazy include contexts, including hidden routes, and fail on unclassified
routes/mounts. Public shells/callback documents/status/docs/assets and independently
signed webhook ingress are explicit exceptions; remaining customer routes require
the existing customer dependency.

A customer signs in using the actual session API on SQLite and PostgreSQL. Each
protected route is then exercised under configured/missing production and local
HTTP development settings, with a forbidden database dependency proving rejection
before handlers. Local HTTP explicitly receives real session/CSRF cookies on a
loopback peer, so omission of Secure cookies cannot explain denial. Customer sessions
remain valid afterward. No missing runtime guard was found, so this package changes
only tests/documentation and adds no duplicate controls or deployment permissions.

Validation: combined assembled-boundary/IAP/operator API/Google push/ingress tests
**90 passed, zero skipped**. Whole-tree Ruff, mypy (359 source files) and diff check
passed. No Full, live calls, IAM/configuration changes or deployment qualification.
Exact assembled successor validation remains required.

### B19 Persisted Operator Attention Evidence — 2026-10-06

Branch `codex/inlet-operations-attention` from root-next `f77553b` adds
`GET /api/v1/operations/attention` to the existing operator bearer router. Its
versioned aggregate contract uses fixed codes/severity/actions and timestamps,
without identifiers, raw errors, provider payloads or mixed-currency totals. It
observes latest sampled job failures/stale execution, overdue billing reconciliation,
connection attention, and unknown publication/action outcomes including closing
workspaces. Future backoff remains expected until 15 minutes past due. Reservation
state is never released, and no provider/storage operation or alert is emitted.

Nine bounded SELECTs each evaluate at most 500 scalar rows, with a sentinel for
explicit truncation/lower-bound counts. PostgreSQL applies a two-second
transaction-local statement timeout. Database failures stay sanitized 503 rather
than reporting no attention. Storage, heartbeat, never-started work, local analysis
history, independent publication-step age and external alert delivery gaps remain
explicit. This is not deployed monitoring or a complete health assertion.

Final operations/boundary/existing API suite: **54 passed, zero skipped**, including
SQLite and PostgreSQL. Tests verify recovery, backoff thresholds, sanitized terminal
uncertainty, reservation preservation after closure, query/result bounds, database
failure sanitization, no-store responses and actual customer-session denial. Whole-tree
Ruff, mypy (363 files) and diff check passed. Updated runbook and exact route inventory
(now 80 protected method/path pairs). No Full, schema change, live calls, IAM or alert
provisioning. External destination/escalation and deployment qualification remain gates.
## B17 Commerce Publication Package (2026-10-06)

Isolated branch `codex/inlet-commerce-evidence` from frozen PR130 `0cf6706`;0051down0047. Implemented terminal-only aggregate commerce publications, source generation/privacy epoch, workspace-first read/import/privacy locking, per-workspace retention transactions, owned no-store GETs, and explicit lifecycle scalar classification. Closure retains history; source privacy still deletes; comparison maturity remains unavailable. No outcome tables or production receipt adapter yet.

Checks: focused suite124 passed2 expected SQLite race skips (`/tmp/inlet-commerce-evidence-focused.log`); final publication/migration subset14 passed1 expected SQLite lock skip (`/tmp/inlet-commerce-publications-final.log`); Ruff, mypy365, diff check pass. Disposable PG populated migration roundtrip passed. No Full/live calls. Export global revision0053/helper owned by portal_repairs is a pending integration dependency; commerce helper alone is not a global privacy guarantee. Next: wire approved global revision bump after that concrete head, then owned receipt adapter only when scheduler read boundary is frozen. See `docs/inlet-commerce-publications.md`.

B17 export-fence followup: shared0053 model/helper cherry-picked from portal_repairs24fe23b (export-only serializer absent on this base omitted). Commerce invalidate now atomically bumps `Workspace.export_privacy_revision`; focused erasure/rebind/disconnect/retention assertions15 passed1 SQLite skip; combined0051+0053 populated roundtrip1 passed; Ruff/mypy367 pass. Archive capture/delivery and other-source invalidation are export-package work. PR136 https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/136 remains draft; root owns migration merge and Full qualification.
## Durable Real-Adapter Creation And Evidence Checkpoint — 2026-10-06

- Isolated child `codex/inlet-provider-coordinator` preserves frozen PR132. Actual
  merge of reviewed foundation1300cf6706 at88c8ba4; reserved0048 joins0046/0047.
- Canonical model registry and all12 protected lifecycle classifications added.
  Closure revokes production consent and cancels future runs, preserving original
  attempts, late readback, financial exposure and blockers; no classification bypass.
- Implemented exact production creation approval, parent reservation with postcommit
  cancellation/authority recheck, durable one-emission marker, real adapter dispatch,
  acknowledgement archive, same-attempt receipt supersession and owned latest projection.
- Focused coordinator/registry/lifecycle suite:29 passed,1 SQLite concurrency skip.
  Final closure-after-receipt adjustment:2 passed. Prior broader lifecycle/quiescing
  suite38 passed,1 skip. Whole Ruff/mypy368 and diff check passed; no Full started.
- Actual Google MockTransport journey covers the entire persisted creation DAG,
  duplicate emission prevention, uncertain result/late acknowledgement reconciliation,
  absent readback remaining unknown, cancellation in the parent-commit gap, concurrent
  claims, current ownership/generation/master/ledger changes, future/foreign receipt
  rejection, conflicting identity and late evidence after workspace closure.
- Missing code: production portfolio/cap/reporting-delay qualification, activation,
  authoritative settlement and integrated social journeys. Shared readers currently
  admit explicit contract-test scenarios only in tests; runtime remains unavailable.

### Successor Integration: Commerce, Operations, And Durable Creation

Successor `codex/inlet-mvp-next` preserves frozen130 while integrating retained Meta
ownership enforcement, schema-revision readiness, actual terminal commerce
publications/privacy epochs, operator attention and durable provider creation.
Combined commerce/operations/lifecycle/route-readiness checks:72passed,2SQLite-only
skips (`/tmp/inlet-next-commerce-ops.log`); Ruff/mypy372passed at that assembly.

The actual coordinator integrates separate production consent, immutable period
ledger, durable original-attempt dispatch and real Google HTTP MockTransport
receipts. Production exposure qualification, activation/settlement and full social
journeys remain open engineering work. The first combined coordinator/lifecycle/
operations run had78passed,2SQLite-only skips,1migration-fixture failure: current
Workspace ORM tried to insert the new privacy column into predecessor0043.
The fixture now seeds with the current ORM at head, downgrades to the real predecessor
with populated retained customer data, then upgrades to head and exercises the
populated0046 downgrade/re-upgrade. Its focused regression passed (1test), without
changing production migrations or weakening retained-user/empty-ledger assertions.
Ruff/whole mypy382passed. Exact logs: `/tmp/inlet-next-coordinator.log` and
`/tmp/inlet-next-coordinator-migration.log`.

Merge0054 joins Meta ownership and commerce/global privacy histories;0056 then joins
provider execution0048. New tables remain explicitly classified in lifecycle
inventory. No successor Full is claimed; frozen130 evidence remains separate.
### B18 TikTok Customer Consent, Selection And Local Disconnect — 2026-10-06

Branch `codex/inlet-tiktok-customer-ui`, isolated from `f77553b`. Customers can
start configured TikTok consent, return through a dedicated auth_code-only GET
bridge, select an authorized advertiser and disconnect locally with explicit data
consequences. Runtime remains disabled by default. No migration or provider writes.

Shared optional GuardedSourceExchange checks the current actor and exact exchanging
nonce after each TikTok HTTP request and releases locks before the next. Retry
replaces only the same session/workspace/provider pending flow. Late exchanges
cannot replace newer attempts; failed exchanges require a fresh start. Existing
CRM PKCE signatures remain intact. Callback authorization codes are stripped from
history and not retained in browser storage; installed access-log filtering
suppresses auth_code callback requests. Disconnect retains reporting/goal history
and sibling grants, clears local grant/staging/scheduling and advances generation.

Checks: shared source/CRM/TikTok batch **178 passed, 14 existing SQLite concurrency
skips**; TikTok browser/customer API/source/status/portal batch **34 passed**; final
auth_code logging/customer API plus adjacent Google/Meta browser batch **19 passed**.
Actual HTTPS browser journeys run against both SQLite and PostgreSQL with mocked
provider HTTP only. Node helpers **11 passed**; Ruff, mypy app tests (**362 files**) and
diff check pass. Full/hosted CI/integration and live provider qualification remain
pending. CRM customer setup UI remains an engineering followup. See
`docs/inlet-tiktok-customer-ui.md` for the frozen interface and limitations.

TikTok journey draft PR: https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/139.
Tested implementation: `bb27c674159ad94dc6e20d86a920291fa3ea2f1a`.
Following commit only records this PR link; Full remains pending.

### Durable Provider Coordinator Attention — 2026-10-06

Isolated `codex/inlet-provider-attention` from integrated `caff2a3` (single migration
head 0056) extends PR137's legacy attention evidence to actual provider coordinator
records. Held exposure is summarized separately by contract-test/live environment;
held alone is not an incident. Current scalar step states surface unknown/conflict,
verified-no-effect review and overdue dispatch/emission, including canceled runs and
closing workspaces. Ledger-end warnings never authorize settlement/replay. No JSON
receipt guessing, amount totals, mutation or provider calls are introduced.

Eleven fixed bounded reads retain caps, lower-bound flags and PostgreSQL timeout.
Actual mocked Google receipt tests verify unknown → success → later unknown for the
same original attempt, cancellation/closure preservation, exact dispatch-age bounds,
separate environments, period-end warnings and capped counts. Final operations,
provider-attention, boundary and existing API suite: **66 passed, zero skipped**.
Whole-tree Ruff, mypy (379 files), and diff check passed. No migration changes, Full,
live grants or external alert delivery. Frozen PR137 remains unchanged.
### Hosted Billing Failure Diagnostics — 2026-10-06

Isolated `codex/inlet-billing-ci-repair` from frozen PR130 `0cf6706` investigates
hosted run 37412515307, job 112103881519. The nested Full summary lists billing
SQLite as failed, but its actual traceback was lost: the parent retained only the
last 8,000 stdout characters, occupied by later video failures. There were no
configured diagnostic artifacts. No billing root cause or successful repair is
claimed from this incomplete evidence. Exact isolated billing SQLite/PostgreSQL
rerun passed both cases.

Nested Full now writes a separate local JUnit report for each of its two runs and
uses short tracebacks. Failure reporting preserves bounded per-case evidence for
up to eight failed/error cases, including each case name, message and final failing
trace, followed by bounded tool stdout/stderr tails. Missing/malformed/oversized
reports retain tool-failure diagnostics. Nonzero exit still fails immediately;
success still requires both complete validations. No assertion, timeout or retry
behavior in the billing journey was changed. No external artifact retention was
provisioned or represented as available.

Focused billing plus diagnostic/CI-contract checks: **9 passed, zero skipped**.
Whole-tree Ruff, mypy (360 files), and diff check passed. Diagnostic tests reproduce
an early billing failure hidden by verbose later output and prove it survives the
new report. No new Full was run. The unresolved billing case needs the next exact
assembled Full/CI run with preserved evidence; root owns separate video failures.
## Hosted Browser Codec Qualification Repair (2026-10-06)

Isolated `codex/inlet-video-playback-ci` from frozen1300cf6706; B17 work preserved uncommitted in `/workspace/inlet-owned-outcomes`. Exact hosted job112103881519 chose stock Chromium154.0.8037.0 and failed real MP4 first-frame assertions; FFmpeg6.1 server tests passed. Added early real H264/AAC blob decode qualification and shared `INLET_TEST_BROWSER` selection, plus bounded failure diagnostics. No weaker assertions or longer timeouts. Exact snapshot download blocked HTTP403; original MediaError remains a hosted evidence gap, explicitly documented.

Matching Ubuntu24.04/FFmpeg6.1/GoogleChrome154 actual silent+AAC decode passes; real HTTPS bothDB browser+portal suite14pass; Ruff/mypy362 and standalone probe mypy pass. See `docs/inlet-browser-media-ci.md`. Parent owns integration and Full/hosted qualification. B17 resumes afterward on its separate worktree.

### Successor Playback And Analysis Closure Integration

Integrated PR146 codec-qualified browser selection at28089c7. Actual customer portal, campaign review and billing browser tests completed successfully (16 tests); whole mypy402 and Ruff passed. Log: /tmp/inlet-next-playback-billing-corrected.log. An earlier invocation named a nonexistent billing test file and ran no tests; it is not evidence. Hosted billing root cause remains unresolved; bounded nested diagnostics will retain future per-case failures.

Integrated PR147 analysis closure admission/persistence fencing. Combined analysis, cadence and customer quiescing checks:45 passed,1 SQLite-only lock-contention skip; whole mypy404 and Ruff passed. Log:/tmp/inlet-next-analysis-closure-corrected.log. An earlier invocation used nonexistent test filenames and ran no tests. This repairs the demonstrated local analysis race without asserting all workers physically drained. No live execution or deployment.

Owner clarified conditional global stop: a verified GitHub plan/usage/resource limit that blocks work requires immediate idleness on all projects until explicit user resumption. All six workers notified. No verified limit observed at this checkpoint.

### Frozen PR130 Terminal Local Full

The unchanged0cf6706 artifact completed local Full with exit0. Initial pytest1813 passed46 skipped; final account-isolation/automation gate38 passed6 PowerShell skips in1014.99s. All intervening lint, types, PostgreSQL, migrations, read-only, security and privacy gates passed. Exact log:/tmp/inlet-mvp-candidate-full.log and its .exitcode file. Hosted37412515307 remains failed; no substitution of local evidence for hosted qualification.

PR146 hosted run37415266510/job112112374138 failed early at real browser codec preflight: installed Google Chrome154.0.8037.57 and Chromium154.0.8037.0 both returned browser_no_result. No plan/quota error was reported. Agent investigating launch diagnostics; no weakened assertions or blind timeout extension authorized.

### Exact Activation Adapter Integration

Integrated PR145 d2c0487, including shared activation contracts and actual Google/Meta/TikTok status-only adapters. Original creation identity, request/readback digest and reviewed paused state remain bound; no budget or creative edits, inferred effect time, retry or automatic activation authority. Coordinator integration and exposure/settlement remain unfinished. Combined activation/publication/optimization HTTP checks:103 passed in2.27s; Ruff and configured mypy410 passed. Log:/tmp/inlet-next-activation-adapters.log. No live requests or extra hosted Full started.

### Resumption And Import Closure Integration

Owner resumed normal Inlet work while leaving the exact blocked workflow dispatch paused. Read-only diagnosis: shell proxy CONNECT to api.github.com returns403 Forbidden before any GitHub API response; existing Actions metadata remains readable through connected GitHub tools. This is not evidence of GitHub quota exhaustion; no credentials/settings changed and no dispatch bypass attempted. Actual verified plan/usage limit still requires all-project stop.

Integrated PR1495cec843 workspace-first Google/CRM import locking. Combined import closure/ownership/customer quiescing checks47 passed,2 SQLite-only concurrency skips; Ruff and configured mypy411 passed. /tmp/inlet-next-import-fence-corrected.log. Initial mistyped test filename ran no tests and is not evidence. This removes demonstrated lock inversion; does not establish physical worker termination.

### Durable Activation Integration

Integrated PR148dd71cdd: separate exact review/approval, original durable activation attempts, full original graph revalidation, retained parent reservation and owned receipt supersession. Combined activation/coordinator/export-domain/model-registry checks48 passed1 SQLite-only concurrency skip; Ruff and configured mypy415 passed. /tmp/inlet-next-durable-activation.log. Production live exposure and authoritative settlement sources remain missing; strict activation export serializer coverage remains a separate integration requirement.

Broader closure worker testing subsequently reproduced a self-deadlock introduced by147: customer_runtime._analyze holds workspace authority in one Session while run_post_sync_analysis opens another and waits for that lock. Repair is in progress; no integrated Full claimed for this successor. Focused47 closure/import tests did not cover that scheduler path.

### B18 CRM Customer Consent, Selection And Disconnect — 2026-10-06

Branch `codex/inlet-crm-customer-ui`, isolated from `915fbcc10151e56f7b28d2a1ae5f643c99503007`.
Klaviyo, HubSpot and Omnisend now have configured customer consent controls, a
code-only same-origin GET bridge, explicit authenticated-account confirmation and
local disconnect with data-effect acknowledgement. Missing configuration is shown
truthfully; provider enablement is independent and the export feature gate does
not hide connection availability. Shopify remains the financial source; authorization
does not qualify identity mapping, retained enrichment or targeting permission.

Optional guarded PKCE exchange extends Klaviyo without changing existing source
interfaces; HubSpot/Omnisend reuse guarded exchange. Each token/account HTTP boundary
rechecks current actor, session, role, nonce and phase before another request or
persistence. No shared adapter guard state. Fresh Klaviyo retry context remains
encrypted; stale exchanges cannot replace it. Callback query stripping, CSP,
no-referrer/no-store and actual access-log suppression cover all three providers.

Validation: combined CRM/browser/renewal/quota/status/portal **219 passed, 14 existing
SQLite concurrency skips**; expanded browser/sibling/status **10 passed**; final
callback/API plus adjacent TikTok/Google/Meta browser **51 passed**. Six CRM journeys
exercise actual local HTTPS/API/database on SQLite and PostgreSQL with mocked
provider HTTP, including real PKCE challenge matching. Meta's adjacent test now
waits for enabled disconnect controls, fixing a reproduced premature test click.
JavaScript helpers **14 passed**; Ruff, mypy app/tests (**400 files**) and diff pass.

No migration, private gateway, persistent enrichment, provider setup/live calls,
spending, merge or deployment. Full/hosted CI and successor integration remain
pending. Private gateway ownership architecture and persistent context policy are
separate owner decisions; live provider qualification/mapping remains unverified.
See `docs/inlet-crm-customer-ui.md` for contracts and evidence.

### CRM Customer Journey Integration

Integrated PR150ae5ffb2: Klaviyo/HubSpot/Omnisend consent, account confirmation and local disconnect, guarded exchanges and server-only Klaviyo PKCE. Combined actual CRM HTTPS browsers, customer APIs/status and adjacent Meta browser checks57 passed; portal JavaScript14 passed; Ruff and configured mypy passed. Logs:/tmp/inlet-next-crm-journeys.log and /tmp/inlet-next-crm-node.log. No private gateway/persistent enrichment or live grant added.
## B18 Customer Activity And Support (Successor Of cd10222)

Added a bounded, authenticated customer activity read and `/app/activity` view.
Goal/campaign summaries come from actual persisted revision timestamps; owner-only
provider outcomes reuse validated latest receipt projection. No provider payloads,
IDs, invented events or support destinations. Existing connection/billing and
closure/export recovery links remain separate. See `inlet-customer-activity.md` for
coverage, truncation, authority and verification limits.

Focused checks: 25 passed, zero skips across customer activity API (SQLite/PostgreSQL),
activity Chromium fixture, route boundary inventory and existing customer portal.
Ruff passed; repository-configured mypy passed (407 files); git diff check passed. No Full, CI,
live account, billing, advertising or deployment operations. Initial test fixture
used an unsupported membership status; corrected to schema-supported suspension.
Standalone `mypy .` encountered the existing duplicate script module discovery;
the repository's configured `mypy` command is the authoritative check.

Final review also guards an obsolete response-body parse failure; the focused Chromium
journey passed again (1 passed). Ruff, mypy (407 files) and diff check passed again.

### Activity And Support Integration

Integrated PR151a0a011c: bounded persisted goal/campaign activity and owner-only validated provider receipt summaries, separate optional page with honest support/recovery links. Combined API, browser and route-boundary checks14 passed with PostgreSQL enabled; Ruff and configured mypy passed. /tmp/inlet-next-activity.log. Coverage/truncation explicit, no fabricated historical events or support endpoint. Browser and API tests remain separate offline evidence.

### B17 Owned Assessments And Measurement History (0057)

Branch `codex/inlet-owned-outcomes` starts at integrated caff2a3. The actual frozen
coordinator reader now feeds workspace-owned immutable assessments backed by a real
retained terminal commerce publication. Creation accepts identifiers/date windows,
not customer-supplied provider evidence. Current owner/session checks, CSRF, latest
receipt resolution, source generation/privacy fences, fresh retention clocks and
publication CASCADE deletion apply. Superseded unknown/conflict evidence never
resurrects earlier success. All installed-producer assessments remain insufficient;
there is no maturity/activation/causal/spending authority claim.

Measurement History is a separate authenticated application journey linked from
Settings, showing actual source as-of/currency/timezone/daily coverage and missing
maturity. Real HTTPS browser journeys exercise sales, confirmed zeros, literal
untrusted names, erasure clearing and session revocation on SQLite/PostgreSQL.
Migration0057→0056→0057 is verified with populated original receipt/publication
fixtures in a guarded disposable PostgreSQL schema. Derived assessment payloads
are classified separately from protected provider audit facts.

Checks actually completed: 85passed/2expectedSQLite concurrency skips in the
combined owned-assessment/migration/browser/pure-evidence/commerce/coordinator/
route suite (`/tmp/inlet-owned-focused.log`); privacy-erasure waiting-replica race
1passed/1SQLite skip (`/tmp/inlet-owned-race-final.log`); existing commerce projection
and lifecycle overlay20passed/1SQLite skip (`/tmp/inlet-owned-lifecycle.log`). Whole
Ruff, mypy389files, JavaScript syntax and whitespace checks passed. No Full started.

Next: export owner must integrate the strict `OwnedAssessment` JSON serializer;
root owns integration/Full qualification. Production exposure, authoritative effect
time, approved maturity policy and qualified comparisons remain open. No live
provider/customer data, migration, deployment or advertising action was used.

### Owned Outcome And Measurement History Integration

Integrated PR152c780d3 and migration0057, preserving newer CRM/activity/export links. Combined owned outcome, populated migration, actual Measurement History browser and route/model-registry checks24 passed1 SQLite-only concurrency skip; Ruff and configured mypy passed. /tmp/inlet-next-owned-outcomes.log. Actual assessments retain contract-test environment and insufficient maturity/effective-time status. Strict owned-outcome export remains pending integration; no measured-lift/live claim.

### Shared Analysis Session And Settlement Integration

PR155a2609d1 cherry-picked asd2cf458. Combined healthy customer scheduler, postclaim source/billing/closure revalidation and analysis admission checks49 passed1 SQLite-only concurrency skip; /tmp/inlet-next-analysis-session.log. This closes the reproduced cross-session self-deadlock without dropping postclaim authorization.

Integrated PR1543def4ba authoritative settlement. Combined settlement/activation suite passed with PostgreSQL enabled; /tmp/inlet-next-settlement.log. Ruff and configured mypy430 passed. Requires original attempts authoritatively closed, exact current receipt set, terminal future-zero and complete reporting; no elapsed-time or target-state-only release. No default live reporting/terminal source and no production qualification.

### Reviewed Portfolio Exposure Composition

Integrated exposure5bcd0aa. Combined-root focused actual SQLite/PostgreSQL checks24 passed; Ruff and configured mypy passed. /tmp/inlet-next-exposure.log. Independent review repaired profile lifetime escaping into later dispatch and disagreement over prior-period held reservations; both have downstream regression coverage. Explicit server facts/profile ports remain unconfigured; no actual native cap or reporting-delay proof is invented, and no default live runtime is enabled.

### Local Closure Reconciliation Integration

Integrated PR15629f7152. Combined current-only closure observation, actual closure browser, scheduler source authority and quiescing checks38 passed1 SQLite-only concurrency skip; Ruff and configured mypy passed. /tmp/inlet-next-closure-reconcile.log. Local pending analysis delivery cancellation is distinct from completed source import; unknown RUNNING records remain blocking and physical_workers_stopped remains null. No external ad shutdown, billing cancellation or deletion-policy inference.

### Actual Social Activation Journey Integration

Integrated PR1531e0c19f test package on assembled successor. Actual Meta/TikTok creation→separate approval→durable activation→owned projections, retained parent reservation, uncertainty/reconciliation, foreign scope, creative/cover drift and revoked generation checks24 passed with zero skips on SQLite/PostgreSQL. /tmp/inlet-next-social-activation.log. Ruff and configured mypy passed; no live provider calls or Full qualification.

### Strict Owned Execution And Outcome Export Integration

Integrated PR159c87a7ff. Actual create→activate→settle→archive, owned outcome export, strict row/digest bindings, privacy cascade after first stream chunk and existing export checks76 passed1 SQLite-only lock-contention skip; Ruff and configured mypy437 passed. /tmp/inlet-next-strict-export.log. Unknown JSON is not dumped; export remains disabled by default. Upcoming durable optimization adds more typed domains and requires a follow-up serializer delta before final freeze.
## B20 Offline Two-Brand Cross-Workflow Acceptance

Branch `codex/inlet-two-brand-pilot`, based on `6eef6d8`. Added one composed
same-database test, parameterized over SQLite/PostgreSQL: two API-provisioned owners,
Shopify/Google/Klaviyo versus Shopify/Meta/HubSpot, actual mocked CRM HTTP account
proof through customer APIs, confirmed goals, exact Google/Meta draft approval,
cross-tenant reads/callback rejection, Brand A durable Google creation and separate
activation through actual MockTransport adapters, then owned closure/receipt history
and Brand B continuity. Existing shared Shopify fixture now accepts optional unique
shop/domain IDs without changing defaults. No production code or migration changes.

`docs/inlet-offline-pilot-matrix.md` identifies the exact evidence and gaps. Native
ad installation/Shopify baseline are fixtures; qualification/exposure inputs remain
contract-test evidence. Google execution is a direct coordinator call because
customer dispatch APIs are absent. Brand B social dispatch and mature measured
outcomes retain their separate existing suite evidence, not claimed composed here.
This does not finish B18 self-serve execution or B20 unrelated real pilots.

Checks actually run: six passed, zero skipped in 13.16s across the new two-brand
scenario, previous assembled customer journey, and original durable Google creation
case (both databases). Ruff passed; repository-configured mypy passed 433 files;
`git diff --check` passed. Log: `/tmp/inlet-pilot-final.log`. No Full, CI dispatch,
live provider, merge or deployment operations. Next: integrate/review this bounded
acceptance evidence, then retain customer coordinator UI and intended-environment
qualification as open work.

### Two-Brand Offline Pilot Integration

Integrated PR1589d4c02. Two independently API-provisioned brands share one database; composed API goal/review/source scopes, actual mocked Google creation/activation, unrelated-tenant denial and closure continuity verified. Combined new pilot and prior customer journey4 passed on SQLite/PostgreSQL; Ruff and configured mypy passed. /tmp/inlet-next-two-brand-pilot.log. Source/qualification fixtures and service-vs-customer-API boundaries are explicit; B20 live unrelated pilots and complete self-service execution remain open.

### Cumulative Accounting Repair Integration

Integrated PR162a68adb8. Parent review reproduced six failures: settled accountA spend60 could be omitted by a new/revised B-only mandate sharing cap100/periodledger, and unresolved other-currency holds were summed numerically. First consent now pins stable accounting account identities; revisions/new mandates/consents/admission cannot change that set. Drafts before consent remain editable. Mixed-currency held exposure blocks new work without assuming FX. No historical accounting or consent is rewritten.

Isolated broad regression74 passed; concurrent consent/claim checks10 passed2 SQLite-only skips; final settlement-IO race/restoration checks9 passed1 skip. Combined-root accounting/exposure/two-brand suite35 passed1 SQLite-only skip; Ruff and configured mypy passed. /tmp/inlet-next-period-accounting.log. Current scalar accounting cannot support arbitrary in-period account-set changes; UI must state that restriction. No migration or live calls.
### Google Existing-Campaign HTTP Optimization — 2026-10-06

Branch `codex/inlet-google-optimization-http` from frozen additive Google ports
`c7a9713566bcf0962310e8421cdeaf031fcef7d9`. Adds actual injectable v25 REST budget/pause
transport, separate from legacy fixture GoogleActions and B07 simulation consent.
Native budget resource is the owner key; paginated campaign topology plus reference
count must prove one independent owner. Search/manual CPC/daily standard budget is
the conservative supported subset. No shared budgets, resume or negative keywords.

Reads bind customer currency/timezone, native settings, schedule, topology and
automatic recommendation state. Masked validate-only and one-shot mutations use
fixed endpoints/bounded responses/timeouts and sanitized errors. Unknown or late
responses retain the original attempt; read-only reconciliation never retries a
mutation, and old state never proves no effect. Native indefinite end is explicitly
null, not an invented date or exposure horizon. Social request documents unchanged.

Checks: actual Google HTTP, additive Google contracts, frozen social adapter/digests
and Google publication tests **92 passed, zero skipped**; Ruff, mypy app/tests
(**389 files**) and diff check passed. No migrations or Full. Runtime factory remains
None and live exposure remains rejected. Coordinator integration/live portfolio
qualification/activation/settlement remain separate work. No live calls, spending,
merge or deployment. See `docs/inlet-google-optimization-http.md`.

## Durable optimization and customer-session fencing checkpoint

Added actual Google/Meta/TikTok one-action optimization coordination under separate
production consent, exact review/approval, current native budget-owner/state/exposure,
one original attempt and retained uncertainty. Shared owned receipt projection now
supports optimization without inferred treatment time. Cumulative positive changes
remain charged across cancellation, settlement and policy revisions; same-owner held
exposure blocks subsequent changes. Server-bound session authorizers revalidate the
original API principal across provider reads/internal commits before protected writes.

Checks: 100 passed/1 SQLite concurrency skip across new durable/session tests and
creation/activation/settlement regressions; separate optimization concurrency1passed/
1SQLite skip; whole Ruff/mypy/diff passed. No Full/workflow dispatch/live operation.
Branch `codex/inlet-durable-optimization`; additive Google contracts e932238/c7a9713,
plan/runtime ports950f6f4 and actual Google adapter15797fd992 are ancestors. Missing:
concrete live exposure/terminal sources, safe ongoing rebudgeting, and actual customer
API/UI/runtime integration. Default runtime factories remain None.

### Durable Three-Provider Optimization Integration

Integrated PR1603df38fc including actualGoogle157 and fresh session authorizer callbacks. Combined real mocked Google/Meta/TikTok budget/pause durable journeys, revoked-session races, PostgreSQL claims and repaired period accounting:50 passed2 SQLite-only skips; Ruff/configured mypy passed. /tmp/inlet-next-durable-optimization.log. Exact allowed targets, positive aggressiveness/cumulative change caps, original-attempt uncertainty and native-owner reservation retention remain enforced. Customer facade/catalog and concrete native qualification sources are separate unfinished packages.

### Optimization Export And Browser Diagnostics Integration

Integrated PR1639a83520 as0d89007. Combined optimization/previous owned archive and browser probe regression checks12 passed; Ruff and configured mypy451 passed. /tmp/inlet-next-optimization-export-probe.log. Actual local Chromium151 decoded both silent H.264 and AAC clips atreadyState4,width64,errornull; /tmp/inlet-next-real-browser-probe.log.

Carried only bounded launch/request/stderr diagnostics and tests frombcf987d into the normal existing preflight. The manual diagnostic workflow mode was not imported; normal required Validation gates remain unchanged. Exact shell dispatch remains paused, without alternate dispatch or network bypass. Hosted Chromium154 behavior still requires the next normal authorized candidate CI evidence.

## Google named configuration HTTP producer — 2026-10-06

Implemented the frozen opaque-selection catalog port from `9c2d9f6e460f45cb0ca42202102212ecfb8bf0db` on isolated branch `codex/inlet-google-catalog`. The actual injectable v25 read-only HTTP producer verifies customer identity, discovers named owned purchase goals with their complete eligible action sets, and resolves exact country/language constants. Bounded pagination, duplicate/foreign reference rejection, expiry, sanitized errors/private HTTP logging and excluded credential fields are covered. Native resource IDs stay server-side; no default factory or live permission was added. See `docs/inlet-google-catalog-http.md` for the integration contract and primary sources.

Validation: `pytest -q tests/test_google_catalog_http.py tests/test_customer_execution_catalog.py tests/test_google_publication_http.py tests/test_provider_publication_contracts.py` passed all 72 tests (no skips); whole-tree `ruff check .` passed; `mypy app tests` passed 432 source files; `git diff --check` passed. All HTTP was mocked. No Full, hosted CI, live provider qualification, deployment or merge is claimed. Explicit credential resolver/runtime composition remains separate work. Native portfolio spending bounds remain unqualified and require the evidence/semantics work recorded in the exposure assessment; catalog discovery grants no publication/spending authority.

### B18 First Customer Execution Journey

Branch `codex/inlet-customer-execution` adds owner+CSRF intent APIs and the separate
Campaign Execution page. Customers review editable proposed limits, separately
consent, select named Google purchase measurement, review exact creative/config,
approve paused creation, advance durable steps, inspect owned receipts and approve
activation separately. Original-session authorization is bound into shared runtime
callbacks across locks/IO; Google preparation now uses the same initial/reentry
callback. A revoked session cannot persist a new review or receive an admitted
in-flight result, while required original provider receipts remain durable.

Dependencies integrated: frozen catalog port9c2d9f6, actual named Google discovery
2d61f56, shared session authorizer/durable optimization3df38fc, and accounting repair
a68adb8. No edits to accounting rules or new migration. Default customer execution
runtime remainsNone; Meta/TikTok expose explicit missing configuration-producer
blockers. All proof, account generation, reservation bounds and provider plans are
server-owned. Pasted provider resource IDs are not part of the customer UI.

Final focused suite110passed/8expectedSQLite-only concurrency/FK skips
(`/tmp/inlet-customer-execution-qualified.log`), covering actual API+HTTPS browser
SQLite/PostgreSQL paths, real named discovery/qualification HTTP adapters with
MockTransport, separate consent/approval, unknown no-replay, original-session
revocation during reads/admitted dispatch, accounting and route guards. Final
browser-only recovery/revoke/logout refinement2passed
(`/tmp/inlet-customer-execution-ui-final.log`). Whole Ruff/mypy454files, JS syntax,
single Alembic head0057 and diff checks passed.

Initial broader checks exposed two test-harness issues, both repaired without
weakening guards: provider qualification migration seeded current ORM at0040
before the workspace privacy column, and its prepare lock barrier preceded the
old source function rather than the new workspace-first authorizer. The fixture
now seeds athead and exercises populated0040↔head; the barrier now observes the
actual authorizer lock via PostgreSQL blocking evidence. Targeted repair7passed/
6SQLite skips, then the full focused suite passed.

Root owns integration/Full. No live advertising, credential factory, deployment or
production qualification occurred. Next: integrate social named configuration
producers, actual live cap/permission qualification and broader customer pilot
checks. Existing activation is observed target state, not causal time or settlement.
## B17 Independent Descriptive Comparison And Stability

Branch `codex/inlet-descriptive-comparisons`, based on `b050854`. Added separate
owner/CSRF read-only POST `/api/customer/v1/workspaces/{id}/descriptive-comparisons`
with `inlet.descriptive-comparison.v1`. Actual owned terminal Shopify publications
can qualify equal-local-day as-of differences; repeated complete reconciliations
report unchanged/revised observed partitions. Current goal/source revision,
manifest bindings, privacy/retention and fresh authorization are checked under
existing fences. Exact Decimal output; zero/negative baselines omit ratios.

Maturity remains explicitly unqualified, action attribution unavailable, causal
lift/recommendation update null and spending authority none. Existing owned action
assessment v2 remains insufficient. No persistence, migration, provider calls or UI
integration. The approved shared contract and narrow owner maturity-policy decision
are documented in `docs/design/b17-owned-comparison-qualification.md`; no 7/30/90-day
policy was invented or borrowed from the unrelated legacy cohort contract.

Checks: 78 passed, 2 SQLite-only row-lock skips (PG variants passed), covering new
descriptive API/producer, existing owned outcomes/pure comparator and assembled route
boundaries. Ruff passed, configured mypy passed 442 files, diff check passed.
Log `/tmp/inlet-descriptive-final.log`. No Full or CI dispatch. Remaining B17:
approved maturity parameters, qualified effective-time producer and bounded explained
recommendation updates; separate customer UI integration remains outstanding.

## Assembled Customer Execution And Comparison Checkpoint

Integrated PR165 (named Google catalog, original-session-bound execution consent,
exact paused creation, separate activation, receipts/recovery) and PR164 (owned
read-only descriptive comparisons; maturity remains unqualified). Source commits
9ac2bb4/db58bb9; integration code head fe710a9. Conflicts were additive route imports
and progress entries only. No schema migration or live runtime enabled.

Combined command: `pytest -q tests/test_customer_execution_api.py
 tests/test_customer_execution_ui.py tests/test_customer_execution_catalog.py
 tests/test_google_catalog_http.py tests/test_descriptive_comparisons.py
 tests/test_route_boundaries.py tests/test_provider_period_accounting.py` using
local disposable PostgreSQL. Exit0, 110 collected:108 passed/2 SQLite-only skips;
log `/tmp/inlet-next-customer-descriptive.log`, exit file alongside it. Whole Ruff,
configured mypy466 files and diff check passed. These are focused checks, not Full.

PR130 now points to earlier assembled e512529. Normal hosted CI run37421671069
passed actual browser H.264/AAC preflight and was running the complete pytest suite
at this checkpoint. The denied manual dispatch remains paused. No quota exhaustion
was reported. Latest customer/comparison integration is not part of that run.

Next: freeze this successor for local Full; continue social audited configuration,
native inventory/qualification and descriptive customer UI independently. Native
spending/exposure sources, mature action comparisons, repeat-owner rebudgeting,
commercial/live configuration and release/pilot gates remain open.

## Spending Review And Social Producer Integration

The parent supplied a bounded independent source review of exact c602a1b on
2026-10-06: both accounting findings closed, no new material issue in that scope.
Stable account identities stay pinned through settlement/consent races;
incompatible-currency unresolved holds reject before composition; positive
optimization changes retain canceled/settled history. This review did not run tests
or qualify providers. Held native owners continue to block unsupported repeat
rebudgeting until an explicit safe replacement protocol is implemented.

Integrated PR166 de9843b/bc5befb as edbb6d9/5786f72: separate social named catalog
contracts, bounded actual Meta discovery adapter and canonical private-media
producer. Root focused social catalog/MetaHTTP/producer suite passed36tests,0skips
(`/tmp/inlet-next-social-catalog.log`); whole Ruff/mypy472/diff passed. Durable
customer declarations, actual TikTok native response parsing and facade remain
blocked; no runtime enabled.

Frozen Full c602a1b tree ad37922d2b9fb2ac5d3be01d575d290d492c060e remains running in
separate worktree. Hosted PR130 e512529 tree37b1831dc312b68b1b51aa48d67e1ea5c195a7c4;
fetched synthetic merge f3e12aa8a0d17726491972b970c0d7e41cdc32ba has the identical
tree. Actual hosted checkout still to confirm from completed job log. CI remains
running, not a terminal pass.

## Google native inventory diagnostics — 2026-10-06

Implemented an actual bounded injectable v25 read-only inventory collector on `codex/inlet-google-native-inventory`, exact base `fe710a9`. It reads all paginated campaign/budget owners (including removed/other-channel rows), observed native-calendar cost, billing setups and proposed/approved/adjusted/pending/future account-budget facts. Missing owners, changed topology, billing read failures and absent cost stay explicit. Output types force unqualified cap semantics and null reporting watermark/unreported/future/proposed upper bounds; no default factory, qualified profile or ledger/reservation mutation exists.

`docs/inlet-google-native-inventory.md` records the actual composition contract, provider evidence and remaining billing-basis/writer-boundary owner decisions. Lower budgets, finite caps and late reports do not prove reusable residual exposure or settle earlier optimization attempts. Runtime persistence/composition and a qualified source remain concrete engineering work, not credential-only gates.

Checks run: `pytest -o addopts='' -q tests/test_google_native_inventory.py tests/test_google_optimization_http.py tests/test_google_catalog_http.py tests/test_customer_execution_catalog.py` — 103 passed, no skips; whole `ruff check .` passed; `mypy app tests` passed 464 source files; `git diff --check` passed. All HTTP mocked. No Full, hosted CI, live API, operational enablement, merge or deployment claimed.

## Native Google Diagnostics

Integrated PR16716fd3b9 as15e99a8. Bounded campaign/budget/cost/billing/account-budget
reads retain pending and adjusted caps and distinguish unavailable billing access
from empty inventory. Output is statically unqualified with null-only reporting
watermark and exposure bounds; no runtime factory or spending authority is added.
Root native inventory regressions24passed (`/tmp/inlet-next-native-inventory.log`),
whole Ruff/mypy474/diff passed. This is focused adapter validation using mocked HTTP,
not actual provider qualification or the separately running frozen Full.

## B17 Descriptive History UI And Owner Decision Bundle

Branch `codex/inlet-descriptive-history`, based on `c602a1b`. Measurement History
adds an owner-only confirmed-goal/date-window form against the existing descriptive
endpoint. Exact Decimal values are formatted without Number precision loss, with
explicit as-of/unqualified/unattributed/no-causal/no-recommendation/no-spend labels.
No prior history selector is invented; the UI does not request stability without
an owned listing. Session/source changes and erasure clear values; epochs reject
late responses and fresh server authorization rejects role loss. Viewer measurement
reads remain available.

`docs/design/b17-maturity-owner-decision.md` proposes independent operational-maturity
and action-time evidence contracts and a genuine unresolved owner worksheet. Every
numeric lag/count/separation/tolerance/freshness choice remains unset. Operational
as-of maturity is recommended as a product direction only; authoritative finality is
not supplied by current Shopify evidence. Delivery-linked launch claims remain the
requirement; configuration observations are separately descriptive. No action
maturity producer is enabled, and no policy approval is inferred from approving code.

Checks: 42 passed, 1 SQLite-only row-lock skip (PG variant passed), including real
HTTPS Chromium→API→SQLite/PG comparisons, role downgrade, stale response clearing,
privacy erasure, exact large values, backend boundaries and assembled route inventory.
Ruff passed, configured mypy passed 466 files, diff check passed. Log:
`/tmp/inlet-descriptive-history-final.log`. No Full, CI dispatch, migrations, live
provider calls, spending, merge or deployment.

## Durable Google exposure design records — 2026-10-06

Saved the [native exposure assessment](design/google-native-exposure-qualification.md) and [joint-envelope proposal](design/google-joint-envelope-proposal.md) under `docs/design` on a docs-only child of PR167 head `16fd3b907177b0446ffda63a694ff6fb753baa2e`. Both crosslink to the actual diagnostic collector and current composer. No currently reviewed preventive Google writer mechanism qualifies, and typed fields alone cannot close strict-cap acceptance. Owner monetary-basis selection remains unresolved; a restricted-launch question is conditional on first demonstrating a real enforceable mechanism. No runtime, migration, policy, or enablement change. Relative links and `git diff --check` verified; tests intentionally not repeated for prose.

## Descriptive History Integration

Integrated PR168e1cb081 as a95ca7c, with owner-only as-of comparison UI and explicit
unqualified maturity/no action-attribution labels, plus unresolved owner decision
worksheet. Root actual browser/API/backend regressions33passed1SQLite-onlyskip
(`/tmp/inlet-next-descriptive-ui.log`). Ruff/mypy474/diff passed. The docs-only
Google exposure assessment/joint-envelope proposal a156fbc is integrated7360e3e;
it does not qualify a provider profile or change the monetary promise.

## Final Credential Context Authorization Repair

PR169d5c0671 integrated as f872552. Credential context resolution now precedes the
final fresh session/claim admission check for creation, activation and optimization;
creation also validates the claimed owner before resolving credentials. Corrected
agent baselines reproduced10 product failures on both databases (earlier erroneous
creation fixture failures are excluded). Root execution-session regression suite
20passed (`/tmp/inlet-next-context-fence.log`); Ruff/mypy474/diff passed. The fixed
artifact is newer than both running c602a1b Full and e512529 hosted CI; any pass from
those predecessors does not qualify this repair or establish release readiness.

## Social Configuration Review Foundation — 2026-10-06

Branch `codex/inlet-social-review`, base `a95ca7c`, reserved0059/down0057.
Implemented strict no-DSA configuration document, owned immutable review/approval
records, current account/source/catalog/media selection, required caller authorizer,
exact idempotent confirmation and current-owner confirmation read. Meta answers are
explicit: applicable/unsure cannot confirm; DSA names are absent from the schema
and rejected as extra fields. Verified DSA-required profiles remain blocked. TikTok
binds actual owned decoded video/cover media; native parser and qualification gates
remain unchanged. Protected lifecycle fields and strict JSON export bind document
to owned scalar lineage. No personal-name retention exception.

Design/copy inventory persisted in `inlet-social-configuration-review-design.md`
and `inlet-social-declaration-privacy-lineage.md`. Current canonical receipt readers
need full original documents, so personal declaration erasure cannot yet preserve
the settlement path. Shared closure-only evidence contract remains design-only;
no personal declaration capture was enabled.

Checks actually run: combined56 passed/1 SQLite-only concurrency skip across new
review/migration, model registry, existing social producer, export execution and
lifecycle tests (`/tmp/inlet-social-review-final.log`). Final confirmation helper,
approval population and cross-workspace FK denial:6 passed
(`/tmp/inlet-social-review-new-final.log`); migration rerun after typed insert fix:
1 passed (`/tmp/inlet-social-review-migration-final.log`). Disposable generated PG
schema0057→0059→0057→0059 preserves existing runs and recreates new tables. Whole
Ruff and clean mypy479 passed; diff check and single alembic head0059 passed.
No broad Full, live operations, deployment or merge.

Remaining: customer API/UI, exact configuration reference in canonical social plan,
coordinator prepare/approve/claim/final-emission revalidation and private pair-review
browser tests. This checkpoint alone does not provide a customer-facing journey or
social dispatch authority. It does not enable a live runtime or remove any native
qualification/spending blocker. DSA personal inputs await complete closure-safe
privacy handling across every original/activation plan and request copy.

## Social Review Storage Foundation

Integrated frozen a08db1b as329ff9f: owned exact no-DSA configuration reviews and
confirmations, explicit strict export/lifecycle classification, migration0059 from
0057. Root review/migration/route suite15passed with4deprecation warnings
(`/tmp/inlet-next-social-review-foundation.log`); Ruff/mypy479/diff passed; current
single Alembic head0059. Customer routes, exact canonical-plan approval binding and
UI remain a dependent package; storage does not enable dispatch. Personal DSA fields
are absent/extra-forbidden; required or unverified DSA profiles remain blocked.

Original audit timeline mapping supplied by the parent's read-only document check
is recorded separately in `docs/inlet-audit-timeline.md`. It supersedes the earlier
unverified weeks4–5 shorthand; phase comparisons are not delivery forecasts.

## Meta/TikTok native spending evidence assessment — 2026-10-06

Added [the bounded official-source eligibility matrix](design/meta-tiktok-native-exposure-assessment.md). TikTok documents editable/resettable account caps and lifetime controls; its credits-adjusted delayed net-cost metric and request-log identifier do not prove a strict portfolio envelope or original-request finality. Meta's official SDK identifies concrete mutable cap fields; inaccessible help/API semantics remain explicit gaps rather than third-party assumptions. The assessment specifies missing native enforcement, counting-period/adjustment, complete ownership, writer prevention and terminal-request evidence. No currently reviewed source qualifies the strict ceiling or safe reservation release. No runtime contracts, provider calls, credentials or authority changes. Relative links and staged diff check passed; no tests required for prose.

## Frozen Full Nested Failure — Investigation In Progress

The c602a1b frozen Full has not terminated, but its first nested Full reported
2507passed/62skipped/4failed (2573tests,1247.354seconds). Preserved JUnit:
`/tmp/inlet-oct06-nested-0.xml`. Failures: Shopify duplicate/disconnect callback
barrier, Shopify expiry-purge barrier, Shopify connection-revocation/import barrier,
and TikTok access-log filter test observing an empty ordinary-health log. The
nested regression therefore fails and outer pytest continues. Dedicated isolated
investigations are reproducing these; no assertions weakened and frozen tree untouched.
These are actual observed failures, not a Full pass or a terminal aggregate result.

## TikTok Access-Log Regression Isolation

On isolated child of root `3a7577e`, reproduced the frozen nested failure without
editing the Full worktree: create `logging.getLogger("uvicorn.access")` as earlier
browser tests do, then call the repository's `logging.config.fileConfig("alembic.ini")`
and execute `test_auth_code_callback_bridge_headers_and_actual_access_filter`.
Alembic's existing-logger disabling left `logger.disabled=True`; `logger.handle`
then suppressed both the sensitive callback and the ordinary-health positive
control. Exact before failure is in `/tmp/inlet-tiktok-log-before.txt`.

The test now explicitly enables its captured logger and restores the prior disabled
state. Both incoming enabled/disabled states are parametrized. The actual callback
query suppression and `GET /health` assertion are unchanged. Pytest monkeypatch
restores the original external state after each case; the contaminated-process
reproducer passed both cases and asserted its original disabled state was restored
(`/tmp/inlet-tiktok-log-after.txt`). Separately verified actual `uvicorn.Config`
re-enables the disabled access logger. No production logger/filter code changed.

The ordered command, with the explicitly disposable PostgreSQL service enabled,
was `pytest -xra tests/test_customer_browser_api_journey.py
tests/test_inlet_integrated_migrations.py tests/test_customer_tiktok.py`:
**20 passed, zero skips, six existing Alembic path-separator deprecation warnings**,
24.39 seconds (`/tmp/inlet-tiktok-log-ordered-tests.txt`). This exercises actual
HTTPS browser tests, populated migration downgrade/reupgrade, then TikTok cases
in one process. Whole-tree Ruff, configured mypy (479 files), and diff check passed.
No new Full or hosted CI result is claimed; the earlier frozen Full failure remains
historical evidence until a repaired integrated tree is validated.

## Frozen Full Shopify Race-Probe Repair

Branch `codex/inlet-shopify-race-fixtures`, isolated from `f4cbcd2`; frozen Full
checkouts unchanged. Reproduced two deterministic probe failures from retained
`/tmp/inlet-oct06-nested-0.xml`: disconnect now waits in the workspace privacy
`FOR NO KEY UPDATE` fence before the old literal `FOR UPDATE` probe, and expiry
purge waits on workspace `FOR UPDATE` before its old OAuth DELETE probe. Updated
only those synchronization probes; expiry also asserts that neither OAuth deletion
nor measurement-store access occurs while waiting. Provider release/listener cleanup
now runs even when a probe fails. No deadline increases, retries, sleeps or production
changes.

The third native import/revocation failure did not reproduce: it passed alone and
alongside the two reproduced failures. Its test now surfaces completed worker
exceptions/early statuses rather than masking them behind an unset event, and
always releases its fixture barrier. The original nested failure remains unresolved;
this diagnostic improvement is not claimed as its root-cause fix. Existing 5s/10s
barriers and 0.2s revocation-blocking assertion remain unchanged.

Checks: original three-case reproduction 2 failed/1 passed (19.67s); native case
alone 1 passed (2.18s). Final complete `test_customer_shopify.py` and
`test_review_native_ownership.py`: 34 passed, 6 SQLite-only PostgreSQL concurrency
skips (25.46s). Ruff passed, configured mypy passed 474 files, diff check passed.
Logs `/tmp/inlet-shopify-race-repro.log`, `/tmp/inlet-native-race-alone.log`,
`/tmp/inlet-shopify-race-fixed.log`. No Full or CI dispatch. Next combined validation
must still observe the native-import case; TikTok logger failure is separate work.

## Combined Frozen-Failure Repair Checks

Integrated TikTok logger-isolation479f282 as57ab587 and Shopify barrier/cleanup
repairbc8a5f7 as1c3ba6f. Root combined `test_customer_shopify.py`,
`test_review_native_ownership.py`, `test_customer_tiktok.py`:50passed/6SQLite-only
skips,27.76seconds (`/tmp/inlet-next-frozen-failure-repairs.log`). Ruff/mypy479/diff
passed. Two stale probes and logger-state contamination have reproduced causes;
the one native-import barrier failure still has no independently reproduced cause.
Its assertions/deadlines remain, with better failed-worker diagnostics and cleanup.
This focused pass does not erase the observed frozen Full failure or establish a
successful new assembled Full. Frozen outer suite and hosted CI still running.

## Repeat Optimization Reservation Replacement — 2026-10-06

Branch `codex/inlet-repeat-optimization` starts at assembled c602a1b and includes
context-fence repair d5c0671. Adds a separately approved repeat review, complete
predecessor/request closure snapshot, server-only transition qualification port,
atomic superseded→successor held reservation transfer and migration 0058. Original
v1 plan/request serialization is unchanged. Default replacement reader is absent.

Google, Meta and TikTok actual HTTP adapters were exercised via MockTransport through
three sequential requests and terminal settlement. All original attempts remain in
the chain. New coverage includes no-attempt inherited hold retention, changed/expired/
missing proof, cancellation after qualification, rollback after partial transactional
writes, PostgreSQL concurrent claims, unknown successor no replay, and strict audit
export plus migration downgrade refusal. Lifecycle inventory explicitly protects the
new table; no arbitrary JSON export or table-classification bypass.

Independent review reproduced a late ancestor contradiction bug on both databases:
unknown receipt appended after successor claim incorrectly allowed emission. Fixed
by checking latest complete ancestor evidence again at final post-context claim.
The two controlled baseline failures became passes; final-context injection variants
also pass. Fresh authority/proof time is resampled after ancestor reads.

Final post-repair command `pytest -o addopts='' -q tests/test_repeat_optimization.py
 tests/test_execution_session_authorizer.py` passed 47 with 1 intentional SQLite-only
row-lock concurrency skip. Ruff (`app tests migrations`), mypy (`app tests`, 467 files)
and diff check passed. Broader repeat/migration/optimization/settlement/session run passed 109 with 1
intentional SQLite concurrency skip before the final additional fresh-authority
check (verified by the 47-pass run). Migration empty roundtrip and populated
downgrade refusal passed. Full is pending integration and root coordination. No manual workflow dispatch.

Remaining: no authoritative native original-request closure/transitional exposure
source for any provider; no live factory or customer repeat-intent UI enabled.
Contract scenarios cannot qualify live. Root must join parallel 0058/0059 using 0060.
Separate personal DSA erasure requires an admission-time nonpersonal closure binding;
this package does not persist personal declarations or relax spending semantics.

## Repeat Optimization / Social Schema Integration

Integrated frozen repeat2ac0604 as5dd0d7a. DraftPR171 created through the connected
GitHub app after the shell API request returned ambiguousForbidden; no manual
workflow-dispatch retry or network/credential change. Adds exact atomic replacement,
complete ancestor original-request closure and receipt drift checks, inherited
exposure settlement protection, and strict audit/export handling. Native source
reader remains absent; no live or customer repeat dispatch is enabled.

Merge0060 joins0058replacement and0059social review heads. Root combined repeat,
replacement migration, social review/migration and fresh-session regression suite:
54passed/1SQLite-onlyskip/8existingdeprecationwarnings,77.51seconds
(`/tmp/inlet-next-repeat-social-merge.log`). Whole Ruff/mypy484/diff passed. Migration
checks cover empty roundtrip and refusal to erase populated replacement lineage;
independent late-ancestor review remains recorded separately. Frozen c602a1b Full
and hosted e512529 do not include this package and are still running.

## Existing Campaign Customer Interface Design (2026-10-06)

- Inspected assembled `5dd0d7a` and migration 0058; recorded the proposed owned
  target catalog and separate initial/repeat review contract in
  `docs/design/b18-existing-campaign-customer-contract.md`.
- Identified required exhaustive purpose/schema dispatch and original-session
  authorization extension in the existing creation/activation customer facade.
  No API, UI, runtime, schema or source producer was implemented by this package.
- Portal owner confirmed the optimization namespace does not conflict with the
  active social configuration work. Default factories remain `None`; native
  repeat closure/transition qualification is still unavailable.
- Validation: documentation diff/whitespace check only; no tests, Full, CI dispatch,
  provider calls, deployment or spend. Next package: freeze typed interfaces, then
  implement owned catalog/preparation and customer boundary regressions.

## Independent Repeat-Protocol Re-Review

Bounded independent review of exact2ac0604 closed the reproduced late-ancestor
receipt finding: final admission compares complete immutable chain/latest receipts
after credential context and fresh authority checks. Independently selected tests
11passed/1SQLite-onlyskip (16deselected),14.81seconds; populated downgrade refusal
and empty migration roundtrip1passed/4deprecationwarnings,3.69seconds. Logs:
`/tmp/inlet-repeat-independent-review.log` and
`/tmp/inlet-repeat-independent-migration.log`. No additional material finding in
that scope; no broad approval, Full or native qualification is inferred.

## Frozen Validation Terminal Outcomes

Local Full on c602a1b3d541a8c14c3d3fc85c41f7284aef6dec,
treead37922d2b9fb2ac5d3be01d575d290d492c060e, terminated exit1:
2511passed/58skipped/4failed/77warnings,2590.01seconds. Failures: nested Full,
Shopify disconnect callback probe, Shopify expiry-purge probe, TikTok logger probe.
The native-import barrier failure was nested-only and did not recur in the outer
suite. Outer skips:52SQLite-only PostgreSQL semantics and6unavailablePowerShell.
Nested skips additionally include one intentional recursion guard and3restore-tool
availability skips in the sanitized child environment. Subsequent Full gates were
not reached because pytest failed. Log `/tmp/inlet-oct06-assembled-full.log` and
exit file; nested evidence `/tmp/inlet-oct06-nested-0.xml`.

HostedPR130 run37421671069/job112132173160 terminated failure. Actual checkout
f3e12aa8a0d17726491972b970c0d7e41cdc32ba merges e512529 into main ea3591c;
tree37b1831dc312b68b1b51aa48d67e1ea5c195a7c4 equals the e512529 source tree.
Browser H264/AAC preflight passed. Main pytest2426passed/51skipped/5failed,
73warnings,2647.00seconds. Failures: nested Full, the same2Shopify probes, TikTok
logger, and old provider-qualification migration fixture missing export privacy
column. The migration fixture was repaired later in PR165; remaining reproduced
probes are repaired in current root. Ruff/mypy/diff/reversible-migration/boundary/
security/privacy/isolation steps were skipped after pytest failed, not passed.
Hosted full log `/tmp/inlet-pr130-e512-hosted.log`.

Hosted nested2424passed/52skipped/6failed: those four direct cases plus HubSpot and
Meta PostgreSQL browser cases. Their exact assertions were lost because the8MiB
JUnit-input bound rejected the report. Both browser cases passed in hosted outer
pytest; cause remains unresolved, with bounded local reproduction underway. No
quota/plan-limit evidence occurred. Manual workflow dispatch remains paused.

The retained local JUnit is17,184,616bytes, mostly parameterized test IDs. Diagnostic
reader now streams a finite64MiB report, clears completed cases and still prints
at most8bounded failures plus short stdout/stderr tails. Regression with a large
passing parameter ID followed by a real failure passes; all7diagnostic tests pass.
Actual retained17MiB report now yields all4case-specific failures. No validation
scope, exit handling, assertion, timeout or required gate is weakened. Ruff,
configured mypy484 and diff check pass. New assembled Full/CI remains required.

## Normal CI Bounded Failure Artifact

Normal PR CI now places the complete pytest run's temporary files under its
runner-local directory and prints all skip/failure summaries (`-ra`). On failure,
standard-library collection retains at most two deduplicated nested reports as a
single summary capped at256KiB, never uploads raw XML/stdout/provider payloads,
and refuses paths escaping the selected test directory. Artifact retention7days.
All existing tests/gates and failure exit behavior remain unchanged; manual
dispatch is still paused. Nested skip reasons/counts are included in the summary.

Diagnostic/workflow contract selection11passed/40deselected; Ruff/mypy484/diff
passed. Actual17MiB retained local report produced a2333-byte per-case summary
before added skip reason counts. This makes the two still-unexplained hosted
nested browser failures diagnosable on the next permitted normal PR run; it does
not mark them fixed. Exact e512 local Chrome154 ordered CRM/Meta reproduction
8passed0skips33.44seconds, `/tmp/inlet-pr130-browser-repro.log` and `.xml`.

## Exact Social Configuration Customer Journey — 2026-10-06

Child `codex/inlet-social-review-journey` of frozen0059 foundation `a08db1b`.
Preserves final credential-context/session fence `d5c0671` (local cherry-pick
`d63cae6`). No migration beyond the already-reserved0059; root owns0060 integration.

Implemented `/app/social-configuration` and owner/session/CSRF intent-only options,
review, historical read and exact confirmation APIs. Actual private video and cover
must decode before browser acknowledgement; changed selection invalidates it and
logout clears object URLs/data. Missing runtime/rules/native qualification are
honest blockers. No personal DSA fields are accepted and no default factory exists.

Version2 persists strict complete nonpersonal configuration, its digest and the
server-reviewed wording actually shown. Version1 remains valid typed history/export
with unchanged hashes but cannot authorize a new forward action. Owned DB declaration
reader and optional canonical approval reference bind the actual customer confirmation.
Current source/owner/configuration guards run through creation and activation admission;
referenced plans require a current server profile/catalog validator and live social
legacy plans without a reference are denied. Golden hashes captured from frozen
`a08db1b` prove legacy Google/social review/plan JSON, including explicit nulls,
remains unchanged. No generic JSON export or inferred regulatory answer.

Checks: guard/session/activation50passed (`/tmp/inlet-social-journey-guard.log`);
assembled route/export/browser/review35passed (`/tmp/inlet-social-journey-final.log`);
final wording/versioned-history/media browser+API+review/migration/golden suite15passed
(`/tmp/inlet-social-wording-final.log`). Subsequent missing-validator/live-unreferenced/
changed-profile/default503 focused guard/API9passed (`/tmp/inlet-social-guard-final.log`).
Final API+actual HTTPS browser+assembled route checks17passed
(`/tmp/inlet-social-customer-final.log`), followed by actual persisted legacy-v1
approval/history compatibility API4passed (`/tmp/inlet-social-history-api-final.log`).
Both SQLite and disposable PostgreSQL were exercised. Whole Ruff, clean mypy484,
JS syntax and diff checks passed. These runs overlap; counts are not summed.
No Full or CI dispatch was started by this package. Root owns assembled qualification.

Remaining: existing customer execution creation intent still supports Google only;
confirmed social configurations must be wired into that path with real current
catalog/profile and native qualification producers before advertising social creation.
The new screen confirms configuration only and does not publish or activate ads.
DSA personal capture remains blocked until closure-safe privacy propagation across
all original/activation copies is implemented. No live credential/provider calls,
spending, merge or deployment. See `inlet-social-review-journey.md` for frozen ports
and `inlet-social-declaration-privacy-lineage.md` for the actual finality dependency.

## Social Customer Configuration And Next Candidate

PR173ae57ccc integrated8221455. Customer owner/session/CSRF routes and actual
private Meta/TikTok review UI bind exact full nonpersonal configuration, readable
reviewed requirement wording and video/cover media. V2 approvals cannot be reused
for changed configuration; v1 history/export stays readable but nonexecutable;
legacy absent-reference plan hashes remain unchanged. DSA-required/unverified
profiles and live/native qualification remain blocked. No new migration; head0060.
Social creation/activation consumer and existing-campaign optimization customer
intent are separate followup packages, not claimed complete here.

Root combined social API/browser/hash/review/migration/repeat/routes suite:
51passed/1SQLite-onlyskip/4deprecationwarnings,86.06seconds
(`/tmp/inlet-next-social-customer-flow.log`); Ruff/mypy489/diff passed. This candidate
includes post-context session repair, repeat accounting, reproduced frozen-failure
fixture repairs, and bounded normal-CI diagnostic artifacts. Next frozen Full and
PR130 CI must establish their own terminal results; neither is assembled-green yet.

## Customer Existing-Campaign Optimization API (2026-10-06)

- Added separate owner/session/CSRF target discovery, optimization-only mandate
  creation/editing and consent, initial exact review and separately qualified repeat
  review endpoints. All target topology is resolved from named server configuration
  plus actual adapter reads; callers cannot supply provider IDs, proof or payloads.
- Shared approval/run/advance/reconciliation now reject unknown purpose/schema
  combinations and dispatch optimization explicitly. Owned review/run projections
  include exact historical mandate limits and independently retained exposure.
  Creation/activation media storage is resolved lazily; budget/pause requires none.
- Actual Google, Meta and TikTok adapter journeys use MockTransport with real customer
  login, CSRF, API calls and durable SQLite/PostgreSQL coordinator records. Added
  stale/foreign/forged input, topology re-consent, missing repeat source, unknown
  dispatch and original-session revocation-during-I/O coverage.
- Production factories remain `None`. Configured offered inventory is not native
  automatic discovery or qualified exposure/finality. Customer optimization UI and
  native qualified producers remain follow-up work; no live execution is enabled.
- Validation: broader API/catalog/UI/pilot/route-boundary/durable/repeat batch
  **113 passed, 1 SQLite-only concurrency skip**. After adding exact historical
  reviewed-limit projection, API/catalog/route-boundary batch **46 passed**. Final
  owner/session/role/topology/capability batch **24 passed in 34.38 seconds**, on
  SQLite and disposable PostgreSQL. Ruff, configured mypy (**489 source files**) and
  `git diff --check` passed. No Full, CI dispatch or live provider call.
- Shared social hook coordinated with portal owner: their later helper may refresh
  social creation authority after `bound()` and lazy media resolution in the legacy
  creation/activation branches. Optimization returns first; historical reconciliation
  does not require new social forward-execution qualification.

## Exact Second Frozen Candidate And Independent API Progress

PR130 and local candidate worktree freeze8efe19668d4920df6607ddd60140ab8ab0779049,
tree11252fdbc785c270b49a1340dff95506d7391405. Local Full runs in
`/workspace/inlet-mvp-candidate`, disposableDBinlet_oct06_candidate2_ci, log
`/tmp/inlet-oct06-candidate2-full.log` (future `.exitcode`). Normal hosted run
37427571832/job112150604656 is running pytest after successful browser preflight.
Fetched merge80e432a072d4970fd4fe50c23b1a913257e99250 has the identical tree; actual
checkout will be confirmed from its completed log. No terminal success yet.

Independent newer root integrates PR174cc9266e asdb22240: owner-scoped named target
catalog, optimization-only mandate/topology consent, initial/repeat API reviews,
exhaustive shared execution dispatch and lazy media access only for creative paths.
Root combined optimization/creation/social API/route checks49passed0skips85.35s
(`/tmp/inlet-next-optimization-customer-api.log`). Ruff/configured mypy/diff passed.
No migration or enabled production factory. Existing-campaign UI, native discovery
and qualification remain separate; this newer API is outside the frozen8efe run.
## B19 terminal provider rejection attention — 2026-10-06

At root `db22240`, a persisted terminal source `provider_error` with no retry timestamp produced `no_attention_observed`, even though reads were blocked. Added fixed `connection_provider_error` warning with `review_connection`; rotating-token `renewal_uncertain` still takes precedence as critical no-retry evidence. No raw provider error codes, identifiers, grants or payloads leave the report. Raised the maximum fixed signal union from 18 to 19 and documented the code. No provider action or automatic retry was added.

Checks: `tests/test_operations_attention.py` and `tests/test_provider_operations_attention.py` passed 31 tests on SQLite and disposable PostgreSQL, no skips; terminal errors with missing/private error codes, recovery, mixed critical precedence and preserved state are covered. Log: `/tmp/inlet-provider-error-attention-tests.log`. Whole Ruff passed; mypy app/tests passed 490 source files; diff check passed. No Full, hosted CI, live calls or alert delivery claimed. Broader read-only B19/B20 review identified populated new-domain restore and composed export/closure/pilot evidence as remaining offline work, distinct from intended-environment/commercial gates.

### Integrated B19 Alert Regression Check

Integrated draft PR175 (`457470a`) as `8935e47` after review. The combined
operations attention, provider operations attention and customer activity tests
passed on SQLite and disposable PostgreSQL (35 cases, exit 0), recorded in
`/tmp/inlet-next-provider-attention.log`. Whole Ruff and configured mypy passed
(490 source files), as did `git diff --check`. No automatic retry or provider
write was introduced. These checks apply to the newer integration branch, not the
still-running frozen `8efe196` Full/PR130 candidate.

The next independent operations packages are populated native restore evidence
and composed owned export/closure with replacement financial lineage and social
approvals. Both remain offline acceptance work; neither is evidence of production
backup recovery or unrelated live customer pilots.
## Existing Campaigns Customer Page (2026-10-06)

- Added separate `/app/optimization` page/module and owned recovery URLs, plus an
  additive execution navigation link. The browser selects named current account/
  target choices, edits explicit UTC spending periods and limits, separately consents,
  reviews/approves/adopts exact runs, executes one reviewed step, reads/reconciles
  original receipts, and prepares qualified repeat budget or pause reviews.
- Added bounded owner-only account choices validated through current account scope,
  and an opaque owned reservation reference in optimization run projections. No
  native provider ID/proof entry, migration, enabled factory or live source added.
- Actual HTTPS Chromium → FastAPI → SQLite/PostgreSQL → Google HTTP MockTransport
  journey verified initial budget, repeat budget and repeat pause with exactly three
  writes. Dropped successful mutation responses recover from owned status without
  replay. Delayed success/failure cannot restore a changed workspace. Owner-role loss,
  disabled runtime recovery and logout preserve the documented boundaries.
- A controlled regression found that a failed session/status GET after an uncertain
  mutation cleared the UI uncertainty flag and re-enabled the old execution button:
  **1 failed** in `/tmp/inlet-optimization-ui-uncertainty-repro.log`. Uncertainty is now
  retained across failed reads until owned recovery. Input edits also invalidate
  in-flight review responses; no timeout increase or automatic retry was added.
- Validation: API/new browser/existing creation browser/route-boundary batch **39
  passed in 79.40 seconds**, no skips; after the uncertainty fix the complete new
  browser journey **2 passed in 15.14 seconds**, both databases. Ruff, configured
  mypy (**490 source files**), Node syntax checks and `git diff --check` passed.
  Logs `/tmp/inlet-optimization-ui-final.log` and
  `/tmp/inlet-optimization-ui-browser-final.log`; corresponding JUnit files retained.
- Boundary: browser journey uses explicit offline qualification/finality fixtures and
  one Google campaign configuration. Backend provider permutations are separate
  evidence. Native automatic discovery and live qualified execution remain unfinished.
  No Full, CI dispatch, merge, deployment, live provider call or advertising spend.

### Integrated Existing-Campaign Page Validation

Integrated PR176 (`12032e0`) with the social configuration routes and navigation
preserved. Root combined optimization API, optimization browser, existing creation
browser and route-boundary suite passed **39 tests, no skips, in 76.14 seconds**
on SQLite and disposable PostgreSQL. Log: `/tmp/inlet-next-optimization-ui.log`.
An initial invocation named a nonexistent browser test file and collected no tests;
the corrected command produced the result above. Ruff, mypy (491 source files),
Node module syntax and whitespace checks passed. Frozen `8efe196` validation does
not include this newer UI. No production factory was enabled.
Merge0060 joins0058replacement and0059social review heads. Root combined repeat,
replacement migration, social review/migration and fresh-session regression suite:
54passed/1SQLite-onlyskip/8existingdeprecationwarnings,77.51seconds
(`/tmp/inlet-next-repeat-social-merge.log`). Whole Ruff/mypy484/diff passed. Migration
checks cover empty roundtrip and refusal to erase populated replacement lineage;
independent late-ancestor review remains recorded separately. Frozen c602a1b Full
and hosted e512529 do not include this package and are still running.

## Social Customer Execution Journey — 2026-10-06

Isolated child `codex/inlet-social-creation` of PR173 `ae57ccc`, incorporating frozen
PR174 `cc9266e` common optimization dispatcher and root's unchanged `ca404a9`/0060
merge revision. No newly allocated migration, live runtime, provider connection or
spending authority. The social feature remains a separate final commit for review.

Added strict owner/session/CSRF social creation intents using only saved configuration
and production consent references. Server reconstruction binds current catalog,
profile, reviewed rules, source/generation, exact private media and persisted customer
confirmation. Forward approval/run/advance and separate activation refresh current
selection outside locks, then retain original-session authorization and a pure local
freshness check at locked coordinator boundaries. Current discovery is deliberately
not a prerequisite for original-attempt reconciliation. Live native catalog blockers
remain denied, and no personal DSA inputs or retention exception are introduced.

The existing customer execution page now offers readable confirmed Meta/TikTok
configuration selection, exact paused creation approval, durable steps and recovery,
separate activation, receipts and logout. Google settings remain separate; social
customers do not paste resource IDs or submit runtime/proof JSON. Contract-test mode
explicitly makes no provider account changes. Activation readback is not causal or
effective-time evidence, and uncertain exposure is not prematurely released.

Actual focused results (separate selections):
- 8 passed: API paths on SQLite/PostgreSQL, extra-proof rejection, owner/CSRF/logout,
  wrong digest, disabled runtime, changed-rule denial, fresh session revocation during
  catalog IO, expiry during qualification, durable creation/activation and original
  receipt recovery with current discovery absent. `/tmp/inlet-social-creation-api-final.log`
- 4 passed: actual HTTPS Chromium social journeys, Meta/TikTok on both databases,
  named selection, literal strings, separate consent/reviews, paused creation,
  activation, owned status recovery and logout. `/tmp/inlet-social-creation-browser.log`
- 52 passed: existing Google API/browser, optimization API, configuration API,
  historical hash compatibility and assembled route boundaries.
  `/tmp/inlet-social-creation-regression-final.log`
- Subsequent final authority checks: 6 passed, covering original-session/expiry
  denial and preservation of any pre-existing server configuration validator.
  `/tmp/inlet-social-creation-authority-final.log` (overlaps the earlier API selection).
- Whole Ruff, clean mypy499, JavaScript syntax and diff checks passed. Single Alembic
  head0060 uses the exact already-reviewed root merge revision.

Earlier fixture runs are superseded: an original media-reader Session reopened after
fixture cleanup and blocked disposable-schema teardown; the final test assembly uses
fresh closed per-read sessions. No production persistence behavior was altered for
that harness repair. Root owns assembled Full/hosted qualification. No Full or CI
workflow was launched for this package. Native spending/finality proof, TikTok native
catalog decoding, DSA personal-data closure handling and live qualification remain
open. See `inlet-social-execution-intents.md` for the exact ports and limits.

### Integrated Social Execution And Cross-Flow Browser Evidence

Integrated PR177 feature `12296ec` while preserving PR176's optimization navigation
and dispatch. Combined social API/guard, Meta/TikTok execution browsers, existing
Google execution browser, optimization browser and route-boundary suite passed
**27 tests, no skips, in 250.88 seconds** on SQLite and disposable PostgreSQL.
Log: `/tmp/inlet-next-social-execution-ui.log`. Ruff, mypy (496 source files), Node
syntax and whitespace checks passed. Exact social creation and separate activation
are now customer-accessible when the required server capabilities are supplied;
production factories remain disabled and native qualification is unresolved.
These newer customer flows are outside frozen `8efe196` Full/CI evidence.

### Composed Archive And Closure On The Integrated Customer Flows

Integrated PR178 (`c1226b5`) coverage: owned HTTP archive with exact replacement
and social-approval documents, foreign-brand denial, local closure preserving
held/superseded reservations and original receipts, denial of new closed-brand
execution, and successful unrelated-brand execution through the customer facade.
Root focused check passed **2 tests in 10.96 seconds**, SQLite and PostgreSQL;
`/tmp/inlet-next-archive-closure.log`. Ruff, mypy (497 source files) and diff checks
passed. No production code changed in this package. The native populated restore
extension is separate and remains in progress. This is not live pilot evidence.

## B19 Populated Native Restore Recovery — 2026-10-06

Branch `codex/inlet-populated-restore`, based on `534a65c`; frozen validation head
`8efe196` was untouched. The disposable drill now builds a valid contract-test
financial graph through production mandate/optimization/replacement services: a
synchronously completed mock predecessor with explicit terminal-request evidence,
atomic qualified replacement, and a successor whose original request is unknown.
It restores and checks retained 40,000,000-micros exposure, 1,000,000-micros reported
high-water, 2,000,000-micros cumulative increases, original requests/fences, exact
replacement audit hashes/scalars, and a second workspace's strict social approval.

Available offline coordinator transport is injected after restore; fresh claiming,
original-claim replay, further replacement and refund are denied without HTTP IO.
Owner receipt/review access, scoped export sections and composite ownership FKs are
checked. A final all-row/schema/sequence/privilege fingerprint proves those checks
did not mutate evidence. The drill helper imports no tests, opens no real provider
transport, and preserves disposable-target/identity/cleanup guards. Media bindings
are metadata fixtures only: image bytes and production media recovery remain unqualified.

Validation actually run: `pytest -o addopts='' -q tests/test_inlet_restore_drill.py`
with explicit disposable PostgreSQL URL/marker and local test container: **29 passed,
no skips**, including SQLite and PostgreSQL corruption/behavior checks, actual native
custom-format dump/restore, and failure cleanup with unrelated sentinel preservation.
Five existing Alembic path-separator deprecation warnings. Whole-repository Ruff passed;
`mypy app tests` passed (490 source files, including imported drill helper); diff check
passed. Logs: `/tmp/inlet-populated-restore-tests.log` and
`/tmp/inlet-populated-restore-types.log`. The new SQLite test explicitly enables FK
checks, which the shared lightweight fixture otherwise leaves off.

No Full, live provider calls, credentials, cloud setup or production restore was run.
Remaining: composed complete customer archive/closure is a separate package; intended-
environment backup/media/key/PITR/RPO/RTO qualification and post-snapshot privacy/
revocation reconciliation remain required. Synthetic finality/exposure proof is never
native spending authority. See `docs/inlet-restore-drill.md` for boundaries.

### Integrated Populated Native Restore Evidence

Integrated PR179 (`a25dcd0`): the disposable native dump/restore now contains a
valid closed predecessor, replacement audit, unknown successor attempt and retained
40-million-micros hold, preserved charge counters, and exact social approval metadata.
The restored available offline coordinator rejects replay/replacement/refund with
zero provider I/O. Ownership foreign keys, receipt access, corrupted evidence and
post-verification fingerprint stability are checked. No production/test import
coupling was added to the self-contained drill.

Root `tests/test_inlet_restore_drill.py` passed **29 tests, no skips, five existing
Alembic configuration deprecation warnings, in 49.60 seconds**, using the explicit
disposable PostgreSQL container. Log: `/tmp/inlet-next-populated-restore.log`.
Ruff, mypy (497 source files) and diff checks passed. Media-object recovery,
production backup/key restoration, PITR/RPO/RTO and post-snapshot revocations are
not qualified. Frozen `8efe196` local Full and normal CI are still running and do
not cover this newer package.

## Continued Offline Engineering And Recovered Executor — 07:43 UTC

The exec server briefly rejected process creation with `transport disconnected`.
One bounded retry succeeded. Verified readable/writable workspace, clean root at
`fad1d005670443efa7d407f7754c3f7de0338337`, identical remote branch hash, and the
still-running outer/nested Full processes. No GitHub quota evidence or lasting
executor blocker was found. Main remains exact audit baseline `ea3591c`.

Frozen `8efe196` Full and normal hosted run 37427571832 remain in progress; no
terminal result or successor freeze yet. The second nested Full subprocess has
started, but that does not establish outer-suite or final-gate success.

Independent review reproduced PR177's stale approval-context race in both database
browser cases: configuration A's late review can become approvable after selecting B.
Saved configuration labels also fail to distinguish identity/measurement/cover
choices. A repair with request-context invalidation and explicit owned distinctions
is underway; `/tmp/inlet-review-context-baseline.log` records the two failing cases.
Backend exact-plan/ownership validation was not identified as bypassed.

The repeat-accounting review reproduced admission of a 33rd reservation beyond the
32-node ancestry reader bound. Admission repair and both-database settlement
regressions are underway. Automatic candidate selection, worker dispatch and a
revocable background authority contract remain separate missing work; existing
manual UI and reservation transfer do not supply them.

Additional packages define missing engineering separately from access: bounded
unqualified native Meta inventory; owned retained reconciliation observations with
no maturity verdict; sanitized analysis-run attention; and an environment-separated
production billing lane. Migration 0061 (down 0060) is reserved for billing scope.
No prices, live keys, provider access, spending or release approval were inferred.
## Repeat Accounting Readiness And Capacity Repair — 2026-10-06

Isolated `codex/inlet-repeat-readiness` from assembled `1c82e03` assessed current
manual customer repeat APIs/UI, durable accounting, native proof producers and the
missing autonomous candidate/scheduler path. Detailed capability/missing-code matrix,
recurring effect semantics, proposed trusted worker ports and a minimal separate
background-delegation decision are in `docs/design/repeat-optimization-readiness.md`.
No worker authority, factory, source qualification or live dispatch was enabled.

Concrete defect: a readable 32-reservation chain could admit a 33rd reservation which
historical settlement could not traverse. Baseline SQLite regression built the exact
32-chain and failed because successor preparation did not reject it. Added shared
capacity admission checks before preparation/approval/transfer without reducing the
historical reader bound or truncating audit. At capacity, late original uncertainty
still retains exposure; later original-fence read-only reconciliation and separately
qualified terminal settlement remain usable.

Checks: exact-limit/late-evidence/terminal-settlement test passed on SQLite and
PostgreSQL (2 passed). Core repeat and current customer optimization API cases passed
53 with 1 intentional SQLite row-lock skip during the combined run. That run also
had two new-test clock errors: the supposed later reconciliation reused the original
observation timestamp/content and correctly could not supersede a newer unknown
receipt. Advancing the test clock one second repaired those fixtures; final isolated
capacity rerun passed both. Product code did not change for that fixture correction.
Ruff (`app tests migrations`), mypy (`app tests`, 498 files) and diff check passed.
No Full, provider access, workflow dispatch or deployment.

Next: freeze typed non-authorizing candidate/queue contracts, then implement offline
policy selection and durable orchestration. Native terminal/transition guarantees
remain missing implementations/evidence, not credentials-only gates. Background
worker provenance must not impersonate per-action human review or weaken the original
interactive session checks. Root owns the authorization decision and integration.

### Repeat History Admission Repair Integrated

PR181 (`ce5b66d`) fixes the reproduced 32-to-33 reservation ancestry edge: further
successors are rejected before preparation, approval and transfer, while historical
readers retain their existing maximum and allow reconciliation/settlement. Root
combined history-capacity, repeat-optimization and customer optimization API suite
passed **55 tests with one SQLite-only lock skip in 142.63 seconds**; PostgreSQL
counterpart ran. Log: `/tmp/inlet-next-repeat-capacity.log`. Ruff, configured mypy
(502 source files) and diff checks passed. No exposure release, larger spending cap
or automatic authority was introduced.

Bounded Full diagnosis at 07:45 UTC: the second nested pytest process was active,
its CPU time increased, and candidate-database sessions showed no lock wait in the
sample. The first nested Full had advanced successfully to the second iteration.
This is progress evidence, not terminal Full or hosted qualification. The frozen
candidate remains unchanged and all required gates remain enabled.
### Customer Execution Approval Context And Exact Media Repair

Isolated from `1c82e03` on `codex/inlet-execution-review-context`. Actual HTTPS
browser baselines failed on both SQLite and disposable PostgreSQL: delayed social
review A became approvable after selecting B (**2 failures**), and two persisted
Meta configurations had identical labels (**2 failures**). Logs:
`/tmp/inlet-review-context-baseline.log`, `/tmp/inlet-review-clarity-baseline.log`.

The customer page now fences responses by monotonic context, captured editable
values and session nonce, including response-body parsing. Changes clear exact
approval; delayed successes/errors cannot restore old authority. Lost mutation
responses disclose uncertainty and require saved-status recovery without replay.
Selection and exact review show owned identity/measurement references plus decoded
private image/video/cover bytes checked against the canonical size and SHA-256.
Historical catalog names were not persisted; owned references are labeled honestly.
See `docs/inlet-execution-review-context.md` for boundaries.

Focused browser checks actually run, covering 40 unique cases across both databases:
18 context-transition cases (`/tmp/inlet-review-context-matrix.log`), 4 Google
journey/delayed-approval cases (`/tmp/inlet-review-google-browser.log`), 8 social
journey/configuration-clarity cases (`/tmp/inlet-review-media-journeys.log`),
4 private-media session/integrity cases (`/tmp/inlet-review-media-context.log`),
4 late-error/lost-response cases (`/tmp/inlet-review-late-failure.log`), and
2 admitted-run response-loss/recovery cases (`/tmp/inlet-review-lost-admission.log`).
All passed. A subsequent session/lost-response subset passed **8 tests**, with
32 deselected (`/tmp/inlet-review-final-session-loss.log`). These were incremental
focused runs, not a single combined run. Whole Ruff and clean mypy passed
(**501 source files**); JavaScript syntax and diff checks passed.

After the final selection reset, the policy-transition and complete Meta/TikTok
journey subset passed **6 tests**, with 28 deselected in 114.20 seconds
(`/tmp/inlet-review-context-final-reset.log`).

No backend/schema, live provider, credentials, runtime enabling or advertising
authority changes. No Full or hosted dispatch run for this repair; root owns
assembled qualification and integration.

### Integrated Exact Approval Context And Configuration Clarity Repair

Integrated PR187 (`20f4b6c`) after both reported defects reproduced in standalone
SQLite/PostgreSQL browser cases. Generation, selected context and session are checked
after fetch and response parsing. Context edits synchronously invalidate review;
captured review IDs prevent approval/run actions from switching targets. Selection
and exact review now distinguish owned Page/identity, measurement and media/cover,
with authenticated hash-checked previews. Lost responses recover saved execution
without automatic replay. No backend authority or schema changed.

Root combined social, Google and optimization browsers plus route boundaries passed
**51 tests, no skips, in 239.96 seconds**. Log:
`/tmp/inlet-next-execution-context.log`. Ruff, configured mypy (502 source files),
JavaScript syntax and diff checks passed. This successor is still outside the
unchanged `8efe196` Full/hosted validation.

The 08:06 executor notification corresponded to a child tool transport disconnect,
not a proved process failure. Root access succeeded immediately; the native assembly
worker reconnected and recovered its terminal result (203 passed). No work loss or
GitHub quota evidence was found. Frozen Full has completed both nested iterations
and advanced into its outer suite; final gates are still pending.

### Integrated Analysis Attention And 08:15 Validation Checkpoint

Integrated PR180 (`262d3cc`), observing bounded latest analysis failures and separate
overdue running analyses without claiming worker termination. Root combined
attention/provider-attention/customer activity checks: **39 passed in 26.53 seconds**.
Ruff, configured mypy (502 files) and diff checks passed. Log:
`/tmp/inlet-next-analysis-attention.log`.

At 08:15 UTC the executor is available. Frozen `8efe196` local Full completed both
nested iterations and reached 77% of outer pytest; no exitcode file exists yet.
Normal hosted run37427571832/job112150604656 remains in pytest with preflight and
migration passed; later gates remain pending. These are not terminal successes.
UI repair for independent re-review is exact pushed `c3bf9b4` (PR187 feature20f4b6c),
with root51 browser/route tests passed. No new assembled freeze until terminal checks.
## Production Spending Source Assessment And Meta Diagnostics — 2026-10-06

Isolated `codex/inlet-spending-source-gap` from frozen `1c82e03`. Durable matrix:
`docs/design/production-spending-source-readiness.md`; docs-first port committed
`66de5f5` before implementation. Exact files distinguish implemented HTTP adapters
from missing native U/F/P, finality/prevention producers, source/profile assembly,
optimization fact binding and automatic named target discovery. Owner access alone
cannot close these engineering gaps. Existing live optimization hard blocker remains.

Approved bounded next package implements actual fixed-v26 Meta account/campaign/ad-set
inventory HTTP in `app/collectors/meta_native_inventory.py`: all SDK-known status pages,
exact account/request/generation context before/after IO, owned child topology, strict
optional counters/flags, bounded wire/pagination and sanitized errors. Native counter
units/basis/epoch are explicitly unqualified; absent values remain null. Result types
cannot supply U/F/P or watermark. No factory or source-to-proof conversion is enabled.
Official pinned SDK field/edge sources are recorded in `docs/inlet-meta-native-inventory.md`.

Checks actually run: `pytest -o addopts='' -q tests/test_meta_native_inventory.py
 tests/test_google_native_inventory.py tests/test_meta_catalog_http.py
 tests/test_social_optimization_http.py` — **106 passed, no skips**. Whole Ruff and
`mypy app tests` passed (499 source files); diff/relative-link checks passed. Logs:
`/tmp/inlet-meta-native-tests.log`, `/tmp/inlet-meta-native-mypy.log`. Initial adjacent
suite command named a nonexistent catalog file and collected no tests; corrected to
`test_meta_catalog_http.py` for the passing run. No Full, provider calls, database/schema
changes, credentials, production assembly or runtime enablement.

Remaining next engineering: documented TikTok native inventory, authenticated diagnostic
assembly/cache and automatic named target discovery; provider-backed source specification
only once authoritative cap/accounting/finality/prevention semantics support it. Genuine
owner choices are a versioned monetary promise and, after a demonstrated mechanism,
acceptability of its restricted customer configurations. Strict ceiling remains; no
best-effort authority inferred and no owner decision used to hide missing code.

## TikTok Regular Native Diagnostics And Scoped Meta Status Coverage — 2026-10-06

`codex/inlet-tiktok-native-inventory`, child of PR182 `c360555`. Frozen collector and
server-assembly interface: `79c36cc`, `docs/design/native-diagnostic-assembly.md`.
Actual fixed TikTok advertiser/campaign/adgroup GET collection now covers accessible
regular endpoint inventory with bounded STATUS_ALL paging, exact advertiser/parent
ownership, stable counts, fresh generation/request context checks around every IO,
precise native decimal observations and private errors. No Budget Manager/reset/closure
schema is invented. U/F/P/watermark/cap/finality stay null; other campaign-family and
historical completeness stay false. No production factory enabled.

Parent review also clarified Meta status-query coverage in separate `5f25593`: pinned
Campaign EffectiveStatus enum has six entries, AdSet adds CAMPAIGN_PAUSED; this does not
prove all current provider statuses. Results now explicitly report SDK-known-only
status scope and false all-status completeness.43 Meta tests passed for that change.

TikTok/new-adjacent HTTP suite:107 passed, no skips; whole Ruff and mypy501 pass, diff
clean. Logs `/tmp/inlet-tiktok-native-tests.log`, `/tmp/inlet-tiktok-native-mypy.log`.
No Full, database/schema changes, credentials or live calls. Server-owned actual
vault/context assembly is separately approved next, with bothDB authorization/race tests;
this adapter package does not claim it exists or supplies qualified financial evidence.

### Native Diagnostic Server Assembly — Offline Complete

`codex/inlet-native-diagnostic-assembly`, isolated child of PR184 `78244fa`.
`NativeDiagnosticService` selects a current persisted consented account, validates its
owned integration/generation and currency/timezone, opens actual provider-bound vault
material, and composes Google/Meta/TikTok native HTTP collectors. Independent sessions
close before advertising/OAuth IO and never commit caller work. Customer authorization
is server-bound and checked before/after IO and on final return. Google refresh uses
an explicit internal helper with bounded documented expiry and an ephemeral per-read
cache. No application factory, API, schedule, provider write or financial proof enabled.

The composed SQLite/PostgreSQL tests exercise actual customer-session revocation,
role downgrade, native identity/generation changes during HTTP, revocation during
Google refresh, foreign canonical selection, stale consent, currency mismatch, expired
and wrong-workspace encrypted grants, missing transport and malformed OAuth expiry.
All diagnostic U/F/P remain null. Google collector now re-resolves authorization between
pages while preserving the earliest observation/context expiry. The expanded initial
run found an expiry extension regression (202 passed/1 failed); the corrected final
run passed all203 tests with no skips. Whole Ruff and mypy503 passed; diffcheck clean.
Commands: `pytest -o addopts='' -q tests/test_native_diagnostic_assembly.py
 tests/test_google_native_inventory.py tests/test_meta_native_inventory.py
 tests/test_tiktok_native_inventory.py tests/test_google_http_runtime.py`, using the
existing disposable PostgreSQL schema fixture and SQLite. Logs:
`/tmp/inlet-native-assembly-tests.log`, `/tmp/inlet-native-assembly-mypy.log`.
No Full, live provider calls, credentials, migrations, deployment or enabled factory.
Native qualification/prevention/finality, production mutation assembly, automatic
optimization-target discovery and diagnostic presentation remain separate code/evidence
work; provider access alone does not close these gaps.

### 2026-10-06 08:25 UTC — Native diagnostics integration and review checkpoint

Integrated frozen PR182/184/188 Meta/TikTok native diagnostics and owned vault-backed
Google/Meta/TikTok assembly. Diagnostic observations remain unqualified for spending:
no production financial exposure source, cap/finality guarantee, route or factory
is enabled by this package. Root focused checks: 181 passed, zero skipped (exit 0),
covering all four native inventory/assembly modules; log
`/tmp/inlet-next-native-assembly.log`. Ruff passed; configured mypy passed across
508 files; staged and unstaged whitespace checks passed.

Parent independently re-reviewed source at c3bf9b470d528b01c5a366b2c12d44ff1d0c238b
and closed both prior PR177 UI findings, with no further material adjacent issue.
This was source review, not independent execution of the 51 root tests.

Repeat-accounting repair integrated at a1a91e779654f5f94fe147582b46532c7ec44c8d
(PR181 frozen ce5b66de93d14de74dae41646a1bc2dd3e833602): a 32-reservation ancestry
could accept successor 33 although readers were bounded to 32. Admission now checks
capacity at preparation, approval and transfer. Focused regression builds the actual
32-entry chain, rejects successor 33, preserves the held reservation and readable
32-entry settlement snapshot, retains contradictory-evidence holds, then reconciles
and settles using qualified contract-test evidence. Root repeat/history/API checks:
55 passed, one expected SQLite-only row-lock skip; Ruff/mypy/diff passed.

Draft PR191 now records frozen candidate compiler 83e136220774dec6048dd26cd1f13cdd7610186b;
it remains non-emitting and is not yet integrated. Feedback0064 and billing offer0063
implementation continue against stable candidate0062 and billing0061 respectively.

Frozen 8efe196 local Full primary pytest completed with 2639 passed, 59 skipped,
85 warnings in 4650.54 seconds. This is NOT terminal Full success: subsequent gates
remain pending/running. Normal hosted run37427571832 is still in pytest at this
checkpoint. No manual dispatch, merge, deployment, provider access or spending.
## B17 Retained Reconciliation Observations (2026-10-06)

Branch `codex/inlet-b17-readiness`, isolated base `1c82e03`. Added an internal,
read-only owned collector with explicit incremental-terminal assurance, maximum 16
retained publications/400 local days, current goal/source/privacy fences, completion
lineage verification, per-day observed changes and retention/truncation reporting.
No maturity or action attribution qualification, recommendation update, spending
permission, endpoint, migration or provider call is enabled. See
`docs/design/b17-production-readiness.md` for the exact remaining production code,
policy calibration decision and next disabled-default registry/evaluator contract.

Validation: existing outcome/descriptive/learning suite 72 passed, 2 SQLite-specific
skips (31.28s). New collector tests 10 passed across SQLite/PostgreSQL (9.57s),
including actual terminal imports, 16-observation cap, revisions, old retention
exclusion, privacy deletion, invalid completion binding, missing coverage, foreign
workspace, stale publication/goal and final fresh authorization rejection. Related
combined run before fixture corrections had 48 passed/2 skips and two new fixture
failures; those were corrected (valid sync interval and actual fixture sales delta),
then all 10 collector cases rerun successfully. Ruff, mypy (504 files), and
`git diff --check` passed. No Full, CI dispatch, live qualification or deployment.

## B17 Parameterized Operational Maturity Evaluator (2026-10-06)

Branch `codex/inlet-operational-maturity`, isolated child of PR183 `1a08ecd`.
Added immutable versioned policy with explicit required parameters, a production-capable
server facts port, generic pure evaluator and registry/service boundary. Both policy
and independent source producer defaults return None. Existing incremental terminal
imports cannot qualify, even under permissive policies. Fixture/live isolation, exact
scope/privacy/goal/source, complete calendar coverage, chronology/freshness, revision
envelope and correction predicates fail closed. Operational qualification is never
finality or causal attribution; no recommendations or spending authority are added.

Frozen contract and proposed next v3 bridge/feedback/retraction interfaces:
`docs/design/b17-operational-maturity-interface.md`. Genuine independent full-window
and authoritative timing producers, owned bridge and feedback/retraction consumer
remain missing code, distinct from owner parameter calibration/live qualification.

Validation: 39 passed in 7.81s (29 pure synthetic boundary tests and 10 actual retained
collector cases across SQLite/PostgreSQL, including proof current imports cannot
qualify). Ruff, mypy (506 files), and diff checks passed. No Full, manual CI dispatch,
API, migration, production policy installation, provider calls or deployment.

## B17 Read-Only Owned V3 Bridge (2026-10-06)

Branch `codex/inlet-owned-outcomes-v3`, isolated child of PR185 `b100317`.
The bridge reads actual owned current receipt/account/goal/source evidence in its
own session, releases database locks before producer IO, then reauthorizes and
rechecks latest receipt, source/privacy/goal and policy in a new fenced session.
No caller transaction is committed. Actual default registries/timing remain
unavailable and yield insufficient. The pure bridge supports future qualified
server facts with strict authoritative interval separation, equal complete local
windows/as-of and exact association arithmetic; it confers no causal attribution,
recommendation or spending authority. Existing v2 persistence/history is untouched.
No endpoint, migration or production producer is installed.

`docs/design/b17-v3-feedback-contract.md` defines the proposed strict v2/v3 document
union and concrete idempotent feedback/contribution/dependency schema, including
privacy retraction and candidate invalidation integration. Persistence and decision
policy remain unimplemented/uninstalled, pending root schema review.

Validation: final new SQLite/PostgreSQL suite 14 passed (20.17s): actual receipt
insufficiency, foreign ownership, unchanged v2 storage, synthetic qualified timing,
zero/negative/large exact values, and independently committed goal/privacy/account/
session/latest-receipt changes during producer IO. Separate-session workspace/goal
locks prove no bridge locks survive into producer IO. Earlier combined v2/v3/pure
suite 50 passed, 1 SQLite-specific skip (31.48s); final added receipt races and exact
large arithmetic were covered in the final 14-case run. Ruff, mypy (508 files), and
diff checks passed. No Full, manual CI dispatch, live call or deployment.

### 2026-10-06 — Outcome foundations assembled after native diagnostics

Integrated PR183/185/189 bounded reconciliation observations, immutable operational
maturity evaluation and owned read-only v3 bridge. Root tests: 62 passed, one
expected SQLite row-lock skip in37.45s (`/tmp/inlet-next-outcomes-v3.log`); Ruff,
configured mypy515 files and staged whitespace checks passed. No independent
production reconciliation/delivery-time producer or numeric policy is registered.
Feedback storage/retraction remains in isolated0064 work; association is not causal
performance direction or spending authority.

Parent bounded source review closed PR181 at c0e10dc with no material finding;
review inspected the actual32-chain regression but did not independently run55checks.
Google original-response evidence capture is approved as an additive source only,
not ClosedOriginalRequest classification or financial release. Migration0066 down0060
reserved; final root merge0067 will join0063,0064,0066. The earlier proposed0065
was never created and is unused.

### 2026-10-06 — Environment-scoped billing foundation integrated

Integrated PR186 frozen0efe061. Billing identity now includes provider/environment/
merchant account across records, events, recovery and ownership. Legacy test rows
cannot grant live entitlement; live provider mandates require scoped paid entitlement.
Root tests106 passed, one SQLite row-lock skip,13 Alembic warnings in45.61s
(`/tmp/inlet-next-billing-scopes.log`). Ruff check . caught two long migration SQL
strings; formatting-only fix applied. Ruff now passed, configured mypy519 files passed,
whitespace passed. Offer qualification0063 is a separate pending package; no commercial
price/defaults, live configuration, purchase or release enabled.

Frozen8efe196 localFull primary2639 passed59 skipped; subsequent Ruff, mypy,
PostgreSQL transaction/migration roundtrip, read-only/security/privacy gates completed.
Final focused gate includes another nestedFull regression and remains running.
Hosted run37427571832 remains nonterminal.

### 2026-10-06 — Commercial offer qualification integrated

Integrated PR193 frozen43b7e38. Exact immutable offer binding, configured-price and
provider-object qualification, paid invoice/payment/charge lineage, original-key
config-drift recovery and failed-fresh-qualification entitlement invalidation are
implemented. No prices, production allowance or live settings enabled. Root checks:
111 passed, one expected SQLite lock skip,13 migration warnings in91.76s, including
browser purchase/recovery and retained settlement (`/tmp/inlet-next-billing-offer.log`).
Ruff check . passed after formatting-only0063 SQL literal split; configured mypy524
files and whitespace passed. Additional production assembly binding is being audited;
unsupported commercial shapes still require code if selected. Offline fixtures do not
qualify a live purchasable release.
## 2026-10-06 — Nonemitting Optimization Candidate Queue (0062)

Branch: `codex/inlet-optimization-candidates`, child of repeat-readiness
`ce5b66de93d14de74dae41646a1bc2dd3e833602`. Draft PR pending parent connector action.

Implemented strict server candidate/evidence/policy contracts, bounded budget
compiler and durable owner/original-session-bound read jobs. Numeric policy and
learning registries default unconfigured. Runtime factory returns None. Jobs
recheck account/mandate/goal/source/receipt/privacy/session after source I/O;
lease/fence/backoff apply only to non-emitting reads. All outputs require fresh
separate execution admission and grant no spending authority. Current descriptive
v2/v3 assessments cannot be promoted into measured learning by registration.

Migration0062 down0060, canonical registry, strict export and local-work/closure
classification are explicit. Privacy, commerce correction/new publication and
receipt append erase derived jobs/results transactionally while retaining all
financial/receipt history. Historical pre0062 fixture helper asserts table
absence and no-ops only new candidate erasure hooks; production has no missing
schema fallback. See `docs/design/nonemitting-optimization-candidates.md` for
interfaces, exact limits and remaining automatic-optimization code.

Checks actually run:

- Current-head candidate/commerce/owned-outcome/closure suites: **91 passed,
  1 expected SQLite concurrency skip** (72.31s).
- Expanded candidate suite plus populated0062 roundtrip and historical replacement,
  owned-outcome, commerce-publication and social-configuration migrations:
  **41 passed** (41.34s), both database backends for parametrized tests.
- Added final two-tenant fairness regression: **2 passed** (SQLite/PostgreSQL;
  36 deselected), one failed source backs off while another completes.
- Ruff whole repository: pass. Mypy app/tests: **511 files pass**. Diff check: pass.
- Intermediate failures were fixed: wrong platform-control accessor; test principal
  detachment/FK setup/expected native amount/clock/issuer; no interrupted or failed
  run is counted as passing. One attempted test selection used a nonexistent
  filename and collected no tests; corrected selection produced91pass result.

No Full, live calls, workflow dispatch, merge or deployment. Actual native
exposure/finality/transition sources, attributed learning, automatic target policy,
emitting scheduler and explicit long-lived delegation remain missing. This is
non-authorizing candidate groundwork, not completed autonomous optimization.

## 2026-10-06 — Session-Bound Candidate Selection And Provenance

Branch `codex/inlet-candidate-selection`, isolated child of PR191 frozen83e1362.
Shared contract approved before implementation; no schema0064 or feedback edits.

Added server-only current-mandate target discovery/selection and atomic v2 job
admission. Exact observed native budget owners must match the full approved target
set. No child substitution, inferred target expansion, performance ranking or
numerical defaults. Repeated catalog content checks and current session, role,
mandate, source/privacy/policy and post-lock clock checks fence admission. Insert
rollback is atomic; fresh clock after flushed writes rejects expiry before commit.
Worker rejects v2 observation state drift before storing a suggestion.

Separate `CandidateWorkV2` stores selection/catalog/state/manifest provenance.
Original CandidateWork v1 bytes/digest remain unchanged; one discriminated parser
serves storage and strict export. No emitting authority, provider mutation,
reservation or approval is created. Default selection factory returns None.
See `docs/design/candidate-selection-orchestration.md` for exact ports/limitations.

Validation actually run:

- Initial combined selection/candidate suite:61 passed,3 expected SQLite row-lock skips.
- Expanded selection/candidate/populated0062 migration suite:66 passed,3 expected
  SQLite skips (74.02s); includes actual Google/Meta/TikTok MockHTTP catalogs to
  durable v2 jobs and nonemitting result, old v1 compatibility/export, role/privacy/
  expiry during controlled PostgreSQL workspace-lock waits, owner-only selection,
  dedup/order, contradictory snapshots, foreign scope, tamper and insert rollback.
- Final fresh-clock refinement selection suite:29 passed,3 expected SQLite skips
  (26.76s), including expiry during a flushed insertion rolling back all jobs.
- Ruff whole repository, mypy514 app/test files, diff check:pass.
- Test fixture errors corrected during development: invalid membership role name,
  wrong mocked Google amount property and imported type reference; failed runs are
  not counted as passing. No Full, live call, dispatch, merge or deploy.

Remaining: actual production runtime assembly/source registry and mature attributed
direction/numerical decision policy, native exposure/finality/transition sources,
automatic emitting scheduler and explicit long-lived delegation. Catalog readback
has no provider CAS; later external changes require fresh worker/execution checks.
This package closes structural candidate assembly/provenance only.

### 2026-10-06 — Candidate preparation and selection integration

Integrated PR19183e1362 and PR1941aed881: owned non-emitting candidate queue plus
server-side exact native-owner selection, versioned provenance, original-session
authority and atomic batch admission. Billing/candidate export registrations merged
additively with discriminated v1/v2 parser. Root checks88 passed,3 expected SQLite
row-lock skips in128.81s (`/tmp/inlet-next-candidate-selection.log`), Ruff check .,
configured mypy536 files and whitespace passed. Migration0062 is a separate branch
from0061/0063 until final0067 merge; assembled migration/Full checks remain pending.
These packages do not complete automatic emitting optimization or qualified learning.

### 2026-10-06 — Production billing assembly bypass repaired

Integrated PR196 frozen ac2a6019603037de9f43f287a2540422ba2eb5bf. Exact defect:
production paid_work used billing mode rather than production environment to select
strict live enforcement; mode disabled/test plus billing_required=false admitted
paid operations. Baseline8 failed assertions across SQLite/PostgreSQL included four
actual app.main media uploads returning200. Repair always routes production paid_work
through live_paid_work, refuses production test transport and prevents unavailable
production status falling back to legacy test billing evidence.

Root checks144 passed in45.08s across assembly/scopes/offers/customerbilling/runtime
scheduler (`/tmp/inlet-next-billing-assembly.log`); Ruff check ., configured mypy537
files and staged whitespace passed. No schema/price/live permission changes. Original
receipt/settlement lanes remain retained. Separately approved receipt-only original-
binding recovery factory is in progress and remains default-off/GET-only.

Frozen8efe196 localFull remains in final focused gate nestedFull; normal hosted
run37427571832 remains in pytest. Neither has terminal result. No gate weakened or
manual dispatch attempted. Google evidence PR195 is ready but not integrated; feedback
0064 and independent Shopify acquisition continue. Final merge0067 waits on0064/0066.
### Original Google Response Capture — Offline Complete, Not Financial Finality

`codex/inlet-google-completion-evidence`, isolated child of docs PR192 `36e3402`.
Added sanitized typed capture only for exact successful original Google v25 single-update
budget/PAUSED responses, plus owned append-only durable reader. Shared normalized response
JSON remains unchanged; no ClosedOriginalRequest mapping, financial proof, hold release or
factory enabled. Timeout/unknown/legacy acknowledgment cannot manufacture capture.
Migration0066 down0060 creates the separate scoped record and refuses populated downgrade.
The registry protects it; typed exports, actual customer closure and native PostgreSQL
backup/restore preserve the original request/fence linkage and held financial obligations.

Primary v25 service schema read/pinned to googleapis7c0638cf893464ba844aeb04683026406eb3f8ca.
The source matrix documents remaining unknown-request, delivery/cost residual and preventive
writer guarantees; a completed configuration operation is not settled spend or financial
finality. No live provider calls or widened write authority.

Validation: focused composed HTTP/durable/export/lifecycle/native restore suite112 passed,
1 SQLite-only row-lock concurrency skip; additional actual closure-retention checks2 passed
(SQLite/PostgreSQL). Whole Ruff and mypy507 pass; diffcheck clean. Native restore exercised
real pg_dump/pg_restore, empty migration roundtrip, populated downgrade refusal, foreign
workspace FK rejection and original attempt retention. Initial export test exposed internal
scalar projection mismatch; fixed without widening export allowlists. An initial new unit
fixture used the wrong clock and was corrected. Logs `/tmp/inlet-completion-tests.log` and
`/tmp/inlet-completion-mypy.log`. No Full performed. Both runtime qualification and any
mapping into authoritative request closure remain deliberately separate review/code work.

### 2026-10-06 — Durable Google original-response evidence integrated

Integrated PR192/195 (36e3402/18466e2): exact successful synchronous original
response capture, protected owned durable record/reader, strict export, closure
retention and native dump/restore. No ClosedOriginalRequest mapping, money release,
fallback for unknown responses or production qualification. Root first command used
a nonexistent test filename and collected no tests; corrected combined suite69
passed with one restore failure caused by current candidate helpers on isolated0066
schema. The fixture now preserves its exact0066 roundtrip, then upgrades all actual
heads before composed current-code population. Native restore rerun1 passed,5 Alembic
warnings in19.01s. Whole Ruff and configured mypy541 files passed; whitespace passed.
Logs `/tmp/inlet-next-google-completion.log` and `...-restore.log`.

Independent source review closed PR196 at ac2a601/integrated56514e7; no independent
test execution claimed. Corrected documentation: connection setup/Google selection
use separate connection limits, not paid_work. No new paid setup requirement added.

Frozen8efe196 HOSTED TERMINAL FAILURE: run37427571832/job112150604656 checked out
80e432a072d4970fd4fe50c23b1a913257e99250 (same frozen tree11252fdb). Outer2 failed,
2643 passed,53 skipped,85 warnings in5113.53s. Meta consent PostgreSQL browser failed
workspace options/enabled readiness; same Meta failure in nested suite1 failed,
2643 passed,54 skipped, causing outer nestedFull wrapper failure. Media preflight
and upgrade passed; later gates skipped. Bounded diagnostics upload succeeded,
artifact11399840346. Complete log `/tmp/inlet-pr130-8efe-hosted.log` retained; focused
root-cause investigation assigned without timeout relaxation. Local frozenFull remains
in its final focused nested regression, primary2639pass59skip and intervening gates
passed; no terminal local result yet. No manual dispatch, merge, release or quota signal.

Schema plan update: candidate-to-review provenance0068down0062 approved; final root
merge0069 will join0063,0064,0066,0068. Proposed0067/0065 were never created.

### 2026-10-06 — Unstarted analysis obligation attention integrated

Integrated PR19071c4550: bounded overdue analysis obligations from owned completed
imports without a corresponding AnalysisRun; fixed inspect-local-job reason only,
no automatic retry or fabricated historical generation. Root checks67 passed in48.16s
(`/tmp/inlet-next-analysis-obligation.log`), Ruff check ., configured mypy542 and
whitespace passed. Initial command named a nonexistent test module and collected
no tests; corrected command used actual attention/activity modules.

At08:45 parent reported another transport disconnect notification. Executor commands,
filesystem read/write probe and in-flight root test progression succeeded immediately;
no observed work loss, process death or quota signal. Frozen local final focused gate
nested pytest remains active,20min elapsed with10min CPU at this checkpoint.

### 2026-10-06 — Original-bound receipt recovery and closure classification

Integrated PR19820efeaac: default-off GET-only original-bound receipt reader and
actual bounded scheduler path independent of current sales offer. Missing/invalid
current offer still blocks forward entitlement; no-ID unknown checkout stays
unresolved without request replay/key replacement. Root combined140 passed2failed:
new Google completion table was absent from lifecycle local-work suffix registry,
so both closure API cases correctly refused incomplete classification. Added explicit
protected_publication classification; final receipt/quiescing suite41 passed in24.98s.
Ruff check ., configured mypy545 and whitespace passed. Logs
`/tmp/inlet-next-billing-receipts.log` and `/tmp/inlet-next-receipts-quiescing.log`.
### Frozen CI Meta Browser Startup Repair

`codex/inlet-meta-browser-ci-repair`, isolated from frozen8efe196. Hosted run37427571832,
job112150604656 checked out merge80e432a072d4970fd4fe50c23b1a913257e99250 (8efe196 into
main ea3591c). Its outer and nested Full failures identify the first Meta workspace
selection, immediately after login and Retry. Candidate worktree/Full database untouched.

Deterministic isolated PostgreSQL reproduction held the initial anonymous session GET
while login completed: sanitized DOM before Retry was disabled=true/bound=true/options0;
HTTP statuses were POST/session200 then initial GET/session401; final DOM was Retryenabled
with options0 and no second session/workspace request. The synthetic disabled click was
dropped. This is the Meta browser fixture synchronization gap already guarded in Google
and Shopify fixtures, not a reproduced product defect. Repro log:
`/tmp/inlet-meta-browser-repro.log` (only selected DOM flags and method/path/status).

The repaired harness preserves the forced overlap, releases the initial probe and waits
for the bound enabled Retry control before one click. No timeouts relaxed, tests deselected,
product behavior changed or live providers contacted. Actual Meta consent/cancel/back/retry/
selection/role/session/disconnect browser journey passes both SQLite and PostgreSQL:
2 passed in14.25s. Dedicated disposableDB inlet_meta_browser_ci. Whole Ruff and mypy485
pass; diffcheck clean. Logs `/tmp/inlet-meta-browser-repair-tests.log` and
`/tmp/inlet-meta-browser-repair-mypy.log`. No Full run by this repair package.

### 2026-10-06 — Hosted browser race and historical fixture repairs integrated

Integrated PR199b04cab6 and PR200dcbdba4. Meta harness baseline deterministically
clicked disabled Retry while initial session probe was pending: no retry request
was sent. Test now holds/releases that probe and waits for bound+enabled control
before the one click; no product change/timeout relaxation/deselection. Root Meta
browser plus primary privacy migration regression4 passed,3 warnings in13.23s.
Other six affected historical migration definitions13 passed,1 expected SQLite skip,
20 warnings in12.96s. Fixtures use real migrated disposable schemas rather than
fictitious stamped ORM history. All prior backfill/ownership assertions remain.
Ruff check ., configured mypy546 and whitespace passed. Logs
`/tmp/inlet-next-ci-fixtures.log` and `/tmp/inlet-next-historical-migrations.log`.
## B17 Owned V3 Feedback Persistence And Retraction — 2026-10-06

Branch `codex/inlet-feedback-contract`, worktree `/workspace/inlet-feedback-contract`,
starts from frozen v3 bridge189 and candidate191 (integration base37e9b84).
Migration0064 follows0062; root owns the subsequent integration join.

Implemented separate strict v3 assessment storage, bounded owned multi-publication
lineage, required-parameter association scoring, idempotent feedback, ABA-safe slot
CAS and active-set recomputation without cached numeric totals. Production maturity
and decision policies remain unset. Actual current sources produce no eligible
feedback. There is no new customer route or live execution authority.

Any dependency erasure removes the whole numeric assessment and dependent feedback.
Retraction and slot replacement clear workspace-wide derived candidate caches even
when anchored to another publication; unrelated brands and financial history survive.
Triggers advance export privacy revisions. PostgreSQL raw mutation guards use NOWAIT
workspace locking; contention fails transactionally without automatic retry.
Existing source/privacy/receipt/closure invalidation composes through shared helpers.
Strict lifecycle exports include the new owned types.

Final focused command: `pytest -o addopts='' -q tests/test_feedback_policy.py
 tests/test_feedback_storage.py tests/test_feedback_races.py
 tests/test_feedback_migration.py tests/test_candidate_migration.py
 tests/test_model_registry.py` with disposable PostgreSQL configured: **36 passed,
1 SQLite row-lock skip, 6 existing Alembic configuration deprecation warnings**,59.56s.
Tests include actual SQLite/PostgreSQL repeatable export-snapshot races, raw PostgreSQL
NOWAIT contention plus explicit later retry, populated migration downgrade/reupgrade,
slot replacement/replay, historical-dependency erasure, unrelated-brand isolation and
actual closure rollback/commit. Earlier expanded regression run:67 passed,2 skipped
(before final guard additions). Final Ruff changed-file checks and mypy529 files pass;
`git diff --check` passes. No Full, CI dispatch, live provider or production DB calls.

Remaining: genuine independently complete source and authoritative delivery timing,
qualified/calibrated production policy values and customer v3 projection. These code
and evidence gates are distinct; B17 acceptance remains incomplete. Raw conflicting
mutations must retry explicitly in a fresh workspace-first transaction; no background
blind retry is introduced. Shared model/export/lifecycle registrations require additive
integration with other frozen packages.

### 2026-10-06 — Retractable owned feedback assembled

Integrated PR201a33c9b3: immutable owned v3 assessments and multi-publication
dependencies, idempotent contributions/CAS slots, transactional full-document
retraction, candidate invalidation and export revision fences. PostgreSQL raw
delete contention fails immediately through workspace NOWAIT rather than inverted
lock waits. Root feedback/storage/race/migration and candidate selection checks:
61 passed,4 expected SQLite lock skips,3 Alembic warnings in75.40s. Ruff check .,
configured mypy557 and whitespace passed (`/tmp/inlet-next-feedback.log`).
No production maturity/decision values or genuine qualified sources enabled.

Hosted frozen8efe196 failure mapping remains exact:
- test_meta_customer_browser_consent_selection_disconnect[postgres]: deterministic
  disabled-Retry click, addressed by PR199b04cab6 integrated6a41d9f; root bothDBpass.
- test_full_validation_can_run_twice_against_same_disposable_database: wrapper
  failed because nestedFull had the same MetaPGbrowser failure, targeted by the
  same repair. This wrapper has NOT passed on the assembled successor yet.
PR200 migration fixture repairs address separately reproduced later-code regressions,
not an additional failure in that frozen hosted run. Focused green checks do not
clear the historical failed Full/CI result. Local frozenFull final nested test remains
running; first nested iteration progressed through primary pytest into latergates.

08:50 disconnect report: shell/filesystem probes and running Full PIDs verified alive;
no observed lost work. Remote preservation is verified only after successful push
and exact remote hash comparison, not from local commits alone.
### Independent Shopify Full-History Acquisition — Offline, Unqualified

Branch `codex/inlet-independent-acquisition`, isolated from `9e56413`; typed
interface frozen first at `084c119`. `IndependentAcquirer` now executes fixed
GraphQL requests through an injected HTTP transport and freshly traverses all
accessible order/agreement/sale pages from an empty cursor. It reuses the existing
merchandise metric, including refunds on processing date from ancient orders,
retaining only requested-window aggregate output. Actual granted scopes and shop
identity/basis are checked at both ends. Bounded I/O, strict parent/cursor checks,
order mutation checks and fresh injected authority/privacy/retention fences fail
closed. No database write, scheduler or default runtime was added.

`ScanCompletion` always reports correction unresolved, snapshot/finality unavailable
and maturity unqualified. No completion is cast to eligible maturity evidence;
production maturity/producer registries remain None. A DB-backed original-session
and privacy authority adapter and reviewed versioned publication/export integration
remain required. The feedback owner confirmed existing owned publication FKs can
support a strict new manifest variant, but no persistence edits or migration were
made. See `docs/inlet-independent-acquisition.md` and the research proposal.

Validation: **38 focused contract/MockTransport tests passed** in 0.31 seconds,
covering ancient-order refunds, actual granted scopes, complete nested/multiple
pages, cross-parent responses, mutations, privacy/session/generation/retention
changes, zero, tax exclusions, DST, throttles/errors, byte/request/order/deadline
bounds and sanitized logs. All five GraphQL operations passed connected Shopify
schema validation (tool exposes no API-version selector; not claimed as pinned
schema validation). Whole Ruff, clean mypy (**523 source files**) and diff checks
passed. No live Shopify or advertising calls, credentials or Full run.

Wider existing commerce/maturity regression on SQLite/disposable PostgreSQL:
**110 passed, 1 failed**, two Alembic deprecation warnings. Failure is existing
`test_privacy_migration_backfills_existing_measurement_identity[postgres]` during
billing-table downgrade: `pk_customer_workspace_billing` constraint absent.
This acquisition package changes no billing or migration code; parent notified for
assembled qualification. Logs: `/tmp/inlet-independent-tests-final.log`,
`/tmp/inlet-independent-regressions.log`, `/tmp/inlet-independent-mypy-final.log`.

### 2026-10-06 — Independent bounded Shopify acquisition integrated

Integrated PR197084c119/df2cad9: fresh bounded all-history HTTP enumeration with
actual granted-history scope proof, ancient-order refunds on processing date, nested
parent/cursor validation, mutation checks and current privacy/session/retention
fences. Independent acquisition remains unresolved/unqualified for maturity; DB
publication/authority/export successor is in progress. Root109 passed,3 Alembic
warnings in29.13s across acquisition, commerce measurement and maturity evaluation
(`/tmp/inlet-next-independent-acquisition.log`). Ruff check ., configured mypy561
and whitespace passed. Updated current acceptance matrix to distinguish newly
implemented billing/feedback/selection from remaining ordinary code and genuinely
unavailable provider guarantees. Main reconfirmed ea3591c5086fbf2cee8038bf9208ac7f0050de75.
## 2026-10-06 — Candidate To Exact Optimization Review Bridge (0068)

Branch `codex/inlet-candidate-review`, isolated child of PR1941aed881. Shared
schema/guard/writer contracts approved before implementation. Migration0068 down0062.

Implemented server candidate-result→initial/repeat exact review preparation with
original-session authority, current scope/source/policy, exact action/state binding,
server-resolved retained predecessor and cumulative allowance checks. Worker stops
at `review_required`; it never fabricates customer approval or creates an attempt.
Actual all3-provider offline composition performs a separate explicit harness
customer approval before the existing durable claim/HTTP/readback flow.

Atomic review+minimal protected provenance uses a default-false marker to prevent
missing links falling back to manual semantics. Candidate deletion sets the optional
composite FK null; forward review/approval/reservation/claim/final emission gates
reject it. Financial qualification clocks are resampled after blocking provenance
guards. Final link reload/row lock catches concurrent dependency-FK retraction.
No measurement bodies or session digest enter customer export. Historical same-fence
reconciliation and qualified settlement remain available after erasure. Populated
downgrade refuses to discard forward fences or protected commitments.

Validation actually run:

- Initial actual three-provider journey/guard suite16pass; early guard+historical
  migration suite22pass; expanded initial/repeat/erasure/settlement journey26pass.
-0068 empty roundtrip/populated refusal plus0062/0058/0057/0059 historical fixtures:
  **5 passed**, disposable PostgreSQL (12.80s).
- Broader bridge/migration/durable optimization/repeat/lifecycle regression:
  **114 passed,2 expected SQLite concurrency skips** (163.83s).
- Fresh guard/rollback/unknown/repeat/privacy refinement:34pass, then final FK race
  refinement **35 passed,1 expected SQLite row-lock skip** (91.22s).
- Strict provenance export: **2 passed** (both DBs,36 deselected).
- Ruff whole repository; mypy **520 app/test files**; diff check:pass.
- Fixture-only development errors (optional return flag and union narrowing) were
  corrected; failed/interrupted runs are not reported as passes. No Full run.

Historical pre0068 tests explicitly assert the new table absent and stub only its
new forward guard; deferred default marker avoids querying a nonexistent column in
historical producer fixtures. Current0068 tests use the real schema and guard.
No production missing-schema fallback. Root must test composed0064 historical
feedback dependency erasure→candidate deletion→0068 guard denial after integration.

Docs/runnable command: `docs/design/candidate-review-orchestration.md`;
`pytest -o addopts='' -q tests/test_candidate_review_bridge.py`.
Remaining actual automatic mandate-derived admission is a separate code contract,
not a human approval surrogate. Native qualification/learning/transition sources,
production assembly and logout-independent delegation remain unavailable. No live
calls, workflow dispatch, main merge or deployment.

### 2026-10-06 — Candidate-to-review provenance and offline journey integrated

Integrated PR2024121c17. Current owned candidate now prepares exact initial/repeat
review with atomic minimal provenance, original-session guard, and final-forward
retraction checks. All3 actual provider adapters exercised in offline journeys with
separate harness customer approval, never worker-fabricated approval. Root62 passed,
1 expected SQLite skip,1 migrationfixturefailure: isolated0068 lacked sibling0064
tables required by current composed helpers. Preserved exact0068 roundtrip, then
upgraded actualheads before composedscenario. Historical0064 fixture explicitly stubs
only nonexistent0068 guard after absence assertion; no production fallback. Final
review/feedback migration2 passed,8 warnings in10.90s. Ruff check ., configured mypy567
and whitespace passed. Logs `/tmp/inlet-next-candidate-review.log` and
`/tmp/inlet-next-review-feedback-migrations.log`. Combined dependency-cascade→claimed
review retraction with protectedGooglecapture is assigned to feedback consumer package.

Broader assembled lifecycle/export check before bridge:160 passed,2 expected SQLite
lock skips in218.13s (`/tmp/inlet-next-composed-lifecycle.log`). No finalFullsuccess.

Approved next actual session-bound automatic decision package reserves0072down0068;
separate start intent/admission/run authority, no fake humanapproval, no logout-
independent grant and defaults disabled pending real sources/policies. B19 bounded
operational observations reserves0070down0060. Finalrootjoin0073 will join0063/0064/
0066/0070/0072. Prior proposed0065/67/69/71 were nevercreated.

### Narrow Google Original Request Terminal Producer — Offline Complete

`codex/inlet-google-request-terminal`, isolated child06dab9a. Added a server-owned
read-only batch producer mapping exact retained Google v25 single-update success captures
to `ClosedOriginalRequest.basis=authoritative_request_terminal`. Assertion remains original
configuration request completion, never delivery/cost finality or later-effect-impossible.
Mandatory current server authorization and consent/account checks precede reconstruction
of the full persisted ancestor/receipt/accounting snapshot. Any unsupported or missing
capture rejects the entire result; no partial closure set, source registration, provider
IO, schema migration, hold update or caller commit is performed.

Actual two-request Google chains verify exact mapping on SQLite/PostgreSQL. A timed-out
original whose readback succeeds still rejects, as does a mixed lineage with legacy
acknowledgment lacking capture. Tests also reject omitted ancestors, altered fences,
environments, unsupported providers, foreign actor/revoked authority, corrupt capture,
future recorded evidence and changed high-water snapshot epoch. Future/expired batch
validation and forbidden later-effect basis are covered. Closure-only batch cannot become
ReplacementEvidence; actual repeat admission remains blocked with no transition source.
Held/superseded financial amounts remain unchanged.

Validation: `pytest -o addopts='' -q tests/test_google_request_terminal.py
 tests/test_google_completion_evidence.py tests/test_repeat_optimization.py`:
75 passed,1 SQLite-only row-lock concurrency skip in150.87s. Whole Ruff and mypy559 pass;
diffcheck clean. Logs `/tmp/inlet-terminal-final-tests.log`, `/tmp/inlet-terminal-mypy.log`.
Dedicated disposableDB inlet_meta_browser_ci; no Full/live calls/default factories.
Source matrix explicitly preserves unknown-request lookup, U/F/P, compatible financial
basis and preventive-writer gaps. Those are not replaced by this narrow closure source.

### 2026-10-06 — Concrete Google synchronous request terminal producer

Integrated PR2036f38e20: mandatory-authorized reconstruction of complete owned
replacement snapshot maps exact durable successful Google synchronous single-update
captures to authoritative_request_terminal. This reviewed narrow inference concerns
configuration request completion, not delivery/cost/future exposure. Missing/legacy/
timed-out/unsupported ancestors reject the whole batch; transition and portfolio
proofs remain mandatory, default registration disabled, no holds released.
Root75 passed,1 expected SQLite row-lock skip in106.63s
(`/tmp/inlet-next-google-terminal.log`), Ruff check ., configured mypy569 and whitespace
passed. No schema or provider calls.

A later read-only executor call explicitly failed with transport disconnected; one
bounded retry restored shell/read-write access, root remained clean before this
package and frozenFull processes remained alive. Affected agents independently
recovered preserved work. No quota signal or verified process/data loss.

### Independent Publication V2 And Original-Session Authority

Dependent child `codex/inlet-independent-publications` implements actual bounded
Shopify acquisition -> fresh original-session/source/privacy authority -> atomic
owned v2 publication -> authenticated provenance read -> strict archive export.
The same publication ownership FK and source-wide erasure remove both versions;
no schema migration is added. V2 commits the exact aggregate acquisition with a
new domain-separated completion digest, acquisition interval (no source watermark),
and unresolved/unqualified state. No maturity/producer/default runtime is enabled.

Legacy v1 stored bytes/digests remain unchanged. SQL version filters preserve v1
latest/default measurement, descriptive/reconciliation and candidate source fences
when a v2 revision is added. Genuine source/privacy changes still deny/erase.
Historical v2 read needs current session/ownership/source/privacy/retention, not an
unchanged token or incremental source revision. Acquiring/publishing does recheck
those exact source bindings. No token refresh or Shopify HTTP runs under DB locks.

First focused DB validation: **38 passed** on SQLite and disposable PostgreSQL
in 55.61 seconds, including actual tar archive, late stored-session/role/provider/
privacy/source changes, v1 coexistence/candidate validity, erased/closed-source and
retention deletion, unsupported JSON/digest rejection and final-commit revocation.
Ruff, clean mypy (**544 source files**) and diff checks passed. Logs:
`/tmp/inlet-independent-owned-freeze.log`,
`/tmp/inlet-independent-owned-freeze-types2.log`.
Feedback resolver integration and wider regression are the next validation step.

### Independent Publication V2 — Integrated Validation

Merged frozen root06dab9a while preserving v1 bytes and version-aware selection.
The feedback resolver now accepts exact owned v2 provenance for insufficient
assessments, matches environment and full metric/goal/source scope, and rejects
unresolved v2 completions as maturity support. Actual MockTransport acquisition ->
publication -> insufficient assessment dependency -> deletion cascade passes both
SQLite and PostgreSQL. No production policy/producer or runtime is installed.

Integrated regression: **205 passed, 3 skipped, 4 failed** initially. All four
failures were existing 409-vs-404 assertions for owned malformed binding; stricter
manifest validation ran earlier and had mapped these to unavailable. Repaired the
error distinction, preserving foreign/erased/retention 404 and raw digest behavior.
Final affected consumer plus acquisition/publication suite: **81 passed, 1 skipped**
(69.84s). Export regression: **47 passed, 1 skipped** (117.02s). Added feedback
provenance/maturity denial tests: **2 passed** (both databases). Whole Ruff, clean
mypy (**564 source files**) and diff checks passed. SQLite-only concurrency skips
remain explicit. No Full run; parent owns assembled qualification.

Logs: `/tmp/inlet-independent-integrated.log`,
`/tmp/inlet-independent-compatibility.log`, `/tmp/inlet-independent-feedback.log`,
`/tmp/inlet-independent-export-regression.log`,
`/tmp/inlet-independent-final-types.log`. A transient execution transport disconnect
occurred after these processes; a subsequent harmless read succeeded and confirmed
terminal logs and preserved files. No GitHub quota block was reported.

### 2026-10-06 — Owned independent commerce publication integrated

Integrated PR204 e8ae8ea/9ade644: original-session DB authority adapter, atomic
v2 publication, strict owned manifest/digest parser, read/export and privacy/
retention erasure. Latest supported-v1 readers and candidate fences preserve
existing measurement behavior; v2 acquisition interval is not a watermark and
unresolved completions cannot establish maturity. Root73 passed,1 expected SQLite
row-lock skip in70.45s (`/tmp/inlet-next-independent-publications.log`); Ruff check .,
configured mypy572 and whitespace passed. No migration, production policy/source
registration or live request.
## B17 Canonical Feedback Consumer And Composed Retraction — 2026-10-06

Branch `codex/inlet-feedback-snapshot`, worktree `/workspace/inlet-feedback-snapshot`,
base `c2e43b9236a5affeca7516d37783ec80bbc0a3f0`. Added server-only canonical
scope, owned apply orchestration and a bounded provenance-rich association snapshot
over actual persisted feedback. It rechecks current session/receipt/goal/source/plan
and policy. Empty, unavailable and nonempty zero scores are distinct. Initial grouping
supports existing-campaign optimization only; activation mapping and directional
candidate consumption remain missing code. Default policies stay None; actual
unqualified inputs cannot create eligible feedback.

New snapshot cases passed across SQLite/PostgreSQL; combined snapshot/policy/storage
suite: **36 passed** (89.26s). New composed0064→candidate→0068 tests: **4 passed**
(14.23s), including final-context retraction after claim and protected0066 response /
financial hold preservation with actual mocked Google emission and reconciliation.
Derived numeric/dependency records are explicitly schema fixtures, not qualified facts.

Final focused command covered `test_feedback_snapshot`, `test_feedback_review_composition`,
`test_feedback_races`, `test_feedback_migration`, `test_candidate_review_migration` and
`test_google_completion_restore`: **17 passed, 2 skipped**, 8 existing Alembic config
warnings (32.42s). Skips: SQLite row-lock test and native Google restore because native
PostgreSQL tooling/container was not configured.0064 and0068 migration roundtrips did
run; no new native0066 restore success is claimed. Final Ruff, mypy **570 files**, and
`git diff --check` passed. No migration, Full, manual dispatch, live call or policy
activation. A transient exec transport disconnect recovered on one harmless retry;
no quota signal occurred. See `docs/design/b17-feedback-decision-wiring.md`.

### 2026-10-06 — Scoped feedback consumer and composed erasure verified

Integrated PR2058323666 canonical owned feedback scope/apply/snapshot. Root13 passed
with2 compositionfixturefailures: synthetic historical dependency incorrectly used
a higher v1revision, so the version-aware current-source guard correctly blocked
before the intended finalcontext race. Fixture now explicitly labels its unsupported
dependency-only manifest and asserts current review before the race. Final4 composition
cases passed in9.73s, preserving actualthird-context deletion, zero writes,0064cascade,
0068forward denial and0066financial/capture/history retention. Configured native0066
restore also passed in the13 priorpasses (no missing-tools skip). Ruff check .,
configured mypy575 and whitespace passed. Logs `/tmp/inlet-next-feedback-consumer.log`
and `/tmp/inlet-next-feedback-composition.log`. Association snapshots do not authorize
direction or spending; actual qualified policy/source remain unavailable.

### Frozen8efe196 LOCAL FULL TERMINAL SUCCESS

`/tmp/inlet-oct06-candidate2-full.exitcode` is0; final log records38passed6PowerShell
unavailable skips29deselected in3344.99s(55m44s) for finalFocused gate. Primarypytest
2639passed59skipped85warnings in4650.54s; Ruff/mypy489/diff, PGtransactions3passed,
actual upgrade/downgrade/reupgrade, ReadOnly75passed, Security98passed1PowerShellskip
and Privacy14passed completed. The long duration is two nested Full iterations in
primarypytest and two more in finalFocused; recursion guard explicitly sets
AD_ANALYZER_SKIP_NESTED_FULL_VALIDATION_REGRESSION=true for children, preventing
unbounded recursion. Process observations showed CPU advance and transition from
primarypytest to latergates; finalallprocessesexited and frozenDB had no active
connections/zero deadlocks. No coverage/timeouts weakened.

The original interactive handle could not resume aftertransport recovery (unknown
session/pongtimeout), but wrapper-owned exitfile and completeterminal log proveprocess
finished successfully. This is not a lost/assumedalive execution. Full log retained
at `/tmp/inlet-oct06-candidate2-full.log`. Hosted37427571832 remains FAILED onthat
exacttree; PR199targetedrepair is onnewintegration and awaits assembledFull/CI.

### 2026-10-06 — Bounded Runtime Observation Integration

Integrated PR206 commits 0fcf7bc and 27e89ce: bounded scheduler and private-media
observations, independent non-masking storage, sanitized operator attention and
migration 0070. The feature remains disabled by default. Root verification:
241 passed, 3 expected SQLite-only skips, 3 Alembic warnings in 29.34s;
`ruff check .`, configured mypy (582 files), and whitespace checks passed.
Log: `/tmp/inlet-next-runtime-observations.log`. No live service probes occurred.

The next frozen batch uses intermediate merge revision 0071 joining 0063, 0064,
0066, 0068 and 0070. Session automation 0072 remains independent and unfinished;
a later 0073 will join 0071 and 0072. This supersedes the earlier unused-0071 plan.

### 2026-10-06 — Successor Migration Join 0071

Joined 0063/0064/0066/0068/0070 without changing their migrations. Combined actual
migration, populated preservation, native Google restore and registry checks:
13 passed, 1 expected SQLite migration skip, 40 existing warnings in 34.25s.
Log `/tmp/inlet-next-0071-join.log`. `./scripts/validate.sh Migrations` passed
upgrade head / downgrade base / upgrade head on newly created disposable database
`inlet_oct06_candidate3_ci`; log `/tmp/inlet-next-0071-roundtrip.log`.
Ruff, configured mypy (582 files) and whitespace passed. This is the completed
batch for the next frozen candidate; unfinished 0072/PR207 are excluded.

### 2026-10-06 09:29 UTC — Successor Frozen And Remotely Preserved

Candidate and integration branches both pushed and verified remotely at
`a4fcd3a35d585d11def78261382234e081fb8f6b`, tree
`67f18fa0b05ae6ce5637f73591cba66774f5928d`. Draft PR130 updated.
Main remains `ea3591c5086fbf2cee8038bf9208ac7f0050de75`.
Normal PR-triggered CI run37443239927 is in progress (no manual dispatch).
Local Full session30802 reached pytest after fresh migration; database
`inlet_oct06_candidate3_ci`, log `/tmp/inlet-oct06-candidate3-full.log`, terminal
wrapper result will be `/tmp/inlet-oct06-candidate3-full.exitcode`. No terminal
success is claimed. Candidate worktree is clean and frozen while 0072 continues.

### 2026-10-06 — Independent Review And Remaining Disabled Consumers

Frozen candidate remains a4fcd3a; integration documentation successor includes the
bounded outcome/feedback review index and PR208 commercial worksheet. The worksheet
requests only seller/markets, offer economics, account allowance and customer-policy
choices; no values, credentials or live authorization are inferred. Agent checked
69 existing billing regressions, Ruff/mypy582 and links; root checked document links
and whitespace. Engineering is explicitly unfinished.

Root approved two additive disabled contracts before implementation: directional
association consumer (owned intervention cohort, stable original-attempt opportunity,
explicit calibration and independently qualified observation-count provenance) and
Google replacement compositor (exact immutable transition certificate plus freshly
rechecked original terminal ancestry). No production registry or finite U/F/P is
created by these approvals. Existing transfer equality, budget ceilings and fresh
original-session guards remain mandatory. Qualified delivery/correction/financial
facts and calibrated values remain unavailable; they are not credentials-only gates.

Normal hosted37443239927 passed decoder preflight and migration and is running pytest.
Local Full30802 is in the bounded nested regression; observed parent/child CPU advances
and zero database deadlocks. Neither successor validation has a terminal result yet.

### Frozen Outcome/Feedback Independent Review

A separate bounded source review of exact a4fcd3a found no concrete P1/P2 defect in
retraction, final execution provenance, protected financial history or export privacy
fences. Reviewer ran 23 focused SQLite/PostgreSQL regressions, 1 expected skip in
43.51s (`/tmp/inlet-outcome-review.log` and companion XML). The frozen tree was not
changed. This is not a Full pass or a review of unavailable production policy/financial
guarantees. Exact component PRs are indexed in `docs/design/inlet-outcome-review-index.md`.

Root also identified potential same-workspace starvation in unfinished0072: an older
revoked-session run could remain the earliest due item. The scheduler owner reproduced
it and added non-authorizing deferral; both database regressions pass. The package is
not yet frozen/integrated; final combined checks and actual backend UI remain pending.

### Session Automatic Decision Ports — 2026-10-06

Branch `codex/inlet-session-automation`, base `c2e43b9`: freeze strict original-session
Start/status/stop/capabilities schemas and distinct automatic admission authority
union in `app/session_automation/contracts.py`; implementation contract in
`docs/design/session-automation-interfaces.md`. No routes, authority records,
worker or enabled policy yet; migration0072 reserved down0068. Next package
implements actual owned customer intent and durable all-provider offline journey.
No human approval fabrication, logout-independent delegation, new campaign,
activation or emergency pause is permitted by these types.

Candidate final evidence hook now requires a current local lineage checker for
registered feedback-dependent schemas before storing suggestions; missing or
retracted lineage blocks. Pure association snapshots do not become directional
learning. Checks actually run: PostgreSQL+SQLite hook regressions6 passed;
strict contract tests3 passed; whole Ruff clean; whole mypy571 files clean;
`git diff --check` clean. No Full, live calls, manual workflow dispatch or deployment.

Root integrated frozen automation interface commits6c95a43 and332d7fc independently
of unfinished0072. Candidate/final-evidence/contracts/review bridge checks:84 passed,
1 expected PostgreSQL-only race skip on SQLite in115.81s. Ruff, configured mypy586
and staged whitespace passed. Log `/tmp/inlet-next-automation-ports.log`.

### Authenticated Directional Evidence Seam

Added optional local evidence transform and original-principal final checker. The
worker supplies the persisted job's current original session, rejects scope/native
state changes, repeats source-profile authorization and current session/time checks,
and refuses result insertion after the claim lease expires during dependency checks.
Existing checker signatures remain compatible; no production adapter is registered.

New boundary suite22 passed in24.58s; candidate/review/feedback composition79 passed,
1 expected SQLite-only concurrency skip in112.33s. The broad run preceded the final
additive lease check; the22-case final suite includes its expired-lease regression.
An initial test-only typo used token_digest rather than CustomerSession.digest and
was corrected before these passes. Ruff, mypy587 and whitespace passed.
Logs `/tmp/inlet-authorized-evidence-final2.log` and
`/tmp/inlet-authorized-evidence-composition.log`.

Executor recovery checked at09:45 UTC after parent disconnect notification: actual
read/write, repository access, original Full pytest PIDs/CPU advance and PostgreSQL
zero deadlocks succeeded. No observed process loss, quota failure or access blocker.

## Disabled Google Replacement Source Composition — 2026-10-06

Branch `codex/inlet-financial-source-composition`, isolated from frozen `a4fcd3a`;
proposal commit `05d7ade` approved before additive implementation. Added exact transition
request/certificate/profile ports and optional server-owned Google replacement compositor.
Actual retained original-success terminal evidence is joined only with an independently
injected allowlisted financial certificate. Private transactions recheck full ancestry,
mandate/account generation, current authorization, high-water and held reservations before/
after source IO; final clock resampling rejects lock/authorization delays. Immutable
certificate epoch and stable closure content preserve exact reviewed transfer equality.
No source fallback, native profile/default factory, migration, financial release or live
provider activity. Native U/F/P and preventive writer guarantees remain missing, as recorded
in `docs/design/production-spending-source-readiness.md`; fixtures do not qualify them.

Checks: completion/terminal/replacement/composition suite **103 passed, 1 SQLite-only
PostgreSQL-lock skip** (160.87s; `/tmp/inlet-composition-tests.log`). After the freshness
repair and added unknown-ancestor case, final compositor suite **32 passed** across SQLite
and PostgreSQL (66.69s; `/tmp/inlet-composition-final.log`). Direct compositor delayed-
authorization regression **2 passed, 30 deselected** (5.87s;
`/tmp/inlet-composition-delay.log`), so coordinator freshness cannot mask that check.
Whole Ruff passed; configured mypy **585 files** passed; diff whitespace and proposal
relative links passed. Dedicated disposable PostgreSQL `inlet_meta_browser_ci`; no Full.
Tests include real prepare/transfer with unchanged certificate, rejection of changed
certificate, persisted owner-role/generation/high-water/hold changes during IO, sanitized
source failures, future/expired/null/unregistered evidence, and unknown original ancestors.
Next: parent review/integration and separate native provider-backed source specification;
credentials or a monetary-basis decision alone do not implement missing guarantees.

Root integrated PR210 (05d7ade + fa3bd4f). Combined compositor, exact original-terminal
and feedback-retraction composition tests60 passed in108.13s. Ruff check .,
configured mypy590 and staged whitespace passed. Log
`/tmp/inlet-next-financial-composition.log`. This provides composition only; no native
financial certificate source, qualification registration or runtime is enabled.
### Original-Session Automatic Budget Execution — 2026-10-06

Branch `codex/inlet-session-automation`, backend successor of ports332d7fc and root
c2e43b9. Migration0072 down0068 adds protected original-session intents and immutable
semantic admissions, scoped to mandate revision/consent/ledger/review. Run authority
is explicitly exact-human or mandate-automatic, never converted/fallback. Customer
CSRF Start/status/Stop/history/capabilities APIs are implemented; Stop records the
current owner and remains available after the initiating session has ended.

The opt-in shipped scheduler now runs actual selection→candidate→exact review→
automatic admission→shared reservation/claim→Google/Meta/TikTok adapter/readback.
No human approval is fabricated. All3 contract scenarios exercise initial AND new
semantic repeat effects with zero ProviderExecutionApproval rows. Stable native
account/owner + ledger + policy family + semantic epoch prevent reuse across new
Starts, refresh timestamps, policy revisions and mandate revisions. Exact numeric
candidate-policy digest prevents same-reference configuration changes. Original
session/candidate/mandate/source and financial proof are checked at forward gates;
Stop during final context lookup blocks emission. Unknown original requests retain
hold/fence, reconcile after Stop/retraction, and are never replayed.

Parent review found a revoked earliest run could shadow a newer valid session in
the same workspace before due time advanced. Fixed by workspace-locked scheduling
maintenance that only defers the failed run; both-DB regression verifies the newer
session executes once. Closure stops all session runs. Explicit registry/export
classifications retain only bounded authority commitments and omit session hashes;
no raw measurements are retained. Populated downgrade refuses to erase semantic
consumption or change authority origin. Narrow historical fixture adapters assert
absent new tables; no production missing-table fallback was added.

Checks actually run: final automation/API/0072/strict-port suite55 passed +1 expected
SQLite concurrency skip; additional final-admission rollback2 passed (bothDB).
Broader bridge/final-evidence/scheduler/0058+0068+0072 checks110 passed +1 SQLite skip
before the final scoped FK/numeric-policy hardening; scoped final FK/scheduler/
concurrency subset12 passed +1 SQLite skip. Whole Ruff clean, mypy581 files clean,
`git diff --check` clean. No Full or manual workflow dispatch in this lane.
UI ports are frozen; UI207 actual-backend integration follows this commit.

Remaining: actual qualified directional learning/numeric policy/native complete
exposure and original-terminal/transition producers plus production registry/runtime
assembly. Default factory None and scheduler flag false are unchanged operational
limits; current native diagnostics are unqualified. These are missing source/code
qualification, not only missing credentials. No live calls, spend, merges into main,
deployment, new-campaign/creative/activation/pause authority or logout-independent
delegation was enabled. Root final migration0073 will join intermediate0071 +0072.

### Authorized Epoch Reader Seam — 2026-10-06

Isolated `codex/inlet-authorized-epoch` successor of frozen backend1d1fc15 (PR212),
without amending that head. Add optional principal-aware SemanticEpochProducer
callback, preferred over the compatible legacy reader. Only the actual original
principal from current session admission reaches it. Missing readers are unavailable;
post-callback revocation/expiry denies admission and provider work. No inferred
owner, browser authority field, source qualification or production enabling change.
Checks: focused authorized/legacy all3/atomic rollback16 passed across SQLite and
PostgreSQL; final authorized callback/missing-reader suite8 passed after availability
hardening; whole Ruff clean, mypy582 files clean, diff check clean. No Full/live calls.
### Session Automation UI — Frozen-Port Consumer Checkpoint

`codex/inlet-session-automation-ui`, isolated child332d7fc, adds separate Start,
status/history recovery and Stop to Existing Campaigns without replacing manual
review. Exact consented mandate and registered policy options come from server
capabilities; readonly limits/environment plus explicit current-session consent
are shown. No browser evidence/financial policy inputs or backend edits.

Validation: actual HTTPS manual API browser journey **2 passed** (both databases).
Combined manual and controlled automation JSON-port browsers **4 passed**. Added
in-flight CSRF/session replacement regression **2 passed** (6.50s), including
A→B→A late success/failure, lost Start/Stop no replay, history-only recovery,
unavailable capability, owner denial and logout cleanup. The first added test
reused a consumed login token; the fixture now exchanges a distinct synthetic token,
preserving replay denial. Ruff, node syntax, clean mypy **571 files**, diff checks
pass. Logs `/tmp/inlet-session-automation-ui-contract.log`,
`/tmp/inlet-session-automation-ui-security.log`,
`/tmp/inlet-session-automation-ui-types.log`.

Actual automation backend routes remain in the scheduler owner's active package;
this consumer checkpoint does not claim their qualification. Next: merge its frozen
head and run the real API/DB automation browser journey. No live calls or Full run.

Review checkpoint: draft [PR207](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/207)
against `codex/inlet-session-automation`, implementation `73cca02`. Final combined
browser run **4 passed** in17.07s. Actual backend qualification remains explicitly
pending its frozen routes/models head; scheduler supplied the upcoming test fixture
and runtime dependency names for the follow-up integration.

### PR207 — Actual Session Automation API Browser Integration

Merged frozen backend0072 `1d1fc15` into the isolated UI child (`a3c3d07`);
no UI-owned schema changes. Actual HTTPS browser coverage now drives real
session/CSRF Start, history/status and Stop routes, durable worker selection/
admission and the real Google HTTP adapter with MockTransport. Exactly one mocked
provider mutation occurs; zero human approval rows, two explicit session Starts.
Late Start A→B→A, lost Start/Stop recovery without replay, original-session logout,
fresh-owner Stop with runtime disabled and current role denial are verified on both
SQLite and PostgreSQL.

Unavailable runtime is not terminal: corrected the UI so a known nonstopped run
can still be stopped. Backend owner delegated the additive capability label hunk:
current owned account names plus bounded mandate reference, and policy reference,
make otherwise identical options distinguishable without customer proof inputs.
Actual browser checks account names render literally, including synthetic markup.

Final combined API/manual/browser/controlled-port validation: **10 passed** in47.44s.
Whole Ruff, clean mypy **582 source files**, JavaScript syntax and diff checks pass.
Logs `/tmp/inlet-session-automation-ui-integrated.log` and
`/tmp/inlet-session-automation-ui-integrated-types.log`. Earlier actual backend
browser-only run: **2 passed** in17.86s. Parent owns integration,0073 join and
assembled Full/hosted qualification. No live runtime or evidence policy enabled.

### 2026-10-06 — Session Backend, Authenticated Epoch And Actual UI Integrated

Integrated PR212 backend1d1fc15, authorized epoch8f384ff, and PR207 UI73cca02 /
1384da9 / b3feacf. Root combined automatic/API/migration/browser/registry suite:
66 passed,1 expected SQLite concurrency skip,4 Alembic warnings in266.29s.
Original-principal epoch, shipped scheduler, protected closure and feedback retraction
composition:46 passed in58.66s. Ruff, configured mypy602, staged whitespace passed.
Logs `/tmp/inlet-next-session-automation.log` and
`/tmp/inlet-next-automation-composition.log`. Actual HTTP adapters are MockTransport;
no live execution or production-source qualification is implied.

The tested path preserves explicit Start, original-session revocation, immutable
numeric-policy binding, distinct automatic admissions, no fabricated human approval,
semantic deduplication, and unknown-request reconciliation after Stop without replay.
Stop remains accessible when runtime is unavailable. PR207 description was successfully
updated through the connected GitHub tool after the shell route returned Forbidden;
that was not quota evidence and no shell bypass/retry was used.

Next: join0071+0072 at0073, complete directional adapter and assess first-action and
actual production assembly. Provider feasibility must separate unavailable official
guarantees from engineering gaps; do not add scaffolding indefinitely or weaken the
strict contract without a concrete owner decision. Frozen a4fcd3a Full/CI still pending.

### 0073 Schema Join And Review Boundary

Joined0071 and0072. Combined historical/current migration, populated-refusal, protected
Google restore and feedback provenance checks8 passed,1 expected SQLite migration skip,
30 existing warnings in40.23s (`/tmp/inlet-next-0073-join.log`). Complete upgrade head /
downgrade base / upgrade head passed on newly created disposable
`inlet_oct06_0073_migration_ci` (`/tmp/inlet-next-0073-roundtrip.log`). Active frozen
candidate3 database was not reset. Ruff/mypy602/whitespace passed.

Parent independently source-reviewed20f2b7b and found no new P1/P2 in owned feedback,
erasure, final-context retraction or protected financial preservation. This review
confirms descriptive associations only; no mature learning acceptance. B17 remains
incomplete while genuine maturity/directional sources and calibrated policies are
unavailable. New adapter fixtures and no-defect reviews must not be labeled learning
completion. No successor candidate is frozen yet.

## B17 Disabled Directional Reader And Evaluator — 2026-10-06

Branch `codex/inlet-directional-runtime`, child of docs-onlyPR209/c222c73 (root
b9d2dce ancestry). Added strict required-parameter policy/profile/facts/opportunity/
result contracts, pure calibrated-association mapping, disabled registries and actual
owned feedback/plan reader. Original action resolution uses current held reservation
and validated durable ancestry, never timestamp sorting or favorable old fallback.
Exact candidate numeric-policy digest is bound to calibration. Qualified completion
count is separate from contribution count; no causal or spending authority is inferred.

First expanded reader/evaluator/snapshot/feedback suite:20 passed across SQLite and
PostgreSQL (34.65s); Ruff and mypy587 files passed. Regression includes real repeat
claim with a newer held original and no receipt, which blocks the old feedback head.
Final contract boundary rerun (facts commitment/live-fixture guard) recorded in the
next freeze report. No migration, Full, live profile, source call or numeric default.

This is the first implementation slice. Candidate adapter and authenticated final /
automatic epoch seams remain separately coordinated next work. Source/timing guarantees,
real calibration and an initial-action policy are not supplied by this feedback loop;
brands with no qualified original action remain blocked here.
Final contract boundary rerun:8 passed (15.69s), including explicit contract-fixture
rejection in live mode, missing calibrated parameters, distinct completion thresholds,
cohort contradiction, absent producers and current-snapshot retraction. Final Ruff,
mypy587 files and diff whitespace checks passed. Adapter remains unimplemented in this
frozen first slice; no direction reaches a candidate or executor yet.

### Authenticated Directional Candidate Adapter — 2026-10-06

Successor of PR211, integrating root authenticated candidate hooks1e7b742 and authorized
epoch8f384ff. Added actual queued native-read→owned feedback transform→final-current
check and exact original-session epoch binding. No new schema, authority or production
registration. Recalibration cannot create a fresh original-action opportunity; committed
contribution retraction after HTTP read prevents a candidate. Qualification fixtures are
synthetic; independent source/timing, calibration and first-action policy remain missing
production work. See design/b17-directional-consumer-contract.md for the explicit split.
Validation: new adapter plus directional reader/evaluator14 passed on SQLite/PostgreSQL
(37.35s); shared authenticated candidate and epoch boundary suites24 passed (29.39s).
Whole Ruff clean; mypy605 source files clean; two added files format check and git diff
check clean. No Full, CI dispatch, live provider call, deployment or activation.

### Directional Consumer Integrated Without A Learning Completion Claim

Integrated PR209 contract b71b3c7/c222c73, PR211 owned evaluator/reader7ca025c and
PR213 authenticated adapterdd48bd8. Root actual queued native-read / original-session /
stable-epoch / retraction / feedback composition suite42 passed in71.84s. Ruff,
configured mypy609 and staged whitespace passed. Log
`/tmp/inlet-next-directional-adapter.log`.

This closes directional consumer wiring: original intervention cohort and latest
original request are owned, recalibration cannot mint an opportunity, and committed
retraction after IO blocks publication. Synthetic fixtures do not qualify live facts.
Genuine maturity/timing/count producers, calibration and automatic first-action policy
remain unavailable; B17 remains incomplete. The existing exact customer-reviewed
initial budget intent is a manual bootstrap, not an automatic learning policy.

### Provider Evidence Decision And Concrete Remaining Assembly

PR214 (f0d8d6b; integrated9c76ff8) supplies the requested provider-by-provider matrix,
using official documentation and distinguishing contradictions from unverified or
inaccessible guarantees. Root independently reopened Google budget/overdelivery,
TikTok Budget Manager and Shopify webhook references. No universal impossibility or
Meta/TikTok completion semantics are inferred from absent documentation.

The current strict total-spend contract is not demonstrated for arbitrary outside-writer
accounts. The proposal recommends an explicitly recommendation-only initial release;
customer-approved configuration control would require a separate versioned contract.
Neither option is authorized or implemented by the document. Existing reviewed exact
initial budget intent is a manual bootstrap; automatic first direction still lacks
qualified objective inputs/calibration. Do not present safe hooks as completed learning.

Actual assembly inspection found diagnostics require a consented mandate, while mandate
creation requires unavailable execution runtime. Approved a concrete independent read
journey: owned account/date request v2, existing real scoped vault/collector assembly,
CSRF endpoint and customer UI, with no fabricated mandate, financial source or new
generic execution port. Existing v1 request bytes remain unchanged. Result contains
bounded counts/reasons only, financial bounds null, optimization unavailable. Backend
and UI implementation are proceeding on isolated branches; no live provider calls.

### Frozen a4fcd3a Nested Validation Failure — Outer Run Still Active

Preserved nested report `/tmp/inlet-a4fcd3a-nested-full-0.xml`:3462 tests,
3386 passed,72 skipped,4 failed in2456.159s. Failures: repurchase regression bothDB,
old Stripe factory expectation, and historical replacement migration accessing later
0066 completion table. The latter is already repaired in0072's asserted historical
fixture; root0073 migration tests passed. Billing owner reproduced the other3 failures:
repurchase is a real service regression (new active subscription incorrectly sent through
historical-terminal verification before resolving its owned checkout), not a waived
fixture. Repair and qualified ownership tests are in progress. Factory expectation is
stale under required reviewed offer/merchant configuration; production gate stays strict.

Both Meta browser cases and both positive-conversion regressions passed in this nested
report. That does not turn the nested or whole run green. Outer local Full continues;
terminal result and hosted37443239927 still pending. No frozen code changed.

Independent bounded source review of41cb48f found no concrete P1/P2 in directional
head/cohort/count/epoch/retraction/session logic;6 targeted SQLite/PostgreSQL tests
passed (`/tmp/inlet-directional-review.log`). This is not maturity/source qualification.

### Repurchase Reconciliation Regression Repaired

Integrated PR21512111aa. Resolve only the persisted owned replacement checkout before
historical-terminal fallback; the prior subscription must still be terminal and the
replacement must pass its original offer/payment proof. Unrelated subscriptions cannot
establish ownership. The old key/version-only factory fixture now expects unavailable;
a usable configured factory test supplies the required reviewed merchant/offer.
Root qualified repurchase, original regression and Stripe transport suites70 passed in
26.54s (`/tmp/inlet-next-billing-repurchase.log`); Ruff, mypy610 and whitespace passed.
Frozen a4fcd3a stays unchanged and failing until its terminal validation is recorded;
these successor passes do not erase that failure.

## Owned Native Account Diagnostics — Read-Only Assembly

Branch `codex/inlet-account-diagnostics`, isolated from root9e8d9f5. The customer
CSRF POST `/api/customer/v1/workspaces/{wid}/execution/diagnostics` now constructs
an actual vault-backed, fixed-endpoint Google/Meta/TikTok diagnostic service without
an execution runtime or spending mandate. Input is owned account ID and bounded
observation dates only. Original-session, owner, source-generation, account-money,
billing and all-data-sync fences are rechecked around OAuth and collector IO.
Per-request transports close deterministically. Default read switch remains off.

New account-observation request v2 variants coexist with unchanged mandate-bound
v1 bytes and digests (baseline hashes captured from8f384ff). Customer output contains
bounded inventory counts and fixed explanatory reasons; no native monetary counters,
resource IDs, raw responses or credentials. Financial bounds remain null and
optimization_available remains false. No diagnostic documents are persisted.

Checks: compatibility/API/native-collector suite218 passed on PostgreSQL and SQLite;
additional final billing/credential fences12 passed. Final API/contract suite recorded
below. Whole Ruff and mypy603 source files pass; whitespace check passes. All HTTP is
MockTransport, encrypted credentials synthetic; no live verification, spending,
provider mutations, Full workflow, manual CI dispatch, merge or deployment.

This closes a real read-service/application assembly gap. It does not qualify a
production spending guarantee or calibrated direction source. Those remain explicit
source/product-boundary limitations, not solved by credentials or this read switch.
UI consumer is owned by customer_portal; actual browser qualification follows the
frozen backend. See docs/design/read-only-native-assembly.md for exact contracts.

Final new API/contracts:62 passed, zero skips, both databases (66.69s), log
`/tmp/diag-final-api.log`; prior218 log `/tmp/diag-all.log`. Static logs
`/tmp/diag-final-ruff.log`, `/tmp/diag-final-mypy.log`. This exact code is ready for
independent browser integration; hosted/full CI remains unclaimed.

Root integrated verification: account diagnostic contracts/API, concrete native
assembly, all three native inventories and model registry: **246 passed in127.46s**,
zero skips (`/tmp/inlet-next-account-diagnostics.log`). Whole Ruff, configured
mypy615 files and staged whitespace check passed. This is synthetic-provider,
SQLite/PostgreSQL verification; no live qualification is asserted.
### Account Diagnostics UI — Actual Read-Only Customer Journey

Isolated branch `codex/inlet-account-diagnostics-ui` from rootb16dac4, merged frozen
ports177edff and concrete backend445616f. New `/app/account-diagnostics`, linked
from Existing Campaigns, uses owned named account selection and an explicit past
UTC window up to366days. It reads only on customer action, needs no spending
mandate, and renders bounded item counts, dates and fixed readable findings.
Optimization remains false; native monetary values, resource IDs, raw JSON and
internal qualification details are not rendered. Date/account/workspace changes,
A→B→A, session-cookie changes, logout and owner denial clear stale output; no
automatic read replay after a lost response.

Actual HTTPS browser→session/CSRF API→encrypted synthetic vault→concrete service/
factory→real Google/Meta/TikTok collectors via MockTransport is verified across
SQLite and PostgreSQL. Only low-level HTTP transport and clock are injected, with
mandate-check sentinel failing if consulted. Each journey verifies four explicit
successful native reads, disabled factory zero calls and deterministic transport
closure, while preserving manual execution UI logic.

Initial browser run: **2 passed, 4 failed** because social fixtures also contained
a valid Google account and the harness assumed a single entry. Corrected selection
of the intended owned account without removing any account or weakening assertions.
Final browser/shell/contracts/route suite: **18 passed**, no skips,26.49s using
inlet_candidate_migration_ci with unique schemas and no shared database reset.
Whole Ruff, clean mypy **609 files**, JavaScript syntax and diff checks pass.
Logs `/tmp/inlet-account-diagnostics-ui-integrated.log` and
`/tmp/inlet-account-diagnostics-ui-final-types.log`. Parent owns assembled Full
and hosted/intended-environment qualification. No live settings or execution enabled.

Review delivery: draft [PR217](https://github.com/Konner-An-Inlet/Ad-Analyzer/pull/217),
branch `codex/inlet-account-diagnostics-ui`, tested implementation `583784c`.

Root assembled UI verification: `pytest -ra tests/test_account_diagnostics_browser.py
 tests/test_account_diagnostics_ui.py tests/test_route_boundaries.py` **16 passed,
zero skips in28.35s**, including all three providers on both databases using actual
browser/API/vault/collector assembly with synthetic HTTP. Log:
`/tmp/inlet-next-account-diagnostics-ui.log`. Whole Ruff, configured mypy617 files,
JavaScript syntax and staged whitespace checks passed. Backend combined246-pass
verification is recorded above. No live settings were enabled.

### Independent Diagnostics Date Repair — PR218

Independent review reproduced Google overflow after reads for an unrepresentable
UTC/account-timezone date. Shared customer/internal account intents now reject
unrepresentable edges before transport construction while preserving ordinary
historical dates,366-day bounds and historical native v1 hashes. Source cd4a053:
158 diagnostic/API/assembly/browser tests passed across both databases; root exact
edge/compatibility checks12 passed (61 deselected) in7.22s, log
`/tmp/inlet-next-diagnostic-date-repair.log`. Ruff, mypy617 and staged whitespace
passed. No additional P1/P2 was established in that bounded review. No live calls.

Original acceptance remains unchanged while the owner considers launch scope.
Restricted Google and social profiles are being assessed separately from an
unsupported universal outside-writer guarantee. Next concrete offline slices are
reviewed PAUSED Google Search total-budget compiler/readback and immutable current
campaign-report completion/reader (Meta first, migration0074 reserved after0073).
Neither enables automatic execution or claims mature learning.
### Meta Campaign Performance Completion — 2026-10-06

Isolated `codex/inlet-campaign-performance` from root c5b58a0. Migration 0074 follows
0073 and adds immutable owned completion metadata plus a composite-owned current
reference. Meta's actual terminal campaign/day importer publishes both atomically with
normalized metrics. The strict owned current reader recomputes the bounded manifest,
checks generation/event/privacy/coverage/native identity and original owner session,
and preserves unavailable metrics separately from observed zero. No historical metric
bodies, causal/mature qualification, policy defaults, API/UI or execution registration.

Frozen service/schema interfaces: `docs/design/campaign-performance-completion.md`.
Google/TikTok producers remain unimplemented; they cannot inherit Meta event semantics.
Next calibration/first-preview package still requires reviewed contracts and explicit
numeric inputs. Current completion timestamps are import observations, not provider
finality or an approved freshness threshold.

Validation: initial actual Meta HTTP→DB→reader suite 16 passed SQLite/PostgreSQL.
Expanded completion plus existing Meta connection/detail suites 48 passed (19.81s).
Final completion/migration plus lifecycle/model registry suites 41 passed, one existing
SQLite skip (22.77s). Actual 0074 update rejection, composite FK/cascade and roundtrip
pass both databases. Whole Ruff and mypy 622 files clean. No Full, live calls, deployment,
manual CI dispatch or runtime activation.
Final targeted rerun after export projection assertions: 20 passed across both databases
(13.77s); Ruff, mypy 622 and diff checks clean.

Root PR219 integration: campaign-performance producer/reader/migration, model registry,
Meta connection and detail suites **51 passed**, three Alembic deprecation warnings,
in22.45s (`/tmp/inlet-next-campaign-performance.log`). Initial invocation named a
nonexistent connection test file and collected no tests; corrected to
`tests/test_meta_connection.py` before this successful run. Whole Ruff, mypy622 and
staged whitespace passed. Full0074 upgrade/downgrade/upgrade on a fresh separate
`inlet_oct06_0074_migration_ci` database passed, log
`/tmp/inlet-next-0074-roundtrip.log`. Running frozen candidate databases untouched.
Prepared validation successor remains immutable dc3c0d5/tree5d17ce3 on
`codex/inlet-mvp-validation-next`; this0074 package is later work, not part of it.
### Google Reviewed Total-Budget PAUSED Publication — Offline Backend

Restricted-profile assessment is independently reviewable in commit `2d746f7`;
shared typed backend interface frozen in `20ad0c4`. Added the explicit
`google_search_total_v25_v1` configuration/compiler and
`google_create_total_budget_v1` operation: `totalAmountMicros`, `CUSTOM_PERIOD`,
independent budget, exact account-local start/end and initially PAUSED Search
campaign. Exact total must fit the reviewed reservation; mixed daily/total fields,
compiler/configuration mismatch and changed operation amount are rejected.
DAILY review/plan golden digests remain unchanged; no social serialized fields change.

The initial supported duration is deliberately an interior subset: 4–89 inclusive
local calendar days plus 72 hours through 90 days elapsed UTC, with existing local
midnight/day-end precision. Three/90-day boundary interpretation is unqualified by
Inlet; this is not a claim that Google rejects those boundaries. See
[the frozen interface](design/google-total-budget-interface-delta.md) and
[restricted-profile assessment](design/google-restricted-mandate-profiles.md).

Actual MockHTTP exercises validation, mutation and semantic readback through the
complete DAG; conflicting daily amount, total amount, period, sharing or omitted
required fields fail closed. Durable SQLite/PostgreSQL tests create the paused
campaign, retain its reservation and project owned receipts. Status-only activation
transport accepts the new immutable configuration without inventing budget fields.
All financial qualification and separate activation approval gates remain intact.
No provider calls, live settings, enrollment, automatic optimization or qualified
native exposure source were added. Customer UI is a separate dependent package.

Validation: broader backend contracts/HTTP/qualification/mandate/coordinator/
activation/social contract suite **164 passed, 8 SQLite-only skips** (80.78s),
`/tmp/inlet-total-backend.log`. Whole Ruff and configured mypy **618 files** pass;
whitespace checks pass. Final expanded recovery suite recorded below.

Expanded coordinator/activation-review recovery suite: **35 passed, 1 SQLite-only
lock skip** (57.16s), `/tmp/inlet-total-recovery.log`. Both budget modes cover lost
acknowledgement without replay, exact separate activation approval retaining the
parent hold, and native budget drift blocking activation review. Static checks
were rerun after these additions and pass. Full/intended-environment validation
belongs to the parent integration; none is claimed by this package.

Root PR220 backend integration: exact total contracts/compiler/native HTTP and
activation suites68 passed in2.14s (`/tmp/inlet-next-google-total.log`); durable
coordinator/activation-review recovery35 passed, one SQLite lock skip in53.31s
(`/tmp/inlet-next-google-total-recovery.log`). Whole Ruff, mypy623 and staged
whitespace passed. Independent exact20ad0c4 review established no P1/P2 in its
bounded scope,67 targeted passes plus four total activation fixture checks;
record `/workspace/inlet-design/GOOGLE-TOTAL-BUDGET-INDEPENDENT-REVIEW.md`.
No current financial gate or live runtime changed. UI integration follows separately.
### Google Campaign Total Budget Customer UI — Offline

Added an explicit daily/campaign-total choice to Campaign Execution, keeping the
legacy daily intent shape. Exact reviews distinguish total budget, reservation,
account time zone and period; guidance labels the 4–89-local-day subset as Inlet's
qualification scope. Budget changes invalidate in-flight review context.

Verification: actual HTTPS browser suite **8 passed** on SQLite/PostgreSQL
(39.71s), including total PAUSED creation/readback, delayed-response mode change,
reservation retention and no activation requests. Existing daily/activation,
context-race and lost-response cases passed. Customer API/compiler/HTTP focused
suite **53 passed** (24.66s); whole Ruff, clean mypy **618 files**, JavaScript
syntax and whitespace checks passed. Tests use MockTransport, no live provider
calls or financial/runtime enablement. Parent owns Full/hosted qualification.
Branch: `codex/inlet-google-total-budget-ui`. See
`docs/inlet-google-total-budget-ui.md`. B20 fresh-brand proposal remains separate
at `/workspace/inlet-design/FRESH-BRAND-PILOT-PROPOSAL.md`; no B20 implementation
is claimed here.

Root PR221 UI/API integration: **20 passed in59.87s** on SQLite/PostgreSQL,
`/tmp/inlet-next-google-total-ui.log`, covering actual daily/total browser flows
and customer API. Ruff, mypy623, JavaScript syntax and staged whitespace passed.
Financial eligibility, separate activation approval and runtime defaults unchanged.
Prepared dc3c0d5 validation snapshot remains unchanged; this package is successor work.

### Frozen a4 Local Terminal And Repaired Candidate Launch

Local Full on a4fcd3a terminated **exit1**:5 failed,3390 passed,67 skipped,
129 warnings in5059.83s. The four known causes plus nested wrapper failed; later
Full gates did not run after pytest failure. Nested first invocation3386 passed,
72 skipped,4 failed. Both B01 positive-conversion and Meta browser database cases
passed nested. Exact repairs are in docs/inlet-candidate-a4-validation.md.
Hosted37443239927 remains in progress; do not call it failed/passed before terminal.

Prepared successor dc3c0d5/tree5d17ce3 is pushed and local Full65083 started against
its separate immutable checkout/database inlet_oct06_candidate4_ci. Log
`/tmp/inlet-oct06-candidate4-full.log`, eventual `.exitcode`. Newdevelopment0074 and
Google total-budget packages remain outside this snapshot. PR130 unchanged until
its hosted result is retained. No manual dispatch, merge or live action.

### Hosted a4 Terminal And New Pre-Run CI Blocker

Hosted37443239927/job112201796837 FAILED:5 failed,3396 passed,61 skipped,
129 warnings in5132.55s. Nested4 failed,3396 passed,62 skipped. Same four causes
plus nested wrapper as local; no additionalfailure. Checkout92a1590238c9e37acd994fcec5f491342aa1025f
tree67f18fa0b05ae6ce5637f73591cba66774f5928d matchesa4 exactly. Log retained
`/tmp/inlet-pr130-a4-hosted.log`; failure artifact11407171330 expires2026-10-13.
PR130 advanced normally to dc3c0d5 and body updated with exact qualification limits.

Its new normal CI37453370292/job112234984790 failed before any runner/steps in
three seconds (10:59:01–10:59:04UTC). Log returns404; check annotation is unavailable
because the connector rejects check-runs URLs. Cause UNKNOWN; no actual GitHub
quota/resource/usage limit confirmed. No retry/manual dispatch. Parent needs exact
annotation evidence. Local candidate4 Full65083 remains running. Agents finishing
existing offlinechecks/freeze were asked to hold additionalpush/CI pending diagnosis;
no global stop claimed without confirmed owner-triggering usage-limit evidence.

### Google/TikTok Campaign Performance Producers — 2026-10-06

Isolated `codex/inlet-provider-performance` from integrated root 73bb5f1 / PR219.
Actual concrete GoogleHTTPRead and TikTokHTTPRead terminal imports now publish immutable
0074 completion/current references in the metric replacement transaction. No new migration.
A frozen server-bound reporting descriptor binds actual query/API versions across pages;
legacy missing descriptors finish normal imports unqualified, and terminal unqualified
writes invalidate old current references even with equal metrics. Positively conflicting
page descriptors fail closed. Google coverage is exactly the last completed bounded slice,
not all history/newest calendar coverage. TikTok child rows are excluded; generic counts
are separately labelled and placeholder value remains unavailable. Meta v1 bytes remain
unchanged; all readers additionally validate the active owned integration.

Strict v2/current reader interfaces and compatibility behavior are documented in
`docs/design/campaign-performance-completion.md`. No initial policy, calibration values,
causal/mature qualification, customer UI/API or automatic execution registration added.

Validation: expanded actual provider producer/reader plus Meta, Google/TikTok importer and
HTTP suites 132 passed (43.22s); final composed all-provider performance/fence/migration
batch 62 passed (35.45s). Final Google/TikTok run after strict v2 cross-field validation:
40 passed across SQLite/PostgreSQL (22.76s). Tests cover actual HTTP→staging→completion→
owned reader, old/partial coverage, correction, equal-metric unknown adapters, legacy
continuation, cross-provider semantic limits, generation/privacy/row/session/native/
integration fences and overflow rollback. Whole Ruff and mypy 624 files clean; diff clean.
No Full, live calls, manual CI dispatch, deployment or activation.

### Local Provider Performance Integration During Remote Hold

Root actual Meta/Google/TikTok performance, Google customer import and TikTok HTTP
suites **112 passed in43.04s**, log `/tmp/inlet-next-provider-performance.log`.
Ruff, configured mypy625 and staged whitespace passed. No new migration. This
integrates PR2228ec322a locally only; new pushes/CI remain held pending the owner's
GitHub check annotation. Local Full65083 continues on unchanged dc3c0d5.

Independent review of not-yet-integrated Plan Review943ce8 reproduced simulation
approval after revoked original session/owner-role loss and server acceptance of
an over-goal planning budget (six failing security assertions across both DBs).
Repairs are active separately; the successful fresh-browser path does not clear
these findings. No live spending follows from this simulation path. Frozen Full
snapshot is not modified; its result will not substitute for these new regressions.

### Local Populated Performance Restore Verification

Integrated local5363542 fixture/drill extension. Root real PostgreSQL dump/restore
suite **33 passed**, five Alembic deprecation warnings, in68.50s; log
`/tmp/inlet-next-performance-restore.log`. Separate disposable database
`inlet_root_performance_restore_test_20261006`; active Full database untouched.
Restored current reader/digest, foreign exclusion, immutable completion trigger,
composite references and deletion cascade pass alongside prior financial/social
checks. Ruff, configured mypy625 and whitespace pass. Explicit script check needs
`mypy --explicit-package-bases scripts/inlet_restore_drill.py
scripts/inlet_restore_fixture.py`; both pass (plain paths initially produced a
module-name duplication configuration error, not a source defect).
Local commits only; remote push/CI hold remains. No real backup/live environment claim.

### Fresh Brand Offline Journey And Plan Review — Local Checkpoint

Branch `codex/inlet-fresh-brand-pilot`, base `dc3c0d5`. The fresh browser journey
exposed a missing visible planning-budget creation/approval step. Added standalone
Plan Review using existing simulation mandate APIs, plus an owned CSRF-protected
planning-context endpoint that derives exact UTC boundaries from the confirmed
goal's timezone. Ambiguous/nonexistent local boundaries fail closed. Customers
explicitly review editable amounts within the goal ceiling, save, and separately
approve the exact revision. The fixed one-new-campaign profile is visibly a planning
simulation; it grants no live spending or publication authority.

Actual HTTPS/Chromium journeys start with zero customer/workspace rows and exercise
visible signup/provisioning, configured immutable TEST Stripe offer checkout and
scoped signed-event reconciliation, Google and Shopify OAuth/vault ownership,
Shopify import/publication, structured goal preview/confirmation, planning review,
separate campaign-content approval, native diagnostics, and truthful unavailable
automation. A second visible identity cannot read the first workspace; returning
as the first identity recovers persisted state without replaying checkout. Mocks
are external transport/identity boundaries and deterministic clocks, with explicit
worker advancement. No customer state is seeded to bridge journey stages. Google
connection and inventory reads are covered, not Google campaign metrics import.
No production execution approval, attempt, or automatic admission is created.

Final checks actually run on SQLite and isolated PostgreSQL schemas:
- Fresh browser plus planning-context suite: **11 passed, zero skips**,23.43s;
  `/tmp/fresh-final.log`.
- Existing portal/campaign-review/context regressions: **23 passed, zero skips**,
  22.63s; `/tmp/fresh-regression.log`.
- Whole Ruff clean; mypy **616 files** clean; JavaScript syntax and diff checks pass.

No Full or live pilot was run. Freeform milestone handling, calibrated direction,
strict native financial qualification, production execution, and live delivery
remain separate acceptance work. This package has no migration. Detailed scope and
harness boundaries are in `docs/design/fresh-brand-offline-pilot.md` and
`docs/design/fresh-plan-review-ui.md`.

Remote push/PR creation is temporarily held by the parent while an unexplained
GitHub pre-run CI failure is diagnosed. It is not established quota evidence.
This checkpoint is local only; no new hosted CI or remote write was requested.

### Plan Review Original-Session And Goal-Ceiling Repair — Local Only

Independent review reproduced stale-session/owner approval and an above-goal saved
simulation. Customer simulation mutations now take the canonical current original
session/role locks before mandate/action locks, with unchanged production default
roles and preserved analyst drafting. Shared validation enforces the confirmed
ceiling at create/edit/approve; zero and exact-ceiling simulations remain valid.

Real PostgreSQL workspace-lock barriers reproduced both prior HTTP200 approval
failures and now deny401/403 without approving the draft. Broader
identity/mandate/context/fresh HTTPS customer checks:90passed,2SQLite-only lock-race
skips(70.70s). Whole Ruff and clean mypy621 files passed. Focused new regression
matrix and local repair details: `docs/inlet-plan-review-safety-repair.md`.
No remote write, CI, live provider, financial gate change or Full run. Parent owns
local integration and subsequent qualification.
Final repaired-head focused matrix:28passed,2SQLite-only lock-race skips(21.31s).
Logs preserved in `/tmp/inlet-plan-repair-{combined,final-focused,types}.log`;
real PostgreSQL failing baseline in `/tmp/inlet-plan-repair-pg-baseline.log`.

### Repaired Fresh Customer Plan Review — Local Integration

Integrated local943ce8 and its independently reproduced/fixed authority defects7987f09.
All simulation mutations now take the original-session and current-role fence before
mandate/action locks. Trusted operation role sets preserve analyst drafting, owner-only
approval and owner/admin stop; existing production guard defaults are unchanged.
Shared service validation enforces confirmed-goal budget ceilings at create/edit/approve,
including saved plans, with zero/exact-ceiling budgets retained. No broader period
policy or live authority was added. Real PostgreSQL barriers reproduce the prior
200-after-revocation/role-loss defect and now deny without changing draft state.

Root fresh HTTPS browser, context, authority and identity suites **72 passed,
2 SQLite-only PostgreSQL-lock skips in48.43s**; log `/tmp/inlet-next-fresh-plan.log`.
Whole Ruff, mypy629, JavaScript syntax and staged whitespace passed. The visible
signup→test purchase→connections/import→goal→plan/content review→diagnostics and
second-identity path uses actual services with synthetic external boundaries, not
seeded customer-state shortcuts. This is offline continuity, not live purchasing,
automatic optimization or B20 live-pilot completion. Remote push/CI hold remains.

### B17 Initial Planning Contracts — Local Implementation In Progress

Parent explicitly authorized the next local-only package after `85e52eb`: retained
owned observations, reproducible calibration and exact initial recommendation preview.
Frozen typed contracts from `3c835fb` integrated as `ad59454`. Root contract tests:
**7 passed**; Ruff and mypy (4 source files) passed. This is an interface checkpoint,
not implemented customer behavior or B17 acceptance completion.

Implementation lanes share the frozen contract: prospective capture/calibration and
migration 0075; lifecycle deletion/retention/export fencing; customer API/browser and
native-state-bound preview. No implicit retention policy, numeric rule defaults or
5/10/20 calibration. Replay must preserve actual observation availability, separate
nonoverlapping windows and later revisions, and label results as descriptive sensitivity.
Existing mature-feedback and live-emission gates remain unchanged.

A preview cannot yet enter execution review: correction/erasure would also need to
invalidate any handed-off review's forward authority while retaining attempted obligations.
The package therefore reports `initial_preview_review_handoff_unavailable` explicitly;
it does not substitute a manual or recommendation-only release for the original scope.

Frozen `dc3c0d5` Full remains running separately (session65083; isolated candidate4
log/database). The hosted pre-run failure annotation remains unresolved. No confirmed
GitHub quota evidence has arrived. Pushes, PR creation and hosted CI remain held.

### Historical Social Review Migration Count Repair — Local Only

The frozen `dc3c0d5` Full failure is a historical test projection defect:
`Query(ProviderExecutionRun).count()` selects current ORM columns inside its
subquery even though migration0057/0059 predate `authority_kind`. Replaced both
counts in `test_social_configuration_migration.py` with a scalar count of the
historically available run ID. Upgrade/downgrade, retained-run count and foreign
workspace integrity assertions remain unchanged; no application fallback added.

Exact isolated predecessor reproduction: **1 failed** in5.43s with the reported
UndefinedColumn (`/tmp/inlet-social-historical-dc3-before.log`). Applying the same
patch gives migration/hash tests **2 passed** in3.38s
(`/tmp/inlet-social-historical-dc3-after.log`). All runs use generated disposable
schemas in `inlet_candidate_migration_ci`; frozen checkout/active Full database
were untouched. Whole Ruff, configured mypy **643 files**, and diff checks pass
on the final `f77fc4c` child.

The current-root focused run separately stops earlier: new planning validation
rejects the social fixture's100m mandate against its inherited50m goal budget
(`/tmp/inlet-social-historical-after.log`). This is reported to the planning owner
for legitimate fixture correction; the count repair does not bypass that check.
Local commit only: no push, PR, workflow dispatch or hosted CI.

### Owned Initial Observations And Lifecycle — Root Verification

Integrated core `7428640` plus actual-completion age/database-clock repair `2175a5b`,
bounded derived storage `ef849d2`, lifecycle `58326d4`, and historical 0074 fixture
ordering `0b17525`. Root suite covering initial observation/calibration/lifecycle,
existing three-provider performance, export privacy and customer closure:
**165 passed, 4 expected SQLite-only skips, 6 Alembic warnings in 126.13s**.
Log: `/tmp/inlet-next-initial-core-lifecycle.log`. Whole Ruff and mypy648 passed.

Complete fresh PostgreSQL migration validation **head0075 → base → head0075 passed**
on dedicated `inlet_oct06_0075_migration_ci`; `/tmp/inlet-next-0075-roundtrip.log`.
Independent review reproduced and then cleared the delayed-capture qualification
error. Its composed erasure/disconnect/expiry and populated migration checks:
**9 passed**, no skips; `/tmp/inlet-calibration-review-composed.log`.

No production retention or numerical policy is installed. Reports are reproducible
reported-efficiency sensitivity, never empirical/causal qualification. Customer API/UI
integration is still pending at this checkpoint; review handoff remains unavailable.

Frozen `dc3c0d5` Full first nested suite failed: **1 failed, 3616 passed, 73 skipped
in 2879.887s**. Preserved report: `/tmp/inlet-dc3-nested-full-0.xml`. Its historical
social migration test projected newer ORM columns before they existed. Local test-only
repair `7c4e333` was independently reproduced and verified on the frozen predecessor;
the outer Full continues unchanged. Current-root social fixtures also need a legitimate
confirmed goal budget matching their existing mandate; that separate test adjustment
is underway. No frozen-run success or later validation gates are claimed.

### Social Fixture Goal Ceiling And Historical Cleanup Compatibility — Local Only

Current social tests now request a100m goal budget at initial goal revision creation,
then use the real confirmation path before the existing100m simulation mandate.
The optional `goal_budget_micros` parameter passes through existing seed helpers;
all other callers retain the50m default. No immutable goal revision is rewritten,
no app ceiling is weakened, and no production code changes.

The historical migration helper now explicitly asserts all later initial-planning
observation/calibration/preview tables absent before stubbing only the new workspace
erasure hook. This lets real historical fixtures continue without introducing a
runtime missing-table fallback. The earlier scalar historical run-count repair
remains in place.

After integrating root `f5115e0`, focused SQLite/PostgreSQL social coordinator,
customer producer, default customer goal and execution mandate tests produced
**99 passed**; the batch's single historical failure occurred before its helper
repair (`/tmp/inlet-social-budget-fixture.log`,150.09s). The repaired historical
migration plus hash compatibility independently pass **2 tests** in4.69s
(`/tmp/inlet-social-budget-migration-final.log`). Whole Ruff, configured mypy
**648 files**, and diff checks pass. Generated schemas use disposable
`inlet_candidate_migration_ci`; no active Full database changes. Local-only delivery;
no push, PR, hosted CI, live provider call or Full run.

### Initial Reported Efficiency Customer Preview — Local Consumer

Branch `codex/inlet-initial-planning-ui`, shared contracts3c835fb and owned backend
7428640/2175a5b/ef849d2 integrated locally. Added `/app/initial-planning`, owned
intent-only capture/calibration/native-option/preview/read APIs, and persisted
preview delivery. Customers explicitly confirm a reported-event CPA objective;
server-owned observation cohorts and configured rule parameters are displayed.
No browser reporting proof, prior action, learned effect, or financial certificate
is fabricated. The real current Meta campaign budget owner can supply a nominal
before/after amount only with matching separately consented limits and environment.
No review handoff, execution approval, reservation or provider mutation is enabled.
Missing current native context is rendered unavailable, never zero.

Every native read is outside database transactions and followed by fresh original
session, goal, report-completion, source, policy and database-clock validation.
Amounts respect native currency quantum without rounding/clamping. Provider minimum/
acceptance and remaining financial/action/cooldown capacity are explicitly unverified.
Preview expiry is capped by original session and evidence/native/mandate lifetimes.
An engineering retention bound128 per owned campaign/environment includes unswept
expired rows; PostgreSQL workspace fencing serializes concurrent inserts. Original
manual optimization remains unchanged; no numerical production policy is installed.

Actual validation, SQLite and PostgreSQL:
- Combined consumer API/HTTPS Chromium UI/real Meta MockHTTP catalog plus shared
  capture/calibration/contracts and0075 migration: **73 passed,1 expected skip**,
  61.48s; `/tmp/initial-consumer-final.log`. PostgreSQL Alembic downgrade/re-upgrade
  passed; SQLite's PostgreSQL-only migration case skipped. Three existing Alembic
  `path_separator` deprecation warnings occurred.
- Added real PostgreSQL simultaneous preview requests at capacity1: exactly one
  succeeds and one is rejected; actual API default policy/calibration/preview caps
  and privacy erasure tests **2 passed** across both databases,6.41s;
  `/tmp/initial-consumer-bound.log`.
- Initial exact-amount suite10 passed and actual API/browser suite10 passed before
  the final combined run. They exercise actual MetaSyncService wire publication,
  retained observations, actual Shopify goal preview/confirmation, session/CSRF,
  and concrete MetaOptimizationTransport reads. Financial readers are sentinels
  that must never run. Actual session/generation changes during native IO reject
  persistence, as do environment mismatch and unrepresentable budget precision.

Test-only corrections during assembly: explicit Settings environment alias,
expected frozen unavailable HTTP409, and SQLite foreign-key enforcement for actual
cascade assertions. No production missing-table/foreign-key fallback was added.
The page displays safe text, clears changed context and logout state, and does not
retry requests. Full, hosted CI, push, PR, provider calls and live pilot were not run.
Remaining source/calibration qualification and durable review-handoff provenance
are documented in `docs/design/initial-planning-customer-consumer.md`.

Root's bounded consumer review found that stored preview delivery had not yet
compared the original actor/session with the incoming principal. Before freezing,
added that equality guard and exact row/document/intent/cohort/native/timestamp
bindings. An actual second valid session for the same owner now receives409 while
the original session can still read its preview. Final consumer API/actual HTTPS
browser/real Meta MockHTTP native suite: **22 passed**, no skips,43.43s;
`/tmp/initial-consumer-session-final.log`. This includes PostgreSQL simultaneous
capacity admission and SQLite with explicit foreign-key enforcement. Final whole
Ruff, configured mypy **652 files**, JavaScript syntax and whitespace checks passed.
A test-only concrete HTTP response-class identity assertion had failed despite a
valid200 response; the test now checks the actual required status/body behavior.
This package is frozen locally only, with no remote write or CI requested.
