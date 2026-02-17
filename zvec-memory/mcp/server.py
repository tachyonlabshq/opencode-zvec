#!/usr/bin/env python3
"""MCP server entrypoint for zvec-memory.

Exposes tools for storing, querying, pruning, and inspecting hybrid memory.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parent))
    from memory_core import create_store  # type: ignore
else:
    from .memory_core import create_store


def _normalize_scope(scope: str) -> str:
    scope = (scope or "both").strip().lower()
    if scope not in ("global", "project", "both"):
        raise ValueError("scope must be one of: global, project, both")
    return scope


def _normalize_tags(tags: Optional[Any]) -> List[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        if not tags.strip():
            return []
        try:
            parsed = json.loads(tags)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except json.JSONDecodeError:
            return [x.strip() for x in tags.split(",") if x.strip()]
    if isinstance(tags, list):
        return [str(x).strip() for x in tags if str(x).strip()]
    return [str(tags)]


def _store(workspace_path: Optional[str] = None):
    return create_store(workspace_path=workspace_path)


def _tool_memory_remember(
    text: str,
    scope: str = "both",
    tags: Optional[Any] = None,
    force_tier: Optional[str] = None,
    workspace_path: Optional[str] = None,
) -> Dict[str, Any]:
    if not text or not text.strip():
        raise ValueError("text is required")
    return _store(workspace_path).remember(
        text=text.strip(),
        scope=_normalize_scope(scope),
        tags=_normalize_tags(tags),
        force_tier=force_tier,
    )


def _tool_memory_query(
    query: str,
    scope: str = "both",
    top_k: int = 5,
    workspace_path: Optional[str] = None,
) -> Dict[str, Any]:
    if not query or not query.strip():
        raise ValueError("query is required")
    top_k = max(1, min(int(top_k), 50))
    return _store(workspace_path).query(
        text=query.strip(), scope=_normalize_scope(scope), top_k=top_k
    )


def _tool_memory_prune(
    scope: str = "both",
    max_age_days: int = 90,
    min_importance: int = 40,
    dry_run: bool = True,
    workspace_path: Optional[str] = None,
) -> Dict[str, Any]:
    return _store(workspace_path).prune(
        scope=_normalize_scope(scope),
        max_age_days=max(1, int(max_age_days)),
        min_importance=max(0, min(int(min_importance), 100)),
        dry_run=bool(dry_run),
    )


def _tool_memory_stats(workspace_path: Optional[str] = None) -> Dict[str, Any]:
    return _store(workspace_path).stats()


def _tool_memory_health(workspace_path: Optional[str] = None) -> Dict[str, Any]:
    store = _store(workspace_path)
    stats = store.stats()
    return {
        "ok": True,
        "workspace": stats["workspace"],
        "project_id": stats["project_id"],
        "global_path": stats["global_path"],
        "project_path": stats["project_path"],
        "openrouter_key_detected": bool(store.embedder.openrouter_key),
    }


def _run_mcp_server() -> None:
    from mcp.server.fastmcp import FastMCP  # type: ignore

    mcp = FastMCP("zvec-memory")

    @mcp.tool(description="Store text in long-term memory with tiered retention")
    def memory_remember(
        text: str,
        scope: str = "both",
        tags: Optional[Any] = None,
        force_tier: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return _tool_memory_remember(text, scope, tags, force_tier, workspace_path)

    @mcp.tool(description="Query semantically similar memory entries")
    def memory_query(
        query: str,
        scope: str = "both",
        top_k: int = 5,
        workspace_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return _tool_memory_query(query, scope, top_k, workspace_path)

    @mcp.tool(description="Prune old, low-value, unaccessed memories")
    def memory_prune(
        scope: str = "both",
        max_age_days: int = 90,
        min_importance: int = 40,
        dry_run: bool = True,
        workspace_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        return _tool_memory_prune(
            scope, max_age_days, min_importance, dry_run, workspace_path
        )

    @mcp.tool(description="Get memory statistics for global and project stores")
    def memory_stats(workspace_path: Optional[str] = None) -> Dict[str, Any]:
        return _tool_memory_stats(workspace_path)

    @mcp.tool(description="Health check for memory backend and key detection")
    def memory_health(workspace_path: Optional[str] = None) -> Dict[str, Any]:
        return _tool_memory_health(workspace_path)

    mcp.run()


def _run_cli() -> int:
    parser = argparse.ArgumentParser(description="zvec-memory MCP/CLI server")
    sub = parser.add_subparsers(dest="command")

    remember = sub.add_parser("remember", help="Store text in memory")
    remember.add_argument("text", nargs="?")
    remember.add_argument("--text", dest="text_flag", default=None)
    remember.add_argument(
        "--scope", default="both", choices=["global", "project", "both"]
    )
    remember.add_argument("--tags", default="")
    remember.add_argument("--force-tier", default=None, choices=["full", "summary"])
    remember.add_argument("--workspace-path", default=None)

    query = sub.add_parser("query", help="Query memory")
    query.add_argument("text", nargs="?")
    query.add_argument("--text", dest="text_flag", default=None)
    query.add_argument("--scope", default="both", choices=["global", "project", "both"])
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--workspace-path", default=None)

    prune = sub.add_parser("prune", help="Prune memory")
    prune.add_argument("--scope", default="both", choices=["global", "project", "both"])
    prune.add_argument("--max-age-days", type=int, default=90)
    prune.add_argument("--min-importance", type=int, default=40)
    prune.add_argument(
        "--apply", action="store_true", help="Apply changes instead of dry-run"
    )
    prune.add_argument("--workspace-path", default=None)

    stats = sub.add_parser("stats", help="Show memory stats")
    stats.add_argument("--workspace-path", default=None)

    health = sub.add_parser("health", help="Show health")
    health.add_argument("--workspace-path", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "remember":
        text = args.text_flag if args.text_flag is not None else args.text
        if not text:
            raise ValueError("remember requires text (positional or --text)")
        tags = [x.strip() for x in args.tags.split(",") if x.strip()]
        out = _tool_memory_remember(
            text=text,
            scope=args.scope,
            tags=tags,
            force_tier=args.force_tier,
            workspace_path=args.workspace_path,
        )
    elif args.command == "query":
        text = args.text_flag if args.text_flag is not None else args.text
        if not text:
            raise ValueError("query requires text (positional or --text)")
        out = _tool_memory_query(
            query=text,
            scope=args.scope,
            top_k=args.top_k,
            workspace_path=args.workspace_path,
        )
    elif args.command == "prune":
        out = _tool_memory_prune(
            scope=args.scope,
            max_age_days=args.max_age_days,
            min_importance=args.min_importance,
            dry_run=not args.apply,
            workspace_path=args.workspace_path,
        )
    elif args.command == "stats":
        out = _tool_memory_stats(args.workspace_path)
    elif args.command == "health":
        out = _tool_memory_health(args.workspace_path)
    else:
        raise ValueError(f"Unsupported command: {args.command}")

    print(json.dumps(out, indent=2, ensure_ascii=True))
    return 0


def main() -> int:
    if os.environ.get("ZVEC_MEMORY_MODE") == "cli":
        return _run_cli()

    try:
        _run_mcp_server()
        return 0
    except ModuleNotFoundError as exc:
        if "mcp" in str(exc):
            print(
                "Missing MCP dependency. Install with: python3 -m pip install -r mcp/requirements.txt"
            )
            return 2
        raise


if __name__ == "__main__":
    raise SystemExit(main())
