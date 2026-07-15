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
        # PyInstaller coloca los datos (runtime/) en sys._MEIPASS: en onedir 6.x
        # es la subcarpeta _internal/ junto al exe; en onefile, el dir temporal.
        meipass = getattr(sys, "_MEIPASS", None)
        base = Path(meipass) if meipass else Path(sys.executable).parent
        return base / "runtime" / "bin" / "java.exe"
    return Path("java")  # dev: Java del sistema en el PATH
