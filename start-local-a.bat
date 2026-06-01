@echo off
setlocal
cd /d "%~dp0"
if not defined LOCAL_POSTGRES_PORT set "LOCAL_POSTGRES_PORT=55432"
if not defined DATABASE_URL set "DATABASE_URL=postgresql+asyncpg://recitation:recitation@127.0.0.1:%LOCAL_POSTGRES_PORT%/recitation"
if not defined EMOTION2VEC_CONDA_PYTHON set "EMOTION2VEC_CONDA_PYTHON=E:\ANACONDA\envs\BERP\python.exe"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-local-a.ps1"
endlocal
