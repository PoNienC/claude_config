<#
.SYNOPSIS
    Run one fresh Codex CLI job for the dual_dev workflow (plan, audit or execute).

.DESCRIPTION
    Wraps `codex exec` so that every call:
      - starts a fresh Codex thread (no carried-over context);
      - uses a fixed sandbox per mode: plan/audit = read-only, execute = workspace-write;
      - reads its brief from a UTF-8 file through stdin (no quoting problems);
      - writes Codex's final message to -OutFile and the full run log to -OutFile.log.

    Windows fix (found 7 October 2026): Codex's Windows sandbox cannot launch
    Microsoft Store (WindowsApps) executables, so a Store-installed PowerShell 7
    makes every Codex shell command fail with
    "CreateProcessAsUserW failed: -1073283067". This script hides WindowsApps
    folders from PATH for the Codex process only; Codex then finds the MSI
    PowerShell 7 in C:\Program Files\PowerShell\7 (installed on PRIORPLAP180,
    7 October 2026) or, on a machine without it, Windows PowerShell 5.1.
    Nothing outside this process changes. Kept as a safety net: a shell
    started from the Store pwsh puts the Store folder first on PATH.

.EXAMPLE
    & run_codex.ps1 -Mode plan -Repo C:\dev\geoai-core `
        -BriefFile C:\dev\geoai-core\.ai\tasks\T001_x\codex\plan_brief.md `
        -OutFile   C:\dev\geoai-core\.ai\tasks\T001_x\codex\plan_raw.md
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('plan', 'audit', 'execute')][string]$Mode,
    [Parameter(Mandatory)][string]$Repo,
    [Parameter(Mandatory)][string]$BriefFile,
    [Parameter(Mandatory)][string]$OutFile,
    [ValidateSet('low', 'medium', 'high', 'xhigh')][string]$Effort = 'high',
    # Empty = the model set in Codex's own config.toml (shared with the Codex app).
    [ValidatePattern('^$|^[A-Za-z0-9][A-Za-z0-9._:-]*$')][string]$Model = ''
)
$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$codexCmd = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codexCmd) {
    throw 'codex CLI not found on PATH. Install it with: npm install -g @openai/codex'
}
foreach ($p in @($Repo, $BriefFile)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "Not found: $p" }
}

$sandbox = if ($Mode -eq 'execute') { 'workspace-write' } else { 'read-only' }
$modelArgs = @()
$modelLabel = $Model
if ($Model) {
    $modelArgs = @('--model', $Model)
} else {
    # Report the config default; Codex itself reads it, nothing is passed.
    $codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
    $cfg = Join-Path $codexHome 'config.toml'
    $hit = if (Test-Path -LiteralPath $cfg) { Select-String -LiteralPath $cfg -Pattern '^\s*model\s*=\s*"([^"]+)"' | Select-Object -First 1 } else { $null }
    $modelLabel = if ($hit) { "default($($hit.Matches[0].Groups[1].Value))" } else { 'default' }
}
$logFile = "$OutFile.log"
$outDir = Split-Path -Parent $OutFile
if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null
}
if (Test-Path -LiteralPath $OutFile) { Remove-Item -LiteralPath $OutFile -Force }

$brief = Get-Content -LiteralPath $BriefFile -Raw -Encoding UTF8
$started = Get-Date
$savedPath = $env:PATH
$savedXdg = $env:XDG_CONFIG_HOME
# Codex's sandbox accounts cannot read ~/.config (kept private: tools store
# tokens there), so git warns "unable to access .config/git/ignore" on every
# command. Point git at a readable copy of the global ignore file instead
# (found 12 October 2026). Nothing else in ~/.config is copied.
$xdg = Join-Path $env:USERPROFILE '.codex\xdg_config'
$userIgnore = Join-Path $env:USERPROFILE '.config\git\ignore'
New-Item -ItemType Directory -Force -Path (Join-Path $xdg 'git') | Out-Null
if (Test-Path -LiteralPath $userIgnore) { Copy-Item -LiteralPath $userIgnore -Destination (Join-Path $xdg 'git\ignore') -Force }
try {
    # Hide WindowsApps (Store PowerShell 7 and other packaged aliases) from the Codex child only.
    $env:PATH = ($env:PATH -split ';' | Where-Object { $_ -and $_ -notmatch '\\WindowsApps(\\|$)' }) -join ';'
    $env:XDG_CONFIG_HOME = $xdg
    $brief | & $codexCmd.Source exec --sandbox $sandbox -C $Repo @modelArgs -c "model_reasoning_effort=`"$Effort`"" -o $OutFile - *> $logFile
    $exitCode = $LASTEXITCODE
}
finally {
    $env:PATH = $savedPath
    $env:XDG_CONFIG_HOME = $savedXdg
}
$secs = [int]((Get-Date) - $started).TotalSeconds

# Usage line (printed on every outcome): tokens for this call from the log,
# plus plan limits from the sibling codex_usage skill (read-only, ~1.5 s).
$logText = if (Test-Path -LiteralPath $logFile) { Get-Content -LiteralPath $logFile -Raw -Encoding UTF8 } else { '' }
# Codex prints "tokens used" then the number on stderr; the final reply (stdout)
# can land between them, so take the last number-only line after the marker.
$tokens = 'unknown'
$logLines = $logText -split "\r?\n"
$marker = [Array]::LastIndexOf($logLines, 'tokens used')
if ($marker -ge 0) {
    for ($j = $marker + 1; $j -lt $logLines.Count; $j++) {
        if ($logLines[$j] -match '^\s*([\d,]+)\s*$') { $tokens = $Matches[1] }
    }
}
$usageScript = Join-Path $PSScriptRoot '..\..\codex_usage\scripts\codex_usage.mjs'
$limits = if ((Test-Path -LiteralPath $usageScript) -and (Get-Command node -ErrorAction SilentlyContinue)) {
    (& node $usageScript --brief 2>$null | Select-Object -First 1)
} else { 'plan limits not checked (codex_usage skill or node missing)' }
$usageLine = "CODEX USAGE: tokens this call $tokens; $limits"

if ($exitCode -ne 0 -or -not (Test-Path -LiteralPath $OutFile)) {
    Write-Output "CODEX FAILED: mode=$Mode exit=$exitCode after ${secs}s"
    Write-Output $usageLine
    Write-Output "Log: $logFile"
    if (Test-Path -LiteralPath $logFile) { Get-Content -LiteralPath $logFile -Tail 20 }
    exit 1
}

$result = Get-Content -LiteralPath $OutFile -Raw -Encoding UTF8
# Known Windows sandbox failures (7 October 2026): Store pwsh cannot start
# (CreateProcessAsUserW), and the unelevated sandbox refuses workspace-write
# ("cannot enforce split writable root sets ... refusing to run unsandboxed").
if ("$result`n$logText" -match 'CreateProcessAsUserW|UnsupportedOperation|refusing to run unsandboxed') {
    Write-Output "CODEX DEGRADED: Codex could not run shell commands (Windows sandbox). Treat the output as untrustworthy."
    Write-Output $usageLine
    Write-Output "Output: $OutFile"
    Write-Output "Log: $logFile"
    exit 2
}

Write-Output "CODEX OK: mode=$Mode sandbox=$sandbox model=$modelLabel effort=$Effort time=${secs}s"
Write-Output $usageLine
Write-Output "Output: $OutFile"
Write-Output "Log: $logFile"
