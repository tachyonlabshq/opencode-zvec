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
  .github/
    workflows/
      ci.yml
  .gitignore
  README.md
  MCP_CONFIG.example.jsonc
  WORKLOG.md
  scripts/
    setup_common.py
    compatibility_check.py
    setup-macos.sh
    setup-linux.sh
    setup-windows.ps1
  zvec-memory/
    SKILL.md
    mcp/
      server.py
      memory_core.py
      requirements.txt
      requirements-minimal.txt
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

Each script installs dependencies, runs health checks, runs backward-compatibility checks against an installed `zvec-memory` (if present), and prints next-step MCP config instructions.

Optional setup flags (supported by all scripts):

- `--profile minimal` for faster install (`zvec` + `mcp` only)
- `--skip-pip-upgrade` to skip pip self-upgrade
- `--skip-health` to skip runtime health check
- `--skip-compat` to skip installed-skill compatibility validation

Examples:

```bash
./scripts/setup-macos.sh --profile minimal
./scripts/setup-linux.sh --profile full
```

Manual setup (all platforms):

```bash
python3 "./scripts/setup_common.py" --profile full
```

Run compatibility smoke tests directly:

```bash
python3 "./scripts/compatibility_check.py"
```

Add MCP config manually using `MCP_CONFIG.example.jsonc`.

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
- Runtime artifacts are ignored via `.gitignore` (`.memory/`, caches, venvs).
- Keep dependency versions in `zvec-memory/mcp/requirements.txt` pinned or range-limited as desired.
