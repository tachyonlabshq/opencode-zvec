$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
$ReqFile = Join-Path $RootDir "zvec-memory\mcp\requirements.txt"
$CliFile = Join-Path $RootDir "zvec-memory\scripts\memory_cli.py"
$McpExample = Join-Path $RootDir "MCP_CONFIG.example.jsonc"

function Get-PythonCommand {
  if (Get-Command py -ErrorAction SilentlyContinue) { return "py -3" }
  if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
  if (Get-Command python3 -ErrorAction SilentlyContinue) { return "python3" }
  throw "Python 3.10+ not found. Install Python first."
}

$Py = Get-PythonCommand

Write-Host "[1/3] Installing dependencies from: $ReqFile"
Invoke-Expression "$Py -m pip install -r `"$ReqFile`""

Write-Host "[2/3] Running health check"
Invoke-Expression "$Py `"$CliFile`" health"

Write-Host "[3/3] Setup complete"
Write-Host ""
Write-Host "Next step: add MCP config from:"
Write-Host "  $McpExample"
Write-Host ""
Write-Host "Typical OpenCode config location (Windows):"
Write-Host "  $env:APPDATA\opencode\opencode.json"
Write-Host ""
Write-Host "Optional verification commands:"
Write-Host "  $Py `"$CliFile`" remember --text `"Use pnpm for this project`" --scope both --tags preference"
Write-Host "  $Py `"$CliFile`" query --text `"what package manager do we use`" --scope both"
