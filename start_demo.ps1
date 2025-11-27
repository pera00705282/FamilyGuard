# Quick Start Script for Windows PowerShell
# Run this to start the demo mode

Write-Host "🚀 Starting Crypto Trading Tool Demo..." -ForegroundColor Cyan
Write-Host "=" * 50

# Set PYTHONPATH
$env:PYTHONPATH = "src"

# Run the demo
try {
    python examples/demo.py
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
    exit 1
}

