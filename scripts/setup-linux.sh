#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 not found. Install Python 3.10+ first." >&2
  exit 1
fi

python3 "$ROOT_DIR/scripts/setup_common.py" "$@"
