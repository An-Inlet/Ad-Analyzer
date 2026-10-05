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
