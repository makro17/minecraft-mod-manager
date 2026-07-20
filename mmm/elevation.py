"""C4 · elevación bajo demanda.

La app arranca como usuario normal (`asInvoker`): gestionar modpacks no pide
permisos. En Windows, TODAS las operaciones de ZeroTier (info/listnetworks/
join/leave) necesitan administrador, así que cuando hacen falta relanzamos la
propia app elevada (un solo UAC) en vez de exigir permisos en cada arranque.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys

from .jre import is_frozen

SW_SHOWNORMAL = 1


def _shell32():
    """Handle de shell32, aislado para poder mockearlo en los tests."""
    return ctypes.windll.shell32


def is_elevated() -> bool:
    """True si el proceso corre con permisos de administrador."""
    if sys.platform != "win32":
        return False
    try:
        return bool(_shell32().IsUserAnAdmin())
    except Exception:  # noqa: BLE001 — sin shell32 asumimos «sin permisos»
        return False


def relaunch_as_admin() -> bool:
    """Relanza la app elevada. True si el relanzamiento arrancó.

    El llamador debe cerrar esta instancia si devuelve True. Devuelve False si
    el usuario canceló el UAC, si falló, o si estamos en dev/no-Windows (donde
    no hay un .exe que relanzar): en ese caso se avisa al usuario.
    """
    if sys.platform != "win32" or not is_frozen():
        return False
    params = subprocess.list2cmdline(sys.argv[1:]) or None
    try:
        rc = _shell32().ShellExecuteW(None, "runas", sys.executable, params, None, SW_SHOWNORMAL)
    except Exception:  # noqa: BLE001
        return False
    return int(rc) > 32
