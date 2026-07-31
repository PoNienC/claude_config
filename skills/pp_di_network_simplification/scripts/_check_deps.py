"""Quick dependency check for the network-simplification engine.

Prints `OK` if every required package imports, otherwise
`NEED_INSTALL: <first-missing-module>` and exits non-zero. Used by the
pp_di_network_simplification skill so the permission allowlist can stay narrow
(a dedicated script rather than an open-ended `python -c ...`).
"""
from __future__ import annotations

import importlib
import sys

REQUIRED = ["osmnx", "neatnet", "geopandas", "shapely", "pandas", "numpy"]

missing = []
for mod in REQUIRED:
    try:
        importlib.import_module(mod)
    except Exception:  # noqa: BLE001 - any import failure means "install needed"
        missing.append(mod)

if missing:
    print(f"NEED_INSTALL: {missing[0]}")
    sys.exit(1)

print("OK")
