# Codex brief — independent plan (PLANNING ONLY, from the pasted context)

Fresh task. You are a peer planner: another agent is planning the same
request separately. Do not assume its approach is correct, and do not
look for it.

## Rules

- Produce an independent implementation plan only. Do not modify, create
  or delete any file. Do not attempt implementation.
- **Everything you need is pasted at the end of this brief** (repo tree,
  key documents, the relevant files in full). Plan from that text. Run a
  command only if a file you truly need is missing from the pack — then
  read only that file. Do not explore the repository folder by folder.
- Be specific to this repository: cite real file paths, functions and
  tests from the pack. Say "not in the pack" rather than guessing.

## The request (verbatim)

{{REQUEST}}

{{NOTES}}

## Output — your final message, Markdown, exactly these sections

# Plan B (Codex) — {{TITLE}}
## Objective
One paragraph.
## Assumptions
## Approach
The design in a few lines: what changes, where, and why this way.
## Numbered tasks
For each task: number, title, objective, depends on, likely files, tests,
risk (low / medium / high). Small, independently testable tasks.
## Implementation order
## Test strategy
## Risks
## Alternatives considered
One line each: what, and why not.
## Open questions for the user
Only what you cannot decide from the pack.

Keep it tight: the whole plan under about 900 words. British English.
No preamble.
