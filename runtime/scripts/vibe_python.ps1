function Assert-VibeLauncherArguments {
    param([AllowEmptyCollection()][string[]]$Arguments)
    for ($Index = 0; $Index -lt $Arguments.Count; $Index++) {
        if ($Arguments[$Index] -match '^--codex-home=[A-Za-z]$' -and ($Index + 1) -lt $Arguments.Count -and $Arguments[$Index + 1] -match '^[\\/]') {
            throw 'Ambiguous --codex-home argument: PowerShell -File may split drive-qualified equals syntax. Use --codex-home followed by a separate quoted absolute path.'
        }
    }
}

function ConvertTo-VibeNativeArgument {
    param([AllowEmptyString()][string]$Value)
    $Escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $Escaped = [regex]::Replace($Escaped, '(\\+)$', '$1$1')
    return '"' + $Escaped + '"'
}

function Invoke-VibePython {
    param([string]$Python, [AllowEmptyCollection()][string[]]$Arguments, [switch]$CaptureOutput)
    $StartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $StartInfo.FileName = $Python
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.EnvironmentVariables['PYTHONUTF8'] = '1'
    $StartInfo.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    $StartInfo.Arguments = (($Arguments | ForEach-Object { ConvertTo-VibeNativeArgument -Value $_ }) -join ' ')
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true
    if ($CaptureOutput) { $StartInfo.StandardOutputEncoding = [Text.UTF8Encoding]::new($false) }
    $Process = [Diagnostics.Process]::Start($StartInfo)
    try {
        $OutputTask = if ($CaptureOutput) { $Process.StandardOutput.ReadToEndAsync() } else { $Process.StandardOutput.BaseStream.CopyToAsync([Console]::OpenStandardOutput()) }
        $ErrorTask = $Process.StandardError.BaseStream.CopyToAsync([Console]::OpenStandardError())
        $Process.WaitForExit()
        $Captured = $OutputTask.GetAwaiter().GetResult()
        [void]$ErrorTask.GetAwaiter().GetResult()
        $script:VibeExitCode = $Process.ExitCode
        if ($CaptureOutput) { return $Captured.TrimEnd("`r", "`n") }
    } finally { $Process.Dispose() }
}

function Test-VibeInterpreter {
    param([string]$Candidate)
    if ($Candidate -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+)' -or -not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { return $false }
    try {
        Invoke-VibePython -Python $Candidate -Arguments @('-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 3)') -CaptureOutput | Out-Null
        return $script:VibeExitCode -eq 0
    } catch { return $false }
}

function Resolve-VibePython {
    param([string]$ConfigHome, [switch]$Bootstrap)
    $ConfigPath = Join-Path $ConfigHome 'vibe-python'
    $Candidate = $env:VIBE_PYTHON
    if (-not $Candidate -and (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
        $Candidate = [IO.File]::ReadAllText($ConfigPath, [Text.Encoding]::UTF8).Trim()
        if (-not $Candidate -or $Candidate.Contains("`n") -or $Candidate.Contains("`r")) { throw "Invalid interpreter configuration: $ConfigPath" }
    }
    if ($Candidate) {
        if (-not (Test-VibeInterpreter $Candidate)) { throw "Configured Vibe Python must be an absolute executable path to Python 3.11+: $Candidate" }
        return $Candidate
    }
    if (-not $Bootstrap) { throw "Missing $ConfigPath. Install Vibe or configure VIBE_PYTHON; runtime commands never create environments." }
    if ($env:VIBE_BOOTSTRAP_PYTHON) {
        if (-not (Test-VibeInterpreter $env:VIBE_BOOTSTRAP_PYTHON)) { throw 'VIBE_BOOTSTRAP_PYTHON must be an absolute executable path to Python 3.11+.' }
        return $env:VIBE_BOOTSTRAP_PYTHON
    }
    $Candidates = @($env:CONDA_PYTHON_EXE)
    $Manager = if ($env:CONDA_EXE) { $env:CONDA_EXE } else { (Get-Command conda -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source }
    if ($Manager) {
        $Directory = Split-Path -Parent $Manager
        for ($Depth = 0; $Depth -lt 3 -and $Directory; $Depth++) {
            $Candidates += Join-Path $Directory 'python.exe'
            $Directory = Split-Path -Parent $Directory
        }
    }
    foreach ($Name in @('miniforge3', 'mambaforge', 'miniconda3', 'anaconda3')) {
        $Candidates += Join-Path $HOME "$Name\python.exe"
    }
    foreach ($Name in @('python', 'python3')) {
        $Candidates += (Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1).Source
    }
    foreach ($Candidate in $Candidates) {
        if ($Candidate -and (Test-VibeInterpreter $Candidate)) { return $Candidate }
    }
    throw 'Cannot bootstrap Vibe. Install Conda and set VIBE_BOOTSTRAP_PYTHON to its absolute Python 3.11+ executable.'
}
