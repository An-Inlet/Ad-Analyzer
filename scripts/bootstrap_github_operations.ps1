[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$ProjectId = "totemic-alchemy-502420-p4",
    [string]$ProjectNumber = "89443799388",
    [string]$Repository = "Konner-An-Inlet/Ad-Analyzer",
    [string]$PoolId = "github-actions",
    [string]$ProviderId = "ad-analyzer-operations",
    [string]$ServiceAccountId = "ad-analyzer-github-ops"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Invoke-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command exited with code $LASTEXITCODE"
    }
}

function Test-Native {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Command @Arguments *> $null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

foreach ($command in @("gcloud", "gh")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $command"
    }
}

if (-not (Test-Native gh auth status --hostname github.com)) {
    throw "GitHub CLI is not authenticated. Run: gh auth login"
}

$activeProject = (& gcloud config get-value project 2>$null).Trim()
if ($activeProject -ne $ProjectId) {
    Write-Host "Setting active Google Cloud project to $ProjectId"
    Invoke-Native gcloud config set project $ProjectId
}

$account = (& gcloud auth list --filter="status:ACTIVE" --format="value(account)").Trim()
if ([string]::IsNullOrWhiteSpace($account)) {
    throw "No active gcloud account. Run: gcloud auth login"
}
Write-Host "Using gcloud account: $account"

Invoke-Native gcloud services enable `
    iamcredentials.googleapis.com `
    sts.googleapis.com `
    iam.googleapis.com `
    --project=$ProjectId

$poolExists = Test-Native gcloud iam workload-identity-pools describe $PoolId `
    --project=$ProjectId `
    --location=global

if (-not $poolExists) {
    Invoke-Native gcloud iam workload-identity-pools create $PoolId `
        --project=$ProjectId `
        --location=global `
        --display-name="GitHub Actions"
}

$providerExists = Test-Native gcloud iam workload-identity-pools providers describe $ProviderId `
    --project=$ProjectId `
    --location=global `
    --workload-identity-pool=$PoolId

$attributeMapping = "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref"
$attributeCondition = "assertion.repository=='$Repository' && assertion.ref=='refs/heads/main'"

if (-not $providerExists) {
    Invoke-Native gcloud iam workload-identity-pools providers create-oidc $ProviderId `
        --project=$ProjectId `
        --location=global `
        --workload-identity-pool=$PoolId `
        --display-name="Ad Analyzer production operations" `
        --issuer-uri="https://token.actions.githubusercontent.com" `
        --attribute-mapping=$attributeMapping `
        --attribute-condition=$attributeCondition
}
else {
    Invoke-Native gcloud iam workload-identity-pools providers update-oidc $ProviderId `
        --project=$ProjectId `
        --location=global `
        --workload-identity-pool=$PoolId `
        --attribute-mapping=$attributeMapping `
        --attribute-condition=$attributeCondition
}

$serviceAccountEmail = "$ServiceAccountId@$ProjectId.iam.gserviceaccount.com"
$serviceAccountExists = Test-Native gcloud iam service-accounts describe $serviceAccountEmail `
    --project=$ProjectId

if (-not $serviceAccountExists) {
    Invoke-Native gcloud iam service-accounts create $ServiceAccountId `
        --project=$ProjectId `
        --display-name="Ad Analyzer GitHub operations auditor"
}

$projectRoles = @(
    "roles/viewer",
    "roles/iam.securityReviewer",
    "roles/secretmanager.viewer"
)

foreach ($role in $projectRoles) {
    Invoke-Native gcloud projects add-iam-policy-binding $ProjectId `
        --member="serviceAccount:$serviceAccountEmail" `
        --role=$role `
        --condition=None
}

$principalSet = "principalSet://iam.googleapis.com/projects/$ProjectNumber/locations/global/workloadIdentityPools/$PoolId/attribute.repository/$Repository"
Invoke-Native gcloud iam service-accounts add-iam-policy-binding $serviceAccountEmail `
    --project=$ProjectId `
    --member=$principalSet `
    --role="roles/iam.workloadIdentityUser"

$providerResource = (& gcloud iam workload-identity-pools providers describe $ProviderId `
    --project=$ProjectId `
    --location=global `
    --workload-identity-pool=$PoolId `
    --format="value(name)").Trim()

Invoke-Native gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER `
    --repo $Repository `
    --body $providerResource
Invoke-Native gh variable set GCP_OPERATIONS_SERVICE_ACCOUNT `
    --repo $Repository `
    --body $serviceAccountEmail

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Repository: $Repository"
Write-Host "Workload identity provider: $providerResource"
Write-Host "Operations service account: $serviceAccountEmail"
Write-Host ""
Write-Host "No service-account key was created."
Write-Host "Run the Production Operations Audit workflow once manually."
