"""Tema claro/oscuro para la app (ttk)."""
from __future__ import annotations

from tkinter import ttk

_DARK = {"bg": "#2b2b2b", "fg": "#e6e6e6", "field": "#3c3f41", "sel": "#4a4d4f"}
_LIGHT = {"bg": "#f0f0f0", "fg": "#1a1a1a", "field": "#ffffff", "sel": "#cce4ff"}


def colors(dark: bool) -> dict:
    return _DARK if dark else _LIGHT


def apply(root, dark: bool) -> None:
    c = colors(dark)
    style = ttk.Style(root)
    try:
        style.theme_use("clam")  # 'clam' admite recolorear
    except Exception:
        pass
    root.configure(bg=c["bg"])
    style.configure(".", background=c["bg"], foreground=c["fg"], fieldbackground=c["field"])
    style.configure("TFrame", background=c["bg"])
    style.configure("TLabel", background=c["bg"], foreground=c["fg"])
    style.configure("TButton", background=c["field"], foreground=c["fg"])
    style.map("TButton", background=[("active", c["sel"])])
    style.configure("TCheckbutton", background=c["bg"], foreground=c["fg"])
    style.map("TCheckbutton", background=[("active", c["bg"])])
    style.configure("TRadiobutton", background=c["bg"], foreground=c["fg"])
    style.map("TRadiobutton", background=[("active", c["bg"])])
    style.configure("TEntry", fieldbackground=c["field"], foreground=c["fg"])
    style.configure("TProgressbar", background=c["sel"], troughcolor=c["field"])
    style.configure("TLabelframe", background=c["bg"], foreground=c["fg"])
    style.configure("TLabelframe.Label", background=c["bg"], foreground=c["fg"])
