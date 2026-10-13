# Codex brief — read-only audit of {{TASK_IDS}} (round {{ROUND}})

Fresh task. You are the reviewer in a dual-agent workflow (see `AGENTS.md`).
Claude Code executed {{TASK_IDS}}. Review them independently and critically.

## Rules

- Read only. Do not modify, create or delete any file. Do not fix anything.
- Review only these changes: range `{{AUDIT_RANGE}}` (one or more commits;
  `HEAD` means the uncommitted changes). The commits, file list and full
  diff are **pasted at the end of this brief** — start there. Run git or
  open files only for extra context, reading them as they are at the end
  of the range (`git show <end>:<path>`); the working tree may already hold
  later work.
- Treat changes under `.ai/` as context, not as code to review.
- You may try read-only test commands (for Python: set
  `PYTHONDONTWRITEBYTECODE=1` and add `-p no:cacheprovider`). If the sandbox
  blocks them, say so — the executor runs tests separately.

## Context

- Task specs and acceptance criteria: `{{TASK_DIR}}/PLAN_APPROVED.md`, sections {{TASK_IDS}}.
- Executor's handover: `{{TASK_DIR}}/TASK_HANDOVER.md`, sections {{TASK_IDS}}.
- Check each task against its own acceptance criteria, and check that the
  tasks fit together.
- Project conventions: `AGENTS.md`, `.ai/PROJECT.md`.

{{ROUND_NOTE}}

## Check

Correctness against the acceptance criteria; bugs and edge cases; tests
(present, meaningful, passing); error handling; security; performance;
consistency with existing code; scope creep (changes outside the task).

## Output — your final message, Markdown

# Codex audit — {{TASK_IDS}} (round {{ROUND}})
## Verdict
PASS, PASS_WITH_FINDINGS or FAIL — one line, plus one line per task.
## Findings
One block per finding, most severe first:
### F<n> [BLOCKER | HIGH | MEDIUM | LOW | NOTE] (T<nn>) short title
- Task: the task ID the finding belongs to (or "cross-task")
- Where: `path:line`
- Problem:
- Why it matters:
- Suggested fix:
Write "None" if there are no findings.
## Tests run
Commands and results, or "None run".

British English. No preamble.
