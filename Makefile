.PHONY: lint test fmt check

PYTHON ?= python3

lint:
	$(PYTHON) -m ruff check swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py scripts/swarm_remote.py

fmt:
	$(PYTHON) -m ruff format swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py scripts/swarm_remote.py

test:
	pytest

check: lint test
