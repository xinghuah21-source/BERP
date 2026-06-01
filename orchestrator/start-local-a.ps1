param(
    [switch]$Headless,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runtimeRoot = Join-Path $PSScriptRoot ".local-runtime"
$logRoot = Join-Path $runtimeRoot "logs"
$pidFile = Join-Path $runtimeRoot "local-a-processes.json"

New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
New-Item -ItemType Directory -Force -Path $logRoot | Out-Null

function Write-Step {
    param([string]$Message)
    Write-Host ("`n== {0} ==" -f $Message)
}

function Load-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return
    }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            return
        }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) {
            return
        }
        $name = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1)
        if ($name) {
            Set-Item -Path ("Env:{0}" -f $name) -Value $value
        }
    }
}

function Get-PreferredPython {
    $candidates = @(
        "E:\Python\python.exe",
        "E:\ANACONDA\pkgs\python-3.10.20-h1044e36_0\python.exe"
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }
    throw "Python 3.10 was not found. Please install Python 3.10 first."
}

function Ensure-Venv {
    param(
        [string]$VenvPath,
        [string[]]$Requirements
    )
    $pythonExe = Join-Path $VenvPath "Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        $basePython = Get-PreferredPython
        Write-Host ("Create venv: {0}" -f $VenvPath)
        & $basePython -m venv $VenvPath
    }

    & $pythonExe -m ensurepip --upgrade | Out-Host
    & $pythonExe -m pip install --upgrade pip setuptools wheel | Out-Host

    if (-not $SkipInstall) {
        $installArgs = @("-m", "pip", "install")
        foreach ($req in $Requirements) {
            $installArgs += @("-r", $req)
        }
        & $pythonExe @installArgs | Out-Host
    }
    return $pythonExe
}

function Stop-ManagedProcesses {
    if (-not (Test-Path $pidFile)) {
        return
    }
    try {
        $records = Get-Content $pidFile -Raw | ConvertFrom-Json
        foreach ($record in $records) {
            $pidValue = [int]$record.pid
            $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
            if ($process) {
                Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        Write-Warning "Failed to read previous local process records. Ignored."
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

function Stop-DockerAppContainers {
    $containers = @("berp_frontend", "berp_websocket", "berp_ai_engine", "berp_backend", "berp_nginx")
    $running = @()
    try {
        $running = docker ps --format "{{.Names}}" | Where-Object { $containers -contains $_ }
    } catch {
        Write-Warning "Failed to inspect Docker containers. Make sure Docker Desktop is running."
    }
    if ($running -and $running.Count -gt 0) {
        Write-Host ("Stop app containers: {0}" -f ($running -join ", "))
        docker stop @running | Out-Host
    }
}

function Ensure-Infrastructure {
    $dockerNames = @()
    try {
        $dockerNames = docker ps --format "{{.Names}}"
    } catch {
        throw "Cannot connect to Docker. Please start Docker Desktop first."
    }

    $hasPostgres = $dockerNames | Where-Object { $_ -match "^berp_postgres(_full)?$" }
    $hasRedis = $dockerNames | Where-Object { $_ -match "^berp_redis(_full)?$" }
    if ($hasPostgres -and $hasRedis) {
        Write-Host "PostgreSQL/Redis are already running in Docker."
        return
    }

    Write-Host "Start Docker infrastructure (PostgreSQL/Redis)..."
    docker compose -f (Join-Path $repoRoot "docker-compose.base.yml") up -d postgres redis | Out-Host
}

function Test-TcpPort {
    param(
        [string]$Address,
        [int]$Port,
        [int]$TimeoutMs = 2000
    )
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect($Address, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            return $false
        }
        $client.EndConnect($iar) | Out-Null
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Ensure-HostRedisReachable {
    if (Test-TcpPort -Address "127.0.0.1" -Port 6379) {
        Write-Host "Redis host port 6379 is reachable."
        return
    }

    Write-Warning "Redis container is running but 127.0.0.1:6379 is unreachable. Recreating redis container..."
    docker compose -f (Join-Path $repoRoot "docker-compose.base.yml") up -d --force-recreate redis | Out-Host

    for ($i = 1; $i -le 15; $i++) {
        if (Test-TcpPort -Address "127.0.0.1" -Port 6379) {
            Write-Host "Redis host port 6379 recovered."
            return
        }
        Start-Sleep -Seconds 1
    }

    throw "Redis is not reachable on 127.0.0.1:6379. WebSocket evaluation would be stuck at 0%."
}

function Invoke-BackendSetup {
    param([string]$PythonExe)
    Push-Location (Join-Path $repoRoot "backend")
    try {
        $env:PYTHONPATH = "."
        & $PythonExe -m alembic upgrade head | Out-Host
        & $PythonExe .\scripts\seed.py | Out-Host
    } finally {
        Pop-Location
    }
}

function Start-ManagedService {
    param(
        [string]$Name,
        [string]$WorkDir,
        [string]$Command
    )

    $logFile = Join-Path $logRoot ("{0}.log" -f $Name)
    if (Test-Path $logFile) {
        Remove-Item $logFile -Force
    }

    $script = @"
Set-Location '$WorkDir'
`$env:PYTHONUTF8 = '1'
Start-Transcript -Path '$logFile' -Force | Out-Null
try {
    Invoke-Expression @'
$Command
'@
} finally {
    Stop-Transcript | Out-Null
}
"@

    $argList = @(
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy", "Bypass"
    )
    if (-not $Headless) {
        $argList += "-NoExit"
    }
    $argList += @("-Command", $script)

    $windowStyle = "Normal"
    if ($Headless) {
        $windowStyle = "Hidden"
    }
    $process = Start-Process -FilePath "powershell.exe" -ArgumentList $argList -PassThru -WindowStyle $windowStyle
    return [pscustomobject]@{
        name = $Name
        pid = $process.Id
        log = $logFile
    }
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$MaxAttempts = 40,
        [int]$SleepSeconds = 2
    )
    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds $SleepSeconds
    }
    return $false
}

Write-Step "Load Environment"
Load-EnvFile (Join-Path $PSScriptRoot ".env")
Load-EnvFile (Join-Path $repoRoot "ai-engine\.env")

if (-not $env:EMOTION2VEC_MODEL_DIR) {
    $defaultModelDir = "C:\Users\26947\.cache\modelscope\hub\models\iic\emotion2vec_base_finetuned"
    if (Test-Path $defaultModelDir) {
        $env:EMOTION2VEC_MODEL_DIR = $defaultModelDir
    }
}

if (-not $env:EMOTION2VEC_MODEL_DIR -or -not (Test-Path $env:EMOTION2VEC_MODEL_DIR)) {
    throw "emotion2vec local model directory was not found. Check EMOTION2VEC_MODEL_DIR."
}

Write-Step "Clean Old Processes"
Stop-ManagedProcesses
Stop-DockerAppContainers

Write-Step "Ensure Docker Infrastructure"
Ensure-Infrastructure
Ensure-HostRedisReachable

Write-Step "Prepare Python"
$apiPython = Ensure-Venv -VenvPath (Join-Path $repoRoot ".venv-local310") -Requirements @(
    (Join-Path $repoRoot "backend\requirements.txt"),
    (Join-Path $repoRoot "websocket-gateway\requirements.txt")
)
$aiPython = Ensure-Venv -VenvPath (Join-Path $repoRoot ".venv-ai310") -Requirements @(
    (Join-Path $repoRoot "ai-engine\requirements.txt")
)

if (-not $env:EMOTION2VEC_CONDA_PYTHON) {
    $env:EMOTION2VEC_CONDA_PYTHON = "E:\ANACONDA\envs\BERP\python.exe"
}

Write-Step "Run Migrations And Seed"
Invoke-BackendSetup -PythonExe $apiPython

Write-Step "Start Local Services"
$managed = @()
$managed += Start-ManagedService -Name "ai-engine" -WorkDir (Join-Path $repoRoot "ai-engine") -Command "& '$aiPython' -m uvicorn main:app --host 0.0.0.0 --port 8001"
$managed += Start-ManagedService -Name "backend" -WorkDir (Join-Path $repoRoot "backend") -Command "`$env:PYTHONPATH='.'; & '$apiPython' -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
$managed += Start-ManagedService -Name "websocket" -WorkDir (Join-Path $repoRoot "websocket-gateway") -Command "`$env:PYTHONPATH='.'; & '$apiPython' -m uvicorn main:app --host 0.0.0.0 --port 8002 --ws-max-size 50000000"
$managed += Start-ManagedService -Name "frontend" -WorkDir (Join-Path $repoRoot "frontend") -Command "npm run dev"

$managed | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8

Write-Step "Health Checks"
$checks = @(
    @{ name = "backend"; url = "http://127.0.0.1:8000/health" },
    @{ name = "ai-engine"; url = "http://127.0.0.1:8001/health" },
    @{ name = "websocket"; url = "http://127.0.0.1:8002/health" },
    @{ name = "frontend"; url = "http://localhost:5173" }
)

foreach ($check in $checks) {
    if (-not (Wait-HttpOk -Url $check.url)) {
        throw ("{0} failed to start. Check log: {1}" -f $check.name, (($managed | Where-Object { $_.name -eq $check.name }).log))
    }
    Write-Host ("{0} OK -> {1}" -f $check.name, $check.url)
}

Write-Step "Ready"
Write-Host "Local plan A runtime is ready."
Write-Host "Frontend: http://localhost:5173"
Write-Host "Stop script: .\stop-local-a.ps1"
