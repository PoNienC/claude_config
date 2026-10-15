# Gate 2 — execution split: {{REQUEST_ID}} {{TITLE}}

- Date: {{DATE}}
- Approved plan: [PLAN_APPROVED.md](PLAN_APPROVED.md) · Gate 1 record: [COMPARISON.md](COMPARISON.md)
- Codex execution on this machine: {{CODEX_EXECUTION}} (from `.ai/PROJECT.md`)
- Codex: model {{MODEL}}, effort {{EFFORT}}
- Decision: _pending_ <!-- after the answer: option, date, the user's words verbatim -->

## Decision needed

Choose one: **A** Claude executes all (default) · **B** Split as below · **C** Codex executes all · **D** Custom.
Also confirm the audit mode, overlap, audit review, and the effort and models below.

Recommendation: **<letter>** — <one-line reason>.

## In short

- **Split:** <who executes which tasks, one line>
- **Audit mode:** **<mode>** — <one-line reason>
- **Overlap:** **<on/off>** — <one-line reason>
- **Audit review:** **<option>** — <one-line reason>
- **Biggest risk:** <one line>

## Proposed split (option B)

| Task | Title | Executor | Reviewer | Depends on | Risk | Why this executor |
|---|---|---|---|---|---|---|
| T01 | | Claude | Codex | — | | |

## What each option means

| Option | Claude executes | Codex executes | Reviews | Codex calls (est.) |
|---|---|---|---|---|
| A | all | none | Codex audits every task | |
| B | | | each task audited by the other agent | |
| C | none | all | Claude's audit subagent reviews every task | |

## Audit mode

- **`per_block` (default):** one audit per block of same-executor tasks.
- **`per_task`:** one audit after every task. Slowest; smallest diffs.
- **`end`:** all audits at the hand-off. Fastest; late findings mean wider rework.

| Mode | Audit points for this split | Codex audit calls | Claude audits |
|---|---|---|---|
| `per_block` | B1 (T01-T03) → Codex · B2 (T04-T05) → Claude · … | | |
| `per_task` | after each of the <n> tasks | | |
| `end` | one per run of consecutive same-executor tasks, all at the hand-off | | |

Blocks under `per_block`:

| Block | Tasks | Executor | Reviewer | Closes because | Overlap with next block? |
|---|---|---|---|---|---|
| B1 | T01-T03 | Claude | Codex | executor changes next | yes / no — <does the next block depend on B1?> |

## Overlap

- **On (default):** while a block is audited, the next one starts if it does not depend on it. Faster; some rework if findings appear.
- **Off:** each block waits for its own audit.

## Audit review

- **`auto` (default):** the executor fixes the findings it accepts; you read the result in `AUDIT_LOG.md`.
- **`ask`:** nothing is fixed until you approve.
- **`ask_high`:** stops for you only on a BLOCKER or HIGH finding.

Expected stops for you: `ask` — <n> (one per audit point); `ask_high` — only where serious findings appear.

## Effort and models per step

| Step | Codex effort | Codex model | Claude |
|---|---|---|---|
| Planning / plan review | {{EFFORT_PLAN}} | {{MODEL}} | this session |
| Execution | {{EFFORT_EXECUTE}} | {{MODEL}} | this session |
| Audit (round 1) | {{EFFORT_AUDIT}} | {{MODEL}} | subagent, session model |
| Re-check (round 2, the last) | {{EFFORT_RECHECK}} | {{MODEL}} | subagent, session model |

## Order of work

1. B1: T01, T02, T03 — Claude executes, commits each → Codex audits B1 in the background → B2 goes on where it does not depend on B1 → B1 fixes at the next block boundary → commit
2. …
3. Hand-off: tests, `REVIEW.md`; you review while the last audits finish → fixes → your go-ahead → completion → push question

## Git plan

- Branch: `<branch per Git conventions>`
- Commit format: `<format>` — commits per the audit mode, one audit-fix commit per audit scope, one close-out commit
- Hand-off commit: HEAD at the hand-off; everything after it is a new commit — nothing you review is amended
- Push policy: <policy> — never before every audit is complete

## Cost and time

- Codex calls so far: <n> (planning) · tokens so far: <n>
- Plan limit: <x>% used, resets <date> (from the last `CODEX USAGE` line)
- Estimated Codex calls for the chosen option: see the table above

## Risks of the split

- <integration points between Claude-owned and Codex-owned tasks, interface assumptions, shared files>

## Detail — how audits run

- **Background:** every audit runs in the background (Codex through the launcher, Claude as a subagent); the chat stays free.
- **Hand-off early:** you get `REVIEW.md` once the last task is committed, while the last audits still run. Fixes come as new commits on top.
- **No early push:** nothing is pushed until every audit is complete.
- **One re-check only:** at most one automatic re-check per scope (round 2), only after a BLOCKER or HIGH fix, on the fix commit only. A BLOCKER or HIGH it finds always comes to you.
- **Claude audits are slower:** about 15–20 minutes against 1–2 for Codex (15 October 2026 test), but more thorough.
