$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
Write-Host "[启动命令行交互...]" -ForegroundColor Green
uv run python run_v2_cli.py
