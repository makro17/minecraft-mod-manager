"""Utilidades de subprocess: evitar el parpadeo de una consola en Windows.

La app se empaqueta sin consola (PyInstaller --noconsole); al invocar CLIs
externos (zerotier-cli.bat → cmd.exe, el instalador de NeoForge → java.exe)
Windows abre y cierra una ventana de consola que parpadea. CREATE_NO_WINDOW
la suprime (no afecta a ventanas GUI del proceso lanzado).
"""
from __future__ import annotations

import subprocess
import sys


def no_window_kwargs() -> dict:
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}
