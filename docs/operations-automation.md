# Production operations automation

This automation performs a read-only audit of the Denticode production deployment every hour and can also be run manually from GitHub Actions.

## Controls checked

The audit verifies, without reading secret payloads or changing cloud resources:

- Cloud Run IAP, traffic, revision readiness, maximum instances, and public IAM exposure.
- Exact dashboard IAP and application email allowlists.
- Google Ads write disablement, execution kill switch, and empty mutation/account allowlists.
- Web, sync, and migration image parity.
- Numeric Secret Manager version pinning in every runtime.
- Secret-level access matrices and absence of project-wide secret accessors.
- No user-managed service-account keys.
- Scheduler target, OAuth identity, cadence, timezone, and recent successful sync execution.
- Job-specific scheduler invocation permission.
- Cloud SQL connector enforcement, encryption, backups, point-in-time recovery, deletion protection, storage auto-increase, and absence of authorized networks.
- Resource-scoped deployer `actAs` grants.

The workflow writes a sanitized JSON artifact and GitHub Actions summary. A failed control opens or updates a single GitHub issue named `Production operations audit failed`. A later successful audit closes that issue automatically.

## One-time bootstrap

The workflow uses GitHub Actions OpenID Connect and Google Cloud Workload Identity Federation. It does not create or store a service-account JSON key.

From an authenticated PowerShell session at the repository root:

```powershell
.\scripts\bootstrap_github_operations.ps1
```

The script:

1. Enables the IAM Credentials, Security Token Service, and IAM APIs.
2. Creates or updates a repository-restricted workload identity pool and provider.
3. Creates `denticode-github-ops` with read-only audit roles.
4. Allows only this repository's `main` branch to impersonate that account.
5. Creates the required GitHub repository variables automatically with `gh variable set`.

The bootstrap requires active `gcloud` and GitHub CLI authentication. It is idempotent and creates no service-account key.

## Manual verification

After merging the pull request and running the bootstrap, open GitHub Actions and run **Production Operations Audit** with `workflow_dispatch`. The first run should finish successfully and produce a `production-audit.json` artifact.

## Safety boundaries

- The audit does not execute the migration or sync jobs.
- The audit does not retrieve Secret Manager values.
- The audit does not alter Cloud Run, Cloud SQL, IAM, Scheduler, or Google Ads.
- GitHub receives short-lived federated credentials only.
- The production write-disable and kill-switch controls are checked on every run.
