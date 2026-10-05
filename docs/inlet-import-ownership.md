# Inlet Import Ownership (B04)

`WorkspaceIntegration.id` is the canonical connection ID. Every advertising import
uses `(workspace_id, connection_id, account_id, platform)` and verifies the active
workspace, connection, provider and account before collection and persistence.
Composite foreign keys prevent cross-workspace account/job bindings. Import locks
include the complete tuple; downstream analysis failure does not repeat a successful
import. Customer membership remains separate from operator authorization (B02).

Meta and Shopify retain their existing native connection and synchronization
architecture. Native rows bind to the canonical registry; disconnect revokes that
registry entry. Migration 0022 backfills only ownership already stored on native
rows. Registry markers make downgrade/re-upgrade safe without restoring revoked
connections. Historical Google account/job connection IDs stay nullable: migration
cannot infer their credentials or owner. New Google imports require explicit scope.

## Deployment Preparation

This is an implementation record, not deployment authorization. No provider setup,
secret creation, IAM change, queue change or live import was performed.

1. Pause import producers/consumers and back up the database through normal release
   procedures. Apply migrations through 0022 and review existing native ownership.
   Migration aborts on conflicting ownership rather than assigning another tenant.
2. For each operator-managed Google collector profile, explicitly bind its existing
   advertising account to a same-workspace `google_ads` registry connection. Configure
   `INLET_GOOGLE_ADS_WORKSPACE_ID`, `INLET_GOOGLE_ADS_CONNECTION_ID`,
   `INLET_GOOGLE_ADS_ACCOUNT_ID` and `INLET_GOOGLE_ADS_CREDENTIALS_REFERENCE`.
   The credential reference must equal that connection's `secret_manager_reference`;
   the configured Google customer ID must equal the owned account's external ID.
   These identifiers do not create OAuth credentials or customer onboarding. Existing
   deployment credentials remain operator-managed; customer OAuth is later backlog.
3. Give each CRM connection a pinned Secret Manager version reference and authorized
   workload access through separately reviewed deployment configuration. No global
   webhook-secret fallback is accepted. The managed secret reader uses ADC and never
   logs secret contents. Missing/unavailable secrets fail closed.
4. Switch CRM producers to
   `POST /v1/crm/workspaces/{workspace_id}/connections/{connection_id}/events`.
   HMAC SHA-256 signs `v2:{workspace_id}:{connection_id}:{timestamp}.` followed by
   the exact request-body bytes, using that connection's secret. Retain the existing
   timestamp/signature headers. Canonical connection IDs are not native CRM row IDs.
   The gateway emits version 2 messages with explicit workspace, connection and
   provider; duplicate event IDs are independent between connections.
5. Configure bounded Pub/Sub retry and a dead-letter destination before resuming.
   Legacy unscoped messages and revoked/mismatched ownership are rejected, never
   assigned to a default workspace. A sanitized digest/reason index is recorded in
   `import_rejections`; raw payloads are not copied into the application database.
   Operators must investigate/replay through a correctly scoped producer. The index
   does not itself provision a dead-letter queue or retention policy.
6. Resume with read-only smoke checks under normal deployment approval. Verify each
   customer's records and failed/revoked imports before expanding rollout.

## Acceptance Evidence

Tests exercise two workspaces sharing provider-side IDs, two active CRM connections
in one workspace, route-bound signatures, actual push ingress and worker persistence,
duplicates, concurrent PostgreSQL claims, revoke-after-enqueue, missing/mismatched
scope, successful imports followed by failed analysis, and migration replay preserving
revocation. SQLite and disposable PostgreSQL tests use synthetic collectors and
secret readers. Provider APIs and production queues remain unverified.
