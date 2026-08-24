<#
.SYNOPSIS
    Backs up irreplaceable PERSONAL Claude data to a local second folder.

.DESCRIPTION
    Protects against the failure mode that actually happens: the Claude
    Desktop app breaking, a failed repair, or a reinstall wiping data.

    SCOPE: personal account only (~/.claude and %APPDATA%\Claude).
    The work seat (~/.claude-work) is version-controlled in its own git
    repo and is deliberately NOT copied here.

    Two layers:
      1. mirror\           - additive copy of every at-risk path.
      2. config_snapshots\ - timestamped copies of the small config
                             files. Keeps 10 generations, so a corrupted
                             config can be walked back past.

    DELETION POLICY - additive, never destructive.
    robocopy runs with /E, NOT /MIR. A file deleted from the source is
    left alone in the backup. This is deliberate: with /MIR, an app
    failure that empties the source would propagate straight into the
    backup on the next nightly run and destroy it. The cost is that the
    backup can hold files you deleted on purpose; see "Pruning" below.

    A shrink guard also runs: if the source has dramatically fewer files
    than the backup, the run is flagged as suspicious in the manifest.

    Deliberately EXCLUDES ~9.9 GB of re-downloadable material:
    vm_bundles/, claude-code/ binaries, claude-code-vm/, caches, logs.

    claude.ai chat conversations are NOT backed up - they live on
    Anthropic's servers and return when you sign in again.

.PARAMETER Destination
    Root backup folder. Defaults to C:\claude_backups.

.PARAMETER ConfigOnly
    Skip the bulk copy; refresh the config snapshot only. Seconds.

.PARAMETER Prune
    Remove backup files whose source counterpart no longer exists.
    Run this occasionally and deliberately - never on a schedule, and
    never straight after an app failure.

.EXAMPLE
    .\backup_claude_data.ps1
    Normal run. First copy is ~670 MB; later runs copy only changes.

.EXAMPLE
    .\backup_claude_data.ps1 -Prune
    Reclaim space by dropping backup files you have deleted at source.

.NOTES
    Run from a NORMAL PowerShell window, or let the scheduled task
    (claude_data_backup, 22:00 daily) do it. PowerShell running inside a
    Claude Code session cannot read %APPDATA%\Claude at all and will
    silently skip those paths - the completeness check catches this.
#>

[CmdletBinding()]
param(
    [string] $Destination = 'C:\claude_backups',
    [switch] $ConfigOnly,
    [switch] $Prune
)

$ErrorActionPreference = 'Stop'
$startedAt     = Get-Date
$stamp         = $startedAt.ToString('yyyyMMdd_HHmmss')
$userProfile   = $env:USERPROFILE
$appDataClaude = Join-Path $env:APPDATA 'Claude'

$mirrorRoot   = Join-Path $Destination 'mirror'
$snapshotRoot = Join-Path $Destination 'config_snapshots'
$logDir       = Join-Path $Destination 'logs'
$logFile      = Join-Path $logDir ("backup_$stamp.log")

$KeepSnapshots = 10
$KeepLogs      = 30

# Flag the run if the source has shrunk to less than this fraction of
# what the backup holds. Catches "the app wiped my data" before it is
# mistaken for a normal night.
$ShrinkGuardRatio = 0.5

# --- Bulk data: PERSONAL ONLY ---------------------------------------
$BulkPaths = @(
    @{ name = 'personal_projects'
       source = Join-Path $userProfile '.claude\projects' }

    @{ name = 'personal_sessions'
       source = Join-Path $userProfile '.claude\sessions' }

    @{ name = 'personal_session_backup_premove'
       source = Join-Path $userProfile '.claude\_session_backup_premove' }

    @{ name = 'desktop_code_sessions'
       source = Join-Path $appDataClaude 'claude-code-sessions' }

    @{ name = 'desktop_agent_mode_sessions'
       source = Join-Path $appDataClaude 'local-agent-mode-sessions' }
)

# --- Small config files: snapshotted with history -------------------
$ConfigFiles = @(
    @{ name = 'claude_desktop_config.json'
       source = Join-Path $appDataClaude 'claude_desktop_config.json' }

    @{ name = 'desktop_config.json'
       source = Join-Path $appDataClaude 'config.json' }

    @{ name = 'personal_dot_claude.json'
       source = Join-Path $userProfile '.claude.json' }

    @{ name = 'personal_settings.json'
       source = Join-Path $userProfile '.claude\settings.json' }

    @{ name = 'personal_settings_local.json'
       source = Join-Path $userProfile '.claude\settings.local.json' }

    @{ name = 'personal_history.jsonl'
       source = Join-Path $userProfile '.claude\history.jsonl' }
)

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Output $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Get-FileCount {
    param([string] $Path)
    if (-not (Test-Path $Path)) { return 0 }
    return @(Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue).Count
}

# --- Prepare ---------------------------------------------------------
foreach ($d in @($Destination, $mirrorRoot, $snapshotRoot, $logDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

Write-Log "Claude data backup starting (personal account only)"
Write-Log "Destination: $Destination"
if ($ConfigOnly) { Write-Log "Mode: config snapshot only" }
if ($Prune)      { Write-Log "Mode: PRUNE - stale backup files will be removed" 'WARN' }

# --- Config snapshot (always) ---------------------------------------
$snapshotDir = Join-Path $snapshotRoot $stamp
New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null

$configCopied = 0
foreach ($cfg in $ConfigFiles) {
    if (Test-Path $cfg.source) {
        Copy-Item -Path $cfg.source -Destination (Join-Path $snapshotDir $cfg.name) -Force
        $configCopied++
    } else {
        Write-Log "config not present, skipped: $($cfg.source)" 'WARN'
    }
}
Write-Log "Config snapshot: $configCopied files -> $snapshotDir"

# Prune old snapshots
$allSnapshots = @(Get-ChildItem -Path $snapshotRoot -Directory | Sort-Object Name -Descending)
if ($allSnapshots.Count -gt $KeepSnapshots) {
    foreach ($old in ($allSnapshots | Select-Object -Skip $KeepSnapshots)) {
        Remove-Item -Path $old.FullName -Recurse -Force
        Write-Log "Pruned old snapshot: $($old.Name)"
    }
}

# --- Bulk copy -------------------------------------------------------
$totalBytes  = 0
$failures    = @()
$shrinkFlags = @()

if (-not $ConfigOnly) {
    foreach ($item in $BulkPaths) {
        $src = $item.source
        $dst = Join-Path $mirrorRoot $item.name

        if (-not (Test-Path $src)) {
            Write-Log "source not present, skipped: $src" 'WARN'
            continue
        }

        # Shrink guard: compare before copying.
        $srcCount = Get-FileCount $src
        $dstCount = Get-FileCount $dst
        if ($dstCount -gt 0 -and $srcCount -lt ($dstCount * $ShrinkGuardRatio)) {
            $msg = "$($item.name): source has $srcCount files, backup has $dstCount"
            $shrinkFlags += $msg
            Write-Log "SHRINK GUARD - $msg" 'WARN'
            Write-Log "  Source shrank sharply. Copy still runs (additive, so" 'WARN'
            Write-Log "  nothing in the backup is lost), but investigate before" 'WARN'
            Write-Log "  trusting the source." 'WARN'
        }

        # /E = copy everything, create empty dirs, DO NOT delete extras.
        $roboArgs = @($src, $dst, '/E', '/R:1', '/W:1', '/MT:8',
                      '/XJ', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')

        if ($Prune) { $roboArgs += '/PURGE' }   # opt-in destructive sync

        & robocopy.exe @roboArgs | Out-Null
        $code = $LASTEXITCODE

        if ($code -ge 8) {
            $failures += "$($item.name) (robocopy exit $code)"
            Write-Log "COPY FAILED: $($item.name) exit=$code" 'ERROR'
        } else {
            $size = 0
            $measured = Get-ChildItem -Path $dst -Recurse -File -ErrorAction SilentlyContinue |
                        Measure-Object -Property Length -Sum
            if ($measured.Sum) { $size = $measured.Sum }
            $totalBytes += $size
            Write-Log ("copied {0}: {1} files, {2} MB" -f `
                $item.name, (Get-FileCount $dst), [math]::Round($size/1MB,1))
        }
    }
}

# --- Completeness self-check ----------------------------------------
# The %APPDATA%\Claude paths are the ones that go missing unnoticed.
$expectAppData = @(
    @{ label = 'desktop_code_sessions'
       check = (Join-Path $mirrorRoot 'desktop_code_sessions') }
    @{ label = 'desktop_agent_mode_sessions'
       check = (Join-Path $mirrorRoot 'desktop_agent_mode_sessions') }
    @{ label = 'claude_desktop_config.json'
       check = (Join-Path $snapshotDir 'claude_desktop_config.json') }
)

$gaps = @()
foreach ($e in $expectAppData) {
    $ok = $false
    if (Test-Path $e.check) {
        $i = Get-Item $e.check
        if ($i.PSIsContainer) { if ((Get-FileCount $e.check) -gt 0) { $ok = $true } }
        else { $ok = $true }
    }
    if (-not $ok) { $gaps += $e.label }
}

if ($gaps.Count -gt 0) {
    Write-Log "INCOMPLETE - these Desktop-app paths are empty or absent:" 'WARN'
    foreach ($g in $gaps) { Write-Log "    - $g" 'WARN' }
    Write-Log "Run from a normal PowerShell window, not inside a Claude session." 'WARN'
}

# --- Trim old logs ---------------------------------------------------
$allLogs = @(Get-ChildItem -Path $logDir -Filter 'backup_*.log' | Sort-Object Name -Descending)
if ($allLogs.Count -gt $KeepLogs) {
    foreach ($old in ($allLogs | Select-Object -Skip $KeepLogs)) {
        Remove-Item -Path $old.FullName -Force
    }
}

# --- Manifest --------------------------------------------------------
$elapsed = (Get-Date) - $startedAt
$mode = 'full'
if ($ConfigOnly) { $mode = 'config_only' }
if ($Prune)      { $mode = 'full_with_prune' }

$manifest = [ordered]@{
    backup_completed_at = (Get-Date).ToString('o')
    elapsed_seconds     = [math]::Round($elapsed.TotalSeconds, 1)
    mode                = $mode
    scope               = 'personal_account_only'
    destination         = $Destination
    mirror_total_mb     = [math]::Round($totalBytes / 1MB, 1)
    config_snapshot     = $snapshotDir
    config_files_copied = $configCopied
    failures            = $failures
    appdata_gaps        = $gaps
    shrink_warnings     = $shrinkFlags
    complete            = ($failures.Count -eq 0 -and $gaps.Count -eq 0)
    machine             = $env:COMPUTERNAME
}
$manifest | ConvertTo-Json -Depth 4 |
    Set-Content -Path (Join-Path $Destination 'last_backup_manifest.json') -Encoding UTF8

Write-Log ("Done in {0}s. Backup total: {1} MB" -f `
    [math]::Round($elapsed.TotalSeconds,1), [math]::Round($totalBytes/1MB,1))

if ($failures.Count -gt 0) {
    Write-Log ("FAILED: {0}" -f ($failures -join '; ')) 'ERROR'
    exit 1
}
if ($gaps.Count -gt 0) { exit 2 }   # incomplete, but not failed

Write-Log "Backup complete."
exit 0
