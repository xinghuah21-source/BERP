@echo off
cd /d %~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File .\check.ps1
echo.
pause
