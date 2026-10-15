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

Choose one (recommendation: **<mode>** — <reason>):

| Mode | Audit points for this split | Codex audit calls | Claude audits | Trade-off |
|---|---|---|---|---|
| `per_block` (default) | B1 (T01-T03) → Codex · B2 (T04-T05) → Claude · … | | | |
| `per_task` | after each of the <n> tasks; each task waits for its own audit (the last one's runs during the hand-off) | | | slowest; smallest diffs |
| `end` | one audit per run of consecutive same-executor tasks, all at the hand-off (one Codex audit if Claude does everything) | | | fastest; late findings mean wider rework |

Blocks under `per_block`:

| Block | Tasks | Executor | Reviewer | Closes because | Overlap with next block? |
|---|---|---|---|---|---|
| B1 | T01-T03 | Claude | Codex | executor changes next | yes / no — <does the next block depend on B1?> |

## Background audits, hand-off and overlap

Every audit runs in the background (Codex through the launcher, Claude as
a subagent), so the chat stays free. You get the **hand-off** — the
result to review, with `REVIEW.md` — as soon as the last task is
committed, while the last audits are still running. Audit fixes then
arrive as new commits on top. **Nothing is pushed until every audit is
complete.**

Overlap — choose **on** (default) or **off** (recommendation: **<on/off>** — <reason>):

- On: while a block is audited, the next block starts if none of its
  tasks depends on a block whose audit is still open. Accepted findings
  are fixed at the next block boundary. Faster; some rework if an audit
  finds problems.
- Off: every block waits for its own audit (the last one still runs
  during the hand-off).
- `per_task` waits for each audit (the last one runs during the
  hand-off); `end` audits everything at the hand-off.

## Audit review

Choose one (recommendation: **<option>** — <reason>):

| Option | After each audit |
|---|---|
| `auto` (default) | the executor evaluates the findings and fixes the ones it accepts; you read the outcome in `AUDIT_LOG.md` |
| `ask` | nothing is fixed until you approve; the proposed resolutions are in `AUDIT_LOG.md` first |
| `ask_high` | stops for you only when an audit has a BLOCKER or HIGH finding; otherwise `auto` |

Expected stops for you with this split: `ask` — <n> (one per audit point); `ask_high` — only where serious findings appear.

Re-checks: at most **one** automatic re-check per audit scope (round 2),
only after a BLOCKER or HIGH fix, and it reviews only the fix commit. A
BLOCKER or HIGH found by the re-check always comes to you (fix, reject
or defer each) — there is no automatic third round.

## Effort and models per step

| Step | Codex effort | Codex model | Claude |
|---|---|---|---|
| Planning / plan review | {{EFFORT_PLAN}} | {{MODEL}} | this session |
| Execution | {{EFFORT_EXECUTE}} | {{MODEL}} | this session |
| Audit (round 1) | {{EFFORT_AUDIT}} | {{MODEL}} | subagent, session model |
| Re-check (round 2, the last) | {{EFFORT_RECHECK}} | {{MODEL}} | subagent, session model |

Claude's audits of Codex work run as a background subagent: slower than
a Codex audit (about 15–20 minutes against 1–2 in the 15 October 2026
test) but more thorough, and the chat stays free meanwhile.

## Order of work

1. B1: T01, T02, T03 — Claude executes, commits each → Codex audits B1 in the background → B2 goes on where it does not depend on B1 → B1 fixes at the next block boundary → commit
2. …
3. Hand-off: tests, `REVIEW.md`; you review while the last audits finish → fixes → your go-ahead → completion → push question

## Git plan

- Branch: `<branch per Git conventions>`
- Commit format: `<format>` — commits per the audit mode (per task or Codex block, plus one audit-fix commit per audit scope), and one close-out commit
- Hand-off commit: HEAD at the hand-off; everything after it (audit fixes, changes you ask for) is a new commit — nothing you review is amended
- Push policy: <policy> — never before every audit is complete

## Cost and time

- Codex calls so far: <n> (planning) · tokens so far: <n>
- Plan limit: <x>% used, resets <date> (from the last `CODEX USAGE` line)
- Estimated Codex calls for the chosen option: see the table above

## Risks of the split

- <integration points between Claude-owned and Codex-owned tasks, interface assumptions, shared files>
