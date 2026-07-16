"""Helpers puros de presentación (sin tkinter): validación y etiquetas."""
from __future__ import annotations

import re

KEY_RE = re.compile(r"^PPL-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")

_STATUS = {
    "no_instalado": ("○", "No instalado"),
    "al_dia": ("●", "Actualizado"),
    "actualizacion": ("⬆", "Actualización disponible"),
}
_ACTION = {"no_instalado": "Instalar", "al_dia": "Jugar", "actualizacion": "Actualizar"}


def valid_key(key: str) -> bool:
    return bool(KEY_RE.match(key or ""))


def status_label(status: str) -> tuple[str, str]:
    return _STATUS.get(status, ("?", status))


def action_label(status: str) -> str:
    return _ACTION.get(status, "Instalar")


def human_size(n) -> str:
    n = float(int(n or 0))
    if n < 1024:
        return f"{int(n)} B"
    for unit in ("KB", "MB", "GB"):
        n /= 1024
        if n < 1024:
            return f"{n:.1f} {unit}"
    return f"{n / 1024:.1f} TB"
