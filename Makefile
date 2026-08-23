.PHONY: test lint typecheck coverage check debug

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run basedpyright
	uv run mypy .

coverage:
	uv run pytest --cov=amdl --cov-report=term-missing --cov-branch

check: lint typecheck test

debug:
	uv run python dev/debug_client.py