@echo off
setlocal
cd /d "%~dp0"
if not exist data_cache mkdir data_cache
if not exist backend\data_cache mkdir backend\data_cache
start "AI Quant Platform - Backend" cmd /k "cd /d %~dp0backend && set PYTHONPATH=%~dp0backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
start "AI Quant Platform - Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo Started:
echo Backend  http://127.0.0.1:8000
echo Frontend http://127.0.0.1:5173
pause
