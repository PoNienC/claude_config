# Claude audit brief — {{TASK_IDS}} (round {{ROUND}})

You are the Claude reviewer in a dual-agent workflow. Codex executed
{{TASK_IDS}}. Review them independently and critically. You run in the
background: nobody can answer questions, so decide and note your
assumptions.

## Rules

- Read only. Do not modify, create or delete any file. Do not fix
  anything. Do not run any command — no git, no tests, no shell: the
  coordinator prepared everything you need, and a command would stop the
  user with a permission prompt.
- Review only the range `{{AUDIT_RANGE}}` (end commit `{{END_COMMIT}}`).
- The changes under review are in `{{CHANGES_FILE}}` — file list, then
  the full diff. Start there; it is authoritative for what changed.
- Commits in the range:

  ~~~text
  {{COMMITS}}
  ~~~

- Read every other file — source, tests, `AGENTS.md`, `.ai/` — from the
  snapshot `{{SNAPSHOT_DIR}}`: the repository exactly at the end commit.
  Never read the live repository; other agents may be editing it. Files
  marked `export-ignore`, submodules and Git LFS content may be missing
  from the snapshot — their absence is not a finding.
- Treat changes under `.ai/` as context, not as code to review.
- The coordinator ran the tests before the commit (results in the
  handover, below). A missing test or a doubtful result is a finding.

## Context (all in the snapshot)

- Task specs and acceptance criteria: `{{TASK_DIR}}/PLAN_APPROVED.md`,
  sections {{TASK_IDS}}.
- Executor's handover (Codex): `{{TASK_DIR}}/TASK_HANDOVER.md`, sections
  {{TASK_IDS}}.
- Check each task against its own acceptance criteria, and check that the
  tasks fit together.
- Project conventions: `{{SNAPSHOT_DIR}}/AGENTS.md`,
  `{{SNAPSHOT_DIR}}/.ai/PROJECT.md`.

{{ROUND_NOTE}}

## Check

Correctness against the acceptance criteria; bugs and edge cases; tests
(present, meaningful, passing per the handover); error handling;
security; performance; consistency with existing code; scope creep
(changes outside the task).

## Output — your final message, Markdown, in full

Your final message is the report itself; the coordinator saves it
verbatim as `{{OUT_FILE}}`. It is a file for the coordinator, not a chat
reply: reply-length caps and no-heading rules do not apply — give every
finding in full.

# Claude audit — {{TASK_IDS}} (round {{ROUND}})
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
## Checked
What you verified and how (files read). "None" under Findings is valid
only with this list.
## Limits
Anything you could not check, and why — or "None".

British English. No preamble.
