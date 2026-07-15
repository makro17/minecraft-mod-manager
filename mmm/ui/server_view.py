"""Vista de detalle de un servidor: instalar/actualizar con progreso."""
from __future__ import annotations

from tkinter import ttk

from .. import config, instances, jre, launcher
from ..worker import InstallWorker
from . import dialogs
from .widgets import ProgressPanel


class ServerView(ttk.Frame):
    def __init__(self, parent, server: dict, on_back):
        super().__init__(parent, padding=16)
        self.server = server
        self.on_back = on_back
        self.worker: InstallWorker | None = None

        self.back_button = ttk.Button(self, text="← Volver", command=self._back)
        self.back_button.pack(anchor="w")
        ttk.Label(self, text=server["name"], font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(8, 0))
        ttk.Label(self, text=server.get("motd", "")).pack(anchor="w")
        ttk.Label(self, text=f'{server.get("loader","")} {server.get("minecraft_version","")} '
                             f'(loader {server.get("loader_version","")})').pack(anchor="w", pady=(4, 8))

        self.progress = ProgressPanel(self)
        self.progress.pack(fill="x")

        self.action = ttk.Button(self, text="Instalar / Actualizar", command=self._start)
        self.action.pack(pady=8)

        self.hint = ttk.Label(self, text="", wraplength=560, foreground="gray")
        self.hint.pack(anchor="w")

    def _back(self):
        self.on_back()

    def _start(self):
        official = config.official_minecraft_dir() or launcher.default_official_dir()
        instance = instances.instance_dir(self.server["slug"], official)
        self.server["instance_path"] = str(instance)
        config.upsert_server(self.server)
        self.action.config(state="disabled")
        self.back_button.config(state="disabled")
        self.worker = InstallWorker()
        self.worker.start(self.server, official, jre.java_exe())
        self.after(200, self._poll)

    def _poll(self):
        if not self.winfo_exists():
            return
        if not self.worker:
            return
        for kind, kw in self.worker.poll():
            if kind == "status":
                self.progress.set_status(kw["text"])
            elif kind == "progress":
                self.progress.set_progress(kw["done"], kw["total"])
                self.progress.set_status(f'Descargando {kw.get("label","")}…')
            elif kind == "done":
                self.server["installed_version"] = kw["version"]
                config.upsert_server(self.server)
                self.progress.set_status("¡Listo! Abre el launcher oficial y elige el perfil "
                                         f'"{self.server["name"]}".')
                self.hint.config(text="TLauncher/otros: apunta el directorio de juego a "
                                       f'{self.server["instance_path"]} y elige la versión instalada.')
                self.action.config(state="normal")
                self.back_button.config(state="normal")
                return
            elif kind == "error":
                self.progress.set_status("Error en la instalación.")
                dialogs.show_error(self, "Error", kw["message"])
                self.action.config(state="normal")
                self.back_button.config(state="normal")
                return
        self.after(200, self._poll)
