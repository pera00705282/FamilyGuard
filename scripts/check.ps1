# Comprehensive code quality check script for Windows PowerShell
$ErrorActionPreference = "Stop"

Write-Host "🔍 Running code quality checks..." -ForegroundColor Cyan

# Set PYTHONPATH
$env:PYTHONPATH = "src"

# Format check
Write-Host "📝 Checking code formatting (black)..." -ForegroundColor Yellow
black --check .

# Lint check
Write-Host "🔎 Running linter (flake8)..." -ForegroundColor Yellow
flake8 src/ tests/

# Type check
Write-Host "🔬 Running type checker (mypy)..." -ForegroundColor Yellow
mypy src/ tests/

# Tests with coverage
Write-Host "🧪 Running tests with coverage..." -ForegroundColor Yellow
pytest --cov=src/crypto_trading --cov-report=term-missing --cov-report=html

Write-Host "✅ All checks passed!" -ForegroundColor Green

