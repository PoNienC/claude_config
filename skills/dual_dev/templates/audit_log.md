# Audit log — {{REQUEST_ID}}: {{TITLE}}

Audit mode: {{AUDIT_MODE}} · Audit review: {{AUDIT_REVIEW}}. One section per
audit scope and round. Findings are copied verbatim from the reviewer's
output and name their task. The executor proposes a resolution for each,
with a reason. Under `ask` (or `ask_high` with a BLOCKER/HIGH finding)
nothing is fixed until the user has filled "Your decision"; the user's
decision overrides the executor's. Raw reviewer output lives in `codex/`
or is quoted here.

## B1 (T01-T03) — round 1 · executor: Claude · reviewer: Codex · DD Month YYYY

Range: `<base>..<end>` (base `<hash>`, end `<hash>`)
Verdict:
Review: auto | awaiting your review | approved DD Month YYYY

| ID | Task | Severity | Finding | Proposed resolution | Reason | Planned fix | Your decision | Outcome |
|---|---|---|---|---|---|---|---|---|
| F1 | T01 | | | ACCEPTED / PARTIALLY_ACCEPTED / REJECTED / DEFERRED | | | approve / fix / reject / defer / — (auto) | fixed in `<hash>` / not fixed |
