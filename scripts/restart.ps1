$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$root = [IO.Path]::GetFullPath($PWD.Path)

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
    # This also avoids a harmless race where the child PID disappears before its
    # own taskkill call and Windows reports "process not found".
    $targetIds = @($targets | ForEach-Object { [int]$_.ProcessId })
    $roots = @($targets | Where-Object { $targetIds -notcontains [int]$_.ParentProcessId })

    foreach ($process in $roots) {
        $pidToStop = [int]$process.ProcessId
        if (Get-Process -Id $pidToStop -ErrorAction SilentlyContinue) {
            # Redirect inside cmd.exe so Windows PowerShell 5.1 does not promote
            # taskkill's stderr into NativeCommandError under ErrorAction=Stop.
            # A disappearing PID is success for restart purposes; final liveness
            # is checked below instead of trusting one taskkill exit code.
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

Write-Host "[CodeFixer] Building frontend and starting server..."
& (Join-Path $PSScriptRoot "run.ps1") --build
exit $LASTEXITCODE
