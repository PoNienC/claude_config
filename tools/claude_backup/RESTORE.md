# Restore runbook — Claude data

Written while nothing is broken. Follow it top to bottom after a failed
repair, a reinstall, or on a brand-new machine.

- **Backup root:** `C:\claude_backups`
- **Backup script:** `~/.claude/tools/claude_backup/backup_claude_data.ps1`
- **Nightly task:** `claude_data_backup`, 22:00 daily
- **Personal config repo:** <https://github.com/PoNienC/claude_config>
- **Work config repo:** local at `~/.claude-work` (add your remote)

---

## 0. Before you repair or reinstall anything

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\tools\claude_backup\backup_claude_data.ps1"
```

Then confirm:

```powershell
Get-Content C:\claude_backups\last_backup_manifest.json | ConvertFrom-Json |
  Select-Object complete, mirror_total_mb, appdata_gaps, failures
```

`complete` must be `True`. If not, fix that **before** touching the app —
a backup with a hole is worse than knowing you have none.

---

## 1. What you do NOT need to restore

- **claude.ai conversations.** Server-side. Reinstall, sign in, they
  return by themselves. Do not go hunting locally.
- **Binaries, `vm_bundles/`, caches.** ~9.9 GB, re-downloaded on first
  launch. Deliberately not in the backup.

If you only lost the app, reinstall and stop after step 3.

---

## 2. Fresh machine — start from nothing

Assumes a blank Windows install with nothing set up.

### 2.1 Prerequisites

| Tool | Why | Get it |
|---|---|---|
| Git for Windows | clone both config repos | <https://git-scm.com/download/win> |
| GitHub Desktop | your review-and-push surface | <https://desktop.github.com> |
| VS Code | the work Claude environment | <https://code.visualstudio.com> |
| Claude Desktop | personal Claude | <https://claude.ai/download> |

### 2.2 Recover the backup itself first

If the machine is new, `C:\claude_backups` does not exist yet. Copy it
from wherever the drive/folder survived, to the same path. Everything
below assumes `C:\claude_backups` is present.

> If the backup did **not** survive: you still get claude.ai
> conversations back (server-side) and both config repos from GitHub.
> Only local Code transcripts are lost. That is the whole reason this
> backup exists.

### 2.3 Git identity

```powershell
git config --global user.name  "PoNienChenPP"
git config --global user.email "ponien.chen@priorpartners.com"
git config --global credential.helper manager
```

---

## 3. Reinstall and sign in

1. Install Claude Desktop, launch, sign in as
   **`pnchenspacesyntax@gmail.com`** (personal Max).
2. Confirm your claude.ai conversations appear. If yes, the server side
   is fine and everything remaining is local restoration.
3. Install VS Code. Confirm the `anthropic.claude-code` extension is
   present (or install it from the Marketplace).

---

## 4. Restore config from git — do this before step 5

Git holds the *text* config: rules, skills, agents, commands, CLAUDE.md.
The mirror holds the *data*. Config first, so the mirror does not
overwrite a half-built tree.

**Personal** — clone to a temp path, then merge so runtime folders are
preserved if any already exist:

```powershell
git clone https://github.com/PoNienC/claude_config.git "$env:TEMP\claude_config_clone"
robocopy "$env:TEMP\claude_config_clone" "$env:USERPROFILE\.claude" /E
Remove-Item "$env:TEMP\claude_config_clone" -Recurse -Force
```

> `/E` includes the hidden `.git` folder, so `~/.claude` becomes a
> working clone. If `Remove-Item` fails on the 8.3 temp path, delete it
> from Git Bash instead:
> `rm -rf "/c/Users/<you>/AppData/Local/Temp/claude_config_clone"`

**Work** — same shape, into `~/.claude-work`:

```powershell
git clone <work-config-repo-url> "$env:TEMP\claude_work_clone"
robocopy "$env:TEMP\claude_work_clone" "$env:USERPROFILE\.claude-work" /E
Remove-Item "$env:TEMP\claude_work_clone" -Recurse -Force
```

If no work remote exists yet, skip this — step 5 restores
`work_config` from the mirror instead.

---

## 5. Restore bulk data from the mirror

Each mirror folder maps to exactly one destination:

| Mirror folder | Restore to |
|---|---|
| `personal_projects` | `%USERPROFILE%\.claude\projects` |
| `personal_sessions` | `%USERPROFILE%\.claude\sessions` |
| `personal_session_backup_premove` | `%USERPROFILE%\.claude\_session_backup_premove` |
| `work_projects` | `%USERPROFILE%\.claude-work\projects` |
| `work_sessions` | `%USERPROFILE%\.claude-work\sessions` |
| `work_file_history` | `%USERPROFILE%\.claude-work\file-history` |
| `work_config` | `%USERPROFILE%\.claude-work` |
| `desktop_code_sessions` | `%APPDATA%\Claude\claude-code-sessions` |
| `desktop_agent_mode_sessions` | `%APPDATA%\Claude\local-agent-mode-sessions` |

Restore all of them:

```powershell
$map = @{
  'personal_projects'               = "$env:USERPROFILE\.claude\projects"
  'personal_sessions'               = "$env:USERPROFILE\.claude\sessions"
  'personal_session_backup_premove' = "$env:USERPROFILE\.claude\_session_backup_premove"
  'work_projects'                   = "$env:USERPROFILE\.claude-work\projects"
  'work_sessions'                   = "$env:USERPROFILE\.claude-work\sessions"
  'work_file_history'               = "$env:USERPROFILE\.claude-work\file-history"
  'work_config'                     = "$env:USERPROFILE\.claude-work"
  'desktop_code_sessions'           = "$env:APPDATA\Claude\claude-code-sessions"
  'desktop_agent_mode_sessions'     = "$env:APPDATA\Claude\local-agent-mode-sessions"
}
foreach ($k in $map.Keys) {
  $src = "C:\claude_backups\mirror\$k"
  if (Test-Path $src) {
    robocopy $src $map[$k] /E /R:1 /W:1 | Out-Null
    Write-Output "restored $k -> $($map[$k])"
  } else {
    Write-Warning "missing from backup: $k"
  }
}
```

> Use `/E`, never `/MIR`. `/MIR` deletes anything in the destination
> that is not in the backup.

Close Claude Desktop before restoring the two `%APPDATA%\Claude` folders,
or the running app may overwrite them.

---

## 6. Restore the MCP config

Highest value per byte in the whole backup — hand-built, not
reproducible from memory.

```powershell
$newest = Get-ChildItem C:\claude_backups\config_snapshots |
          Sort-Object Name -Descending | Select-Object -First 1
Copy-Item "$($newest.FullName)\claude_desktop_config.json" `
          "$env:APPDATA\Claude\claude_desktop_config.json" -Force
Copy-Item "$($newest.FullName)\desktop_config.json" `
          "$env:APPDATA\Claude\config.json" -Force
Write-Output "restored MCP config from $($newest.Name)"
```

If the newest snapshot is itself suspect — the config was already
corrupted when it was taken — walk back through older ones. That is
precisely why 10 generations are kept:

```powershell
Get-ChildItem C:\claude_backups\config_snapshots | Sort-Object Name -Descending
```

**Not restored, by design:** `.credentials.json` and `.claude.json`.
Those are auth and machine identity — you get them fresh by signing in.
Never copy them between machines.

---

## 7. Recreate the work VS Code launcher

The work setup is a shortcut, not an install.

- **Target:** `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
- **Arguments:**
  ```
  -NoProfile -WindowStyle Hidden -Command "$env:CLAUDE_CONFIG_DIR='C:\Users\po.nienchen\.claude-work'; code --user-data-dir 'C:\Users\po.nienchen\.vscode-work'"
  ```
- **Start in:** `C:\Users\po.nienchen`
- **Icon:** `C:\Program Files\Microsoft VS Code\Code.exe,0`
- **Name:** `Company Claude (VS Code)`

Or create it from PowerShell:

```powershell
$s = (New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\Company Claude (VS Code).lnk")
$s.TargetPath  = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
$s.Arguments   = '-NoProfile -WindowStyle Hidden -Command "$env:CLAUDE_CONFIG_DIR=''C:\Users\po.nienchen\.claude-work''; code --user-data-dir ''C:\Users\po.nienchen\.vscode-work''"'
$s.WorkingDirectory = 'C:\Users\po.nienchen'
$s.IconLocation = 'C:\Program Files\Microsoft VS Code\Code.exe,0'
$s.Save()
```

Launch it and sign in as **`ponien.chen@priorpartners.com`**
(PriorPartners team seat). Org policy re-downloads automatically.

---

## 8. Re-arm the nightly backup

The scheduled task does not survive a machine rebuild.

```powershell
$taskName = 'claude_data_backup'
$script   = "$env:USERPROFILE\.claude\tools\claude_backup\backup_claude_data.ps1"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
$action  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At '22:00'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Nightly backup of irreplaceable Claude data to C:\claude_backups.'
```

---

## 9. Verify — tick every box

```powershell
# Transcript counts (compare against the baseline table below)
(Get-ChildItem "$env:USERPROFILE\.claude\projects" -Recurse -Filter *.jsonl).Count
(Get-ChildItem "$env:USERPROFILE\.claude-work\projects" -Recurse -Filter *.jsonl).Count
(Get-ChildItem "$env:APPDATA\Claude\local-agent-mode-sessions" -Recurse -File).Count

# Repo health
git -C "$env:USERPROFILE\.claude" status
git -C "$env:USERPROFILE\.claude" remote -v      # expect PoNienC/claude_config

# Scheduled task
Get-ScheduledTaskInfo -TaskName claude_data_backup | Select-Object LastRunTime, LastTaskResult, NextRunTime
```

- [ ] Personal `.jsonl` count ≈ baseline
- [ ] Work `.jsonl` count ≈ baseline
- [ ] Personal Claude Code: `/resume` lists old sessions
- [ ] Work VS Code window signed in as the priorpartners.com account
- [ ] `/mcp` shows your MCP servers connected
- [ ] `/context` shows your skills and rules loaded
- [ ] Both repos clean, correct remotes
- [ ] Scheduled task `Ready`, `NextRunTime` tomorrow 22:00
- [ ] Run the backup once more so the mirror reflects restored state

---

## Baseline counts (survey of 2026-08-24)

Expected values when verifying a restore:

| Path | Files | Size |
|---|---:|---:|
| `.claude\projects` | 492 (222 `.jsonl`) | 568 MB |
| `.claude-work\projects` | 172 (68 `.jsonl`) | 396 MB |
| `.claude-work\file-history` | 1,705 | 36 MB |
| `local-agent-mode-sessions` | 548 | 36 MB |
| `_session_backup_premove` | 24 | 35 MB |
| `claude-code-sessions` | 127 | 15 MB |
| **Mirror total** | | **~1.1 GB** |

---

## Known issue — the %APPDATA%\Claude blind spot

A PowerShell session running **inside** a Claude Code conversation cannot
see `%APPDATA%\Claude` at all — `Test-Path`, `[System.IO.File]::Exists`
and extended-length paths all return false, while Git Bash reads the same
files fine. The four Desktop-app paths are therefore skipped when the
script is run from inside a Claude session.

**Consequence:** run the script from a **normal PowerShell window**, or
let the nightly task do it. The script's completeness self-check reports
`complete: false` and lists `appdata_gaps` whenever those paths are
missing, so a silent hole is not possible.

If a run ever reports gaps, fill them from Git Bash:

```bash
cp -r "/c/Users/po.nienchen/AppData/Roaming/Claude/claude-code-sessions/." \
      "/c/claude_backups/mirror/desktop_code_sessions/"
cp -r "/c/Users/po.nienchen/AppData/Roaming/Claude/local-agent-mode-sessions/." \
      "/c/claude_backups/mirror/desktop_agent_mode_sessions/"
```
