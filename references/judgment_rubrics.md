# Judgment rubrics — decisions turned into checklists

> Read when: unsure whether to escalate, declare done, ask the user,
> change approach, or accept quality. Every rubric has one positive and
> one negative example from THIS user's real project history — cite
> them when explaining a decision. Written 4 July 2026.

## 1. When to escalate the model

Escalate when the task involves: an external API contract that must be
reasoned about (not looked up), a cross-file architectural change, an
irreversible action's blast-radius analysis, or reconciling
contradictory evidence.

- ✅ Escalate: the Push-to-GIS bug — `arcpy.ListFeatureClasses` was
  called with a `workspace` kwarg the real API lacks, and the test mock
  ACCEPTED the phantom kwarg, so the suite stayed green. Catching that
  required reasoning about the real Esri signature vs the mock — a
  contract question, not a lookup.
- ❌ Do not escalate: renaming a button label, bumping a version
  string, moving a file. Two failed retries of THOSE means re-read the
  error, not upgrade the model.

## 2. When something counts as truly done

Done = the work's own definition of complete, not "the code ran".
Domain floors that already exist and BIND:
- PostGIS load: exactly 1 PK + 1 GIST + table & column comments +
  catalogue refreshed (see `~/.claude/rules/sql.md`). A load missing
  any of these is INCOMPLETE.
- FGDB push: feature counts match source, CRS = project EPSG (not
  4326), provenance fields present.
- A release bundle: smoke-tested from a clean unzip, not merely built.

- ✅ Done properly: the 4 July 2026 style merge — reviewed side-by-side
  by the user, revised, THEN committed, with provenance doc.
- ❌ Not done: v0.9.5b1's zip was declared ready but never smoke-tested
  from a clean unzip; the tag was never created. "Built" was mistaken
  for "shipped", and the gap persisted across sessions.

## 3. When to stop and ask the user

Ask BEFORE acting when the action is: naming a production/published
artefact; modifying source data during ingestion (nulls, units,
filters, renames); committing/merging/pushing anything not explicitly
ordered; deleting or overwriting pre-existing files; sending anything
outside the machine; spending money; or a job expected to exceed the
>5-minute cost-honesty threshold (state the cheaper alternative first —
references/performance_discipline.md).

- ✅ Asked correctly: the GT America fonts — committing licensed font
  files needed the user's licence ruling (got "private repo OK").
- ❌ Should have asked (historical): a `UNIQUE NOT NULL` constraint
  added to six staging tables without sign-off — user had to drop six
  constraints (26 May 2026, VOA load).
Do NOT ask about: ports, temp paths, obvious defaults, which of two
equivalent test names to use. One-turn clarifications are for
decisions that change the outcome, not for reassurance.

## 4. Signals the direction is wrong (switch path, do not retry)

- The same fix has failed twice with the same error class.
- You are fighting the platform (e.g. styling BaseWeb portal internals,
  forcing CSS across an iframe) — find the injection point the platform
  provides instead (the `_LayerControlExtras` header-macro lesson).
- Output contradicts the tool's own documentation — stop, re-read docs
  (the `globs:` frontmatter did nothing for months; the key is `paths:`).
- A long single-shot operation keeps timing out — chunk it (the 74-min
  abandoned `ST_Union` vs the 19-min per-LAD rewrite; chunking should
  be the FIRST plan for heavy geometry, see performance discipline).
- ✅ Good switch: OneDrive `WinError 5` on rmtree → wrote
  `rmtree_force()` handling reparse points, instead of retrying rmtree.
- ❌ Bad persistence: re-running an unchanged failing command a third
  time "to see if it passes".

## 5. How to verify the quality floor

- A green test suite proves only what the tests actually assert. If a
  mock is looser than the real API, green is a lie — mirror real
  signatures in mocks (the ListFeatureClasses incident is the canonical
  example; the hardened mock now raises TypeError on the phantom kwarg).
- Files claimed written → a fresh agent (or at minimum a directory
  listing + line counts) confirms existence and non-emptiness.
- UI changes → the user's eyeball round IS the verification when no
  DOM tooling is available; say so plainly instead of claiming
  "verified".
- Data outputs → counts reconciled against source, CRS checked
  explicitly, spot-check attributes. Never declare a spatial output
  correct without the CRS check — wrong-CRS is the silent failure mode.
- Report failures faithfully: state the red tests with output, name
  what was skipped. Optimistic summaries compound into next-session
  archaeology.
