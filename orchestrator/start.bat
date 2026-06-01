@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d %~dp0
if exist .env (
  for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if not "%%A"=="" set "%%A=%%B"
  )
)
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Build
echo.
pause
