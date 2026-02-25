# Work Log

## 2026-02-25

### Scope

- Hardened repository for GitHub publication and repeatable installs.
- Added compatibility validation against the currently installed `zvec-memory` MCP server.

### Implemented

1. Installer consolidation
   - Added shared installer: `scripts/setup_common.py`
   - Updated wrappers to call shared installer:
     - `scripts/setup-macos.sh`
     - `scripts/setup-linux.sh`
     - `scripts/setup-windows.ps1`

2. Faster install profile
   - Added `zvec-memory/mcp/requirements-minimal.txt` (`zvec` + `mcp` only)
   - Kept `zvec-memory/mcp/requirements.txt` as backward-compatible full profile

3. Backward compatibility test harness
   - Added `scripts/compatibility_check.py`
   - Validates helper function signatures and CLI smoke schema parity against installed server when available

4. GitHub hardening
   - Added `.gitignore` for runtime artifacts/caches/venvs
   - Added CI workflow: `.github/workflows/ci.yml`
   - Removed tracked cache artifact: `zvec-memory/mcp/__pycache__/memory_core.cpython-311.pyc`

5. Documentation refresh
   - Updated `README.md` install/testing flow
   - Updated `zvec-memory/SKILL.md` quick start to use portable relative paths
   - Updated `zvec-memory/references/workflows.md` commands and compatibility step
   - Updated `zvec-memory/references/api_reference.md` with install profiles and runtime env vars

## 2026-02-16

### Scope

- Built and validated a production-ready `zvec-memory` skill for OpenCode as a separate package (no OpenCode core file edits).
- Prepared a publish-ready distribution folder at:
  - `./ZVEC Opencode`

### Implemented

1. Skill bundle
   - `zvec-memory/SKILL.md`
   - `zvec-memory/references/api_reference.md`
   - `zvec-memory/references/architecture.md`
   - `zvec-memory/references/workflows.md`

2. MCP server
   - `zvec-memory/mcp/server.py`
   - `zvec-memory/mcp/memory_core.py`
   - `zvec-memory/mcp/requirements.txt`

3. CLI helper
   - `zvec-memory/scripts/memory_cli.py`

4. Publish artifacts
   - `README.md`
   - `MCP_CONFIG.example.jsonc`
   - `WORKLOG.md`

### Core Behaviors Confirmed

- Hybrid memory scope:
  - global: `~/.opencode/memory/global`
  - project: `<workspace>/.memory/zvec-memory`
- Embedding router:
  - OpenRouter key auto-detect (`ZVEC_OPENROUTER_KEY`, `OPENROUTER_API_KEY`, OpenCode auth store)
  - fallback to local sentence-transformers
  - fallback to deterministic hashed embeddings
- Retention policy:
  - store full for high-importance
  - store summary for medium-importance
  - skip low-importance
- Pruning:
  - dry-run and apply modes
  - age + importance + access count logic
  - auto-prune when storage/item thresholds are exceeded

### Testing Performed

- Python compile checks for all server/CLI modules
- Skill structure validation (`quick_validate.py`)
- End-to-end CLI smoke tests:
  - `health`
  - `remember`
  - `query`
  - `prune`
  - `stats`

### Packaging Notes

- Removed transient `__pycache__` artifacts from publish folder.
- `.memory` design is hidden runtime data and does not affect standard builds/compiles.

### OpenRouter Auth Troubleshooting Update

- Diagnosed OpenRouter behavior:
  - environment key in `OPENROUTER_API_KEY` returned 401 `User not found` on embeddings.
  - key in the OpenCode auth store succeeded for embeddings.
- Implemented resilience fix in `zvec-memory/mcp/memory_core.py`:
  - discover multiple candidate OpenRouter keys (env + auth store)
  - try keys in order for embeddings
  - skip unauthorized keys (401/403) and continue
  - cache the first working key for subsequent requests
- Verified runtime now uses `embedding_source: "openrouter"` successfully.
- Synced updated file into publish bundle copy.

### Cross-Platform Setup Scripts

- Added quick setup scripts for all requested platforms in publish bundle:
  - `scripts/setup-macos.sh`
  - `scripts/setup-linux.sh`
  - `scripts/setup-windows.ps1`
- Scripts perform:
  - dependency install from `zvec-memory/mcp/requirements.txt`
  - memory health check via `zvec-memory/scripts/memory_cli.py`
  - print next-step MCP config guidance
- Updated `README.md` with one-command setup instructions for macOS, Linux, and Windows.
