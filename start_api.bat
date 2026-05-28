@echo off
cd /d "%~dp0"
echo [启动 FastAPI 服务...]
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
