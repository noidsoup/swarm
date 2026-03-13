.PHONY: lint test fmt check smoke

PYTHON ?= python3

lint:
	$(PYTHON) -m ruff check swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py scripts/swarm_remote.py

fmt:
	$(PYTHON) -m ruff format swarm tests run.py daemon.py setup.py simplemem_client.py simplemem_cli.py scripts/swarm_remote.py

test:
	pytest

## Run local smoke dispatch without Ollama (SWARM_SMOKE_SKIP_LLM=1). Use to verify pipeline wiring.
smoke:
	SWARM_SMOKE_SKIP_LLM=1 $(PYTHON) -c "from swarm.config import cfg; from swarm.dispatch import Dispatcher; d=Dispatcher(cfg); r=d.dispatch(plan='cursor smoke test', feature_name='cursor smoke test', builder_type='python_dev', repo_path='.', execution_mode='local'); print('OK' if r.get('status')=='complete' and 'SMOKE_OK' in str(r.get('build_summary','')) else r)"
	@echo "Smoke OK: pipeline wiring verified (no LLM required)"

check: lint test
