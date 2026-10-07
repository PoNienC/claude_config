<#
.SYNOPSIS
    Nightly backup of Claude data (both accounts) and OneDrive Documents.

.DESCRIPTION
    Protects against the failure modes that actually happen: the Claude
    Desktop app breaking, a failed repair, a reinstall wiping data, or a
    lost laptop. The output restores on Windows OR macOS with
    restore_backup.py, which renames session folders so /resume finds
    them under the new machine's paths.

    SCOPE
      personal   ~/.claude       + Claude Desktop app data  (Max seat)
      work       ~/.claude-work                             (PriorPartners)
      documents  OneDrive - priorpartners.com\Documents
      git_repos  C:\git - .git folders of OneDrive repos, kept outside
                 OneDrive (git init --separate-git-dir), added 7 October 2026

    LAYOUT - one folder per machine, so the Mac and this laptop never
    write over each other inside the shared OneDrive:
      <Destination>\win_<computername>\
        mirror\                    additive copies of Claude data + config
          git_repos\               additive copy of C:\git
        documents\                 additive copy of OneDrive Documents
        config_snapshots\<stamp>\  small config files, 10 generations
        logs\
        last_backup_manifest.json  read by restore_backup.py

    The config trees (rules, skills, references, tools, CLAUDE.md) are
    copied too, so uncommitted config survives. Git is still the
    primary home for config (PoNienC/claude_config, claude_config_work).
    Secrets are never copied: .credentials.json and .claude.json stay
    out of the mirror (.claude.json is only snapshotted, never restored).

    DELETION POLICY - additive, never destructive.
    robocopy runs with /E, NOT /MIR. A file deleted from the source is
    left alone in the backup. With /MIR, an app failure that empties the
    source would propagate straight into the backup on the next nightly
    run and destroy it. The cost is that the backup can hold files you
    deleted on purpose; see -Prune.

    A shrink guard also runs: if the source has dramatically fewer files
    than the backup, the run is flagged as suspicious in the manifest.

    DESKTOP APP DATA. Claude Desktop is an MSIX package, so its
    %APPDATA%\Claude is virtualised. The real files live under
    %LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude and are
    invisible at %APPDATA%\Claude to processes outside the package - the
    scheduled task included. Found 25 September 2026: every nightly run
    before then silently skipped the Desktop sessions and MCP config.
    The script now resolves the real folder itself.

    ONEDRIVE PATH LIMIT. OneDrive will not sync a path longer than 400
    characters (counted from the OneDrive root). Desktop agent-mode
    sessions nest up to ~540. So that item is mirrored additively into a
    LOCAL staging folder (-StagingRoot, no limit) and only a zip of it
    goes to OneDrive - rebuilt only when something changed; OneDrive's
    version history keeps earlier zips. Every other item is checked each
    night and the log warns if any path goes over the limit.

    Deliberately EXCLUDES re-downloadable material: vm_bundles/,
    claude-code/ binaries, claude-code-vm/, caches, logs, and in
    Documents: .venv, node_modules and tool caches. Cloud-only
    OneDrive files are skipped rather than downloaded.

    claude.ai chat conversations are NOT backed up - they live on
    Anthropic's servers and return when you sign in again.

.PARAMETER Destination
    Backup root. Must already exist. Defaults to the "Paul - Personal"
    OneDrive: %USERPROFILE%\OneDrive\claude_backups.

.PARAMETER DocumentsSource
    Folder mirrored into documents\. Defaults to the work OneDrive
    Documents folder.

.PARAMETER GitReposRoot
    Folder of .git folders kept outside OneDrive, mirrored into
    mirror\git_repos\ whenever Documents is backed up. Skipped quietly
    if it does not exist. Defaults to C:\git.

.PARAMETER StagingRoot
    Local folder for items too deep for OneDrive; they are zipped from
    here. Defaults to C:\claude_backups\staging.

.PARAMETER SkipDocuments
    Back up Claude data only.

.PARAMETER DocumentsOnly
    Back up OneDrive Documents only.

.PARAMETER ConfigOnly
    Skip every bulk copy; refresh the config snapshot only. Seconds.

.PARAMETER Prune
    Remove backup files whose source counterpart no longer exists.
    Run this occasionally and deliberately - never on a schedule, and
    never straight after an app failure.

.EXAMPLE
    .\backup_claude_data.ps1
    Normal run. The first Documents copy is ~91 GB; later runs copy
    only changes.

.EXAMPLE
    .\backup_claude_data.ps1 -SkipDocuments
    Claude data only. Seconds.

.NOTES
    The scheduled task claude_data_backup runs this at 22:00 daily.
    Restore: see RESTORE.md in this folder.
#>

[CmdletBinding()]
param(
    [string] $Destination     = (Join-Path $env:USERPROFILE 'OneDrive\claude_backups'),
    [string] $DocumentsSource = (Join-Path $env:USERPROFILE 'OneDrive - priorpartners.com\Documents'),
    [string] $GitReposRoot    = 'C:\git',
    [string] $StagingRoot     = 'C:\claude_backups\staging',
    [switch] $SkipDocuments,
    [switch] $DocumentsOnly,
    [switch] $ConfigOnly,
    [switch] $Prune
)

$ErrorActionPreference = 'Stop'
$startedAt   = Get-Date
$stamp       = $startedAt.ToString('yyyyMMdd_HHmmss')
$userProfile = $env:USERPROFILE

# Refuse to run if the backup OneDrive is missing. Creating the folder
# here would make a plain local folder that never syncs anywhere.
if (-not (Test-Path -LiteralPath $Destination)) {
    Write-Output "Destination not found: $Destination"
    Write-Output "Is the backup OneDrive signed in? Nothing was copied."
    exit 1
}

$machineName  = 'win_' + ($env:COMPUTERNAME.ToLower() -replace '[^a-z0-9]', '_')
$machineRoot  = Join-Path $Destination $machineName
$mirrorRoot   = Join-Path $machineRoot 'mirror'
$docsDest     = Join-Path $machineRoot 'documents'
$snapshotRoot = Join-Path $machineRoot 'config_snapshots'
$logDir       = Join-Path $machineRoot 'logs'
$logFile      = Join-Path $logDir ("backup_$stamp.log")

$KeepSnapshots = 10
$KeepLogs      = 30

# Flag the run if the source has shrunk to less than this fraction of
# what the backup holds. Catches "the app wiped my data" before it is
# mistaken for a normal night.
$ShrinkGuardRatio = 0.5

# OneDrive refuses paths longer than this, counted from its root.
$OneDriveRoot      = Split-Path $Destination -Parent
$OneDrivePathLimit = 400

function Resolve-DesktopDir {
    # MSIX install first: that is where the files really are.
    $pkgRoot = Join-Path $env:LOCALAPPDATA 'Packages'
    $candidates = @()
    if (Test-Path $pkgRoot) {
        $candidates += @(Get-ChildItem -Path $pkgRoot -Directory -Filter 'Claude_*' -ErrorAction SilentlyContinue |
                         ForEach-Object { Join-Path $_.FullName 'LocalCache\Roaming\Claude' })
    }
    $candidates += (Join-Path $env:APPDATA 'Claude')
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c 'claude-code-sessions')) { return $c }
    }
    return (Join-Path $env:APPDATA 'Claude')
}

$desktopDir = Resolve-DesktopDir

# --- Claude data: BOTH accounts + Desktop app -----------------------
# xd = top-level folders left out of a config tree (session data is
# copied separately; the rest is cache or machine state).
$personalHome = Join-Path $userProfile '.claude'
$workHome     = Join-Path $userProfile '.claude-work'
$configXd     = @('projects', 'sessions', 'file-history', '_session_backup_premove',
                  'cache', 'debug', 'downloads', 'shell-snapshots', 'session-env',
                  'statsig', 'telemetry', 'ide', 'backups', 'paste-cache')
$configXf     = @('.credentials.json', '.claude.json', 'history.jsonl')

$ClaudeItems = @(
    # --- personal account (~/.claude) ---
    @{ name = 'personal_projects';               source = Join-Path $personalHome 'projects';  required = $true }
    @{ name = 'personal_file_history';           source = Join-Path $personalHome 'file-history' }
    @{ name = 'personal_session_backup_premove'; source = Join-Path $personalHome '_session_backup_premove' }
    @{ name = 'personal_config';                 source = $personalHome;  required = $true
       xd = @($configXd | ForEach-Object { Join-Path $personalHome $_ });  xf = $configXf }

    # --- work account (~/.claude-work) ---
    @{ name = 'work_projects';                   source = Join-Path $workHome 'projects' }
    @{ name = 'work_file_history';               source = Join-Path $workHome 'file-history' }
    @{ name = 'work_config';                     source = $workHome
       xd = @($configXd | ForEach-Object { Join-Path $workHome $_ });  xf = $configXf }

    # --- Claude Desktop app (personal) ---
    @{ name = 'desktop_code_sessions';           source = Join-Path $desktopDir 'claude-code-sessions';      required = $true }
    @{ name = 'desktop_agent_mode_sessions';     source = Join-Path $desktopDir 'local-agent-mode-sessions'; required = $true
       zip = $true }   # paths up to ~540 chars: staged locally, zipped to OneDrive
)

# --- OneDrive Documents ---------------------------------------------
# /XA:O skips cloud-only files so the backup never triggers a mass
# download. Rebuildable folders are left out by name at any depth.
$DocumentsItem = @{
    name = 'documents'; source = $DocumentsSource; dest = $docsDest; partialOk = $true
    xd = @('node_modules', '.venv', 'venv', '__pycache__', '.pytest_cache',
           '.mypy_cache', '.ruff_cache', '.ipynb_checkpoints', '.tox')
    xf = @('~$*', '*.tmp', 'Thumbs.db')
    xa = 'O'
}

# --- Git folders kept outside OneDrive ------------------------------
# Repos whose working files live in OneDrive keep their .git folder in
# C:\git (git init --separate-git-dir), so OneDrive never syncs git
# internals. The working tree only holds a one-line .git pointer file,
# so without this item their history would exist on this PC alone.
$GitReposItem = @{ name = 'git_repos'; source = $GitReposRoot; partialOk = $true }

# --- Small config files: snapshotted with history -------------------
$ConfigFiles = @(
    @{ name = 'claude_desktop_config.json';   source = Join-Path $desktopDir 'claude_desktop_config.json' }
    @{ name = 'desktop_config.json';          source = Join-Path $desktopDir 'config.json' }
    @{ name = 'personal_dot_claude.json';     source = Join-Path $userProfile '.claude.json' }
    @{ name = 'personal_settings.json';       source = Join-Path $personalHome 'settings.json' }
    @{ name = 'personal_settings_local.json'; source = Join-Path $personalHome 'settings.local.json' }
    @{ name = 'personal_history.jsonl';       source = Join-Path $personalHome 'history.jsonl' }
    @{ name = 'work_dot_claude.json';         source = Join-Path $workHome '.claude.json' }
    @{ name = 'work_settings.json';           source = Join-Path $workHome 'settings.json' }
    @{ name = 'work_history.jsonl';           source = Join-Path $workHome 'history.jsonl' }
    @{ name = 'work_policy_limits.json';      source = Join-Path $workHome 'policy-limits.json' }
)

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $line = "{0} [{1}] {2}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Output $line
    Add-Content -Path $logFile -Value $line -Encoding UTF8
}

function Get-LongPath {
    param([string] $Path)
    if ($Path.StartsWith('\\?\')) { return $Path }
    if ($Path.StartsWith('\\'))   { return '\\?\UNC\' + $Path.Substring(2) }
    return '\\?\' + $Path
}

function Get-TreeStats {
    # files, bytes, newest write time, and how many paths exceed the
    # OneDrive limit (counted from $OneDriveRoot).
    param([string] $Path)
    $stats = @{ files = 0; bytes = [int64]0; newest = [datetime]::MinValue; overLimit = 0 }
    if (-not (Test-Path -LiteralPath $Path)) { return $stats }
    $baseLen = (Get-LongPath $OneDriveRoot).Length + 1
    Get-ChildItem -LiteralPath (Get-LongPath $Path) -Recurse -File -Force -ErrorAction SilentlyContinue |
        ForEach-Object {
            $stats.files++
            $stats.bytes += $_.Length
            if ($_.LastWriteTimeUtc -gt $stats.newest) { $stats.newest = $_.LastWriteTimeUtc }
            if (($_.FullName.Length - $baseLen) -gt $OneDrivePathLimit) { $stats.overLimit++ }
        }
    return $stats
}

function Update-ZipIfChanged {
    # Rebuild <ZipPath> from <Source> only when the tree changed, so an
    # unchanged night uploads nothing. Written to .partial first, so a
    # half-built zip never replaces a good one.
    param([string] $Source, [string] $ZipPath, [hashtable] $SourceStats)
    if (Test-Path -LiteralPath $ZipPath) {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zipTime = (Get-Item -LiteralPath $ZipPath).LastWriteTimeUtc
        $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        try     { $zipFiles = @($archive.Entries | Where-Object { $_.Name -ne '' }).Count }
        finally { $archive.Dispose() }
        if ($SourceStats.newest -le $zipTime -and $SourceStats.files -eq $zipFiles) { return $false }
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $tmp = "$ZipPath.partial"
    if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
    [System.IO.Compression.ZipFile]::CreateFromDirectory($Source, $tmp,
        [System.IO.Compression.CompressionLevel]::Optimal, $false)
    Move-Item -LiteralPath $tmp -Destination $ZipPath -Force
    return $true
}

$itemResults = @()
$failures    = @()
$shrinkFlags = @()
$totalBytes  = [int64]0

function Invoke-MirrorItem {
    param([hashtable] $Item)

    $src = $Item.source
    $dst = $Item.dest
    if (-not $dst) { $dst = Join-Path $mirrorRoot $Item.name }
    if ($Item.zip) { $dst = Join-Path $StagingRoot $Item.name }

    if (-not (Test-Path -LiteralPath $src)) {
        Write-Log "source not present, skipped: $src" 'WARN'
        $script:itemResults += [ordered]@{ name = $Item.name; source = $src; status = 'source_missing'; files = 0; mb = 0 }
        return
    }

    # Shrink guard: compare before copying.
    $srcStats = Get-TreeStats $src
    $dstStats = Get-TreeStats $dst
    if ($dstStats.files -gt 0 -and $srcStats.files -lt ($dstStats.files * $ShrinkGuardRatio)) {
        $msg = "$($Item.name): source has $($srcStats.files) files, backup has $($dstStats.files)"
        $script:shrinkFlags += $msg
        Write-Log "SHRINK GUARD - $msg" 'WARN'
        Write-Log "  Source shrank sharply. Copy still runs (additive, so" 'WARN'
        Write-Log "  nothing in the backup is lost), but investigate before" 'WARN'
        Write-Log "  trusting the source." 'WARN'
    }

    # /E = copy everything, create empty dirs, DO NOT delete extras.
    $roboArgs = @($src, $dst, '/E', '/R:1', '/W:1', '/MT:8',
                  '/XJ', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($Item.xd) { $roboArgs += '/XD'; $roboArgs += $Item.xd }
    if ($Item.xf) { $roboArgs += '/XF'; $roboArgs += $Item.xf }
    if ($Item.xa) { $roboArgs += "/XA:$($Item.xa)" }
    if ($Prune)   { $roboArgs += '/PURGE' }   # opt-in destructive sync

    $out  = & robocopy.exe @roboArgs
    $code = $LASTEXITCODE
    $errs = @($out | Where-Object { $_ -match 'ERROR \d+' } | Select-Object -First 10)

    $status = 'copied'
    if ($code -ge 16 -or ($code -ge 8 -and -not $Item.partialOk)) {
        $status = 'failed'
        $script:failures += "$($Item.name) (robocopy exit $code)"
        Write-Log "COPY FAILED: $($Item.name) exit=$code" 'ERROR'
    } elseif ($code -ge 8) {
        $status = 'partial'
        Write-Log "PARTIAL: $($Item.name) exit=$code - some files could not be copied (open in another app?)" 'WARN'
    }
    foreach ($e in $errs) { Write-Log "  robocopy: $($e.Trim())" 'WARN' }

    $after = Get-TreeStats $dst
    $bytes = $after.bytes
    $store = 'mirror'
    if ($Item.zip -and $status -ne 'failed') {
        $zipPath = Join-Path $mirrorRoot "$($Item.name).zip"
        $rebuilt = Update-ZipIfChanged -Source $dst -ZipPath $zipPath -SourceStats $after
        $bytes = (Get-Item -LiteralPath $zipPath).Length
        $store = 'zip'
        if ($rebuilt) { Write-Log "zipped $($Item.name) -> $zipPath" }
        else          { Write-Log "$($Item.name): unchanged, zip kept" }
    } elseif ($after.overLimit -gt 0) {
        Write-Log ("{0}: {1} paths are longer than OneDrive's {2}-character limit and will not sync" -f `
            $Item.name, $after.overLimit, $OneDrivePathLimit) 'WARN'
    }
    $mb = [math]::Round($bytes / 1MB, 1)
    $script:totalBytes += $bytes
    $script:itemResults += [ordered]@{ name = $Item.name; source = $src; status = $status; store = $store
                                       files = $after.files; mb = $mb; over_path_limit = $after.overLimit }
    if ($status -ne 'failed') {
        Write-Log ("copied {0}: {1} files, {2} MB" -f $Item.name, $after.files, $mb)
    }
}

# --- Prepare ---------------------------------------------------------
foreach ($d in @($machineRoot, $mirrorRoot, $snapshotRoot, $logDir, $StagingRoot)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

Write-Log "Backup starting (personal + work accounts + Documents)"
Write-Log "Destination: $machineRoot"
Write-Log "Desktop app data: $desktopDir"
if ($ConfigOnly)    { Write-Log "Mode: config snapshot only" }
if ($SkipDocuments) { Write-Log "Mode: Claude data only (Documents skipped)" }
if ($DocumentsOnly) { Write-Log "Mode: Documents only" }
if ($Prune)         { Write-Log "Mode: PRUNE - stale backup files will be removed" 'WARN' }

# --- Config snapshot (always) ---------------------------------------
$snapshotDir = Join-Path $snapshotRoot $stamp
New-Item -ItemType Directory -Path $snapshotDir -Force | Out-Null

$configCopied = 0
foreach ($cfg in $ConfigFiles) {
    if (Test-Path -LiteralPath $cfg.source) {
        Copy-Item -LiteralPath $cfg.source -Destination (Join-Path $snapshotDir $cfg.name) -Force
        $configCopied++
    } else {
        Write-Log "config not present, skipped: $($cfg.source)" 'WARN'
    }
}
Write-Log "Config snapshot: $configCopied files -> $snapshotDir"

$allSnapshots = @(Get-ChildItem -Path $snapshotRoot -Directory | Sort-Object Name -Descending)
if ($allSnapshots.Count -gt $KeepSnapshots) {
    foreach ($old in ($allSnapshots | Select-Object -Skip $KeepSnapshots)) {
        Remove-Item -Path $old.FullName -Recurse -Force
        Write-Log "Pruned old snapshot: $($old.Name)"
    }
}

# --- Bulk copy: Claude data first, Documents last --------------------
# Documents is last so a slow or partial Documents run can never delay
# or block the small, critical Claude data. Git folders go just before
# Documents: they belong with it, and are small.
if (-not $ConfigOnly) {
    if (-not $DocumentsOnly) {
        foreach ($item in $ClaudeItems) { Invoke-MirrorItem $item }
    }
    if (-not $SkipDocuments) {
        if (Test-Path -LiteralPath $GitReposRoot) { Invoke-MirrorItem $GitReposItem }
        else { Write-Log "No $GitReposRoot on this machine - git_repos skipped" }
        Invoke-MirrorItem $DocumentsItem
    }
}

# --- Completeness self-check ----------------------------------------
# A required item whose source is missing means the backup has a hole.
$gaps = @()
foreach ($r in $itemResults) {
    $req = @($ClaudeItems | Where-Object { $_.name -eq $r.name -and $_.required })
    if ($req.Count -gt 0 -and $r.status -eq 'source_missing') { $gaps += $r.name }
}
if (-not (Test-Path (Join-Path $snapshotDir 'claude_desktop_config.json'))) {
    $gaps += 'claude_desktop_config.json'
}
if ($gaps.Count -gt 0) {
    Write-Log "INCOMPLETE - these required paths were not found:" 'WARN'
    foreach ($g in $gaps) { Write-Log "    - $g" 'WARN' }
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
if ($SkipDocuments) { $mode = 'claude_data_only' }
if ($DocumentsOnly) { $mode = 'documents_only' }
if ($ConfigOnly)    { $mode = 'config_only' }
if ($Prune)         { $mode = "$($mode)_with_prune" }

$manifest = [ordered]@{
    format_version      = 2
    backup_completed_at = (Get-Date).ToString('o')
    elapsed_seconds     = [math]::Round($elapsed.TotalSeconds, 1)
    mode                = $mode
    scope               = 'personal_work_documents'
    source_os           = 'windows'
    machine             = $env:COMPUTERNAME
    machine_folder      = $machineName
    source_home         = $userProfile
    source_documents    = $DocumentsSource
    source_git_repos    = $GitReposRoot
    source_desktop_dir  = $desktopDir
    destination         = $machineRoot
    mirror_total_mb     = [math]::Round($totalBytes / 1MB, 1)
    config_snapshot     = $snapshotDir
    config_files_copied = $configCopied
    items               = $itemResults
    failures            = $failures
    appdata_gaps        = $gaps
    shrink_warnings     = $shrinkFlags
    complete            = ($failures.Count -eq 0 -and $gaps.Count -eq 0)
}
$manifest | ConvertTo-Json -Depth 5 |
    Set-Content -Path (Join-Path $machineRoot 'last_backup_manifest.json') -Encoding UTF8

Write-Log ("Done in {0}s. Backup total: {1} MB" -f `
    [math]::Round($elapsed.TotalSeconds, 1), [math]::Round($totalBytes / 1MB, 1))

if ($failures.Count -gt 0) {
    Write-Log ("FAILED: {0}" -f ($failures -join '; ')) 'ERROR'
    exit 1
}
if ($gaps.Count -gt 0) { exit 2 }   # incomplete, but not failed

Write-Log "Backup complete."
exit 0
