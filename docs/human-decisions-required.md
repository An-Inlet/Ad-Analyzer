# Human decisions required

Last refreshed: 2026-07-20

The automated buildout has completed the technically implementable roadmap work that can be performed safely without live advertising changes, production infrastructure, credentials, or release approval. The remaining roadmap units require explicit human decisions before implementation or activation.

## Blocking decisions

| Decision | Blocks roadmap units | Required human input |
|---|---|---|
| Phase 11.3 production mutation enablement | 11.3, 11.4 | Decide whether live Google Ads mutations are permitted at all. |
| Google Ads mutation allowlist | 11.3, 11.4 | Select exact mutation types, if any, that may be implemented. |
| Live account allowlists | 11.3, 11.4 | Provide approved production account allowlists through external configuration, not this repository. |
| Execution kill switch disablement | 11.3, 11.4 | Approve any production process for setting `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=false`. |
| Stale recommendation and rollback policies | 11.3, 11.4 | Finalize expiration windows and compensating-action expectations before live execution. |
| Hosting platform | 12.1, 12.2 | Select the production hosting platform. |
| Managed PostgreSQL provider | 12.2 | Select the managed PostgreSQL provider and backup responsibility. |
| Secrets manager | 12.2 | Select the external secrets system; do not put secret values in Git. |
| Monitoring and alert destinations | 12.3 | Select alert destinations and escalation expectations. |
| Backup retention | 12.3 | Select retention period and restore-test cadence. |
| Production release approval | 12.4 | Record final human release approval after validation and reviews. |
| Denticode measurement contract | Improvement step 2 activation | Confirm the optimization outcome, CRM source of truth, attribution window, outcome-maturity window, customer-value horizon, and whether view-through attribution remains disabled. |
| Unified outcome data source | Improvement step 3 activation | Approve the read-only GA4 property and BigQuery export dataset, the shared opaque `analytics_pseudonymous_id` contract, permitted aggregate dimensions and retention, and the operating owner before any production feed is configured. |

## Permanent constraints

- Do not commit credentials, `.env` files, OAuth tokens, private keys, service-account files, or production database URLs.
- Do not perform live Google Ads writes or campaign changes without explicit approval.
- Keep `DENTICODE_GOOGLE_ADS_WRITE_ENABLED=false` and `DENTICODE_GOOGLE_ADS_EXECUTION_KILL_SWITCH=true` unless a human-approved controlled execution process changes them outside Git.
- Do not deploy production infrastructure or spend advertising/infrastructure funds from automation.
