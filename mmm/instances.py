"""Derivación de rutas de la instancia aislada por servidor."""
from __future__ import annotations

import json
from pathlib import Path

_MARKER = ".mmm.json"


def instance_dir(slug: str, official_dir: Path) -> Path:
    return Path(official_dir).with_name(f".minecraft-{slug}")


def read_installed_version(instance: Path) -> int | None:
    """Versión de modpack instalada según el marcador de la instancia (o None)."""
    try:
        data = json.loads((Path(instance) / _MARKER).read_text(encoding="utf-8"))
        v = data.get("version")
        return int(v) if v is not None else None
    except Exception:
        return None


def write_installed_version(instance: Path, version: int) -> None:
    p = Path(instance)
    p.mkdir(parents=True, exist_ok=True)
    (p / _MARKER).write_text(json.dumps({"version": int(version)}), encoding="utf-8")


def mods_dir(instance: Path) -> Path:
    return Path(instance) / "mods"


def shaderpacks_dir(instance: Path) -> Path:
    return Path(instance) / "shaderpacks"
