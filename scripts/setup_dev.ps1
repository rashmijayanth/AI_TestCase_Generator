# Creates/updates the local dev virtual environment and installs dev tooling.
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

if (-not (Test-Path ".venv")) {
    py -3.11 -m venv .venv
}

& ".venv\Scripts\python.exe" -m pip install --upgrade pip
& ".venv\Scripts\python.exe" -m pip install -e ".[dev]"

Write-Output "Dev environment ready. Activate with: .venv\Scripts\Activate.ps1"
