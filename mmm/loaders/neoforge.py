"""Instalador headless de NeoForge (cliente)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import requests

from .. import hashing, procutil
from ..launcher import ensure_launcher_profiles
from .base import LoaderInstaller

MAVEN = "https://maven.neoforged.net/releases/net/neoforged/neoforge"
SESSION = requests.Session()


def version_id(loader_version: str) -> str:
    return f"neoforge-{loader_version}"


def installer_url(loader_version: str) -> str:
    return f"{MAVEN}/{loader_version}/neoforge-{loader_version}-installer.jar"


def sha256_url(loader_version: str) -> str:
    return installer_url(loader_version) + ".sha256"


def expected_sha256(loader_version: str) -> str:
    r = SESSION.get(sha256_url(loader_version), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(
            f"No se pudo obtener el checksum de NeoForge (HTTP {r.status_code})."
        )
    return r.text.strip()


def build_command(java: Path, installer_path: Path, official_dir: Path) -> list[str]:
    # NOTA: verificar el flag exacto con NeoForge 21.1.x en la verificación manual
    # (histórico Forge/NeoForge: --install-client <dir>).
    return [java.as_posix(), "-jar", installer_path.as_posix(), "--install-client", official_dir.as_posix()]


def download_installer(loader_version: str, dest: Path) -> None:
    r = SESSION.get(installer_url(loader_version), stream=True, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"No se pudo descargar el instalador de NeoForge (HTTP {r.status_code}).")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk:
                f.write(chunk)
    try:
        hashing.verify_sha256(dest, expected_sha256(loader_version))
    except (hashing.HashInvalido, RuntimeError):
        try:
            dest.unlink()
        except OSError:
            pass
        raise


def _run(cmd: list[str]):
    return subprocess.run(cmd, capture_output=True, text=True, **procutil.no_window_kwargs())


class NeoForgeInstaller(LoaderInstaller):
    def ensure_installed(self, mc_version: str, loader_version: str,
                         official_dir: Path, java: Path, progress=None) -> str:
        official_dir = Path(official_dir)
        vid = version_id(loader_version)
        if (official_dir / "versions" / vid).is_dir():
            return vid
        ensure_launcher_profiles(official_dir)
        installer = official_dir / "mmm-cache" / f"neoforge-{loader_version}-installer.jar"
        if progress:
            progress("Descargando instalador de NeoForge…")
        download_installer(loader_version, installer)
        if progress:
            progress("Instalando NeoForge (puede tardar)…")
        result = _run(build_command(java, installer, official_dir))
        if result.returncode != 0:
            raise RuntimeError(
                "El instalador de NeoForge falló.\n"
                f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
            )
        if not (official_dir / "versions" / vid).is_dir():
            raise RuntimeError("El instalador terminó pero no se creó la versión esperada.")
        return vid
