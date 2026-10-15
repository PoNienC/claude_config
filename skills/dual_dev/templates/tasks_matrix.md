# Tasks — {{REQUEST_ID}}: {{TITLE}}

- Branch: `{{BRANCH}}` · push policy: {{PUSH_POLICY}}
- Commit format: `{{COMMIT_FORMAT}}`
- Plan source: {{PLAN_SOURCE}}
- Codex: model {{MODEL}}, effort {{EFFORT}}
- Audit mode: {{AUDIT_MODE}} (per_task | per_block | end) · overlap: {{OVERLAP}} (on | off; n/a for per_task and end)
- Audit review: {{AUDIT_REVIEW}} (auto | ask | ask_high)
- Allocation approved by the user: {{DATE}}
- Hand-off: {{HANDOFF}} <!-- pending | `<commit>`, DD Month YYYY — see REVIEW.md -->
- Running now: none <!-- every background job: step, started HH:MM, output file — e.g. "B1_audit_r1 (Codex) 14:05 → codex/B1_audit_r1_out.md" -->
- Codex tokens so far: {{CODEX_TOKENS}}

| Task | Title | Executor | Reviewer | Block | Depends on | Risk | Status | Commit | Audit fix |
|---|---|---|---|---|---|---|---|---|---|
| T01 | | Claude | Codex | B1 | — | | Pending | — | — |

Status values: Pending · In progress · Done, audit pending · In audit · Awaiting your review · Corrections · Complete · Blocked
Blocks: consecutive tasks with the same executor, closed after a High-risk task or six tasks (`per_block`); in `end`, each run of consecutive same-executor tasks is one audit point, all audited at the hand-off; each task is its own block in `per_task`.
