# ZVEC Opencode

Production-ready OpenCode memory extension using zvec + MCP + skill packaging.

## What This Includes

- `zvec-memory/` skill bundle for OpenCode
- Hybrid memory scope:
  - Global: `~/.opencode/memory/global`
  - Project-local: `<workspace>/.memory/zvec-memory`
- Tiered retention:
  - High-value interactions stored in full
  - Medium-value interactions stored as compressed summaries
  - Low-value interactions skipped
- Automatic key detection for OpenRouter embeddings (`OPENROUTER_API_KEY` and OpenCode auth store)
- Fallbacks:
  - OpenRouter -> local sentence-transformers -> deterministic hashed embeddings

## Folder Layout

```text
ZVEC Opencode/
  README.md
  MCP_CONFIG.example.jsonc
  WORKLOG.md
  scripts/
    setup-macos.sh
    setup-linux.sh
    setup-windows.ps1
  zvec-memory/
    SKILL.md
    mcp/
      server.py
      memory_core.py
      requirements.txt
    scripts/
      memory_cli.py
    references/
      api_reference.md
      architecture.md
      workflows.md
```

## Install

### Quick Setup Scripts (Recommended)

- macOS:

```bash
chmod +x "./scripts/setup-macos.sh" && "./scripts/setup-macos.sh"
```

- Linux:

```bash
chmod +x "./scripts/setup-linux.sh" && "./scripts/setup-linux.sh"
```

- Windows (PowerShell):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup-windows.ps1
```

Each script installs dependencies, runs a health check, and prints next-step MCP config instructions.

1) Install Python dependencies:

```bash
python3 -m pip install -r "./zvec-memory/mcp/requirements.txt"
```

2) Verify health (CLI mode):

```bash
python3 "./zvec-memory/scripts/memory_cli.py" health
```

3) Add MCP config manually using `MCP_CONFIG.example.jsonc`.

## Minimal MCP Config

Use the block from `MCP_CONFIG.example.jsonc` in your OpenCode config.

## Example Commands

```bash
python3 "./zvec-memory/scripts/memory_cli.py" remember --text "Use pnpm for this monorepo" --scope both --tags preference,tooling
python3 "./zvec-memory/scripts/memory_cli.py" query --text "what package manager do we use" --scope both --top-k 5
python3 "./zvec-memory/scripts/memory_cli.py" prune --scope both --max-age-days 90 --min-importance 40
```

## Project Safety

- The project-local store is inside hidden folder `.memory/`.
- This does not affect compilers/builds in normal workflows.
- Recommended: add `.memory/` to each project `.gitignore`.

## Notes for Publishing

- This bundle is designed to be copied as-is.
- If publishing publicly, replace absolute paths in the MCP example with your repo-relative or install-relative paths.
- Keep dependency versions in `zvec-memory/mcp/requirements.txt` pinned or range-limited as desired.
