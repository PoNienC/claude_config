"""Quick dependency + native-core check for the space syntax engine.

Spatial input/output: none - pure import / environment check, CRS-agnostic.
Data layer: infrastructure.

Prints ``OK`` when every required Python package imports AND the vendored
pstalgo native core (``pstalgo64.dll``) loads; otherwise prints
``NEED_INSTALL: <module>`` (a missing pip package) or
``PSTALGO_LOAD_FAILED: <reason>`` (the native core could not be loaded) and
exits non-zero. Used by the pp_space_syntax_analysis skill so the permission
allowlist can stay narrow (a dedicated script rather than an open-ended
``python -c ...``).

Works unchanged from the repository root and from a self-contained skill
install: both place ``vendor/`` one level above this script's parent
(``<root>/scripts/_check_deps.py`` -> ``<root>/vendor/...``).
"""
from __future__ import annotations

import importlib
import sys
import warnings
from pathlib import Path

REQUIRED = ["geopandas", "pyogrio", "shapely", "pyproj", "pandas", "numpy"]


def main() -> int:
    for mod in REQUIRED:
        try:
            importlib.import_module(mod)
        except Exception:  # noqa: BLE001 - any import failure means "install needed"
            print(f"NEED_INSTALL: {mod}")
            return 1

    # Native core: replicate the loader's relative path so this check matches
    # exactly what the analysis scripts do at run time.
    pstalgo_python = (
        Path(__file__).resolve().parents[1]
        / "vendor" / "pstqgis_extracted" / "pst" / "pstalgo" / "python"
    )
    if not pstalgo_python.is_dir():
        print(f"PSTALGO_LOAD_FAILED: vendored pstalgo not found at {pstalgo_python}")
        return 1
    sys.path.insert(0, str(pstalgo_python))
    try:
        with warnings.catch_warnings():
            # Vendored PST emits a harmless SyntaxWarning (invalid escape
            # sequence) on first compile under Python 3.12+; it is not ours
            # to fix, so silence it at the import site.
            warnings.simplefilter("ignore")
            import pstalgo  # noqa: PLC0415 - deferred import after path shim
    except Exception as exc:  # noqa: BLE001 - any load failure is reportable
        print(f"PSTALGO_LOAD_FAILED: {exc}")
        return 1
    _ = pstalgo.__file__  # touch the module so linters see it used

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
