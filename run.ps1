# Usage:
#   .\run.ps1 signup
#   .\run.ps1 profile
#   .\run.ps1 profile --limit 1
#   .\run.ps1 cookies
#   .\run.ps1 cookies --limit 1

param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet("signup", "profile", "cookies")]
    [string]$Command,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Creating venv and installing dependencies..."
    python -m venv .venv
    & $python -m pip install -r requirements.txt
    & $python -m playwright install chromium
}

switch ($Command) {
    "signup" { & $python run_signup.py @Rest; exit $LASTEXITCODE }
    "profile" { & $python run_complete_profile.py @Rest; exit $LASTEXITCODE }
    "cookies" { & $python run_get_cookies.py @Rest; exit $LASTEXITCODE }
    default { Write-Error "Unknown command: $Command" }
}
