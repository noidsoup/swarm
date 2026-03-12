#!/usr/bin/env bash
# Run this on your Mac to set up the remote swarm client.
# Usage: bash scripts/mac-setup.sh <WINDOWS_IP>

set -euo pipefail

WINDOWS_IP="${1:-}"
WINDOWS_USER="${2:-nicho}"

if [[ -z "$WINDOWS_IP" ]]; then
    echo "Usage: bash scripts/mac-setup.sh <WINDOWS_IP> [username]"
    echo "  Example: bash scripts/mac-setup.sh 192.168.1.50 nicho"
    exit 1
fi

echo "=== Mac Setup for Remote Swarm ==="

# 1. Generate SSH key if needed
SSH_KEY="$HOME/.ssh/id_ed25519"
if [[ ! -f "$SSH_KEY" ]]; then
    echo "[1/4] Generating SSH key..."
    ssh-keygen -t ed25519 -C "mac-to-windows" -f "$SSH_KEY" -N ""
else
    echo "[1/4] SSH key already exists at $SSH_KEY"
fi

# 2. Copy key to Windows (interactive — will ask for password once)
echo "[2/4] Copying public key to Windows..."
echo "  You'll be asked for your Windows password (one time only)."
cat "$SSH_KEY.pub" | ssh "$WINDOWS_USER@$WINDOWS_IP" \
    'powershell -Command "
        \$authFile = \"C:\\ProgramData\\ssh\\administrators_authorized_keys\";
        \$key = [Console]::In.ReadLine();
        Add-Content -Path \$authFile -Value \$key;
        Write-Host \"Key added to \$authFile\"
    "'

# 3. Add SSH config entry
echo "[3/4] Adding SSH config entry..."
SSH_CONFIG="$HOME/.ssh/config"
if grep -q "Host winbox" "$SSH_CONFIG" 2>/dev/null; then
    echo "  'winbox' entry already exists in $SSH_CONFIG"
else
    cat >> "$SSH_CONFIG" <<EOF

# AI Dev Swarm remote compute
Host winbox
    HostName $WINDOWS_IP
    User $WINDOWS_USER
    IdentityFile $SSH_KEY
    LocalForward 9000 localhost:9000
    LocalForward 11434 localhost:11434
    LocalForward 3000 localhost:3000
    ServerAliveInterval 60
    ServerAliveCountMax 3
EOF
    echo "  Added 'winbox' entry to $SSH_CONFIG"
fi

# 4. Install Python deps for the remote CLI
echo "[4/4] Installing swarm-remote dependencies..."
pip3 install --user httpx rich 2>/dev/null || pip install httpx rich

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Connect to your Windows machine:"
echo "  ssh winbox"
echo ""
echo "Submit tasks from your Mac:"
echo "  python3 scripts/swarm_remote.py submit 'Build a login page'"
echo "  python3 scripts/swarm_remote.py status"
echo "  python3 scripts/swarm_remote.py gpu"
echo ""
echo "Or alias it:"
echo "  alias swarm-remote='python3 $(pwd)/scripts/swarm_remote.py'"
