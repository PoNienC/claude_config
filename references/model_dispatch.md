# Model dispatch — who does what, at which tier

> Read when: spawning any subagent, planning a multi-step task, or a
> subtask has failed twice. Written 4 July 2026; model facts verified
> against the live tool schemas and code.claude.com docs that day.
> If a model name below is not offered by the harness, STOP and use
> what the Agent tool schema actually lists — do not guess.

## Verified facts (do not fill these in from memory)

- Agent tool `model` parameter accepts: `sonnet` | `opus` | `haiku` | `fable`.
- Model IDs: `claude-fable-5`, `claude-opus-4-8`, `claude-sonnet-5`,
  `claude-haiku-4-5-20251001`.
- Reasoning effort: the in-session Agent tool has NO effort parameter.
  Effort comes from (a) the session `/effort` level (inherited by
  subagents), (b) a custom agent definition's `effort:` frontmatter
  (`low|medium|high|xhigh|max`) in `.claude/agents/*.md`, or (c) the
  Workflow tool's `agent(prompt, {effort})`.
  Docs: code.claude.com/docs/en/sub-agents.md, /model-config.md
- Subagent types available in this environment: `Explore` (read-only
  search), `Plan`, `general-purpose`, `claude`, `claude-code-guide`
  (docs questions), `geoai_critic` (review spatial outputs),
  `gis_code_reviewer` (read-only code review), `spatial_data_explorer`
  (read-only lineage), `sql_postgis_optimiser`.
- Whether safety-routed requests consume a scarce model window:
  UNCONFIRMED — test empirically on the usage dashboard.

## Rule 1 — the commander does not get into the field

The main conversation spends tokens ONLY on: decisions, user dialogue,
short precision edits, and arbitration between agent results. Delegate:

| Work | Send to | Why |
|---|---|---|
| Repo-wide scans, "where is X used" | Explore (haiku/sonnet) | Conclusions, not file dumps |
| Reading many/large files for a summary | general-purpose (haiku) | Main thread gets the summary |
| Docs/API questions ("does Claude Code support…") | claude-code-guide | Never answer harness questions from memory |
| Mechanical batch edits with clear spec | general-purpose (sonnet) | Spec is the judgment; typing is not |
| Verification of finished work | fresh general-purpose (sonnet) | See Rule 4 |
| Spatial output sanity | geoai_critic | Firm rule: runs before delivery |

Exception: a lookup of one known file/value is cheaper inline than an
agent spin-up. If it is under ~3 tool calls and you know exactly where
to look, do it inline.

## Rule 2 — every task assignment has three elements

1. **Goal + motivation** — what and why, one paragraph, self-contained
   (the agent has no conversation context).
2. **Acceptance criteria** — testable statements ("all 4 files compile",
   "returns the count and the top 5 paths").
3. **Report format** — "return ONLY: conclusions + `file:line` refs;
   write anything long to <path> and return the path."

Templates: `~/.claude/references/task_templates.md`.

## Rule 3 — escalation / de-escalation ladder

- Start mechanical work at **haiku**, standard work at **sonnet**.
- One clear error from haiku → resend to **sonnet** (same prompt +
  the failure).
- Two consecutive failures on the SAME subtask → escalate to **opus**
  and include the FULL failure trace of both attempts.
- Never retry the same approach more than **two rounds** — a third
  identical retry is the wrong-direction signal (see judgment_rubrics).
- Once the hard case is solved and a pattern exists, drop back to the
  cheap model and batch-apply the pattern.

## Rule 4 — verification is never self-verification

The author of a change never certifies it. After substantive work:
- **Files written** → a FRESH agent reads them back against the
  acceptance criteria (existence, completeness, internal consistency).
- **Code** → run the tests / the app; a green suite that never
  exercised the contract is not verification (see judgment_rubrics —
  the lenient-mock incident).
- **High-risk judgment** (irreversible, outward-facing, ambiguous) →
  second opinion from a differently-prompted agent, or ask the user.

## Reporting contract (paste into every agent prompt)

"Your final message is data for the orchestrator, not prose for a
human. Return only: (1) conclusions, (2) `file:line` references,
(3) explicit UNRESOLVED list if anything failed. Write long output to
a file and return its path. Do not echo file contents you were given."
