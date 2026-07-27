$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
for ($i = 0; $i -lt $args.Count; $i++) {
    if ($args[$i] -eq '--codex-home' -and ($i + 1) -lt $args.Count) { $ConfigHome = $args[$i + 1] }
    elseif ($args[$i] -like '--codex-home=*') { $ConfigHome = $args[$i].Substring('--codex-home='.Length) }
}
$Python = & py -3 "$Root\scripts\bootstrap_vibe_python.py" --codex-home $ConfigHome --requirements "$Root\runtime\scripts\requirements.txt" --env-name $(if ($env:VIBE_CONDA_ENV) { $env:VIBE_CONDA_ENV } else { 'vibe-coding' }) --no-create --print-python
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $Python.Trim() "$Root\scripts\global_installer.py" uninstall @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
