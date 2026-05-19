$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "==============================================" -ForegroundColor Yellow
Write-Host "Stopping Document Intelligence RAG Platform" -ForegroundColor Yellow
Write-Host "==============================================" -ForegroundColor Yellow
Write-Host ""

Set-Location $ProjectRoot

docker compose down --remove-orphans

Write-Host ""
Write-Host "Stopped." -ForegroundColor Green
Write-Host ""