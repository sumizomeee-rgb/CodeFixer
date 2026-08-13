$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$root = [IO.Path]::GetFullPath($PWD.Path)
$venvPython = Join-Path $root "backend\.venv\Scripts\python.exe"
$runScript = Join-Path $root "scripts\run.py"

if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Project virtual environment is missing. Run scripts\bootstrap.ps1 first."
}
if (-not (Test-Path -LiteralPath $runScript)) {
    throw "scripts\run.py is missing."
}

Write-Host "[CodeFixer] Building frontend..."
& $venvPython $runScript --build-only
if ($LASTEXITCODE -ne 0) {
    Write-Host "[CodeFixer] Build failed. Existing instance was left running."
    exit $LASTEXITCODE
}

function Get-CodeFixerProcesses {
    @(Get-CimInstance Win32_Process | Where-Object {
        $commandLine = [string]$_.CommandLine
        if ([string]::IsNullOrWhiteSpace($commandLine)) { return $false }
        if ($commandLine.IndexOf($root, [StringComparison]::OrdinalIgnoreCase) -lt 0) { return $false }
        return (
            $commandLine -match '(?i)(?:^|\s)scripts[\\/]+run\.py(?:\s|$)' -or
            $commandLine -match '(?i)(?:^|\s)-m\s+codefixer(?:\s|$)'
        )
    })
}

$targets = Get-CodeFixerProcesses
if ($targets.Count -gt 0) {
    Write-Host "[CodeFixer] Stopping existing instance..."

    # run.py starts `python -m codefixer`. taskkill /T already terminates the whole
    # child tree, so only kill target processes whose parent is not another target.
    $targetIds = @($targets | ForEach-Object { [int]$_.ProcessId })
    $roots = @($targets | Where-Object { $targetIds -notcontains [int]$_.ParentProcessId })

    foreach ($process in $roots) {
        $pidToStop = [int]$process.ProcessId
        if (Get-Process -Id $pidToStop -ErrorAction SilentlyContinue) {
            # Redirect inside cmd.exe so Windows PowerShell 5.1 does not promote
            # taskkill stderr into NativeCommandError under ErrorAction=Stop.
            & $env:ComSpec /d /c "taskkill.exe /PID $pidToStop /T /F >nul 2>&1"
        }
    }

    $deadline = [DateTime]::UtcNow.AddSeconds(5)
    do {
        Start-Sleep -Milliseconds 200
        $remaining = Get-CodeFixerProcesses
    } while ($remaining.Count -gt 0 -and [DateTime]::UtcNow -lt $deadline)

    if ($remaining.Count -gt 0) {
        $ids = ($remaining | ForEach-Object ProcessId) -join ', '
        throw "CodeFixer process did not stop in time. Remaining PID(s): $ids"
    }

    Write-Host "[CodeFixer] Previous instance stopped."
} else {
    Write-Host "[CodeFixer] No existing instance found."
}

Write-Host "[CodeFixer] Starting server..."
& $venvPython $runScript
exit $LASTEXITCODE
