---
name: postgis-layer-creation
description: Create or import a new spatial layer into PostGIS using the firm's 12-theme taxonomy, 30-character field limit, and CRS validation rules. Use whenever the user asks to add, ingest, register, or create a new layer, table, feature class, or dataset in PostGIS or PostgreSQL.
---

# PostGIS layer creation

You are creating a new spatial layer. Follow the firm's standards exactly.

## 1. Confirm the theme code
Before any DDL, ask the user which of the 12 theme codes applies:
`ADM, DEM, HSG, HTH, ENV, TRN, ECN, EDU, COM, HER, INF, LND`

If the user gives a layer description without a code, propose the best match and ask them to confirm. Never invent new codes.

## 2. Build the layer name
Pattern: `<THEME>_<source>_<dataset>_<date>`

- Theme code uppercase (e.g. `ENV`)
- Everything after the theme is lowercase
- Underscores only; no hyphens or spaces
- Source is a short abbreviation (`ons`, `os`, `naturalengland`, `historicengland`, `geosa`)
- Date as `<mon><year>` lowercase (e.g. `apr2025`) when known, otherwise omit

Good: `ENV_naturalengland_sssi_apr2025`
Bad: `env-natural-england-sssi-2025` (hyphens, mixed case)

## 3. Validate field names
- Every field name must be **≤ 30 characters**.
- Snake_case, lowercase.
- No joins or relations on `OBJECTID` — surface a domain key.
- Use coded-value domains where the field has a vocabulary.
- For Saudi/GEOSA submissions, English primary with Arabic alias documented in the metadata.

If the user proposes a longer field name, suggest a shorter alternative and explain why.

## 4. CRS handling
- Confirm the source CRS by EPSG code.
- Confirm the target CRS (PostGIS canonical store): usually EPSG:27700 for UK projects, EPSG:32638 for UTM Zone 38N / Saudi unless SANSRS is mandated.
- If client brief is unclear about SANSRS vs UTM 38N, **stop and ask** — do not reproject silently.
- Never assume WGS84 geographic (EPSG:4326) is acceptable for analytical layers.

## 5. DDL template

```sql
CREATE TABLE IF NOT EXISTS public.{LAYER_NAME} (
    id            BIGSERIAL PRIMARY KEY,
    -- domain key (NOT OBJECTID) for joins
    source_id     TEXT UNIQUE,
    -- attributes here, each ≤ 30 chars, snake_case
    geom          GEOMETRY({GEOM_TYPE}, {EPSG}) NOT NULL,
    metadata      JSONB,
    ingested_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS {LAYER_NAME}_geom_idx
    ON public.{LAYER_NAME} USING GIST (geom);

COMMENT ON TABLE public.{LAYER_NAME} IS
    '{ONE_LINE_DESCRIPTION} | source={SOURCE} | epsg={EPSG} | ingested={DATE}';
```

## 6. Output
Produce:
1. The proposed layer name (and reasoning if non-obvious).
2. A field-by-field validation table flagging anything over 30 chars or using `OBJECTID`.
3. The DDL (parameters filled in).
4. A one-line ingestion command (e.g. `ogr2ogr` or `shp2pgsql`) using the confirmed CRS.

Stop and confirm with the user before running anything that mutates the database.
