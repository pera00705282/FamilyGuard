# Contributing Guidelines

Welcome! To help keep this project robust and reliable, please follow these rules when contributing:

## 🏗️ Environment Setup
- Use **Python 3.13** (or latest supported version from requirements.txt)
- Always use a virtualenv: `python -m venv .venv && source .venv/bin/activate` (Linux/Mac) or `.venv\Scripts\activate` (Win)
- Install dependencies with:
  ```sh
  pip install -r requirements.txt
  ```

## 🚦 Running the Test Suite and Checks
- For local tests, ensure project root is active and set PYTHONPATH:
  ```sh
  export PYTHONPATH=src  # Linux/Mac
  set PYTHONPATH=src     # Windows cmd
  $env:PYTHONPATH="src" # Windows PowerShell
  ```
- To run tests with coverage:
  ```sh
  python -m pytest --cov=src/crypto_trading --cov-report=term-missing --cov-report=html tests/
  ```
- All code must:
  - Pass **pytest**
  - Pass **flake8** (no errors)
  - Pass **mypy** (no errors)
  - Be formatted with **black** (check: `black --check .`, auto-fix: `black .`)
  - Achieve and not decrease code coverage (CI will fail PRs with missing coverage)

## 🌳 Branching + Workflow
- Use `main` for latest stable, `develop` for in-progress features.
- Feature/fix branches: `feature/description`, `fix/description` etc. Keep PRs focused and small.
- Always update or create CHANGELOG.md entries for dependency or impactful changes.
- Reference issues in commit messages and PRs.

## 🤝 Help & Reporting
- For support or to report a bug, open a GitHub issue or email the owners.
- See README and this document for usage and help links.

Thank you for making this a safe and robust platform!
