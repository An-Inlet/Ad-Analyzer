# Private CRM integration gateway (Phase 1)

> Historical deployment design: B04 replaces the legacy ingress with a scoped v2
> route and per-connection verification. The existing publish-only Terraform is
> not ready for that SQL-backed lookup. See [B04 deployment decision and blockers](inlet-import-ownership.md#review-repairs-and-remaining-crm-infrastructure-decision)
> before using the historical setup or payload examples below. No permission
> expansion or deployment has been approved by this implementation change.

## Architecture and security boundary

The public API Gateway exposes only `GET /health` and `POST /v1/crm/events`. It invokes an authenticated, private Cloud Run gateway. The gateway verifies the CRM HMAC, applies a strict non-PHI allowlist, and publishes normalized JSON to a dedicated Pub/Sub topic. A separate private worker consumes the subscription, persists events idempotently, and updates attribution/lifecycle state. The analyzer API, dashboard, database, recommendations, and advertising credentials are not routed through API Gateway.

The four service accounts are intentionally separate. API Gateway can invoke only the gateway; the gateway can read only its HMAC secret and publish to the CRM topic; Pub/Sub uses a dedicated push authenticator to invoke the worker; and the worker can read only its database secret. No advertising credential or write role is granted. Cloud Run direct invocation has no `allUsers` binding. Payloads and identifiers are omitted from application logs.

Service accounts use a shorter prefix than the other resources so their IDs always fit Google's 30-character limit. For the default `production` environment, Terraform generates these exact, stable account IDs:

- `aa-prod-crm-gateway`
- `aa-prod-crm-worker`
- `aa-prod-crm-push`
- `aa-prod-crm-api-gw`

The `development`, `staging`, and `production` environment names are abbreviated to `dev`, `stg`, and `prod` respectively. Other valid environment names remain unchanged; the environment validation reserves those abbreviations to avoid collisions between, for example, `production` and `prod`.

## Event contract

Send JSON with `event_id`, `event_type`, `occurred_at` (timezone required), and `crm_lead_id`. Optional allowed fields are `crm_opportunity_id`, non-negative `value`, ISO uppercase `currency`, `analytics_pseudonymous_id`, `gclid`, `gbraid`, `wbraid`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, and HTTP(S) `landing_page`. Supported types are `lead_created`, `appointment_scheduled`, `lead_qualified`, `proposal_sent`, `sale_won`, `sale_lost`, `sale_cancelled`, and `revenue_adjusted`. Unknown fields are rejected. `analytics_pseudonymous_id` must be an opaque 8-128 character identifier containing only letters, digits, dots, underscores, colons, or hyphens; it must not be an email address or another direct identifier. Never send names, email, phone, treatment, diagnosis, notes, patient data, or other PHI.

Fake example:

```json
{"event_id":"evt_fake_001","event_type":"lead_created","occurred_at":"2026-07-29T12:00:00Z","crm_lead_id":"lead_fake_001","analytics_pseudonymous_id":"practice-pseudo-001","gclid":"fake-click-id","utm_source":"google","utm_campaign":"fake-campaign","landing_page":"https://example.invalid/fake"}
```

## HMAC signing and CRM integration

1. Serialize the exact JSON bytes that will be transmitted (do not reformat after signing).
2. Set `X-AnInlet-Timestamp` to the current Unix epoch seconds.
3. Compute lowercase hex HMAC-SHA256 with the shared secret over `timestamp + "." + raw_body`.
4. Send that digest (or `sha256=<digest>`) as `X-AnInlet-Signature` and the matching payload ID as `X-AnInlet-Event-Id`.
5. Treat `202` as accepted. Retry `503` with exponential backoff using the same event ID and body. Do not retry `401` or `422` until corrected. A `409` means that event ID was already accepted.

Keep clocks synchronized; requests more than five minutes from gateway time are rejected. Event IDs must be stable across retries.

## Local testing and configuration

Install Python 3.12 dependencies and run `pytest`, `ruff check .`, and `mypy`. Tests use fake publishers and no network or credentials. Required runtime variables are:

- `AD_ANALYZER_CRM_WEBHOOK_SECRET` (Secret Manager injection only)
- `AD_ANALYZER_CRM_PUBSUB_PROJECT_ID`
- `AD_ANALYZER_CRM_PUBSUB_TOPIC_ID`
- `CLOUD_SQL_CONNECTION_NAME`, `DATABASE_USER`, and `DATABASE_NAME` for the worker
- `DATABASE_PASSWORD` for the worker (existing Secret Manager secret injection only)

For local manual calls only, place a disposable secret in an untracked `.env`, start `uvicorn app.main:app`, and generate the headers using the process above. Never commit that file.

## Infrastructure and secrets

Terraform in `infra/gcp` targets project `totemic-alchemy-502420-p4`. Cloud Run, Cloud SQL, and the other existing regional resources remain in `us-west1`. API Gateway is deployed separately in `us-west3` because API Gateway does not support `us-west1`; the `us-west3` gateway may proxy requests to the existing Cloud Run gateway backend in `us-west1`. Its partial GCS backend must be initialized by an operator with bucket `totemic-alchemy-502420-p4-terraform-state` and prefix `ad-analyzer/crm-production`; the backend credentials are not stored in this configuration. Both `DATABASE_PASSWORD` and `ad-analyzer-production-crm-webhook-hmac` are existing Secret Manager containers. Secret versions are created through an approved out-of-band process. Terraform neither creates secret versions nor reads or stores secret payloads in its state. The worker connects to the existing Cloud SQL instance through its `/cloudsql` Unix-socket mount; the public gateway has no database configuration or Cloud SQL permission.

Review-only command sequence (do not run `apply` from automation):

```sh
cd infra/gcp
terraform init -backend-config='bucket=totemic-alchemy-502420-p4-terraform-state' -backend-config='prefix=ad-analyzer/crm-production'
terraform fmt -check -recursive
terraform validate
terraform plan -var='gateway_image=us-west1-docker.pkg.dev/PROJECT/REPOSITORY/GATEWAY@sha256:DIGEST' -var='worker_image=us-west1-docker.pkg.dev/PROJECT/REPOSITORY/WORKER@sha256:DIGEST' -out=review.tfplan
# Only an explicitly authorized human may later run: terraform apply review.tfplan
```

Before a future deployment, publish reviewed immutable images, add secret versions manually, insert the CRM connection with only its secret reference, apply the Alembic migration, and configure the CRM with the API Gateway hostname. Configure Pub/Sub's service agent permissions for dead-letter forwarding if the plan identifies they are not already present.

## Rollback

Stop CRM sends, retain the subscription to avoid message loss, and route traffic away from the API Gateway. Roll the Cloud Run revision back to the prior immutable image. Repair/replay dead-lettered messages after validation. Database downgrade is destructive and should occur only after a reviewed backup and confirmation no CRM records must be retained. Infrastructure destruction is a separate, explicitly approved operator action; secret versions and audit logs should follow the organization's retention policy.
