# Gate 2 — what the options mean (standing text, same for every request)

This file is linked from each request's `ALLOCATION.md`; it is never
copied into it. Request-specific choices and reasons live in `ALLOCATION.md`.

## Execution split

| Option | Claude executes | Codex executes | Reviews |
|---|---|---|---|
| A (default) | all tasks | none | Codex audits every scope |
| B | the tasks marked Claude | the tasks marked Codex | each scope audited by the other agent |
| C | none | all tasks | Claude's audit subagent reviews every scope |
| D | custom — the user names the split | | |

Codex suits tasks that are independent, well scoped, testable and
interface-stable. A Codex-executed scope is reviewed by Claude's audit
subagent, which takes about 15–20 minutes against 1–2 for a Codex audit
(measured 15 October 2026) — split for a real execution benefit, not for
balance.

## Audit mode

| Mode | Audits happen | Trade-off |
|---|---|---|
| `per_block` (default) | once per run of consecutive same-executor tasks (a block also closes after a High-risk task or six tasks) | one finding may touch several tasks |
| `per_task` | after every task; each task waits for its own audit (the last one's runs during the hand-off) | slowest; smallest diffs |
| `end` | one audit per same-executor run, all at the hand-off | fastest; late findings mean wider rework |

Every audit runs in the background. The hand-off review (`REVIEW.md`)
comes as soon as the last task is committed; audit fixes arrive as new
commits on top; nothing is pushed until every audit is complete.

## Overlap (`per_block` only)

- On (default): while a block is audited, the next block starts if none of
  its tasks depends on a block whose audit is still open; accepted
  findings are fixed at the next block boundary. Faster; some rework if an
  audit finds problems.
- Off: every block waits for its own audit.

## Audit review

| Option | After each audit |
|---|---|
| `auto` (default) | the executor evaluates the findings and fixes the ones it accepts; the outcome is in `AUDIT_LOG.md` |
| `ask` | nothing is fixed until the user approves the proposed resolutions in `AUDIT_LOG.md` |
| `ask_high` | the user is asked only when an audit has a BLOCKER or HIGH finding; otherwise `auto` |

Re-checks: at most one automatic re-check per scope (round 2), only after a
BLOCKER or HIGH fix, reviewing only the fix commit. A BLOCKER or HIGH found
by the re-check always comes to the user.

## Codex effort and model

| Step | Default | With `--xhigh` |
|---|---|---|
| Plan, plan review | medium | high |
| Execute, corrections | high | xhigh |
| Audit (round 1) | medium | medium |
| Re-check (round 2, the last) | low | low |

Model: Codex's own default unless the request says `--model <name>`. Claude's
audit subagent runs on the session model.

## Git

One request = one branch; one commit per task (or per Codex block); one
audit-fix commit per scope; one close-out commit. Commits under audit or
under the user's review are never amended. Push only with the user's
approval, and never while an audit is open.
