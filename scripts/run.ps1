$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$venvPython = Join-Path $PWD "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) { throw "项目虚拟环境不存在，请先运行 scripts\bootstrap.ps1。" }
& $venvPython scripts/run.py @args
exit $LASTEXITCODE
