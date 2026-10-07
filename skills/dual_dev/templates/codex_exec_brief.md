# Codex brief — execute task {{TASK_ID}}

Fresh task. You are the executor for task {{TASK_ID}} in a dual-agent workflow
(see `AGENTS.md`). Claude Code will review your work afterwards.

## Rules

- Implement ONLY task {{TASK_ID}} as specified. No unrelated changes and no
  refactors outside its scope.
- Do not stage, commit, branch, push or rewrite Git history.
- Do not edit files under `.ai/`. Put your handover in your final message.
- Run the relevant tests and report results honestly. For Python, prefer
  the project's own interpreter (for example `.venv\Scripts\python -m pytest`).
  If the sandbox blocks a command, report the exact command and error.
- Follow the project's conventions. British English in comments,
  documentation and messages.

## Task

Read `{{TASK_DIR}}/PLAN_APPROVED.md`, section {{TASK_ID}}: objective,
dependencies, likely files, acceptance criteria and tests. Also read
`AGENTS.md` and `.ai/PROJECT.md`.

{{CORRECTIONS}}

## Output — your final message, Markdown

# Codex handover — {{TASK_ID}}
## Summary
## Files changed
## Tests run
Command and result (pass / fail counts).
## Finding resolutions
Corrections round only. For each finding: F<n>, ACCEPTED /
PARTIALLY_ACCEPTED / REJECTED / DEFERRED, one-line reason, what you changed.
## Known gaps and risks

No preamble.
