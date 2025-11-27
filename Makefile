.PHONY: help install test lint type-check format check coverage clean

help:
	@echo "Available commands:"
	@echo "  make install      - Install dependencies"
	@echo "  make test         - Run tests with coverage"
	@echo "  make lint         - Run flake8 linter"
	@echo "  make type-check   - Run mypy type checker"
	@echo "  make format       - Format code with black"
	@echo "  make check        - Run all quality checks"
	@echo "  make coverage     - Generate coverage report"
	@echo "  make clean        - Clean generated files"

install:
	pip install -r requirements.txt

test:
	PYTHONPATH=src pytest --cov=src/crypto_trading --cov-report=term-missing --cov-report=html

lint:
	flake8 src/ tests/

type-check:
	mypy src/ tests/

format:
	black .

check: format lint type-check test

coverage:
	PYTHONPATH=src pytest --cov=src/crypto_trading --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

clean:
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete

