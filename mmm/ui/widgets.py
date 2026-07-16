"""Widgets reutilizables de la biblioteca."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .format import status_label


class Tooltip:
    """Muestra el nombre del botón al dejar el puntero encima."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _evt=None):
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, background="#ffffe0", foreground="#000000",
                 relief="solid", borderwidth=1, font=("Segoe UI", 8)).pack()

    def _hide(self, _evt=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ServerRow(ttk.Frame):
    def __init__(self, parent, server: dict, status: str, on_open, on_update, on_delete, on_reveal):
        super().__init__(parent, padding=(8, 8))
        sym, txt = status_label(status)
        installed = server.get("installed_version")
        modpack = f"Modpack v{installed}" if installed else "Sin instalar"

        # ── Info (clicable → abre los detalles) ──────────────────────────────
        info = ttk.Frame(self)
        info.pack(fill="x")
        labels = [
            ttk.Label(info, text=server["name"], width=20, font=("Segoe UI", 11, "bold")),
            ttk.Label(info, text=f'{server.get("loader", "")} {server.get("minecraft_version", "")}', width=16),
            ttk.Label(info, text=modpack, width=14),
            ttk.Label(info, text=f"{sym} {txt}", width=22),
        ]
        for lb in labels:
            lb.pack(side="left")

        def _open(_evt=None):
            on_open(server)

        for w in (info, *labels):
            w.configure(cursor="hand2")
            w.bind("<Button-1>", _open)

        # ── Acciones (debajo, aprovechando el ancho) ─────────────────────────
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(6, 0))
        # A la izquierda: ver + instalar/actualizar (nada si ya está al día).
        ttk.Button(actions, text="Ver", width=8, command=lambda: on_open(server)).pack(side="left", padx=(0, 4))
        if status != "al_dia":
            label = "Instalar" if status == "no_instalado" else "Actualizar"
            ttk.Button(actions, text=label, width=11,
                       command=lambda: on_update(server)).pack(side="left", padx=4)
        # A la derecha: iconos con tooltip.
        b_del = ttk.Button(actions, text="🗑", width=3, command=lambda: on_delete(server))
        b_del.pack(side="right", padx=4)
        b_dir = ttk.Button(actions, text="📂", width=3, command=lambda: on_reveal(server))
        b_dir.pack(side="right", padx=4)
        Tooltip(b_del, "Eliminar")
        Tooltip(b_dir, "Mostrar en carpeta")


class ProgressPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent, padding=10)
        self._status = ttk.Label(self, text="")
        self._status.pack(anchor="w")
        self._bar = ttk.Progressbar(self, length=420, mode="determinate")
        self._bar.pack(fill="x", pady=6)

    def set_status(self, text: str) -> None:
        self._status.config(text=text)

    def set_progress(self, done: int, total: int) -> None:
        self._bar.config(maximum=max(total, 1), value=done)
