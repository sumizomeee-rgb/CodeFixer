$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12-64 -c "import sys; assert sys.version_info >= (3,12) and sys.maxsize > 2**32" 2>$null
    if ($LASTEXITCODE -eq 0) { & py -3.12-64 scripts/bootstrap.py @args; exit $LASTEXITCODE }
}
foreach ($candidate in @("python3.12", "python3", "python")) {
    if (-not (Get-Command $candidate -ErrorAction SilentlyContinue)) { continue }
    & $candidate -c "import sys; assert sys.version_info >= (3,12) and sys.maxsize > 2**32" 2>$null
    if ($LASTEXITCODE -eq 0) { & $candidate scripts/bootstrap.py @args; exit $LASTEXITCODE }
}
throw "CodeFixer 需要 64 位 CPython 3.12+。请先安装，再重新运行 bootstrap.ps1。"
