# Codex brief — independent plan (PLANNING ONLY)

Fresh task. You are a peer planner in a dual-agent workflow (see `AGENTS.md`).
Another agent is planning the same request separately. Do not assume its
approach is correct, and do not look for it.

## Rules

- Produce an independent implementation plan only.
- Do not modify, create or delete any file. Do not attempt implementation.
- Do not read `{{TASK_DIR}}/PLAN_A.md` or any plan under `.ai/tasks/` other
  than this request's `REQUEST.md`.

## Read first

1. `AGENTS.md`
2. `.ai/PROJECT.md`, `.ai/STATE.md`, `.ai/DECISIONS.md`
3. `{{TASK_DIR}}/REQUEST.md`
4. The relevant source code and tests — inspect the repository yourself.

{{REVISION_NOTE}}

## Output — your final message, Markdown, exactly these sections

# Plan B (Codex) — {{TITLE}}
## Objective
## Assumptions
## Proposed architecture
## Numbered tasks
For each task: number, title, objective, depends on, likely files, tests,
risk (low / medium / high).
## Implementation order
## Test strategy
## Risks
## Alternatives considered
## Rollback
## Open questions for the user

Be specific to this repository: cite real file paths, functions and tests.
British English. No preamble.
