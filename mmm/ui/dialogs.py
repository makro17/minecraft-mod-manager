"""Diálogos tkinter: añadir clave, errores."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

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
