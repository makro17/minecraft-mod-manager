"""Derivación de rutas de la instancia aislada por servidor."""
from __future__ import annotations

from pathlib import Path


def instance_dir(slug: str, official_dir: Path) -> Path:
    return Path(official_dir).with_name(f".minecraft-{slug}")


def mods_dir(instance: Path) -> Path:
    return Path(instance) / "mods"


def shaderpacks_dir(instance: Path) -> Path:
    return Path(instance) / "shaderpacks"
