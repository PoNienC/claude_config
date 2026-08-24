<#
.SYNOPSIS
    Backs up irreplaceable Claude data to a local second folder.

.DESCRIPTION
    Protects against the failure mode that actually happens: the Claude
    Desktop app breaking, a failed repair, or a reinstall wiping AppData.

    Two layers:
      1. mirror\           - robocopy /MIR of every at-risk path. Fast
                             (deltas only after the first run). This is
                             the restore source.
      2. config_snapshots\ - timestamped copies of the small config files
                             only (~2 MB). Keeps 10 generations, so if a
                             config gets corrupted and the mirror
                             faithfully mirrors the corruption, you can
                             still walk back to a good one.

    Deliberately EXCLUDES ~9.9 GB of re-downloadable material:
    vm_bundles/, claude-code/ binaries, claude-code-vm/, all browser
    caches, and logs.

    claude.ai chat conversations are NOT backed up - they live on
    Anthropic's servers and return when you sign in again.

.PARAMETER Destination
    Root backup folder. Defaults to C:\claude_backups.

.PARAMETER ConfigOnly
    Skip the mirror; refresh the config snapshot only. Takes seconds.
    Use before editing settings or installing an MCP server.

.EXAMPLE
    .\backup_claude_data.ps1
    Full run. First run copies ~1.1 GB; later runs copy only changes.

.EXAMPLE
    .\backup_claude_data.ps1 -ConfigOnly
    Quick config-only snapshot.

.NOTES
    Written for Windows PowerShell 5.1 compatibility (no ternary, no ??).
    Run before any Claude Desktop repair or reinstall.
#>

[CmdletBinding()]
param(
    [string] $Destination = 'C:\claude_backups',
    [switch] $ConfigOnly
)

$ErrorActionPreference = 'Stop'
$startedAt   = Get-Date
$stamp       = $startedAt.ToString('yyyyMMdd_HHmmss')
$userProfile = $env:USERPROFILE
$appDataClaude = Join-Path $env:APPDATA 'Claude'

$mirrorRoot   = Join-Path $Destination 'mirror'
$snapshotRoot = Join-Path $Destination 'config_snapshots'
$logDir       = Join-Path $Destination 'logs'
$logFile      = Join-Path $logDir ("backup_$stamp.log")

$KeepSnapshots = 10

# --- Bulk data: mirrored, not versioned -----------------------------
# name        = folder name under mirror\
# source      = absolute path
# excludeDirs = subfolder names to skip
$BulkPaths = @(
    @{ name = 'personal_projects'
       source = Join-Path $userProfile '.claude\projects'
       excludeDirs = @() }

    @{ name = 'personal_sessions'
       source = Join-Path $userProfile '.claude\sessions'
       excludeDirs = @() }

    @{ name = 'personal_session_backup_premove'
       source = Join-Path $userProfile '.claude\_session_backup_premove'
       excludeDirs = @() }

    @{ name = 'work_projects'
       source = Join-Path $userProfile '.claude-work\projects'
       excludeDirs = @() }

    @{ name = 'work_sessions'
       source = Join-Path $userProfile '.claude-work\sessions'
       excludeDirs = @() }

    @{ name = 'work_file_history'
       source = Join-Path $userProfile '.claude-work\file-history'
       excludeDirs = @() }

    @{ name = 'desktop_code_sessions'
       source = Join-Path $appDataClaude 'claude-code-sessions'
       excludeDirs = @() }

    @{ name = 'desktop_agent_mode_sessions'
       source = Join-Path $appDataClaude 'local-agent-mode-sessions'
       excludeDirs = @() }

    # Work config tree. Runtime subfolders excluded - they are either
    # mirrored separately above or genuinely disposable.
    @{ name = 'work_config'
       source = Join-Path $userProfile '.claude-work'
       excludeDirs = @('projects', 'sessions', 'file-history', 'cache',
                       'telemetry', 'shell-snapshots', 'session-env',
                       'backups', 'plugins', 'ide') }
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

    @{ name = 'work_dot_claude.json'
       source = Join-Path $userProfile '.claude-work\.claude.json' }

    @{ name = 'work_settings.json'
       source = Join-Path $userProfile '.claude-work\settings.json' }

    @{ name = 'work_history.jsonl'
       source = Join-Path $userProfile '.claude-work\history.jsonl' }

    @{ name = 'work_policy_limits.json'
       source = Join-Path $userProfile '.claude-work\policy-limits.json' }
)

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Output $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

# --- Prepare ---------------------------------------------------------
foreach ($d in @($Destination, $mirrorRoot, $snapshotRoot, $logDir)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

Write-Log "Claude data backup starting"
Write-Log "Destination: $Destination"
if ($ConfigOnly) { Write-Log "Mode: config snapshot only (-ConfigOnly)" }

# --- Config snapshot (always) ---------------------------------------
$snapshotDir = Join-Path $snapshotRoot $stamp
New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null

$configCopied = 0
$configMissing = 0
foreach ($cfg in $ConfigFiles) {
    if (Test-Path $cfg.source) {
        Copy-Item -Path $cfg.source -Destination (Join-Path $snapshotDir $cfg.name) -Force
        $configCopied++
    } else {
        Write-Log "config not present, skipped: $($cfg.source)" 'WARN'
        $configMissing++
    }
}
Write-Log "Config snapshot: $configCopied copied, $configMissing absent -> $snapshotDir"

# Prune old snapshots
$allSnapshots = Get-ChildItem -Path $snapshotRoot -Directory | Sort-Object Name -Descending
if ($allSnapshots.Count -gt $KeepSnapshots) {
    $toRemove = $allSnapshots | Select-Object -Skip $KeepSnapshots
    foreach ($old in $toRemove) {
        Remove-Item -Path $old.FullName -Recurse -Force
        Write-Log "Pruned old snapshot: $($old.Name)"
    }
}

# --- Bulk mirror -----------------------------------------------------
$totalBytes = 0
$failures = @()

if (-not $ConfigOnly) {
    foreach ($item in $BulkPaths) {
        $src = $item.source
        if (-not (Test-Path $src)) {
            Write-Log "source not present, skipped: $src" 'WARN'
            continue
        }

        $dst = Join-Path $mirrorRoot $item.name

        $roboArgs = @($src, $dst, '/MIR', '/R:1', '/W:1', '/MT:8',
                      '/XJ', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
        foreach ($xd in $item.excludeDirs) {
            $roboArgs += '/XD'
            $roboArgs += (Join-Path $src $xd)
        }

        & robocopy.exe @roboArgs | Out-Null
        $code = $LASTEXITCODE

        # robocopy: 0-7 success, 8+ real failure
        if ($code -ge 8) {
            $failures += "$($item.name) (robocopy exit $code)"
            Write-Log "MIRROR FAILED: $($item.name) exit=$code" 'ERROR'
        } else {
            $size = 0
            if (Test-Path $dst) {
                $measured = Get-ChildItem -Path $dst -Recurse -File -ErrorAction SilentlyContinue |
                            Measure-Object -Property Length -Sum
                if ($measured.Sum) { $size = $measured.Sum }
            }
            $totalBytes += $size
            $mb = [math]::Round($size / 1MB, 1)
            Write-Log "mirrored $($item.name): $mb MB (exit $code)"
        }
    }
}

# --- Manifest --------------------------------------------------------
$elapsed = (Get-Date) - $startedAt
$manifest = [ordered]@{
    backup_completed_at = (Get-Date).ToString('o')
    elapsed_seconds     = [math]::Round($elapsed.TotalSeconds, 1)
    mode                = $(if ($ConfigOnly) { 'config_only' } else { 'full' })
    destination         = $Destination
    mirror_total_mb     = [math]::Round($totalBytes / 1MB, 1)
    config_snapshot     = $snapshotDir
    config_files_copied = $configCopied
    failures            = $failures
    machine             = $env:COMPUTERNAME
}
$manifestPath = Join-Path $Destination 'last_backup_manifest.json'
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding UTF8

Write-Log ("Done in {0}s. Mirror total: {1} MB" -f `
    [math]::Round($elapsed.TotalSeconds,1), [math]::Round($totalBytes/1MB,1))

if ($failures.Count -gt 0) {
    Write-Log ("COMPLETED WITH {0} FAILURE(S): {1}" -f $failures.Count, ($failures -join '; ')) 'ERROR'
    exit 1
}

Write-Log "All paths backed up cleanly."
exit 0
