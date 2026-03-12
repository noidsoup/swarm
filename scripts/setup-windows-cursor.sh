#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <windows-user> <windows-host> [identity-file]"
  exit 1
fi

WIN_USER="$1"
WIN_HOST="$2"
IDENTITY_FILE="${3:-}"
REMOTE="${WIN_USER}@${WIN_HOST}"

SSH_ARGS=()
SCP_ARGS=()
if [[ -n "${IDENTITY_FILE}" ]]; then
  SSH_ARGS+=(-i "${IDENTITY_FILE}")
  SCP_ARGS+=(-i "${IDENTITY_FILE}")
fi

echo "Creating remote queue directories..."
ssh "${SSH_ARGS[@]}" "${REMOTE}" \
  "python -c \"from pathlib import Path; root=Path('~/.swarm').expanduser(); (root/'inbox').mkdir(parents=True, exist_ok=True); (root/'outbox').mkdir(parents=True, exist_ok=True); print(root)\""

echo "Installing swarm worker rule template..."
ssh "${SSH_ARGS[@]}" "${REMOTE}" "python -c \"from pathlib import Path; (Path('~/.cursor/rules').expanduser()).mkdir(parents=True, exist_ok=True)\""
scp "${SCP_ARGS[@]}" "templates/swarm-worker.mdc" "${REMOTE}:~/.cursor/rules/swarm-worker.mdc"

echo "Windows Cursor worker setup complete."
