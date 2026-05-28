$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
Write-Host "[启动 FastAPI 服务...]" -ForegroundColor Green
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
