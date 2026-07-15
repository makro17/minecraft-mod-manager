"""Cliente de la API pública `/pub` del panel. La app SOLO usa estas rutas."""
from __future__ import annotations

from pathlib import Path

import requests

BASE_URL = "https://maincra.newsik.net"
TIMEOUT = 30
SESSION = requests.Session()


class PubError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _get(path: str, params: dict | None = None, stream: bool = False):
    r = SESSION.get(BASE_URL + path, params=params, stream=stream, timeout=TIMEOUT)
    if r.status_code != 200:
        raise PubError(f"HTTP {r.status_code} en {path}", status=r.status_code)
    return r


def _stream_to(r, dest: Path, progress) -> None:
    total = int(r.headers.get("Content-Length", 0) or 0)
    done = 0
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if not chunk:
                continue
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)


def resolve(key: str) -> dict:
    return _get("/pub/resolve", params={"key": key}).json()


def get_manifest(key: str) -> dict:
    return _get("/pub/manifest", params={"key": key}).json()


def download_file(sha256: str, key: str, dest: Path, progress=None) -> None:
    _stream_to(_get(f"/pub/file/{sha256}", params={"key": key}, stream=True), dest, progress)


def app_version() -> dict:
    return _get("/pub/app/version").json()


def download_app(dest: Path, progress=None) -> None:
    _stream_to(_get("/pub/app/download", stream=True), dest, progress)
