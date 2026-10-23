# Gate 2 — execution split: {{REQUEST_ID}} {{TITLE}}

- Date: {{DATE}}
- Approved plan: [PLAN_APPROVED.md](PLAN_APPROVED.md) · Gate 1 record: [COMPARISON.md](COMPARISON.md)
- Codex execution on this machine: {{CODEX_EXECUTION}} (from `.ai/PROJECT.md`)
- Codex: model {{MODEL}}, effort {{EFFORT}} · [what the options mean]({{STANDING_OPTIONS_PATH}})
- Decision: _pending_ <!-- after the answer: option, date, the user's words verbatim -->

## In short

- **Split:** <A / B / C / D> — <one-line reason>
- **Audit mode:** <per_block with overlap on / off · end · per_task> — <one-line reason>; <n> audit points, <n> Codex calls (est.)
- **Audit review:** <auto / ask / ask_high> — <one-line reason>; expected stops for you: <n>
- **Effort and model:** <as standing table, or the change>
- **Close-out:** ask at the end (default) — or automatic, if you approve it here under the same conditions as the combined gate

## Proposed split

| Task | Title | Executor | Reviewer | Block | Depends on | Risk | Why this executor |
|---|---|---|---|---|---|---|---|
| T01 | | Claude | Codex | B1 | — | | |

## Blocks and audit points

| Block | Tasks | Executor | Reviewer | Closes because | Overlap with next block? |
|---|---|---|---|---|---|
| B1 | T01-T03 | Claude | Codex | executor changes next | yes / no — <does the next block depend on B1?> |

## Order of work

1. B1: T01, T02, T03 — Claude executes, commits each → Codex audits B1 in the background → B2 goes on where it does not depend on B1 → B1 fixes at the next block boundary → commit
2. …
3. Hand-off: tests, `REVIEW.md`; you review while the last audits finish → fixes → your go-ahead → completion → push question

## Git plan

- Branch: `<branch per Git conventions>` · commit format: `<format>` · push policy: <policy>

## Cost so far

- Codex calls: <n> (planning) · tokens: <n> · plan limit: <x>% used, resets <date>

## Risks of the split

- <integration points between Claude-owned and Codex-owned tasks, interface assumptions, shared files>

<!-- Whole file: at most 300 words outside the tables. Standing explanations stay in gate2_standing_options.md — link, never copy. -->
