param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

$envFile = Join-Path (Get-Location) ".env"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if (-not $line) { return }
        if ($line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $k = $line.Substring(0, $idx).Trim()
        $v = $line.Substring($idx + 1)
        if ($k) { [System.Environment]::SetEnvironmentVariable($k, $v) }
    }
}

$dc = "docker compose -f docker-compose.full.yml"
$up = "up -d"
if ($Build) { $up = "up -d --build" }

Invoke-Expression "$dc $up"
