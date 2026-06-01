$ErrorActionPreference = "Stop"

$runtimeRoot = Join-Path $PSScriptRoot ".local-runtime"
$pidFile = Join-Path $runtimeRoot "local-a-processes.json"

if (-not (Test-Path $pidFile)) {
    Write-Host "No managed local process record was found."
    exit 0
}

try {
    $records = Get-Content $pidFile -Raw | ConvertFrom-Json
    foreach ($record in $records) {
        $pidValue = [int]$record.pid
        $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host ("Stop {0} (PID {1})" -f $record.name, $pidValue)
            Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        }
    }
} finally {
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Write-Host "Local services were stopped."
