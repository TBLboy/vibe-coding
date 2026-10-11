$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\vibe_python.ps1')
Assert-VibeLauncherArguments -Arguments $args
$ConfigHome = if ($env:OPENCODE_CONFIG_DIR) { $env:OPENCODE_CONFIG_DIR }
    elseif (Test-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'vibe-python')) { Split-Path $PSScriptRoot -Parent }
    else { Join-Path $HOME '.config\opencode' }
$Forward = @()
for ($Index = 0; $Index -lt $args.Count; $Index++) {
    if ($args[$Index] -eq '--config-home') {
        $Index++
        if ($Index -ge $args.Count -or -not $args[$Index] -or $args[$Index].StartsWith('--')) { throw '--config-home requires a path.' }
        $ConfigHome = $args[$Index]
    } elseif ($args[$Index] -like '--config-home=*') {
        $ConfigHome = $args[$Index].Substring('--config-home='.Length)
        if (-not $ConfigHome) { throw '--config-home requires a path.' }
    } else { $Forward += $args[$Index] }
}
$Python = Resolve-VibePython -ConfigHome $ConfigHome
$env:OPENCODE_CONFIG_DIR = $ConfigHome
$env:PYTHONUTF8 = '1'
Invoke-VibePython -Python $Python -Arguments (@('-B', (Join-Path $PSScriptRoot 'scripts\vibe.py')) + $Forward)
exit $script:VibeExitCode
