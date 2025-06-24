# Makefile for DeepSecure development

.PHONY: help install install-dev install-traditional test lint format build clean docs security

# Default target
help:
	@echo "DeepSecure Development Commands"
	@echo "==============================="
	@echo ""
	@echo "Setup Commands:"
	@echo "  install           - Install package for end users"
	@echo "  install-dev       - Install with development dependencies (modern)"
	@echo "  install-traditional - Install using requirements files"
	@echo "  setup             - Run automated setup script"
	@echo ""
	@echo "Development Commands:"
	@echo "  test              - Run tests"
	@echo "  test-cov          - Run tests with coverage"
	@echo "  lint              - Run linting (ruff + mypy)"
	@echo "  format            - Format code (black + isort)"
	@echo "  security          - Run security scans"
	@echo ""
	@echo "Build Commands:"
	@echo "  build             - Build package"
	@echo "  clean             - Clean build artifacts"
	@echo "  docs              - Build documentation"
	@echo ""
	@echo "Quality Commands:"
	@echo "  check-all         - Run all quality checks"
	@echo "  pre-commit        - Run pre-commit checks"

# Installation targets
install:
	pip install .

install-dev:
	pip install -e ".[all-dev]"

install-traditional:
	pip install -r requirements/dev.txt

setup:
	./scripts/setup_dev.sh

# Development targets
test:
	pytest

test-cov:
	pytest --cov=deepsecure --cov-report=html --cov-report=term

lint:
	ruff check .
	mypy deepsecure/

format:
	black .
	isort .
	ruff check --fix .

security:
	bandit -r deepsecure/
	safety check

# Build targets
build:
	./scripts/build_package.sh

clean:
	rm -rf build/ dist/ *.egg-info/ deepsecure.egg-info/
	rm -rf .pytest_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docs:
	@echo "Documentation build not yet configured"
	@echo "Install docs dependencies: pip install -e .[docs]"

# Quality assurance targets
check-all: lint test security
	@echo "✅ All quality checks passed!"

pre-commit: format lint test
	@echo "✅ Pre-commit checks completed!"

# Development workflow targets
dev-setup: install-dev
	@echo "🎉 Development environment ready!"
	@echo "Run 'make test' to verify everything works"

# CI/CD targets
ci-test:
	pip install -e .[test]
	pytest --cov=deepsecure --cov-report=xml

ci-lint:
	pip install -e .[lint]
	ruff check .
	black --check .
	isort --check-only .
	mypy deepsecure/ 