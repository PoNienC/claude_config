---
name: dual_plan
description: Fast two-agent plan — Claude and Codex each plan the same request in parallel from one shared context pack, then Claude merges the two into a single plan for the user to review. Planning only, no implementation; the merged plan can start /dual_dev with --plan. Only when the user types /dual_plan.
argument-hint: "[--repo <path>] [--deep] <what to plan>"
disable-model-invocation: true
---

# Dual plan — two plans in parallel, one merged plan to review

Request: $ARGUMENTS

In short: the user gets ONE merged plan (`PLAN.md`, "In short" first)
within a few minutes, with both source plans saved beside it. Nothing is
implemented and no gate files are written. The speed comes from three
things — never skip them:

1. **One context pack, built once by you, used by both planners.** Codex
   plans from pasted text instead of exploring the repo (its plans took
   7–14 minutes and 13–26 shell commands each when it explored; audits
   dropped from ~7 minutes to ~1.5 when the diff was pasted).
2. **Codex is launched before you write anything**, and you plan while it
   runs. Never wait for Codex before starting your own plan.
3. **A light merge**: one file, at most 8 difference points — not the
   /dual_dev comparison tables.

## Fixed conventions

- **Skill dir** = the base directory shown when this skill loaded; the
  skills folder is its parent. Scripts: `<skill dir>/scripts/`,
  templates `<skill dir>/templates/`. Codex runs through the dual_dev
  launcher: Windows `<skills>\dual_dev\scripts\run_codex.ps1` (PowerShell
  tool), macOS `bash <skills>/dual_dev/scripts/run_codex.sh` (Bash tool),
  `run_in_background: true`, mode `plan` (read-only sandbox).
- **Options** (strip them from the request): `--repo <path>` names the
  repo; `--deep` runs Codex at effort `high` instead of the default
  `medium` (use for large or risky requests only).
- **Plan folder** `<PD>`: inside a repo that has `.ai/`,
  `<repo root>/.ai/plans/<yymmdd>_<slug>/` (slug = two to four
  snake_case words); otherwise `<session scratchpad>/plan_<yymmdd>_<slug>/`.
  Files: `context_pack.md`, `codex/plan_brief.md`, `codex/plan_out.md`,
  `PLAN_A.md`, `PLAN_B.md`, `PLAN.md`. Nothing is committed.
- **Time budget:** if Codex has not returned 10 minutes after launch,
  tell the user in one line and offer to review your plan alone now
  (Codex's plan is merged in later if it arrives). Launcher exit 1 or 2:
  say so, give the log path, and present your plan alone — say it is
  single-agent.
- **Codex usage:** report the `CODEX USAGE` line in one line after the
  call; above 80% of the limit, ask before launching.
- Links and paths: every message that refers to plan files opens with
  clickable links (relative to the session's working folder, spaces as
  `%20`) then one code block of absolute paths — as in /dual_dev.

## Steps

### 1. Context pack (target: under 3 minutes of your time)

1. Find the repo root: `--repo`, else `git rev-parse --show-toplevel`
   from the current folder, else the first repo up to three levels down
   whose root has `AGENTS.md` or `.ai/` — state it in one line. No repo
   at all: plan from the request and any files the user named, with an
   empty tree.
2. Pick the relevant files — fast, not exhaustive: `git grep -l` for two
   to four keywords from the request, plus the obvious modules, tests
   and configs; at most 12 files, the ones the plan will touch or must
   respect. Do not read them yet.
3. Build the pack:
   `node "<skill dir>/scripts/build_context_pack.mjs" --repo "<repo root>" --out "<PD>/context_pack.md" --include <path> --include <path> …`
   (paths relative to the repo root; cap 160k characters; it prints a
   `CONTEXT PACK:` line — check the included-file count).
4. Fill `templates/codex_plan_brief.md` (`{{REQUEST}}` verbatim,
   `{{TITLE}}`, `{{NOTES}}` = constraints the user gave, else empty),
   append the whole context pack under a final heading
   `## Context pack (pasted)`, save as `<PD>/codex/plan_brief.md`, and
   **launch Codex now**: mode `plan`, effort `medium` (`high` with
   `--deep`), out `<PD>/codex/plan_out.md`.

### 2. Your plan (while Codex runs)

Write `PLAN_A.md` from the same pack (read more files only if the pack
is missing something — then note it, so the merge can weigh it). Same
sections as the Codex brief, header `Author: Claude Code`, under about
900 words. Do not read `codex/` until your plan is saved.

### 3. Merge (after Codex returns)

1. Save Codex's output unchanged as `PLAN_B.md`, header line
   `Author: Codex, model <from the launcher's OK line>, effort <effort>, <time>s`.
2. Compare on merit, not authorship: tasks, order, files touched, tests,
   risks, open questions. Note what only one plan found.
3. Write `PLAN.md` from `templates/plan_merged.md`, every section filled:
   "In short" first; at most 8 difference points, each saying what was
   taken and why; the merged task list with each task's source (A, B,
   both or new); open questions only where neither plan could decide.
4. Delete nothing; the pack stays for reuse by /dual_dev.

### 4. Reply and decision

- Review links first: `PLAN.md` (open this first), `PLAN_A.md`,
  `PLAN_B.md`; then the absolute paths in one code block; then at most
  six bullets: what the plan delivers, the biggest difference between
  the two plans and what the merge took, timing (Codex seconds and
  tokens; your own elapsed time), and anything that needs the user.
- Then ONE decision, asked in the chat per the user's "Input from me"
  rules (short bold title; what yes does; recommendation; what no does):
  approve the merged plan as written · approve with changes (the user
  says which) · take one plan as it stands · revise (the user says what;
  repeat from step 1.4 with the notes, reusing the pack).
- On approval, record the decision at the top of `PLAN.md` (option, date,
  the user's words verbatim) and offer, in one line, to execute it with
  `/dual_dev --plan "<absolute path of PLAN.md>" <request>`.
