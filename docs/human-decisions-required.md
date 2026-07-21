# Human decisions required

Last refreshed: 2026-07-20

The approved defaults unblock provider-neutral, non-production, and fail-closed implementation work while preserving human stops for live advertising activity, production credentials, paid infrastructure, and release approval. The remaining decisions below still require explicit human approval before live operation or production activation.

## Blocking decisions

| Decision | Blocks roadmap units | Required human input |
|---|---|---|
| Phase 11.3 production mutation enablement | Live portions of 11.3, 11.4 | Live Google Ads mutations are not approved; only mocked adapters, dry-run planning, policy validation, stale checks, rollback models, execution audit structures, docs, and fail-closed tests may proceed. |
| Google Ads mutation allowlist | Live portions of 11.3, 11.4 | Keep live mutation allowlist empty; mocked test-only mutation types may be documented without enabling live writes. |
| Live account allowlists | Live portions of 11.3, 11.4 | No production customer account is approved; keep repository defaults empty and use placeholders only. |
| Execution kill switch disablement | Live portions of 11.3, 11.4 | Keep the kill switch enabled by default; visibility, alerts, tests, and operator procedures may proceed. |
| Stale recommendation and rollback policies | 11.3, 11.4 | Finalize expiration windows and compensating-action expectations before live execution. |
| Hosting platform | Production activation in 12.1, 12.2 | Use provider-neutral containerized reference architecture; do not select, purchase, or activate a paid provider. |
| Managed PostgreSQL provider | Production activation in 12.2 | Document PostgreSQL-compatible managed database requirements and placeholders; do not connect to production. |
| Secrets manager | Production activation in 12.2 | Use environment-variable references and external secret-manager placeholders only. |
| Monitoring and alert destinations | Production activation in 12.3 | Implement provider-neutral monitoring hooks and placeholder destinations only. |
| Backup retention | 12.3 production activation | Use approved documented defaults: daily logical backups, 30-day daily retention, 12-month monthly retention, pre-migration backup, and quarterly disposable-PostgreSQL restore tests. |
| Production release approval | 12.4 | Record final human release approval after validation and reviews. |

## Permanent constraints

- Do not commit credentials, `.env` files, OAuth tokens, private keys, service-account files, or production database URLs.
- Do not perform live Google Ads writes or campaign changes without explicit approval.
- Keep `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false` and `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true` unless a human-approved controlled execution process changes them outside Git.
- Do not deploy production infrastructure or spend advertising/infrastructure funds from automation.
