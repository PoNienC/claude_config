---
name: session_handover
description: Pause the session safely and hand over to a new one — overwrite the live HANDOVER.md (pending decisions first, ≤120 lines) and give a ready-to-paste prompt for the next session. Use when the context guard says the context window is nearly full, when the user types /session_handover, or asks to wrap up, hand over, or continue in a new session.
---

# Session handover

Goal: a new session can carry on from files alone, without this
conversation. Keep it fast — the context is nearly full.

## 1. Stop at a safe point

- Finish only the atomic step in hand: no half-written file, no
  half-applied edit, no uncommitted half of a two-part change.
- Start nothing new. Do not launch new Codex jobs or long commands.
- A background job still running (Codex, tests, a server): do not wait
  more than a minute. Record its output file or log path instead.

## 2. Where the handover goes

- Session started in a project or repo folder → `<that folder>/HANDOVER.md`.
  If that folder is a git repo and `HANDOVER.md` is not ignored, add
  `/HANDOVER.md` to its `.gitignore` in the same change (it is personal).
- Session started in the home folder or with no project → the profile's
  `handovers/<topic_slug>/HANDOVER.md` (`~/.claude/handovers/…`, or
  `~/.claude-work/handovers/…` in the work profile).
- It is the single **live** state file: read the existing one first,
  keep what is still true, overwrite in place. Never create versioned
  copies here (frozen `HANDOVER_<task>_<YYMMDD>.md` notes are a separate,
  manual archive).

## 3. What it contains (≤120 lines, British English, DD Month YYYY)

1. **Pending decisions** — at the very top, numbered, each with the
   options and your recommendation.
2. **State** — done (with commit hashes and files), in flight (exact
   step, branch, `git status` summary), blocked (and on what).
3. **`/dual_dev` request**, if one is active — request ID, repo root,
   phase or gate, current task or block, audit mode, links to
   `TASKS.md`, `AUDIT_LOG.md`, `ALLOCATION.md` / `COMPARISON.md`; any
   Codex job still running and its output file. Make sure `TASKS.md` and
   `AUDIT_LOG.md` are current before writing this.
4. **Next actions** — ordered, concrete, first one doable immediately.
5. **Facts learnt this session** — paths, commands, gotchas the next
   session would otherwise rediscover. Durable lessons also go to memory
   (`~/.claude/references/maintenance_protocol.md`).
6. **Files touched** — absolute paths.
7. **Prompt for the next session** — the same text as step 4 below.

## 4. The prompt for the next session

One fenced `text` block, ready to paste, each paragraph on one line,
under about 120 words:
- which folder to open the new session in;
- "Read `<absolute path of HANDOVER.md>` first — pending decisions are at
  the top", plus any other file it must read;
- the exact next step, and "do not redo finished work";
- for a `/dual_dev` request, start the prompt with
  `/dual_dev --resume <request id> --repo "<repo root>"`.

## 5. Reply, then stop

- One-line result, then: a clickable link and the absolute path of
  `HANDOVER.md` (in a code block), the prompt block, and "Open a new
  session in `<folder>` and paste this prompt."
- Then stop. Do not continue the work in this session unless the user
  explicitly asks.
