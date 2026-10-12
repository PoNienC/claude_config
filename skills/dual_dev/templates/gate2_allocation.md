# Gate 2 — execution split: {{REQUEST_ID}} {{TITLE}}

- Date: {{DATE}}
- Approved plan: [PLAN_APPROVED.md](PLAN_APPROVED.md) · Gate 1 record: [COMPARISON.md](COMPARISON.md)
- Codex execution on this machine: {{CODEX_EXECUTION}} (from `.ai/PROJECT.md`)
- Codex: model {{MODEL}}, effort {{EFFORT}}
- Decision: _pending_ <!-- after the answer: option, date, the user's words verbatim -->

## Decision needed

Choose one: **A** Claude executes all (default) · **B** Split as below · **C** Codex executes all · **D** Custom.
Also confirm the Codex model and effort above.

Recommendation: **<letter>** — <one-line reason>.

## Proposed split (option B)

| Task | Title | Executor | Reviewer | Depends on | Risk | Why this executor |
|---|---|---|---|---|---|---|
| T01 | | Claude | Codex | — | | |

## What each option means

| Option | Claude executes | Codex executes | Reviews | Codex calls (est.) |
|---|---|---|---|---|
| A | all | none | Codex audits every task | |
| B | | | each task audited by the other agent | |
| C | none | all | Claude reviews every task | |

## Order of work

1. T01 — <executor> → audit by <reviewer> → tests → commit
2. …

## Git plan

- Branch: `<branch per Git conventions>`
- Commit format: `<format>` — one commit per audited task, plus one close-out commit
- Push policy: <policy>

## Cost and time

- Codex calls so far: <n> (planning) · tokens so far: <n>
- Plan limit: <x>% used, resets <date> (from the last `CODEX USAGE` line)
- Estimated Codex calls for the chosen option: see the table above

## Risks of the split

- <integration points between Claude-owned and Codex-owned tasks, interface assumptions, shared files>
