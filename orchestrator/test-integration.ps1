$ErrorActionPreference = "Stop"

Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "1. API health..."
$api = Invoke-WebRequest -Uri "http://localhost/api/health" -UseBasicParsing
$ai = Invoke-WebRequest -Uri "http://localhost/ai/health" -UseBasicParsing
if ($api.StatusCode -ne 200) { throw "API health failed" }
if ($ai.StatusCode -ne 200) { throw "AI health failed" }
Write-Host "OK"

Write-Host "2. WebSocket test..."
$temp = New-TemporaryFile
$pyLines = @(
  'import asyncio, json, time',
  'import websockets',
  'from jose import jwt',
  '',
  'secret = "your-secret-key-here"',
  'token = jwt.encode({"sub": "test", "exp": int(time.time()) + 3600}, secret, algorithm="HS256")',
  '',
  'async def t():',
  '    uri = f"ws://127.0.0.1/ws/test_user?token={token}"',
  '    async with websockets.connect(uri) as ws:',
  '        await ws.recv()',
  '        await ws.send(json.dumps({',
  '            "type": "audio_chunk",',
  '            "data": "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=",',
  '            "seq": 1,',
  '            "is_final": False',
  '        }))',
  '        msg = await ws.recv()',
  '        print(msg)',
  '',
  'asyncio.run(t())'
)
$py = $pyLines -join "`n"
Set-Content -Path $temp.FullName -Value $py -Encoding UTF8
& E:\ANACONDA\envs\BERP\python.exe $temp.FullName
$exit = $LASTEXITCODE
Remove-Item $temp.FullName -Force
if ($exit -ne 0) { throw "WebSocket test failed" }
Write-Host "OK"
