.PHONY: test lint typecheck coverage check debug profile-imports flamegraph

ARGS ?= --help

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

# 	`make profile-imports ARGS="--help"`
profile-imports:
	uv run python3.15 -X importtime -m amdl $(ARGS) 2> dev/import.log
	uv run tuna dev/import.log

flamegraph:
	uv run python3.15 -m profiling.sampling run --flamegraph -o dev/profile.html -m amdl.main $(ARGS)
	xdg-open dev/profile.html
