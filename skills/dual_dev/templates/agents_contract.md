# Dual-agent development contract

This project uses Claude Code and OpenAI Codex as cooperating development
agents. This section is the operating contract for both.

## Authority

The user is the final authority for architecture, plan selection, execution
allocation and acceptance of significant changes.

- Claude Code is the default workflow coordinator and default executor.
- Claude is NOT automatically the preferred planner.
- Codex is a peer planner, optional executor and reciprocal reviewer.

## Mandatory workflow (substantial requests only)

The user starts it with `/dual_dev <request>` in Claude Code. Small edits
skip it.

1. Claude and Codex each produce an independent plan.
2. Neither agent sees the other's plan until both are complete.
3. Claude presents both plans and a neutral comparison to the user.
4. No implementation before the user approves Claude's plan, Codex's plan
   or a hybrid (Gate 1).
5. Claude then asks how execution is allocated (Gate 2). Default: Claude
   executes all tasks. The user may assign any subset to Codex.
6. Every executed task is reviewed by the other agent. An agent is never
   the sole reviewer of its own work.

## Planning

Both plans cover: objective; assumptions; architecture; numbered tasks;
dependencies; implementation order; testing; risks; alternatives
considered; rollback where relevant.

Planning never modifies project files. Codex plans in a read-only sandbox.

## Reciprocal audit

- Claude executes → Codex reviews (read-only) → Claude evaluates each
  finding → Claude fixes accepted findings.
- Codex executes → Claude reviews → Codex evaluates each finding → Codex
  fixes accepted findings.
- Reviewers never silently modify the executor's implementation.

Severity: BLOCKER, HIGH, MEDIUM, LOW, NOTE.
Resolution: ACCEPTED, PARTIALLY_ACCEPTED, REJECTED, DEFERRED — always with
a reason.

Re-review limits: BLOCKER/HIGH → mandatory re-review after the fix;
MEDIUM → fix plus tests is enough; LOW/NOTE → no second audit. At most two
correction rounds per audit scope; after that the user breaks the deadlock.

## Task boundaries and Git

Branch names, commit format and push cadence follow this project's own
rules, recorded in `.ai/PROJECT.md` under "Git conventions". Where the
project has none: branch `dual_dev/T###_slug`, commit `T## <task title>`,
no push without approval.

Always:

- One request = one branch. The user picks the audit mode at Gate 2:
  `per_task` (audit after every task), `per_block` (audit once per run
  of consecutive tasks by the same executor) or `end` (audit everything
  after all tasks). Work is committed per task (or per Codex block) and
  the audit reviews the commit range; audit fixes get their own commit.
- Never push commits whose audit is still pending.
- Push only the request branch, and only with the user's approval. If the
  project requires a push every session, offer it when work pauses.
- Never push to or merge into the main branch, and never open a pull
  request, without the user's explicit approval.
- The two agents never edit the same working tree at the same time.
- No AI-agent credit lines in commit messages.

## Shared state (in the repository, not in agent memory)

- `.ai/PROJECT.md` — what the project is, stack, layout, how to test, Git
  conventions.
- `.ai/STATE.md` — current shared state; updated at the end of each request.
- `.ai/DECISIONS.md` — material architectural decisions, newest first.
- `.ai/tasks/T###_slug/` — one folder per request: `REQUEST.md`,
  `PLAN_A.md` (Claude), `PLAN_B.md` (Codex), `COMPARISON.md`,
  `PLAN_APPROVED.md`, `TASKS.md`, `TASK_HANDOVER.md`, `AUDIT_LOG.md`, and
  `codex/` (briefs and raw Codex output).

Git history remains the authoritative implementation history. A root
`HANDOVER.md`, if present, is a personal note and not part of this contract.

## Rules for Codex when called by this workflow

- Follow the brief you are given; it states your role (planner, auditor or
  executor) and your limits.
- As planner or auditor: read only; never modify files.
- As executor: change only what the assigned task needs; run the relevant
  tests; do not stage or commit; do not edit `.ai/` files — put your
  handover in your final message instead.
- British English in code comments, documentation and messages.
