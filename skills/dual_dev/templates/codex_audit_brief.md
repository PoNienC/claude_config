# Codex brief — read-only audit of task {{TASK_ID}} (round {{ROUND}})

Fresh task. You are the reviewer in a dual-agent workflow (see `AGENTS.md`).
Claude Code executed task {{TASK_ID}}. Review it independently and critically.

## Rules

- Read only. Do not modify, create or delete any file. Do not fix anything.
- Review only this task's changes: `git status --short`, `git diff HEAD`,
  and the content of any untracked files listed.
- Treat changes under `.ai/` as context, not as code to review.
- You may try read-only test commands (for Python: set
  `PYTHONDONTWRITEBYTECODE=1` and add `-p no:cacheprovider`). If the sandbox
  blocks them, say so — the executor runs tests separately.

## Context

- Task spec and acceptance criteria: `{{TASK_DIR}}/PLAN_APPROVED.md`, section {{TASK_ID}}.
- Executor's handover: `{{TASK_DIR}}/TASK_HANDOVER.md`, section {{TASK_ID}}.
- Project conventions: `AGENTS.md`, `.ai/PROJECT.md`.

{{ROUND_NOTE}}

## Check

Correctness against the acceptance criteria; bugs and edge cases; tests
(present, meaningful, passing); error handling; security; performance;
consistency with existing code; scope creep (changes outside the task).

## Output — your final message, Markdown

# Codex audit — {{TASK_ID}} (round {{ROUND}})
## Verdict
PASS, PASS_WITH_FINDINGS or FAIL — one line.
## Findings
One block per finding, most severe first:
### F<n> [BLOCKER | HIGH | MEDIUM | LOW | NOTE] short title
- Where: `path:line`
- Problem:
- Why it matters:
- Suggested fix:
Write "None" if there are no findings.
## Tests run
Commands and results, or "None run".

British English. No preamble.
