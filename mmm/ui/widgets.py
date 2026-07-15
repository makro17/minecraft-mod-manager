"""Widgets reutilizables de la biblioteca."""
from __future__ import annotations

from tkinter import ttk

from .format import action_label, status_label


class ServerRow(ttk.Frame):
    def __init__(self, parent, server: dict, status: str, on_open):
        super().__init__(parent, padding=(8, 6))
        sym, txt = status_label(status)
        ttk.Label(self, text=server["name"], width=20,
                  font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Label(self, text=f'{server.get("loader", "")} {server.get("minecraft_version", "")}',
                  width=18).pack(side="left")
        ttk.Label(self, text=f"{sym} {txt}", width=22).pack(side="left")
        ttk.Button(self, text=action_label(status),
                   command=lambda: on_open(server)).pack(side="right")


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
