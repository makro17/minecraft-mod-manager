"""Arranque de la app: auto-update no bloqueante + ventana principal."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from tkinter import messagebox

from . import api, config, hashing, updater
from .version import __version__


def maybe_self_update(local_version, ask, download_and_launch, app_version_fn=api.app_version) -> bool:
    info = updater.check_for_update(local_version, app_version_fn)
    if not info:
        return False
    if not ask(info):
        return False
    download_and_launch(info)
    return True


def _ask(info) -> bool:
    return messagebox.askyesno(
        "Actualización disponible",
        f'Hay una nueva versión ({info["version"]}).\n\n{info.get("notes", "")}\n\n¿Actualizar ahora?',
    )


def _download_and_launch(info) -> None:
    dest = Path(tempfile.gettempdir()) / "MakroModManager_setup.exe"
    api.download_app(dest)
    try:
        hashing.verify_sha256(dest, info.get("sha256"))
    except hashing.HashInvalido as e:
        try:
            dest.unlink()
        except OSError:
            pass
        messagebox.showerror(
            "Actualización cancelada",
            "El instalador descargado no superó la verificación de integridad "
            f"y no se ejecutará.\n\n{e}",
        )
        return
    subprocess.Popen([str(dest)])


def main() -> None:
    # registra la versión actual en el estado
    state = config.load_state()
    state["app_version"] = __version__
    config.save_state(state)

    if maybe_self_update(__version__, _ask, _download_and_launch):
        sys.exit(0)  # el instalador toma el relevo

    from .ui.app_window import AppWindow
    AppWindow().mainloop()


if __name__ == "__main__":
    main()
