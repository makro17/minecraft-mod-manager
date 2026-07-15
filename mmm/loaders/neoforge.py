"""Instalador headless de NeoForge (implementación completa en la siguiente tarea)."""
from __future__ import annotations

from pathlib import Path

from .base import LoaderInstaller


class NeoForgeInstaller(LoaderInstaller):
    def ensure_installed(self, mc_version: str, loader_version: str,
                         official_dir: Path, java: Path, progress=None) -> str:
        raise NotImplementedError("Se implementa en la tarea del instalador NeoForge.")
