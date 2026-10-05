# Project-wide Automation Policy

This policy governs every remaining Ad Analyzer phase through production-ready v1.

## Branch and PR rules

- Every branch starts from latest `main`.
- Never write directly to `main`.
- Keep only one dependent product PR open at a time.
- Do not start a later dependent PR until the preceding dependency is merged.
- Use squash merge only after required approval and checks pass.
- Do not bypass required checks, rulesets, review requirements, or branch protections.

## Automated fix limits

- Codex may automatically fix only concrete CI failures and P1/P2 review findings.
- Automated fixes may not broaden scope or add unapproved product behavior.
- Codex must stop for product, privacy, security, or architecture decisions.

## Security, privacy, and ads safety

- Do not print, store, or commit secrets.
- Do not expose sensitive search-term text in output, logs, screenshots, or broad test failures.
- No Google Ads writes before Phase 11 controlled execution.
- No live writes without explicit approved policy and human authorization.
- No production deployment without a human release gate.
- No destructive migration against local development, staging, or production; downgrade tests run only on disposable PostgreSQL.

## Completion rule

- Stop automatically after the production-ready v1 definition is satisfied and produce the final readiness report.

## User-approved buildout-only integration exception (2026-07-20)

For the remaining Ad Analyzer v1 buildout, the user approved a single long-running integration branch, `codex/complete-ad-analyzer-buildout`, with sequential phase commits and one final pull request against `main` after the complete analyzer is ready for human review. This exception does not authorize live operations, production deployment, self-approval, final merge, credential handling, weakened CI, weakened account isolation, weakened migration safety, weakened privacy protections, or weakened Google Ads mutation safeguards.

## User-approved Inlet foundation exception (2026-10-05)

The owner explicitly approved Google Cloud Identity Platform with PostgreSQL-backed
revocable customer sessions, and sequential B02–B04 commits on the existing B01
branch `codex/inlet-b01-conversion-diagnostics` and draft PR #64 before its merge.
This scoped exception permits dependent foundation work in that PR; it does not
extend beyond B04 or authorize provider provisioning, credentials, permission
expansion, live customer-account changes, advertising spend, self-approval, merging,
or deployment. Human review, merge and production-release gates remain required.
The public website is now entirely owner-managed and outside this work.

## User-approved B05 extension (2026-10-05)

At 15:46:40 UTC the owner approved extending the same PR #64 integration exception
through B05. Approved measurement: Shopify merchandise sales after discounts and
refunds, excluding tax/shipping; refunds on processing date; store-local calendar
months explicitly confirmed in goals; 13 months of minimal measurement history
with deletion requirements preserved. This does not authorize B06 implementation,
merge/deployment/live access, or the unanswered CRM gateway architecture proposal.
