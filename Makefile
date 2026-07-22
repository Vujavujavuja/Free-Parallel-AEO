.DEFAULT_GOAL := help
.PHONY: help dev test lint typecheck fmt build run docker clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

dev:  ## Install package + dev dependencies (editable)
	uv pip install -e ".[dev]" || pip install -e ".[dev]"

lint:  ## Run ruff lint
	ruff check .

fmt:  ## Format with ruff
	ruff format .
	ruff check --fix .

typecheck:  ## Run mypy --strict
	mypy src

test:  ## Run the test suite with coverage
	pytest --cov=aeo --cov-report=term-missing

run:  ## Bootstrap everything and serve the UI
	python run.py

serve:  ## Serve the API/UI without full bootstrap
	python -m aeo serve

build:  ## Build the frontend into src/aeo/web/dist
	cd frontend && npm install && npm run build

docker:  ## Build the Docker image
	docker build -t free-parallel-aeo:latest .

clean:  ## Remove build/test artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build *.egg-info htmlcov .coverage
