---
name: dual_dev
description: Run the dual-agent development workflow — independent Claude and Codex plans, a human plan gate, explicit task allocation, execution with reciprocal Claude/Codex audit, and one local commit per audited task. Only when the user types /dual_dev.
argument-hint: "[--xhigh] <development request>"
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
  `--mode --repo --brief --out --effort` in place of the `-Mode -Repo
  -BriefFile -OutFile -Effort` parameters. Same modes, exit codes and output.
- **Repo root** = `git rev-parse --show-toplevel`.
- **Request ID** = `T###_slug`: next number above the highest folder in
  `.ai/tasks/` (start at `T001`), slug = two to four snake_case words.
  **TD** = `.ai/tasks/<request id>/` (use its absolute path in commands).
- Tasks inside a request: `T01`, `T02`, …
- **Codex effort** = `high`. Use `xhigh` if the request starts with
  `--xhigh` (strip the flag) or the user asks at any point.
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
  (write inside the repo works, write outside is denied). Whether Codex
  may execute on the current machine comes from `.ai/PROJECT.md` (see
  Phase 3). After any Codex execute run, always check `git diff` yourself
  — a stalled run can still print "CODEX OK" with nothing changed.
- **Git conventions** = `.ai/PROJECT.md` → section "Git conventions"
  (branch pattern, commit format, push policy, pull request rules, GitHub
  account). **Project rules win.** Defaults only where the project has none:
  branch `dual_dev/<request id>`, commit `T01 <task title>`, no push
  without approval. Slugs use underscores; keep any separator the
  project's pattern fixes (e.g. `feat/<module>-T001_slug`).
- Never edit the working tree while a Codex job is running.
- Chat stays short; detail goes into TD files. Whenever you name files:
  clickable links, plus one code block listing every absolute path.

Launch pattern (fill the placeholders in a template first and save it as the brief):

```powershell
& "<skill dir>\scripts\run_codex.ps1" -Mode <plan|audit|execute> -Repo "<repo root>" -BriefFile "<TD>\codex\<step>_brief.md" -OutFile "<TD>\codex\<step>_out.md" -Effort high
```

```bash
bash "<skill dir>/scripts/run_codex.sh" --mode <plan|audit|execute> --repo "<repo root>" --brief "<TD>/codex/<step>_brief.md" --out "<TD>/codex/<step>_out.md" --effort high
```

Step names: `plan`, `plan_r2`, `T01_audit_r1`, `T01_exec`, `T01_fix_r1`, `T01_audit_r2`, …

## Phase 0 — Context

1. Find the repo root. If `AGENTS.md` lacks "Dual-agent development
   contract" or `.ai/` is missing, stop and tell the user to run
   `/dual_dev_init` first.
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
   line `Author: Codex, effort <effort>`).

Running both at once keeps independence: neither plan is seen by the other
agent before both are saved.

## Phase 2 — Comparison and Gate 1

1. Write `TD/COMPARISON.md`: agreements; a differences table
   (area | Plan A | Plan B | recommended); trade-offs; ordering and testing
   differences; risks only one plan found; recommended synthesis with
   reasons. Judge on merit, not authorship.
2. Chat: at most six bullets on the key differences, plus links to
   `PLAN_A.md`, `PLAN_B.md`, `COMPARISON.md`.
3. Gate 1 with AskUserQuestion: **A** Claude plan · **B** Codex plan ·
   **C** Hybrid (your recommended mix, or the user's) · **D** Revise both.
   Put your recommendation first.
4. **STOP** until answered. On D: append the revision notes to
   `REQUEST.md`, then repeat Phase 1 as round 2 (fresh Codex run, step
   `plan_r2`, `{{REVISION_NOTE}}` = the notes; keep round-1 files).

## Phase 3 — Approved plan and Gate 2

1. Write `TD/PLAN_APPROVED.md`: the source (A, B or hybrid, with the user's
   instructions verbatim), then atomic tasks `T01`… each with objective,
   dependencies, likely files, acceptance criteria, tests and risk level.
2. Check `.ai/PROJECT.md` for "Codex execution on <this machine>". Not
   "available" (or missing) → Claude executes all tasks; say so in one line
   and skip to step 3 with option A only.
   Otherwise recommend an allocation. Give Codex tasks that are independent,
   well scoped, testable and interface-stable — not "a share of the work".
   Never split tightly coupled tasks across agents.
3. Gate 2 with AskUserQuestion: **A** Claude executes all (default) ·
   **B** Split as recommended (state it) · **C** Codex executes all ·
   **D** Custom. In the same call, confirm effort (`high` or `xhigh`).
   State the Git plan from the Git conventions: the branch name, the
   commit format, one commit per audited task plus one close-out commit,
   and the push policy.
4. **STOP** until answered.
5. Write `TD/TASKS.md` from `templates/tasks_matrix.md`, and start
   `TD/TASK_HANDOVER.md` and `TD/AUDIT_LOG.md` (from `templates/audit_log.md`).
6. `git switch -c <branch per Git conventions>`. The `.ai/` planning files
   ride along in the T01 commit.

## Phase 4 — Execute, one task at a time, in dependency order

Before each task: dependencies are Complete and the tree holds no
unrelated changes. Keep the TASKS.md status current.

### Claude-owned task

1. Implement only this task. Run the relevant tests.
2. Append to `TASK_HANDOVER.md`: task, summary, files changed, tests and
   results, known gaps.
3. Fill `templates/codex_audit_brief.md` (round 1, `{{ROUND_NOTE}}` empty) →
   launch Codex, mode `audit`. Wait.
4. Copy the findings verbatim into `AUDIT_LOG.md`.
5. Evaluate every finding on its merits. Mark each ACCEPTED,
   PARTIALLY_ACCEPTED, REJECTED or DEFERRED with a reason.
6. Fix accepted findings only. Re-run the tests.
7. If any BLOCKER or HIGH was accepted: Codex audit round 2 with
   `{{ROUND_NOTE}}` listing those finding IDs to verify. Record it.
8. Mark Complete and commit.

### Codex-owned task

1. Fill `templates/codex_exec_brief.md` (`{{CORRECTIONS}}` empty) → launch
   Codex, mode `execute`. Wait.
2. Put Codex's handover into `TASK_HANDOVER.md`.
3. Check it yourself: `git status`, full `git diff HEAD`, and run the
   relevant tests (the sandbox may have blocked some of Codex's).
4. Review the complete diff against the acceptance criteria, using the
   audit brief's checklist. Record findings in `AUDIT_LOG.md`. Never edit
   Codex's code yourself.
5. If there are findings: fill the exec brief again with `{{CORRECTIONS}}`
   = "Corrections round <n>. Claude's findings are in `TD/AUDIT_LOG.md`
   under <task> round <n>. Evaluate each one independently, mark it
   ACCEPTED, PARTIALLY_ACCEPTED, REJECTED or DEFERRED with a reason, fix
   only what you accept, then re-run the tests." Launch, mode `execute`.
   Copy Codex's resolutions into `AUDIT_LOG.md`.
6. Re-review BLOCKER and HIGH fixes; re-run the tests.
7. Mark Complete and commit.

### Limits

- At most two correction rounds per task. Then stop and ask the user.
- An agent is never the sole reviewer of its own work. If Codex cannot
  run (launcher exit 1 or 2), pause and ask the user — do not self-audit.
- A Codex job running longer than 30 minutes: tell the user and offer to
  stop it.

### Commit (each Complete task)

- `git status` first. Stage only this task's files and the request's
  `.ai/` files. Never stage secrets, data dumps or caches.
- Subject line in the project's commit format (default `T01 <task title>`;
  for Conventional Commits, e.g. `feat(<module>): <task title> [T01]`).
  Blank line, then `Request: <request id>; audit log:
  .ai/tasks/<request id>/AUDIT_LOG.md`. No other trailer lines.
- Record the short hash in `TASKS.md`.

### Push

- Only the request branch, only after the user says yes, never forced
  unless the project allows it and the user approves.
- If the push policy says "push every session", offer a push whenever
  work pauses (end of session, waiting on the user mid-execution) and at
  Phase 5. Otherwise ask only at Phase 5.

## Phase 5 — Completion

1. Run the full relevant test suite.
2. Review the whole branch: `git diff <start commit>..HEAD --stat`, then
   skim the full diff.
3. Update `.ai/STATE.md`; add material decisions to `.ai/DECISIONS.md`.
   Commit, subject `<request id> close-out` in the project's format
   (e.g. `chore: <request id> close-out`).
4. Chat: tasks done, findings accepted/rejected per agent, remaining risks,
   branch name, links to `TASKS.md` and `AUDIT_LOG.md`.
5. Ask before any push, pull request or merge.
6. Before a pull request: run `gh repo view <owner>/<repo>` with the
   active GitHub CLI account. If it fails and another logged-in account
   (`gh auth status`) owns or can see the repo, tell the user, run
   `gh auth switch -u <account>`, create the pull request only after
   approval, then switch back to the previous account.
