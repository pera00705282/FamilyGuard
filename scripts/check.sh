#!/bin/bash
# Comprehensive code quality check script
set -e

echo "🔍 Running code quality checks..."

# Set PYTHONPATH
export PYTHONPATH=src

# Format check
echo "📝 Checking code formatting (black)..."
black --check .

# Lint check
echo "🔎 Running linter (flake8)..."
flake8 src/ tests/

# Type check
echo "🔬 Running type checker (mypy)..."
mypy src/ tests/

# Tests with coverage
echo "🧪 Running tests with coverage..."
pytest --cov=src/crypto_trading --cov-report=term-missing --cov-report=html

echo "✅ All checks passed!"

