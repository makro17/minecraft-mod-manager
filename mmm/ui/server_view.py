"""Vista de detalle de un servidor: vista previa del contenido → instalar/actualizar."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from .. import api, config, instances, jre, launcher, zerotier
from ..worker import InstallWorker
from . import dialogs
from .format import human_size
from .widgets import ProgressPanel


class ServerView(ttk.Frame):
    def __init__(self, parent, server: dict, on_back, auto_update: bool = False):
        super().__init__(parent, padding=16)
        self.server = server
        self.on_back = on_back
        self.worker: InstallWorker | None = None
        self._preview: ttk.Frame | None = None
        self._mirror_shaders = tk.IntVar(value=0)  # 0 = añadir, 1 = sobrescribir

        self.back_button = ttk.Button(self, text="← Volver", command=self._back)
        self.back_button.pack(anchor="w")
        ttk.Label(self, text=server["name"], font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(8, 0))
        ttk.Label(self, text=server.get("motd", "")).pack(anchor="w")
        ttk.Label(self, text=f'{server.get("loader","")} {server.get("minecraft_version","")} '
                             f'(loader {server.get("loader_version","")})').pack(anchor="w", pady=(4, 4))

        self.status_label = ttk.Label(self, text="Comprobando estado…", foreground="gray")
        self.status_label.pack(anchor="w", pady=(0, 8))

        self.progress = ProgressPanel(self)
        self.progress.pack(fill="x")

        # El botón se muestra según el estado (oculto cuando ya está al día).
        self.action = ttk.Button(self, text="Instalar", command=self._load_preview)

        self.zt_button = ttk.Button(self, text="Unirse a la red (ZeroTier)", command=self._join_network)
        self.zt_button.pack(pady=(0, 4))

        self.zt_status = ttk.Label(self, text="ZeroTier: comprobando…", foreground="gray")
        self.zt_status.pack(anchor="w", pady=(0, 6))

        self.hint = ttk.Label(self, text="", wraplength=560, foreground="gray")
        self.hint.pack(anchor="w")

        self._poll_zt()
        self._refresh_status()

        if auto_update:  # "Actualizar" desde la lista: usa el modo de shaders efectivo
            self.after(300, lambda: self._start_install(config.resolve_shaders_mirror(self.server)))

    # ── Estado instalado / al día ────────────────────────────────────────────
    def _show_action(self, text: str):
        self.action.config(text=text, state="normal")
        if not self.action.winfo_ismapped():
            self.action.pack(pady=8, before=self.zt_button)

    def _hide_action(self):
        self.action.pack_forget()

    def _refresh_status(self):
        def run():
            try:
                latest = api.resolve(self.server["key"]).get("latest_version", 0)
            except Exception:
                latest = None
            if self.winfo_exists():
                self.after(0, lambda: self._apply_status(latest))

        threading.Thread(target=run, daemon=True).start()

    def _apply_status(self, latest):
        if not self.winfo_exists():
            return
        if latest is None:
            self.status_label.config(text="Sin conexión: no pude comprobar el estado.", foreground="gray")
            self._show_action("Instalar / Actualizar")
            return
        st = config.server_status(self.server, latest)
        installed = self.server.get("installed_version")
        if st == "al_dia":
            self.status_label.config(text=f"✓ Ya está actualizado (v{installed})", foreground="#3a8a3a")
            self._hide_action()
        elif st == "actualizacion":
            self.status_label.config(text=f"⬆ Actualización disponible (v{latest} · tienes v{installed})", foreground="#b0894a")
            self._show_action("Actualizar")
        else:
            self.status_label.config(text="No instalado", foreground="gray")
            self._show_action("Instalar")

    def _back(self):
        self.on_back()

    def _join_network(self):
        from . import zt_dialog
        zt_dialog.ensure_access(self, self.server["key"])
        self._poll_zt()  # refresca el estado justo después

    # ── Estado de acceso ZeroTier (se refresca solo) ─────────────────────────
    def _poll_zt(self):
        if not self.winfo_exists():
            return

        def run():
            state = zerotier.access_status()
            if self.winfo_exists():
                self.after(0, lambda: self._apply_zt_state(state))

        threading.Thread(target=run, daemon=True).start()

    def _set_zt_button(self, text: str, command):
        self.zt_button.config(text=text, command=command)
        if not self.zt_button.winfo_ismapped():
            self.zt_button.pack(pady=(0, 4), before=self.zt_status)

    def _apply_zt_state(self, state: str):
        if not self.winfo_exists():
            return
        action = zerotier.ui_action(state, config.get_zt_onboarded())
        if action == "disconnect":
            user = config.get_username()
            suffix = f" como «{user}»" if user else ""
            self.zt_status.config(text=f"ZeroTier: ✓ autorizado{suffix} — ya puedes conectar", foreground="#3a8a3a")
            self._set_zt_button("Desconectar de la red", self._disconnect_network)
        elif action == "pending":
            self.zt_status.config(text="ZeroTier: solicitud enviada · pendiente de que el admin te autorice…", foreground="#b0894a")
            self.zt_button.pack_forget()
        elif action == "reconnect":
            self.zt_status.config(text="ZeroTier: desconectado — pulsa «Conectar» para volver a entrar", foreground="gray")
            self._set_zt_button("Conectar a la red", self._reconnect_network)
        elif action == "install":
            self.zt_status.config(text="ZeroTier: no instalado — pulsa el botón para instalarlo", foreground="#b0894a")
            self._set_zt_button("Unirse a la red (ZeroTier)", self._join_network)
        else:  # join
            self.zt_status.config(text="ZeroTier: no estás en la red — pulsa «Unirse a la red»", foreground="gray")
            self._set_zt_button("Unirse a la red (ZeroTier)", self._join_network)
        self.after(4000, self._poll_zt)

    def _reconnect_network(self):
        # Ya hicimos onboarding: el controlador nos tiene autorizados, así que basta
        # con volver a unirse — sin pedir nombre ni reenviar solicitud.
        try:
            zerotier.join()
        except Exception as e:  # noqa: BLE001
            from tkinter import messagebox
            messagebox.showerror("ZeroTier", f"No pude reconectar: {e}", parent=self)
        self._poll_zt()

    def _disconnect_network(self):
        # Desconecta del túnel pero seguimos «onboarded» → luego reconectamos directo.
        try:
            zerotier.leave()
        except Exception as e:  # noqa: BLE001
            from tkinter import messagebox
            messagebox.showerror("ZeroTier", f"No pude desconectar: {e}", parent=self)
        self._poll_zt()

    # ── Fase 1: vista previa del contenido ───────────────────────────────────
    def _load_preview(self):
        self.action.config(state="disabled")
        self.progress.set_status("Obteniendo lista de contenido…")

        def run():
            try:
                manifest = api.get_manifest(self.server["key"])
            except Exception as e:  # noqa: BLE001 — se reporta a la UI
                self.after(0, lambda: self._preview_error(str(e)))
                return
            self.after(0, lambda: self._show_preview(manifest))

        threading.Thread(target=run, daemon=True).start()

    def _preview_error(self, message: str):
        self.progress.set_status("Error al obtener la lista.")
        dialogs.show_error(self, "Error", message)
        self.action.config(state="normal")

    def _show_preview(self, manifest: dict):
        self.progress.set_status("")
        self.action.pack_forget()
        if self._preview is not None:
            self._preview.destroy()
        pv = ttk.Frame(self)
        # En el sitio del botón (encima de la sección ZeroTier), no enterrada al
        # final del layout: si no, «Actualizar» oculta el botón y la vista previa
        # queda fuera de vista y parece que no pasó nada.
        try:
            pv.pack(fill="both", expand=True, before=self.zt_button)
        except tk.TclError:  # el botón ZT puede estar oculto (estado 'pendiente')
            pv.pack(fill="both", expand=True, before=self.zt_status)
        self._preview = pv

        files = manifest.get("files", [])
        mods = [f for f in files if f.get("target_dir") == "mods"]
        shaders = [f for f in files if f.get("target_dir") == "shaderpacks"]
        total = sum(int(f.get("size") or 0) for f in files)

        ttk.Label(pv, text=f"Se descargará · {len(mods)} mods, {len(shaders)} shaders · {human_size(total)}",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 2))
        ttk.Label(pv, text="(los archivos que ya tengas se omiten automáticamente)",
                  foreground="gray").pack(anchor="w")

        box = ttk.Frame(pv)
        box.pack(fill="both", expand=True, pady=6)
        sb = ttk.Scrollbar(box, orient="vertical")
        lst = tk.Listbox(box, height=10, yscrollcommand=sb.set)
        sb.config(command=lst.yview)
        sb.pack(side="right", fill="y")
        lst.pack(side="left", fill="both", expand=True)
        for f in mods + shaders:
            lst.insert("end", f'{f.get("target_dir")}/{f.get("filename")}  —  {human_size(f.get("size"))}')

        self._mirror_shaders.set(1 if config.resolve_shaders_mirror(self.server) else 0)
        if shaders:
            sf = ttk.LabelFrame(pv, text="Shaders del modpack")
            sf.pack(fill="x", pady=6)
            ttk.Radiobutton(sf, text="Añadir a los que ya tengo", variable=self._mirror_shaders, value=0).pack(anchor="w")
            ttk.Radiobutton(sf, text="Sobrescribir toda la carpeta de shaders", variable=self._mirror_shaders, value=1).pack(anchor="w")

        bf = ttk.Frame(pv)
        bf.pack(fill="x", pady=6)
        ttk.Button(bf, text="Confirmar e instalar", command=lambda: self._confirm_install(manifest)).pack(side="left")
        ttk.Button(bf, text="Cancelar", command=self._cancel_preview).pack(side="left", padx=6)

    def _cancel_preview(self):
        if self._preview is not None:
            self._preview.destroy()
            self._preview = None
        self._refresh_status()

    # ── Fase 2: instalación ──────────────────────────────────────────────────
    def _confirm_install(self, manifest: dict):
        # La elección del usuario aquí queda como override para ESE servidor.
        mirror = bool(self._mirror_shaders.get())
        self.server["shaders_mirror"] = mirror
        config.upsert_server(self.server)
        self._start_install(mirror)

    def _start_install(self, mirror_shaders: bool):
        if self._preview is not None:
            self._preview.destroy()
            self._preview = None
        self._hide_action()
        official = config.official_minecraft_dir() or launcher.default_official_dir()
        instance = instances.instance_dir(self.server["slug"], official)
        self.server["instance_path"] = str(instance)
        config.upsert_server(self.server)
        self.back_button.config(state="disabled")
        self.worker = InstallWorker()
        self.worker.start(self.server, official, jre.java_exe(), mirror_shaders=mirror_shaders)
        self.after(200, self._poll)

    def _restore_action(self):
        self.back_button.config(state="normal")
        self._refresh_status()

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
                self._restore_action()
                return
            elif kind == "error":
                self.progress.set_status("Error en la instalación.")
                dialogs.show_error(self, "Error", kw["message"])
                self._restore_action()
                return
        self.after(200, self._poll)
