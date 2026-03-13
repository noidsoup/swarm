.PHONY: lint test fmt check

lint:
	python -m ruff check swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py scripts/swarm_remote.py

fmt:
	python -m ruff format swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py scripts/swarm_remote.py

test:
	pytest

check: lint test
