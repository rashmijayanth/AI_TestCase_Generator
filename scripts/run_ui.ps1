# Runs the Streamlit UI against a locally running API (uvicorn testgen.api.app:app,
# defaulting to http://localhost:8000 -- override via API_BASE_URL in .env).
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

& ".venv\Scripts\python.exe" -m streamlit run "src\testgen\ui\app.py"
