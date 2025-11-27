# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2025-11-23

### Added

- **Complete CI/CD automation**: GitHub Actions workflow for automated testing, linting, type checking, and coverage reporting
- **Code quality automation**:
  - `mypy.ini` configuration for type checking
  - `.flake8` configuration for code style enforcement
  - `pyproject.toml` for black, pytest, and coverage configuration
  - Pre-commit hooks configuration (`.pre-commit-config.yaml`)
- **Developer tooling**:
  - `Makefile` with common development commands
  - `scripts/check.sh` and `scripts/check.ps1` for comprehensive quality checks
  - `scripts/format.sh` and `scripts/format.ps1` for code formatting
- **Documentation**:
  - `CONTRIBUTING.md` with complete contribution guidelines
  - `CHANGELOG.md` for tracking all project changes
- **Type safety improvements**:
  - Added type stubs for pandas, PyYAML, and psutil
  - Enhanced mypy configuration for better type checking

### Changed

- **Dependencies**: All dependencies updated to latest compatible versions
- **Pydantic migration**: Migrated all `@validator` decorators to Pydantic V2 `@field_validator` to eliminate deprecation warnings
- **Requirements**: Cleaned and strictly version-pinned `requirements.txt` with only necessary packages
- **Test infrastructure**: Enhanced test suite with coverage reporting and proper PYTHONPATH configuration

### Removed

- Obsolete and unused dependencies
- `cryptofeed` (temporarily removed due to Python 3.13 incompatibility)

### Fixed

- Import paths in test files to use proper package structure
- Pydantic deprecation warnings in configuration models
