# Source fidelity and ingestion discipline

> Relocated verbatim from ~/.claude/CLAUDE.md on 4 July 2026 (backup:
> ~/.claude/backup_20260704/CLAUDE.md). READ THIS BEFORE any task that
> imports, ingests, or copies an external dataset (CSV, GPKG, XLSX,
> shapefile, Parquet, raster, geodatabase, API response — anything)
> into a database, file store, or other persistent destination.
> SQL-specific comment layout: ~/.claude/rules/sql.md.

Established 2026-05-26 during the VOA NDR 2023 load. In that session the
agent (a) labelled DB columns "biz_floorspace" while the data was
actually property counts, (b) invented a `median_floorspace_*` column
from a misread of source documentation, and (c) carried forward an
empty `unitary_authority` column copied from a pre-existing table
rather than the source CSV. None of those columns were traceable to the
publisher's documentation. The user pays the cost of any such invention
— in rebuilt tables, misled downstream analyses, or eroded trust in the
catalogue.

## Rule 1 — Never invent fields, units, or semantics

If the source doesn't document something, you don't know it. Empirical
evidence (sum-matches, code-counts, suggestive filenames) is a *signal*,
not a substitute for the publisher's own documentation.

- **No invented columns.** Every column in the destination must trace to
  either (a) a source field copied as-is, (b) a clearly-labelled
  synthetic surrogate (e.g. `fid serial PRIMARY KEY`), (c) a geometry
  joined from an explicitly-named boundary table, or (d) a derivation
  the user has approved by name.
- **No inferred sector / category labels.** If the source says
  `table_FS_OA2`, you cannot label it "Retail" until the publisher's own
  documentation says so. Quote the source line. If you cannot find the
  line, name the column after the source identifier and leave the human
  label to the user.
- **No guessed units.** "Floorspace" without a unit annotation is
  unknown floorspace, not "probably m²". Find the publisher's unit
  statement or ask.
- **No guessed vintages.** Don't write `lsoa21cd` if the source column
  is just `ons_code` — propose the rename to the user with the
  count-based evidence for the vintage and wait for sign-off.
- **No copying columns from pre-existing tables** in the same schema
  "to match the pattern". Each new column has to justify itself against
  the source, not against another table that may itself have been wrong.

## Rule 2 — No modification or calculation without prior approval

Any of these is a modification and needs explicit user permission
BEFORE it happens — not "let me do it and check":

- Coercing NULL to 0, or 0 to NULL (suppression handling)
- Multiplying / dividing to change units
- Computed columns (area, length, density, ratios, means, medians)
- Filtering rows (e.g. England-only, year > X, dropping suppressed)
- Spatial joins that add attribute fields from another layer
- Renaming columns to a different semantic name (case-only changes like
  `LSOA21CD` → `lsoa21cd` are fine; `ons_code` → `lsoa21cd` is a
  semantic rename and needs sign-off)
- Combining multiple source files into one destination row
- Dropping source columns entirely from the destination

Propose the modification in writing with the rationale, get an explicit
yes, then do it.

## Rule 3 — Required ingestion brief before any load

Before writing the `CREATE TABLE`, `ogr2ogr`, `COPY`, or `INSERT` that
touches the destination, post a brief showing:

1. **Source inventory.** For each source file: filename, every column
   name as published, data type, row count, and the publisher's
   documented meaning of each field. Quote, don't paraphrase. If a field
   has no published definition, mark it `[UNDOCUMENTED]` and carry it
   forward by its source name only.
2. **Destination schema.** The full proposed `CREATE TABLE` with every
   column. Mark each column's origin as one of:
   - `[source]` — direct copy; name the source field
   - `[boundary]` — geometry / attribute from a named boundary table
   - `[synthetic]` — generated surrogate, e.g. `fid serial`
   - `[derived — needs approval]` — describe the derivation rule
3. **Open questions.** Units, vintages, sector labels, suppression
   conventions, and anything else the source did not state. Flag what
   you would need to ask the user about or inspect empirically before
   proceeding.

No destination writes happen until the user signs off on the brief.

## Rule 4 — When in doubt, ask

A one-turn clarification is cheap. A rebuilt table is not. If the source
documentation is ambiguous, ask the user with the specific ambiguous
text quoted — do not pick the most plausible interpretation and proceed.

## Rule 5 — Every ingested dataset gets structured metadata comments

Before a load is considered complete, every persistent destination —
SQL table, GeoPackage layer, parquet file, JSON catalogue entry,
whatever the target format supports — MUST carry source-faithful
metadata. A downstream reader should be able to understand the table
without needing to ask Claude or the user.

**Required on every table / layer / collection:**

1. **What it is** — one-line description plus the grain (row = ?).
2. **Full name of any acronym on first use** — write "Valuation Office
   Agency (VOA)" first, then "VOA" is fine. No bare acronyms in
   metadata.
3. **Source organisation, publication date, source file name or
   endpoint** — the canonical reference the dataset came from.
4. **URL to the publisher's documentation page** where definitions
   live. Future readers click through; this is the source-of-truth link.
5. **Quoted definitions** of the core concepts — taken directly from the
   publisher's own documentation, wrapped in double-quotes, with a short
   attribution (e.g. `(gov.uk background-information page)`). The
   double-quote marks themselves signal source-faithful copy — do not
   add any explicit marker about quote fidelity; the quotes already say
   that. Never paraphrase, never summarise.
6. **Filter / scope** if the destination is a subset of source.
7. **Load timestamp** (ISO 8601, UTC).

**Required on every field / column / attribute:**

- **Value columns**: state the UNIT, taken word-for-word from the
  publisher's documentation and wrapped in double-quotes. One line, e.g.
  `Unit: "total floorspace (thousand metres squared)"`.
- **Identifier columns**: name the source field, e.g.
  `` Source field `ons_code` ``. One line.
- **Synthetic surrogates** (`fid serial` etc.): no comment needed.
- **Boundary- or join-derived columns** (e.g. `geom`): cite the source
  table, e.g. `Geometry from uk_baseline.adm_ons_lsoa_boundary_2021`.
- **Derived / calculated columns** (only when the user has approved the
  derivation per Rule 2): describe the derivation rule and the source
  columns it draws from.

**Permanent local audit copy:** when direct quotes from a third-party
page are baked into metadata, also save those quotes — with URL and
capture date — to a `reference/source_definitions.md` or equivalent in
the same project. Publisher pages move and edit; local audit copies
survive.

If any of the above is unknown, the load is not complete. Either find it
in the source documentation, or ask the user. Never invent or
paraphrase.

**Layout**: SQL tables and views use the sectioned template defined in
`~/.claude/rules/sql.md § "COMMENT ON TABLE template"` — one-line
description on top, then uppercase section headers (`SOURCE`,
`DOCUMENTATION`, `DEFINITIONS`, `SCOPE`, `CRS`, `LICENCE`, plus optional
`DATA QUALITY CAVEATS`, `ENRICHMENT`, `UPDATE REQUIRED`,
`NOT IN THIS DATASET`, `DERIVED FROM`, `LOADED INTO uk_baseline`).
Non-SQL destinations (GeoPackage, parquet, JSON) carry the same content
in the target format's native metadata fields.

## Banned wording in COMMENTs (added 2026-05-28)

Forbidden in `COMMENT ON TABLE` / `COMMENT ON COLUMN` text. Full
enforcement spec in `~/.claude/rules/sql.md § "Banned wording"`:

- **`vintage`** — any form. State the date directly or use "release" /
  "edition" / "boundary". `Data vintage X` → `Loaded by [importer],
  [date].` `LSOA 2011 vintage` → `LSOA 2011 boundary`.
- **`(accessed YYYY-MM-DD)`** in any section header or body — drop it.
  The double-quotes around publisher text already signal source-faithful
  copy.
- **`at audit time`** / **`verified at audit time`** / **`not recorded
  at audit time`** — never appear in a comment. Say facts, or ASK the
  user. Don't ship a placeholder hedge.
- **Unused acronym parentheticals** (e.g. `(GIAS)`) — only expand an
  acronym in parentheses if downstream readers actually use it.
- **SQL syntax of any kind** (added 2026-05-29) — comments describe WHAT
  the data is, never HOW to query or compute it. No `COUNT(DISTINCT …)`
  / `GROUP BY` / `WHERE` query instructions AND no derivation
  expressions — write those in plain English: `ST_Area(geom)/10000` →
  "area in hectares, computed at load from the geometry". Backtick
  `field_name` citations of source fields stay (mandated identifier
  format — not SQL). Full spec: `~/.claude/rules/sql.md § "No SQL in
  comments"`.

## DEFINITIONS — firm definitional tone (added 2026-05-29)

A `DEFINITIONS` bullet states what the thing IS, in glossary tone — not
a mission statement, product introduction, or explanation. Drop
first-person / organisational framing ("our", "we", "we work with…"),
introductions and date-as-lead-in ("Established in 1984, our
'Register…'" → "the Register (established 1984) identifies…"), and
explanatory connectives ("because", "in other words", "which helps…" →
"to…"). Prefer a verbatim publisher sentence that is already
definitional (double-quoted); if the publisher's nearest wording is
mission/intro/explanatory, select a more definitional sentence or state
it plainly and attribute it WITHOUT double-quotes (normalised, not
verbatim). Never alter a fact inside double-quotes. Full spec:
`~/.claude/rules/sql.md § "DEFINITIONS — firm definitional tone"`.

## Date format inside COMMENTs (added 2026-05-28)

Use `D Month YYYY`. Never ship ISO timestamps like
`2026-05-13T14:59:17+00:00` in a COMMENT — drop the time component and
humanise the date.

- Good: `Loaded by PNC, 27 May 2026.`
- Bad : `Loaded by PNC, 2026-05-27T14:59:17+00:00.`
- Bad : `Data vintage May 2026.` (banned word; correct form:
  `Loaded by PNC, May 2026.`)

## LOADED INTO uk_baseline block — include or drop

- **Include** when the PP Data Register's `date_imported` column carries
  a real date. Populate as `Loaded by [data_importer], [D Month YYYY].`
- **Drop** the block entirely when `date_imported` is `N/A` / blank /
  `unknow(n)`. Don't write "Load date not recorded" — that's a hedge,
  not a fact.

## uk_baseline catalogue must be refreshed after any layer change

The `uk_baseline` schema is published as a colleague-facing catalogue in
three forms — an Excel workbook and a standalone HTML on the practice
share, plus a live GitHub Pages site (`Prior-Partners/PP_uk_baseline`,
https://prior-partners.github.io/PP_uk_baseline/). **Any time a layer is
loaded, renamed, re-commented, or dropped in `uk_baseline`, the task is
not complete until all three are regenerated and republished.** Full
procedure and exact commands:
`~/.claude/rules/sql.md § "Catalogue refresh (uk_baseline)"`.
Established 2026-06-01.
