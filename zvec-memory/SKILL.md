---
name: zvec-memory
description: Long-term semantic memory for OpenCode using zvec with hybrid global and per-project stores. Use this skill for memory-aware coding sessions, recall of prior decisions, and compressed retention of low-value interactions.
---

# zvec-memory

## Overview

Use this skill to add production-grade memory to OpenCode sessions. It stores high-value interactions in full form, compresses lower-value interactions into summaries, and retrieves relevant context from both global memory and project-local memory.

This skill does not modify OpenCode config files automatically. It ships a local MCP server and scripts so setup remains explicit and reversible.

## When To Use This Skill

Trigger this skill when the user asks for:

- Better long-term memory across sessions
- Recall of prior architectural decisions, fixes, or preferences
- Hybrid memory scope (global plus project-specific)
- Automatic compression/pruning of low-value conversation history
- Semantic retrieval using vector similarity

## Behavior Model

Storage policy implemented by the bundled server:

- High-value interactions: stored in full text
- Medium-value interactions: stored as compressed summaries plus key details
- Low-value interactions: skipped
- Pruning: automatic and manual, with age/access/storage thresholds

Scope policy:

- Global memory path: `~/.opencode/memory/global`
- Project memory path: `<workspace>/.memory/zvec-memory`

The `.memory` folder is hidden and isolated; it does not affect normal project builds/compiles in standard tooling.

## Quick Start

1) Install dependencies for the bundled server:

```bash
python3 -m pip install -r ./mcp/requirements.txt
```

Fast install profile (optional):

```bash
python3 -m pip install -r ./mcp/requirements-minimal.txt
```

2) Start the MCP server directly (for local validation):

```bash
python3 ./mcp/server.py
```

3) Test via CLI helper:

```bash
python3 ./scripts/memory_cli.py remember --text "Use pnpm for this monorepo" --scope both
python3 ./scripts/memory_cli.py query --text "what package manager do we use" --scope both
python3 ./scripts/memory_cli.py stats
```

## OpenRouter + Local Embedding Strategy

Embedding routing:

- First choice: OpenRouter embeddings via detected key (`OPENROUTER_API_KEY` or OpenCode auth store)
- Fallback: local `sentence-transformers` model if installed
- Last-resort fallback: deterministic hashed embeddings to keep workflows operational

Detection is automatic; no OpenCode file edits are required.

## Recommended Integration Steps (Manual)

Because this setup is intentionally separate, add the MCP entry yourself in OpenCode config when ready. Use the docs in `references/workflows.md` for the exact snippet and verification commands.

## Built-In Resources

- `references/architecture.md`: system design and decision rationale
- `references/api_reference.md`: MCP tools, env vars, and data model
- `references/workflows.md`: install/run/test/operate runbooks
- `scripts/memory_cli.py`: local command-line utility for remember/query/prune/stats
- `mcp/server.py`: bundled MCP server entry point
