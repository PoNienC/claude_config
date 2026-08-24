# Restore runbook — Claude data

Written while nothing is broken. Follow it top to bottom when the Claude
Desktop app has failed, a repair has failed, or you are moving to a new
machine.

Backup root: `C:\claude_backups`
Backup script: `~/.claude/tools/claude_backup/backup_claude_data.ps1`

---

## 0. Before you repair or reinstall anything

Run this first. It takes seconds if a mirror already exists, and it is
the difference between a clean restore and a guess.

```powershell
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\tools\claude_backup\backup_claude_data.ps1"
```

Then confirm it succeeded:

```powershell
Get-Content C:\claude_backups\last_backup_manifest.json
```

`failures` must be `[]`. If it is not, fix that before touching the app.

---

## 1. What you do NOT need to restore

- **claude.ai chat conversations.** Server-side. Reinstall, sign in,
  they come back on their own. Do not go hunting for them locally.
- **Claude Code binaries, `vm_bundles/`, caches.** Re-downloaded
  automatically on first launch. They are ~9.9 GB and deliberately not
  in the backup.

If the only thing you lost was the app itself, reinstall and stop here.

---

## 2. Reinstall

1. Reinstall Claude Desktop from the official download.
2. Launch and sign in as `pnchenspacesyntax@gmail.com` (personal Max).
3. Confirm your claude.ai conversations are visible before continuing.
4. If you use the VS Code work setup, confirm the extension
   `anthropic.claude-code` is present in `~/.vscode/extensions`.

---

## 3. Restore config from git (preferred — text, versioned)

Personal config:

```powershell
cd $env:USERPROFILE
git clone https://github.com/PoNienC/claude_config.git .claude_restored
```

Then merge into place, preserving anything new:

```powershell
robocopy "$env:USERPROFILE\.claude_restored" "$env:USERPROFILE\.claude" /E /XO
Remove-Item "$env:USERPROFILE\.claude_restored" -Recurse -Force
```

Work config: clone the work config repo to `~/.claude-work` the same way.
If that repo does not exist yet, use the mirror copy in step 4 instead.

---

## 4. Restore bulk data from the mirror

Each mirror folder maps to exactly one destination:

| Mirror folder | Restore to |
|---|---|
| `mirror\personal_projects` | `%USERPROFILE%\.claude\projects` |
| `mirror\personal_sessions` | `%USERPROFILE%\.claude\sessions` |
| `mirror\personal_session_backup_premove` | `%USERPROFILE%\.claude\_session_backup_premove` |
| `mirror\work_projects` | `%USERPROFILE%\.claude-work\projects` |
| `mirror\work_sessions` | `%USERPROFILE%\.claude-work\sessions` |
| `mirror\work_file_history` | `%USERPROFILE%\.claude-work\file-history` |
| `mirror\work_config` | `%USERPROFILE%\.claude-work` |
| `mirror\desktop_code_sessions` | `%APPDATA%\Claude\claude-code-sessions` |
| `mirror\desktop_agent_mode_sessions` | `%APPDATA%\Claude\local-agent-mode-sessions` |

Restore one with:

```powershell
robocopy "C:\claude_backups\mirror\personal_projects" "$env:USERPROFILE\.claude\projects" /E
```

Restore all of them:

```powershell
$map = @{
  'personal_projects'                = "$env:USERPROFILE\.claude\projects"
  'personal_sessions'                = "$env:USERPROFILE\.claude\sessions"
  'personal_session_backup_premove'  = "$env:USERPROFILE\.claude\_session_backup_premove"
  'work_projects'                    = "$env:USERPROFILE\.claude-work\projects"
  'work_sessions'                    = "$env:USERPROFILE\.claude-work\sessions"
  'work_file_history'                = "$env:USERPROFILE\.claude-work\file-history"
  'work_config'                      = "$env:USERPROFILE\.claude-work"
  'desktop_code_sessions'            = "$env:APPDATA\Claude\claude-code-sessions"
  'desktop_agent_mode_sessions'      = "$env:APPDATA\Claude\local-agent-mode-sessions"
}
foreach ($k in $map.Keys) {
  $src = "C:\claude_backups\mirror\$k"
  if (Test-Path $src) { robocopy $src $map[$k] /E /R:1 /W:1 | Out-Null; Write-Output "restored $k" }
}
```

> Use `/E` here, not `/MIR`. `/MIR` would delete anything in the
> destination that is not in the backup.

---

## 5. Restore the MCP config

Highest value per byte in the whole backup — hand-built and not
reproducible from memory.

```powershell
Copy-Item "C:\claude_backups\config_snapshots\<newest>\claude_desktop_config.json" `
          "$env:APPDATA\Claude\claude_desktop_config.json" -Force
```

Pick `<newest>` with:

```powershell
Get-ChildItem C:\claude_backups\config_snapshots | Sort-Object Name -Descending | Select-Object -First 1
```

If the newest snapshot is itself suspect (the config was already
corrupted when it was taken), walk back through the older snapshots —
that is exactly why 10 generations are kept.

---

## 6. Restore the work VS Code launcher

The work setup is a shortcut, not an install. If the desktop shortcut is
gone, recreate it:

- **Target:** `C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe`
- **Arguments:**
  ```
  -NoProfile -WindowStyle Hidden -Command "$env:CLAUDE_CONFIG_DIR='C:\Users\po.nienchen\.claude-work'; code --user-data-dir 'C:\Users\po.nienchen\.vscode-work'"
  ```
- **Start in:** `C:\Users\po.nienchen`
- **Icon:** `C:\Program Files\Microsoft VS Code\Code.exe,0`

Sign in inside that window as `ponien.chen@priorpartners.com`
(PriorPartners team seat).

---

## 7. Verify

Check each of these before declaring the restore done:

- [ ] `Get-ChildItem "$env:USERPROFILE\.claude\projects" -Recurse -Filter *.jsonl | Measure-Object` — expect ~222
- [ ] `Get-ChildItem "$env:USERPROFILE\.claude-work\projects" -Recurse -Filter *.jsonl | Measure-Object` — expect ~68
- [ ] Personal Claude Code: `/resume` lists your old sessions
- [ ] Work VS Code window: signed in as the priorpartners.com account
- [ ] `/mcp` shows your MCP servers connected
- [ ] `cd $env:USERPROFILE\.claude; git status` — clean, remote is `PoNienC/claude_config`
- [ ] Run the backup script once more so the mirror reflects the restored state

---

## Counts as of the last full survey (2026-08-24)

Use these as the expected-value baseline when verifying:

| Path | Files | Size |
|---|---:|---:|
| `.claude\projects` | 492 (222 `.jsonl`) | 568 MB |
| `.claude-work\projects` | 172 (68 `.jsonl`) | 396 MB |
| `.claude-work\file-history` | 1,705 | 36 MB |
| `local-agent-mode-sessions` | 548 | 36 MB |
| `_session_backup_premove` | 24 | 35 MB |
| `claude-code-sessions` | 127 | 15 MB |

Total mirrored: ~1.1 GB.
