# Tasks — {{REQUEST_ID}}: {{TITLE}}

- Branch: `{{BRANCH}}` · push policy: {{PUSH_POLICY}}
- Commit format: `{{COMMIT_FORMAT}}`
- Plan source: {{PLAN_SOURCE}}
- Codex: model {{MODEL}}, effort {{EFFORT}}
- Audit mode: {{AUDIT_MODE}} (per_task | per_block | end)
- Allocation approved by the user: {{DATE}}
- Codex tokens so far: {{CODEX_TOKENS}}

| Task | Title | Executor | Reviewer | Block | Depends on | Risk | Status | Commit | Audit fix |
|---|---|---|---|---|---|---|---|---|---|
| T01 | | Claude | Codex | B1 | — | | Pending | — | — |

Status values: Pending · In progress · Done, audit pending · In audit · Corrections · Complete · Blocked
Blocks: consecutive tasks with the same executor, closed after a High-risk task or six tasks (`per_block`); everything is one audit point per executor in `end`; each task is its own block in `per_task`.
