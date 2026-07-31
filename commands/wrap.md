---
description: Reconcile STATUS.md against the session's actual work, then show the diff. Never commits.
allowed-tools: Read, Edit, Write, Glob, Bash(git status:*), Bash(git log:*), Bash(git diff:*)
---

# /wrap

End-of-session reconciliation. Bring the project root's `STATUS.md` back in line with
what actually happened this session, then stop. Do not commit. Do not push.

## Steps

1. **Read the ledger.**
   `STATUS.md` at the project root. If it is missing, say so and ask before creating
   one — never invent a ledger silently.

2. **Gather evidence.** Do not rely on memory of the conversation alone.
   ```bash
   git status --short
   git log --oneline -20
   ```
   Also account for files written this session, tests run, and anything the user
   confirmed explicitly.

3. **Reconcile, item by item.**
   - Every existing `## Open` / `## Blocked` item: did this session touch it? Move it
     only where the evidence supports the move.
   - **Evidence rule** — tick `- [x]` only on a commit, a passing test, a file on disk,
     or the user's explicit confirmation. Otherwise it stays open. State which evidence
     you used for each completion.
   - Work done this session with no matching item → add it straight to
     `## Done recently`, dated today.
   - New outstanding work surfaced this session → add to `## Open` with today as the
     first-seen date and a concrete `Next:` line.
   - Newly blocked → move to `## Blocked` and name the person or ticket it waits on.

4. **Housekeeping.**
   - Never delete an item; only move it between sections.
   - First-seen dates never change. Completion appends `→ done YYYY-MM-DD`.
   - Drop `## Done recently` entries older than 7 days.
   - Update the `_Last updated:_` line.
   - Keep the section headings and item syntax exactly as they are — a scheduled task
     parses this file.

5. **Prose goes to HANDOVER.md**, not STATUS.md — decisions taken, gotchas hit, where
   the code stands. Overwrite it in place, keep it ≤120 lines, pending decisions at the
   top (per `~/.claude/references/maintenance_protocol.md`). If the project has no
   HANDOVER.md, keep the prose in STATUS.md's `## Context for next session` and say so.

6. **Run the session-end checklist** from `maintenance_protocol.md` §"Session-end
   checklist": approved work committed or PR'd, corrections written to memory,
   background servers stopped, new file paths recorded.

7. **Show the diff and stop.** Report the STATUS.md diff, plus anything you chose *not*
   to mark done and why. Give absolute paths for every file touched.

## Failure modes

- **No evidence for a claimed completion** → leave it open and say so plainly. A false
  `- [x]` is worse than a stale `- [ ]`.
- **Nothing ledger-worthy happened** → say "nothing to reconcile" and touch no files.
- **Several projects touched this session** → reconcile only the current working
  directory's STATUS.md, then name the others so they can be wrapped there.
- **STATUS.md hand-edited into a different shape** → repair the syntax rather than
  working around it, and mention what you repaired.
