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
    foreach ($process in $targets) {
        & taskkill.exe /PID $process.ProcessId /T /F 2>$null | Out-Null
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
