---
name: uk_baseline_new_layer
description: Load a brand-new data layer into the uk_baseline PostGIS database end to end — scope and name, source capture, ingestion brief, staged load into uk_new, table and column comments, verification, then one review pull request; after the data manager merges, promotion into uk_baseline, the data register and the catalogue. Use this whenever someone wants to load, add, ingest, import or register a new dataset, layer, table or file into uk_baseline or the gis database — including "start a load", "new layer", "load this GeoJSON / GPKG / shapefile / CSV into the database" — and when resuming an in-flight load branch or checking whether a load pull request has been merged. Supersedes the older postgis_layer_creation skill. Not for adding MSOA, LAD, county or SDS geography columns to a layer (that is the separate enrichment skill), not for refreshing a layer that already exists, and not for ad-hoc analysis tables outside uk_baseline.
---

# uk_baseline_new_layer — load a new layer, with one review gate

## What this skill covers, and what it deliberately does not

It takes a dataset from a publisher's website to an accepted, documented table
in `uk_baseline`. It does **not** add the standard geography columns
(`msoa21cd`, `lad25cd`, `ctyua25cd`, `sds_name` and the rest). That work
splits and rewrites the loaded rows, so it carries its own strict rules and
lives in a **separate enrichment skill**, run after the merge. When a load
finishes, say so plainly: the layer is loaded and accepted, and enrichment is
a separate job the data manager schedules.

**Who runs this.** A data loader with a read-write role on the database. The
safety model is *review, not permissions*: nothing physically stops a
premature write, so the discipline is the protection. Two consequences:

1. **Be instructive.** The loader is learning the discipline by running it. At
   each gate, say in a sentence or two *why* it exists before doing the work.
2. **Every write is deliberate.** Dry-run first, show the output, and only
   apply after the loader has read it and said to go ahead. Never chain a dry
   run straight into a write.
3. **Asking means stopping.** Wherever this skill says to confirm something,
   put the question to the loader and **wait for their answer** before doing
   anything else. Announcing a decision and carrying on in the same reply is
   the most common way these gates fail — it looks like consultation and is
   not. If you find yourself writing "I'll proceed unless you object", stop and
   ask properly instead.

**One load at a time.** If a `load/*` branch is already open, finish or park
it first. Concurrent spatial writes contend on IO — a six-minute job once took
twenty-eight minutes running alongside another.

## The shape of the flow

```
Phase A — branch load/<name>, everything in the staging schema uk_new
  01 scope + proposed name    02 capture the source
  03 ingestion brief          04 stage the load into uk_new
  06 comment the table        08 verify + the loader's QGIS check
  → build the load report → open ONE pull request, ready for review

HARD STOP — the data manager merges. Merge = the load is accepted.

Phase B — after the merge only
  05 promote into uk_baseline      09 complete the data register row
  10 refresh the catalogue         11 close the loop + report addendum
  → hand off to the separate enrichment skill
```

Step 05 sits in Phase B on purpose. The eleven-step guide prints it earlier,
but the data manager confirms the production name **at the pull request**, so
promoting before the merge would mean promoting under an unconfirmed name. If
the name or the brief is rejected at review, the rework is a rename or reload
in `uk_new` — cheap, because production was never touched.

## Hard stops — never pass these yourself

| Never | Who decides | When |
|---|---|---|
| Move past step 01 without the importer agreeing the name out loud | Importer | At step 01 — confirm or amend, and wait for the answer |
| Load without the importer agreeing the source and target CRS | Importer | At step 04 — confirm or amend, and wait |
| Change the target from EPSG:27700 | Data manager | Deviation from the standard; record it and flag it in the PR |
| Confirm the production table name | Data manager | At the PR |
| Sign off the ingestion brief | Data manager | At the PR |
| Approve a derived column, unit change, row filter or semantic rename | Data manager | At the PR — flag each one in the PR body |
| Create any index beyond one PK + one GIST(geom) | Data manager | Per instance |
| Run a write unprompted | Loader, after reading the dry run | Each write |
| Touch `uk_baseline`, the register or the catalogue before the merge | — | Phase B only |
| Publish the catalogue without the data manager's review | Data manager | Phase B |
| Start a second concurrent load | — | One at a time |

Prepare each gate — draft the register row, generate the brief, print the dry
run, build the report — and stop at it.

## Hard rules — fail loudly, never work around

- **Never invent** a column, unit, label, edition date or name. Undocumented
  source fields are carried under their source name and marked
  `[UNDOCUMENTED]`.
- **EPSG:27700** for all UK work. An unstated input CRS is assumed EPSG:4326
  until inspection proves otherwise. Never measure distance or area in 4326.
- **Staging first**: every load lands in `uk_new`, never straight into
  `uk_baseline`.
- **Index floor**: exactly one PRIMARY KEY and exactly one GIST(geom),
  verified after every load — `PROMOTE_TO_MULTI` can silently stop the primary
  key forming.
- **Comments are mandatory**, in the sectioned template: no SQL inside
  comments, no banned words ("vintage", "grain" as a resolution term,
  "(accessed …)", "at audit time"), dates as `D Month YYYY`, British English.
- **Cost honesty**: before anything you estimate over five minutes, state the
  estimate and the cheaper chunked alternative first.

## Preflight — before step 01

Run `python scripts/preflight.py` from the repository. It checks Python,
psycopg, `ogr2ogr`, the database connection, whether the caller really holds
CREATE on `uk_new`, git, `gh`, and the register on P:. If anything fails, tell
the loader to run `setup.bat` (which installs the lot and signs them in to
GitHub) and point at `docs/user_setup_and_run.md` — do not try to hand-fix
their machine.

Then **ask the loader for their initials** — two or three letters, going into
the register's `data_importer` column so every layer traces to a person. Also
confirm no other `load/*` branch is open.

**Do not create the branch yet.** It is named after the layer, and the layer is
not named until the importer agrees it at step 01. A trial created the branch
first and ended up with `load/..._airfield` against a table called
`..._airfields` — harmless but confusing, and it makes the branch look like the
authority on the name when the importer is. Create both **after** the step 01
agreement:

```
git checkout -b load/<agreed_name>
copy templates\load_manifest.json manifests\<agreed_name>.json
```

The manifest is the running record — fill it as you go; the report generator
renders it, so an unfilled field becomes a visibly unfinished report. Commit
after each step (`load/<name>: step 04 staged (rows=52,341)`) and push the
branch as the audit trail, but open **no pull request** until Phase A is done.

If the data manager corrects the name at the pull request, that correction wins:
the branch keeps its old name (renaming it mid-review loses the thread), and the
table is promoted under the corrected name in Phase B.

## Phase A — build the layer in staging

### Step 01 — scope and name

- Check the register first — is this dataset, or an older edition, already
  loaded?
  `P:\0_Practice\10_Data management resources\04_Spreadsheets\DI\uk_baseline_data_register.xlsx`
- Assign one of the twelve theme codes and build the name to the standard in
  `docs/naming_standard.md`. Never invent a code or a shape.
- Draft the register row now; it is completed in Phase B.

#### Then stop and get the name agreed — do not skip this

**The importer must actively agree the name before anything is created.**
Recording it in the manifest and carrying on is not agreement. Neither is
saying "this is a proposal" and continuing in the same breath — that reads as
told, not asked, and the name then reaches the pull request having been seen by
nobody.

Present the name broken into its parts, so the importer can judge each
decision rather than accept or reject a single string:

```
Proposed layer name:   her_stirlingcouncil_ww2_airfields_jan2025

  her               Heritage & Historical Assets - historic, non-operational sites
  stirlingcouncil   the publisher
  ww2_airfields     what the data is
  jan2025           the data's own edition (published as modified 27 January
                    2025), not today's date
```

Say where each part came from, and flag anything you were unsure about — a
publisher who might be the host rather than the originator, an edition date
you had to infer, a theme that was a close call between two codes.

##### If the publisher does not state an edition, ask — never infer

The publisher's own words settle the edition. When they say nothing, **the
importer decides**, and machine timestamps do not. Two trial runs of the same
dataset named it `aug2026` and `jan2025` because three timestamps disagreed and
each run picked a different one.

Present every candidate side by side and say plainly that the publisher is
silent:

```
Edition - the publisher states none in words. Candidates:

  aug2024   `created`          the service was first published
  mar2025   `modified`         the record was last edited
  aug2026   `dataLastEditDate` a row was last touched - three days before this
                               load, with the row count unchanged, so this
                               looks like an automated republish
  (none)    the dataset genuinely has no edition
```

Then ask which the name should carry, and **wait**. A timestamp that moves while
the row count does not is a republish, not a new edition — naming from it makes
the layer's name churn on every reload. Record the choice and the reason in
`manifest.decisions`. If the importer does not know either, load under the name
they nominate and flag the edition as unresolved in the PR body for the data
manager. Full rule: `docs/naming_standard.md`.

Then **ask, and wait.** Use `AskUserQuestion` where it is available, otherwise
a plainly numbered choice. Offer exactly these:

- **Confirm** — use this name as it stands.
- **Amend** — the importer supplies a different name, or changes one part of
  it. Rebuild the name, present it in the same broken-down form, and ask again.
  Repeat until they confirm.
- **Not sure** — explain the trade-off in more detail and ask again. Never
  resolve an unsure into a yes on their behalf.

**Silence is not consent.** If there is no answer, stop and wait; do not
proceed to step 02.

This is the importer's agreement, and it does **not** replace the data
manager's confirmation at the pull request. Two people look at the name for
different reasons: the importer checks it describes the data they are holding,
and the data manager checks it fits the collection. Both matter, because a
rename later cascades through the catalogue, the Dashboard styles, users' QGIS
projects and the register.

Record the agreed name in `manifest.proposed_name`, and record any amendment
the importer made in `manifest.decisions` — what it was and why — so the data
manager can see the name was considered rather than generated.

### Step 02 — capture the source

Two routes; pick whichever suits the source, and record which in
`manifest.source_capture.route`.

- **Route A — Claude downloads it.** Fetch from the publisher's canonical page
  (not a mirror) straight into `data/source/<source_name>/`.
- **Route B — the loader downloads it.** Some publishers need a login, a
  licence acceptance, an email link or a manual area selection. The loader
  downloads it themselves and saves it either locally or on the practice
  server, then tells Claude the full path. Confirm the file is readable and
  record that path in the manifest. This route is normal, not a fallback —
  say so, so the loader does not fight a portal unnecessarily.

Either way:

- Record the exact source URL, edition date and licence (most UK government
  data is Open Government Licence v3.0).
- Keep the raw file **untouched** — it is the audit copy.
- Copy the publisher's definitions of the core concepts **verbatim**, in double
  quotes, with the URL. They go in **two** places, and **never** in a per-layer
  file of their own:
  - the cumulative `reference/source_definitions.md` in the project, which
    gathers every dataset — that is what you search when trying to remember
    what a publisher meant three loads ago;
  - the brief's appendix (step 03), so the brief stands on its own for review.
- Record the raw file's size and feature count — step 04 checks against it.
- Note what the source does *not* say: undocumented columns, missing units,
  unstated CRS. These become step 03's open questions.

### Step 03 — the ingestion brief

Write the brief and record its path in the manifest:

1. **Source inventory** — every column as published, its type, the row count,
   and the publisher's documented meaning. Quote, don't paraphrase. No
   published definition means `[UNDOCUMENTED]`.
2. **Destination schema** — the full proposed `CREATE TABLE`, every column
   tagged `[source]`, `[boundary]`, `[synthetic]` or
   `[derived — needs approval]`.
3. **Open questions** — units, editions, licences, anything unstated.
4. **Appendix: the publisher's definitions, verbatim** — the same quotes taken
   in step 02, so the brief stands on its own and a reviewer reads one document
   rather than chasing a second. Do **not** create a separate per-layer
   source-definitions file.

Set `manifest.brief_status = "drafted"`. The data manager signs it at the PR,
not before the staging write; the accepted trade-off is cheap staging rework.
Anything tagged `[derived — needs approval]` may be built in staging but must
be listed in the PR body for an explicit yes or no.

### If the source is a CSV or spreadsheet — find its geometry first

A CSV carries no geometry, so before step 04 can run at all it needs one. Do
this between the brief and the load, and record the outcome in the brief:
it changes the destination schema.

Start by profiling the file. This is the one job a script does far better than
reading the columns by eye, because it test-joins against what we actually
hold:

```
python scripts/inspect_csv.py <path-to-file.csv>
```

It reports every column, what each looks like, and — for anything code-shaped —
the **match rate against every boundary in `uk_baseline`**. Then work down this
list; the first route that holds wins.

**1. An administrative code that joins to a boundary we hold.** The best
outcome. The boundaries available are Output Area 2021, LSOA 2011 and 2021,
MSOA 2011 and 2021, ward May 2025, and local authority 2011 / May 2022 / May
2024 / May 2025.

**Establishing which edition is the whole difficulty, and it is not optional.**
Codes usually survive a boundary revision unchanged, so a 2011 file can match
the 2021 boundary at 97% — or, for MSOA, at 100%. A high match rate proves the
codes *fit* that boundary; it does not prove it is the boundary the publisher
built the data against. When the tool reports two editions close together:

- Find the publisher's own statement of which edition they used, and quote it
  in the brief. That, not the match rate, settles it.
- **Never simply take the higher number.** Joining 2011 data to 2021 boundaries
  silently misplaces rows wherever a boundary changed, and nothing downstream
  will ever flag it.
- If the documentation genuinely does not say, that is an open question for the
  data manager — put it in the brief and the PR, do not resolve it yourself.

Either way, **put the recommended route and edition to the loader and get an
explicit yes** before writing anything.

**2. No usable code, but coordinates in columns.** Eastings and northings imply
EPSG:27700; latitude and longitude imply EPSG:4326 and must be reprojected on
load. Confirm the CRS with the loader — a column called `x` is not evidence —
and sanity-check that the points land in the United Kingdom before going on.

**3. No code and no coordinates — look for a postcode.** It may be under a name
the profiler does not recognise: `site postcode`, `location`, `address`,
`ward office`. Ask the loader to check the publisher's column list. We hold the
full ONS postcode directory (`adm_ons_postcode_centroid_feb2026`, 2.7 million
postcodes), so a postcode column is a workable route. Say plainly what it
produces: **a centroid, not a real extent** — the layer becomes points, and the
table comment must record that the geometry is a postcode centroid rather than
the feature's true shape.

**4. The right boundary is not in `uk_baseline`.** If the data is at a
geography we do not hold — parish, travel-to-work area, health board, a
boundary edition we lack — do not substitute the nearest thing we have. Find
the official boundary on the ONS Open Geography Portal:

```
https://geoportal.statistics.gov.uk/
```

Give the loader the **specific dataset link** to verify, and stop there.
Loading that boundary is a new layer in its own right, which means its own
load, its own name and its own review.

**5. Anything else — hand it to the data manager.** Codes that are not ONS
codes, a bespoke reference system, a geography that needs a judgement call:
commit what you have with the profiler output, open a pull request describing
exactly what was found and what is missing, and say so. An unresolved question
in a pull request is a good outcome. A guessed join is not.

Whatever the route, the brief must state it, the table comment must record how
the geometry was derived, and — for routes 2 and 3 — that the geometry is
derived rather than supplied by the publisher.

### Step 04 — stage the load

#### First, stop and get both coordinate systems agreed

**Ask before loading, the same way as the name in step 01.** Two separate
facts, and the source one is the more dangerous:

- **Source CRS** — what the data is *already* in. Get this wrong and every
  feature lands somewhere plausible but wrong, with nothing downstream to
  catch it. An unstated CRS is assumed EPSG:4326 (the GeoJSON default), and
  **that assumption must be shown, not buried** — it is a guess, and the
  importer may know better.
- **Target CRS** — EPSG:27700 (British National Grid) for everything in
  `uk_baseline`. This is the house standard, not a preference.

Present both, with the evidence for each:

```
Coordinate reference systems

  Source   EPSG:3857 (Web Mercator)
           declared by the publisher's service; requested as EPSG:4326 on
           download because 3857 is a web-tile projection and is never used
           for analysis here

  Target   EPSG:27700 (British National Grid)      <- uk_baseline standard
```

Then ask, using `AskUserQuestion` where available, and **wait**:

- **Confirm** — both are right, proceed.
- **Amend** — the importer corrects either one. Rebuild and ask again.
- **Not sure about the source** — do not guess. Check the publisher's
  documentation, or load a sample and see where it lands on a basemap, then
  come back with evidence.

Say what you actually checked: a declared CRS in the file, an `.prj` sidecar,
the service metadata, or nothing at all. "Assumed 4326 because the file says
nothing" is an honest answer and the importer can then agree or correct it.

**If the importer amends the target away from EPSG:27700**, that is a
deviation from the standard, not a preference. Record it in
`manifest.decisions` with their reason, flag it in the PR body for the data
manager, and say plainly that measuring distance or area in a geographic CRS
such as 4326 is never valid here.

#### Then load

- Into `uk_new`, reprojected to the agreed target. Resolve `ogr2ogr` with
  `scripts/db.py` (`find_ogr2ogr()`) — it is not on the PATH on a standard
  workstation, it lives inside QGIS.
- **Give `ogr2ogr` an absolute source path**, always. A relative one failed in a
  trial because the working directory had moved between the download and the
  load, and the error it gives ("failed to open") reads like a corrupt file
  rather than a missing one, which sends you looking in the wrong place.
- **A CSV is loaded as its attribute table first**, then given geometry by the
  route agreed in the section above — never by inventing a coordinate.
- The canonical flag set, each flag there because of a past failure. Set
  `-s_srs` explicitly when the source CRS was assumed rather than declared, so
  the assumption is visible in the command the importer approves:

  ```
  -t_srs EPSG:27700
  -lco GEOMETRY_NAME=geom  -lco FID=gid  -lco PRECISION=NO
  --config PG_USE_COPY YES  -gt 65536  -progress
  ```

- **Geometry type: keep whatever the source has.** There is deliberately no
  `-nlt` in the set above, so `ogr2ogr` carries the source type through — a
  point layer stays `POINT`, a polygon layer stays `POLYGON`. `uk_baseline`
  currently splits 13 `POINT` to 5 `MULTIPOINT` only because the old flag set
  promoted single points for no benefit.

  Add `-nlt PROMOTE_TO_MULTI` **only** when the source genuinely mixes single
  and multi parts in one layer, where the load fails without it. When you do,
  say so and expect the consequence: promoting makes the source FID repeat
  across rows, so `-lco FID=gid` yields a non-unique column and **no primary
  key forms**. Step 08 catches it; the fix is a fresh
  `gid bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY`, which is part of the
  default set and needs no approval.

- Print the full command as the dry run, then **stop and ask** whether to run
  it. Same rule as the name in step 01: showing the command and continuing is
  not asking. Wait for a yes.
- Count `ST_IsValid` failures. **Never repair silently** — put the
  keep-or-`ST_MakeValid` decision to the loader, record it in
  `manifest.decisions`, and it goes into the table comment as a caveat.
- Check: staged row count equals the source count from step 02;
  `geometry_columns` shows the agreed SRID; and the extent lands where the data
  should be. An extent in the wrong hemisphere, or metres where degrees were
  expected, means the source CRS was wrong — stop and re-ask rather than
  loading it again with a different guess.

### Step 06 — comment the table, in staging

`COMMENT ON TABLE` in the sectioned template — a one-line description leading
with the source organisation and ending with the edition Month YYYY, then
SOURCE, DOCUMENTATION, DEFINITIONS, SCOPE, CRS, LICENCE, optional DATA QUALITY
CAVEATS, and LOADED INTO. Then `COMMENT ON COLUMN` for every column, one line
each: value columns state the unit verbatim in double quotes, identifier
columns cite the source field in backticks. Comments travel with the table
when it is promoted.

Check: sections in order, banned-word scan, a comment on every non-surrogate
column, no SQL anywhere in the text.

### Step 08 — verify, in staging

Run each check against `uk_new` and record it in `manifest.verification`:

```sql
-- exactly one primary key (expect 1)
SELECT count(*) FROM pg_constraint
WHERE conrelid = 'uk_new.<table>'::regclass AND contype = 'p';

-- exactly one GIST index on geometry (expect 1), and no others
SELECT indexname FROM pg_indexes WHERE schemaname='uk_new' AND tablename='<table>';

-- table comment present, column comments present
SELECT obj_description('uk_new.<table>'::regclass) IS NOT NULL;
SELECT count(*) FROM pg_description
WHERE objoid = 'uk_new.<table>'::regclass AND objsubid > 0;
```

Then the **loader's QGIS visual check**: connect QGIS to `uk_new`, inspect the
layer (extent, geometry sanity, symbology on a key attribute, a known-place
spot check), and sign `manifest.qgis_check` — by, date, what was checked,
verdict. The report prints that signature and an unsigned check blocks the PR.

### Close Phase A — the report and the single pull request

```
python scripts/build_load_report.py --layer <staging_table> \
    --manifest manifests/<name>.json
```

A non-zero exit means the index floor or the CRS check failed. Fix and re-run;
**do not open the PR on a failing report.**

The report **embeds the brief**, so it is the single document a reviewer opens:
proposal, then measured facts, then decisions, then what is still unresolved.
Keep the branch to **three files** — the manifest (a machine record, not for
reading), the brief, and the report. Anything else duplicates one of them, and
a reviewer facing four documents reads none of them properly.

Then commit and push, open **one pull request, ready for review** (not a
draft), with the body from `templates/pr_body.md` and every box genuinely
ticked. The body links **the report only** — do not list the manifest or the
brief as separate things to read. Tell the loader what the data manager will
do: confirm the name, sign the brief, rule on each flagged derivation, run
their own QGIS check on the staging table, and merge.

## The wait — merge is the only signal

```
gh pr view <number> --json state,mergedAt
```

`MERGED` unlocks Phase B. Changes requested means rework in staging, a
regenerated report, and another wait. An approving review **without** a merge
is not acceptance. Do not poll in a loop — check when the loader next asks.

## Phase B — production, after the merge only

Re-run the merge check even if the loader says it is merged, and use the name
**as merged**: if the data manager corrected it in review, that correction
wins over the manifest.

**05 — Promote.** `ALTER TABLE uk_new.<staging> SET SCHEMA uk_baseline;` then
`RENAME TO` the confirmed name. Dry-run first. **Re-verify the index floor on
the promoted table** — if no unique not-null column exists, add
`gid bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY` (part of the default
set, no approval needed). Audit `pg_indexes` for extras.

**09 — The data register.** Complete the row drafted in step 01, using the
loader's initials in `data_importer`. Field-by-field instructions are in
`docs/data_register_guide.md`. The workbook must be closed in Excel first — an
open file silently blocks the save. Unknown fields stay blank, never invented.

**10 — The catalogue.** Regenerating and republishing the catalogue requires
the data manager's review; it is not the loader's call. Prepare what is needed
and hand over unless the data manager has said to proceed.

**11 — Close the loop.** Append the completion record:

```
python scripts/build_load_report.py --addendum --layer <confirmed_name> \
    --schema uk_baseline --report reports/<layer>_<yymmdd>.md \
    --register-updated yes --catalogue-commit <hash> --site-published yes
```

Then hand off: the layer is loaded and accepted; **geography enrichment is the
separate enrichment skill** and is the data manager's to schedule. Finish by
giving the loader the full paths of the merged report and anything else
produced.

## Refuse loudly when

- Asked to skip a dry run, a gate, or the one-load-at-a-time rule.
- Tempted to carry on past step 01 because the name "looks obvious" — it is
  agreed out loud or the load does not start.
- Asked to write to `uk_baseline`, the register or the catalogue before the
  merge is visible.
- A name, unit, column or label would have to be invented to proceed.
- A CSV's boundary edition is uncertain and the answer would be a guess —
  including picking whichever edition matched slightly better.
- Verification fails and the suggestion is to carry on anyway.
- Asked to add geography columns here — that is the enrichment skill.
- A second load is requested while one is in flight.

## Files this skill uses

| What | Where |
|---|---|
| Connection + `ogr2ogr` discovery | `scripts/db.py` |
| Setup check | `scripts/preflight.py` |
| CSV geometry assessment | `scripts/inspect_csv.py` |
| One-click machine setup (installs + GitHub sign-in) | `setup.bat` |
| Report generator | `scripts/build_load_report.py` |
| Manifest and PR body templates | `templates/` |
| Naming standard | `docs/naming_standard.md` |
| Register field guide | `docs/data_register_guide.md` |
| Manual route (no Claude) | `docs/manual_import_qgis_db_manager.md` |
| The eleven-step guide, in full | `reference/new_layer_ingestion_guide.md` |
| Data register | `P:\0_Practice\10_Data management resources\04_Spreadsheets\DI\uk_baseline_data_register.xlsx` |
