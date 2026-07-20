# Decision Register

Each decision uses: decision ID, affected phase, status, blocking/non-blocking, options, recommended default, rationale, final human decision, and decision date.

| Decision ID | Affected phase | Status | Blocking | Available options | Recommended default | Rationale | Final human decision | Decision date |
|---|---|---|---|---|---|---|---|---|
| DR-001 analytics thresholds | Phase 8 | Proposed | Blocking for findings | Conservative fixed thresholds; operator-configurable thresholds; learned thresholds | Conservative fixed thresholds | Deterministic and auditable first | Pending | TBD |
| DR-002 metric availability by entity level | Phase 8 | Proposed | Blocking | Strict required metrics; nullable availability state; per-entity matrix | Per-entity availability matrix | Prevents confusing zero with unavailable data | Pending | TBD |
| DR-003 search-term display and redaction | Phase 8 | Proposed | Blocking | Hide all terms; masked terms; role-gated exact text | Masked by default with role-gated exact text | Search-term text is sensitive | Pending | TBD |
| DR-004 finding and recommendation severity policy | Phases 8-9 | Proposed | Blocking | Low/medium/high; numeric score; hybrid | Low/medium/high with rationale | Review queues need deterministic sorting | Pending | TBD |
| DR-005 executable recommendation types | Phase 11 | Proposed | Blocking | None; budget only; bid/status/search-term negatives; allowlist | Start with none until Phase 11 approval | Avoid premature writes | Pending | TBD |
| DR-006 Google Ads mutation allowlist | Phase 11 | Proposed | Blocking | No mutations; narrow allowlist; broad operator-selected | Narrow allowlist after dry-run proof | Limits blast radius | Pending | TBD |
| DR-007 human approval requirements | Phases 10-11 | Proposed | Blocking | One approver; two approvers; risk-based | One authenticated approver plus audit event | Balances safety and operability | Pending | TBD |
| DR-008 account allowlists | Phase 11 | Proposed | Blocking | Global disabled; account allowlist; campaign allowlist | Account allowlist plus kill switch | Prevents accidental broad execution | Pending | TBD |
| DR-009 stale recommendation expiration | Phase 11 | Proposed | Blocking | 24h; 72h; configurable | 72h default with revalidation | Avoids acting on stale metrics | Pending | TBD |
| DR-010 rollback expectations | Phase 11 | Proposed | Blocking | Manual instructions; compensating actions; automatic rollback | Documented compensating actions first | Ads APIs may not support true rollback | Pending | TBD |
| DR-011 hosting platform | Phase 12 | Proposed | Blocking | Render; Fly.io; AWS; GCP; Azure | Human-selected managed platform | Impacts secrets, workers, networking | Pending | TBD |
| DR-012 managed PostgreSQL provider | Phase 12 | Proposed | Blocking | Platform DB; RDS; Cloud SQL; Neon | Same vendor as hosting if compliant | Reduces operational complexity | Pending | TBD |
| DR-013 secrets manager | Phase 12 | Proposed | Blocking | Platform secrets; cloud secrets manager; 1Password integration | Managed secrets with rotation support | No secrets in repo or logs | Pending | TBD |
| DR-014 monitoring and alert destinations | Phase 12 | Proposed | Blocking | Email; Slack; PagerDuty; platform alerts | Human-selected alert channel | Alerts must reach operators | Pending | TBD |
| DR-015 backup retention | Phase 12 | Proposed | Blocking | 7 days; 30 days; 90 days | 30 days plus restore test | Practical recovery window | Pending | TBD |
| DR-016 production release criteria | Phase 12 | Proposed | Blocking | Checklist only; sign-off issue; release approval record | Recorded human approval with checklist | Auditable release gate | Pending | TBD |
