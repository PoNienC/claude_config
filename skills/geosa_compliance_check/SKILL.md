---
name: geosa_compliance_check
description: Pre-flight a GIS dataset against Saudi GEOSA / ADA Digital Data Standards before submission. Use when the user mentions GEOSA, SANSRS, ADA, UTM Zone 38, Saudi submission, Riyadh, Riyadh Development Authority, or asks to verify a deliverable for a Saudi client. Returns a checklist of failures, not a pass/fail verdict.
---

# GEOSA / ADA compliance pre-flight

This skill checks a deliverable against the firm's encoded Saudi standards. It does not approve a submission — only flags issues.

## Checks to run

### 1. Coordinate system
- Confirm CRS in writing from client: SANSRS or UTM Zone 38N (EPSG:32638). These conflict in some briefs.
- Refuse to assume. If unclear, output a question for the user to ask the client.
- Verify all submitted layers share the same CRS.

### 2. Format
- Vector: shapefile (`.shp`) **and** ESRI Geodatabase (`.gdb`) unless the client specifies one.
- Raster: GeoTIFF with embedded CRS.
- No GeoJSON, KML, or GPKG as primary deliverables — those are export-only.

### 3. Field naming
- Every field name ≤ 30 characters.
- English primary, Arabic alias documented in metadata.
- No relations or joins on `OBJECTID`.
- Coded-value domains for any field with a vocabulary.

### 4. Metadata
- ISO 19115-compliant XML for each feature class.
- ISO 19139 XML schema for serialisation.
- Source documentation, temporal coverage, lineage, and quality assessment per ISO 19157.

### 5. Quality thresholds (from GEOSA 2024)
| Layer type | Completeness | Positional accuracy |
|-----------|--------------|---------------------|
| Land Parcels | 85% | 25 cm urban / 1.5 m rural |
| Imagery | 95% | sensor-dependent |
| Buildings | 95% | scale-dependent |
| Transport | 95% | network-appropriate |
| National Address | 95% | 3 m max |

If your dataset doesn't meet the threshold, the submission will be rejected.

### 6. Document naming (ADA convention)
`<number>_<title>_<author>_<version>_<status>.<ext>`
- Status: `inp` (in progress), `fin` (final, unapproved), `app` (approved)
- Author: client-provided initials (e.g. `ada`)
- Example: `01_landuse_zoning_ada_v-3_app.shp`

### 7. MXD / APRX paths
- All paths must be relative.
- For ArcGIS Pro, deliver `.aprx`, not `.mxd` (MXD is legacy).

## Output
A markdown checklist with:
- ✅ for items confirmed correct
- ⚠️ for items needing client clarification (CRS conflict is the most common)
- ❌ for items that will fail submission

Each ❌ includes a one-line remediation step.

Never mark something ✅ on assumption — if a check requires inspecting a file you haven't read, mark it ⚠️ and request access.
