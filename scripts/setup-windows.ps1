$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")

function Get-PythonCommand {
  if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3") }
  if (Get-Command python -ErrorAction SilentlyContinue) { return @("python") }
  if (Get-Command python3 -ErrorAction SilentlyContinue) { return @("python3") }
  throw "Python 3.10+ not found. Install Python first."
}

$PyCommand = Get-PythonCommand
$PythonExe = $PyCommand[0]
$PythonArgs = @()
if ($PyCommand.Length -gt 1) {
  $PythonArgs = $PyCommand[1..($PyCommand.Length - 1)]
}

$SetupScript = Join-Path $RootDir "scripts\setup_common.py"
& $PythonExe @PythonArgs $SetupScript @args

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
