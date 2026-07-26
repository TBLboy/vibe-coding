$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
py -3 "$Root\scripts\global_installer.py" install @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
