# Definition of Done

## PR-level gates

- Approved scope implemented.
- Explicit exclusions respected.
- Focused tests pass.
- Full tests pass.
- PostgreSQL tests pass or are clearly marked as environmental skips outside CI.
- Migrations safely upgrade.
- Reversible migrations are tested only on disposable PostgreSQL.
- Ruff passes.
- mypy passes.
- Diff check passes.
- No unexplained skips.
- Account isolation is verified.
- Privacy impact is documented.
- Security impact is documented.
- Google Ads read/write impact is documented.
- No unresolved P1/P2 findings.
- Required review threads resolved.
- CI green.
- Human approval present when required.

## Production-ready v1 gates

- Analytics works on synchronized data.
- Recommendations are deterministic and reviewable.
- All live writes require approved controls.
- Execution is idempotent and audited.
- Rollback or compensating procedures exist.
- Secrets are externally managed.
- PostgreSQL is managed and backed up.
- Monitoring and alerting are active.
- Restore procedure is tested.
- Production deployment is documented.
- Operator runbook exists.
- Incident response exists.
- Security and privacy review is complete.
- Release approval is recorded.
