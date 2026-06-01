@echo off
cd /d %~dp0
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%CD%\\start-service.ps1"" -Build'"
