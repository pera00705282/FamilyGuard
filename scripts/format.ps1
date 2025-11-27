# Auto-format code script for Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "🎨 Formatting code with black..." -ForegroundColor Cyan

black .

Write-Host "✅ Code formatted!" -ForegroundColor Green

