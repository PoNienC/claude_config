# Codex brief — execute {{TASK_IDS}}

Fresh task. You are the executor for {{TASK_IDS}} in a dual-agent workflow
(see `AGENTS.md`). Claude Code will review your work afterwards.

## Rules

- Implement ONLY {{TASK_IDS}}, in this order, as specified. No unrelated
  changes and no refactors outside their scope.
- Finish each task and run its tests before starting the next one. If a
  task cannot be completed, stop there and report why — do not start the
  tasks after it.
- Do not stage, commit, branch, push or rewrite Git history.
- Do not edit files under `.ai/`. Put your handover in your final message.
- Run the relevant tests and report results honestly. For Python, prefer
  the project's own interpreter (for example `.venv\Scripts\python -m pytest`).
  If the sandbox blocks a command, report the exact command and error.
- Follow the project's conventions. British English in comments,
  documentation and messages.

## Tasks

Read `{{TASK_DIR}}/PLAN_APPROVED.md`, sections {{TASK_IDS}}: objective,
dependencies, likely files, acceptance criteria and tests. Also read
`AGENTS.md` and `.ai/PROJECT.md`.

{{CORRECTIONS}}

## Output — your final message, Markdown

# Codex handover — {{TASK_IDS}}
One section per task:
## T<nn> — <title>
### Summary
### Files changed
### Tests and checks run
One line per command — the task's tests, then the package checks named in
`.ai/PROJECT.md` (lint, types): command, result (pass / fail counts), or
the exact error if the sandbox blocked it.
### Finding resolutions
Corrections round only. For each finding: F<n>, ACCEPTED /
PARTIALLY_ACCEPTED / REJECTED / DEFERRED, one-line reason, what you changed.
### Known gaps and risks

No preamble.
