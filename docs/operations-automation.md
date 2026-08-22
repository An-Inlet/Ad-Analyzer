# Production operations automation

This automation can perform a read-only audit of the Denticode production deployment every hour and can also be run manually from GitHub Actions. The scheduled audit is disabled by default; manual `workflow_dispatch` runs remain available.

## Dashboard control

The platform administrator dashboard exposes **GitHub hourly production audit** as a master toggle. It synchronizes the repository variable `PRODUCTION_OPERATIONS_AUDIT_ENABLED`; only the literal value `true` allows scheduled audit jobs to run. Missing or false values fail closed, and manual audit runs are unaffected.

Configure `AD_ANALYZER_GITHUB_CONTROL_TOKEN` from an external secret and scope it only to this repository with repository **Variables: write** permission. `AD_ANALYZER_GITHUB_CONTROL_REPOSITORY` defaults to `Konner-An-Inlet/Denticode-Ads-Optimizer`. The application never stores the token in the database or logs GitHub response bodies. If the external update fails, the dashboard does not record the requested state change.

The platform administrator dashboard also exposes **All Ad Analyzer data syncs** as a database-backed master toggle. Turning it off makes every new scheduled, one-shot, or manually invoked Google Ads sync cycle exit successfully before acquiring the sync lock, creating a job run, or contacting Google Ads. Existing synchronized data remains available, and nightly or weekly analysis can continue according to their own controls. A sync that was already running when the control changed is allowed to finish safely; the next cycle observes the new state.

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
