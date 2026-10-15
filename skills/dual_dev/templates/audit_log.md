# Audit log — {{REQUEST_ID}}: {{TITLE}}

Audit mode: {{AUDIT_MODE}} · Audit review: {{AUDIT_REVIEW}}.

- One section per audit scope and round. Each opens with "In short", then
  one titled line per finding, then the full table.
- Findings in the table are copied verbatim from the reviewer; the executor
  proposes a resolution for each, with a reason.
- Under `ask` (or `ask_high` with a BLOCKER/HIGH) nothing is fixed until you
  fill "Your decision"; your decision wins.
- Round 2 (re-check of a BLOCKER/HIGH fix) is the last automatic round; a
  BLOCKER or HIGH it finds always comes to you.
- Raw reviewer output: `codex/` (Codex) and `subagent/` (Claude's audit subagent).

## B1 (T01-T03) — round 1 · executor: Claude · reviewer: Codex (<model>, <effort>) · DD Month YYYY

**In short:** <verdict> · findings B/H/M/L/N: <n/n/n/n/n> · <needs you: yes/no>

- **F1 (<severity>, T01) <plain title, ≤8 words>** → <proposed resolution, one line>

Range: `<base>..<end>` (base `<hash>`, end `<hash>`)
Review: auto | awaiting your review | approved DD Month YYYY

| ID | Task | Severity | Finding | Proposed resolution | Reason | Planned fix | Your decision | Outcome |
|---|---|---|---|---|---|---|---|---|
| F1 | T01 | | | ACCEPTED / PARTIALLY_ACCEPTED / REJECTED / DEFERRED | | | approve / fix / reject / defer / — (auto) | fixed in `<hash>` / not fixed |
