# Vendored third-party code

## PST (Place Syntax Tool) 3.3.2

- Source release: https://github.com/SMoG-Chalmers/PST/releases/tag/v3.3.2
- Downloaded file: `pstqgis_3.3.2_2026-05-13.zip` (11 June 2026)
- Extracted unmodified to `pstqgis_extracted/`
- Developers: KTH School of Architecture, Chalmers School of
  Architecture (SMoG) and Spacescape AB
- Licence: GNU Lesser General Public License v3 (or later)
- Source code: https://github.com/SMoG-Chalmers/PST

The parts used by this repository are:

- `pstqgis_extracted/pst/pstalgo/bin/pstalgo64.dll` — the compiled
  analysis core (Windows x64)
- `pstqgis_extracted/pst/pstalgo/python/pstalgo/` — the Python ctypes
  bindings
- `pstqgis_extracted/pst/analyses/` — read as reference for replicating
  the QGIS plugin behaviour (column naming, option mapping); not
  imported at runtime

No files have been modified. The binaries are redistributed here under
the terms of the LGPL v3; the corresponding source is available at the
repository linked above.
