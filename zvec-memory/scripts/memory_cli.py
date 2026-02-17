#!/usr/bin/env python3
"""Convenience CLI for zvec-memory.

This wrapper runs the skill's backend in CLI mode, so users can test memory
operations without wiring MCP first.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    skill_root = Path(__file__).resolve().parent.parent
    server = skill_root / "mcp" / "server.py"

    env = os.environ.copy()
    env["ZVEC_MEMORY_MODE"] = "cli"

    cmd = [sys.executable, str(server)] + sys.argv[1:]
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
