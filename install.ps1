$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $Root 'runtime\scripts\vibe_python.ps1')
Assert-VibeLauncherArguments -Arguments $args
$ConfigHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
for ($i = 0; $i -lt $args.Count; $i++) {
    if ($args[$i] -eq '--codex-home') {
        if (($i + 1) -ge $args.Count -or -not $args[$i + 1] -or $args[$i + 1].StartsWith('--')) { throw '--codex-home requires a path.' }
        $ConfigHome = $args[$i + 1]
    }
    elseif ($args[$i] -like '--codex-home=*') { $ConfigHome = $args[$i].Substring('--codex-home='.Length) }
}
if (-not $ConfigHome) { throw '--codex-home requires a path.' }
$BootstrapPython = Resolve-VibePython -ConfigHome $ConfigHome -Bootstrap
$env:PYTHONUTF8 = '1'
$Python = Invoke-VibePython -Python $BootstrapPython -Arguments @('-B', "$Root\scripts\bootstrap_vibe_python.py", '--codex-home', $ConfigHome, '--requirements', "$Root\runtime\scripts\requirements.txt", '--env-name', $(if ($env:VIBE_CONDA_ENV) { $env:VIBE_CONDA_ENV } else { 'vibe-coding' }), '--print-python') -CaptureOutput
if ($script:VibeExitCode -ne 0) { exit $script:VibeExitCode }
Invoke-VibePython -Python $Python -Arguments (@('-B', "$Root\scripts\global_installer.py", 'install') + $args)
exit $script:VibeExitCode
