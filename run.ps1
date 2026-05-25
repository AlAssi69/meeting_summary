# Launch Meeting Assistant from the repository root (activates .venv, then runs main.py).
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$activate = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path -LiteralPath $activate)) {
    Write-Error @"
Virtual environment not found at .venv
Create it from this folder:  python -m venv .venv
Then install dependencies:   pip install -r requirements.txt
"@
}

. $activate
py main.py
exit $LASTEXITCODE
