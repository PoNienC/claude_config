---
name: owl-validation
description: Validate PostGIS records against an OWL ontology using the hybrid schema-only pattern. Use when the user asks to validate data against ontology rules, run a reasoner, check axiom compliance, or build a PostGIS-to-OWL bridge. Do NOT use this skill to populate OWL with instance data — that pattern is forbidden by the project architecture.
---

# OWL + PostGIS hybrid validation

The project uses a strict separation: OWL holds schema, PostGIS holds instances, Python bridges them. Never violate this.

## Hard rules
1. **Never persist instance data into the OWL file.** OWL stores only classes, properties, axioms, disjointness rules, and reference individuals. Target file size: 100–300 KB.
2. **Always batch.** Pull PostGIS rows in batches of 10,000–50,000. Create temporary OWL individuals, validate, then discard. Never load all rows at once.
3. **Reasoner is HermiT.** Don't suggest Pellet or Fact++ unless the user explicitly asks.
4. **Hardware assumption: 16 GB RAM, no GPU.** OWL reasoning is CPU-bound and single-threaded. Don't suggest GPU acceleration.

## Validation pattern

```python
from owlready2 import get_ontology, sync_reasoner_hermit
import psycopg2

# Load schema only
onto = get_ontology("file://schemas/gis_urban_planning.owl").load()

with psycopg2.connect(DATABASE_URL) as conn, conn.cursor(name="batch") as cur:
    cur.itersize = 10_000
    cur.execute("SELECT id, source_id, geom_wkt, attrs FROM {LAYER_NAME}")

    for row in cur:
        with onto:
            # Create temp individual, validate, discard
            ind = onto.LandParcel(f"_tmp_{row[0]}")
            # ... map attributes to OWL data properties
            try:
                sync_reasoner_hermit([onto], infer_property_values=False)
                # if we reach here, the row is consistent with axioms
            except Exception as e:
                yield {"id": row[0], "violation": str(e)}
            finally:
                # Critical: destroy the individual to free memory
                destroy_entity(ind)
```

## What to check before running
- The target OWL file is < 1 MB. If it's bigger, instance data has leaked in — stop and investigate.
- Batch size is set. No `LIMIT 0` or unbounded `SELECT`.
- The Python script imports nothing that pins instance data to the ontology graph permanently.

## Output
Produce a validation report with:
- Layer name and theme code
- Total rows validated
- Violations grouped by axiom
- Sample row IDs for the first 5 violations of each type

If the user asks to "save the populated ontology back to disk", refuse and explain the architectural rule.
