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
