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

**Everything you need is pasted at the end of this brief** — the repo
tree, `AGENTS.md`, `.ai/PROJECT.md`, `.ai/STATE.md`, `.ai/DECISIONS.md` and
the relevant source and tests in full — and the request is in
`{{TASK_DIR}}/REQUEST.md`. Plan from that text. Run a command only if a
file you truly need is missing from the pack, then read only that file;
do not explore the repository folder by folder. Say "not in the pack"
rather than guessing.

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

Be specific to this repository: cite real file paths, functions and tests
from the pack. Keep the whole plan under about 900 words. British English.
No preamble.
