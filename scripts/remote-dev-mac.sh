#!/usr/bin/env bash
# Mac helper for remote-first swarm usage (Windows cursor worker).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/remote-dev-mac.sh <swarm_remote_args...>

Examples:
  scripts/remote-dev-mac.sh dispatch "Implement feature X" --repo-path "C:/Users/<you>/repos/my-repo"
  scripts/remote-dev-mac.sh status
  scripts/remote-dev-mac.sh logs <task-id>

Behavior:
  - Sets remote-friendly defaults for cursor mode.
  - Forces --mode cursor for dispatch if you did not pass --mode.
EOF
}

if [[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ -z "${WINDOWS_HOST:-}" || -z "${WINDOWS_USER:-}" ]]; then
  echo "Error: WINDOWS_HOST and WINDOWS_USER must be set in your shell or .env."
  echo "Example:"
  echo "  export WINDOWS_HOST=192.168.x.x"
  echo "  export WINDOWS_USER=<windows-user>"
  exit 1
fi

if [[ -z "${WINDOWS_SSH_KEY:-}" && -f "$HOME/.ssh/id_ed25519_nopass" ]]; then
  export WINDOWS_SSH_KEY="$HOME/.ssh/id_ed25519_nopass"
fi

export DEFAULT_EXECUTION_MODE="${DEFAULT_EXECUTION_MODE:-cursor}"
export WINDOWS_CURSOR_TIMEOUT="${WINDOWS_CURSOR_TIMEOUT:-900}"
export WINDOWS_CURSOR_HEARTBEAT_TIMEOUT="${WINDOWS_CURSOR_HEARTBEAT_TIMEOUT:-180}"

args=("$@")
if [[ "${args[0]}" == "dispatch" ]]; then
  has_mode=0
  for arg in "${args[@]}"; do
    if [[ "$arg" == "--mode" ]]; then
      has_mode=1
      break
    fi
  done
  if [[ "$has_mode" -eq 0 ]]; then
    args+=("--mode" "cursor")
  fi
fi

python3 "$ROOT_DIR/scripts/swarm_remote.py" "${args[@]}"
