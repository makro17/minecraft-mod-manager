"""Ventana principal: biblioteca de servidores."""
from __future__ import annotations

import random
import tkinter as tk
from tkinter import ttk

from .. import api, config, instances, launcher, prank
from ..version import __version__
from ..resources import resource_path
from . import dialogs, theme
from .server_view import ServerView
from .widgets import ServerRow, Tooltip


class AppWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MakroModManager")
        self.geometry("720x480")
        self.minsize(680, 520)
        theme.apply(self, config.get_dark_mode())
        self._teleport_count = 0
        self._prank_image_shown = False
        self._in_library = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.refresh()
        self.after(60000, self._auto_refresh)  # C2: detecta updates de modpack en vivo

    def _auto_refresh(self):
        # Refresca el estado de la biblioteca (incl. "actualización disponible")
        # sin reiniciar la app. Solo si seguimos en la biblioteca (no dentro de un
        # servidor, para no interrumpir una instalación).
        if self._in_library and self.winfo_exists():
            self.refresh()
        self.after(60000, self._auto_refresh)

    # ── C1 · broma al cerrar ─────────────────────────────────────────────────
    def _on_close(self):
        if self._prank_image_shown or not config.get_prank_enabled():
            self.destroy()
            return
        if prank.should_teleport(self._teleport_count):
            self._teleport_count += 1
            self._teleport_window()
            if self._teleport_count >= 3:
                self._show_prank_image()
                self._prank_image_shown = True
            return
        self.destroy()

    def _teleport_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = random.randint(0, max(0, sw - w))
        y = random.randint(0, max(0, sh - h))
        self.geometry(f"+{x}+{y}")

    def _show_prank_image(self):
        top = tk.Toplevel(self)
        top.title("...")
        try:
            img = tk.PhotoImage(file=str(resource_path("assets/cigarro.png")))
            lbl = tk.Label(top, image=img)
            lbl.image = img  # mantener la referencia para que no la recoja el GC
            lbl.pack()
        except Exception:
            tk.Label(top, text="🚬", font=("Segoe UI", 48)).pack(padx=40, pady=40)

    def _open_config(self):
        top = tk.Toplevel(self)
        top.title("Configuración")
        top.resizable(False, False)

        top.configure(bg=theme.colors(config.get_dark_mode())["bg"])

        row = ttk.Frame(top)
        row.pack(fill="x", padx=24, pady=(24, 10), anchor="w")
        ttk.Label(row, text="Nombre de usuario:").pack(side="left")
        name_var = tk.StringVar(value=config.get_username())
        ttk.Entry(row, textvariable=name_var, width=22).pack(side="left", padx=8)
        ttk.Button(row, text="Guardar",
                   command=lambda: config.set_username(name_var.get())).pack(side="left")

        sh_var = tk.BooleanVar(value=config.get_shaders_mirror_default())
        ttk.Checkbutton(
            top, text="Sobrescribir mis shaders con los del modpack (si no: mantener los míos y añadir)",
            variable=sh_var,
            command=lambda: config.set_shaders_mirror_default(sh_var.get()),
        ).pack(anchor="w", padx=24, pady=4)

        dm_var = tk.BooleanVar(value=config.get_dark_mode())
        ttk.Checkbutton(
            top, text="Modo oscuro", variable=dm_var,
            command=lambda: self._toggle_dark(dm_var.get(), top),
        ).pack(anchor="w", padx=24, pady=4)

        prank_var = tk.BooleanVar(value=config.get_prank_enabled())
        ttk.Checkbutton(
            top, text="", variable=prank_var,
            command=lambda: config.set_prank_enabled(prank_var.get()),
        ).pack(anchor="w", padx=24, pady=(4, 16))

        # Versión instalada: sirve para comprobar de un vistazo si el auto-update entró.
        ttk.Label(top, text=f"MakroModManager v{__version__}", foreground="gray").pack(
            anchor="w", padx=24, pady=(0, 24))

    def _toggle_dark(self, dark: bool, dialog):
        config.set_dark_mode(dark)
        theme.apply(self, dark)
        dialog.configure(bg=theme.colors(dark)["bg"])

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def refresh(self):
        self._in_library = True
        self._clear()
        header = ttk.Frame(self.container, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="MakroModManager",
                  font=("Segoe UI", 14, "bold")).pack(side="left")
        cfg_btn = ttk.Button(header, text="⚙", width=3, command=self._open_config)
        cfg_btn.pack(side="right")
        Tooltip(cfg_btn, "Configuración")

        body = ttk.Frame(self.container, padding=8)
        body.pack(fill="both", expand=True)

        servers = config.list_servers()
        if not servers:
            ttk.Label(body, text="No hay servidores. Añade uno con su clave.").pack(pady=20)
        for server in servers:
            status = self._status_for(server)
            ServerRow(body, server, status, self._open_server,
                      self._update_server, self._delete_server, self._reveal_server,
                      self._reenter_key).pack(fill="x", pady=2)

        ttk.Button(self.container, text="+ Añadir servidor (clave)",
                   command=self._add_server).pack(pady=10)

    def _status_for(self, server: dict) -> str:
        if server.get("key_locked"):
            return "clave_bloqueada"
        try:
            info = api.resolve(server["key"])
            # refresca los metadatos cacheados con la versión del modpack publicado
            if config.apply_resolve_meta(server, info):
                config.upsert_server(server)
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
        inst = instances.instance_dir(
            slug, config.official_minecraft_dir() or launcher.default_official_dir())
        # Auto-detección: si el servidor se había eliminado pero su instalación
        # sigue en disco, recupera la versión de modpack instalada.
        detected = instances.read_installed_version(inst)
        server = {
            "slug": slug, "name": info["server_name"], "key": key,
            "loader": info["loader"], "minecraft_version": info["minecraft_version"],
            "loader_version": info["loader_version"], "motd": info.get("motd", ""),
            "installed_version": detected,
            "instance_path": str(inst),
        }
        config.upsert_server(server)
        if detected:
            from tkinter import messagebox
            messagebox.showinfo(
                "Instalación detectada",
                f"Recuperé una instalación previa de este servidor (modpack v{detected}).",
                parent=self,
            )
        self.refresh()

    def _open_server(self, server: dict, auto_update: bool = False):
        self._in_library = False
        self._clear()
        ServerView(self.container, server, on_back=self.refresh, auto_update=auto_update).pack(fill="both", expand=True)

    def _update_server(self, server: dict):
        self._open_server(server, auto_update=True)

    def _delete_server(self, server: dict):
        from tkinter import messagebox
        if not messagebox.askyesno(
            "Eliminar servidor",
            f'¿Eliminar "{server["name"]}" de la app?\nLos archivos ya instalados NO se borran.',
            parent=self,
        ):
            return
        config.remove_server(server["slug"])
        self.refresh()

    def _reveal_server(self, server: dict):
        import os
        from tkinter import messagebox
        path = server.get("instance_path")
        if path and os.path.isdir(path):
            os.startfile(path)
        else:
            messagebox.showinfo("Carpeta", "Aún no hay carpeta (instala el modpack primero).", parent=self)

    def _reenter_key(self, server: dict):
        key = dialogs.ask_key(self)
        if not key:
            return
        try:
            api.resolve(key)
        except api.PubError as e:
            msg = "Clave inválida o caducada." if e.status == 403 else str(e)
            dialogs.show_error(self, "No se pudo actualizar", msg)
            return
        server["key"] = key
        server.pop("key_locked", None)
        server.pop("_key_cipher", None)
        config.upsert_server(server)
        self.refresh()
