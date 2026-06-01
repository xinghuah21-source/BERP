$ErrorActionPreference = "Continue"

Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Check-Url {
    param([string]$Url)
    for ($i = 1; $i -le 10; $i++) {
        try {
            $resp = Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri $Url
            Write-Host ("OK {0} {1}" -f $resp.StatusCode, $Url)
            return $true
        } catch {
            if ($i -eq 10) {
                Write-Host ("FAIL {0} {1}" -f $_.Exception.Message, $Url)
                return $false
            }
            Start-Sleep -Seconds 1
        }
    }
}

Check-Url "http://127.0.0.1/api/health" | Out-Null
Check-Url "http://127.0.0.1/ai/health" | Out-Null
Check-Url "http://127.0.0.1/ws/health" | Out-Null

docker compose -f docker-compose.full.yml ps
