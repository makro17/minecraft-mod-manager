"""Orquestación de instalación + hilo worker con cola de eventos hacia la UI."""
from __future__ import annotations

import queue
import threading
from pathlib import Path

from . import api, launcher, sync
from .loaders.base import get_installer


def install_server(server: dict, official_dir: Path, *, java: Path, events, cancel,
                   get_manifest=api.get_manifest, installer_for=get_installer,
                   sync_fn=sync.sync_manifest, write_profile=launcher.write_profile,
                   download_file=api.download_file) -> int:
    def status(text):
        events("status", text=text)

    key = server["key"]
    slug = server["slug"]
    official_dir = Path(official_dir)
    instance = Path(server["instance_path"])

    status("Obteniendo manifiesto…")
    manifest = get_manifest(key)

    inst = installer_for(manifest["loader"])
    status("Instalando loader…")
    version_id = inst.ensure_installed(
        manifest["minecraft_version"], manifest["loader_version"],
        official_dir, java, progress=status,
    )

    status("Descargando modpack…")
    sync_fn(manifest, instance, key, download_file, cancel=cancel,
            progress=lambda d, t, l: events("progress", done=d, total=t, label=l))

    write_profile(official_dir, f"mmm-{slug}", server["name"], version_id, instance)
    status("Completado")
    return int(manifest["version"])


class InstallWorker:
    """Ejecuta install_server en un hilo; expone eventos por una cola."""
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self.result: int | None = None

    def start(self, server: dict, official_dir: Path, java: Path) -> None:
        def emit(kind, **kw):
            self.q.put((kind, kw))

        def run():
            try:
                self.result = install_server(
                    server, official_dir, java=java, events=emit,
                    cancel=self._cancel.is_set,
                )
                self.q.put(("done", {"version": self.result}))
            except Exception as e:  # noqa: BLE001 — se reporta a la UI
                self.q.put(("error", {"message": str(e)}))

        self._cancel.clear()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def poll(self) -> list[tuple[str, dict]]:
        out = []
        while True:
            try:
                out.append(self.q.get_nowait())
            except queue.Empty:
                break
        return out
