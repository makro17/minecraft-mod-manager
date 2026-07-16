"""Motor de sincronización: descarga + verificación sha256 + mirror del manifiesto."""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

_MIRROR_DIRS = ("mods", "shaderpacks")


class Cancelado(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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
        target_dir = f["target_dir"]
        dest = instance_dir / target_dir / f["filename"]
        kept.setdefault(target_dir, set()).add(f["filename"])
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
