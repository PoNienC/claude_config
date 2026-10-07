# Backup and restore runbook — Claude data + OneDrive Documents

Written while nothing is broken. Follow it top to bottom after a failed
repair, a reinstall, or on a brand-new Windows PC or Mac.
Rewritten 25 September 2026 (OneDrive destination, Mac support,
cross-OS restore). Previous version: git history of this file.

## At a glance

| | Windows | macOS |
|---|---|---|
| Backup script | `backup_claude_data.ps1` | `backup_macos.sh` |
| Schedule | task `claude_data_backup`, 22:00 | launchd `local.ponien.nightly_backup`, 22:00 (`install_schedule_macos.sh`) |
| Backup root | `%USERPROFILE%\OneDrive\claude_backups` | `~/Library/CloudStorage/OneDrive-Personal/claude_backups` |
| Local staging | `C:\claude_backups\staging` | `~/.backup_staging` |
| Restore | `restore_backup.py` (same script on both) | |

- **Backup OneDrive:** "Paul - Personal" (IT approved). Both machines
  write into it, each in its own folder: `win_<computer>` / `mac_<host>`.
- **Config repos:** <https://github.com/PoNienC/claude_config> and
  <https://github.com/PoNienC/claude_config_work>. The backup also
  carries the config trees, so uncommitted config is not lost.

## Layout of one machine folder

```
claude_backups\win_priorplap180\
  last_backup_manifest.json        what ran, when, from which paths; restore reads it
  logs\backup_<stamp>.log          one log per run, 30 kept
  config_snapshots\<stamp>\        10 generations of small config files
  mirror\
    personal_projects\             ~/.claude/projects - session transcripts + memory
    personal_file_history\         ~/.claude/file-history - rewind checkpoints
    personal_session_backup_premove\
    personal_config\               ~/.claude minus data and secrets (rules, skills, tools...)
    work_projects\ work_file_history\ work_config\     same for ~/.claude-work
    desktop_code_sessions\         Desktop app Code-tab session list (titles, folders)
    desktop_agent_mode_sessions.zip  Desktop agent-mode sessions, zipped (see below)
    git_repos\                     C:\git - .git folders of OneDrive repos (see Known issues)
  documents\                       additive copy of OneDrive - priorpartners.com\Documents
```

Additive everywhere: a file deleted at source stays in the backup.
`-Prune` / `--prune` removes those, deliberately, never on a schedule.

---

## 0. Before you repair or reinstall anything

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\tools\claude_backup\backup_claude_data.ps1" -SkipDocuments
Get-Content "$env:USERPROFILE\OneDrive\claude_backups\win_$($env:COMPUTERNAME.ToLower())\last_backup_manifest.json" |
  ConvertFrom-Json | Select-Object complete, mirror_total_mb, appdata_gaps, failures
```

```bash
bash ~/.claude/tools/claude_backup/backup_macos.sh --skip-documents
```

`complete` must be `true`. Then wait for OneDrive to finish uploading
(green ticks) before touching the app.

## 1. What you do NOT need to restore

- **claude.ai conversations** — server-side; sign in and they return.
- **Binaries, `vm_bundles/`, caches** — re-downloaded on first launch.
- **Documents** — OneDrive re-syncs them when you sign in to the work
  account. Use the backup copy only if OneDrive itself lost files.
- **Logins** — `.credentials.json` and `.claude.json` are never
  restored. Sign in fresh on every machine.

## 2. Any new machine — common steps

1. Install Claude Desktop, sign in as `pnchenspacesyntax@gmail.com`
   (personal Max). Confirm claude.ai conversations appear.
2. Install Python 3 (Windows: python.org; Mac: `xcode-select --install`,
   which also gives git).
3. Sign in to OneDrive with **both** accounts: work
   (`ponien.chen@priorpartners.com`, gives Documents) and
   "Paul - Personal" (gives `claude_backups`).
4. Right-click `claude_backups\<machine folder>` → **Always keep on
   this device**, and wait until it is fully downloaded.
5. **Quit Claude Desktop** before the restore (it may overwrite files).

## 3. Restore — dry run first, then apply

The restore script is inside the backup itself, so nothing else is
needed. `<B>` = the machine folder you restore FROM.

**Windows**
```powershell
$B = "$env:USERPROFILE\OneDrive\claude_backups\win_priorplap180"
python "$B\mirror\personal_config\tools\claude_backup\restore_backup.py" $B
python "$B\mirror\personal_config\tools\claude_backup\restore_backup.py" $B --apply
```

**macOS**
```bash
B="$HOME/Library/CloudStorage/OneDrive-Personal/claude_backups/win_priorplap180"
python3 "$B/mirror/personal_config/tools/claude_backup/restore_backup.py" "$B"
python3 "$B/mirror/personal_config/tools/claude_backup/restore_backup.py" "$B" --apply
```

What it does — it MERGES into a machine that already has Claude Code;
nothing on the machine is ever deleted:
- **Sessions, file history, Desktop sessions:** added next to the ones
  already there. Old and new sessions share a project folder, so
  `claude --resume` lists both.
- **Prompt history:** merged line by line.
- **Config (CLAUDE.md, rules, skills, settings) and project memory:**
  the machine's own copy wins. Where the backup's copy differs, it is
  set aside in `~/.claude/restore_reports/conflicts_<stamp>/` (same
  sub-paths) for you — or Claude Code — to merge by hand. Skills and
  rules the machine lacks are simply added. `--prefer-backup` lets
  newer backup copies win instead.
- An existing `~/.claude/.git` clone is left untouched.
- **Renames session folders for the new machine's paths**, so
  `claude --resume` inside a project lists its old sessions. Default
  maps: backup home → this home; backup Documents → this Documents.
- Folders it cannot map are copied unchanged and listed as `NOTE`.
  Add maps for network drives and other roots, e.g. on a Mac:
  `--map "N:\=/Volumes/PP_Team_Nas" --map "\\priorpsrv03\PP_Team_Nas=/Volumes/PP_Team_Nas"`
- Writes a report to `~/.claude/restore_reports/`, including
  `mcp_servers_from_backup_<stamp>.json` — MCP servers to re-add by hand
  when moving between Windows and Mac (commands and paths differ).
- `--include-documents` also copies the Documents backup — only if
  OneDrive is NOT restoring it.
- `--include-git-repos` restores `C:\git` (Windows only; `--git-root`
  to change it). A repo folder that already exists is left untouched.
- `--install-root <folder>` stages everything in a test folder instead
  of your real home.

## 4. After the restore

**Windows — work launcher** (shortcut, not an install):
- Target `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
- Arguments: `-NoProfile -WindowStyle Hidden -Command "$env:CLAUDE_CONFIG_DIR='C:\Users\po.nienchen\.claude-work'; code --user-data-dir 'C:\Users\po.nienchen\.vscode-work'"`
- Name: `Company Claude (VS Code)`; sign in as `ponien.chen@priorpartners.com`.

**Windows — re-arm the nightly task**
```powershell
$taskName = 'claude_data_backup'
$script   = "$env:USERPROFILE\.claude\tools\claude_backup\backup_claude_data.ps1"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
$action  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At '22:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 4) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Nightly backup of Claude data and OneDrive Documents to the Personal OneDrive.'
```

**macOS — work account**: add to `~/.zshrc`
`alias claude_work='CLAUDE_CONFIG_DIR="$HOME/.claude-work" claude'`
and sign in as `ponien.chen@priorpartners.com` the first time.

**macOS — nightly backup**
```bash
brew install rsync          # lets the backup skip cloud-only Documents files
bash ~/.claude/tools/claude_backup/install_schedule_macos.sh
launchctl kickstart gui/$(id -u)/local.ponien.nightly_backup   # first run now
```
If `~/Library/Logs/nightly_backup.log` shows "Operation not permitted",
give `/bin/bash` Full Disk Access (System Settings → Privacy & Security).

## 5. Verify — tick every box

- [ ] `claude --resume` inside a project folder lists its old sessions
- [ ] `/mcp` shows your MCP servers (re-add from the report if moving OS)
- [ ] `/context` shows skills and rules loaded
- [ ] Work account signed in as the priorpartners.com account
- [ ] Nightly backup ran once and its manifest says `complete: true`
- [ ] The new machine's folder appears in `claude_backups` next to the old one

## Known issues

- **Desktop app data is virtualised (MSIX, Windows).** The real files
  are in `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude`,
  invisible at `%APPDATA%\Claude` to the scheduled task. Before
  25 September 2026 every nightly run silently skipped Desktop sessions
  and the MCP config. The script now finds the real folder itself.
- **OneDrive path limit: 400 characters** from the OneDrive root.
  Desktop agent-mode sessions nest to ~540, so they are staged locally
  and only a zip goes to OneDrive (rebuilt only when changed; OneDrive
  version history keeps older zips). Every other item is checked each
  night; the log warns if any path goes over the limit.
- **Mac Documents**: files OneDrive has not downloaded are skipped, not
  fetched — the backup holds what is on the Mac's disk.
- **Old local backup**: `C:\claude_backups\mirror`, `config_snapshots`,
  `logs` and `last_backup_manifest.json` are the pre-25-September
  backup, copied into OneDrive on that date. Only `staging\` is still
  in use. Delete the rest once you are happy.
- **OneDrive repos with the git folder in `C:\git`** (added 7 October
  2026). The OneDrive folder holds the files plus a one-line `.git`
  pointer (`gitdir: C:/git/<name>.git`); the history lives in `C:\git`
  and is backed up as `mirror\git_repos`. On a new Windows PC, restore
  with `--include-git-repos` to the same `C:\git` path and the pointers
  work again. On a Mac or second laptop the pointer leads nowhere: clone
  from GitHub instead, and never edit the pointer file — OneDrive would
  sync the change back and break the Windows repo.
- **Sessions over 200 characters of path** get a hashed folder name in
  Claude Code; the restore cannot recompute it and copies them unchanged.

## Baseline counts (25 September 2026)

| Item | Files | Size |
|---|---:|---:|
| personal_projects | 638 | 813 MB |
| personal_config | 935 | 22 MB |
| work_projects | 347 | 985 MB |
| work_file_history | 3,286 | 76 MB |
| desktop_code_sessions | 155 | 23 MB |
| desktop_agent_mode_sessions (zip) | 975 | 23 MB zipped |
| documents (first run pending) | ~223,000 | ~89 GB |
