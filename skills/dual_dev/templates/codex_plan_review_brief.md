# Codex brief — review Claude's plan (light mode, PLANNING ONLY)

Fresh task. You are the plan reviewer in a dual-agent workflow (see
`AGENTS.md`). The user chose light mode for this small request: Claude
wrote the only plan, and you check it before any work starts. Be
critical — do not assume the plan is right.

## Rules

- Read only. Do not modify, create or delete any file.
- Do not write a plan of your own; review this one.

## Read

1. `AGENTS.md`, `.ai/PROJECT.md`, `.ai/STATE.md`, `.ai/DECISIONS.md`
2. `{{TASK_DIR}}/REQUEST.md`
3. Claude's plan: `{{TASK_DIR}}/PLAN_A.md`
4. The source code and tests the plan touches — check its claims against
   the repository.

## Check

Does the plan meet the request? Wrong assumptions or file paths; missing
tasks, tests or edge cases; wrong order or dependencies; risks it misses;
a simpler way to do the same thing; anything that should make the user
run the full two-plan mode instead.

## Output — your final message, Markdown

# Codex plan review — {{REQUEST_ID}}
## Verdict
APPROVE, APPROVE_WITH_CHANGES or REWORK — one line.
## Findings
One block per finding, most severe first:
### P<n> [BLOCKER | HIGH | MEDIUM | LOW | NOTE] short title
- Where in the plan: task or section
- Problem:
- Suggested change:
Write "None" if there are no findings.
## Should this request use the full two-plan mode?
Yes or no, one line why.

British English. No preamble.
