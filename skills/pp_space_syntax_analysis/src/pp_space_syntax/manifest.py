"""Reproducibility manifest writing.

Spatial input/output: none — JSON metadata only, CRS recorded as text.
Data layer: provenance.
"""
from __future__ import annotations

import hashlib
import json
import logging
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import PST_VERSION, __version__
from .pstalgo_loader import PSTALGO_PYTHON_DIR

logger = logging.getLogger(__name__)


def file_sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(path: Path, steps: list[dict], input_files: list[Path]) -> None:
    """Write a JSON manifest capturing inputs, parameters and environment."""
    dll_path = PSTALGO_PYTHON_DIR.parent / "bin" / "pstalgo64.dll"
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tool": {
            "name": "PP_space_syntax_analysis",
            "version": __version__,
            "pst_version": PST_VERSION,
            "pstalgo_dll_sha256": file_sha256(dll_path) if dll_path.is_file() else None,
        },
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "inputs": [
            {
                "path": str(p),
                "sha256": file_sha256(p),
            }
            for p in input_files
            if p is not None and Path(p).is_file()
        ],
        "steps": steps,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    logger.info("Manifest written to %s", path)
