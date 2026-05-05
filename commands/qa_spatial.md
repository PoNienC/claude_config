---
description: Run spatial QA across the repo: layer naming, field length, CRS consistency, OBJECTID joins. Reports issues without modifying anything.
allowed-tools: Read, Grep, Glob, Bash(psql:*)
---

# /qa-spatial

Audit all spatial layers and code in scope for compliance with firm conventions. Read-only.

## Checks

### 1. Layer/table naming
Grep `sql/`, `python/`, `arcpy/`, `pyqgis/` for table names. Flag any that:
- Don't start with one of the 12 theme codes (`ADM_`, `DEM_`, `HSG_`, `HTH_`, `ENV_`, `TRN_`, `ECN_`, `EDU_`, `COM_`, `HER_`, `INF_`, `LND_`)
- Use hyphens, spaces, or mixed case after the theme code
- Lack a date suffix where the source dataset is versioned

### 2. Field length
Scan SQL DDL for `CREATE TABLE` and column definitions. Flag any field name > 30 characters. Suggest abbreviations for each.

### 3. OBJECTID joins
Grep for `OBJECTID` in JOIN clauses or foreign-key constraints. Every match is a flag — joins must use domain keys.

### 4. CRS consistency
- For each spatial table, check `Find_SRID` or `geometry_columns` for the EPSG.
- Flag any table without a declared SRID.
- Flag mixed SRIDs across tables that are joined.

### 5. Hard-coded paths
Grep for absolute paths (`/Users/`, `/home/`, `C:\\`, `Z:\\`). All paths should be relative or environment-driven.

### 6. WGS84 assumptions
Flag any reprojection to EPSG:4326 used as input to analytical (not display) code. WGS84 is for display only at this firm.

### 7. OWL boundary check
Grep `python/` for any code that writes instance data to `.owl` files. The hybrid pattern forbids this — only schema lives in OWL.

## Output format

```
# QA Report — <date>

## Summary
- Layers audited: N
- Critical issues: X
- Warnings: Y

## Critical
- file:line — issue — remediation

## Warnings
- file:line — issue — remediation

## OK
- One-line summary of what passed
```

End with a single sentence stating whether the repo is ready for a Saudi/GEOSA submission (if applicable) or merely for internal use. Never approve — only flag.
