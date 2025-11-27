# Development Guide

This document provides a quick reference for developers working on this project.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run all quality checks
make check
# OR on Windows PowerShell:
.\scripts\check.ps1

# Format code
make format
# OR on Windows PowerShell:
.\scripts\format.ps1

# Run tests
make test
```

## Available Commands

### Using Make (Linux/Mac)

- `make install` - Install all dependencies
- `make test` - Run tests with coverage
- `make lint` - Run flake8 linter
- `make type-check` - Run mypy type checker
- `make format` - Format code with black
- `make check` - Run all quality checks (format, lint, type-check, test)
- `make coverage` - Generate HTML coverage report
- `make clean` - Clean generated files

### Using Scripts (Cross-platform)

- `scripts/check.sh` or `scripts/check.ps1` - Run all quality checks
- `scripts/format.sh` or `scripts/format.ps1` - Format code

## Code Quality Standards

All code must:

- ✅ Pass `pytest` (all tests)
- ✅ Pass `flake8` (no style errors)
- ✅ Pass `mypy` (type checking - some errors allowed for now)
- ✅ Be formatted with `black`
- ✅ Maintain or improve code coverage

## Pre-commit Hooks

Install pre-commit hooks to automatically check code before commits:

```bash
pip install pre-commit
pre-commit install
```

This will automatically run black, flake8, and mypy on every commit.

## CI/CD

GitHub Actions automatically runs all quality checks on every push and pull request. PRs will be blocked if:

- Tests fail
- Linting fails
- Code formatting is incorrect

## Configuration Files

- `mypy.ini` - Type checking configuration
- `.flake8` - Linting configuration
- `pyproject.toml` - Black, pytest, and coverage configuration
- `.pre-commit-config.yaml` - Pre-commit hooks configuration

## Environment Setup

Always set `PYTHONPATH=src` when running tests locally:

```bash
# Linux/Mac
export PYTHONPATH=src

# Windows PowerShell
$env:PYTHONPATH="src"

# Windows CMD
set PYTHONPATH=src
```

## Coverage Reports

Coverage reports are generated in `htmlcov/index.html` after running tests. Open this file in a browser to see detailed coverage information.
