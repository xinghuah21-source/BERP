param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

$dc = "docker compose -f docker-compose.full.yml"
$up = "up -d"
if ($Build) { $up = "up -d --build" }

function Invoke-HttpOk {
    param(
        [Parameter(Mandatory=$true)][string]$Url,
        [int]$MaxAttempts = 30,
        [int]$SleepSeconds = 2
    )

    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) {
                return $true
            }
            Write-Host ("Health not ready: {0} status={1} attempt={2}/{3}" -f $Url, $resp.StatusCode, $i, $MaxAttempts)
        } catch {
            Write-Host ("Health not ready: {0} err={1} attempt={2}/{3}" -f $Url, $_.Exception.Message, $i, $MaxAttempts)
        }
        Start-Sleep -Seconds $SleepSeconds
    }
    return $false
}

try {
    Write-Host "1. Start infrastructure..."
    Invoke-Expression "$dc $up postgres redis"
    Start-Sleep -Seconds 5
    Write-Host "OK"

    Write-Host "2. Start AI engine..."
    Invoke-Expression "$dc $up ai-engine"
    Start-Sleep -Seconds 3
    Write-Host "OK"

    Write-Host "3. Start backend API..."
    Invoke-Expression "$dc $up backend"
    Start-Sleep -Seconds 5
    Write-Host "OK"

    Write-Host "4. Start WebSocket gateway..."
    Invoke-Expression "$dc $up websocket"
    Start-Sleep -Seconds 3
    Write-Host "OK"

    Write-Host "5. Start frontend..."
    Invoke-Expression "$dc $up frontend nginx"
    Start-Sleep -Seconds 3
    Write-Host "OK"

    Write-Host "6. Health checks..."
    $apiOk = Invoke-HttpOk -Url "http://127.0.0.1/api/health" -MaxAttempts 30 -SleepSeconds 2
    if (-not $apiOk) {
        Invoke-Expression "$dc ps"
        throw "API health failed"
    }

    $aiOk = Invoke-HttpOk -Url "http://127.0.0.1/ai/health" -MaxAttempts 30 -SleepSeconds 2
    if (-not $aiOk) {
        Invoke-Expression "$dc ps"
        throw "AI health failed"
    }

    $wsOk = Invoke-HttpOk -Url "http://127.0.0.1/ws/health" -MaxAttempts 30 -SleepSeconds 2
    if (-not $wsOk) {
        Invoke-Expression "$dc ps"
        throw "WebSocket health failed"
    }
    Write-Host "OK"

    Write-Host "ALL OK. Open http://localhost"
} catch {
    Write-Host ("FAILED: {0}" -f $_.Exception.Message)
    Invoke-Expression "$dc ps" | Out-Host
    Read-Host "Press Enter to close"
    exit 1
}
