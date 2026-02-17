# zvec-memory API Reference

This document defines the interfaces and behavior for the bundled `zvec-memory` memory engine and MCP server.

## Components

- `mcp/server.py`: MCP server and CLI mode entrypoint
- `mcp/memory_core.py`: storage, embedding, scoring, retrieval, pruning logic
- `scripts/memory_cli.py`: convenience wrapper for CLI mode

## Memory Scope Model

- `global`: `~/.opencode/memory/global`
- `project`: `<workspace>/.memory/zvec-memory`
- `both`: write/query both stores and merge results

Workspace resolution order:

1. Explicit `workspace_path` argument
2. `OPENCODE_WORKSPACE`
3. `OPENCODE_PROJECT_ROOT`
4. `PWD`
5. Current process working directory

## Storage Tiering Policy

Importance thresholds:

- Keep threshold: `40`
- Full-text threshold: `70`

Result:

- `score < 40`: skip storage
- `40 <= score < 70`: store `summary`
- `score >= 70`: store `full`

Optional override:

- `force_tier = full | summary`

## Embedding Routing Policy

Order:

1. OpenRouter embedding API
2. Local sentence-transformers
3. Deterministic hashed embedding fallback

OpenRouter key detection:

1. `ZVEC_OPENROUTER_KEY`
2. `OPENROUTER_API_KEY`
3. OpenCode auth store (best-effort discovery)

Default models:

- OpenRouter: `openai/text-embedding-3-small`
- Local: `sentence-transformers/all-MiniLM-L6-v2`
- Target embedding dimension (internal): `384`

## MCP Tools

### `memory_remember`

Store content in long-term memory.

Input:

- `text: string` (required)
- `scope: global|project|both` (default `both`)
- `tags: string|array` (optional)
- `force_tier: full|summary` (optional)
- `workspace_path: string` (optional)

Output includes:

- `stored: bool`
- `importance_score: int`
- `tier: full|summary` when stored
- `ids: {global?: string, project?: string}`
- `embedding_source: openrouter|local|hashed|empty`

### `memory_query`

Semantic search across selected scope.

Input:

- `query: string` (required)
- `scope: global|project|both` (default `both`)
- `top_k: int` (default `5`, capped to `50`)
- `workspace_path: string` (optional)

Output:

- `query`
- `embedding_source`
- `results[]` sorted by score desc with:
  - `id`, `score`, `scope`, `project_id`, `tier`, `importance_score`
  - `summary`, `text`, `tags`, `created_at`, `last_accessed`, `access_count`

### `memory_prune`

Remove stale, low-value, unaccessed items.

Input:

- `scope: global|project|both` (default `both`)
- `max_age_days: int` (default `90`)
- `min_importance: int` (default `40`)
- `dry_run: bool` (default `true`)
- `workspace_path: string` (optional)

Prune condition (all required):

- `importance_score < min_importance`
- `last_accessed < now - max_age_days`
- `access_count == 0`

Output:

- `removed_count`
- `removed[]` with id/scope/importance/last_accessed
- effective prune parameters

### `memory_stats`

Returns counts and quality metrics for global and project stores.

Output:

- `workspace`, `project_id`
- `global_path`, `project_path`
- `global` + `project` summary objects:
  - `count`, `full`, `summary`, `average_importance`

### `memory_health`

Health check for path and key visibility.

Output:

- `ok: true`
- `workspace`, `project_id`, `global_path`, `project_path`
- `openrouter_key_detected: bool`

## CLI Mode

Run server in local CLI mode (without MCP client):

```bash
ZVEC_MEMORY_MODE=cli python3 mcp/server.py stats
ZVEC_MEMORY_MODE=cli python3 mcp/server.py remember "Use uv for tooling" --scope both --tags preference,tooling
ZVEC_MEMORY_MODE=cli python3 mcp/server.py query "what tooling do we use" --scope both --top-k 5
```

Helper wrapper:

```bash
python3 scripts/memory_cli.py stats
```

## Environment Variables

- `ZVEC_OPENROUTER_KEY`: explicit key override
- `OPENROUTER_API_KEY`: default OpenRouter key source
- `ZVEC_OPENROUTER_EMBED_MODEL`: override OR embedding model
- `ZVEC_LOCAL_EMBED_MODEL`: override local ST model name
- `ZVEC_FORCE_JSON_BACKEND=1`: disable zvec backend and use JSON backend only
- `OPENCODE_WORKSPACE`: workspace root hint
- `OPENCODE_PROJECT_ROOT`: workspace root hint fallback
- `ZVEC_MEMORY_MODE=cli`: run CLI mode instead of MCP mode

## Backend Behavior

Backend selection:

- Uses zvec backend when `zvec` import succeeds and JSON-forced mode is not enabled
- Falls back to JSON backend automatically on missing/unsupported zvec runtime

zvec backend details:

- Stores vectors in zvec collection
- Stores authoritative metadata in JSON sidecar (`metadata.json`)
- If zvec query API shape mismatches runtime, falls back to cosine over sidecar vectors

## Notes on `.memory` Folder and Builds

- `.memory` is a hidden runtime data directory in project root.
- It is not imported by compilers/build tools by default.
- It should not affect builds unless custom scripts recursively include hidden directories.
- Recommended: add `.memory/` to project `.gitignore`.
