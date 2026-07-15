"""Localiza el ejecutable de Java (JRE bundleado en producción, override en dev)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def java_exe() -> Path:
    override = os.environ.get("MMM_JAVA")
    if override:
        return Path(override)
    if is_frozen():
        return Path(sys.executable).parent / "runtime" / "bin" / "java.exe"
    return Path("java")  # dev: Java del sistema en el PATH
