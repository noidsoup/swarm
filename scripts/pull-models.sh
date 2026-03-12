#!/usr/bin/env bash
# Pull Ollama models into the running container.
# Usage: bash scripts/pull-models.sh [--large]
#
# Default: pulls the 7b worker model.
# --large: also pulls 14b for planning/review and 3b for lint/docs.

set -euo pipefail

OLLAMA_CONTAINER="swarm-ollama"

echo "=== Pulling Ollama models ==="

echo "[1] qwen2.5-coder:7b (worker default, ~4.4GB)"
docker exec "$OLLAMA_CONTAINER" ollama pull qwen2.5-coder:7b

if [[ "${1:-}" == "--large" ]]; then
    echo "[2] qwen2.5-coder:14b (planner/reviewer, ~9GB — needs 12GB VRAM)"
    docker exec "$OLLAMA_CONTAINER" ollama pull qwen2.5-coder:14b

    echo "[3] qwen2.5-coder:3b (lint/docs — fast, ~2GB)"
    docker exec "$OLLAMA_CONTAINER" ollama pull qwen2.5-coder:3b
fi

echo ""
echo "=== Installed models ==="
docker exec "$OLLAMA_CONTAINER" ollama list
echo ""
echo "Done!"
