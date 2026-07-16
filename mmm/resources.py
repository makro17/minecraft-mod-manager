"""Localiza assets del repo tanto en dev como empaquetado con PyInstaller."""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(rel: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / rel
    # dev: raíz del proyecto (padre de mmm/)
    return Path(__file__).resolve().parent.parent / rel
