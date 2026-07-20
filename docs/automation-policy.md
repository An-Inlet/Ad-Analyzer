# Project-wide Automation Policy

This policy governs every remaining Denticode Ads Optimizer phase through production-ready v1.

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
