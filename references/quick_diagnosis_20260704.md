# Quick diagnosis — how this harness leaks tokens, loses focus, and breaks

> Written 4 July 2026 during the Fable 5 system-building session.
> Read this FIRST when wondering why sessions feel slow or expensive.
> Each finding: evidence → concrete fix → status.

## Leak 1 — ~15–18k tokens of always-on config injected into EVERY session

**Evidence (measured 4 July 2026):** `~/.claude/CLAUDE.md` = 534 lines plus
eight `~/.claude/rules/*.md` files (sql.md 455, prior_partners_brand.md 200,
gpkg_to_postgis 65, geoai 58, arcpy 23, notebooks 19, pyqgis 19, python 10)
= **1,383 lines**, all injected even into sessions that touch no SQL, ArcPy
or notebook file (verified empirically in a CSS-only session).

**Root cause (verified against docs):** the conditional-loading frontmatter
key is **`paths:`** — these files use **`globs:`**, which is silently
ignored, so every rule loads unconditionally.
Docs: https://code.claude.com/docs/en/memory.md#path-specific-rules

**Fix:**
1. Rename `globs:` → `paths:` (list syntax, e.g. `paths: ["sql/**/*.sql"]`)
   in: arcpy.md, gpkg_to_postgis.md, notebooks.md, pyqgis.md, sql.md.
2. Shrink CLAUDE.md to a ≤150-line router; relocate bulk content to
   `~/.claude/references/` (verified NOT auto-injected — the scanned set
   is a closed list; `@import` is EAGER, so never use it for big files:
   https://code.claude.com/docs/en/claude-directory.md).
3. Router lines say "before doing X, Read <file>" — an explicit Read is
   the on-demand mechanism weak models can follow.

**Status:** references/ dir created; CLAUDE.md router + `paths:` fixes in
progress this session (see letter_to_future_sessions.md for what landed).

## Leak 2 — state-reconstruction tax + search noise at session start

**Evidence:** 10 versioned `docs/SDC_HANDOVER_V*.md` + root `HANDOVER.md`
+ `SESSION_HANDOFF.md` (two parallel handover systems, ~10k tokens to
re-read); a stale git worktree (`.claude/worktrees/awesome-dijkstra-962dca`)
and 22 duplicate .md files under `bundle/staging/` polluted nearly every
Grep/Glob result this session.

**Fix:**
1. Root `HANDOVER.md` = the ONLY live state file, overwrite-in-place,
   ≤120 lines. Versioned handovers are frozen archive — never re-read
   them unless investigating deep history.
2. User to run once (classifier blocks agent deletion of pre-existing files):
   ```powershell
   git worktree remove ".claude/worktrees/awesome-dijkstra-962dca" --force; git worktree prune
   git branch -D feat/v0.9.5b1-release-prep
   Remove-Item -Recurse -Force bundle\staging   # rebuilt by build_bundle.bat
   ```
3. Agents: when searching this repo, exclude `bundle/`, `.claude/worktrees/`.

## Leak 3 — open loops: approved work left uncommitted across sessions

**Evidence:** the Push-to-GIS fix + headless runner sat uncommitted for
days; the 6 permanently-red "Quirk 9" tests were re-explained in every
session since May; two pending merges interleaved in one working tree.
Every new session re-audited the same diff and re-learned the same
excuses.

**Fix (the commit gate):** when a change is approved and tests pass,
commit it on a branch and open the PR IN THE SAME SESSION — never park
approved work in the tree. A red test baseline is never "known-red":
fix it or delete it (Quirk 9 was a 2-fixture repair, done 4 July 2026,
suite fully green: 237 passed).

## Focus-loss pattern (not a token leak but an error source)

Long sessions interleave threads (style + runner + release + docs).
Weak models lose the pending-decision stack. **Fix:** maintain a
"pending decisions" list at the top of root HANDOVER.md; when the user
pivots mid-thread, append the parked item there BEFORE switching.

## Break 1 — a failing UserPromptSubmit hook blocks every prompt, silently

> Added 26 August 2026 after the "VS Code Claude is not responding" incident.

**Evidence:** Claude Code in VS Code (work profile
`C:\Users\po.nienchen\.claude-work`) accepted prompts but never ran. Nothing
appeared in the chat — no error, no spinner, no reply. The transcript record
carried `"preventContinuation": true` and:

```
UserPromptSubmit operation blocked by hook:
[py -3 "%USERPROFILE%\.claude-work\hooks\reply_style_reminder.py"]:
python.exe: can't open file '...\Qiddiya D2-3 DMP1\%USERPROFILE%\.claude-work\
hooks\reply_style_reminder.py': [Errno 2] No such file or directory
```

**Root cause:** the hook command used `%USERPROFILE%`. Claude Code does NOT
expand `%VAR%` (cmd.exe syntax) in hook commands on Windows. Python received
the literal string `%USERPROFILE%\...`, resolved it against the project cwd,
failed with errno 2 and exited non-zero. A non-zero `UserPromptSubmit` hook
blocks the prompt by design — so a one-character config fault presents as
"Claude is broken", not as a hook error. The hook script itself was fine
(runs, exits 0).

**Fix:**
1. **Absolute paths in every hook command.** Never `%USERPROFILE%`, never `~`.
2. **Test the exact command string in a shell before saving it** — pipe
   `{"prompt":"test"}` into it and check the exit code is 0.
3. **Restart the session after any hook edit.** Hooks are snapshotted at
   session start, so a running session keeps the broken one.
4. **Re-validate the JSON after editing.** `sed` on a Windows path
   under-escapes backslashes and silently produces invalid JSON; edit
   settings files with `json.load`/`json.dumps`, not `sed`.

**Diagnostic recipe** (any "Claude not responding" report, ~30 seconds):

```powershell
# newest transcript in the affected profile, then look for a blocking hook
Get-ChildItem "$env:USERPROFILE\.claude-work\projects" -Recurse -Filter *.jsonl |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
  ForEach-Object { Get-Content $_.FullName -Tail 5 } | Select-String "blocked by hook"
```

The user's original prompt is preserved verbatim in that record — it is
blocked, not lost, so it can simply be re-pasted after the fix.

**Status:** fixed 26 August 2026 in
`C:\Users\po.nienchen\.claude-work\settings.json` (backup:
`settings_json_backup_260826.bak`). Hook re-tested, exit 0.
**Still to check:** the main profile's `pre_tool_geoai_validate_crs.py` hook
uses `${HOME}` — shell-style, so probably fine, but it has NOT been verified
to expand. Confirm before trusting it.
