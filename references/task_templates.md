# Task-assignment templates — fill in the blanks, delete nothing

> Read when writing any agent brief. Every template carries the three
> mandatory elements (goal+motivation / acceptance criteria / report
> format) and the reporting contract. Agents have NO conversation
> context — briefs must stand alone. Written 4 July 2026.

## Common footer (append to EVERY brief, verbatim)

"Your final message is data for the orchestrator, not prose. Return
ONLY: (1) conclusions, (2) file:line references, (3) an UNRESOLVED
list if anything failed or was ambiguous. Write long output to
<SCRATCH_PATH>/<name>.md and return the path. Do not echo file
contents you were given. If you cannot meet an acceptance criterion,
say so explicitly — do not approximate silently."

## 1. Search / locate  (agent: Explore; model: haiku, sonnet if subtle)

GOAL: Find <what> in <repo/path>. We need this because <one line>.
SCOPE: Search breadth = <medium | very thorough>. Include <dirs>;
EXCLUDE bundle/, .claude/worktrees/, node_modules, .venv.
ACCEPTANCE: every match as path:line + a one-line role description;
state the total count; say "none found" explicitly if none.
REPORT: list of path:line + roles; no file dumps.

## 2. Implementation  (agent: general-purpose; model: sonnet)

GOAL: Implement <feature/fix> in <files>. Why: <one line>.
CONSTRAINTS: match surrounding code style; British English in
docstrings/comments; type hints on public functions; pathlib not
os.path; no new dependencies without flagging; do NOT touch <files>.
ACCEPTANCE: <named tests> pass (`<exact test command>`); no new
failures vs baseline <N passed>; the change is ≤ <scope bound>.
REPORT: files changed as path:line ranges; test summary line verbatim;
UNRESOLVED list.

## 3. Refactoring  (agent: general-purpose; model: sonnet)

GOAL: Refactor <target> to <shape>, behaviour-preserving. Why: <line>.
CONSTRAINTS: NO behaviour change — public signatures stay unless the
brief lists the rename map; update all call sites + tests; keep
comment density.
ACCEPTANCE: full suite green (`<command>`, baseline <N>); grep shows
zero remaining references to <old name(s)>.
REPORT: rename/move map (old → new path:line); suite summary; any
call site you were unsure about.

## 4. Research  (agent: claude-code-guide for harness/API questions,
     general-purpose + web tools otherwise; model: sonnet)

GOAL: Answer <precise question(s)>. Decision it feeds: <one line>.
METHOD: primary sources first (official docs, vendor pages); note the
URL for every claim; if sources conflict, present both sides.
ACCEPTANCE: each question answered in ≤3 sentences with a confidence
marker — documented / inferred / not-found. "Not found" is an
acceptable answer; a guess is not.
REPORT: per question: answer, confidence, URL(s).

## 5. Review / verification  (agent: FRESH general-purpose or
     gis_code_reviewer (read-only); model: sonnet; never the author)

GOAL: Adversarially review <artefact(s)> against <criteria/brief>.
Assume the author was wrong somewhere; your job is to find where.
CHECK AT MINIMUM: internal contradictions; paths/names that do not
exist on disk (verify by listing, not trust); claims of "verified"
without evidence; mocks looser than the real API; wording a weaker
model could misread (two plausible readings = a finding).
ACCEPTANCE: every finding has severity (blocker/major/minor),
location (file:line), and a concrete fix suggestion. Zero findings is
a valid result ONLY after listing what you checked.
REPORT: findings table + checked-list; nothing else.
