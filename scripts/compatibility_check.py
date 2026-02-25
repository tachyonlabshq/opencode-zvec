#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Dict


REQUIRED_HELPERS = (
    "_tool_memory_remember",
    "_tool_memory_query",
    "_tool_memory_prune",
    "_tool_memory_stats",
    "_tool_memory_health",
)

EXPECTED_TOP_LEVEL_KEYS = {
    "health": {
        "ok",
        "workspace",
        "project_id",
        "global_path",
        "project_path",
        "openrouter_key_detected",
    },
    "remember": {"stored", "importance_score"},
    "query": {"query", "embedding_source", "results"},
    "stats": {
        "workspace",
        "project_id",
        "global_path",
        "project_path",
        "global",
        "project",
    },
    "prune": {"dry_run", "removed_count", "removed", "max_age_days", "min_importance"},
}


def _load_module(path: Path, label: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"zvec_memory_{label}", str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _signature_map(module: ModuleType) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name in REQUIRED_HELPERS:
        fn = getattr(module, name, None)
        if fn is None or not callable(fn):
            raise RuntimeError(f"Missing required helper: {name}")
        signature = inspect.signature(fn)
        params = []
        for param in signature.parameters.values():
            default_value = (
                None if param.default is inspect._empty else repr(param.default)
            )
            params.append(
                {
                    "name": param.name,
                    "kind": str(param.kind),
                    "default": default_value,
                }
            )
        out[name] = params
    return out


def _run_json(server: Path, args: list[str], env: Dict[str, str]) -> Dict[str, Any]:
    cmd = [sys.executable, str(server), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON output for command: {' '.join(cmd)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        ) from exc


def _assert_keys(payload: Dict[str, Any], required: set[str], label: str) -> None:
    missing = sorted(required - set(payload.keys()))
    if missing:
        raise RuntimeError(f"{label} missing keys: {', '.join(missing)}")


def _run_smoke(server: Path, label: str) -> Dict[str, Dict[str, Any]]:
    with tempfile.TemporaryDirectory(prefix="zvec-memory-compat-") as tmp_dir:
        tmp_root = Path(tmp_dir)
        home_dir = tmp_root / "home"
        workspace = tmp_root / "workspace"
        home_dir.mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env.update(
            {
                "ZVEC_MEMORY_MODE": "cli",
                "ZVEC_FORCE_JSON_BACKEND": "1",
                "HOME": str(home_dir),
                "OPENCODE_WORKSPACE": str(workspace),
                "PYTHONUTF8": "1",
            }
        )

        base_args = ["--workspace-path", str(workspace)]

        health = _run_json(server, ["health", *base_args], env)
        remember = _run_json(
            server,
            [
                "remember",
                "--text",
                "Decision: Use pnpm for this repository because it keeps workspace installs consistent.",
                "--scope",
                "both",
                "--tags",
                "preference,decision,tooling",
                *base_args,
            ],
            env,
        )
        query = _run_json(
            server,
            [
                "query",
                "--text",
                "which package manager do we use",
                "--scope",
                "both",
                "--top-k",
                "5",
                *base_args,
            ],
            env,
        )
        stats = _run_json(server, ["stats", *base_args], env)
        prune = _run_json(
            server,
            [
                "prune",
                "--scope",
                "both",
                "--max-age-days",
                "90",
                "--min-importance",
                "40",
                *base_args,
            ],
            env,
        )

        snapshots = {
            "health": health,
            "remember": remember,
            "query": query,
            "stats": stats,
            "prune": prune,
        }

        for name, payload in snapshots.items():
            _assert_keys(payload, EXPECTED_TOP_LEVEL_KEYS[name], f"{label}:{name}")

        if not remember.get("stored", False):
            raise RuntimeError(f"{label}: remember did not store the test record")
        if not isinstance(query.get("results"), list):
            raise RuntimeError(f"{label}: query.results is not a list")

        return snapshots


def _compare_schema(name: str, left: Dict[str, Any], right: Dict[str, Any]) -> None:
    left_keys = sorted(left.keys())
    right_keys = sorted(right.keys())
    if left_keys != right_keys:
        raise RuntimeError(
            f"Top-level schema mismatch for '{name}': workspace={left_keys}, installed={right_keys}"
        )


def _parse_args() -> argparse.Namespace:
    root_dir = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Validate zvec-memory backward compatibility"
    )
    parser.add_argument(
        "--workspace-server",
        default=str(root_dir / "zvec-memory" / "mcp" / "server.py"),
        help="Path to workspace server.py",
    )
    parser.add_argument(
        "--installed-server",
        default=str(
            Path.home() / ".agents" / "skills" / "zvec-memory" / "mcp" / "server.py"
        ),
        help="Path to installed server.py",
    )
    parser.add_argument(
        "--skip-installed-check",
        action="store_true",
        help="Only validate workspace server",
    )
    parser.add_argument(
        "--require-installed-check",
        action="store_true",
        help="Fail if installed server path does not exist",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace_server = Path(args.workspace_server).expanduser().resolve()
    installed_server = Path(args.installed_server).expanduser().resolve()

    if not workspace_server.exists():
        raise SystemExit(f"Workspace server not found: {workspace_server}")

    workspace_module = _load_module(workspace_server, "workspace")
    workspace_signatures = _signature_map(workspace_module)
    workspace_smoke = _run_smoke(workspace_server, "workspace")
    print("workspace: signature and smoke checks passed")

    if args.skip_installed_check:
        print("installed: skipped")
        return 0

    if not installed_server.exists():
        message = f"installed: not found at {installed_server}"
        if args.require_installed_check:
            raise RuntimeError(message)
        print(message)
        return 0

    installed_module = _load_module(installed_server, "installed")
    installed_signatures = _signature_map(installed_module)
    if workspace_signatures != installed_signatures:
        raise RuntimeError("Function signature mismatch against installed server")

    installed_smoke = _run_smoke(installed_server, "installed")
    for key in EXPECTED_TOP_LEVEL_KEYS:
        _compare_schema(key, workspace_smoke[key], installed_smoke[key])

    print(f"installed: signature and smoke checks passed ({installed_server})")
    print("compatibility: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
