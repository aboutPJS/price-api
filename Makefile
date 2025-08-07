.PHONY: help install dev-install test test-cov lint format type-check clean build run dev docker-build docker-run init-db fetch-prices

# Default target
help:
	@echo "Energy Price API - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  install       Install production dependencies"
	@echo "  dev-install   Install development dependencies"
	@echo ""
	@echo "Development:"
	@echo "  run           Start the API server"
	@echo "  dev           Start the API server in development mode"
	@echo "  init-db       Initialize the database"
	@echo "  fetch-prices  Manually fetch price data"
	@echo ""
	@echo "Testing:"
	@echo "  test          Run tests"
	@echo "  test-cov      Run tests with coverage"
	@echo ""
	@echo "Code Quality:"
	@echo "  lint          Run linting checks"
	@echo "  format        Format code with black and isort"
	@echo "  type-check    Run type checking with mypy"
	@echo ""
	@echo "Docker:"
	@echo "  docker-build  Build Docker image"
	@echo "  docker-run    Run Docker container"
	@echo ""
	@echo "Utilities:"
	@echo "  clean         Clean up build artifacts and cache files"
	@echo "  build         Build the package"

# Setup
install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install -e .

# Development
run:
	python -m src.main

dev:
	python -m src.main --reload

init-db:
	python scripts/dev.py init-db

fetch-prices:
	python scripts/dev.py fetch-prices

# Testing
test:
	pytest

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

# Code Quality
lint:
	flake8 src tests scripts
	mypy src

format:
	black src tests scripts
	isort src tests scripts

type-check:
	mypy src

# Docker
docker-build:
	docker build -t energy-price-api:latest .

docker-run:
	docker-compose up -d

# Utilities
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .coverage
	rm -rf htmlcov/

build:
	python -m build

# Development workflows
ci: format lint test-cov
	@echo "CI checks completed successfully"

pre-commit: format lint
	@echo "Pre-commit checks completed"
