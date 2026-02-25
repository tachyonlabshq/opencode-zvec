#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


MIN_PYTHON = (3, 10)


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _check_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        version = ".".join(str(x) for x in MIN_PYTHON)
        raise SystemExit(f"Python {version}+ is required")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install and validate zvec-memory")
    parser.add_argument(
        "--profile",
        choices=["full", "minimal"],
        default="full",
        help="Install profile: full includes local embeddings, minimal is faster",
    )
    parser.add_argument(
        "--skip-pip-upgrade",
        action="store_true",
        help="Skip 'python -m pip install --upgrade pip'",
    )
    parser.add_argument(
        "--skip-health",
        action="store_true",
        help="Skip CLI health check",
    )
    parser.add_argument(
        "--skip-compat",
        action="store_true",
        help="Skip installed-skill compatibility check",
    )
    parser.add_argument(
        "--installed-server",
        default=str(
            Path.home() / ".agents" / "skills" / "zvec-memory" / "mcp" / "server.py"
        ),
        help="Path to the currently installed zvec-memory server.py",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _check_python_version()

    script_dir = Path(__file__).resolve().parent
    root_dir = script_dir.parent

    req_map = {
        "full": root_dir / "zvec-memory" / "mcp" / "requirements.txt",
        "minimal": root_dir / "zvec-memory" / "mcp" / "requirements-minimal.txt",
    }
    req_file = req_map[args.profile]
    cli_file = root_dir / "zvec-memory" / "scripts" / "memory_cli.py"
    compat_file = root_dir / "scripts" / "compatibility_check.py"
    mcp_example = root_dir / "MCP_CONFIG.example.jsonc"

    if not req_file.exists():
        raise SystemExit(f"Missing requirements file: {req_file}")
    if not cli_file.exists():
        raise SystemExit(f"Missing CLI helper: {cli_file}")
    if not compat_file.exists():
        raise SystemExit(f"Missing compatibility checker: {compat_file}")

    print("[1/4] Installing dependencies")
    if not args.skip_pip_upgrade:
        _run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], root_dir)
    _run([sys.executable, "-m", "pip", "install", "-r", str(req_file)], root_dir)

    print("[2/4] Running health check")
    if args.skip_health:
        print("Skipped health check")
    else:
        _run([sys.executable, str(cli_file), "health"], root_dir)

    print("[3/4] Running compatibility check")
    if args.skip_compat:
        print("Skipped compatibility check")
    else:
        _run(
            [
                sys.executable,
                str(compat_file),
                "--installed-server",
                args.installed_server,
            ],
            root_dir,
        )

    print("[4/4] Setup complete")
    print("")
    print("Next step: add MCP config from:")
    print(f"  {mcp_example}")
    print("")
    print("Typical OpenCode config location:")
    print("  ~/.config/opencode/opencode.json (macOS/Linux)")
    print("  %APPDATA%\\opencode\\opencode.json (Windows)")
    print("")
    print("Optional verification commands:")
    print(
        f'  {sys.executable} {cli_file} remember --text "Use pnpm for this project" --scope both --tags preference'
    )
    print(
        f'  {sys.executable} {cli_file} query --text "what package manager do we use" --scope both'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
