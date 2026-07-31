---
globs: pyqgis/**/*.py
---

# PyQGIS-specific rules

Loaded only when working inside `pyqgis/`.

## Initialisation
- Headless scripts must initialise QGIS via `QgsApplication([], False)` and call `initQgis()` before any `Qgs*` import is used.
- Tear down with `app.exitQgis()` in a `finally` block.

## Layer access
- Load layers with `QgsVectorLayer(path, name, "ogr")` — verify `isValid()` immediately and raise on failure.
- Never assume a layer's CRS — read `layer.crs().authid()` and assert.

## Processing algorithms
- Use `processing.run()` with explicit input/output dicts.
- Pass `feedback=QgsProcessingFeedback()` so cancellation works in long jobs.

## Memory
- For large layers, iterate features with `getFeatures(QgsFeatureRequest().setFilterRect(bbox))` rather than loading everything.
- Don't accumulate features in a Python list; write to a sink as you go.

## CRS handling
- Use `QgsCoordinateTransform(src_crs, dst_crs, QgsProject.instance())` and reuse the transform — don't construct one per feature.
