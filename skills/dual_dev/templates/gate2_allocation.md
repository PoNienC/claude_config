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

## Audit mode

Choose one (recommendation: **<mode>** — <reason>):

| Mode | Audit points for this split | Codex audit calls | Claude audits | Trade-off |
|---|---|---|---|---|
| `per_block` (default) | B1 (T01-T03) → Codex · B2 (T04-T05) → Claude · … | | | |
| `per_task` | after each of the <n> tasks | | | slowest; smallest diffs |
| `end` | once for all Claude tasks (Codex) + once for all Codex tasks (Claude), at the same time | | | fastest; late findings mean wider rework |

Blocks under `per_block`:

| Block | Tasks | Executor | Reviewer | Closes because | Overlap with next block? |
|---|---|---|---|---|---|
| B1 | T01-T03 | Claude | Codex | executor changes next | yes / no — <does the next block depend on B1?> |

## Overlap (per_block only)

Choose **on** or **off** (recommendation: **<on/off>** — <reason>).
On: while Codex audits a block, the next block starts if it does not
depend on the block under audit. Accepted findings are then fixed at the
next task boundary. Faster; some rework if the audit finds problems.

## Audit review

Choose one (recommendation: **<option>** — <reason>):

| Option | After each audit |
|---|---|
| `auto` (default) | the executor evaluates the findings and fixes the ones it accepts; you read the outcome in `AUDIT_LOG.md` |
| `ask` | nothing is fixed until you approve; the proposed resolutions are in `AUDIT_LOG.md` first |
| `ask_high` | stops for you only when an audit has a BLOCKER or HIGH finding; otherwise `auto` |

Expected stops for you with this split: `ask` — <n> (one per audit point); `ask_high` — only where serious findings appear.

## Codex effort per step

| Step | Effort |
|---|---|
| Planning / plan review | {{EFFORT_PLAN}} |
| Execution | {{EFFORT_EXECUTE}} |
| Audit (round 1) | {{EFFORT_AUDIT}} |
| Re-check (round 2) | {{EFFORT_RECHECK}} |

## Order of work

1. B1: T01, T02, T03 — Claude executes, commits each → Codex audits B1 → fixes → commit
2. …

## Git plan

- Branch: `<branch per Git conventions>`
- Commit format: `<format>` — commits per the audit mode (per task or Codex block, plus one audit-fix commit per audit scope), and one close-out commit
- Push policy: <policy>

## Cost and time

- Codex calls so far: <n> (planning) · tokens so far: <n>
- Plan limit: <x>% used, resets <date> (from the last `CODEX USAGE` line)
- Estimated Codex calls for the chosen option: see the table above

## Risks of the split

- <integration points between Claude-owned and Codex-owned tasks, interface assumptions, shared files>
