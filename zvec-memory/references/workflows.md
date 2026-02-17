# zvec-memory Workflows

## 1) Install and Smoke Test

Install dependencies:

```bash
python3 -m pip install -r ~/.agents/skills/zvec-memory/mcp/requirements.txt
```

Run quick health check in CLI mode:

```bash
python3 ~/.agents/skills/zvec-memory/scripts/memory_cli.py health
```

Expected output includes:

- `ok: true`
- `global_path` under `~/.opencode/memory/global`
- `project_path` under `<workspace>/.memory/zvec-memory`

## 2) Write and Query Memory

Store important preference across scopes:

```bash
python3 ~/.agents/skills/zvec-memory/scripts/memory_cli.py remember "Use pnpm for this monorepo" --scope both --tags preference,tooling
```

Store ephemeral note as forced summary:

```bash
python3 ~/.agents/skills/zvec-memory/scripts/memory_cli.py remember "Temporary debug notes" --scope project --force-tier summary --tags noise
```

Query:

```bash
python3 ~/.agents/skills/zvec-memory/scripts/memory_cli.py query "which package manager do we use" --scope both --top-k 5
```

## 3) Inspect Store Health

```bash
python3 ~/.agents/skills/zvec-memory/scripts/memory_cli.py stats
```

Use stats to verify:

- Full vs summary distribution
- Memory growth across scopes
- Average importance trends

## 4) Prune Safely

Dry-run first:

```bash
python3 ~/.agents/skills/zvec-memory/scripts/memory_cli.py prune --scope both --max-age-days 90 --min-importance 40
```

Apply prune when results look correct:

```bash
python3 ~/.agents/skills/zvec-memory/scripts/memory_cli.py prune --scope both --max-age-days 90 --min-importance 40 --apply
```

## 5) Add MCP Entry Manually

Do this yourself in OpenCode config when ready (this skill does not edit config files automatically):

```json
{
  "mcp": {
    "zvec-memory": {
      "type": "local",
      "command": [
        "python3",
        "./zvec-memory/mcp/server.py"
      ]
    }
  }
}
```

After restarting OpenCode, tools should be available:

- `memory_remember`
- `memory_query`
- `memory_prune`
- `memory_stats`
- `memory_health`

## 6) Operational Best Practices

- Add `.memory/` to repo `.gitignore`
- Prefer `scope=both` for persistent preferences and conventions
- Use project-only scope for transient implementation details
- Run prune dry-runs periodically, then apply
- Keep fallback behavior enabled for resilience
