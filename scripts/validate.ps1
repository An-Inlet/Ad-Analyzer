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
function Invoke-Focused { Invoke-Step 'python -m pytest tests/test_automation_foundation.py tests/test_api_v1_read_only.py -k "automation_foundation or scoping or account_scoped or no_writes"' }
function Invoke-PostgreSQL { Require-DisposablePostgres; Invoke-Step 'python -m pytest tests/test_phase7_postgres_transactions.py' }
function Invoke-Migrations { Require-DisposablePostgres; Invoke-Step 'alembic upgrade head'; Invoke-Step 'alembic downgrade base'; Invoke-Step 'alembic upgrade head' }
function Invoke-Security { Invoke-Step 'python -m pytest tests/test_google_ads_read_only.py tests/test_token_files.py tests/test_generate_google_ads_refresh_token.py tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "read_only or token or secret or credential or sanitized or error_messages or controlled or approval"' }
function Invoke-Privacy { Invoke-Step 'python -m pytest tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "sanitized or secret or credential or token or error_messages or sensitive or search_term"' }
function Invoke-ReadOnly { Invoke-Step 'python -m pytest tests/test_google_ads_read_only.py tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "read_only or no_writes or no_product or pre_write"' }
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
