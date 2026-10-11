# Inlet Build Progress

Current status entry point: [October 11 acceptance checkpoint](inlet-acceptance-20261011.md).
The [earlier matrix](inlet-current-acceptance.md) and entries below retain historical evidence.
This ledger retains chronological package and validation evidence; older entries do
not describe later code or qualify a different artifact.

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

### Initial Preview Stale Selection Repair — Local Follow-Up

Independent review reproduced HTTP500 for schema-valid native selections whose
account differed from the owned calibration objective. Both `/native-options` and
`/previews` constructed the strict internal intent without translating its domain
validation failure. Exact base `b92a3c8`: **4 baseline failures** across SQLite and
PostgreSQL, `/tmp/initial-intent-baseline.log`.

The API now shares a strict intent-construction helper that translates this
validation failure to a fixed, sanitized HTTP409 before provider IO. Internal
scope validation remains unchanged; no submitted IDs, objective contents, or
Pydantic diagnostics are echoed. Expanded coverage exercises stale account, goal,
and goal revision for both endpoints on both databases, asserting zero native
reads and zero inserted previews.

Actual checks: **34 passed**,54.74s for the new regressions plus existing customer
API, actual HTTPS browser, and real Meta MockHTTP preview paths
(`/tmp/initial-intent-final.log`). Exact final regression rerun after a test import
annotation adjustment: **12 passed**,14.87s (`/tmp/initial-intent-exact.log`). Whole
Ruff and configured mypy **657 files** pass; diff check clean. No Full, remote write,
CI request, or live call. Branch `codex/inlet-initial-preview-intent` is local only;
root integrates the separate goal-currency guard independently.

### Initial Customer Preview Package — Assembled Local Checkpoint

Integrated customer API/browser/native preview `5b0c037`, explicit goal/report
currency guard `ffe4bdc`, and controlled stale-selection rejection `4426e77`.
The real customer path captures owned Meta reports, confirms an explicit reported
CPA objective, runs chronological sensitivity comparisons and shows a nominal exact
budget preview when a matching owned native catalog and mandate are available.
Original-session reuse, foreign/stale inputs, corrections, expiry, capacity and
currency mismatches are rejected. No default numerical/retention policy, empirical
qualification, executable review handoff or live spending authority was introduced.

Root final consumer/API/HTTPS browser/native/currency/malformed-intent suites:
**48 passed, no skips in60.19s**, `/tmp/inlet-next-initial-consumer-final.log`.
An initial command used a nonexistent test filename and collected zero tests; the
corrected complete command is the result above. Whole Ruff, configured mypy658,
JavaScript syntax and whitespace checks passed. Earlier root composition165passed/
4expected skips and complete0075 migration roundtrip remain valid. Repaired social
coordinator/customer producer/historical migration on assembled branch: **41 passed**,
4Alembic warnings96.65s; `/tmp/inlet-next-social-fixture-repair.log`.

This completes the local retained-observation/calibration/initial-preview slice,
not B17 mature action-outcome learning, a purchasable live release or approval for a
recommendation-only release. Next proposal is retained in
`docs/design/b17-operational-feedback-next-package.md`: actual fixed-window acquisition,
configuration-associated comparable observations, retractable bounded feedback and
explained preview updates; policy/calibration/live qualification remain unset.

Frozen dc3 Full still runs unchanged at approximately42% of its outer suite, after
its nested failure. Four additional outer social-review browser failures are visible;
detailed tracebacks await terminal output. The historical ORM count failure has a
verified local repair. A delegated monitor owns terminal evidence collection and
subsequent isolated reproduction. No success is claimed for this Full. Hosted failure
annotation and release-scope questions remain unanswered; no confirmed GitHub quota
limit. All commits remain local under the push/PR/hosted-CI hold.


### Current Acceptance Matrix — Docs-Only Snapshot

Added `docs/inlet-current-acceptance.md` as the acceptance entry point for reviewed
code `31a412dfdd4c30b7e1e8bb5f01441d00f47d32e7`, tree
`84820fdac7bcf38e989598f302bc6ef8ed6f34f8`, migration0075, 2026-10-06 12:17UTC.
Separates IMPLEMENTED, FOCUSED-TESTED, AGGREGATE-TESTED and LIVE-QUALIFIED for B01–B20;
records actual default-unavailable runtime factories, remaining B17 ordinary code,
customer versus owner-managed webpage scope, commercial/policy inputs and live gates.
Older matrices have pointers; their evidence/counts remain unchanged.

Verified historical local Full8efe19668d4920df6607ddd60140ab8ab0779049 and tree
11252fdbc785c270b49a1340dff95506d7391405 using local git objects, wrapper exitfile0
and terminal log. Its hosted failure is retained; no newer aggregate success and no
live qualification is claimed. Parent confirmed31a412d snapshot and ongoing failed
frozendc3 run before commit. Dynamic terminal results belong in a later ledger entry.

Docs only: relative file links and whitespace checked; pytest/Ruff/mypy not rerun,
since no code changed. No Full, remote operation, provider call or policy activation.
### Initial Preview Review Lifecycle And Strict Export — Local Only

Registered0076's protected hash-only provenance link with explicit workspace scope,
strict scalar export and original-session exclusion. Protected execution review
exports include the initial-origin/required marker; nullable retraction never
asserts current authority. No aggregate payload or credential copy was added.

Actual Meta mocked-HTTP preview→qualified contract review fixtures passed against
metadata and actual0076 schemas on SQLite/PostgreSQL: immutable protected origin,
review deletion denial, nullable pointer erasure, no reattachment, deleted-child
retry denial, scoped/session-safe export and cached ordinary-marker refresh denial.
Actual migration downgrade refuses retained protected provenance. Combined new
and existing initial lifecycle/export/backend suite:45passed,1SQLite-only lock-race
skip(96.84s). Whole Ruff and clean mypy669 passed; whitespace clean. Evidence:
`/tmp/inlet-initial-handoff-combined.log`, `/tmp/inlet-initial-handoff-types.log`.
See `docs/inlet-initial-review-lifecycle.md`. Parent/backend owner retains attempted
historical reconciliation/settlement qualification. No remote/Full/live action.

### B19: Populated 0075 Native Restore Acceptance

Local isolated child of `9833b9f`; see
[inlet-initial-planning-restore-evidence.md](inlet-initial-planning-restore-evidence.md).
The real PostgreSQL archive now contains owned observation/calibration/dependency/
preview rows and checks strict export/session-hash exclusion, original owner/session,
source generation and expiry guards, actual configuration-independent expired-derived
cleanup, current-report availability, closing-compatible privacy erasure, immutable
triggers and composite ownership/cascades after restore. Existing financial holds,
replacement lineage, social approvals and failure-cleanup checks remain enforced.
Calibration/preview documents are synthetic insufficient fixtures, not a claim that
service admission or production policy qualification ran.

Exact command/environment is in the linked evidence document. Final
`pytest -o addopts='' -q tests/test_inlet_restore_drill.py`: **37 passed**, five existing
Alembic path-separator warnings, 105.70s. Includes actual native dump/restore and
injected archive/restore failures, plus SQLite/PostgreSQL strict serializer cases.
Log `/tmp/inlet-initial-restore-final.log`; terminal exit0. New dedicated database
`inlet_initial_restore_test_20261006`, container `inlet-b01-postgres`; no active Full
DB touched. Temporary restore schemas removed. `ruff check .`, configured `mypy`
(658 files), explicit mypy of both restore scripts (2 files), and `git diff --check`
pass. Initial three failed cases were a fixture-only wrong column name (`status`
instead of reservation `state`), corrected; no product defect inferred from them.

No product/migration changes, Full, remote writes, live calls or qualification.
This evidence is through0075. Root's later0076 protected preview-review lineage is
not populated by this fixture; run the combined drill after integration and extend
protected provenance coverage separately if required.
### 2026-10-06 — Initial Preview Customer Exact-Review Consumer (0076)

Local branch `codex/inlet-preview-review-ui`; predecessor shared core `7c5b365`
(local equivalent `65f1a1f`). Added original-session owned review readiness and
owner/CSRF preparation endpoints, preserving all immutable PreviewV1 bytes.
Readiness explicitly leaves financial qualification unchecked. Both endpoints use
the ordinary approval runtime dependency and reject absent/mismatched planning
context; browser submits only the server preview digest. The standalone preview
page now requests a separate exact review, links to the normal owned optimization
screen, and never automatically approves or executes. Query parameters are lookup
keys, not review authority. Session/objective/selection changes clear local state.

Verification actually run: combined API/core/customer contracts/default and
configured HTTPS browser/normal optimization browser suite **26 passed**;
after coherent generic-runtime assembly, affected API + HTTPS browser **8 passed**;
final missing-context/mismatched-policy API regressions **4 passed**, all with
SQLite and PostgreSQL enabled and no skips. Actual browser flow covers fresh
login → report capture → calibration → native options → exact preview → review →
ordinary separate checkbox/approval. Provider POST count remains zero. API checks
cover wrong digest, CSRF, extra proof fields, different valid original session,
idempotent response recovery, byte preservation, and capsule retraction with
financial review history retained. Whole Ruff and mypy (**667 files**) pass;
JavaScript syntax and diff checks pass. Logs: `/tmp/preview-review-consumer-final.log`,
`/tmp/preview-review-assembly-final.log`, `/tmp/preview-review-policy-final.log`.

No Full, remote write/CI, live provider calls, deployment, or production financial
qualification. Contract-test qualification/exposure readers are explicit test
fixtures. Production financial sources remain unavailable. Core migration,
forward-gate/late-retraction/concurrency qualification remains the separate 0076
backend package; this consumer adds no schema or provider mutation code.

### Frozen Full Social Browser Clock Repair — Local Only

Existing frozen `dc3c0d5` Full completed with exit1: outer pytest **6 failed,
3616 passed,68 skipped** in6285.54s. Failures were the nested Full wrapper, four
social-review browser platform/database cases, and the historical social migration
count. Original terminal log preserved at `/tmp/inlet-dc3-terminal-pytest.log`;
wrapper exit marker `/tmp/inlet-oct06-candidate4-full.exitcode`. No duplicate Full
was launched, and its checkout/database were not modified.

On isolated current root `3fcba5d`, all four actual social browsers reproduced
(**4 failed**,96.34s). Sanitized route/status capture established social options200
followed by campaign preview409 (`/tmp/inlet-social-browser-diagnostic.log`). The
fixture pinned social discovery to October5 but the preview API used wall time;
the outer Full crossed the fixture mandate's October6 noon expiry. The production
expiry gate correctly rejected the stale fixture.

The browser test now gives actual campaign preview and social discovery one
explicit fixture clock. It additionally advances that clock past expiry after
exact confirmation, then proves real review/save/confirmation are blocked and
private media cleared. Only test code changes; no application expiry fallback,
timeout extension or coverage removal. First repaired four-browser run **4 passed**
in20.96s. Final combined checks recorded below. No push/PR/hosted CI/live calls.

Final combined browser/API/migration/route suite: **16 passed,2 failed** in55.89s
(`/tmp/inlet-social-browser-final.log`). All four actual browser and all four API
cases pass. The two independent current-root failures are historical0057 fixture
insertion of later `provider_execution_reviews.initial_preview_origin_id` and the
route inventory missing `GET /app/plan-review`; both are reported for separate
integration repair, not hidden or bypassed here. Whole Ruff, configured mypy
**669 files**, JavaScript syntax and diff checks pass. This local commit contains
only the demonstrated browser clock repair, explicit expiry coverage and diagnostics.

### Later Preview Schema Historical Fixture And Route Inventory Repairs

The pre0059 social migration fixture now inserts its execution-review row through
an actual reflected historical Core table, then attaches that persisted identity
for the existing coordinator assertions. It explicitly rejects later provenance
markers; current ORM defaults cannot insert0076 columns into0057. Scalar historical
run counts and all existing downgrade/upgrade/foreign-workspace assertions remain.
No production model, service fallback or historical schema widening was added.

The actual0074 performance DDL test now downgrades0076 before0075 and restores0075
then0076 around both historical DDL paths. This preserves immutability, ownership
and deletion assertions without CASCADE or skipping the PostgreSQL case. Exact
static FileResponse routes `/app/plan-review` and `/app/initial-planning` are added
to the public-document inventory; authenticated data APIs remain guarded. The
consumer owner was notified to classify subsequent routes explicitly.

Final focused actual0074 (SQLite/PostgreSQL), social historical migration and
assembled route boundary suite **12 passed** in10.96s, no skips
(`/tmp/inlet-social-integration-final.log`). Whole Ruff, configured mypy **669 files**
and diff checks pass. Local-only followup to the browser clock commit; no remote,
Full, runtime permission or production changes.


### Assembled 0076 Acceptance And Frozen Full Repairs — Local Only

Code head1e337f9eff86353d068e46e2b9ed91c9a2bdec95, tree
861f1b557d0c3610865694e31f747269baefb31a, includes shared/core0076,
independent lifecycle/export, actual customer handoff and Full-failure repairs.
Original preview bytes remain immutable. The additive handoff uses the actual
generic runtime with matching planning context; no financial fixture becomes a
production source. Retraction blocks every forward stage, including final emission;
actual attempted receipt reconciliation and reservations survive evidence erasure.

Root command with explicit disposable PostgreSQL enabled:
`pytest -o addopts='' -q tests/test_initial_preview_review.py tests/test_initial_preview_review_api.py tests/test_initial_preview_review_contracts.py tests/test_initial_review_export.py tests/test_initial_review_lifecycle.py tests/test_initial_planning_browser.py tests/test_customer_optimization_ui.py`
**57 passed,1 expected SQLite-only concurrency skip,231.62s**,
`/tmp/inlet-next-0076-composed.log`. Whole Ruff and mypy670 passed at the assembled
consumer/lifecycle snapshot before the later test-only repair commits.
Fresh dedicated database inlet_oct06_0076_migration_ci: complete
`bash scripts/validate.sh Migrations` head0076→base→head0076 **passed**,
`/tmp/inlet-next-0076-roundtrip.log`.

Independent unchanged98a27b6 native restore composition: **37 passed**,5 existing
Alembic warnings97.79s, `/tmp/inlet-combined-0076-restore.log`, actual0076 schema
and populated0075 graph; protected0076 provenance not populated by that native
archive fixture. No fabricated cross-platform tombstone was added. Actual0076
DDL/provenance graph acceptance remains covered by separate lifecycle tests.

Frozen dc3 Full is terminal exit1: **6failed,3616passed,68skipped**6285.54s.
Nested wrapper and historical migration failures are repaired; four social-browser
failures were test-clock mismatch at real mandate expiry, reproduced then repaired
without weakening expiry. Root exact repaired composition
`pytest -o addopts='' -q tests/test_customer_social_review_ui.py tests/test_social_configuration_migration.py tests/test_campaign_performance.py tests/test_route_boundaries.py`
**36passed,4warnings,40.75s**, `/tmp/inlet-next-full-repairs-final.log`.
One preceding command named nonexistent test_customer_route_boundaries.py and
collected zero tests (exit4), `/tmp/inlet-next-full-repairs.log`; it is not a pass.

The current acceptance matrix now credits implemented/verified0076 behavior, not
just its design. B17 operational action feedback is actively under implementation
in isolated0077 branches; it is not integrated or accepted at this head. No current
Full success, live qualification, production policy, spend, merge/deploy, push/PR
or hosted-CI action is claimed. Remote hold and original launch scope remain.

### Frozen0076 Early Failure Repairs — Local Test Fixtures

Read-only exact-head collection mapped the first six Full failures to four Google
retirement/overdue tests and two archive/closure financial-social journeys. Isolated
reproduction at frozen `97e5f7b`: **6 failed** in8.04s
(`/tmp/inlet-0076-early-failures.log`). The frozen Full remains untouched/running.

Google completion timestamps use the repository wall clock, while the test observes
overdue obligations at a fixed October6 noon. After wall time crossed that cutoff,
zero overdue obligations was correct. The test now anchors the actual repository
clock to the import fixture time and asserts both persisted completion timestamps;
current-generation retirement and other-workspace preservation assertions remain.

The archive fixture now supplies100m as the social brand's initial confirmed goal
budget before its100m simulation mandate. An optional durable-fixture parameter
preserves50m defaults for every other caller. No immutable goal revision edits,
product ceiling changes or alert logic changes.

Targeted original six cases: **6 passed** in22.93s. Wider actual attention,
archive/closure and durable optimization suites on SQLite/PostgreSQL: **66 passed**
in86.14s, no skips (`/tmp/inlet-0076-early-final.log`). Whole Ruff, configured mypy
**670 files**, and diff checks pass. Local-only commit; no push/PR/CI, additional
Full or live provider calls. Existing frozen Full is separately monitored.
### B17 Operational Reported Feedback: Lifecycle0077 — Local Only

Isolated lifecycle child of assembled0076 `98a27b6`; consumes core contracts/services
through upstream `e832d25` and Meta acquisition `efd11ce`. See
[inlet-reported-feedback-lifecycle.md](inlet-reported-feedback-lifecycle.md).
New0077 explicitly creates/classifies five erasable owned tables and expands the
Meta phase constraint. Core numeric documents/dependencies are immutable; job
progress stays writable without changing its original owned/session/policy input.
Deleting any comparison/dependency/capsule conservatively retracts all workspace
feedback slots, including indirect contributors. Semantic privacy/closure erases
the graph; ordinary terminal correction preserves capsules/jobs but retracts
comparisons before the next completion stamp. No protected financial writes.

The existing independent housekeeping dispatcher now sweeps persisted expiries
without configured capture policy or active-workspace admission. Capsule expiry
also retires its request. Strict exports omit original-session digests, bind typed
JSON to scalar scope/digests, include all expiry deadlines, and freshly validate
both comparisons and slots using core validators under workspace fencing after
identity IO. A cached archive does not bypass original authority or dependency
revocation. Positive actual Meta acquisition→comparison→archive coverage revokes
the original comparison session while exporting through a different still-valid
owner session; delivery then fails closed. Acquisition uses an explicit offline
future-window clock; this is not live maturity/report-finality qualification.

Before freeze, a new migration test reproduced SQLite native staging loss under
foreign_keys=ON during batch constraint rebuild: **1 failed,1 passed** (PostgreSQL
preserved it). The migration now preserves exact metrics/checkpoint/cursor/page
rows in connection-local temporary tables, restores in parent order, verifies
bidirectional equality and foreign keys. Downgrade refuses any rf_* phase. Fixed
actual migration/historical0074 dependency ordering: **5 passed,1 SQLite-only
migration skip**, `/tmp/inlet-reported-migration-final.log`. No destructive shortcut
or foreign-key disabling. Root historical-schema repair `1e337f9` was incorporated.

Focused evidence, separate from any Full/aggregate qualification:

- Structural lifecycle/strict export graph: **12 passed** both databases;
  `/tmp/inlet-reported-lifecycle-tests.log`. Actual offline Meta receipt/hold,
  synthetic insufficient comparison/slot documents; no fabricated stability claim.
- Final broad focused command below: **143 passed,3 expected SQLite-only skips**,
  four existing Alembic warnings,401.68s; `/tmp/inlet-reported-lifecycle-combined.log`.
  This ran while the final comparison-only export validator integration was being
  completed separately; it is not an immutable whole-tree qualification.
- Final changed export/dependency path plus actual composition and PostgreSQL
  fail-fast raw-deletion lock test: **7 passed,1 SQLite lock skip**,65.48s;
  `/tmp/inlet-reported-export-final.log`. SQLite archive uses a real file/WAL engine.
- `ruff check .`, configured `mypy` (**694 files**), and `git diff --check` pass.

Commands use only dedicated `inlet_initial_restore_test_20261006`, never candidate4:

```sh
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_initial_restore_test_20261006 \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true /workspace/inlet-venv/bin/pytest -o addopts='' -q \
  tests/test_reported_feedback_lifecycle.py tests/test_reported_feedback_migration.py \
  tests/test_reported_feedback_acquisition.py tests/test_reported_feedback_service.py \
  tests/test_reported_feedback_evaluator.py tests/test_customer_exports.py \
  tests/test_initial_planning_lifecycle.py tests/test_customer_quiescing.py
AD_ANALYZER_TEST_POSTGRES_URL=postgresql+psycopg://postgres@127.0.0.1:55432/inlet_initial_restore_test_20261006 \
AD_ANALYZER_CI_DISPOSABLE_POSTGRES=true /workspace/inlet-venv/bin/pytest -o addopts='' -q \
  tests/test_reported_feedback_exports.py tests/test_reported_feedback_composition.py \
  tests/test_reported_feedback_lifecycle.py::test_raw_erasure_fails_fast_behind_workspace_fence
```

Earlier fixture-only failures were a missing Workspace.client_name and unclassified
owned job checkpoint fields; both corrected and relevant regressions passed. This
package does not claim positive multi-original operational learning or a populated
feedback-slot customer handoff; the core/consumer composed journey remains separate.
No Full, remote push/CI, live calls, policy defaults, deployment or spend authority.
### 2026-10-06 — 0077 Operational Comparison Customer Consumer

Local `codex/inlet-reported-feedback-ui`, based on frozen `b5595a0` with core
`8aaf345`, `d4e92eb`, `62b1da7`, `f1922ad` integrated as local equivalents.
Added the standalone Reported Action Comparisons page, History/Workspace links,
and owner/original-session/CSRF APIs for bounded owned action/baseline discovery,
request/history/status/detail, explicit re-observation, and explained preview
update/read. Service transactions commit on successful POST; detail commits its
immutable local assessment/dependencies. No provider I/O runs in these endpoints.
Existing 0076 initial-preview/review UI is untouched.

The UI displays explicit configured comparison and feedback parameters, both
windows' spend/events/CPA, missing dates, acquisition observations, revision
agreement and configuration-observation uncertainty. An insufficient comparison
cannot update a preview. The update shows baseline/delta/result, both CPAs, exact
applied policy and distinct original-action count. It grants no review handoff or
spending authority; no production parameters are installed. Original-session and
workspace/input changes clear derived state, including late async responses.

Checks actually run: **13 passed**, no skips, with SQLite and PostgreSQL enabled
(`tests/test_reported_feedback_customer_api.py`, customer browser, contracts).
Actual API coverage resolves a real mocked-HTTP Meta action receipt, discovers its
owned campaign, admits/replays one original-session job, reads history/status,
rejects another valid session and incomplete detail/re-observation, and adds no
provider mutation beyond the fixture's original action. Actual HTTPS default-off
browser checks use real auth/APIs. Configured rich rendering/re-observation/apply
and stale-response browser cases use explicitly controlled JSON projections and
are NOT the final acquisition-to-feedback integration. Whole Ruff, mypy **675
files**, JavaScript syntax and diff checks pass.

Log `/tmp/reported-feedback-consumer-final.log`. No Full, remote calls/writes,
CI, live provider access, deployment or production qualification. Remaining
composed acceptance: root's actual Meta fixed-window acquisition through core
capsules/comparison to this API/UI's genuinely computed updated preview. Core
migration/lifecycle/aggregate retraction remains owned by the 0077 backend lane.

### 0077 Fixed Current Report And Real Initial Baseline — Local Verification

The genuine fixed-window acquisition→initial capture composition first failed:
`campaign_performance.read_current` required rolling coverage/time even when the
current completion was an actual fixed acquisition. The reader now accepts an
alternate local proof only for the exact acquired campaign: retained immutable
capsule and job commitments, current request head, original session, exact
completion/run/window/time, source generation and privacy. Existing current
pointer and complete metric manifest checks remain. No default policy, financial
eligibility, provider I/O, or rolling timestamp rewrite is introduced.

The genuine service journey passes on both databases: mocked HTTP fixed reports,
actual initial captures/calibration, refreshed commerce, separately consented
current fixture mandate, actual native catalog/read and initial preview, then
explicit computed feedback. Fixture reported CPA changes 5→2.5; native45 produces
initial46 and updated47 (currency units). Provider writes remain the one original
fixture action. Sixteen cases pass including deleted capsule/job, expiry,
supersession, source generation, session and other-campaign rejection. Whole Ruff
and mypy681 pass. Logs: `/tmp/reported-feedback-real-preview.log`,
`/tmp/reported-feedback-journey-mypy-full.log`. Actual composed browser remains
next; no live qualification, review handoff, remote actions or Full run.

Broader composition check: campaign-performance/acquisition/comparison collected
suite has39pass/3fail. Two failures are pre-existing missing0077 lifecycle table
classification when these models load together; one is historical0074 downgrade
fixture dropping0075 under a0077 FK. Backend owner notified. Standalone campaign
performance suite22pass; these integration gaps are not represented as passes.

### 0077 Actual Changed-Preview Customer Browser — Local Verification

The actual HTTPS Chromium journey now passes on SQLite and PostgreSQL. A real
customer login/session submits the comparison intent through the customer UI;
test-only worker advancement acquires four actual mocked Meta HTTP windows. The
fixture invokes genuine0075 capture/calibration, current commerce refresh,
separate explicit fixture consent and real native catalog/initial-preview services
(no inserted observation, calibration, comparison or preview documents). Browser
status/detail/apply use actual APIs and computed responses, displaying beforeCPA5,
afterCPA2.5, initial46 and adjusted47. Only the original fixture advertising action
was emitted; updated-preview review handoff remains unavailable.

The fixture explicitly extends its login lease to span its future closed reporting
windows; no production session setting changes. Provider transport and numeric
policies remain explicit contract-test fixtures. Late actual apply responses after
workspace change or actual session rotation cannot restore stale values. Logout
clears state. Final consumer run: **11passed**, zero skips (actual browser, API,
default-unavailable and controlled-rendering regressions). Ruff, mypy682files,
JavaScript syntax and diff checks pass. Log:
`/tmp/reported-feedback-actual-consumer-final.log`.

This verifies offline customer composition, not production policy qualification,
multi-original historical learning, live report stability, deployment or spending
authority. No Full, remote call/push/CI or live provider operation was performed.

### Operational Feedback Exact Arithmetic And Idempotent Preview — Local Only

Isolated successor of `2d3b9b1`. Reproduced Decimal rounding in the prior CPA-derived
ratio: $700 / 21 versus $700 / 42 produces `0.499999...`, then a 249999-micro
adjustment where the exact reported ratio implies 250000. Compute relative change
from cross-products of original spend/conversion totals. Repeated identical current
comparison/baseline/policy application now returns the same freshly validated slot,
without compounding or incrementing the original opportunity count.

Focused exact-base command: `pytest -o addopts='' -q
 tests/test_reported_feedback_evaluator.py tests/test_reported_feedback_preview_guards.py`
with explicit disposable PostgreSQL configuration: **12 passed**,15.01s. Actual Meta
wire acquisitions, real calibration/native baseline and both databases verify
same-slot replay, count1, policy-revision denial, physical capsule→slot retraction and
unchanged protected attempt/receipt/hold counts. Whole `ruff check .`, configured
`mypy` (**702 files**) and diff checks passed. Logs `/tmp/inlet-rf-final-guards.log`,
`/tmp/inlet-rf-final-ruff.log`, `/tmp/inlet-rf-final-mypy.log`.

No Full, remote operation, live provider request, production policy qualification,
new execution authority or spend. This does not report another worker's joint run
as passed; that frozen run was still pending at this checkpoint.

### 0077 Assembled Replacement Fence Repair

At assembled2d3b9b1, actual browser repeated Apply exposed DELETE-trigger privacy
revision invalidation. Core3b8092b fixes identical retries by returning the existing
fully validated preview. Both actual HTTPS browser cases now pass with genuine
workspace and original-session late-response checks retained.

A different feedback policy still returned a newly saved preview whose baseline
was immediately unreadable. Controlled both-database regression failed twice
before repair. Apply now rereads the exact initial preview after the slot mutation
and final original-session/source checks. Failure propagates before API commit;
transaction rollback preserves the old slot, source privacy revision and readable
baseline. No immutable source rebasing or export/privacy trigger weakening.

Six focused guard+actual-browser cases pass, zero skips; Ruff, mypy702, JavaScript
syntax/diff pass. Logs `/tmp/reported-feedback-replacement-baseline.log` (2 baseline
failures), `/tmp/reported-feedback-replacement-fixed.log` (6pass). Limitation:
changed-input replacement while deleting a retained slot is rejected. Separate
immutable revision/current-pointer design is prepared at
`/workspace/inlet-design/REPORTED-PREVIEW-REVISION-PROPOSAL.md`; no schema change in
this repair. No Full, remote writes or live provider calls.

### Reported Comparison Static Route Classification

Verified `/app/reported-comparison` returns only its static FileResponse shell.
Customer values are fetched through the original-session/owned APIs; the public
HTML contains no customer state. Added this GET to the explicit PUBLIC route
inventory alongside Initial Planning and Measurement History. Full route-boundary
file:9pass, zero skips; Ruff/mypy702/diff pass. Log
`/tmp/reported-feedback-route-boundaries.log`. No product authorization change.
### Fixed Meta Report Retry Preserves Its Original Acquisition — Local Only

Isolated successor of `3b8092b`. An actual injected `URLError` at rf_adsets reproduced
on SQLite/PostgreSQL: initial `meta_unavailable`, no read before persisted backoff,
then `meta_reported_feedback_authority_changed` instead of resumption at the deadline.
The previous transport error was being interpreted as lost original source authority.
Before repair: **2 failed**,9.23s (`/tmp/inlet-rf-retry-before.log`).

The existing page savepoint now clears only `meta_unavailable`/`meta_throttled`, only
for a bound fixed run with a persisted retry deadline that has elapsed, before the
unchanged full lease/session/source/receipt checks. It does not clear fatal errors
or missing deadlines. Failed pages restore the savepoint and use the existing error
handler/backoff; successful pages retain the same original run/start timestamp.

Actual HTTP timeout/throttle, before/exact deadline, same-run completion, original
session revocation, source-generation drift, HTTP401 reconnect and missing-deadline
cases passed both databases. Final focused command with explicit disposable PG:
`pytest -o addopts='' -q tests/test_reported_feedback_retry.py
 tests/test_reported_feedback_acquisition.py` — **28 passed**,61.99s;
`/tmp/inlet-rf-retry-final.log`. Whole Ruff, configured mypy (**703 files**) and diff
checks passed. The fixture's opener lookup/header typing was corrected before static
checks; those were harness typing issues, separate from the reproduced product bug.
No Full, remote action, live API, provider mutation, runtime enable or spend authority.
## Populated 0076/0077 Native Restore Followup (Local Only)

Isolated successor to root `2d3b9b1`, branch
`codex/inlet-populated-0077-restore`. New test-only coverage builds real offline
Meta preview-review and operational reported-feedback graphs through existing
fixtures/services, then performs native `pg_dump`/drop/`pg_restore` in separate
fixture-owned Alembic schemas. Complete schema/data/privilege fingerprints must
match. Restored protected provenance, strict session exclusion and cross-workspace
exclusion remain enforced; original-session revocation, source generation change
and expiry deny numeric reads; semantic privacy erasure retains original financial
receipts/reservations. The original advertising HTTP POST remains a controlled
fixture action, never a live provider call. No production files or migrations
changed. See `docs/inlet-populated-planning-restore.md` for the exact command.

Early new-test failures were fixture mistakes (session field and injected clock
shape), not reproduced product defects. The final checks and local log are recorded
below; existing Full/hosted evidence is unchanged. No remote operation, Full,
production restore, physical media restore or live qualification is claimed.

Final immutable-test-file run: **2 passed, 2 expected SQLite skips**, two existing
Alembic configuration warnings, **61.79s**; log
`/tmp/inlet-populated-planning-restore-final-pass.log`. `ruff check .`, configured
`mypy` (**702 source files**) and `git diff --check` passed. Dedicated database:
`inlet_initial_restore_test_20261006`; active candidate databases were untouched.


## October 7 Recovery And CI Cost Package

Owner resumed Inlet only, reporting a $10 monthly Actions budget and confirming
full-scope Inlet as the MVP. Recommendation-only is not an accepted replacement.
Existing live/credential/spending/merge/deployment gates remain. A confirmed renewed
usage limit stops work again. Other projects and website work remain paused/outside scope.

Preserved a1adc737 on an isolated codex/inlet-ci-cost-reliability worktree. Remote
reads verified main ea3591c and development d897d1d. Shell Actions API is Forbidden;
the connector succeeds. Repository-scoped in-progress, queued and waiting queries
all returned zero; no cancellation, push or hosted run was performed.

Replaced recursive test-owned Full execution with bounded real Bash/PowerShell
orchestration coverage. Scripts and product code are unchanged. One real entire
suite and every downstream gate remain required. Added per-workflow/PR/ref stale-run
cancellation, preserved manual runs, pip/npm caching and explicit timeouts. Workflow
triggers and Validation context unchanged. Static/preflight checks precede aggregate;
bounded failure artifacts now consume the actual aggregate JUnit report.

Checks: automation/orchestration/diagnostics with actual dedicated disposable PG,
60 passed/22 PowerShell skips in 30.55s; final bounded checks 27 passed/16 PowerShell
skips in 6.27s; unchanged real Focused gate 37 passed/6 PowerShell skips/29 deselected
in 27.52s. Whole Ruff, mypy705 and diff checks passed. Structural full-suite invocation
count drops five to one; hosted savings unmeasured. Historical job112185728275 took
144.6 runner minutes, including57.18 in final Focused. Do not equate local seconds
with hosted billed savings. Details and logs: [CI cost recovery](inlet-ci-cost-recovery.md).

Next: preserve this reviewable package; run known repaired product fixtures on the
assembled candidate, then one real local Full before a single deliberate hosted
qualification. The October6 interrupted runs remain non-passing evidence. Product
backlog/production runtime and qualified financial evidence gaps are not solved by CI.

### Independent CI Review And Previously Skipped Cases Closed

Independent read-only review of155dad29 found no actionable regression. Official
Microsoft PowerShell7.6.6, SHA256-verified and installed in a workspace-local prefix,
now executes through a launcher using writable XDG directories (sandbox HOME remains
unchanged). The initial read-only-cache launch failures are recorded, not hidden.
Final combined automation/orchestration/diagnostics run: **83 passed, zero skips,
41.60s**, including all22 previously skipped PowerShell cases and real PostgreSQL
repeat/reset integration. Log /tmp/inlet-ci-powershell-closure-fixed.log. Real browser
H.264/AAC preflight passed too. See inlet-ci-cost-recovery.md for source/install and
review evidence. No hosted run or product qualification is claimed by these checks.

## October 7 — Local Qualification Repairs In Progress

Frozen candidate `9396839c9128bfa5862122fbc1674c541932cf24` remains unchanged in
`/workspace/inlet-oct07-validation`. Its single Full run started about 05:56:57 UTC
and is still running; it has a recorded failure and is not qualified. No hosted
run, push, merge, deployment or live provider call has occurred in this package.

The historical 0062 candidate migration test invokes current fixture producers.
A newer planning privacy hook reached `reported_feedback_jobs`, which correctly
does not exist at 0062. Reproduced against disposable PostgreSQL, then used the
existing test-only `without_initial_planning` adapter, which asserts the historical
planning tables are absent. The actual populated candidate upgrade/downgrade
and retained-mandate assertions remain intact. Application guards are unchanged.

Broader checks exposed two tenant-isolation fixture failures: seed wrappers did
not forward the shared seed's `days` and `goal_budget_micros` keyword arguments.
The two tenant wrappers and the identical feedback-erasure wrapper now forward
those arguments while preserving their distinct workspace slugs.

Checks actually run on `codex/inlet-oct07-validation-repairs`:

- Historical migration reproduction failed with missing `reported_feedback_jobs`;
  the repaired exact migration case passed. Logs: `/tmp/inlet-oct07-candidate-repro.log`
  and `/tmp/inlet-oct07-candidate-fixed.log`.
- Candidate migration, candidate service, initial-planning lifecycle and reported
  lifecycle: **2 failed, 81 passed, 2 skipped in 215.04 seconds** before keyword
  wrapper repair. Both failures were the tenant wrapper on SQLite/PostgreSQL.
  Both skips are SQLite-only row-lock tests, whose PostgreSQL variants ran.
  Log: `/tmp/inlet-oct07-repair-focused.log`.
- Repaired tenant-isolation case plus all feedback-storage cases: **26 passed in
  41.57 seconds**, SQLite and PostgreSQL. No skips.
  Log: `/tmp/inlet-oct07-fixture-kwargs-fixed.log`.
- Whole-tree Ruff passed; mypy passed **705 source files**; `git diff --check` passed.

Remaining: collect the frozen Full terminal result and every gate, repair any
additional failures locally, then qualify one new immutable candidate before the
authorized single normal PR-triggered hosted run. These focused results are not
a full-suite or live-qualification claim.

### Historical Financial Producer Fixtures

The frozen Full exposed the same later-planning-table mismatch in the populated
0064 feedback migration. Isolated reproduction failed; adding only the historical
planning-hook adapter then exposed the newer `initial_preview_origin_id` ORM
column absent from the historical review table (**1 failed, 24 feedback-storage
cases passed in 38.15 seconds**). These failed results remain in
`/tmp/inlet-oct07-feedback-migration-repro.log` and
`/tmp/inlet-oct07-feedback-migration-fixed.log`.

The final repair creates the genuine mocked-provider receipt graph at the current
schema, then downgrades to the historical predecessor before testing the target
upgrade, populated dependency erasure and roundtrip. It preserves application
authority guards and does not add historical columns or a missing-table runtime
fallback. Receipt/reservation identities are captured before the preparatory
downgrade and asserted unchanged throughout the feedback migration.

The related 0056→0057 owned-outcome migration independently reproduced the same
missing review-origin column (**1 failed, 1 passed in 6.26 seconds** in
`/tmp/inlet-oct07-historical-financial.log`) and now uses the same genuine graph
preparation. Actual owned-assessment create/read and repeated-upgrade assertions
remain. Final paired migration check: **2 passed in 6.89 seconds**, disposable
PostgreSQL, `/tmp/inlet-oct07-historical-financial-fixed.log`. The preceding exact
feedback migration check passed in 4.34 seconds.

The original Full is still running on unchanged9396839; its results are not
relabelled with these repairs. A subsequent frozen candidate must pass Full before
the single authorized hosted qualification.

### Combined Failure Cohort And Independent Review

At exact `46d55660dc7fb924bbbd3f249243642f82676345`, all 21 identified
failure cases were run together with the relevant candidate, feedback, owned
outcome, provider coordinator and Google action-plan fixture consumers:
**115 passed, 2 SQLite-only concurrency skips in 138.64 seconds**. Their
PostgreSQL variants passed. JUnit case-ID comparison confirmed every one of the
21 failing node IDs was present and passed. Evidence: `inlet-oct07-fixture-cohort`
log/XML/coverage JSON under `/workspace/inlet-evidence/20261007`, with hashes.
Independent read-only review of46d5566 against9396839 found no actionable issue
or weakened product assertion; production code and runtime guards are unchanged.

### Replacement Migration Historical Fixture

The still-running frozen Full subsequently found a 22nd failure: the 0058
replacement migration's current review producer inserted a later provenance
column. Its exact reproduction failed. Preparing this graph at head then
downgrading correctly refused to discard protected Google0066 completion
evidence (**1 failed, 27 repeat-optimization consumers passed, 1 SQLite-only
concurrency skip in 46.15 seconds**). That protected-evidence guard is unchanged.

The final fixture stays at0058 and reuses the existing reflected historical review
insert, which asserts all later authority markers are absent/unset. A test-local
session supplies the two initial-preview discriminator values only after asserting
those columns do not exist; it makes no SQL writes and leaves the actual forward
owned-review guard in place. Existing explicitly historical candidate/session/
Google-capture adapters remain. The empty0058 roundtrip and populated downgrade
refusal are retained, now asserting the exact replacement ID set before and after
refusal. No production fallback, evidence deletion or migration-policy weakening.

Exact repaired PostgreSQL case: **1 passed in 4.55 seconds**. Whole-tree Ruff,
mypy705 and diff checks passed. Failed/intermediate and final logs remain:
`/tmp/inlet-oct07-replacement-{repro,fixed,historical,historical-fixed}.log`.
All failures must be included in a final combined cohort on the repaired tree
before one successor Full. Frozen9396839 has not yet reached terminal; no hosted
qualification has begun.

### Frozen Full Terminal Result — October 7, 07:01 UTC

Exact frozen head9396839/treef0e6c2a ran **one** complete pytest invocation. Process
ancestry also showed one complete-suite subprocess, not recursive Full children.
Full started05:56:56 UTC and exit1 was recorded07:01:36.577 UTC: **64m40.58s**
wall duration, including shutdown. Pytest reported **24 failed, 4,081 passed,
72 skipped, 138 warnings in 3770.08s (62m50.08s)**. This is failed qualification.

Disposable-target guard, reset and upgrade-to-head passed. Full stopped at pytest;
Ruff, mypy, diff, PostgreSQL, Migrations, ReadOnly, Security, Privacy and Focused
were **not reached within this Full**. Separately run static/focused checks are
not represented as completed Full gates. Exact failure inventory and gate results:
[immutable run record](validation/inlet-20261007-9396839.json). Full log, exitcode,
process evidence and checksummed focused logs are preserved under
`/workspace/inlet-evidence/20261007`. No hosted run has started; no dollar-savings
claim is made.

The final two failures were the two-brand pilot's fixture setup lambda rejecting
the shared producer's explicit total_budget keyword. It now accepts that exact
parameter and asserts False, preserving this pilot's reviewed daily-budget case
instead of silently accepting another mode. Both SQLite/PostgreSQL cases passed
in12.35s (`/tmp/inlet-oct07-pilot-fixed.log`). Whole Ruff, mypy705 and diff checks
passed. All corrections remain tests/docs only.

Independent read-only review of c906a9e's historical replacement correction found
no actionable issue: absent-column assertions, actual owned forward guard and exact
replacement-ID preservation remain. Next: include **all24** terminal failure IDs
plus relevant fixture consumers in one combined invocation on the assembled repair
tree, then exactly one successor Full. Existing115-pass/2-skip evidence at46d5566
covered the first21 cases and is retained without overstating its scope.


### October 7 Successor Full — Terminal Failure And Concurrency Diagnostics

Frozen `5f24d8187757ff757eea6dbbe3147a1640ee1841` ran one complete pytest
invocation. Pytest finished **1 failed, 4,104 passed, 72 skipped in 4171.13s**.
Full exited1 at08:19:52 UTC after **4284.23s (71m24.23s)** including shutdown.
Guard/reset/upgrade passed; all later Full gates were not reached. The exact
[run record](validation/inlet-20261007-5f24d818.json) and external evidence preserve
this failed qualification. No hosted run or dollar-savings claim follows from it.

The failure was `test_simultaneous_first_meta_connections_resolve_without_deadlock`
(PostgreSQL), at the five-second first-worker insertion wait, before the second
connection started. The original harness did not surface the first worker outcome
on this path. Its precise delay or exception cause is therefore **not established**;
isolated passes are not evidence that the full-suite failure was fixed.

Investigation confirmed a fresh unique schema per customer-engine test, explicit
pool disposal/schema cleanup, and the existing workspace-first Meta lock order.
Unchanged isolated cases passed2 in2.76s. The immediately preceding seven Meta files,
including the failing case, passed73 with2 expected SQLite-only skips in46.32s.
Neither run reproduced the original failure. Independently, the harness's separate
5s startup and5s observation allowances competed with its10s winner-release wait.

A controlled six-second delay before the first worker's database work reproduced
exactly the old insertion-wait assertion:1 failed in9.37s. The repaired harness
uses one bounded30s observation deadline, longer worker/database watchdogs, a bounded
observer query, monotonic stage diagnostics and surfaced worker exceptions. It
retains actual PostgreSQL blocker observation, the blocked second future, exact loser
error and all one-connection/account/integration/grant ownership assertions.
New regressions exercise delayed startup and immediate first-worker failure. No
production code or account-lock behavior changed.

Normal and delayed cases initially passed4 in9.59s. A temporary negative control
removing only the test's workspace-lock delegation still failed in2.88s when the
second account reached insertion; the delegation was restored immediately. Thus the
harness does not accept missing serialization. Final preceding-Meta cohort plus both
new regressions: **77 passed,2 expected SQLite-only skips in51.94s**. Whole Ruff,
mypy705 and diff checks passed. Independent read-only review found no actionable
issue and retained the unresolved-original-cause caveat. These are focused results;
a new immutable candidate must still pass Full before any hosted qualification.

Logs `/tmp/inlet-oct07-meta-{delayed-baseline,race-repaired,fence-negative-control,
final-cohort}.log`, original trace, exitcode and full log are preserved with hashes
under `/workspace/inlet-evidence/20261007`. New product packages remain isolated.

### 0078 Immutable Feedback Revisions And Current Pointer — Local Package

Existing `reported_feedback_slots` now retains immutable revisions (same v1 IDs,
JSON bytes/digests and old revision values). `reported_feedback_current` identifies
the exact owned current revision with a composite FK and immutable group fields;
updates permit only a different slot at exact revision+1. The service serializes
append/pointer advance under original workspace/session authority, reuses an exact
current replay, caps retained rows at128 including unswept expiry, and revalidates
baseline/source/session before commit. Pointer loss never selects an older row.
Existing public reads are current-only; exports retain strictly validated as-of
rows and commit the pointer in their freshness stamp. Appending changes that stamp
without erasing data or rebasing source privacy. Genuine erasure, correction,
retention and financial-history isolation remain intact.

Migration20261007_0078 follows0077. It preserves populated row bytes/revisions,
seeds exact pointers, and refuses downgrade when retained history or deleted
current state would be lost/revived. SQLite batch alteration temporarily preserves
and restores exact referencing trigger SQL; FK enforcement remains enabled.
Explicit lifecycle/strict scalar export classification includes the new table.

Checks actually run (SQLite and PostgreSQL, no Full):
- Revision/guard/actualHTTPS suite26passed,2expectedSQLite concurrency skips:
  `/tmp/reported-revisions-final.log`.
- Missing-pointer downgrade regression2passed:
  `/tmp/reported-revisions-missing-pointer.log`.
- Schema/lifecycle/historical0077 suite32passed,2expectedSQLite skips:
  `/tmp/reported-revisions-schema.log`.
- Targeted populatedDDL/concurrency/finalsession run6passed,2expectedSQLite skips:
  `/tmp/reported-revisions-races.log`.
- Broader performance/API/comparison run33passed,2historical0074 fixture failures
  (`/tmp/reported-revisions-regressions.log`). Fixed the remaining historical
  teardown block to remove0078 before0077 and restore it afterward; both failing
  cases thenpassed (`/tmp/reported-revisions-historical-fixed.log`). The earlier
  invocation is not represented as green.
- Whole Ruff, mypy707files and diff checks pass.

Covered genuine changed-policy and newly prepared unadjusted-baseline replacement,
no compounding, old bytes preserved, superseded/public-read rejection, pointer and
current-row deletion no fallback, exact replay, PostgreSQL identical/different
concurrent requests, final authority rollback, FK/+1 guards and bounded retention.
ActualHTTPS continues to verify response/session changes discard stale output.
No live policy, spending permission, adjusted-preview handoff, remote actions or
provider calls were enabled. V2 read-only native baseline integration remains a
separate shared-interface follow-up; this package preserves v1 behavior.
### Planning/Reporting Runtime First Contract Checkpoint — 2026-10-07

Local successor of frozen9396839; proposal2230e15 approved for staged implementation.
Added separate deeply frozen native budget request/observation/owner/catalog ports,
without qualification IDs or a financial period. Tuple-based owner topology retains
existing target-set semantics and checks its exact digest. No native IO or runtime
activation is introduced. Added explicit initial/window/optional-feedback/read-limit
profile and bounded local JSON loader: missing pair is unavailable, malformed or
partial configuration, duplicate keys, oversized input, policy drift and digest
mismatch fail with a fixed sanitized error. The caller retains the immutable profile;
there is no implicit cache, principal, engine selection or hot reload.

Validation:32 focused contract/configuration/legacy initial-policy tests passed in
1.59s; whole-tree Ruff passed; whole-tree mypy passed711 source files; diff-check
passed. First mypy attempt found only three frozen-assignment test typing errors,
repaired before the final checks. No Full, remote, provider or deployment actions.
Next: shared neutral Meta parser and actual owned GET-only collector, then API/worker
assembly and explicit v2 preview with lifecycle/consumer version dispatch. This
checkpoint does not implement those behaviors or qualify any writes. Feedback
revision service/models/migration0078 remain owned by the separate package.

### Owned Native Meta Budget Collection — 2026-10-07

Successor of7767b54. Extracted one shared neutral Meta budget parser; existing
qualified adapter delegates without changed serialized state. Added fixed-origin
GET-only collector with private original-session vault assembly, full owner topology,
explicit read limits and deadlines, no synthetic qualification/financial period.
USD→2 is the initial explicit supported mapping; other currencies fail unsupported,
and existing qualified adapter coverage stays intact. Daily/lifetime modes remain
distinct. Factory owns transport cleanup; private DB sessions close before HTTP and
recheck original authority/current goal/source after every response.

Final78 focused tests passed11.10s (actual SQLite/PostgreSQL vault/session/gen/goal
journeys, native HTTP/error bounds, profile/contract tests and legacy social HTTP
regressions); whole-tree Ruff passed; mypy716 passed; diff-check passed. Earlier
new-fixture failures exposed a goal-digest namespace/commerce-refresh mismatch and
one renamed settings attribute; corrected using actual goal definition/commerce
sync, not guard bypass. Frozen subtype equality was normalized in the shared parser
before target comparison. Prior-parser byte comparison and pinned campaign/adset
state digests verify legacy compatibility. No Full, live provider, remote or factory
activation. See inlet-planning-native-budget-read.md for callable ports and remaining
ordinary API/worker/v2 lifecycle assembly.

### Explicit Initial Preview V2 Contract — 2026-10-07

Added only the new typed v2 document and pure strict version-dispatch parser.
The v2 commitment includes environment/profile and the full unqualified native
observation; exact amount, scope/objective, goal revision, quantum and expiry bind
together. There is no qualified native-state digest. Legacy v1 class/serialization
and its bridge remain unchanged. No v2 persistence or route is enabled yet; root
approved leaving nullable native_state_digest NULL when later v2 persistence lands.
Owned read/export/consumer dispatch and explicit bridge rejection must land before
v2 can be served. Scheduler coordinates its immutable0078 baseline accessor.

Validation:23 new-version/native/legacy contract tests passed0.59s; whole-tree Ruff
passed; mypy718 passed; diff-check passed. No migration, Full, remote or live calls.

### Versioned Baseline Consumer Ports — 2026-10-07

Isolated successor from9a75119. PreviewIntentV2 persists server-resolved objective,
calibration/observation/profile/environment/goal commitment, opaque native option ID
and exact optional mandate ID/revision. It never fabricates TargetChoice. Pure
bind_preview_row and preview_mandate_reference enforce typed intent/document/scalar
bindings; owned read_preview returns the strict v1/v2 union and preserves current
session/source/goal/calibration/expiry/mandate checks. V2 requires the exact installed
profile and nullable qualified native_state_digest staysNULL. Initial export uses
strict version dispatch and the same row binder. Qualified review bridge explicitly
rejects v2 before reading v1 native state. No v2 producer/route is enabled yet.

Unchanged native configuration now has a stable opaque choice ID across acquisition
timestamps; full observation digest still commits those timestamps and expiry.
Changed budget/scope/profile/settings still changes the choice. Final53 focused
binding/version/initial API/lifecycle tests passed,1skipped,44.43s; whole Ruff and
mypy720 passed; diff-check passed. No Full/remote/live. Actual v2 producer/runtime
journey remains next; scheduler owns feedback consumer changes after this freeze.

## Version-aware reported baseline consumer — local checkpoint

Based on frozen 0078 c9b019c and actual merge of producer ports 42c20ba.
The feedback consumer now uses the strict versioned row binder and persisted
mandate reference, preserves the final owned reader recheck, and rejects v2
cross-environment or nonrepresentable currency amounts in both application and
as-of dependency validation. Existing v1 bytes, revision pointers, authority and
privacy behavior remain unchanged. No initial-planning producer/export files
were modified by this consumer package.

Pure version/quantum tests and existing genuine v1 baseline guards are validation
of the consumer boundary only. Actual v2 producer → owned GET → adjusted-preview
acceptance remains pending the producer fixture; no hand-built document test is
claimed as that journey. Runtime defaults and financial gates remain unchanged.
No remote action, Full suite or live provider call was made.

Checkpoint checks: `pytest -ra tests/test_reported_feedback_versions.py
 tests/test_initial_preview_binding.py tests/test_reported_feedback_preview_guards.py`
passed **20 tests** on SQLite/PostgreSQL (`/tmp/inlet-feedback-v2-final.log`).
Whole Ruff and mypy **723 files** passed; `git diff --check` passed.
### Actual Configured Planning/Reporting Assembly — 2026-10-07

Successor of42c20ba. Added explicit profile settings and sanitized readiness check,
pinned loader/actual-engine bundle, ordinary initial/reporting API getters and Meta
worker construction. No installed profile remains unavailable; no global principal
or implicit background engine. Added actual owned native-option discovery and v2
producer with separate consent/cap/quantum checks. Public native selection is only
an opaque option ID; full unqualified observation is committed, qualified state
column staysNULL, v1 serialization/optimizer hashes remain intact. New native goal
commitment now matches the existing initial-preview goal namespace and strict row
binding. Original identity is captured before releasing DB transactions for HTTP.

Actual run_meta_tick previously omitted due fixed jobs on fresh rolling coverage.
Installed-profile selection now also considers bounded exact owned source/account/
integration/generation/environment/window-policy obligations, preserving due time,
expiry, connection backoff and existing page authority/lease checks. No new queue
or retry authorization. The actual entrypoint fixture proves four fixed observations
while preserving the original rolling completion timestamp.

Validation: broad targeted run133passed1skipped with one outdated expected readiness
checklist failure (140.78s); corrected that assertion to include the genuinely added
profile check and added partial-profile rejection. Deployment9passed1.48s. Final
actual configured producer/entrypoint/authority-negative/export/bridge+deployment
run19passed45.77s, both SQLite/PostgreSQL. Whole Ruff passed; mypy725 passed;
diff-check passed. The initial typo in the broad test filename collected no tests,
then the actual documented run above executed. No Full or remote/provider live IO.

Reusable tests/planning_runtime_fixture.py:configured_journey installs explicit
fixture profile, uses ordinary API runtime getters, actual run_meta_tick, real report
captures/calibration/commerce refresh and encrypted-vault GETs to produce USD45→46.
Only DB/identity harness, low-level HTTP and clock seams are substituted; no runtime
getter override or fabricated native qualification. Session/generation/profile/
expiry changes deny reads; actual strict export excludes original session digest;
v2 qualified bridge returns explicit409. Consumer930feaca+0078 integration and its
actual adjusted-preview/browser journey remain dependent work, not claimed here.
See inlet-planning-runtime-assembly.md for callable ports and remaining scope.

## Configured v2 reported-preview acceptance — local follow-up

Actual merge 8944f06 integrates producer c340bbf with consumer 930feac and immutable
revision package c9b019c. The new API tests use the producer's configured_journey:
actual file profile, normal runtime getters, Meta worker four fixed observations,
owned captures/calibration, commerce refresh and vault-backed GET-only native
catalog. No v2 row fabrication or runtime-getter override bridges the journey.
The explicit fixture policy changes the genuine 46.00 baseline to 45.75; it is
not a production policy or spending qualification.

Eight SQLite/PostgreSQL API cases pass, including same-ID exact replay, current
read, strict export, no additional native requests, and denial after original
session revocation, source generation change, expiry or baseline erasure.
Two actual TLS Chromium cases pass using the actual API-created original session
and customer page: selected comparison/baseline produces the changed preview;
late actual responses cannot restore state after workspace change or real session
rotation. Existing no-handoff/no-spending messaging is preserved. These tests
extend the real producer fixture; the browser does not redo account onboarding.

Evidence: /tmp/inlet-feedback-configured-v2.log (8 passed),
/tmp/inlet-feedback-configured-browser.log (2 passed). Whole Ruff and mypy730
passed. No live call, remote operation, schema change or Full run occurred.
Existing v1/version/binder/guard/TLS browser regression invocation also passed
22 tests (/tmp/inlet-feedback-v2-compatibility.log). `git diff --check` passed.

## First Customer Budget UI — Consumer Checkpoint

The initial-planning page now shows the selected native scope, confirmed goal
budget/period/time zone/named aggressiveness, and an editable nonnegative USD
limit that cannot exceed the goal. A separate exact review displays server-derived
money caps and affected scope; an explicit checkbox and consent request bind the
returned revision/policy/preparation digests. Returned IDs are selected internally,
never requested as customer input. Consent remains conditional, with no exposure
qualification, new-campaign approval, activation or execution claim.

Goal/report/selection/amount/session changes clear the review; target/amount changes
also clear the selected active plan. No mutation is automatically retried. A missing
budget-review policy is explained as unavailable. Numeric server operating choices
are not added to the form. Named aggression changes require goal reconfirmation.

Existing actual initial-planning TLS browser regressions: four passed on both DBs
(/tmp/inlet-budget-ui-regression-final.log). Node syntax checks passed for consumer
and prepared new browser driver. Whole mypy733 passed. Whole Ruff encountered an
inherited bcf4ed0 B010 in test_budget_mandate_contracts.py; producer owner notified,
no unrelated edit made. Diff check passed. The new browser driver is prepared but
not yet executed: actual no-preexisting-mandate backend fixture is awaiting freeze.
This checkpoint is not acceptance of the new first-customer consent journey.
### 2026-10-07 — Conditional first-customer budget mandate backend

- Isolated `codex/inlet-customer-budget-contract`, from02377c8; typed policy/ports
  frozenbcf4ed0. Added ordinary read-runtime-backed prepare/consent endpoints and
  separately pinned explicit server operating policy. Customers submit budget,
  named aggression and native scope; technical policy fields are rejected.
- Added0079down0078 minimal protected immutable provenance with owned revision FK,
  policy-binding trigger, strict export and nonempty downgrade refusal. Existing
  mandate revisions/consent/ledger reused. `revise(commit=False)` preserves default
  old commit behavior and permits atomic draft+provenance+final session fencing.
- Actual no-prior-production-authority fixture uses real imported/captured history,
  normal goal edit/preview/confirm, configured native GET HTTP mock and normal API
  prepare/consent/retry/v2 preview. No write-runtime overrides or exposure proof.
- Checks:18 API/migration cases passed on SQLite/PostgreSQL (actual Alembic roundtrip
  on PostgreSQL),27 contract/model-registry/existing mandate/lifecycle cases passed;
  whole Ruff passed, mypy740 files passed, diff check passed. Logs:
  `/tmp/inlet-budget-final-focused.log`, `/tmp/inlet-budget-compatibility.log`.
  Concurrent DB session revocation inside provider HTTP denies consent; final guard
  failure after sidecar insertion leaves neither draft nor provenance.
- No Full, remote actions, live calls, merge or deployment. Dependent actual TLS UI
  journey belongs scheduler_wiring and is not claimed by this backend checkpoint.
  Required real operating-policy values, coherent process policy deployment and
  independent provider execution qualification remain explicit prerequisites.

### 2026-10-07 — Configured Google Creation And Separate Activation

- Local successor to frozen `9209c14d`: ordinary request-scoped API assembly now
  uses the actual DB engine, original principal/session, owned vault credentials,
  actual OAuth/catalog/qualification/create/readback/activation HTTP adapters and
  existing financial readers. Missing manifest or server evidence source denies;
  no shipped live source, proof JSON admission or runtime getter test override.
- Shipped real transport refuses contract-test manifests before construction.
  Explicit MockHTTP injection is required for synthetic evidence tests; a live
  manifest with scenario evidence and direct social API bodies deny before IO.
  Ephemeral contexts/transports close on successful and denied requests.
- Genuine configured API builds production mandate consent, exact creation review,
  paused graph and separate activation approval without seeded execution reviews,
  attempts, receipts or holds. Unknown mutation retains one attempt/hold and never
  replays. This is offline contract evidence, not live provider/financial evidence.
- Reproduced PostgreSQL self-lock in activation preparation after identical receipt
  reconciliation: backend7331 waited on7325 (receipt lookup transaction). Stopped
  that exact test and canceled its waiting query; interrupted run is not a pass.
  Narrow explicit commit before external qualification releases the completed
  read phase. Final authority/graph checks remain; regression revokes the original
  session during qualification and verifies denial, no duplicate receipt/write,
  and one retained hold.
- Checks: combined API/contracts/legacy execution/activation suite 46 passed
  (`/tmp/inlet-google-runtime-final-checks.log`); final transport-guard successor
  contracts/configured API suite 16 passed, both DBs
  (`/tmp/inlet-google-runtime-transport-checks.log`). Whole Ruff and mypy749 passed;
  diff check passed. No Full, remote, live calls, merge or deployment.
- Next: actual TLS customer journey through this configured assembly. Real approved
  evidence-source implementation and policy qualification remain prerequisites;
  this package does not enable live writes or complete remaining provider/worker
  assembly. Process-pinned manifest rollout assumptions are documented.

## Configured Google Execution — Actual TLS Browser Acceptance

On frozen backend6586d46, the new dedicated browser harness uses
configured_customer's ordinary request-scoped runtime, pinned manifest, actual
owned OAuth/vault/catalog/qualification/creation/activation adapters, and explicit
server-side contract-scenario evidence with MockHTTP. No runtime getter override
or seeded execution review, attempt, reservation or receipt bridges the journey.
Approved creative is an existing prerequisite, not claimed as generated here.

The actual execution page obtains the catalog, records separate spending consent,
prepares and explicitly approves exact paused creation, advances the resource graph,
then prepares and separately approves activation. It reads the resulting receipt,
recovers the saved owned run and revokes local consent. The single parent reservation
remains held. Contract-test state is not live advertising or causal-effect evidence.

Additional actual browser scenarios cover timeout/unknown creation: one original
attempt/write and one held reservation; Continue is disabled and Check Original
Request reconciles without replay. Revoking the original session during the actual
post-release qualification callback blocks activation review and makes no activation
write, preserving the existing hold.

Final SQLite/PostgreSQL six-case TLS suite:6passed34.51s
(/tmp/inlet-google-configured-browser-v3.log). Whole Ruff, Node syntax, mypy750,
and diff checks passed. Earlier harness failures are retained: first omitted the
existing campaign-draft listing router; second expected legacy injected-runtime
social-blocker wording. Fixed only harness route mounting/assertion specificity;
no application changes or weakened gates. No Full/remote/live/artifacts.

### 2026-10-07 — Meta Runtime Interface Freeze

- Additive successor to Google TLS4ff8d74 and approved design356dfa7: frozen Meta
  manifest, exact configuration bundle, server evidence and owned-context ports.
  Google contracts/configuration and all native Meta qualification blockers unchanged.
- Bounded manifest16KiB/bundle64KiB loader rejects duplicate keys and missing,
  mismatched or foreign rules. Immutable canonical bundle owns nested policy data;
  accessors return defensive copies. USD exponent2/no-DSA only, explicit wording.
- Real transport factory refuses contract-test before constructing HTTPTransport;
  no sockets/source factory/registry/API composition installed by this checkpoint.
- Final focused contracts11 passed (including existing Google cases); whole Ruff,
  mypy754 and diff check passed. No DB, Full, remote or live operations. Next is
  request-owned contexts and lazy typed provider composition after sharing this
  freeze; actual configured API/TLS journey remains outstanding.

### 2026-10-07 — Configured Meta Image And Lazy Provider Composition

- Successor to bd35908 wires request-owned Meta vault/media contexts, ordinary
  social-review dependency and typed lazy Google/Meta execution composition.
  `configured_execution(db, principal, provider, settings, media_store_factory,
  social_only=False)` owns resources until request exit. Actual original session,
  DB bind, current source/generation and exact declaration/profile guards retained.
- Same-environment Google+Meta capability discovery builds no evidence source or
  transport. Typed Meta work never builds Google; unsupported TikTok catalog/plans
  and inert HTTP slot deny before factories/IO. Missing Meta leaves Google working.
  Native Meta four qualification blockers remain; no registered live source or
  blocker-filtering code. Real transport rejects contract-test before construction.
- Actual configured Meta fixture seeds no execution review/attempt/receipt/hold and
  overrides no runtime getters. Ordinary API performs mandate consent, actual named
  HTTP catalog, explicit declaration review/confirmation, exact creation approval,
  image/paused graph and separate activation/readback. Unknown create/activate retain
  original hold and do not replay. Session revocation or generation change during
  catalog HTTP, expired credentials and absent source deny without writes.
- Checks:42 combined Meta/Google/legacy API cases passed; final49 Meta contracts/API,
  legacy social API and all6 configured Google TLS regression cases passed on both
  DBs. Logs `/tmp/inlet-meta-composition-focused.log` and
  `/tmp/inlet-meta-composition-final.log`. Whole Ruff/mypy758/diff check passed.
  Exploratory old Google real-transport regression initially expected eager denial
  during local mandate preparation; lazy behavior requires no unused transport.
  It now exercises actual configuration discovery and preserves the forbidden-real-
  constructor/no-IO assertion. No production/hash/financial check was relaxed.
- Callable composition and `tests/meta_runtime_fixture.py:configured_meta_customer`
  are frozen for dependent actual Meta TLS acceptance. That new Meta browser journey
  remains outstanding; Google browser compatibility is verified. No Full, remote,
  live calls, merge or deployment, and no claims of live qualification.

### Configured Meta customer TLS acceptance (2026-10-07)

- Isolated successor of `55e6a35387593483a34e86ebbd002d27473d2802` adds
  dedicated browser tests only. The actual social configuration page performs
  named HTTP catalog discovery, explicit no-special-category declaration, private
  image decoding, saved exact review and separate confirmation. The same original
  session then uses the actual execution page for mandate consent, creation review,
  explicit approval, paused resource graph, separate activation review/approval,
  status recovery and owned receipt readback.
- Ordinary configured runtime and vault/HTTP adapters are used with lower-level
  MockTransport. No runtime getter overrides or seeded execution reviews, attempts,
  receipts or reservations. Explicit server contract-scenario evidence remains
  test-only; this does not establish live provider qualification.
- Unknown creation and activation responses are reconciled through the actual
  Check Original Request control without replay. Original session revocation,
  source-generation change, missing private media and withdrawn declaration
  confirmation block activation while retaining the held reservation.
- Adverse harness evidence: initial SQLite run correctly rejected previewing the
  October 5 fixture draft using the route's real October 7 clock (409). The harness
  now supplies the existing fixture clock to that route as well; no product
  freshness, approval or financial gate was changed. Logs:
  `/tmp/inlet-meta-configured-browser.log` and
  `/tmp/inlet-meta-configured-browser-v2.log`.
- Preliminary cohorts: eight complete/unknown/session cases passed; six additional
  source/media/declaration cases passed (38.94 seconds), all across SQLite and PG.
  Final combined result recorded below. Whole Ruff, mypy (449 source files), both
  JavaScript syntax checks and diff check passed. No new Full, remote activity,
  screenshots, live requests, deployment or production code changes.
- Final combined focused run: **14 passed, zero skips**, 91.27 seconds on SQLite
  and PostgreSQL (`/tmp/inlet-meta-configured-browser-final.log`).

## First Customer Budget UI — Actual Backend Acceptance

Actual merge 295e4c7 combines UI1671552 with backend4fadeda. The TLS Chromium
journey begins with zero production mandates, consents, attempts and reservations,
uses real customer capture/calibration and configured native GET readers, then
selects a scope, reviews derived caps, explicitly consents, and creates a native
v2 preview. No manually supplied mandate IDs, seeded authority or runtime getter
overrides bridge the customer flow. One consent is persisted; attempts and
reservations remain zero and all native requests remain GET. Amount edits clear
the active plan; delayed actual prepare responses cannot restore a changed
workspace. Existing legacy UI behavior remains covered.

Adverse result retained: /tmp/inlet-first-budget-browser-final.log had 2 failed
missing-policy cases and 6 passed. Backend correctly returned409 with its precise
unavailable code; UI mapped it to generic changed-context wording. Added a fixed
safe customer message for that known code. The repaired run passed8 tests in
/tmp/inlet-first-budget-browser-repaired.log. Optional screenshot work was canceled
by the owner and all dedicated uncommitted screenshot helper/endpoints were removed
from this package; no walkthrough or deployment is claimed.

Final exact package checks after artifact removal: 8 passed on SQLite/PostgreSQL
(`/tmp/inlet-first-budget-browser-no-artifacts.log`,46.88s), whole Ruff clean,
mypy741 clean, both Node syntax checks and `git diff --check` passed. The producer's
inherited Ruff B010 is repaired by its frozen backend commit. No Full, remote
operation, live provider request or change to qualification checkout/database.

## Owned Goal Sales Progress Backend — Local Checkpoint

The additive revision-scoped GET returns only complete closed store-local day
prefix sales from the existing unchanged merchandise measurement reader. The goal's
monthly/cumulative target remains unchanged; net refunds may produce signed negative
progress and genuine zero remains distinct from unavailable null. Current recorded
confirmation suffices for informational progress; there is no re-confirmation,
achievement, causal attribution or spending authority. No snapshots or other rows
are created by the read. Exact midnight/date/time-zone bindings reject ambiguous
boundaries while preserving23/25-hour DST days.

Original session and current read-role membership are fenced workspace-first,
with fresh database/application wall clocks after waits. Privacy, disconnected,
in-progress, missing-history and stale sources deny the amount. Real PostgreSQL
workspace-lock wait plus session revocation denies the response. Existing goal API
mutation behavior is unchanged.

Actual normalized September sale/October processing-date refund and completed
CommerceSyncService import underpin the reusable tests/goal_progress_fixture.py
ready(engine,configuration,replicas) helper. It returns alice,provider,wid,gid,
revision,store_id,original principal,now. Optional explicit fixture clock spans the
confirmed target end without approving a goal after its deadline.

Checks:30passed1expected SQLite row-lock skip (/tmp/inlet-goal-progress-delivery.log),
then13 strict contract/DST tests passed after final UTC/date validation additions.
Whole Ruff and mypy746 pass; diff check passed. Adverse fixture attempts were kept:
future updatedAt relative to import cutoff correctly rejected; trying to confirm
an already-ended goal correctly rejected. Fixtures were corrected, not product
guards. UI/TLS integration is the separate dependent package. No Full/remote/live.

## Goal API / Progress PostgreSQL Lock Order Repair

Independent review identified an actual cycle: the existing goal GET locked Goal
before its serialize→assessment→baseline→measurement path acquired Workspace,
while new progress acquired Workspace then Goal. A controlled actual PostgreSQL
HTTP interleave reproduced DeadlockDetected (backend8832↔8835) on57febe8 before
product edits. `/tmp/inlet-goal-lock-baseline.log`:1failed1SQLite skip5.97s.
The regression has a3-second database lock timeout and bounded workers/cleanup.

Customer goal access now uses the existing canonical original-principal/provider
workspace→user→session→membership guard before goal or measurement locks. Existing
read roles remain owner/admin/analyst/viewer; edit remains owner/admin/analyst;
confirm remains owner/admin. MutationPrincipal/CSRF requirements remain unchanged.
Create/edit/confirm reacquire the guard before post-commit serialization. No Goal
locks were removed and no measurement, privacy, retention or financial semantics
were relaxed. The new regression explicitly covers all four role projections.

The exact controlled interleave passes after repair (1passed1SQLite skip2.99s,
/tmp/inlet-goal-lock-repaired.log). The reproduction is an actual two-request lock
cycle, not a query-order-only assertion. No Full/remote/live/root-checkout edits.

Final focused invocation:85passed2expected SQLite concurrency skips,3existing
Alembic configuration warnings66.71s (/tmp/inlet-goal-lock-regressions.log).
Includes controlled lock regression, exact roles, old goal services/migration,
progress source/contract cases, actual goal-progress TLS and existing customer
API/browser journey. Whole Ruff and mypy749 passed; diff check passed.

### Goal interpretation original-session delivery fence (2026-10-07)

- Isolated child of `8a9cad1991c6848bd23a2aa5e9a5255b26f22b72`; fixes a
  pre-existing interpretation gap, not a regression introduced by goal lock ordering.
  The route authorized before `reserve()` committed, then returned adapter output
  without rechecking original authority or goal revision after unlocked adapter work.
- Controlled offline adapters reproduced eight actual API failures across SQLite
  and PostgreSQL: revocation, expiry, owner-to-viewer change and goal revision drift
  all returned HTTP 200. Corrected baseline: eight failed in 8.23 seconds,
  `/tmp/inlet-goal-interpretation-baseline-corrected.log`. The first exploratory
  baseline used an incorrect test session attribute for revoke/expiry; its evidence
  is superseded by the corrected run, not counted as those reproductions.
- `interpreter.run` now accepts an optional trusted `authorize_result` callback.
  The customer route binds the actual original principal, canonical workspace-first
  guard, refreshed owned goal and expected revision. It rechecks after adapter IO
  before the usage update and again after the accounting commit before delivery.
  Existing usage quotas, durable reservation and idempotency remain unchanged.
- Guard denial suppresses output while retaining the actual completed/invalid/
  uncertain call accounting. No proposal/result text is persisted. Tests verify
  completed zero-cost usage remains counted and a newly authorized session cannot
  replay the same call. A controlled post-accounting-commit revocation also denies
  response delivery on both databases.
- Exact prior source context is compared (store revision/status/basis, connection
  identity/status, integration status and workspace privacy revision). This adds no
  source freshness or baseline qualification requirement: the offline adapter still
  receives only milestone text, and incomplete goals remain supported.
- Checks: initial fixed interpreter/old-goal cohort **48 passed**; expanded
  interpreter, old-goal, progress and controlled PG lock-order cohort **82 passed,
  2 expected SQLite concurrency skips**, 3 existing Alembic warnings, 61.44 seconds
  (`/tmp/inlet-goal-interpretation-final.log`). Final strengthened accounting/replay
  cohort **14 passed**, 15.46 seconds (`/tmp/inlet-goal-interpretation-accounting.log`).
  Whole Ruff, mypy (441 source files), and diff checks pass. No Full, remote action,
  external model/provider call, live spending, schema change or deployment.

### 2026-10-07 — Optimization Assembly Contract And Origin Proposal

- Isolated child of cd5c2b8/Meta55: additive typed manifest, true catalog-admission,
  existing qualification/exposure/replacement/settlement ports and owned-context
  protocols; no installed runtime or native-to-qualified cast. Separate required
  operating policy and simple customer amount/aggression/opaque-selection intent
  preserve all existing v1 hashes. Action count aligns with existing1000 maximum.
- Proposed minimal dedicated immutable optimization mandate sidecar plus parent
  revision origin discriminator/digest and deferred owned FK. Missing origin cannot
  silently downgrade to legacy consent; configured forward gates must require new
  origin while preserving historical attempts/holds. Exact export/retention and
  nonempty downgrade refusal are documented; no migration/ORM edits yet.
- Pure contract checks16 passed (new optimization plus Google/Meta/budget contracts),
  whole Ruff/mypy761/diffcheck passed. No DB, Full, remote or live actions. Next is
  root review of origin schema/anti-bypass gates before inventory/runtime/consumer
  implementation. Owner operating/evidence inputs remain explicit, never defaults.

### 2026-10-07 — Optimization Origin0080 Schema Freeze

- Standalone child of7796d09: strict minimal retained preparation document/model,
  canonical protected lifecycle/export classification and migration0080 down0079.
  Parent financial policy JSON/v1 digests remain unchanged. New parent discriminator
  and nullable deferred digest FK bind a globally unique exact owned sidecar;
  parent digest uniqueness prevents simultaneous borrowing before proof insertion.
  Exact reverse scope/policy guards and marked-revision immutability preserve origin.
  Legacy unrelated updates keep existing behavior; legacy-to-marked update denies.
- Actual0080 uses only additive parent columns/index/triggers, never a populated
  financial-table rebuild or disabled integrity. BothDB populated downgrade/reupgrade
  preserves existing real revision bytes and RESTRICT consent. Nonempty downgrade
  refuses. SQLite downgrade initially exposed a sidecar-trigger ordering defect;
  the final migration drops that dependent trigger before removing its column.
- Existing SQLite connections are not universally FK-enabled. Marked INSERT now
  explicitly denies when pragma_foreign_keys is off; future configured service must
  preflight this too. No global engine/fixture behavior changed. SQLite's empty ORM
  test fixture is normalized to pre0080 structure before actual migration execution;
  PostgreSQL starts from real Alembic heads. The populated test never rebuilds tables.
- Final focused suite:31 passed,1 expected SQLite-specific test skipped on PostgreSQL
  in24.09s. Includes actual migration/atomic rollback/missing proof/wrong workspace
  and policy/both insertion orders/duplicate digest/update/delete/FK-off denial,
  strict export and model registry, existing execution mandate/lifecycle regressions.
  Whole Ruff and mypy765 passed; git diffcheck passed. Evidence:
  /tmp/inlet-origin-final.log. No Full, remote, live calls or candidate changes.
- This is storage provenance, not configured execution acceptance. Runtime preparation,
  original-session final fence, generic consent/forward origin dispatch and current
  policy/qualification/exposure checks remain the next package. Structural fixture
  documents are explicitly not real admitted financial proof. No live source enabled.

### 2026-10-07 — Configured Google/Meta Optimization Backend

- Isolated actual merge59a1235+catalog2cc, API contracts2356077; inherited substrate382
  as c120344 and metadata repairs302/68 as cced47a/d58d0c9. Added request-owned lazy
  configured runtime, meaningful customer preparation/consent endpoints, atomic marked
  revision+sidecar insertion and generic/forward origin guards. Actual typed source
  admission precedes factories/credentials/HTTP; real transport denies contract_test.
  Default registry remains empty. No legacy v1 financial/state hash changes.
- Customers confirm budget/aggression/scope; all technical limits come from pinned
  required server policy. New consent refreshes native inventory and separately
  admitted qualification. Preserves original inventory audit digest while validating
  fresh semantic scope/state/source identity/revision/evidence; acquisition timestamps
  alone do not force new preparation. Review discovery uses real original mandate
  period/binding. Policy/source/goal/session and financial/current-state gates retain
  their original boundaries; no overall-cap increase from aggression or edit.
- Final focused79 passed,1 expected SQLite-only assertion skipped on PostgreSQL,
 150.38s. Includes28 genuine configured API cases: Google/Meta budget/pause/unknown
  journeys, +15s before consent/+10s before review, actual vault/native MockHTTP, no
  seeded provider mandate/review/attempt/hold or runtime getter overrides; meaningful
  native/qualification-revision drift denies. Unknown recovery retains one write,
  attempt and held reservation. Independent session/source/generation changes during
  HTTP deny; post-both-insert failure rolls back all financial/provenance records.
  Generic/technical consent bypasses, cap increase and scenario real-transport deny.
  Actual strict origin export, metadata/migration and legacy45 API/mandate checks pass.
- Whole Ruff/mypy781, targeted format and git diffcheck pass. Evidence:
  /tmp/inlet-opt-final-focused.log. No Full, remote, live calls or root candidate edits.
  Optional replacement delegates only to admitted existing source ports; no new
  settlement endpoint or empirical live proof. UI/TLS followup separately owns the
  actual customer page; this checkpoint is backend offline acceptance only.

### 2026-10-07 — Exact Local Financial Budget Boundaries

- Isolated child of c418bc4. Reproduced old implicit normalization: Havana
  2026-11-01 midnight maps to either04:00 or05:00UTC by fold; Apia
  2011-12-30 midnight previously maps to10:00UTC and roundtrips to December31.
  Shared financial budget-period helper now rejects either ambiguous or missing
  boundary with sanitized409 financial_budget_period_unavailable. Both configured
  optimization and initial-budget preparation use it. Explicit dates/timezone remain
  authoritative; valid New York23/25-hour DST periods and ordinaryUTC are unchanged.
- Final focused55 tests passed (terminal exit0), covering seven pure boundary cases,
  four actual confirmed-goal optimization API cases on SQLite/PostgreSQL, and existing
  initial-budget/configured optimization API positives and authority guards. Invalid
  API requests create zero mandates/revisions/ledgers/provenance and open no provider
  factory or HTTP. Invalid initial-budget API behavior was not separately exercised;
  it uses the same tested converter, with its existing actual API regressions passing.
- Whole Ruff and mypy784, five-file format check and git diffcheck pass. Evidence:
  /tmp/inlet-budget-period-final.log. No goal/schema/legacy v1 hash, immutable ledger,
  commerce measurement or runtime qualification changes. No Full, remote or live calls.
### TikTok configured runtime contracts and pinned loader (2026-10-07)

- Isolated child of approved design `42760f60b72ac3b0bc417cc449e9057484ba78df`.
  New TikTok-only manifest, evidence/source, reserved owned-context protocols,
  canonical immutable configuration bundle and strict pinned loader are documented
  in [the callable interface record](inlet-tiktok-runtime-contracts.md).
- Decoded catalog callback is contract-test only; live identity admission always
  denies while native identity/pixel catalog decoding remains unverified. Empty
  default registry and existing mandatory catalog blockers remain unchanged. Real
  transport refuses scenario manifests before construction, uses zero retries and
  no environment proxies. No runtime assembly or source registration is installed.
- Bundle pins exact profile/requirements pairs, explicit video-cover review and
  nonblank wording; defensive typed copies preserve immutable canonical bytes.
  Duplicate keys, partial inputs, unknown fields, oversized documents, version or
  pin mismatches deny with sanitized errors. Existing social schemas and hashes,
  Google/Meta code and settings are untouched. Credential expiry remains unknown
  unless an eventual owned reader verifies it; no lifetime is invented here.
- Checks: initial 34 pure contract/loader/catalog tests passed; final focused
  TikTok/Meta/Google contracts, catalog and social producer compatibility cohort
  **70 passed** in 27.89 seconds, including SQLite/PG producer cases. Log:
  `/tmp/inlet-tiktok-runtime-contracts-final.log`. Whole Ruff, mypy (452 source
  files) and diff check pass. No migration, Full, remote action, live calls,
  production registration or API/TLS qualification. Runtime implementation waits
  for review of these frozen interfaces.

### TikTok owned configured runtime and ordinary API journeys (2026-10-07)

- Isolated successor of `305ce1a96005d23c6e5fb316eac84db0bf2c477f` adds lazy
  configured TikTok composition, private owned source-vault/media readers, pinned
  settings and ordinary customer API assembly. Original session, exact account
  generation, manifest, paid-work and explicit credential expiry are rechecked.
  Missing, expired or timezone-naive credential expiry denies; no TTL is inferred.
- Actual fixture starts with zero execution reviews, attempts, reservations and
  receipts. Ordinary APIs exercise named decoded test catalog, real video/cover
  validation and confirmation, separate mandate consent, exact creation approval,
  paused graph, separate activation approval, actual HTTP adapter readback and
  original-attempt reconciliation through injected MockTransport. No runtime getter
  is overridden. Google/Meta composition and existing serialized contracts remain
  compatible. Fixture and callable details: [runtime record](inlet-tiktok-configured-runtime.md).
- Live source admission remains denied; default evidence registry stays empty.
  Decoded catalog is explicitly contract-test data, not native catalog HTTP.
  Native catalog decoding and genuine financial qualification are still missing.
  No live execution, schema change, migration, Full or remote action occurred.
- Adverse evidence: first fixture run failed because its cover binding used the
  wrong mock-server key; the actual request remained unknown with its hold intact
  (`/tmp/inlet-tiktok-configured-api.log`). Corrected fixture: six passed. Later
  removal of the exact private cover reproduced uncaught FileNotFoundError on
  both databases (two failed, six passed in
  `/tmp/inlet-tiktok-extra-boundaries.log`). Approved narrow repair normalizes
  OSError at the existing selection boundary to sanitized 409, with no existence
  fallback, activation or reservation release. Both repaired cases pass.
- Final focused TikTok API/contracts: **50 passed** in 357.67 seconds
  (`/tmp/inlet-tiktok-configured-final.log`). Additional paid-work denial:
  **2 passed** (`/tmp/inlet-tiktok-billing-denial.log`). Strengthened original
  attempt reconciliation and unknown-expiry checks: **6 passed** in 110.30 seconds
  (`/tmp/inlet-tiktok-original-reconcile.log`); no replay and original holds remain.
- Google/Meta ordinary API and actual TLS compatibility: **54 passed** in 232.12
  seconds, including six Google and fourteen Meta browser cases
  (`/tmp/inlet-tiktok-provider-compatibility.log`). Whole Ruff and mypy over app
  and tests (**762 source files**) pass; diff check passes. These are mocked
  provider/offline results, not live qualification. Next package: actual TikTok
  TLS customer journey using the frozen ordinary configured fixture.

### Explicit source-vault settings follow-up (2026-10-07)

- `SourceVault(configuration: Settings = settings)` preserves existing default
  callers and ciphertext bytes while owned TikTok contexts pass their explicit
  configuration. Non-global key tests prove missing/wrong global secrets cannot
  replace the explicit key; foreign scope still denies.
- Focused vault and TikTok complete/credential-expiry cases: **8 passed**, 26
  deselected, SQLite/PG, 103.22 seconds (`/tmp/inlet-tiktok-vault-followup.log`).
  Ruff, targeted mypy (three files) and diff check pass. No schema or gate change.

### Actual configured TikTok TLS acceptance (2026-10-07)

- Child of vault fix `7a352020449b1daf0d2225e68f9c4dbafab20293` adds only browser
  tests/drivers and documentation. Actual local HTTPS application pages, original
  API session, configured runtime, video/cover decoding and exact confirmation
  lead through consent, paused creation, separate activation and owned readback.
  Provider HTTP uses MockTransport; decoded catalog remains explicitly contract
  test with native discovery unavailable. No runtime getter overrides or seeded
  execution review/attempt/receipt/reservation, and no demo artifacts.
- Complete flow **2 passed** across SQLite/PG in 92.19 seconds
  (`/tmp/inlet-tiktok-browser-first.log`). Boundary cohort initially **12 passed,
  2 failed** in 410.71 seconds (`/tmp/inlet-tiktok-browser-boundaries.log`): only
  the profile scenarios failed because the new harness changed an unused fixture
  Settings object instead of the actual server settings. No app guard was changed.
  Corrected profile rerun **2 passed** in 73.75 seconds
  (`/tmp/inlet-tiktok-browser-profile.log`). All sixteen scenarios therefore have
  passing evidence; the failed invocation is not reported as a clean suite run.
- Unknown creation/activation explicitly reconcile the original request without
  replay; session revocation, source generation, missing cover, withdrawn exact
  confirmation and changed profile deny activation. The original hold remains
  held in every scenario. Complete flow also checks receipt interpretation,
  consent revocation and logout clearing.
- Whole Ruff, mypy app/tests (**764 source files**), both JavaScript syntax checks
  and diff check pass. No production code changes in this browser package, no
  Full, remote operations, native live calls, deployment or live qualification.

### 2026-10-07 — Standalone Planning Contract Import Repair

- Reproduced fresh-process ImportError on initial_planning.contracts: TargetChoice
  pulled customer_runtime solely for utc_now, then activation/coordinator/mandates
  reentered partially initialized Frozen through optimization-origin contracts.
- Extracted identical UTC clock into import-neutral publication.clock; legacy runtime
  reexports the same callable and both dataclass defaults retain its identity. No
  schema/default behavior changes. Three fresh-import/default identity regressions
  passed within27 focused tests; whole mypy814 passed. No application-bootstrap
  workaround remains in tests. No DB, Full, remote or live calls.

### 2026-10-07 — Pure V2 Preview Execution Handoff Contracts

- Frozen new strict customer intent/prepared response/hash-only proof and native
  semantic-match projection; docs/design/configured-v2-review-contract-freeze.md
  records callable signatures and actual field mapping. Separate consent requires
  distinct mandate/consent identities on the same ledger/environment. No native
  observation is relabeled as qualified state and existing preview/v1 bytes unchanged.
- Actual shared Meta codec commits objective/buying type in unchanged-settings digest;
  status is explicitly compared (not falsely claimed in that digest). Campaign-only
  parent status equality follows actual same-row parsing. Native financial period and
  qualification are absent, so future owned bridge must independently validate both
  policy/consent/origin/period/cap bindings and current source/session/financial gates.
- Final45 tests passed,8 owned-DB cases deliberately deselected,3.79s; actual GET-only
  MockHTTP both readers, changed-semantic matrix, strict proof/client inputs, legacy
  state digest pins and fresh import regressions. Whole Ruff/mypy814, format and
  diffcheck pass. Evidence /tmp/inlet-v2-review-contracts.log. No DB, routes, runtime
  registration, UI, migration, Full, remote or live calls. This freeze grants no
  financial authority and does not implement the future durable handoff service.

### 2026-10-07 — 0081 V2 Execution Proof Storage

- Added immutable owned hash-only proof table, composite CASCADE FK and unique link
  index without rebuilding populated SQLite parents. Portable insert guards bind
  existing v2 preview/link/protected review commitments. ORM preinsert additionally
  validates canonical proof/preview/native/review/plan hashes, full execution mandate,
  separately bound planning references and reconstructed handoff intent. Missing or
  NULL-retracted pointers deny insertion; retained protected review origin survives.
- V2 link intent now explicitly means new handoff intent and mandate digest execution
  policy; unchanged v1 interpretation is separated by immutable preview schema. No
  additional version marker is needed, but future v2 guard must reject missing proof
  without falling through. Strict16KiB hash-only historical export and protected
  lifecycle registry added, no session secret; no claim export grants current authority.
- Combined48 tests passed32.87s on SQLite/PostgreSQL: actual0081 populated prior-link
  downgrade/upgrade, metadata/migration ownership/immutability/cascade/retraction,
  validly rehashed contradictory parent insert denial, malformed export and existing
  v1 lifecycle/contracts. Final storage11 passed15.34s after qualified-state hash
  crosscheck plus migration graph/frozenSQL parity (one existing Alembic config
  deprecation warning). Whole Ruff/mypy818, format/diffcheck pass. Logs:
  /tmp/inlet-v2-proof-final.log and /tmp/inlet-v2-proof-final-storage.log.
- Historical0076 fixture now removes/restores the real0081 child around its direct
  parent migration roundtrip. Positive v2 storage parents are internally canonical
  typed structural fixtures, not a customer handoff or claimed financial admission.
  No route/runtime/UI, live calls, Full or remote actions. Remaining actual bridge
  must perform original-session/current-source/policy/period/cap/consent validation
  and every forward financial gate; historical reconciliation remains untouched.

### 2026-10-07 — Bind V2 Proof Inner Commitments

- Followup to af14eb8: proof qualification_digest now commits the entire retained
  OptimizationQualification using inlet.initial-preview-execution-qualification.v1,
  not only evidence_digest. semantic_match_digest must equal the existing
  NativeReviewMatchV1 digest recomputed from retained native preview and review state.
  Both canonical checks run before ORM proof insertion; no new eligibility fact or
  authority is inferred. Domains documented in the storage design.
- BothDB storage/migration tests now reject each contradictory inner hash after
  recomputing a valid outer proof hash.35 affected tests passed14.14s (one existing
  Alembic config deprecation warning); whole Ruff/mypy818, format/diffcheck pass.
  Evidence /tmp/inlet-v2-proof-commitments.log. No schema expansion, route/runtime,
  Full, remote or live actions.

### 2026-10-07 — V2 Execution Options/API Interface Freeze

- Frozen immutable bounded options/response and exact callable protocols in
  review_v2_api_contracts; documented GET execution-review-options and POST
  execution-review under the existing owned preview path. Up to50 named separately
  consented matching0080 options carry exact period/caps; availability explicitly
  does not assert financial qualification. Existing three-field intent and prepared
  response unchanged; no raw proofs/amounts/native IDs admitted from customers.
-32 pure/codec contract tests passed2.63s; whole Ruff/mypy820, format/diffcheck pass.
  No routes/runtime/UI/schema/DB, remote, Full or live calls. Concrete guarded service
  and ordinary configured API acceptance remain next; docs/design/v2-execution-review-api-freeze.md
  freezes names, ownership, unavailable semantics and transaction responsibilities.

### 2026-10-07 — Configured V2 Handoff Backend And Fixture

- Implemented bounded named execution options and exact three-field handoff through
  ordinary configured dependencies. Requires separate marked0080 consent under the
  same ledger/goal/period/overall cap; no0079 promotion or native qualification cast.
  Transactional writer stores protected origin/link/0081 proof after fresh original
  authority and financial checks; version guards cover ordinary approval/dispatch.
- Actual configured SQLite/PostgreSQL API cases:10 passed99.30s then8 passed66.02s
  (two overlap;16 distinct). Covers verified mutation, uncertain no-replay and
  historical reconciliation after proof erasure, deletion after committed claim,
  cap/native drift and original-session revocation during provider HTTP.
  Logs /tmp/inlet-v2-handoff-expanded.log and /tmp/inlet-v2-handoff-new-negatives.log.
- Whole Ruff/mypy827 and diffcheck passed. Reusable ready() fixture and limitations
  documented in docs/inlet-v2-configured-handoff.md. Genuine TLS and expanded
  compatibility remain dependent followups. No Full, live or remote actions.

### 2026-10-07 — V2 Handoff Drift And Transaction Followup

- Added ten passing SQLite/PostgreSQL negative cases: current goal revision/source
  generation changed in an independent transaction during real mocked provider IO;
  tampered expected preview digest; same owner with a newly authenticated original
  session; and controlled final guard failure after both link and proof were flushed.
  Every rejected preparation leaves no review/link/proof and emits no provider write.
  The final-guard fault tests rollback, not an alternate authority implementation.
- Exit0 for eight cases in /tmp/inlet-v2-handoff-final-negatives.log and two in
  /tmp/inlet-v2-handoff-session.log. Whole Ruff/mypy827/diffcheck passed.
  Duplicate local legacy compatibility cohort was interrupted when root took that
  combined cohort; it is not pass evidence. No production edits after063243c;
  independent source review of that exact head reported no actionable finding.
  Genuine TLS remains owned by customer_signin. No Full, remote or live actions.
## 2026-10-07 — Standalone TikTok Discovery Parser

- Isolated `codex/inlet-tiktok-native-discovery-parser` from `01d238a1446be85636ab420fc52f6bfd5556b315`.
- Added strict versioned pure identity/pixel request and observation parsers. Unknown,
  absent and null remain distinct; deprecated events retained; duplicate known IDs
  and known ownership contradictions rejected. Pixel/event ID scalar types stay
  explicitly unverified. Every result is page-only, pagination-unverified and grants
  no publication or spending authority.
- Existing social catalog/publication/runtime source and bytes untouched. No provider
  calls, database changes, Full, remote actions or live qualification.
- Focused parser + existing TikTok runtime/social publication contracts: **100 passed
  in 0.46s**. Initial parser-only run: 61 passed; subsequent additions cover reviewer
  requests for deprecated events, duplicates and incomplete page-count metadata.
- Whole repository Ruff passed; configured mypy passed all 830 source files; `git diff --check` passed.
- Next: independently review this parser; implement separately owned bounded native
  collector and linked-identity contract only after shared interfaces are approved.
  See [frozen parser interface and evidence limits](design/tiktok-native-discovery-parser-v1.md).

### 2026-10-07 — Pure Linked TikTok Discovery Assessment

- Added strict versioned assessment over frozen native parser pages and supplied
  account scope. Retains selected observations/ID scalar qualification and fixed
  reasons; publication eligibility always not_assessed, spend none, ownership only
  scope consistency. No DB/freshness claim, catalog promotion or ad/create changes.
-93 pure assessment/parser cases passed, including rehashed tampering and exact
  SHOPPING with parser recognition deliberately unevaluated; whole Ruff/mypy832
  pass. Log /tmp/inlet-linked-assessment.log. One expected serializer warning from
  intentional wrong-type model_copy input. No DB, Full, remote or live operations.
- Existing social publication contract compatibility:14 tests passed, preserving
  original v1 source contracts; /tmp/inlet-linked-v1-compat.log. Diffcheck clean.

### 2026-10-07 — Freeze Nested Linked Assessment Scope

- Root review found the frozen request still held mutable ExecutionAccount and
  AccountScope instances. Added exact-shape frozen local projections and a copied
  input conversion; shared financial models unchanged. Event index now bounds0–999.
-108 assessment/parser/v1 compatibility tests passed, including original-instance
  mutation isolation and rejected nested result assignments. Whole Ruff/mypy832 and
  diffcheck passed. /tmp/inlet-linked-assessment-frozen.log. No DB/IO/live/remote.
## 2026-10-07 — Bounded Owned TikTok Discovery Reads

- Isolated `codex/inlet-tiktok-owned-discovery` descends parser `1b5cee8`;
  proposal `caaddb3`, strict aggregate interfaces `8864036` + expected frozen-model
  mutation test annotation `57c01c9`. Contract-only five cases passed. The first
  static invocation correctly flagged the intentional assignment to a frozen model;
  a narrowly scoped expected-error annotation corrected that test, not its behavior.
- Added `TikTokOwnedDiscovery.identities(...)` / `.pixels()`, GET-only MockTransport
  contract-test assembly using existing owned TikTok vault/session contexts. Exact
  scope/token/current generation/original session rechecked around every HTTP read
  and after transport close. No DB locks during HTTP, no new secret reader, no retry.
- Full requested-scope traversal requires consistent cardinality, totals and unique
  IDs. Unknown/missing native IDs cannot establish completeness. Scalar-shape and
  publication/financial qualification remain explicitly unavailable. Ten-page,
  per-page/cumulative-byte and total elapsed-time bounds; duplicate raw JSON keys,
  nonfinite scalars and deep nesting fail closed and sanitize without raw output.
- Final parser/aggregate/owned-context tests: **113 passed, zero skips**, 64.01s,
  SQLite + PostgreSQL. Intermediate 36-case cohort passed. Adverse initial byte-limit
  test: 24 passed/one failure because the fixture's950-byte allowance exceeded the
  actual total response; corrected to first actual encoded response length+1. No
  production limit or guard relaxed. Logs `/tmp/inlet-tiktok-owned-discovery-tests.log`
  and `/tmp/inlet-tiktok-owned-discovery-final-strict.log` preserve this distinction.
- Whole Ruff and configured mypy834 passed. Extra elapsed context/stream-delay and transport-mode tests: **4 passed**
  (42 deselected) in7.36s across both DBs. Final `git diff --check` passed.
- **Not wired:** native customer API/browser, new linked identity publisher, native
  production qualification. Existing decoded CUSTOMIZED_USER runtime remains as-is.
  No schema, root qualification checkout, Full, remote or live provider action.
- Final requested ownership boundary: caller-supplied wrong workspace and stale
  connection generation both reject before the first GET on SQLite and PostgreSQL:
  **4 passed** (46 deselected),7.77s. Product code remains `17cb712`; this successor
  adds only focused tests/ledger. Focused Ruff/mypy and diff check pass.

## 2026-10-07 — Customer TikTok Discovery API

- Isolated `codex/inlet-tiktok-discovery-api` from root `dc75330283e674f70f3053f0bbcdb7f9c15ac881`.
  Contracts frozen2052a5b, strict event/permission consistency e3887f6. Added owned
  CSRF POST `/execution/tiktok/discovery`, bounded safe customer projection and normal
  pinned-source/owned-vault read assembly. Default source unavailable; BC selection
  unavailable until server-owned source exists. No provider identifiers accepted.
- Preserves original bound authorizer across rollback, separate fresh transport per
  traversal, original credentials across both reads and final source/session delivery
  checks. Counts describe complete requested traversal; visible lists max20 with
  explicit truncation, missing event totals stay null. No financial builder or writes.
- Final actual configured API + contracts + route-boundaries: **41 passed**, zero
  skips,50.35s on SQLite/PostgreSQL. Intermediate20API passed38.94s. Initial test-only
  privacy substring assertion failed because `scope` occurred in the literal
  `complete_requested_scope`; exact forbidden-key assertion corrected it. Evidence
  logs `/tmp/inlet-tiktok-discovery-api.log` and `...-api-checked.log` retain results.
- Whole Ruff + configured mypy848 passed; diff clean. Reusable fixture and exact UI
  schema documented in [customer discovery API](design/tiktok-customer-discovery-api.md).
- Remaining dependent acceptance: actual customer UI/TLS. No old social serializer,
  eligibility gate, schema, Full, remote or live-provider changes.

### Read-Only TikTok Customer Discovery UI — 2026-10-07

Local UI package follows frozen customer API `1fa24090ca0c58c613905f0769b560720cc2ca45`.
The execution page explicitly loads owned TikTok accounts and reads named identity,
pixel and event observations. Reported availability is not publication eligibility;
missing events remain unknown, and bounded display truncation is visible. Session,
workspace and local selection changes erase stale output. Existing approval and
publication controls remain independent.

Validation on the composed UI/API tree: actual configured HTTPS journey **2 passed**
(SQLite/PostgreSQL), including exact seven-GET/no financial-builder checks and zero
provider writes or financial graph records. Focused frontend/contracts plus existing
configured TikTok complete-publication browser compatibility **13 passed**. Whole
Ruff, scoped mypy (2 UI test files), Node syntax, and `git diff --check` passed.
No Full, remote action, screenshot, live call, or runtime getter override was used.
See `docs/inlet-tiktok-discovery-ui.md`. Publication qualification and Business Center
selection remain separate unavailable capabilities; this feature grants neither.

### 2026-10-07 — Owned Candidate API And Per-Job Runtime

- Added ordinary configured candidate-only capabilities/read/status/review API,
  per-original-principal shared native runtime, exact selection_for(mandate), and
  per-job scheduler contexts. Private read sessions do not commit caller state;
  pinned source registry remains empty, automatic first-decision remains unavailable.
  Default-off stage uses existing customer tick/master switch. Manual/V2 preserved.
- Actual configured Google/Meta bothDB API/worker with no seeded candidate/jobs:
  unqualifiedblocked result, scenario separate exact review+approval, original-session
  revocation before/during nativeHTTP and closed contexts.22 configured/manual/V2
  checks passed108.99s; broader156pass4expectedSQLite skips terminal0.
- Independent review found earliest pre-process admission failure could shadow later
  same-workspace work. ReproducedSQLite+PG beforefix (preserved starvation-before logs).
  Canonical locked60s metadata-only deferral preservesfences/leases/attempts and no
  retryauthority. Final fairness/API/scheduler58passed79.69s. WholeRuff/mypy843,
  fresh assembly/API/main imports and diffcheck pass. Exact logs/limits documented
  docs/inlet-configured-candidates.md. No Full/remote/live/schema changes.
- Evidence correction: initial8f93 purefixture IDs were invalid;1testfailed, trailing
  staticcommand maskedpytestexit. Corrected2puretests passed withvalidIDs; no schema
  relaxation. Parent notified immediately; original overwrittenlog limitation and
  retained observed failureexcerpt documented. Do not treat initial claim aspass.

### Candidate-Only Customer UI — 2026-10-07

Isolated child of configured backend `9580eb98`; additive projection commit
`2480f9f` supplies canonical server `decision_digest` with exact null/hash validation.
Existing Campaigns now offers named registered policies and consented mandates,
explicit bounded read requests/progress refresh, plain blocked reasons and exact
result review handoff to ordinary separate approval. No automatic mode, client
proof/hash construction, numeric policy editing or provider mutation is introduced.

Actual configured HTTPS journeys **4 passed** across SQLite/PostgreSQL, plus the
focused DOM contract **1 passed**. They create jobs via the ordinary API, execute
the scoped worker, retain unqualified results as blocked, and clearly label fixture
qualification on the scenario review/approval path. No seeded candidate/execution
records or runtime getter overrides. Zero provider writes/attempts/receipts/holds.
The final configured API/contract + existing manual Google/V2 browser compatibility
cohort **13 passed**. Whole Ruff, scoped mypy **8 files**, Node syntax/DOM and diff
checks passed. Exact stale detached review controls cannot send new requests.

No Full, remote action, live call, deployment or automatic-source activation.
Genuine calibrated production evidence remains unavailable; the UI does not grant
it. See `docs/inlet-candidate-customer-ui.md` for limitations and recovery behavior.
### Google Original Creation/Activation Completion — 2026-10-07

Isolated branch `codex/inlet-google-completion-extension`, baseline `ac26a67`.
Pinned official v25 seven-service review found a genuine conversion-goal wire defect:
`partialFailure` is unsupported by that update-only service. Separate fix `3318338`
reproduced one strict-schema failure before repair; 41 focused tests passed afterward.
Typed evidence interfaces frozen in `24ffb68` preserve v1 document and shared response
bytes. The implementation captures only original successful single-operation responses,
atomically persists exact run/attempt/fence/operation/result lineage, and consumes it
through the existing owned receipt GET. Final original-session/owner checks preserve
closing-workspace historical reads. No financial finality, closure inference, replay,
reservation release, new schema or live authority is introduced.

Final affected cohort: `pytest tests/test_google_execution_completion.py
 tests/test_google_execution_completion_contracts.py tests/test_google_runtime_api.py
 tests/test_google_publication_http.py tests/test_google_activation.py
 tests/test_google_completion_evidence.py tests/test_google_request_terminal.py
 tests/test_provider_coordinator.py` — **154 passed, 1 SQLite-only concurrency skip**,
167.25s, `/tmp/inlet-google-completion-final-cohort.log`. The added conflicting-response
rollback cases separately passed **2** on SQLite/PostgreSQL, 5.95s. Actual configured
API journeys use ordinary runtime assembly and lower MockHTTP, never seeded execution
reviews/attempts/receipts or getter overrides. Both original holds remain protected.
Native PostgreSQL v1/v2 populated dump/restore, scoped immutable FK and downgrade
refusal: **2 passed**, 68.81s, `/tmp/inlet-google-completion-restore2.log` (10 existing
Alembic path-separator warnings). The initial missing-tools invocation had 2 skips;
real container tools resolved it without reset or installation. Whole Ruff, mypy
**850 files**, and diff checks passed. Full, remote, deploy and live-provider actions
were not run. Root's immutable qualification checkout/database were untouched.

Source, exact interfaces, adverse fixture evidence and remaining financial gaps:
`docs/design/google-publication-completion-extension.md`. Next independent work is
review/integration; native financial source/control-boundary qualification remains
unavailable and is not inferred from this operation evidence.

### Google Original Total-Envelope Observation — Local Read-Only Package

- Source root `d94cd6a`, isolated `codex/inlet-total-envelope-observation`; public contract
  freeze `fc29011`. Explicit owned CSRF POST `/execution/runs/{run_id}/envelope-observation`
  binds actual captured original total-budget creation to the existing native inventory.
- Original native amount and retained reservation remain separate; current matching/drift
  never grants spending authority, financial bounds or settlement. Historical consent is
  lineage, not a requirement to reactivate an old grant. Current session/source/paid-read
  checks and fresh post-I/O binding/clock are mandatory; no DB locks span provider reads.
- Actual configured API + vault + MockHTTP SQLite/PostgreSQL verification, exact guards,
  default-off behavior and Google regressions: **74 passed in 91.45s**. Whole Ruff and
  configured mypy **867 files** pass; diff clean. Evidence and adverse intermediate results:
  `docs/design/google-total-envelope-observation-interface.md`,
  `/tmp/inlet-total-envelope-final.log`. No schema, persistence, Full, remote or live calls.
- Next: independent source review and optional customer UI consuming the frozen response.
  Financial quantity/history/complete-allocation qualification remains explicitly unresolved.
### Resumable Shopify acquisition — shared interface checkpoint

- Root approved storage/cadence64ff701 and reserved0082 down0081. New isolated
  contracts define explicit technical profile, exact customer intent/status,
  immutable checkpoint/day aggregates and private native-handle shape. Three ORM
  declarations carry composite owned FKs, active-store uniqueness and state/time/
  lease constraints. Registration, migration guards and lifecycle integration are
  next; no deployed schema or usable job route exists at this checkpoint.
- Existing Shopify Vault encrypts handles under a domain committing workspace,
  store, acquisition/request, phase/sequence and entire checkpoint digest. No raw
  customer identity or provider response is admitted to that shape.
- Focused contracts plus existing independent HTTP/contract tests:50passed0.48s,
  terminal0. WholeRuff passed; wholemypy847 passed; diffcheck passed. New tests cover
  seven cross-context/checkpoint tamper cases, immutable fields and invalid cadence.
  No DB/Full/remote/live calls. No maturity/direction registration. Next: portable
  0082guards and actual bounded enqueue→leased worker→unchanged v2publication.

### Resumable Shopify acquisition — configured operational package

- Added actual original-session owner API enqueue/status/cancel and dedicated
  default-off `app.jobs.commerce_acquisition_worker`. The ordinary configured API
  reads an explicit server profile; actual mocked GraphQL steps publish through
  the existing unchanged v2 independent-publication format. No acquisition jobs,
  publications, runtime getters or authority guards are seeded/overridden in the
  new enqueue-to-worker acceptance. Existing fixture source connection/confirmed
  goal setup is reused; identity/clock/HTTP are explicit offline provider seams.
- Migration0082 down0081 adds only owned job/checkpoint/HMAC-seen leaf tables and
  frozen portable guards. Request/profile/scope/deadline are immutable; active
  store uniqueness, composite ownership, SQLite FK enforcement, nonempty downgrade
  refusal and populated parent preservation are exercised. PostgreSQL fixture uses
  real Alembic history; SQLite uses existing metadata parents then actual0082
  downgrade/upgrade. The historical0081 graph test now asserts its own ancestry,
  rather than incorrectly requiring0081 to remain the latest revision.
- Each leased claim emits at most one provider request. Canonical principal/source
  locks precede the queue row; no DB transaction is held during HTTP. Exact source,
  original session, generation, lease and sequence are rechecked before persistence.
  Bounded round-robin selection excludes active leases. Factory failure/backoff and
  abandoned lease recovery preserve original acquisition ID/start/deadline; failed
  request byte reservations are distinct from successful response-byte counts.
- Existing metric normalization is reused, including older-order refunds on their
  processing date. Nested sale and order pagination round-trip durable JSON. Late
  logout/generation/goal/cancel denies publication and removes staging. Another
  session belonging to the same owner cannot adopt/replay the active job. Every
  publication remains unresolved/unqualified, with no advertising authority.
- Native handles are encrypted under the existing Vault with full checkpoint and
  deadline purpose binding; malformed/mismatched pending handles deny before IO.
  Supplied transports close even when local pre-IO validation fails. Handle reads
  deny at the fixed deadline; bounded physical cleanup remains reachable while
  disabled through the runner and existing privacy maintenance. This is not a
  guaranteed exact-time physical erasure or cryptographic key-destruction claim.
  Lifecycle registry/export explicitly excludes private checkpoint/seen tables and
  private job fields. Protected financial records are unaffected.
- Validation, all offline and on a dedicated disposable database:
  - Initial expanded compatibility:143passed/3expected skips/5failed. Failures were
    explicit export dispositions and the old assumption every owned table exports;
    fixed without weakening private-field omission. Exact five-case rerun passed.
  - Final acquisition + archive/lifecycle cohort:107passed/2expected skips in144.56s
    (`/tmp/inlet-acquisition-final.log`). Earlier focused independent-publication/
    source/proof0081 compatibility cohort:124passed, terminal0.
  - Actual same-ID abandoned lease recovery:2passed5.17s; frozen DDL/guard inventory:
    1passed; final reducer/transport closure:6passed0.37s; final actual configured
    API publication+retry:4passed8.54s with `--durations=20`. Longest test call in
    that bounded sample was PostgreSQL retry1.77s, not a Full performance diagnosis.
  - Whole Ruff, whole mypy857 and diffcheck pass. No Full, remote, live store calls,
    source qualification, automatic registration, deployment or advertising changes.
- Retained intermediate failures: SQLite aware-deadline projection corrected;
  dedicated migration database renamed to the repository's required `_test`
  convention; two-tenant fixture needed distinct login tokens/workspace/shop names.
  None were treated as passing checks or repaired by relaxing production ownership.
- Next: independent source review and parent integration; production scope access,
  runtime deployment and measured real-store capacity remain unverified. The
  acquisition itself does not supply settled/mature assurance. See
  `docs/inlet-resumable-shopify-acquisition.md` for configuration and limitations.

### Acquisition publication atomicity correction

- Independent source review of b0eeeeb found a real late-denial transaction gap:
  `publish_in_transaction` flushes a publication/revision before its final authority
  check. The worker caught that failure and committed unavailable-job cleanup in
  the same transaction, inadvertently retaining the publication. b0eeeeb is
  superseded by this correction; do not integrate it alone.
- Reproduced through actual API enqueue and five actual MockHTTP GraphQL steps.
  Advancing the clock two hours immediately after the real publication INSERT made
  the original check deny while publication count incorrectly rose from1to2
  (`/tmp/inlet-acquisition-atomicity-before.log`,1failed2.68s). Reviewer independently
  reproduced identity denial after flush on both databases,2failed7.60s; no authority
  guard was replaced by a passing fake.
- Wrapped the publication writer, completion/staging updates and every final check
  in a real nested transaction. A late failure rolls back publication and revision
  before unavailable cleanup commits. Final fixed-deadline and current operational
  controls are now checked explicitly within that savepoint as well.
- BothDB real clock/credential and deadline-only denials now retain original
  publication count/revision, no job publication pointer, and erased staging.
  Together with ordinary configured publication and transport retry:8passed14.18s,
  `--durations=20` (`/tmp/inlet-acquisition-atomicity-after.log`). WholeRuff/mypy857
  and diffcheck pass. No schema/interface/byte-format change, Full, remote or liveIO.

### Acquisition final-deadline ordering follow-up

- Reviewer independently confirmed2cdc's savepoint repair (bothDB2passed5.33s),
  then identified a remaining ordering gap: the last source/identity check can
  block after the prior deadline sample. Reproduced with the real completed-job
  UPDATE followed by clock advancement to deadline+1 inside the final workspace
  SELECT while credentials remain valid; publication count again became2vs1
  (`/tmp/inlet-acquisition-final-deadline-before.log`,1failed2.77s).
- Re-sample the persisted fixed deadline immediately after final `_check`, inside
  the same rollback-protected savepoint. Both insert-time and final-check-time
  advancement at1801s/7200s plus ordinary actual configured publication now pass
  both databases:10passed18.37s with durations20. WholeRuff/mypy857/diffcheck pass.
  Final successor is required alongside2cdc; no schema/interface or live changes.

### Customer Google Budget Observation UI — Local Package

- Isolated `codex/inlet-envelope-customer-ui` from `7f10a42`, consuming frozen backend
  `2655940`. Saved execution now offers an explicit read-only Google Budget Observation.
  Unsupported runs/default-off returns truthful unavailable; no inferred eligibility.
- Separately displays original/current native total and recorded reservation, with fixed
  financial-unqualified/no-release captions. Strict response/run/environment/expiry checks;
  clears stale run/workspace/session/logout and delayed ABA responses, including local expiry.
  No automatic native reads, polling or new advertising mutation.
- Actual configured creation/capture then actual HTTPS login/API/vault/MockHTTP on both DBs:
  final new tests **3 passed in 9.45s**, exact two-read wire count/no holds changed.
  Existing configured all-three-provider creation+activation HTTPS compatibility:
  **6 passed, 30 deselected in 123.53s**. Both commands used `--durations=20`.
  Whole Ruff/mypy **869 files**, Node syntax and diff clean. Evidence:
  `docs/inlet-google-envelope-ui.md`, `/tmp/inlet-envelope-ui-final.log`,
  `/tmp/inlet-envelope-ui-compat.log`. No Full, remote, live or preview artifacts.
- Independent Shopify0082 review also closed at `512df29`: reproduced late-authority
  publication commit leak (both DBs), author savepoint+post-final-check deadline repair,
  independent final regressions **2 passed in 5.31s**. No reviewer source edits.


### Customer Shopify Window Reads And Original-Session Recovery

Branch `codex/inlet-commerce-acquisition-ui`, base 19ff2fa; response contract freeze
70780aa. Added bounded original-session recovery GET (20 + probe, explicit
truncation) without changing AcquisitionIntent/Status or schema. Measurement History
now supports confirmed-goal/local-window selection, explicit request, named status,
fixed deadline, cancel, reload recovery and independent publication reference.
Unresolved corrections, unqualified maturity and no spending authority remain
visible. Existing v1 measurements/descriptive behavior remains separate.

Actual configured TLS → API → worker → newly produced v2 publication passed on both
DBs, including disabled configuration, lost ID, conflicting active request,
cancellation, original-session revocation and delayed-response selection fencing.
Separate API tests prove another original session cannot list/adopt/cancel the job;
21 actual enqueue/cancel requests prove recovery truncation. Existing worker
atomicity/fairness/privacy/lease tests remained green.

Exact validation: 42 passed in 57.72s, `/tmp/acquisition-customer-final.log`; final
frontend original-cookie/pre-IO guard then 4 impacted TLS passed in 13.31s,
`/tmp/acquisition-customer-session-final.log`. Both ran `--durations=20`. Whole Ruff,
mypy882 (`/tmp/acquisition-customer-mypy.log`), Node syntax and diff checks passed.
No Full, remote/hosted, live provider calls, new schema, runtime enablement or
advertising actions. Dedicated disposable PostgreSQL fixture schemas were used.

Failure record: initial API fixture used datetime for integer session revoked_at
and replayed an already-exchanged identity token; corrected to integer/fresh token
without production changes. Initial TLS exposed tied-timestamp recovery selecting
an older completed job over the newly requested job; fixed exact selection/active
priority. Next TLS ran all browser actions but its final fixture wrongly expected
jobs after existing session-revocation erasure; corrected to verify actual job and
publication before revoke, then verify queue deletion. Initial Ruff UTC alias and
unused-ignore mypy issues were corrected before final checks. Failed logs retained
at `/tmp/acquisition-recovery-api.log`, `/tmp/acquisition-recovery-api-fixed.log`,
`/tmp/acquisition-customer-browser.log`, `/tmp/acquisition-customer-combined.log`.

Limits: the configured dedicated worker must run; browser refresh does not run it.
Completion is an as-of observation, not settled/full-history/causal or automatic
optimization evidence. Design and callables:
`docs/design/customer-shopify-acquisition-flow.md`.
### Linked TikTok Pull VIDEO catalogue — pure interface freeze

- Reused unchanged linked owner/identity contracts from5e418b0. Added immutable
  request/page/post/catalogue types and pure lossless decoder; exact owned request
  binding is explicitly not returned per-row identity proof or eligibility.
- Parent-rendered identity/video/get schema supplies the fields. First cursor is
  omitted based on its absence from the required list; no guessed zero. Numeric
  cursors retain original canonical strings and convert directly to integer, may
  decrease, and reject continuation cycles/duplicate posts. Empty terminal pages
  remain valid. Optional facts preserve null/absence; media URLs/signatures and
  unnecessary authorization/anchor contents are discarded.
-21pure tests passed0.27s with durations20. Actual owned HTTP collector and bothDB
  revocation/pagination acceptance are next; no endpoint/UI or live-source claim.
  Exact proposed callables and evidence limits:docs/design/tiktok-linked-posts-catalog.md.


### Linked TikTok Pull VIDEO catalogue — owned collector

Implemented the frozen reader with actual original-session/source/Vault contexts,
GET-only fixed endpoint, before/after-page and post-close authority checks, exact
cursor serialization and lossless decimals. Traversal is bounded by 25 pages,
500 rows, 2 MB/page, 8 MB total and 30 seconds; incomplete traversal returns no
catalogue. No media URLs are fetched or retained. Only explicit contract-test
MockTransport works; constructors reject live/nonmock before credential access.

Validation (isolated `codex/inlet-tiktok-linked-posts`, base 5e418b0):
- Actual owned SQLite/PostgreSQL suite: 14 passed, 24.37 seconds, including request
  and close-time revocation, generation/manifest drift and foreign workspace.
  `/tmp/tiktok-linked-posts-owned.log`; dedicated disposable database
  `inlet_tiktok_posts_test`, isolated fixture schemas.
- Pure parser/resource bounds: 32 passed, 1.58 seconds before two constructor
  denial additions. Final parser/bounds plus existing linked contracts/compiler/
  wire cohort: 59 passed (exit 0), `/tmp/tiktok-linked-posts-compat.log`.
  Both planned cohorts retained `--durations=20` output.
- Whole Ruff and whole app/tests mypy passed; diff check passed.

No routes/UI/schema, source registration, live calls, advertising changes, remote
writes or Full validation. Publication eligibility remains `not_assessed`, spending
authority `none`; pagination does not imply stable snapshot/full-history coverage.
Details: `docs/design/tiktok-linked-posts-catalog.md`.
### Linked TikTok Compatibility Fixture Migration

Test-only package on `codex/inlet-tiktok-linked-compat`, author base494ec217 plus
root committed UI f7a5667 as dependency. Future coordinator/activation and all
eight configured browser scenarios now use linked Push contracts and actual linked
customer review/consent. Old configured CUSTOMIZED_USER future creation explicitly
expects409 with no new reviews/attempts/holds/writes. Five previous future scenarios
remain in author-owned `test_tiktok_linked_runtime_api`. Historical rollout and
canonical producer fixtures use explicitly named old setup with a narrow pre-policy
context; the production guard is restored before forward/readback assertions.
No product scenario exemption, runtime getter override or application-code change.

Terminal validation, both DBs, each `--durations=20`:
-74 coordinator/activation/historical policy/runtime boundary tests passed307.69s:
  `/tmp/tiktok-linked-compat-first.log`.
-28 producer and customer execution tests passed69.42s:
  `/tmp/tiktok-linked-compat-producers.log`.
-14 direct configuration API/UI/review/populated-migration consumers passed57.45s;
  four existing Alembic path_separator deprecation warnings:
  `/tmp/tiktok-linked-compat-legacy-consumers.log`.
-16 configured linked TLS browser cases passed412.39s (6m52s), all eight scenarios
  on SQLite/PostgreSQL: complete, unknown creation, unknown activation, revoked,
  source, media, declaration and profile. `/tmp/tiktok-linked-compat-browser-final.log`.
  Slowest37.62s; ordinary saved-run state/receipt/hold assertions retained.
-Whole Ruff, mypy890 (`/tmp/tiktok-linked-compat-mypy.log`), Node syntax and diff pass.

Initial migrated browser16 failed due to getElementById being passed nested CSS
selectors; corrected driver to querySelector, retaining actual video/cover decoding
assertions. One corrected complete case then found the old environment assertion
looked at the unloaded workspace capability panel on direct saved-run navigation;
assertion now uses the real saved run's Contract Test label. Corrected single case
passed35.11s before final16. Failed logs retained at
`/tmp/tiktok-linked-compat-browser.log` and `...-browser-one.log`.
No prior Full pass is claimed for this successor. No Full/hosted/remote/live/deploy
or advertising actions. Exact coverage mapping:
`docs/design/tiktok-linked-compatibility-migration.md`.

### Missed Historical TikTok Execution-UI Fixture Follow-Up

Root identified one additional direct `setup_social` consumer:
`test_customer_social_execution_ui.py`. Unchanged TikTok journey/clarity baseline
reproduced4failures105.61s on bothDB, waiting for a positive review after intended
new-CUSTOMIZED_USER409. Baseline log `/tmp/tiktok-legacy-ui-baseline.log` is terminal,
not partial/cancelled. Import search found no further direct consumers.

Added a TikTok-only historical-denial browser driver retaining exact owned
identity/pixel/media summary, distinct covers and actual playable video/decoded
image checks. New creation must return the fixed409 code with hidden review,
disabled approval/run, no new reviews/attempts/receipts/holds or provider writes.
Future positive/media/unknown journeys remain in the genuine linked browser suite;
Meta drivers are unchanged.

8repaired+Meta compatibility tests passed55.94s (26unaffected scenarios deselected),
`/tmp/tiktok-legacy-ui-fixed.log`, durations20. Whole Ruff/mypy890, Node syntax/diff
pass. Initial new-test line-length formatting fixed before final static check.
Test-only successor to4c1b05e; no application changes/Full/remote/live.

### 2026-10-07: separate reported-rule contract/compiler checkpoint (local)

Approved interface854fa69 now has strict ReportedRulePolicy/Evidence/Observation/
Work/Candidate variants and pure nominal compiler in reported_feedback. No old v1
literal/hash/parser changed; no source registered, no runtime consumer enabled.
Actual report evaluator fixture supplies before/after totals; 11 focused cases
passed, covering no qualified-learning cast, complete distinct report references,
direction/absence/environment contradictions, stale/actions/native/quantum blockers
and cumulative increase clipping without changing the mandate. Scoped Ruff/mypy
(3files) and diff check pass. Initial static invocation found import sorting and
optional-action test annotations; fixed before checkpoint. 0083 dependency relation
reserved; owned source/worker/API/TLS remain in implementation, not yet accepted.

## Reported-rule owned evidence and erasure foundation (2026-10-07, local)

The separate operational reported-efficiency reader now consumes actual retained
Meta comparisons/capsule dependencies and a fresh whole-owner native snapshot.
It checks the original session, current source, original request/ledger/native
scope, and final lifetime after authorization waits. It never labels these facts
qualified learning or grants spending authority. The reader performs no network
calls, commits or financial mutations.

Reserved migration 0083 adds immutable, composite-owned candidate dependencies.
Capsule/comparison/job erasure retracts derived suggestions; explicit replacement
requests invalidate previous candidate dependencies transactionally. Original
attempts and held financial obligations are retained. A populated downgrade is
rejected. Registry, archive allowlist, local-work classification and historical
0074 fixture ordering include the new relation.

Evidence: actual mocked original Meta operation, four report acquisitions, fresh
native GET and ordinary commerce import feed the source tests on SQLite and
PostgreSQL. The erasure cohort covers candidate/comparison/capsule deletion,
explicit changed-objective replacement, foreign lineage rejection and retained
obligations. Initial fixture failures (missing commerce publication, wrong review
binding accessor, SQLite foreign keys disabled), a test expecting IntegrityError
instead of PostgreSQL trigger RaiseException, and an attempted reobserve of a
sufficient comparison were corrected; none qualified a product pass. Their logs
remain under /tmp/inlet-reported-rule-*. Whole mypy passes 893 files; Ruff and diff
checks pass. Configured worker/review/explicit-Start composition is still pending;
this foundation is not completion of usable automatic optimization and no
production rule/profile is registered.

Foundation check completion: pure compiler 11 passed; owned source/final-wait
expiry 4 passed; final erasure/foreign-owner/lossless-downgrade cohort 10 passed;
actual 0083 empty roundtrip 2 passed. Existing service/authority/lifecycle cohort
had 41 passed, two historical-fixture failures and one PostgreSQL-only skip on
SQLite; explicit 0083 predecessor handling repaired both. Final historical
0077/0074 cohort: 7 passed, one SQLite-only Alembic skip. Whole Ruff, mypy
(893 files) and diff checks passed. The 0083 fixture correction also covers the
previous Full's exact 0074 test on both databases. No Full/remote/live run.

Independent source review follow-up: the final rule helper previously depended
on its future caller to repeat the commerce source fence. Two controlled source
revision drift tests reproduced acceptance on both databases. The helper now
checks owner and exact current commerce source itself after the original-session
workspace fence. All six source/final-wait/source-drift cases pass; no financial
admission or production source registration changed. Baseline/fixed logs:
/tmp/inlet-reported-source-final-before.log and -after.log.

### Operational reported-rule dispatcher checkpoint (local, 2026-10-07)

The new discriminated work/policy/decision parsers preserve legacy v1/v2 documents. Real Meta native catalog reads now select the exact current owned comparison and original receipt, enqueue a dependency-bound job, compile the separate reported-efficiency result, and export it through strict versioned parsers. The reported work requires the original attempt and receipt commitment in the existing source fence. All result publication rechecks the original session, source, comparison and dependency after I/O. Legacy qualified-learning transforms and automatic admission explicitly reject the new operational variant; distinct automatic Start/configured policy assembly is still pending.

Actual SQLite/PostgreSQL catalog→selection→queue→worker cases pass with unchanged provider writes, attempts and reservations. Late session revocation, source revision and capsule erasure deny result publication. The combined worker/selection/pure-rule/directional compatibility cohort passed 54 tests with 3 expected SQLite-only skips; the all-provider legacy candidate review + automatic execution + exact numeric-policy binding subset passed 14 tests. Whole Ruff, mypy (896 files), and diff checks passed. Logs: `/tmp/inlet-reported-dispatch-final.log`, `/tmp/inlet-reported-dispatch-legacy.log`, `/tmp/inlet-reported-dispatch-mypy.log`.

Adverse evidence retained: initial worker fixture used an already-expired original mandate period and correctly failed admission. The fixture now genuinely consents an explicit extended period before the original action; no production freshness or financial guard changed. Subsequent test-only context typing and annotation errors were corrected before the final checks. This checkpoint is not configured customer/TLS acceptance, an operational automatic Start implementation, or production policy qualification. Those remain ordinary follow-on implementation within the approved package. No Full, remote, provider-live, or qualification checkout/DB action occurred.

### Reported customer basis / explicit Start interface freeze

The additive candidate basis projection is now constructed from the actual owned current comparison and exact rule. Pure contract tests4 pass; genuine report acquisition→selection→worker→safe basis projection2 pass across SQLite/PostgreSQL. Exact CPA strings5000000→2500000, four completions versus one original, nominal delta-250000 and omitted capsule bodies verified. Whole Ruff/mypy899/diff passed. Separate operational automatic policy/option/Start models freeze the dependent UI surface, but their route union and runtime/admission wiring remain pending, explicitly documented in `docs/design/reported-rule-customer-interface.md`. No automatic or production qualification claim.

### Operational repeat admission and exact own-successor continuation

The actual reported acquisition→candidate→review→manual approval or distinct original-session reported-rule Start→automatic admission→Meta HTTP path now completes on SQLite and PostgreSQL. Automatic execution adds no human approval; the original exposure transfers through the existing reviewed replacement proof and one held reservation remains. Financial closure/exposure in this component fixture is explicitly the existing contract scenario, not inferred from reports or promoted to production.

Adverse baseline: `/tmp/inlet-rule-auto-actual.log` reproduced self-invalidation at claim after the successor reservation transfer. The strict original-head anchor was correctly rejecting a changed head. The bounded repair adds a private forward review context, validated against exact composite candidate/result/job/session/review and direct immutable replacement lineage. Only its own still-dispatching, not-emitting original attempt without response/receipt is excluded from intervention checks. Normal reads and unrelated review IDs remain denied; the original anchor retains its original reservation commitment. Details: `docs/design/reported-rule-own-successor-context.md`.

Twelve actual both-DB cases passed in `/tmp/inlet-rule-auto-negative.log` (slowest PostgreSQL automatic happy15.96s): manual/automatic success, revocation/capsule deletion/original latest unknown receipt before emission, unknown successor no replay and reconciliation after candidate erasure. A further exact policy revision/restart dedupe regression passed both DB in `/tmp/inlet-rule-auto-restart.log` (16.19s PostgreSQL,7.88s SQLite); the existing semantic admission remains one. Legacy API/automatic contracts plus reported comparison/service compatibility33 passed in `/tmp/inlet-rule-continuation-compat.log`. Commands used `pytest -q ... --durations=20` against the isolated per-test PostgreSQL schemas; no Full or qualification database touched. Whole Ruff/mypy901/diff clean.

API Start now accepts the distinct reported request only for its matching registered policy/digest; legacy bodies cannot select it, and cross-basis fallback rejects. Capabilities emits the separate frozen option with explicit parameters/cadence/lifetime when such a runtime is actually provided. Pinned configured assembly and genuine configured HTTPS acceptance remain next; this checkpoint does not install any policy/source/runtime default or claim that assembly complete.

### 2026-10-07 — configured operational repeat API and original-session worker

On isolated `codex/inlet-learning-requirement-trace` after reviewed 7a89035,
implemented pinned, separately discriminated reported-rule configuration and the
ordinary request/worker assembly (`docs/design/reported-rule-configured-runtime.md`).
Default source registration remains absent. Existing configured optimization
qualification/origin/exposure/replacement gates are unchanged.

Genuine API fixture starts with the actual 0080 customer mandate origin and first
Meta HTTP operation, discovers campaign data through HTTP, requests the comparison,
and acquires four reports through `run_meta_tick`. It then uses ordinary configured
candidate/review and explicit automatic Start endpoints; no runtime getter override
or execution/candidate row seeding. The rule changes the observed nominal budget
45.00→44.75 under explicit fixture parameters. This is operational reported evidence,
not qualified learning or production financial proof. Automatic admission creates
zero new human approval rows and retains one linked held reservation.

Checks (all local, disposable per-test SQLite/PG schemas, `--durations=20`):
- `tests/test_configured_reported_rule_api.py`: 12 both-DB candidate/review and
  Start success/session/capsule/source/unknown cases passed in
  `/tmp/inlet-configured-reported-final.log`; slowest PG unknown 17.86s.
- Added master-off and same-workspace revoked-session fairness cases: 4 passed,
  `/tmp/inlet-configured-reported-fairness.log`; slowest PG fairness 6.10s.
- Strengthened subsequent-due-tick fence/no-replay checks: affected 4 automatic
  success/unknown cases passed, `/tmp/inlet-reported-configured-replay.log`;
  slowest PG success 21.58s. Original attempt IDs/fences remain unchanged.
- Reported/legacy configuration, legacy session API and original acquisition-helper
  compatibility: 41 passed, `/tmp/inlet-reported-configured-compat2.log`.
- Entire existing customer scheduler cohort: 32 passed,
  `/tmp/inlet-reported-configured-scheduler.log`.
- Whole Ruff, mypy (906 files) and diff check passed. No Full, hosted, live or
  remote action. Dependent actual HTTPS UI qualification remains separate.

Adverse invocation evidence retained: the first compatibility invocation named
nonexistent `tests/test_customer_runtime.py`; it ran no tests and was corrected to
`tests/test_customer_runtime_scheduler.py`. Early new-fixture failures concerned
an invalid one-day policy (existing minimum is seven days), absent campaign import,
response field names and the expected 0.25 rather than 1.00 adjustment. They were
corrected in the fixture/assertions without loosening application gates. Configured
origin checks correctly required actual 0080 consent rather than the earlier
component fixture's direct-service mandate.

### Continuous Fresh Customer Purchase, Planning And Monitoring Recovery

Successor to7bb02e9 on `codex/inlet-continuous-purchase-acceptance` extends the real
fresh-customer HTTPS pilot without seeding customer steps: unknown Stripe test
checkout recovery retains original purchase identity; Google reconnect keeps one
owned connection; goal editing advances its revision; saved progress/reload retains
its exact definition and honestly reports a not-yet-started period. Session
revocation clears progress and denies reads without provider IO. Existing actual
signup/provisioning, Shopify consent/import, paid-test webhook reconciliation,
planning consent, separate campaign review and second-brand isolation remain.

BothDB focused suite2passed19.54s, `/tmp/inlet-continuous-fresh-both.log`; initial
SQLite probe passed. Whole Ruff/mypy948/diff passed. No product edit or Full/remote/
live action. This is planning consent/offline campaign approval, not financial
execution consent; the fresh customer→configured execution bridge remains explicit.
See `inlet-continuous-purchase-acceptance.md` for exact fixture boundaries and gaps.

Freshcustomer independent-review followup asserts exact edited12000 target value,
no additional providerPOST from billing status GET, then exact2POSTs/1originalkey
after explicit customerResume. Initial proposed1POSTtotal expectation failed bothDB
because Resume intentionally performs a bound idempotent retry; no automatic retry
or product defect established, no billing code changed. Docs corrected to avoid
GET-onlyrecovery implication. Final strengthened2DBjourney2pass16.94s, whole
Ruff/mypy948/diffpass. Logs `/tmp/inlet-continuous-fresh-review.log` (failed proposed
assertion) and `/tmp/inlet-continuous-fresh-review-final.log` (passed).
## 2026-10-07 — initial reported-rule central worker/review checkpoint

Composed the strict initial document discriminator, actual owned source and 0084
source dependencies into central enqueue/worker/result/exact-review/export paths.
Generic selection cannot silently select an initial preview. Original-session and
observation erasure deny forward review; no attempts or holds are created by these
component tests. Initial automatic admission remains explicitly unavailable until
the separately proposed exact Start binding is implemented.

Evidence: 14 both-DB initial/repeat worker cases, 25 strict compiler/dispatch cases,
and 2 actual stored initial job/result export cases passed with durations recorded.
Whole Ruff and mypy (923 files) passed. See
`docs/inlet-initial-rule-central-checkpoint.md` for commands, logs, limitations and
the corrected test-only typing error. No Full, remote, hosted or live action.

### Initial Start Concurrency And Admission Acceptance

Test-only lane from4ec67ee adds real owned Start then revoked-original-mandate and
spent-ledger denial, two simultaneous independent PostgreSQL workers, actual0085
populated downgrade refusal, and ordinary configured maintenance dispatch. No
production changes; no seeded execution/admission/approval. Complete narrow run
9passed1expectedSQLiteconcurrencyskip149.94s. Positivefixture explicitlyuses120s
native/preview lifetime beforeproduction, leaving the ordinary contract-test30sTTL unchanged; no productionTTL selected.
WholeRuff/mypy934passed. Detailedfixtureboundaries/evidence and complementary
unknown-provider authorcoverage: `inlet-initial-concurrency-acceptance.md`.
Initial acceptance strengthened consumed-origin assertion: affected3positivecases
passed131.58s (7deselected), `/tmp/inlet-initial-acceptance-origin.log`; exactone
origin/admission/attempt/POST andzeroapproval onbothDBmaintenance andPGcompetition.

## 2026-10-07 — Owner Approved Comprehensive Planning MVP

Rebased acceptance and dependency plan in `inlet-planning-mvp-transition.md` on zero
advertising writes and customer manual implementation. Preserved2155ff3 and all isolated
execution successors. Next P01 maps mutation entrypoints and freezes a deployment
write-prohibition interface; coherent planning journey and recommendation quality follow.
This checkpoint is documentation only; diff checks passed, no new tests or live actions.

## 2026-10-08 — Owner Authorized Resume: Recovery Verified

Resumed from clean090a140 after environment startup. All316worktrees exist; all eight
archived historical test files are byte-identical to their preserved originals.
Inventory head differences are exactly the two documented terminal/checkpoint commits
(d7736ba and090a140). Read-only git ls-remote verified main remains ea3591c.
No tests/profilers survived the pause. No hosted run, push or provider call started.
Interrupted Full remains incomplete; previous raw logs and archives are preserved.
Next P01 is deployment prohibition of every advertising mutation; map routes, stale
jobs, CLI and concrete transports first. Planning account selection currently depends
on an execution catalog route and needs an owned read-only replacement. Execution
work remains post-launch. Recovery evidence: /workspace/inlet-evidence/20261008/recovery.json.
Documentation diff check passed; no new product behavior or tests in this checkpoint.

## 2026-10-08 — Planning MVP P01 Assembled Acceptance

Shared immutable no-ad-write boundary, direct route/background/admission/transport
guards and independent planning confirmation0086 integrated. Known Google POST search
and actual owned planning API/HTTPS browser reads preserved. Independent reviews closed.
207passed/1expectedSQLite concurrency skip/1existing Alembic warning217.16s; Ruff,
mypy994files, JSsyntax anddiffpass. Exact ledger:inlet-planning-p01-status-20261008.md.
Historical engines use explicit isolated fixtures; full legacy-suite adaptation and
Fullqualification not claimed. All work local oncodex/inlet-planning-mvp, no push/hosted/
live/deploy/mainmerge. NextP02 native targetcatalog + manual-use metadata and complete
planning recommendation/lifecycle journey; initialcatalog ownershipprojectionrepair
pending review, not silently accepted.

## 2026-10-08 — P02 Initial Three-Platform Catalog Integrated

Reviewed native target catalog and ambiguous-social-budget-ownership repair integrated
with P01.183assembled default planning cases passed69.67s across SQLite/PostgreSQL;
Ruff/mypy1001/diff pass. No financial execution dependencies or advertising writes.
Ledger:inlet-planning-p02-integration-20261008.md. Names/native references/Google adgroups
are explicit next usability work, followed by comprehensive plan/version/manual-action/
progress lifecycle. No Full/hosted/live/remote qualification claimed.


## 2026-10-11 — Exhaustive Local W1 Validation Passed

Frozen `9d7aa2e1193ec627b33088764210f94e49cf504d`: 7,011 passed / 83 unchanged
skips across all 7,094 parents; separately 404 passed / 3 allowed skips across
407 historical children in 19 batches. Exact disjoint union, archives, database
dumps, manifest hashes, original evidence and all 15 preflight groups verified.
52 completed partitions; no active validation process. No OOM; minimum sampled
memory headroom 3.10 GiB. Original failed/interrupted attempts remain preserved.
[Final result and limits](inlet-w1-validation-result-20261011.md).
Local branch `codex/inlet-w1-followup`; pushes/hosted retries held; no live calls,
ad mutations, merge or deployment. Q01–Q16 partial; six human release gates unmet.

## 2026-10-11 — Shared Selected-Event Contract

Implemented and independently reviewed immutable customer-selection/capture DTOs,
separate from aggregate metrics, with whole-source correction/privacy/generation
binding, strict presence and DST-safe instants.140focused tests passed; repository
Ruff and mypy1272files passed. [Package ledger](inlet-selected-contract-package-20261011.md)
and [Q01–Q16/human gate work matrix](inlet-quality-next-packages-20261011.md).
Pure contract only; storage/import/customer consumer not yet activated. Frozen W1
qualification preserved; all remote/hosted/live/release holds remain.

## 2026-10-11 — Resume And Raw Observation Parsing

Recovered exactdb4574c checkpoint;3drafts/14backups/52baselinearchives/52JUnit files
hash-verified. Completed independently reviewed pure Google selected-action and
TikTok generic-presence parsers; zero/missing/unsupported retained.204focused tests
passed1.65s, full Ruff and mypy1276files passed. [Package/recovery ledger](inlet-selected-raw-package-20261011.md).
No runtime import or plan activation yet. Durable-selection/publication interface
review is next; all remote/hosted/live/release holds remain.

## 2026-10-11 — Selected Summary Preparation

Pure whole-graph selected summary added; sparse/missing evidence cannot qualify full-
window zero.13new cases;156combinedpassed0.88s; Ruff/mypy1278pass; independent review
closed. [Package ledger](inlet-selected-summary-package-20261011.md). Customer-plan
activation awaits owned storage/import integration; no live or remote operation.

## 2026-10-11 — Injected Google Selected Read

Added exact account/action-metadata + selected-report HTTP reader with mandatory
server revalidation, expiry/stream deadlines and no runtime default.84MockHTTP/raw
cases passed0.63s; Ruff/mypy1280pass; independent review closed after two deadline
repairs. [Package ledger](inlet-google-selected-read-package-20261011.md). No live
qualification, source-job publication or customer-plan activation is claimed.

## 2026-10-11 — Selected Storage And Catalog Integrated

Reviewed migration0091 owned storage/CAS/invalidation/privacy/export and injected
Google event catalog integrated locally through9ed8fbb. Root combined226cases passed
70.324s across SQLite/PostgreSQL; catalog/pure cohort194passed0.896s (overlapping,
not additive); zero failures/skips. WholeRuff/mypy1295/diff passed. Both independent
reviews closed. [Integration ledger](inlet-selected-integration-20261011.md).
Original-session resolver and customer confirmation are next; strict refreshed-
aggregate proof is a caller obligation. No public activation/live qualification,
push/hosted/main merge/deploy; frozen exhaustive baseline remains untouched.

## 2026-10-11 — Private Creative Runtime Qualification

Private V5 service `4100fe5` and actual API/lifecycle fixture are implemented.
Eighteen strengthened negative/lifecycle cases passed on SQLite and PostgreSQL;
whole Ruff/mypy1,407 passed. Positive journeys passed across recorded cohorts,
but an earlier PostgreSQL generation exceeded the five-second authority limit.
The limit remains unchanged; reviewed first-slice performance work is underway.
[Exact attempts, test repairs and remaining gate](inlet-creative-runtime-qualification-20261011.md).
Default customer service remains V3. No live/hosted/release qualification claimed.

## 2026-10-11 — Private V5 Normal Runtime Checks Complete

Reviewed same-pass SQL reuse `e478b4b` preserves every independent fresh proof pass.
Normal API/lifecycle suite passed all28 cases on both databases in319.863s;
whole Ruff/mypy1408 passed. SQL counts decreased in bounded diagnostics, but
elapsed time did not improve; original timeout cause remains unproven.
Real six-second-delay regression `db4a220` passed SQLite/PostgreSQL and review,
proving unchanged five-second authority rejection with no generation writes;
its whole Ruff/mypy1409 passed. [Runtime ledger](inlet-creative-runtime-qualification-20261011.md).
Common Basis actual V5 review artifacts are next; expert/live/release gates remain.

## 2026-10-11 — Q08 Preparation And Q06 Shared-Owner Baseline

Private Q08 account preparation now retains exact empty-query proof and rejects
substituted evidence before persistence. Focused consumer98, actual API4 and one
ordered browser7 passed; their counts overlap other package checks and are not an
exhaustive claim. Q06 actual shared-owner baseline4 passed across both databases;
exact native-edit and recovery outputs remain unimplemented. Integrated whole Ruff
and mypy1,433 passed. [Checkpoint and next package](inlet-q08-q06-checkpoint-20261011.md).
R01 remains open, six human judgments remain pending, and all remote/live/release
holds remain. Artifacts are local only.

## 2026-10-11 — Original Shared-Owner Evidence And Discovery

Standalone Q06 owner/intent contracts are integrated and reviewed. Actual original
Google catalogs exposed missing metadata status; narrow query/parser retention
now supplies observed status without modifying historical receipts.54 focused pure
and4 both-database API cases passed; old missing-status catalogs still refuse.
[Metadata prerequisite](inlet-google-owner-metadata-status-20261011.md).

Read-only private V5 owner discovery integrated79ff5fc/checkpoint9e77ab8:26 actual
API cases across both databases and7 separate pure cases passed; final independent
review CLOSED. Root verified8 artifacts/four strict catalog+view pairs and whole
Ruff/mypy1,443. [Exact evidence and retained failed attempts](inlet-google-budget-owner-discovery-20261011.md).
No input/native-setting output or public UI activation. Pure input binding and
explicit historical provenance design continue; unselected account source fences
cannot be invented from current state. Q06 remains partial. Original R01 and six
human gates remain open; no remote/live/release/upload operation occurred.

## 2026-10-11 — Owner Hypothesis Inputs And Original History

Reviewed standalone active/history bindings and scalar commitment are integrated.
Atomic input consumer `cd65fdd` retains original receipt commitments through
create/edit, read, request recovery, replay and export. All non-null owner inputs
(includingempty) remain refused by generation; no budget mutation/output activation.
Final36 SQLite/PostgreSQL cases passed163.240s, plus separate15pure/golden checks;
initial overlapping SQLite cohorts are documented. Root16evidencehashes/fourXML
verified, wholeRuff/mypy1,455 passed; independentreview CLOSED.
[Exact qualification and limitations](inlet-google-budget-owner-inputs-20261011.md).

The15:52 shell disconnect recovered after one harmlessretry; savedwork/evidence
verified, no resets or duplicate tests. Q09 baseline qualification proceeds on the
new input consumer. Its exactMeta-lead/TikTok-attribution case remains unsupported;
no missing semantics are invented. Owner output remains a separate design, and
all live/remote/release/sharing holds remain.

## 2026-10-11 — Standalone Owner Review And R02 Observation

Standalone investigation-only contracts/composer/validator integrated `91171a2`
(author `072f6c3`), independently reviewed CLOSED.37 focused pure tests passed
5.457s, including legacy bytes and all seven existing generation refusals. Root
verified11 evidence hashes/XML; whole Ruff and configured mypy1,458 passed.
No existing document field, runtime policy, history path or UI was activated.
[Package evidence](inlet-google-budget-owner-review-pure-20261011.md).

Exactly one reviewed external observer ran the frozen Q09 PostgreSQL complete case
(source `0b6fd79`):1 passed21.668s. All observed authority checks returned; maximum
fact age3.042576s with session lifetime remaining. Full generation recorded8,628
SQL statements; save was an inclusive3,146-statement subset. These observations
do not establish the cause of the earlier failure. R02 and the original four-case
Q09 qualification remain open; no second probe or guard change followed. Evidence
is local in `creative-q09-baseline/probe04*`. Next work is a reviewed private V6
integration contract and separate source-only query-path investigation proposal.
All remote/live/release/sharing holds and six pending human judgments remain.

## 2026-10-11 — Historical Owner Review Ports

Reviewed V6 design `dee53c4` explicitly retains complete linked catalogs for
ordinary cross-account allocations and exclusions; owner witnesses alone cannot
cover that graph. No catalog is fabricated for an unselected owned account.
Historical slice1 integrated `3007e90` (author `b7f7163`), independently CLOSED.
Eight new pure cases, ten SQLite, ten PostgreSQL and29 unchanged active regressions
passed without duplicated SQLite cases. Root verified5 source hashes/14 evidence
hashes/three XML files; integrated Ruff and configured mypy1,460 passed.
[Exact results and limits](inlet-google-owner-retained-slice-20261011.md).

The retained helper returns validated immutable catalog/source values, preserving
original input links and opaque scalar commitments. Existing active full-source
validation and public None-returning receipt validation remain intact. Clean-root
checks do not claim sticky flush detection or natural-expiry qualification. Expected
Connection-fault cleanup warnings and repaired test-only mypy findings are retained.
No document field, registry, generation, service or UI activation in this slice.
Next is reviewed slice2 genuine V6 pure document/composition; runtime remains gated.
R01/R02, incomplete Q09 and six human judgments remain open. All work local only.

## 2026-10-11 — Coherent Manual Flow And Genuine Pure V6

The reviewed [customer milestone](design/q06-manual-owner-flow-milestone.md)
(`beccf61`) binds remaining work to one existing-portal journey, using the already
reserved V6 pair. The [portal contract](design/google-budget-owner-portal-interface-v1.md)
(`bc2c56b`) distinguishes explicit empty V6 hypotheses from absent legacy inputs,
shows all affected members, and labels the editable value a requested hypothesis.
No additional policy generation or default switch is proposed.

Pure composition integrated `e8c7600` (author `18027ee`), independently CLOSED.
234 distinct passing cases comprise61new and173legacy across preserved attempts;
the final compatibility cohort177 passed15.850s. Three earlier failures are retained:
two synthetic fixture inconsistencies and a real Meta optional-schedule mismatch.
The narrow reviewed fix permits absent native Meta schedules only in their exact
settings shape; required reporting times remain strict. Root16source/21evidence
hashes/fiveXML verified; integrated Ruff and configured mypy1,467 passed.
[Exact source/result limits](inlet-google-owner-v6-pure-20261011.md).

New full linked-catalog fields, genuine composer and checked V6 serialization are
pure only. Old V1–V5 refusals and output goldens remain; no registry/service/SQL/UI
activation or authority-window qualification is claimed. Retained current/history
implementation now proceeds under reviewed `0ea8854`, reusing the existing receipt
loader; service/registry/save integration planning is separate with shared ports
frozen first. Next acceptance is complete private API wiring, then the reviewed
portal and one frozen integration milestone.

A [bounded diagnostic census](design/q09-next-milestone-helper-census-v1.md) is
source-reviewed for that later new milestone; it has not run. R01/R02 remain
unresolved, original Q09 incomplete, and six human judgments open. No unchanged
probe retry, live/remote/release action or external sharing occurred.

## 2026-10-11 — Original-Receipt V6 Current And Historical Reads

Integrated independently reviewed `b336e9b` as `fca7178` on the local
`codex/inlet-w1-followup` branch. Exact V6 retained reads now validate original
authenticated owner input receipts, full linked catalogs, owner proof and complete
reporting/commerce/creative dependencies. Public V5 entry points retain their prior
policy and error boundaries. No service registration, default change or advertising
authority is introduced by this package.

[Package ledger](inlet-owner-review-retained-20261011.md) records 26 distinct passing
cases: 24 SQLite/PostgreSQL retained-component cases and two direct wrapper
regressions. The overlapping smoke is not added to the total. The initial immutable
receipt UPDATE fixture failure is preserved; only its fault-injection seam changed.
Two warnings came from deliberate Connection transaction replacement cleanup.
Root independently checked all 10 source hashes, 14 evidence hashes and three XML
reports; independent review CLOSED. Root whole Ruff and configured no-path mypy
passed (1470 files). Evidence is local under
`/workspace/inlet-evidence/20261011/owner-review-retained/`.

The fixture performs genuine discovery/input/media/read/composition but explicitly
stores the resulting version/dependencies for retained-port checks. This does not
qualify actual generation/save or the final five-second authority interval. Next:
reviewed exact-V6 service integration with 13 disjoint actual API cases per database,
then the existing customer portal. R01/R02, human usefulness judgments and all
remote/live/release/sharing holds remain unchanged.

## 2026-10-11 — Restricted Retained Context Validation

Integrated independently reviewed `fb2d864` as `788edfc`. The private retained context
now supports an additional exact-policy restriction while always validating the
whole document. The two owner entry points consume that checked result instead
of immediately validating the same document twice before any database access.
All subsequent receipt, source, transaction, privacy and authority checks remain.

[Package ledger](inlet-owner-context-restriction-20261011.md) records30distinct
passing cases:16pure/wrapper and14affected retained cases acrossSQLite/PostgreSQL.
The final14-case pure rerun overlaps that count. Initial static findings are retained;
final changes were an equivalent short-circuit style repair and test-only typing.
Root verified4source/14evidence hashes and3XML reports, then wholeRuff and configured
no-path mypy passed1471files. Local evidence: `owner-context-restriction/`.

This validates the narrow context behavior, not generation latency or R03 resolution.
The service/storage branch is assembling this commit with the independently reviewed
canonical-once storage-pair change for16pure and28actualAPI checks on changed source.
Service remains unintegrated pending that qualification. All live/remote/release
holds, human usefulness gaps and original reliability findings remain explicit.

## 2026-10-11 — Local Owner Service And Customer Flow Integration

Successor service qualification is now integrated. The two-file owner-domain
derivation refactor retained strict public validation/serialization and fresh
checks across SQL boundaries; its pure cohort passed194 cases. The actual service
matrix covers all28 planned IDs across disjoint runs: six initial SQLite passes,
one separately corrected substitution-fixture pass, and21 remaining SQLite/PG
passes. The original invalid-fixture failure and earlier authority-expiry failures
are preserved. This is not one28-pass run or a measured latency margin.

[Service integration ledger](inlet-owner-service-integration-20261011.md) records
code head1e2d1da, source identity, root Ruff/mypy1479 and independently verified
source/evidence/artifact hashes. Default V3, legacy V5 boundaries, original-session
receipts, atomic rollback and no advertising authority remain enforced.

The [browser prerequisite package](inlet-owner-browser-prerequisites-20261011.md)
integrated87d052d:29 fixed-route diagnostic cases plus four genuine complete/partial
acquisition fixtures passed. Root Ruff/mypy1481 passed. These are not TLS journeys.

The [customer UI package](inlet-google-owner-review-portal-20261011.md) integrated
9952ff8 (integration ledger7c60866). Three distinct Chromium checks passed across
two runs: owner component and legacy document display, then actual controller
compatibility. The UI preserves primitive input projection, exact amounts and
full-member provenance, asynchronous invalidation, saved-proof honesty and no
silent legacy-input upgrade. Root Ruff/mypy1483 passed;14-source/19-evidence
hashes were independently verified. No existing passing cohort was repeated just
for source-identical integration.

Next is the source-reviewed four-case authenticated original-session TLS matrix:
SQLite complete/partial then PostgreSQL complete/partial, using actual browser
target reads, discovery, input submission, generation, history and export. Its
execution remains separately gated on an exact frozen source/manifest and stops
at the first unexpected failure. No customer browser/API journey is claimed yet.
All original incident, human usefulness, remote/hosted-CI, live, merge and deployment
holds remain unchanged. Public website work stays owner-managed.
