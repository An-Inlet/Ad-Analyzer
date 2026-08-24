# Platform naming and production cutover

## Naming contract

Ad Analyzer is the platform and repository identity. Client names appear only inside their own
workspace, account, measurement, and integration records.

| Surface | Neutral platform identifier |
| --- | --- |
| Product and dashboard | `Ad Analyzer` |
| GitHub repository | `Konner-An-Inlet/Ad-Analyzer` |
| Environment variables | `AD_ANALYZER_*` |
| Cloud Run web service | `ad-analyzer-web` |
| Cloud Run sync job | `ad-analyzer-sync` |
| Cloud Run migration job | `ad-analyzer-migration` |
| Cloud Scheduler job | `ad-analyzer-sync-hourly` |
| Cloud SQL instance | `ad-analyzer-postgres` |

The existing client workspace slug, database records, advertising-account names, measurement
contracts, and CRM configuration are client data. They are not renamed by the platform cutover.

## Why the web address needs a new service

A Cloud Run service name is part of its generated hostname and is not an application-level title.
Removing a client name from the browser address therefore requires a parallel
`ad-analyzer-web` service rather than only changing the HTML. In the current project and region,
the expected generated dashboard URL is:

`https://ad-analyzer-web-89443799388.us-west1.run.app/dashboard`

Confirm the authoritative URL returned by Cloud Run after deployment before distributing it.

## Parallel, rollback-safe sequence

1. Merge the neutral naming changes after CI passes.
2. Create or update the neutral GitHub Workload Identity provider and service accounts with
   `scripts/bootstrap_github_operations.ps1`. No service-account key is created.
3. Build one reviewed immutable image and deploy it to the new web, sync, and migration resources.
   Bind the existing Secret Manager versions by reference; never copy or print secret values.
4. Run the new migration job against the existing database, then deploy the new web service with
   the same workspace and account data.
5. Configure IAP and the application administrator allowlist on the new service. Verify
   `/health`, `/ready`, dashboard authentication, workspace isolation, and read-only behavior.
6. Point the neutral scheduler at the neutral sync job and verify a successful manual sync and
   production operations audit.
7. Switch operator bookmarks and any approved external routing to the neutral dashboard URL.
8. Keep the previous service and jobs available but unscheduled for a defined rollback window.
   Roll back routing and the scheduler target if the neutral revision fails validation.
9. Retire the previous platform resources only after the rollback window closes and logs,
   database backups, IAM, and scheduled execution have been reviewed.

Do not enable advertising writes as part of this naming change. The write-disable, execution kill
switch, empty allowlists, IAP boundary, and read-only audit controls remain unchanged.

## Repository guardrail

`tests/test_platform_naming.py` protects platform-facing files from reintroducing the former
product, repository, environment-variable, branch, or cloud-resource identifiers. It deliberately
does not reject client-specific workspace and account records.
