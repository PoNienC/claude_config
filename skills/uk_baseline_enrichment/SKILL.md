---
name: uk_baseline_enrichment
description: Add the standard geography columns to one existing uk_baseline layer — MSOA 2021 code and names, the House of Commons Library readable name, Local Authority District 2022 and 2025, county or unitary authority 2025, and the Spatial Development Strategy area and group. Use this whenever someone wants to enrich, tag, or add geography, MSOA, LSOA, LAD, county, CTYUA or SDS columns to a layer that is already loaded; to backfill lad25cd on an older district edition; to split a polygon or line layer by MSOA; or to check which enrichment route a layer would take. Works one layer at a time, in the staging schema uk_new, promoting back only after an audit passes. A split runs in staging and produces a review report for the data manager to sign off before promotion. Not for loading a new layer (that is uk_baseline_new_layer). It never changes, recomputes or apportions a numeric value, and never aggregates to a coarser geography.
---

# uk_baseline_enrichment — geography columns for one existing layer

## Read this first

The method is `docs/enrichment_methodology.md` — which boundaries exist, which
lookups bridge which years and levels, which bridges are exact and which are
approximations, and what a NULL is allowed to mean. **Read it before the first
enrichment of a session.** This skill is the runnable form of it; where the two
disagree, stop and say so.

## What this skill will and will not do

**No numeric value is ever changed.** Nothing is rolled up to a coarser
geography and nothing is apportioned down to a finer one. Enrichment adds keys;
it never changes what a number means. That is the whole of the "no aggregation
or disaggregation" rule, and it is absolute.

**Splitting is in scope, but gated.** Enriching a polygon or line that crosses
MSOA boundaries faithfully means one row per feature × MSOA piece. The split
itself is geometry work and is allowed. What it does to *numbers* is the danger:
every attribute value is copied onto every piece, so a measure that was true of
the whole feature is now repeated N times.

So the split runs **in `uk_new` only**, produces a **review report naming every
numeric measure that stops being trustworthy**, and waits. The data manager
signs off and it is promoted, or rejects it and the staging table is rebuilt.
Nothing published changes in between. Values are copied, never recomputed or
apportioned — recomputing even an area column is a new numeric value and needs
explicit approval.

**No new layers.** Loading is `uk_baseline_new_layer`.

**Still a hard stop:** an MSOA-2011 or district-level aggregate, where a 2021
MSOA name would be finer than the data. Reporting that and stopping is a
**correct outcome**. Say so plainly rather than apologising for it — the
alternative is a silently wrong table.

## One layer at a time

Never batch. Concurrent spatial writes contend on IO; a six-minute job once took
twenty-eight minutes running alongside another. If a second layer is requested
while one is in flight, finish or park the first.

## The shape of the flow

```
1  plan        read-only: which route, what would change, is it in scope
2  confirm     the operator agrees the route and the columns  <-- STOP
3  stage       copy the published layer into uk_new
              (split route: build the split into uk_new instead)
4  enrich      run the route against the staging copy only
5  verify      row count, coverage, NULL reasons, independent audit
6  QGIS check  the operator looks at it and signs        <-- STOP
6b split report + the data manager's sign-off           <-- STOP (split only)
7  promote     swap into uk_baseline, keeping a backup   <-- STOP
8  close       register, catalogue, report
```

**Nothing touches `uk_baseline` until step 7**, and step 7 happens only after
the audit passes and a person has looked at the layer.

## Hard stops

| Never | Who decides | When |
|---|---|---|
| Choose the route without the operator agreeing it | Operator | Step 2 — confirm or amend, and wait |
| Run any write without showing the dry run first | Operator | Every write |
| Promote before the audit passes and the QGIS check is signed | Operator | Step 7 |
| Promote a **split** without the data manager's sign-off on the report | Data manager | Step 6b |
| Change, recompute or apportion any numeric value | Data manager | Never without explicit approval |
| Aggregate to a coarser geography | — | Never; report and stop |
| Enrich a second layer while one is in flight | — | One at a time |
| Drop the `__preswap` backup | Data manager | After the layer passes QGIS QA |
| Invent a key, or substitute a boundary edition we do not hold | — | Never |

## Step 1 — plan

```
python scripts/enrich/enrichment_plan.py <table>
```

Read-only. Reports the row count, geometry and CRS, which keys the layer already
carries, which of the eleven columns it already has, which would be added, and
the route. Exit 0 means in scope; exit 2 means out of scope and nothing should
be written.

The routes, first match wins:

| Route | When | Row change |
|---|---|---|
| `attr_join` | Already has `msoa21cd`, or a clean 2021 `lsoa21cd` / `oa21cd` | None |
| `tag_points` | Point layer — point-in-MSOA and point-in-district | None |
| `bestfit_2011` | Keyed on LSOA 2011; area-dominant best fit, **approximate** | None |
| `backfill_lad25` | Older district edition; trace 2022 → 2025, exact | None |
| `split` | Polygon or line crossing MSOAs | **Changes — gated on sign-off** |
| `STOP` | MSOA-2011 or district-level aggregate | No valid route |

An aggregate source can still reach county and SDS through its district key,
even when the MSOA columns are impossible. Say so rather than reporting a flat
failure.

## Step 2 — get the route agreed

**Present the plan and wait.** Announcing a route and continuing in the same
reply is not asking. Offer:

- **Confirm** — proceed with this route and these columns.
- **Amend** — a different route or a subset of columns. Re-plan and ask again.
- **Not sure** — explain the trade-off and ask again. Never resolve an unsure
  into a yes.

Where the route is `bestfit_2011`, say explicitly that the result is
**approximate by construction** and will carry a cross-edition caveat. The
operator should agree to that, not discover it later.

## Step 3 — stage

Copy the published layer into `uk_new`. Work happens on the copy; the live table
is untouched until step 7.

```
python scripts/enrich/stage.py <table>            # dry run
python scripts/enrich/stage.py <table> --apply    # write
```

**Do not hand-write the `CREATE TABLE AS`.** It copies rows and nothing else —
not the primary key, not the indexes, and **not the table or column comments**.
The first two have always been rebuilt by hand; the comments were not, so a
staging copy started undocumented, the enrichment scripts appended their
sections to an empty string, and promoting it swapped a fully documented layer
for one carrying only the enrichment notes. Nothing in the flow caught it,
because no check looked at comments.

`stage.py` does the whole step: copies the rows, rebuilds the floor (the primary
key — a fresh identity `gid` if no single-column key exists — and one GIST on
the geometry), carries every table and column comment across, then verifies row
count, CRS, floor and comment parity against the source. It refuses to overwrite
an existing staging table, and only ever reads `uk_baseline`.

## Step 4 — enrich the staging copy

Run the agreed route with `--schema uk_new`. Dry run first, show it, wait, then
apply.

```
python scripts/enrich/enrich.py       <table> --schema uk_new             # preview
python scripts/enrich/enrich.py       <table> --schema uk_new --apply     # attr_join / tag_points
python scripts/enrich/enrich_sds.py   <table> --schema uk_new --report    # preview
python scripts/enrich/enrich_sds.py   <table> --schema uk_new --apply     # county + SDS
python scripts/enrich/enrich_sds.py   <table> --schema uk_new --apply --backfill-lad25
```

Both take a preview flag and a write flag, and **without the write flag they
change nothing** — that is the dry run to show the operator. `enrich.py` picks
`lsoa21`, `oa21` or `points` itself; `--mode` overrides it. It refuses
`--schema uk_baseline` outright.

Read the preview before applying. `unmatched key` is the number that matters on
an attribute join: a row whose key matches no boundary we hold. It should be 0,
and anything else is a stop, not a caveat.

Backbone and lookups are read from `uk_baseline` and `uk` — reading published
data is fine; writing to it is not.

## Step 5 — verify

All of these, against the staging copy:

- **Row count unchanged.** Every in-scope route adds columns only. A changed
  count means something split, and that is a stop.
- **Index floor** still exactly one primary key and one GIST(geom).
- **Comments still present.** The staging copy must carry the published layer's
  table comment and every column comment it had, on top of whatever the
  enrichment scripts appended. A staging copy documented only by the enrichment
  sections has lost the source, licence and CRS blocks, and promoting it would
  strip them from a published layer. `stage.py` verifies this at step 3; check
  it again here, because a rebuild between the two would lose them silently.
- **`msoa21hclnm` agrees with the backbone** — zero rows differing.
- **County and SDS single-valued per district** — a district resolving to two
  counties means the join is wrong.
- **NULLs explained**: `python scripts/enrich/null_reasons.py --report <table>
  --schema uk_new`. Every NULL must be England-and-Wales-boundary, Scotland or
  Northern Ireland, offshore, or no-coordinates. **A recoverable NULL — a row
  sitting inside an England or Wales district with no key — is a fault**, not a
  caveat.
- **Independent audit**, scoped to the staging copy — it re-derives the county
  and SDS chain rather than trusting the write:

  ```
  python scripts/enrich/audit_sds.py <table> --schema uk_new
  ```

  Pass the table and the schema. With no arguments it sweeps every enriched
  table in `uk_baseline` instead, which takes minutes and tells you nothing
  about the layer in hand.

Write the coverage counts and the NULL reasons into the table comment's
`DATA QUALITY CAVEATS`, and record the route, the lookup and the edition under
`ENRICHMENT`. The comment carries the method, not just the result.

## Step 3b / 6b — the split route

When the plan says `split`, steps 3 and 4 are replaced by one command, and a
second sign-off is added before step 7.

```
python scripts/enrich/split.py <table>                       # dry run
python scripts/enrich/split.py <table> --apply \
    --report reports/<table>_split_<yymmdd>.md
```

The dry run writes nothing and reports the row multiplication and, crucially,
**every numeric measure that the split will break**. Show it and wait, exactly
as at step 2. `--apply` builds `uk_new.<table>` — the published layer is only
ever read — rebuilds the index floor, and checks that geometry is conserved at
100.000%. Anything else is a stop.

Then run `enrich_sds.py --schema uk_new` as usual for the county and SDS
columns; the split has already filled the seven MSOA and LAD columns.

**Take the report to the data manager and wait.** It states what the split did,
what carries no MSOA and why, and each numeric measure with its sum before and
after. Two outcomes, and both are fine:

- **Sign off** → continue to step 7 and promote, keeping the `__preswap` backup.
- **Reject** → drop the staging table and rebuild. Nothing published changed, so
  a rejection costs only the staging time.

Watch for the case that catches people out: a column computed from the geometry
(`area_ha`, `length_m`, `shape_area`). After a split each piece still carries
the **whole feature's** value, so every row is wrong rather than merely
non-summable — on one real layer the total went from 6.7 million hectares to
94.8 million, about four times the land area of the United Kingdom. Do not
quietly recompute it: that is a new numeric value and needs the data manager's
explicit approval, recorded in the column comment.

## Step 6 — the QGIS check

The operator connects QGIS to `uk_new`, symbolises by a new key, and looks at
it: do the seams follow real boundaries, does a known place carry the right
name, are the NULLs where the coverage rules say they should be. They sign it.
**An unsigned check blocks the promotion.**

## Step 7 — promote

Only after the audit passes and the check is signed — and, for a split, after
the data manager has signed off the report. Dry-run the SQL, show it, wait for a
yes, then:

```sql
ALTER TABLE uk_baseline.<table> RENAME TO <backup_name>;
ALTER TABLE uk_baseline.<backup_name> SET SCHEMA uk;
ALTER TABLE uk_new.<table> SET SCHEMA uk_baseline;
```

**The backup lands in `uk`, not `uk_baseline`.** All 57 existing backups are in
`uk`, and one left in `uk_baseline` would be picked up by the catalogue and the
Dashboard as though it were a published layer.

**Check the backup name fits in 63 characters** before renaming. PostgreSQL
truncates silently at that limit, which has already cost the date suffix on nine
existing backups — and two backups of the same long-named layer would collide.
Where `<table>__preswap_<mmmdd>` is too long, shorten the base, never the date:

```sql
SELECT length('<table>__preswap_<mmmdd>');   -- must be <= 63
```

Then **re-verify the floor on the promoted table** and confirm the row count
matches what was staged. For a split the row count is *expected* to differ from
the pre-split published table — it must match the **staged** count, not the old
one. The `__preswap` backup stays until the layer has passed QGIS QA and the
data manager releases it; it is the only undo. `scripts/enrich/backups.py`
lists what is held.

## Step 8 — close the loop

- **The data register**: the column list has changed, so the row is updated.
  **On the split route the row count has changed too**, so update that as well —
  the published figure is now wrong, and it is the number colleagues quote.
- **The catalogue**: regenerate and republish. A layer change is unfinished
  until it ships — and publication is the data manager's call.
- **Report** what was done, which route, the coverage counts, and what remains
  NULL and why.

**No pull request is opened here, or anywhere in this skill.** Enrichment is
gated by the stops above — the route agreed, the QGIS check signed, the promote
approved, and for a split the report signed off — not by a merge. Say so plainly
when the operator asks what the data manager has to review: for a split it is
`reports/<table>_split_<yymmdd>.md`, and for every other route it is the staging
copy and the verification output, in the session. Do not tell them to wait for a
PR that will never appear.

## Refuse loudly when

- Asked to change, recompute or apportion any numeric value without the data
  manager's explicit approval — including "just recompute `area_ha`".
- Asked to aggregate to a coarser geography.
- Asked to promote a split without the data manager's sign-off on the report.
- Asked to enrich straight into `uk_baseline` without staging.
- Asked to promote before the audit passes or the check is signed.
- Geometry conservation on a split is not 100.000% and the suggestion is to
  carry on.
- A recoverable NULL is dismissed as acceptable.
- A best-fit result is described as though it were boundary-true.
- Asked to enrich a second layer while one is in flight.
- The methodology and this skill disagree.

## Files

| What | Where |
|---|---|
| The method, in full | `docs/enrichment_methodology.md` |
| Boundary and lookup reference | `docs/enrichment_methodology.md` §2–3 |
| Route planner (read-only) | `scripts/enrich/enrichment_plan.py` |
| Stage into `uk_new`, floor and comments intact | `scripts/enrich/stage.py` |
| MSOA split into staging + review report | `scripts/enrich/split.py` |
| Attribute join and point tagging | `scripts/enrich/enrich.py` |
| County, SDS, LAD25 backfill | `scripts/enrich/enrich_sds.py` |
| NULL classification | `scripts/enrich/null_reasons.py` |
| Independent audit | `scripts/enrich/audit_sds.py` |
| Connection and tool discovery | `scripts/db.py` |
