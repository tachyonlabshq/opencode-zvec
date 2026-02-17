#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REQ_FILE="$ROOT_DIR/zvec-memory/mcp/requirements.txt"
CLI_FILE="$ROOT_DIR/zvec-memory/scripts/memory_cli.py"
MCP_EXAMPLE="$ROOT_DIR/MCP_CONFIG.example.jsonc"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found. Install Python 3.10+ first." >&2
  exit 1
fi

echo "[1/3] Installing dependencies from: $REQ_FILE"
python3 -m pip install -r "$REQ_FILE"

echo "[2/3] Running health check"
python3 "$CLI_FILE" health

echo "[3/3] Setup complete"
echo
echo "Next step: add MCP config from:"
echo "  $MCP_EXAMPLE"
echo
echo "Typical OpenCode config location:"
echo "  ~/.config/opencode/opencode.json"
echo
echo "Optional verification commands:"
echo "  python3 \"$CLI_FILE\" remember --text \"Use pnpm for this project\" --scope both --tags preference"
echo "  python3 \"$CLI_FILE\" query --text \"what package manager do we use\" --scope both"
