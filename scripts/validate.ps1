param(
    [ValidateSet('Full', 'Focused', 'PostgreSQL', 'Migrations', 'Security', 'Privacy', 'ReadOnly', 'ControlledWrites', 'Release')]
    [string]$Scope = 'Full'
)
$ErrorActionPreference = 'Stop'

function Invoke-Step {
    param([Parameter(Mandatory=$true)][string]$Command)
    Write-Host "+ $Command"
    Invoke-Expression $Command
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
function Require-DisposablePostgres {
    if ([string]::IsNullOrWhiteSpace($env:DENTICODE_TEST_POSTGRES_URL)) { Write-Error 'DENTICODE_TEST_POSTGRES_URL is not configured; PostgreSQL integration testing cannot run.' }
    if ($env:DENTICODE_CI_DISPOSABLE_POSTGRES -ne 'true' -and $env:DENTICODE_TEST_POSTGRES_URL -notmatch '(_ci|test)') { Write-Error 'Refusing migration validation: DENTICODE_TEST_POSTGRES_URL must identify a disposable CI/test database.' }
    $env:DATABASE_URL = $env:DENTICODE_TEST_POSTGRES_URL
}
function Invoke-Focused { Invoke-Step 'python -m pytest tests/test_automation_foundation.py' }
function Invoke-PostgreSQL { Require-DisposablePostgres; Invoke-Step 'python -m pytest tests/test_phase7_postgres_transactions.py' }
function Invoke-Migrations { Require-DisposablePostgres; Invoke-Step 'alembic upgrade head'; Invoke-Step 'alembic downgrade base'; Invoke-Step 'alembic upgrade head' }
function Invoke-Security { Invoke-Step 'python -m pytest tests/test_google_ads_read_only.py tests/test_automation_foundation.py -k "security or approval or controlled or read_only"' }
function Invoke-Privacy { Invoke-Step 'python -m pytest tests/test_automation_foundation.py' }
function Invoke-ReadOnly { Invoke-Step 'python -m pytest tests/test_automation_foundation.py -k "read_only or no_product"' }
function Invoke-ControlledWrites { Write-Error 'ControlledWrites gates are intentionally not implemented before Phase 11 approved policy and human authorization.' }
function Invoke-Release { Write-Error 'Release gates are intentionally not implemented before Phase 12 production release approval.' }

switch ($Scope) {
    'Full' {
        if (-not [string]::IsNullOrWhiteSpace($env:DENTICODE_TEST_POSTGRES_URL)) { $env:DATABASE_URL = $env:DENTICODE_TEST_POSTGRES_URL } else { Write-Host 'DENTICODE_TEST_POSTGRES_URL is not configured; PostgreSQL integration testing cannot run locally.' }
        Invoke-Step 'alembic upgrade head'; Invoke-Step 'python -m pytest'; Invoke-Step 'ruff check .'; Invoke-Step 'mypy'
        $diffBase = if ([string]::IsNullOrWhiteSpace($env:DENTICODE_DIFF_BASE)) { 'HEAD' } else { $env:DENTICODE_DIFF_BASE }; Invoke-Step "git diff --check $diffBase"
        if (-not [string]::IsNullOrWhiteSpace($env:DENTICODE_TEST_POSTGRES_URL)) { Invoke-PostgreSQL; Invoke-Migrations }
        Invoke-ReadOnly; Invoke-Security; Invoke-Privacy; Invoke-Focused
    }
    'Focused' { Invoke-Focused }
    'PostgreSQL' { Invoke-PostgreSQL }
    'Migrations' { Invoke-Migrations }
    'Security' { Invoke-Security }
    'Privacy' { Invoke-Privacy }
    'ReadOnly' { Invoke-ReadOnly }
    'ControlledWrites' { Invoke-ControlledWrites }
    'Release' { Invoke-Release }
}
