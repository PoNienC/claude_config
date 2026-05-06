# Sync guide — ~/.claude/ via GitHub Desktop

How to keep your global Claude Code config (`~/.claude/` on macOS,
`C:\Users\po.nienchen\.claude\` on Windows) in sync between machines using
**GitHub Desktop**, plus copy-paste prompts for asking Claude Code to revise
the synced files for you.

Repo: <https://github.com/PoNienC/claude_config>
Branch: `main`. Source of truth alternates per session — whichever machine
last pushed wins; the other must pull before editing.

---

## 1. One-time setup per machine

### Mac
1. Install GitHub Desktop from <https://desktop.github.com>.
2. Sign in with your `PoNienC` GitHub account.
3. **File → Add local repository** → choose `~/.claude` (already a clone).
   - If GitHub Desktop complains "this is not a git repo," then
     `~/.claude/.git/` is missing — re-run the Mac-side bootstrap first.

### Windows

If `C:\Users\po.nienchen\.claude\` already exists with runtime state from a
previous Claude Code launch (almost certain on a machine where Claude Code has
been opened even once), `git clone` directly into it will fail. Bootstrap with
the **clone-merge** pattern, then add the repo to GitHub Desktop.

#### First-time bootstrap (clone-merge into existing folder)

```powershell
# 1. Cache GitHub credentials so the PAT is reused
git config --global credential.helper manager

# 2. Clone the synced repo to a scratch dir
$tmp = Join-Path $env:TEMP 'claude_config_clone'
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
git clone https://github.com/PoNienC/claude_config.git $tmp
# (GCM will prompt once for your PAT, then cache it for future ops.)

# 3. Merge tracked content into .claude\, preserving runtime dirs.
#    /E includes hidden .git; /XO is defensive vs same-or-newer files.
robocopy $tmp 'C:\Users\po.nienchen\.claude' /E /XO

# 4. Clean up the scratch dir (use Git Bash or cmd — see gotcha below)
```

#### Verify

```powershell
cd C:\Users\po.nienchen\.claude
git log --oneline -3      # confirms HEAD matches origin
git status                # tracked files clean; runtime dirs ignored
git remote -v             # origin → PoNienC/claude_config

# Line endings on .sh hooks should be LF (per .gitattributes eol=lf)
$bytes = [System.IO.File]::ReadAllBytes('hooks\session_start_context.sh')
$hasCRLF = $false
for ($i=0; $i -lt $bytes.Length-1; $i++) {
  if ($bytes[$i] -eq 13 -and $bytes[$i+1] -eq 10) { $hasCRLF = $true; break }
}
Write-Output "hasCRLF=$hasCRLF"   # expect False
```

#### PowerShell 5.1 gotcha — `$env:TEMP` short-name path

`$env:TEMP` resolves to a Windows 8.3 short-name path
(`C:\Users\<USER>~1.<DOM>\AppData\Local\Temp\…`). PowerShell 5.1's `Move-Item`
and `Remove-Item` reject that form with "An object at the specified path …
does not exist." Workarounds:

- `robocopy` handles short-name paths fine — use it for the merge step.
- For cleanup, use Git Bash (`rm -rf "/c/Users/<you>/AppData/Local/Temp/claude_config_clone"`)
  or `cmd /c "rmdir /s /q %TEMP%\claude_config_clone"`.

#### Add to GitHub Desktop

After bootstrap:

1. Install GitHub Desktop from <https://desktop.github.com>.
2. Sign in with your `PoNienC` GitHub account.
3. **File → Add local repository** → choose `C:\Users\po.nienchen\.claude`.

After this, both machines see the repo as "claude_config" in the GitHub
Desktop sidebar.

---

## 2. Daily workflow

### Before starting any editing session

1. Open GitHub Desktop, select **claude_config**.
2. Click **Fetch origin**. If it shows "Pull origin (N commits)", click that.
3. **Quit and relaunch Claude Code** so it re-reads any new skills, agents,
   commands, or `settings.json`.

> **Why first**: editing without pulling first risks merge conflicts that you
> then have to untangle by hand.

### After making changes (whether via Claude Code or by hand)

1. Open GitHub Desktop → the **Changes** tab shows modified files.
2. Review the diff in the right pane. Sanity-check that runtime files
   (`sessions/`, `projects/`, `debug/`, `.credentials.json`, etc.) are NOT
   showing — `.gitignore` should already block them. If you see any, **do
   not commit** — investigate first.
3. Write a commit message in the lower-left box. Convention used so far:
   imperative mood, optional body (`Update agent X to do Y`).
4. Click **Commit to main**.
5. Click **Push origin** in the top bar.
6. On the other machine, repeat **section 2 / "Before starting"** before your
   next session there.

### Bidirectional discipline

Both machines edit and push. There is no "primary" — source of truth is "the
latest commit on `origin/main`". To keep history linear and avoid merge
bubbles in this small personal repo:

- **Default to rebase, not merge.** From the command line:
  `git pull --rebase origin main`. From GitHub Desktop:
  **Branch menu → Rebase current branch onto upstream branch**.
- **If a rebase has conflicts**, fall back to the prompt in § 5.7 ("Resolve a
  merge conflict") to have Claude Code untangle it.
- **Never `git push --force` to `main`.** If you ever feel the need to, stop
  and ask — there's almost always a non-destructive path.
- **"I forgot to pull and now have local commits"** recipe: `git pull --rebase`
  picks up the remote commits and replays yours on top. If it can't auto-merge,
  same § 5.7 prompt.
- **Settings hygiene**: machine-local prefs (theme, autoUpdatesChannel,
  machine-specific MCP servers) belong in `settings.local.json`, which is
  gitignored. Only put genuinely-shared config in tracked `settings.json`.
  Claude Code merges both at runtime.

---

## 3. The underscore naming rule

All names in this repo use underscores, never dashes. Applies to: files,
folders, branch names, slash commands, agent/skill `name:` frontmatter,
identifiers. If GitHub Desktop ever shows you committing a dash-named file,
stop and rename it first.

All current files comply. To enforce going forward, use the bulk audit prompt
in § 5.7.

---

## 4. What never to commit

`.gitignore` should already block these, but verify before clicking commit:

- `.credentials.json`, `oauth_account.json` — auth tokens
- `mcp-needs-auth-cache.json` — MCP auth state
- Anything under `sessions/`, `projects/`, `debug/`, `telemetry/`, `statsig/`,
  `shell-snapshots/`, `backups/`, `session-env/`, `plans/` — runtime/local
- Any `.env` file
- `plugins/` — installed via marketplace, not source

If you ever notice `git status` shows one of these as tracked (not untracked),
that's a `.gitignore` bug — fix the `.gitignore` rather than committing.

---

## 5. Asking Claude Code to revise the synced files

Open Claude Code in any working directory (CC reads global `~/.claude/`
regardless of cwd). Paste these prompts. Replace `<placeholders>` with real
names. After CC finishes, switch to GitHub Desktop to review the diff,
commit, and push.

### 5.1 Skills

**Update a skill body**
```
Read ~/.claude/skills/<skill_name>/SKILL.md and revise it to <describe
the change — e.g. "add a step for handling NULL geometries">. Preserve
the YAML frontmatter (name, description, triggers). Keep the file under
500 lines.
```

**Improve a skill's triggering description (so it fires more reliably)**
```
Open ~/.claude/skills/<skill_name>/SKILL.md. The description field in the
frontmatter is what Claude uses to decide when to load this skill.
Rewrite the description so it (a) names the concrete triggers — file
extensions, library imports, user phrases — and (b) lists what it does
NOT cover, to suppress false positives. Don't change the body.
```

**Create a new skill**
```
Use the skill_creator skill to create a new skill named <snake_case_name>
that <describe purpose>. The trigger conditions are <list them>. Save it
under ~/.claude/skills/<snake_case_name>/SKILL.md. Use underscores in the
folder name and the frontmatter `name:` field.
```

**Audit all skills for inconsistencies**
```
Read every SKILL.md under ~/.claude/skills/. Report a table with: skill
name, whether the folder name matches the frontmatter `name:`, whether
the description is over 250 chars (too long) or under 50 (too vague),
and whether any dashes appear in the name. Don't change anything yet —
just the report.
```

### 5.2 Agents

**Update an agent**
```
Read ~/.claude/agents/<agent_name>.md and revise <which section — system
prompt, description, examples> to <describe change>. Don't add scope
the agent didn't already have. Preserve frontmatter.
```

**Tighten an agent's description for better routing**
```
The description field of ~/.claude/agents/<agent_name>.md is what the
main agent reads when deciding whether to delegate to this subagent.
Rewrite it so the trigger conditions are concrete (specific tasks, file
types, or user phrases) and the boundaries are explicit (what to refuse
or hand back). Body unchanged.
```

### 5.3 Slash commands

**Update a command**
```
Open ~/.claude/commands/<command_name>.md and <describe change>.
Preserve frontmatter (description, allowed-tools, argument-hint).
```

**Add a new slash command**
```
Create ~/.claude/commands/<snake_case_name>.md as a new slash command
that <describe what it does>. Use underscores in the filename.
Frontmatter must include description and allowed-tools. The body should
be the prompt that runs when I type /<snake_case_name>.
```

### 5.4 Hooks

**Add a new hook script**
```
Create ~/.claude/hooks/<snake_case_name>.sh as a <PreToolUse|PostToolUse|
SessionStart|Stop> hook that <describe behavior>. Save with LF line
endings (the .gitattributes already enforces this). Then update
~/.claude/settings.json via the update-config skill to wire the hook to
the right event.
```

**Note**: Windows can't natively execute `.sh` hooks. If you need hooks
to fire on both OSes, ask:
```
The hook ~/.claude/hooks/<name>.sh needs to run on Windows too. Create a
PowerShell sibling at ~/.claude/hooks/<name>.ps1 with equivalent
behavior, and update settings.json to use the OS-appropriate one. Use
update-config skill for the settings change.
```

### 5.5 Rules

**Update a rule**
```
Open ~/.claude/rules/<rule_name>.md and <describe change>.
```

### 5.6 settings.json

Use the **update-config** skill — it knows the schema and won't corrupt
the file:
```
Use update-config to <add permission for "Bash(npm:*)" | set env var
DEBUG=true | wire hook X to event Y | etc>.
```

### 5.7 Bulk operations

**Enforce the underscore rule across the whole repo**
```
Find any dash-named files or folders under ~/.claude/ (in skills/,
agents/, commands/, hooks/, rules/). For each: rename to underscores
using `git mv` (so history is preserved), and update any internal
references that name them — agent/skill frontmatter `name:` fields,
slash command headings, README tables, hook script comment headers.
Stage everything but don't commit; I'll review the diff in GitHub
Desktop and commit there.
```

**Check sync status**
```
cd to ~/.claude/. Run `git fetch`, then tell me: am I ahead, behind, or
in sync with origin/main? List any uncommitted changes. Don't pull or
push.
```

**Resolve a merge conflict**
```
~/.claude/<file> has a merge conflict after pulling. The "ours" side is
<describe what you changed locally>; "theirs" is <describe what the
other machine pushed>. Pick the right resolution and write the merged
file. Explain which conflicts you resolved and how.
```

---

## 6. Restart Claude Code after pulling

Whenever GitHub Desktop pulls new commits that touch `skills/`, `agents/`,
`commands/`, `hooks/`, or `settings.json`, you must fully quit and relaunch
Claude Code. The CLI loads these at startup and won't re-read them mid-session.

Mac: `Cmd-Q`, then relaunch.
Windows: close the window, then run from a fresh PowerShell:
```powershell
Get-Process -Name claude -ErrorAction SilentlyContinue | Stop-Process -Force
```
…then relaunch from your usual launcher.

---

## 7. Quick reference

| Action | Where to do it |
|---|---|
| See what changed | GitHub Desktop → Changes tab |
| Pull updates | GitHub Desktop → Fetch origin → Pull origin |
| Commit + push | GitHub Desktop → Commit → Push origin |
| Edit a skill / agent / command | Ask Claude Code (section 5) |
| Tweak settings.json | Ask Claude Code with the update-config skill |
| Verify CRLF/LF on hooks | Section 5.4 prompt, or `git check-attr eol path/to/file.sh` |
| Restart CC | Cmd-Q (Mac) / `Stop-Process -Name claude -Force` then relaunch (Win) |
