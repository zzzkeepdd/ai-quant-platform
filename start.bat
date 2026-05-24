@echo off
setlocal
cd /d "%~dp0"
if not exist data_cache mkdir data_cache
if not exist backend\data_cache mkdir backend\data_cache
start "AI量化平台-后端" cmd /k "cd /d %~dp0backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
start "AI量化平台-前端" cmd /k "cd /d %~dp0frontend && npm run dev"
echo 已启动：后端 http://127.0.0.1:8000  前端 http://127.0.0.1:5173
