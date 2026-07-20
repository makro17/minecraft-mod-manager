"""Diálogos tkinter: añadir clave, errores, espera modal."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .format import valid_key


def ask_key(parent) -> str | None:
    while True:
        key = simpledialog.askstring(
            "Añadir servidor",
            "Introduce la clave del servidor (PPL-XXXX-XXXX-XXXX):",
            parent=parent,
        )
        if key is None:
            return None
        key = key.strip().upper()
        if valid_key(key):
            return key
        messagebox.showwarning("Clave inválida",
                               "El formato debe ser PPL-XXXX-XXXX-XXXX.", parent=parent)


def show_error(parent, title: str, message: str) -> None:
    messagebox.showerror(title, message, parent=parent)


def run_busy(parent, title: str, message: str, fn):
    """Ejecuta `fn()` en un hilo con un modal indeterminado. Devuelve (resultado, error)."""
    top = tk.Toplevel(parent)
    top.title(title)
    top.transient(parent)
    top.resizable(False, False)
    top.protocol("WM_DELETE_WINDOW", lambda: None)  # no cancelable: dejaría el MSI a medias
    ttk.Label(top, text=message, padding=16).pack()
    bar = ttk.Progressbar(top, mode="indeterminate", length=280)
    bar.pack(padx=16, pady=(0, 16))
    bar.start(12)
    top.grab_set()

    box: dict = {}

    def work():
        try:
            box["result"] = fn()
        except Exception as e:  # noqa: BLE001 — se devuelve al llamador
            box["error"] = e
        finally:
            top.after(0, top.destroy)

    threading.Thread(target=work, daemon=True).start()
    parent.wait_window(top)
    return box.get("result"), box.get("error")
