@echo off
cd /d "%~dp0"
echo [启动命令行交互...]
uv run python run_v2_cli.py
pause
