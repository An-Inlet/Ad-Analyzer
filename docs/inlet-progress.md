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
- `scripts/validate.sh Full` with guarded disposable PostgreSQL: running final
  gates; primary pytest result **600 passed, 6 skipped**. The six skips require
  PowerShell, which is unavailable on this Linux environment.
- Ruff: passed. Mypy: passed, 159 source files. Whitespace diff check: passed.
- PostgreSQL integration tests and migration upgrade/downgrade/upgrade: passed.
- ReadOnly: **75 passed**. Security: **98 passed, 1 skipped** (PowerShell).
- Privacy: **14 passed**. Final Focused gate pending completion.
- Full log: `/tmp/inlet-validation-full.log` in this execution environment.

PR and CI status will be recorded after pushing. Nothing is live-verified or
deployed. No new migration is introduced by B01.

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
