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
    if ([string]::IsNullOrWhiteSpace($env:AD_ANALYZER_TEST_POSTGRES_URL)) {
        Write-Error 'AD_ANALYZER_TEST_POSTGRES_URL is not configured; PostgreSQL integration testing cannot run.'
    }
    if ($env:AD_ANALYZER_CI_DISPOSABLE_POSTGRES -ne 'true') {
        Write-Error 'Refusing migration validation: AD_ANALYZER_CI_DISPOSABLE_POSTGRES must exactly equal true.'
    }
    try {
        $uri = [System.Uri]::new($env:AD_ANALYZER_TEST_POSTGRES_URL)
    } catch {
        Write-Error 'Refusing migration validation: malformed AD_ANALYZER_TEST_POSTGRES_URL.'
    }
    if ($uri.Scheme -ne 'postgresql' -and $uri.Scheme -ne 'postgresql+psycopg') {
        Write-Error 'Refusing migration validation: AD_ANALYZER_TEST_POSTGRES_URL must use a PostgreSQL scheme.'
    }
    $databaseName = [System.Uri]::UnescapeDataString(($uri.AbsolutePath.Trim('/') -split '/')[-1]).ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($databaseName)) {
        Write-Error 'Refusing migration validation: PostgreSQL database name is empty.'
    }
    if ($databaseName -match 'prod|production|stage|staging') {
        Write-Error 'Refusing migration validation: staging/production database names are never disposable.'
    }
    if (-not ($databaseName.EndsWith('_ci') -or $databaseName.EndsWith('_test') -or $databaseName.Contains('_ci_') -or $databaseName.Contains('_test_'))) {
        Write-Error 'Refusing migration validation: database name must use a controlled _ci or _test naming convention.'
    }
    $env:DATABASE_URL = $env:AD_ANALYZER_TEST_POSTGRES_URL
}
function Invoke-Focused { Invoke-Step 'python -m pytest tests/test_automation_foundation.py tests/test_api_v1_read_only.py -k "automation_foundation or scoping or account_scoped or no_writes"' }
function Invoke-PostgreSQL { Require-DisposablePostgres; Invoke-Step 'python -m pytest tests/test_phase7_postgres_transactions.py' }
function Invoke-Migrations { Require-DisposablePostgres; Invoke-Step 'python scripts/reset_disposable_postgres.py'; Invoke-Step 'alembic upgrade head'; Invoke-Step 'alembic downgrade base'; Invoke-Step 'alembic upgrade head' }
function Invoke-Security { Invoke-Step 'python -m pytest tests/test_google_ads_read_only.py tests/test_token_files.py tests/test_generate_google_ads_refresh_token.py tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "read_only or token or secret or credential or sanitized or error_messages or controlled or approval"' }
function Invoke-Privacy { Invoke-Step 'python -m pytest tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "sanitized or secret or credential or token or error_messages or sensitive or search_term"' }
function Invoke-ReadOnly { Invoke-Step 'python -m pytest tests/test_google_ads_read_only.py tests/test_api_v1_read_only.py tests/test_automation_foundation.py -k "read_only or no_writes or no_product or pre_write"' }
function Invoke-ControlledWrites {
    Invoke-Step 'python -m pytest tests/test_analyzer_v1.py -k "dry_run or recommendation"'
    Invoke-Step 'python -c "from app.settings import Settings; settings = Settings(); assert settings.google_ads_write_enabled is False; assert settings.google_ads_execution_kill_switch is True"'
}
function Invoke-Release {
    Invoke-Step 'python -m pytest'
    Invoke-Step 'ruff check .'
    Invoke-Step 'mypy'
    $diffBase = if ([string]::IsNullOrWhiteSpace($env:AD_ANALYZER_DIFF_BASE)) { 'HEAD' } else { $env:AD_ANALYZER_DIFF_BASE }
    Invoke-Step "git diff --check $diffBase"
}

switch ($Scope) {
    'Full' {
        if (-not [string]::IsNullOrWhiteSpace($env:AD_ANALYZER_TEST_POSTGRES_URL)) {
            Require-DisposablePostgres
            Invoke-Step 'python scripts/reset_disposable_postgres.py'
        } else {
            Write-Host 'AD_ANALYZER_TEST_POSTGRES_URL is not configured; PostgreSQL integration testing cannot run locally.'
        }
        Invoke-Step 'alembic upgrade head'; Invoke-Step 'python -m pytest'; Invoke-Step 'ruff check .'; Invoke-Step 'mypy'
        $diffBase = if ([string]::IsNullOrWhiteSpace($env:AD_ANALYZER_DIFF_BASE)) { 'HEAD' } else { $env:AD_ANALYZER_DIFF_BASE }; Invoke-Step "git diff --check $diffBase"
        if (-not [string]::IsNullOrWhiteSpace($env:AD_ANALYZER_TEST_POSTGRES_URL)) { Invoke-PostgreSQL; Invoke-Migrations }
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
