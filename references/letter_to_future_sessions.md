# Letter to future sessions

> Written 4 July 2026, at the end of the one-off high-tier system
> session. Read when continuing the system build, or when something
> feels like it used to work better.

## Three things Po did not ask about, but matter most

1. **The verification gap is the project's real risk, not speed.** The
   push-to-FGDB bug lived for weeks behind a green suite because a mock
   accepted an argument the real API rejects. The single highest-value
   habit any future session can keep: when a test doubles an external
   API, mirror the REAL signature, and treat "the suite is green" as a
   claim about the tests, not about the code. Rubric 5 has the
   checklist.
2. **Release discipline is half-finished by default here.** v0.9.5b1
   was built but never tagged, released, or smoke-tested — for two
   months, across many sessions, everyone assumed someone else's
   session had done it. Anything called "shipped" needs the §2 done-
   definition (tag exists, release published, clean-unzip smoke test).
   The pending list below carries it forward explicitly.
3. **The OneDrive repo location is a standing hazard.** Files-On-Demand
   reparse points break rmtree (mitigated in build_bundle), sync can
   flip files read-only mid-write, and Claude config must never be
   created there. If odd `WinError 5` / permission errors appear:
   pause OneDrive sync first, investigate second.

## How this system will degrade, and prevention

- **Someone adds content to CLAUDE.md "just this once".** The router
  grows back into a 500-line always-on file. Prevention: the 150-line
  cap in maintenance_protocol.md — enforce it at session end; new
  doctrine goes in references/ with a route line.
- **A rules file gets a new `globs:` key by habit.** It will load
  always and silently. The working key is `paths:` (list syntax).
  Check with: does the file appear in context in an unrelated session?
- **HANDOVER.md drifts back into an append-only diary.** Overwrite in
  place; finished threads become one line; pending decisions stay at
  the top or they get lost on the next pivot.
- **Memory duplicates the references.** Memory = project facts and Po's
  corrections; references = doctrine. If a memory restates doctrine,
  replace it with a pointer.
- **The stubs get "helpfully" re-expanded.** rules/prior_partners_brand
  and rules/geoai_spatial_discipline are 8–11 line pointers BY DESIGN;
  full text lives in references/. Re-expanding them re-creates the
  token leak.

## Honest low-confidence list (this session's outputs)

1. **`paths:` gating behaviour — THE ONE THING TO VERIFY.** The whole
  token-leak fix rides on `paths:` actually gating the five scoped rules
  files. The key name is documented (code.claude.com/docs/en/memory.md);
  `globs:` was silently ignored. But I could NOT empirically verify
  gating fires on this harness version — a session's START snapshot
  always reflects the pre-edit state, so it is NOT evidence either way
  (an adversarial reviewer mistook the session-start dump for proof the
  fix failed — it was not). REAL TEST: open a FRESH session that touches
  no SQL/ArcPy/notebook file and inspect whether sql.md's text is in
  context. If YES → `paths:` is ignored here; correctness is still safe
  (the router's "Read X before Y" pointers make every file reachable on
  demand), only the savings are lost — then convert sql.md (455 lines,
  the bulk) to a stub + `references/sql_postgis.md`, and update the
  cross-refs that cite `rules/sql.md §`. If NO → the fix worked, leave
  it.
2. **BaseWeb portal CSS in the dark theme** (dropdown menus) — most
  version-fragile styling in the port; flagged in brand_dark.css. Not
  DOM-verified; Po's eyeball is the outstanding verification.
3. **Map-iframe font loading** (srcdoc base-URL inheritance for
  /app/static/ URLs) — reasoned from spec, not observed; harmless
  fallback to Arial if wrong.
4. **Quota routing** — whether safety-routed requests consumed the
  scarce window this session: unverifiable from inside; test on the
  usage dashboard.
5. **This letter's pending list** goes stale fastest — trust
  HANDOVER.md over this file for project state.

## Unfinished at time of writing (also in HANDOVER.md)

- [PR #5](https://github.com/Prior-Partners/PP_Spatial_Delivery_Console/pull/5)
  (push fix + runner + green suite) awaits Po's review/merge — after
  merging, re-run the full suite on main (expect 237 passed, 0 failed).
- User-run cleanup (classifier-blocked for agents; commands in
  quick_diagnosis_20260704.md §Leak 2): stale worktree removal +
  `bundle\staging` deletion.
- v0.9.5b1 (or v0.9.6) tag + GitHub Release + clean-unzip smoke test;
  bundle should be REBUILT from current main (style + fixes postdate
  the existing zip).
- Push-to-GIS layer-mapping happy-path verification run (then the
  `_BETA_DISABLE_PUSH_TO_GIS` decision) — runbook in
  docs/SDC_HEADLESS_RUNNER_PLAN.md §10.
- SDF document thread: second-pass items X2/X6/X8/X12/X13/X14 need
  Po's sign-off on proposed text. (The old defect-register plan file is
  no longer in ~/.claude/plans/ — ask Po for the current location or
  rebuild the register from the doc-revision session.)
- GETTING_STARTED.md describes pre-style UI (old title/expander/CRS
  default) — refresh before the next release.
- Graphics team: canonical lime (#DAE950 theme.json vs #DADF50
  template) firm-wide.
