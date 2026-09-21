$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\vibe_python.ps1')
Assert-VibeLauncherArguments -Arguments $args
$ConfigHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME '.codex' }
$Forward = @()
for ($Index = 0; $Index -lt $args.Count; $Index++) {
    if ($args[$Index] -eq '--codex-home') {
        $Index++
        if ($Index -ge $args.Count -or -not $args[$Index] -or $args[$Index].StartsWith('--')) { throw '--codex-home requires a path.' }
        $ConfigHome = $args[$Index]
    } elseif ($args[$Index] -like '--codex-home=*') {
        $ConfigHome = $args[$Index].Substring('--codex-home='.Length)
        if (-not $ConfigHome) { throw '--codex-home requires a path.' }
    } else { $Forward += $args[$Index] }
}
$Python = Resolve-VibePython -ConfigHome $ConfigHome
$env:CODEX_HOME = $ConfigHome
$env:PYTHONUTF8 = '1'
Invoke-VibePython -Python $Python -Arguments (@('-B', (Join-Path $PSScriptRoot 'scripts\vibe.py')) + $Forward)
exit $script:VibeExitCode
