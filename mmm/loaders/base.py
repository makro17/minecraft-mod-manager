"""Contrato común de instaladores de loader + selección por nombre."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class LoaderNoSoportado(Exception):
    pass


class LoaderInstaller(ABC):
    @abstractmethod
    def ensure_installed(self, mc_version: str, loader_version: str,
                         official_dir: Path, java: Path, progress=None) -> str:
        """Instala el loader (idempotente) y devuelve el version_id resultante."""


def get_installer(loader: str) -> LoaderInstaller:
    if loader == "neoforge":
        from .neoforge import NeoForgeInstaller
        return NeoForgeInstaller()
    raise LoaderNoSoportado(f"Loader no soportado todavía: {loader}")
