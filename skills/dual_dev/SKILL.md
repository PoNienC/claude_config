---
name: dual_dev
description: Run the dual-agent development workflow — independent Claude and Codex plans (or a light mode where Codex reviews Claude's plan), a human plan gate, explicit task allocation, execution with reciprocal Claude/Codex audit per task, per block or at the end, audits in the background with an early hand-off, and local commits. Only when the user types /dual_dev.
argument-hint: "[--resume <request id>] [--plan <path>] [--solo_plan] [--xhigh] [--model <name>] [--repo <path>] <development request>"
disable-model-invocation: true
---

# Dual-agent development workflow

Request: $ARGUMENTS

You are the workflow coordinator, not the sole decision-maker. Follow the
phases in order. **No implementation before Gate 1 and Gate 2 are both
passed.** The user's global rules still apply: short replies, British
English, clickable links plus absolute paths, no "claude" in any name or
commit message, no AI credit lines in commits.

## Fixed conventions

- **Skill dir** = the base directory shown when this skill loaded.
  Templates: `<skill dir>/templates/`. Launcher by OS:
  Windows → `<skill dir>\scripts\run_codex.ps1` (PowerShell tool);
  macOS / Linux → `bash <skill dir>/scripts/run_codex.sh` (Bash tool) with
  `--mode --repo --brief --out --effort --model --diff-range` in place of
  the `-Mode -Repo -BriefFile -OutFile -Effort -Model -DiffRange`
  parameters. Same modes, exit codes and output.
- **Repo root** = found in Phase 0 step 1; the session may sit in a parent
  folder (e.g. the project root, with the repo in `04_Code\<name>`).
  Every git command therefore uses `git -C "<repo root>"`, and every file
  path is absolute under the repo root.
- **Request ID** = `T###_slug`: next number above the highest folder in
  `.ai/tasks/` (start at `T001`), slug = two to four snake_case words.
  **TD** = `.ai/tasks/<request id>/` (use its absolute path in commands).
- Tasks inside a request: `T01`, `T02`, …
- **Codex effort per step** (pass `-Effort` on every call):

  | Step | Default | With `--xhigh` |
  |---|---|---|
  | Plan, plan review | `high` | `xhigh` |
  | Execute, corrections | `high` | `xhigh` |
  | Audit round 1 | `medium` | `medium` |
  | Re-check (round 2, the last) | `low` | `low` |

  Strip `--xhigh` from the request. The user can change any row at Gate 2
  or at any point; record the table in `ALLOCATION.md` and `TASKS.md`.
- **Approved plan from /dual_plan:** `--plan <path>` in the request (strip
  it) names a `PLAN.md` written by the `dual_plan` skill and approved by
  the user (its "Decision" line is filled). Phases 1 and 2 are then
  skipped: Phase 0 runs as usual, Phase 3 starts from that file (copy it
  into TD as `PLAN_APPROVED.md` with the source line "dual_plan, merged
  from Claude and Codex, approved <date>"; copy its `PLAN_A.md`,
  `PLAN_B.md` and `context_pack.md` into TD too). If the Decision line
  is still pending, stop and ask the user to approve the plan first.
- **Light mode:** `--solo_plan` in the request (strip it) — for small,
  clear requests. Claude writes the only plan; Codex reviews it instead of
  planning independently (Phase 1 and Gate 1 below). Suggest it in one
  line when a request looks small, but only the user switches it on.
- **Codex model** = Codex's own default (`model` in `~/.codex/config.toml`,
  shared with the Codex app); the launcher's OK line shows it as
  `model=default(<name>)`. Use another model if the request includes
  `--model <name>` (strip it) or the user asks at a gate: pass
  `-Model <name>` (Windows) / `--model <name>` (macOS) on every launcher
  call for that request. Record the model in `REQUEST.md`.
- **Audit models:** audits use the request's models — Codex at audit
  effort, the audit subagent on the session model. There is no
  fast-audit option: on 15 October 2026 no faster model kept audit
  quality (Codex gpt-6.1-sol 94 s vs 79 s for the default; gpt-6-luna
  13 s but missed the main flaw; a Sonnet subagent 19 min vs 18 min).
- **Every Codex call goes through the launcher.** Never call `codex`
  directly and never use the plugin's `/codex:*` commands here — the
  launcher carries the Windows sandbox fix and the read-only/write split.
  Run it with `run_in_background: true`; you are notified when it exits.
  Then read the output file.
  Exit 0 = OK. Exit 1 = failed. Exit 2 = degraded (Codex could not run
  commands). On 1 or 2: tell the user, give the log path, do not use the result.
- **Windows sandbox note:** Codex can execute tasks on Windows only with
  `[windows] sandbox = "elevated"` in `~/.codex/config.toml` (one-time
  admin setup). With `"unelevated"`, write mode refuses every command
  ("cannot enforce split writable root sets") or stalls; the launcher
  returns exit 2. PRIORPLAP180 was switched to elevated on 7 October 2026
  (write inside the repo works, write outside is denied). The sandbox
  accounts run as the group `CodexSandboxUsers`: programs installed
  per-user under `%LOCALAPPDATA%\Programs` (Git, Python) need
  `icacls "%LOCALAPPDATA%\Programs" /grant "CodexSandboxUsers:(OI)(CI)RX"`
  run once by the user (done on PRIORPLAP180, 12 October 2026) — without
  it Codex "cannot read git". `~/.config` stays private; the launcher
  gives Codex a readable copy of the global git ignore file. Whether Codex
  may execute on the current machine comes from `.ai/PROJECT.md` (see
  Phase 3). After any Codex execute run, always check `git diff` yourself
  — a stalled run can still print "CODEX OK" with nothing changed.
- **Codex usage:** every launcher run prints a `CODEX USAGE:` line —
  tokens for that call, and the plan limit % used with its reset time
  (from the sibling `codex_usage` skill). After each Codex step, tell the
  user in one line: step, tokens, limit % used. Keep a running total:
  `Codex tokens so far: <n>` in `REQUEST.md` until `TASKS.md` exists, then
  in the `TASKS.md` header. If any limit is above 80%, stop before the next
  Codex call and ask: continue, lower the effort (`medium` / `low`), or
  pause — never switch to a self-audit.
- **Git conventions** = `.ai/PROJECT.md` → section "Git conventions"
  (branch pattern, commit format, push policy, pull request rules, GitHub
  account). **Project rules win.** Defaults only where the project has none:
  branch `dual_dev/<request id>`, commit `T01 <task title>`, no push
  without approval. Slugs use underscores; keep any separator the
  project's pattern fixes (e.g. `feat/<module>-T001_slug`).
- **Background audits:** every audit runs in the background so the chat
  and the next task stay free — Codex audits through the launcher,
  Claude's audits as a read-only subagent (Phase 4). An audit reviews a
  committed range (Codex reads files at its end commit; the subagent
  reads a snapshot of it), so later edits do not disturb it, and
  several audits may run at once.
  **One writer at a time:** you, or one Codex `execute` call — never
  both, and never two `execute` calls. The one exception: while Codex
  executes you may update the `.ai/` bookkeeping files (`TASKS.md`,
  `AUDIT_LOG.md`, `REVIEW.md`, saved reports), which Codex never
  touches — but make no commit until it ends. Keep `TASKS.md` → "Running now"
  current: add every background job when you launch it (Codex plan,
  audit, re-check or execute call; audit subagent) with its start time
  and output file, and remove it when it ends.
- **Review files and links:** chat stays short; the full detail always
  goes into a Markdown file in TD **before** you ask the user anything
  (Gate 1 → `COMPARISON.md`, or `GATE1_REVIEW.md` in light mode;
  Gate 2 → `ALLOCATION.md`; hand-off → `REVIEW.md`; completion →
  `TASKS.md`, `AUDIT_LOG.md` and `REVIEW.md`). Never ask a gate question before its
  review file exists and is complete. Every message that refers to these
  files opens with them as clickable links, then one code block with
  their absolute paths:
  - link target = the path **relative to the session's working folder**,
    forward slashes, spaces written `%20`, e.g.
    `[COMPARISON.md](04_Code/arcgis_workflows/.ai/tasks/T003_x/COMPARISON.md)`;
  - only if the file is outside the working folder, use
    `file:///C:/full/path` (spaces `%20`) instead.
  Link text is the file name; add "open this first" to the main one.

Launch pattern (fill the placeholders in a template first and save it as the brief):

```powershell
& "<skill dir>\scripts\run_codex.ps1" -Mode <plan|audit|execute> -Repo "<repo root>" -BriefFile "<TD>\codex\<step>_brief.md" -OutFile "<TD>\codex\<step>_out.md" -Effort high [-Model <name>]
```

```bash
bash "<skill dir>/scripts/run_codex.sh" --mode <plan|audit|execute> --repo "<repo root>" --brief "<TD>/codex/<step>_brief.md" --out "<TD>/codex/<step>_out.md" --effort high [--model <name>]
```

Step names: `plan`, `plan_r2`, `T01_audit_r1`, `T01_exec`, `T01_fix_r1`, `T01_audit_r2`, `B1_audit_r1`, …
Claude's audit subagent uses the same step names: its report is
`TD/subagent/<step>_out.md`; its brief, changes file and snapshot live in
a scratchpad work folder (Phase 4), never in the repo.

## Resuming a request (`--resume <request id>`)

Used by a new session after a handover (see "Context guard" below).

1. Find the repo root (Phase 0 step 1; `--repo` usually given). Read, in
   this order: the root `HANDOVER.md` if it names this request, then in
   TD: `REQUEST.md`, the Gate 1 file, `PLAN_APPROVED.md`,
   `ALLOCATION.md`, `TASKS.md`, `TASK_HANDOVER.md`, `AUDIT_LOG.md`, and
   `REVIEW.md` if it exists.
2. Check the repo matches the record: current branch, `git status`, and
   the last commits against `TASKS.md`. Report any mismatch and ask
   before going on.
3. Background work started by the old session is not tracked here (see
   `TASKS.md` → "Running now"). A Codex job: if its output file exists,
   use it; if not and no Codex process is running, re-launch that step.
   A Claude audit subagent cannot be reached: if its `_out.md` is
   missing, prepare it again in this session (Phase 4, subagent steps
   1–3: a new work folder with snapshot, changes file and brief in this
   session's scratchpad) and re-launch it.
4. Chat, review links first: where the request stands in at most six
   bullets, and the next step. Then continue from that step — a pending
   gate is asked again; Phase 4 continues with the next task or audit;
   after the hand-off, Phase 5 continues with the open audits, or
   Phase 6 once the user said close out.
   Never redo finished, committed work. Skip Phases 0–3 otherwise.

## Context guard

A hook tells you when this session's context is 90% full. Then: finish
the step in hand, make sure `TASKS.md` (with "Running now") and
`AUDIT_LOG.md` are current, run the `session_handover` skill, and give
the prompt
`/dual_dev --resume <request id> --repo "<repo root>"`. At 95% without a
handover the hook stops you; the user then types `/session_handover`.

## Phase 0 — Context

1. Find the repo root, in this order:
   - `--repo <path>` in the request (strip it) → `git -C <path> rev-parse --show-toplevel`;
   - else `git rev-parse --show-toplevel` from the current folder;
   - else search down to three levels below the current folder for a
     `.git` folder or `.git` pointer file (skip `_work*`, `node_modules`,
     `.venv`, `venv`; listing folders only, never opening data files), and
     keep the repos whose root `AGENTS.md` contains "Dual-agent development
     contract". One found → state its path and confirm with the user;
     several → ask which one (AskUserQuestion); none → stop.
   If the chosen repo's `AGENTS.md` lacks "Dual-agent development
   contract" or `.ai/` is missing, stop and tell the user to run
   `/dual_dev_init` first. If its contract section lacks the line
   "Hand-off before audits finish", it predates the current workflow
   (background audits, early hand-off, one re-check): tell the user in
   one line that this skill and the briefs govern, and offer to refresh
   that section from `templates/agents_contract.md` as the first change
   on the request branch.
   The current branch may be an unmerged setup branch (for a pilot). That
   is allowed: note in `REQUEST.md` that the request branch stacks on it,
   and warn that its pull request will include the setup commit unless
   setup merges first.
2. Read `AGENTS.md`, `.ai/PROJECT.md`, `.ai/STATE.md`, `.ai/DECISIONS.md`;
   run `git status`, `git branch --show-current`, `git log --oneline -10`.
   If `.ai/PROJECT.md` has no "Git conventions" section, read the
   project's branch, commit and push rules from `CLAUDE.md` (and
   `CONTRIBUTING.md`, `docs/`), use them, and tell the user to re-run
   `/dual_dev_init` to record them.
3. If the request is a trivial edit, say so and ask whether to skip the
   workflow.
   Check that the Agent tool lists `dual_dev_auditor` (Claude's audits
   of Codex work need it). If not, say so once in one line: those audits
   would fall back to `general-purpose`, read-only by instruction only;
   to install, put `dual_dev_auditor.md` in the profile's `agents/`
   folder (`~/.claude/agents/`, or `~/.claude-work/agents/` in the work
   profile) — a new file can take minutes to load, a new folder needs a
   restart.
4. If the working tree is not clean, stop and ask: commit, stash or abort.
5. Ask clarifying questions only if the request is genuinely ambiguous.
6. Create TD and write `TD/REQUEST.md`: the request verbatim, confirmed
   constraints and answers, effort, date (DD Month YYYY), starting branch
   and commit hash.
7. Do not modify any source file.

## Phase 1 — Independent dual planning

1. Fill `templates/codex_plan_brief.md` (`{{REVISION_NOTE}}` empty) →
   `TD/codex/plan_brief.md`. Launch Codex, mode `plan`, in the background **now**.
2. While Codex runs, write your own plan with the same sections as the
   brief's output (Objective … Open questions). Read source as needed, but
   do not read anything under `TD/codex/` except the brief.
3. Save your draft to the session scratchpad (outside the repo) as
   `plan_a_<request id>.md`. Codex cannot see it there, and it survives
   context compaction. Do not write it into the repo yet.
4. Only after your draft is saved, wait for the Codex notification and read
   `TD/codex/plan_out.md`.
5. Write `TD/PLAN_A.md` (your draft unchanged, header line
   `Author: Claude Code`) and `TD/PLAN_B.md` (Codex output unchanged, header
   line `Author: Codex, model <model from the launcher's OK line>, effort <effort>`).

Running both at once keeps independence: neither plan is seen by the other
agent before both are saved.

### Light mode (`--solo_plan`) instead of steps 1–5

1. Write your plan (same sections) to `TD/PLAN_A.md`, header line
   `Author: Claude Code (light mode)`.
2. Fill `templates/codex_plan_review_brief.md` → `TD/codex/plan_review_brief.md`;
   launch Codex, mode `plan`, plan-review effort; wait.
3. Save Codex's output unchanged as `TD/PLAN_REVIEW.md`, header line
   `Author: Codex, model <model>, effort <effort>`.
4. Evaluate every finding on its merits: ACCEPTED, PARTIALLY_ACCEPTED or
   REJECTED, with a reason. Do not edit `PLAN_A.md` yet — accepted changes
   go into the Gate 1 file and then into `PLAN_APPROVED.md`.
5. If Codex says the request needs the full two-plan mode, say so at Gate 1.

## Phase 2 — Comparison and Gate 1

**Light mode:** write `TD/GATE1_REVIEW.md` from
`templates/gate1_solo_review.md` (every section filled) instead of
`COMPARISON.md`; link `GATE1_REVIEW.md` (open this first), `PLAN_A.md`
and `PLAN_REVIEW.md`; ask **A** approve with the accepted changes ·
**B** approve as written · **C** switch to full two-plan mode (run Phase 1
steps 1–5 now) · **D** revise. Record the decision at the top of
`GATE1_REVIEW.md`. Otherwise:

1. Write `TD/COMPARISON.md` from `templates/gate1_comparison.md`, every
   section filled. It must stand on its own: the user decides from this
   file alone — full differences table, both task lists side by side,
   testing compared, one-plan-only risks, and the recommended hybrid as a
   numbered task list with each task's source. Judge on merit, not
   authorship.
2. Chat — **review links first**, per "Review files and links": links to
   `COMPARISON.md` (open this first), `PLAN_A.md`, `PLAN_B.md`, then the
   absolute paths in one code block, then at most six bullets on the key
   differences and your recommendation.
3. Gate 1 with AskUserQuestion: **A** Claude plan · **B** Codex plan ·
   **C** Hybrid (as in `COMPARISON.md`, or the user's mix) · **D** Revise
   both. Put your recommendation first; each option's description names
   the section of `COMPARISON.md` that explains it.
4. **STOP** until answered. Record the decision at the top of
   `COMPARISON.md` (option, date, the user's words verbatim). On D: append
   the revision notes to `REQUEST.md`, then repeat Phase 1 as round 2
   (fresh Codex run, step `plan_r2`, `{{REVISION_NOTE}}` = the notes; keep
   round-1 files).

## Phase 3 — Approved plan and Gate 2

1. Write `TD/PLAN_APPROVED.md`: the source (A, B or hybrid — or, in light
   mode, Claude's plan plus the accepted review changes — with the user's
   instructions verbatim), then atomic tasks `T01`… each with objective,
   dependencies, likely files, acceptance criteria, tests and risk level.
2. Check `.ai/PROJECT.md` for "Codex execution on <this machine>". Not
   "available" (or missing) → Claude executes all tasks; say so in one line
   and skip to step 3 with option A only.
   Otherwise recommend an allocation. Give Codex tasks that are independent,
   well scoped, testable and interface-stable — not "a share of the work".
   Never split tightly coupled tasks across agents.
3. Write `TD/ALLOCATION.md` from `templates/gate2_allocation.md`, every
   section filled, **before** asking: the proposed split with a reason per
   task, what each option means (who executes, who reviews, estimated
   Codex calls), the **audit mode** (see Phase 4) with the blocks and the
   audit points it creates, overlap (default on; which blocks could
   overlap), the audit review option, effort and models per step, the
   order of work up to the hand-off, the Git plan from the Git
   conventions (branch, commit format, when commits happen under the
   chosen audit mode, one close-out commit, push policy), cost so far and
   the current limit %, and the risks of the split. When Codex execution
   is not available, the file says so and shows option A only.
4. Chat — **review links first**, per "Review files and links": links to
   `ALLOCATION.md` (open this first) and `PLAN_APPROVED.md`, then the
   absolute paths in one code block, then at most six bullets: who does
   which tasks, and your recommendation.
5. Gate 2 with one AskUserQuestion call holding up to four questions:
   (1) split — **A** Claude executes all (default) · **B** Split as in
   `ALLOCATION.md` · **C** Codex executes all · **D** Custom;
   (2) audit mode — `per_block` with overlap (default), `per_block`
   without overlap, `end` or `per_task`, each with its audit count;
   (3) **audit review** — `auto` (default), `ask` or `ask_high` (see
   Phase 4); recommend `ask` or `ask_high` for High-risk requests;
   (4) Codex effort per step and model — as in `ALLOCATION.md`
   (default), or change.
6. **STOP** until answered. Record the decision at the top of
   `ALLOCATION.md` (option, date, the user's words verbatim; for D, the
   final per-task split).
7. Write `TD/TASKS.md` from `templates/tasks_matrix.md`, and start
   `TD/TASK_HANDOVER.md` and `TD/AUDIT_LOG.md` (from `templates/audit_log.md`).
8. `git switch -c <branch per Git conventions>`. The `.ai/` planning files
   ride along in the T01 commit.

## Phase 4 — Execute and audit

### Audit mode (chosen at Gate 2; recorded in `ALLOCATION.md` and `TASKS.md`)

| Mode | Audits happen | Speed | Trade-off |
|---|---|---|---|
| `per_task` | after every task | slowest | smallest diffs; a problem is caught before later tasks build on it |
| `per_block` (default) | once per **block** — a run of consecutive tasks with the same executor | faster | one finding may touch several tasks of the block |
| `end` | after all tasks, at the hand-off: every run of consecutive tasks by one executor is audited by the other agent, all at once (one Codex audit when Claude did everything) | fastest | a late finding can force rework across many tasks |

In every mode the audits run in the background (see "Background audits
and overlap") and you hand the result over as soon as the last task is
committed (Phase 5).

Example, `per_block`: T01–T03 Claude → one Codex audit; T04–T05 Codex →
one Claude audit; T06–T12 Claude → one Codex audit. A block also closes
after a High-risk task (so it is audited before others build on it) and
after six tasks. Name blocks B1, B2, … and list them in `ALLOCATION.md`
and `TASKS.md`.

Before each task: its dependencies are done and the tree holds no
unrelated changes. Under `per_block` with overlap, check whole blocks:
start a block (or a Codex `execute` call for it) only if none of its
tasks depends on a scope whose audit, fixes or re-check are still open;
otherwise wait. Checking the whole block up front means a block never
stops half-way waiting for fixes that themselves wait for the block to
end (`end` accepts that risk by design). Keep the `TASKS.md` status current
(Pending → In progress → Done, audit pending → In audit → Awaiting your
review → Corrections → Complete).

### Audit review (chosen at Gate 2; recorded in `ALLOCATION.md` and `TASKS.md`)

Who fixes: the reviewer only reads and reports; the **executor** — the
agent that did the work — evaluates the findings and fixes them.

| Option | After an audit |
|---|---|
| `auto` (default) | the executor evaluates every finding and fixes the ones it accepts; you see the outcome in `AUDIT_LOG.md` |
| `ask` | nothing is fixed until you approve |
| `ask_high` | as `ask`, but only when the audit has a BLOCKER or HIGH finding; otherwise `auto` |

When the review stops for you:

1. Write the proposals into `AUDIT_LOG.md` under the scope, **before any
   fix**: each finding with its severity and task, the proposed
   resolution (ACCEPTED, PARTIALLY_ACCEPTED, REJECTED or DEFERRED), the
   reason and the planned fix. For a Claude-executed scope these are your
   evaluations of Codex's findings; for a Codex-executed scope they are
   your findings with your recommendation (Codex has not seen them yet).
2. Chat, review links first: `AUDIT_LOG.md` (open this first) and the raw
   audit output; at most six bullets — counts by severity and anything
   proposed for rejection or deferral.
3. AskUserQuestion: **A** approve as proposed · **B** fix everything found
   · **C** change some (the user names finding IDs and decisions) ·
   **D** stop here (scope stays "Awaiting your review").
4. Record the user's decision per finding in `AUDIT_LOG.md` ("Your
   decision" column). **The user's decision overrides the executor's.**
5. Fix exactly the approved findings: you for Claude's tasks; for Codex's
   tasks, one Codex `execute` call whose `{{CORRECTIONS}}` lists the
   approved findings and says "The user has approved these findings for
   fixing. Fix each one; if one cannot be fixed, stop and explain why —
   do not reject it."
6. The BLOCKER/HIGH re-check (round 2) follows as usual; a BLOCKER or
   HIGH it reports comes back through this same procedure (see Limits).
   In `end` mode, review all the audits in one stop once all have
   returned.

### Execute

- **Claude task:** implement only this task; run its tests; append to
  `TASK_HANDOVER.md` (summary, files changed, tests and results, known
  gaps); commit now (see Commit) and mark "Done, audit pending". Every
  mode commits first and audits the commit range.
- **Codex tasks:** `per_task` → one Codex `execute` call per task. Other
  modes → **one call per block** of consecutive Codex tasks: fill
  `templates/codex_exec_brief.md` with all the block's task IDs in order
  (`{{CORRECTIONS}}` empty). After the call: put Codex's handover into
  `TASK_HANDOVER.md`; check `git status` and the diff yourself; run the
  tests (the sandbox may have blocked some) and record your command and
  result under the block in `TASK_HANDOVER.md`; commit the block (one
  commit for the block) and mark its tasks "Done, audit pending".
- Then launch the scope's audit if the mode calls for one now, and go on
  per "Background audits and overlap".

### Audit (when the mode calls for it)

The **scope** is the tasks being audited; its **range** is
`<base>..<end>`: the commit before the scope's first task, and the last
commit of the scope. Write scope, range and both hashes at the top of the
`AUDIT_LOG.md` section.

- **Scope executed by Claude → Codex audits:** fill
  `templates/codex_audit_brief.md` (`{{TASK_IDS}}`, `{{AUDIT_RANGE}}`,
  round 1, `{{ROUND_NOTE}}` empty) → launch Codex in the background, mode
  `audit`, audit effort, with
  `-DiffRange <base>..<end>` (`--diff-range` on macOS) so the launcher
  pastes the commits and diff into the brief. When it returns, copy the
  findings verbatim (each names its task). Evaluate every finding on its
  merits: ACCEPTED, PARTIALLY_ACCEPTED, REJECTED or DEFERRED, with a
  reason. If the audit review calls for it, stop for the user now (see
  Audit review). Fix accepted (or user-approved) findings only; re-run the tests of every task in
  scope; commit the fixes as one commit. If any BLOCKER or HIGH was
  accepted: one Codex re-check (round 2) at re-check effort, `-DiffRange`
  = the fix commit (`<fix>~1..<fix>`), `{{ROUND_NOTE}}` = each of those
  findings in full (ID, severity, text and the fix made — finding IDs
  restart in every scope) — the last automatic round (see Limits).
- **Scope executed by Codex → Claude audits, as a background subagent**
  (step `<scope>_audit_r<n>`, report in `TD/subagent/`):
  The subagent has no shell (so it never stops the user with a
  permission prompt) and never reads the live repository (other agents
  may be editing it): you prepare everything it needs, outside the repo.
  1. Work folder `<work>` = `<scratch>/dd_<request number>_<step>` (e.g.
     `dd_T009_B2_audit_r1`) in the session scratchpad — outside the repo
     and OneDrive, readable without prompts; if there is no scratchpad,
     the system temp folder. Keep the name short: Windows paths over 260
     characters need long-path support. Snapshot the repository at
     `<end>` into `<work>/snap`. Windows, in this order:
     `New-Item -ItemType Directory -Force "<work>/snap"`, then
     `git -C "<repo root>" archive --format=tar -o "<work>/snap.tar" <end>`,
     then `& "$env:SystemRoot\System32\tar.exe" -xf "<work>/snap.tar" -C "<work>/snap"`
     (plain `tar` may be Git's GNU tar, which misreads `C:` paths).
     macOS: `mkdir -p "<work>/snap" && git -C "<repo root>" archive --format=tar <end> | tar -x -C "<work>/snap"`.
     Check that `<work>/snap/AGENTS.md` and the request's
     `PLAN_APPROVED.md` exist in the snapshot; if the archive or the
     extraction failed, stop and tell the user — never launch the
     subagent on a partial snapshot.
  2. Write the changes file (file list, then the full diff; `.ai/` left
     out — the snapshot holds it):
     `git -C "<repo root>" -c core.quotepath=off diff --stat --patch --output="<work>/changes.diff" <base>..<end> -- . ":(exclude).ai"`.
  3. Fill `templates/subagent_audit_brief.md` → `<work>/brief.md`, all
     ten placeholders: `{{TASK_IDS}}` (the scope's tasks), `{{ROUND}}`,
     `{{AUDIT_RANGE}}` = `<base>..<end>`, `{{END_COMMIT}}` = `<end>`,
     `{{CHANGES_FILE}}` = `<work>/changes.diff`, `{{COMMITS}}` =
     `git -C "<repo root>" log --oneline <base>..<end>`,
     `{{SNAPSHOT_DIR}}` = `<work>/snap`, `{{TASK_DIR}}` = the request
     folder inside the snapshot, `{{ROUND_NOTE}}` (empty in round 1),
     `{{OUT_FILE}}` = `TD/subagent/<step>_out.md`.
  4. Start the Agent tool with `subagent_type: "dual_dev_auditor"`, in
     the background (`run_in_background: true` where the tool offers
     it), and the prompt "Read and follow the brief at <absolute path of
     `<work>/brief.md`>. Your final message is the report, in full." Add
     it to "Running now" and carry on. If `dual_dev_auditor` is not
     listed (Phase 0 step 3), use `general-purpose`, add "Use only Read,
     Grep and Glob" to the prompt and note the fallback in
     `AUDIT_LOG.md`; afterwards check `git status` for changes you did
     not make — any means the audit failed.
  5. When it completes, create `TD/subagent/` if missing and save its
     final message verbatim as `TD/subagent/<step>_out.md`; copy the
     findings into `AUDIT_LOG.md` (reviewer: Claude subagent, with its
     model). No usable report: re-launch once with the same work folder,
     then ask the user — never skip the audit. Once a usable report is
     saved, delete `<work>` — only that folder; if the deletion is
     refused, leave it (it is in the scratchpad).
  6. Never edit Codex's code yourself. If the audit review calls for it,
     stop for the user now and send Codex only the approved findings (see
     Audit review). Otherwise, if there are findings: one Codex `execute`
     call with `{{CORRECTIONS}}` = "Corrections round <n>. Claude's findings
     for <task IDs> are in `TD/AUDIT_LOG.md` under <scope> round <n>.
     Evaluate each one independently, mark it ACCEPTED, PARTIALLY_ACCEPTED,
     REJECTED or DEFERRED with a reason, fix only what you accept, then
     re-run the tests." Copy Codex's resolutions into `AUDIT_LOG.md`;
     check and commit the fixes. If a BLOCKER or HIGH was fixed: one
     re-check (round 2) by a fresh subagent — repeat steps 1–5 with base
     `<fix>~1`, end `<fix>`, step `<scope>_audit_r2`, round 2 and
     `{{ROUND_NOTE}}` = each re-checked finding in full (ID, severity,
     text and the fix made) — the last automatic round.
- **`end` mode:** at the hand-off, launch every audit at once in the
  background — one per run of consecutive tasks by the same executor
  (Codex for Claude's runs, a subagent for Codex's runs), so no range
  holds the other agent's commits. Apply corrections one agent at a time
  (Claude's fixes, then Codex's correction call) — never two agents
  editing at once.
- Remove a job from "Running now" as soon as it ends. When a scope's
  audit closes: mark its tasks Complete, record the fix commit in
  `TASKS.md`, and update the audit table in `REVIEW.md` once that file
  exists.

### Background audits and overlap

- When a scope is committed and its audit launched, carry on with the
  next block **if** the mode is `per_block`, overlap is on (the
  default), and the block passes the whole-block check under "Before
  each task". Otherwise wait for the audits it depends on; the chat
  stays free for the user meanwhile.
- `per_task`: every task waits for its own audit, except the last one.
  `end`: all audits start at the hand-off. In every mode the last
  scope's audit runs during the hand-off (Phase 5).
- Audits may run alongside each other and alongside one writer (you, or
  one Codex `execute` call). Two `execute` calls never run at once, and
  you never edit while a Codex `execute` runs — except the `.ai/`
  bookkeeping files (`TASKS.md`, `AUDIT_LOG.md`, `REVIEW.md`, saved
  reports), which Codex never touches; make no commit until it ends.
- When an audit returns with findings: the review question (if any) can
  go to the user straight away, but fixes wait until the block in
  progress is finished and committed, so every scope's range holds only
  its own executor's commits. Then commit the fixes before the next
  block. If a fix changes something a later task relied on, re-run that
  task's tests and note it in `AUDIT_LOG.md`.

### Limits

- **At most one automatic re-check per audit scope** (round 2): only
  after a BLOCKER or HIGH fix, reviewing only the fix commit, at
  re-check effort. Round 2's MEDIUM and LOW findings are handled as
  usual, with no further audit. A BLOCKER or HIGH that round 2 reports —
  new, or an original one still unresolved — always stops for the user
  through the Audit review procedure (proposals in `AUDIT_LOG.md` first;
  each finding can be fixed, rejected with a reason, or deferred as a
  known risk), whatever the audit review option. Fixes approved there
  are not re-checked unless the user asks for one more round; that round
  follows the same rule. A scope left at "stop here" stays open, so
  completion and any push wait for the user's decision — say so when
  stopping.
- An agent is never the sole reviewer of its own work. If Codex cannot
  run (launcher exit 1 or 2), pause and ask the user — do not self-audit.
- A Codex job or audit subagent running longer than 30 minutes: tell the
  user and offer to stop it.

### Commit

- `git status` first — before every commit and every Codex `execute`
  call. If anything moved that you did not change (for example the user
  edited a file during the hand-off), stop and ask. Stage only the
  task's (or block's) files and the request's `.ai/` files. Never stage
  secrets, data dumps or caches.
- When, in every mode: one commit per Claude task right after its
  tests, one commit per Codex task or block after your check, and one
  commit of audit fixes per scope. Never amend, rebase or squash a
  commit that is under audit or that the user is reviewing.
- Subject in the project's commit format (default `T01 <task title>`;
  Conventional Commits, e.g. `feat(<module>): <task title> [T01]`; a Codex
  block `T04-T05 <short title>`; fixes `B1 audit fixes (T01-T03)` or
  `fix(<module>): audit fixes T01-T03 [B1]`). Blank line, then
  `Request: <request id>; audit: <done | pending (B1 | end)>; log:
  .ai/tasks/<request id>/AUDIT_LOG.md`. No other trailer lines.
- Record the short hash in `TASKS.md`.

### Push

- Only the request branch, only after the user says yes, never forced
  unless the project allows it and the user approves.
- Never push while any audit or re-check is running, pending or
  awaiting the user — nothing is pushed before every audit is complete.
- If the push policy says "push every session", offer a push whenever
  work pauses with every audit complete (end of session, waiting on the
  user mid-execution) and at Phase 6; if audits are still open at such a
  pause, say in one line that the push waits for them. Otherwise ask
  only at Phase 6.

## Phase 5 — Hand-off (as soon as the last task is committed)

Do not wait for running audits: hand off first, then handle the audits,
including any that have already returned. In `end` mode, launch every
audit now.

1. Run the full relevant test suite.
2. Write `TD/REVIEW.md` from `templates/review.md`, every section
   filled: what was built (one line per task), how to try it, test
   results, the hand-off commit (HEAD now), files changed
   (`git diff <start commit>..HEAD --stat`), and the audit table — every
   scope with its reviewer and status. Record the hand-off commit in
   `TASKS.md`.
3. Chat — review links first: `REVIEW.md` (open this first),
   `TASKS.md`, `AUDIT_LOG.md`; then at most six bullets: what to look at
   first, which audits are still running, that nothing is pushed until
   they finish, and that review notes go in chat — please do not edit
   files in the repo until completion, as fixes land there (each one
   announced).
4. While the user reviews, handle each audit as it returns (Phase 4,
   Audit and Audit review): a review stop goes to the user as soon as
   its audit returns — in `end` mode, once all have returned (one
   combined stop). Fixes are new commits on top of the hand-off commit;
   after each, tell the user in one line (commit, findings fixed, files
   touched) — they may be trying the result. Keep the audit table in
   `REVIEW.md` current with targeted edits, never a full rewrite.
5. Record each review note from chat in `REVIEW.md` → "Your review
   notes" with the task it became or "no action". A change the user asks
   for becomes a new task (`T<next>` in `PLAN_APPROVED.md` and
   `TASKS.md`; you execute it unless they say otherwise): do it after
   any fix in progress, commit it, and audit it in the background like
   any other scope.
6. When every audit and re-check is closed, send one message: the
   commits since the hand-off (one line each), and ask whether the user
   has review notes or wants to close out. Go to Phase 6 only on their
   go-ahead. If no audit is open at the hand-off, ask this in the
   hand-off message itself.

## Phase 6 — Completion (every audit closed, the user said close out)

Review notes that arrive after the close-out go back to Phase 5 step 5;
then repeat this phase (one more close-out commit).

1. If anything changed since the hand-off, run the full relevant test
   suite again.
2. Review the whole branch: `git diff <start commit>..HEAD --stat`, then
   skim the full diff. Fill `REVIEW.md` → "Changes since the hand-off"
   (`git diff <hand-off commit>..HEAD --stat`, one line per commit).
3. Update `.ai/STATE.md`; add material decisions to `.ai/DECISIONS.md`.
   Commit, subject `<request id> close-out` in the project's format
   (e.g. `chore: <request id> close-out`).
4. Chat: what changed since the hand-off, findings accepted/rejected per
   agent, remaining risks (including deferred findings), total Codex
   tokens for this request and the current limit % used, branch name,
   links to `REVIEW.md`, `TASKS.md` and `AUDIT_LOG.md`.
5. Ask before any push, pull request or merge.
6. Before a pull request: run `gh repo view <owner>/<repo>` with the
   active GitHub CLI account. If it fails and another logged-in account
   (`gh auth status`) owns or can see the repo, tell the user, run
   `gh auth switch -u <account>`, create the pull request only after
   approval, then switch back to the previous account.
