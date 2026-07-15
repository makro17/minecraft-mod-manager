"""Ventana principal: biblioteca de servidores."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import api, config, instances, launcher
from . import dialogs
from .server_view import ServerView
from .widgets import ServerRow


class AppWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MakroModManager")
        self.geometry("720x480")
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.refresh()

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def refresh(self):
        self._clear()
        header = ttk.Frame(self.container, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="MakroModManager",
                  font=("Segoe UI", 14, "bold")).pack(side="left")

        body = ttk.Frame(self.container, padding=8)
        body.pack(fill="both", expand=True)

        servers = config.list_servers()
        if not servers:
            ttk.Label(body, text="No hay servidores. Añade uno con su clave.").pack(pady=20)
        for server in servers:
            status = self._status_for(server)
            ServerRow(body, server, status, self._open_server).pack(fill="x", pady=2)

        ttk.Button(self.container, text="+ Añadir servidor (clave)",
                   command=self._add_server).pack(pady=10)

    def _status_for(self, server: dict) -> str:
        try:
            info = api.resolve(server["key"])
            return config.server_status(server, info["latest_version"])
        except Exception:
            # sin red o clave caducada: se muestra según lo instalado
            return "al_dia" if server.get("installed_version") else "no_instalado"

    def _add_server(self):
        key = dialogs.ask_key(self)
        if not key:
            return
        try:
            info = api.resolve(key)
        except api.PubError as e:
            msg = "Clave inválida o caducada." if e.status == 403 else str(e)
            dialogs.show_error(self, "No se pudo añadir", msg)
            return
        slug = info.get("server") or info["server_name"].lower().replace(" ", "-")
        server = {
            "slug": slug, "name": info["server_name"], "key": key,
            "loader": info["loader"], "minecraft_version": info["minecraft_version"],
            "loader_version": info["loader_version"], "motd": info.get("motd", ""),
            "installed_version": None,
            "instance_path": str(instances.instance_dir(
                slug, config.official_minecraft_dir() or launcher.default_official_dir())),
        }
        config.upsert_server(server)
        self.refresh()

    def _open_server(self, server: dict):
        self._clear()
        ServerView(self.container, server, on_back=self.refresh).pack(fill="both", expand=True)
