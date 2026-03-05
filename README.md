# opencode-zvec

Zero-config OpenCode plugin that auto-registers and runs the `zvec-memory` MCP server.

## Install

Add this to your OpenCode config:

```json
{
  "plugin": ["opencode-zvec"]
}
```

That is the only required config. OpenCode resolves npm plugins from package name, and `opencode-zvec` auto-creates `mcp.zvec-memory`.

Optional: install locally for development with `npm install opencode-zvec`.

## What It Does

- Injects `mcp.zvec-memory` automatically through the OpenCode plugin `config` hook.
- Works on macOS, Linux, and Windows.
- Detects Python (`python3`, `python`, `py -3`) and bootstraps a virtualenv on first run.
- Installs Python dependencies once and reuses a cached runtime.
- Runs the bundled MCP server from this package.

## Runtime Paths

- macOS cache: `~/Library/Caches/opencode-zvec`
- Linux cache: `${XDG_CACHE_HOME:-~/.cache}/opencode-zvec`
- Windows cache: `%LOCALAPPDATA%\opencode-zvec`

## Optional Environment Variables

- `ZVEC_INSTALL_PROFILE=minimal|full` (default: `minimal`)
- `ZVEC_PYTHON=/path/to/python`
- `ZVEC_CACHE_DIR=/custom/cache/dir`
- `ZVEC_FORCE_REINSTALL=1`
- `ZVEC_SKIP_PIP_UPGRADE=1`
- `ZVEC_AUTO_REGISTER_MCP=0` (disable auto MCP injection)

## Local Development

```bash
npm ci
npm run build
npm run test:smoke
npm run test:compat
```

## Security Checks

```bash
npm run security:node
npm run security:python
```

`security:python` runs `pip-audit` against `zvec-memory/mcp/requirements-minimal.txt`.

## Publish to npm

1. Ensure `package.json` version is bumped.
2. Run quality + security gates:
   - `npm test`
   - `npm audit --audit-level=low`
   - secret scan with `rg` for keys/tokens/private keys
   - `npm pack --dry-run`
3. Ensure npm auth:
   - `npm whoami`
   - `npm profile get "two-factor auth"`
4. Publish:
   - `npm publish --access public`
5. Verify:
   - `npm view opencode-zvec version`
   - `npm view opencode-zvec dist-tags`

Manual publish:

```bash
npm test
npm audit --audit-level=low
npm pack --dry-run
npm publish --access public
```
