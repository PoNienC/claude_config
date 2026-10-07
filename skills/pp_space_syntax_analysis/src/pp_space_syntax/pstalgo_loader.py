"""Import shim for the vendored pstalgo package (PST 3.3.2).

Spatial input/output: none — pure import logic, CRS-agnostic.
Data layer: infrastructure.

pstalgo lives unmodified under ``vendor/pstqgis_extracted`` and loads its
native core (``pstalgo64.dll`` on Windows x64) via ctypes relative to its
own package location, so no installation step is required.
"""
from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
PSTALGO_PYTHON_DIR = (
    REPO_ROOT / "vendor" / "pstqgis_extracted" / "pst" / "pstalgo" / "python"
)


def import_pstalgo() -> ModuleType:
    """Import the vendored pstalgo package, adding it to sys.path if needed."""
    if not PSTALGO_PYTHON_DIR.is_dir():
        raise FileNotFoundError(
            f"Vendored pstalgo not found at {PSTALGO_PYTHON_DIR}. "
            "Has vendor/pstqgis_extracted been removed?"
        )
    path_str = str(PSTALGO_PYTHON_DIR)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
    with warnings.catch_warnings():
        # Vendored PST emits a harmless SyntaxWarning (invalid escape sequence)
        # on first compile under Python 3.12+; silence it at the import site.
        warnings.simplefilter("ignore")
        import pstalgo  # noqa: PLC0415 — deliberate deferred import after path shim

    logger.debug("pstalgo imported from %s", pstalgo.__file__)
    return pstalgo
