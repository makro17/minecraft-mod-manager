"""Motor de sincronización: descarga + verificación sha256 + mirror del manifiesto."""
from __future__ import annotations

import os
import time
from pathlib import Path

from .hashing import sha256_file

_MIRROR_DIRS = ("mods", "shaderpacks")


class Cancelado(Exception):
    pass


class ManifiestoInseguro(ValueError):
    """El manifiesto (no confiable) pide escribir fuera de las carpetas permitidas."""


def _es_nombre_simple(name) -> bool:
    """True solo si `name` es un nombre de archivo plano y seguro.

    Rechaza vacío, `.`/`..`, separadores de ruta (POSIX y Windows), dos puntos
    (unidad Windows / ADS) y byte nulo. Así ningún `filename` del manifiesto
    puede escapar de su carpeta destino.
    """
    return (
        isinstance(name, str)
        and name not in ("", ".", "..")
        and not any(c in name for c in ("/", "\\", ":", "\x00"))
    )


def _safe_dest(instance_dir: Path, target_dir, filename) -> Path:
    """Valida `target_dir`/`filename` (no confiables) y devuelve el destino seguro."""
    if target_dir not in _MIRROR_DIRS:
        raise ManifiestoInseguro(f"target_dir no permitido: {target_dir!r}")
    if not _es_nombre_simple(filename):
        raise ManifiestoInseguro(f"filename inseguro: {filename!r}")
    return instance_dir / target_dir / filename


def _fetch_verified(download, sha256, key, dest, attempts):
    last = None
    for a in range(attempts):
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            download(sha256, key, tmp)
            if sha256_file(tmp) == sha256:
                os.replace(tmp, dest)
                return
            last = ValueError(f"sha256 no coincide: {dest.name}")
        except Exception as e:  # red u otro fallo transitorio
            last = e
        finally:
            if tmp.exists():
                tmp.unlink()
        if a < attempts - 1:
            time.sleep(0.5 * (a + 1))
    raise last if last else RuntimeError("descarga fallida")


def sync_manifest(manifest, instance_dir, key, download, cancel=None,
                  progress=None, attempts: int = 3, mirror_shaders: bool = True) -> None:
    instance_dir = Path(instance_dir)
    files = manifest.get("files", [])
    total = len(files)
    kept: dict[str, set] = {d: set() for d in _MIRROR_DIRS}
    for i, f in enumerate(files):
        if cancel and cancel():
            raise Cancelado()
        dest = _safe_dest(instance_dir, f["target_dir"], f["filename"])
        kept[f["target_dir"]].add(f["filename"])
        if progress:
            progress(i, total, f["filename"])
        if dest.exists() and sha256_file(dest) == f["sha256"]:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        _fetch_verified(download, f["sha256"], key, dest, attempts)
    _mirror(instance_dir, kept, mirror_shaders)
    if progress:
        progress(total, total, "")


def _mirror(instance_dir: Path, kept: dict, mirror_shaders: bool = True) -> None:
    # Los mods se sincronizan SIEMPRE exactos (borra lo que no esté en el
    # manifiesto). Los shaders solo se "espejan" en modo sobrescribir; en modo
    # añadir se conservan los del usuario.
    dirs = ["mods"]
    if mirror_shaders:
        dirs.append("shaderpacks")
    for sub in dirs:
        d = instance_dir / sub
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.is_file() and p.name not in kept.get(sub, set()):
                p.unlink()
