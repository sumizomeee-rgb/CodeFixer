$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $PWD "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) { throw "Project virtual environment is missing. Run scripts\bootstrap.ps1 first." }
& $venvPython scripts/run.py @args
exit $LASTEXITCODE
