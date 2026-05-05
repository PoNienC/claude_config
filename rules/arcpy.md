---
globs: arcpy/**/*.py, arcpy/**/*.pyt
---

# ArcPy-specific rules

Loaded only when working inside `arcpy/`.

## Environment
- Target ArcGIS Pro 3.x. No code that assumes ArcMap or `.mxd`.
- `arcpy.env.workspace` set explicitly at function level — never rely on session state.
- `arcpy.env.overwriteOutput = True` only when the function documents that side effect.

## Cursors
- Always use `with arcpy.da.SearchCursor(...) as cur:` form.
- Never nest a write cursor inside a search cursor on the same feature class.

## Reprojection
- Use `arcpy.management.Project`, never `arcpy.Project_management` (legacy form).
- Always pass an explicit transformation method when reprojecting between SANSRS, UTM Zone 38N, and WGS84.

## Toolboxes (`.pyt`)
- One tool per class.
- `getParameterInfo` must list parameters in user-facing order, not implementation order.
- Validate inputs in `updateParameters`, not in `execute`.

## Output paths
- Default outputs to `arcpy.env.scratchGDB`, never `in_memory` for anything > 100 MB.

## Licensing
- Flag any tool that requires Spatial Analyst, 3D Analyst, or Network Analyst extensions in the docstring. Failed checkouts are a common runtime error.
