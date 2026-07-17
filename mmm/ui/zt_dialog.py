"""C4 · flujo de onboarding ZeroTier en el cliente (GUI)."""
from __future__ import annotations

import webbrowser
from tkinter import messagebox, simpledialog

from .. import api, config, zerotier

DOWNLOAD_URL = "https://www.zerotier.com/download/"


def _ask_name(parent, default: str):
    """Pide un nombre obligatorio, con el username como valor por defecto."""
    while True:
        name = simpledialog.askstring(
            "Tu nombre",
            "Nombre con el que el admin te identificará (obligatorio):",
            initialvalue=default,
            parent=parent,
        )
        if name is None:
            return None  # cancelado
        name = name.strip()
        if name:
            return name
        messagebox.showwarning("Nombre obligatorio", "Tienes que poner un nombre.", parent=parent)


def ensure_access(parent, key: str) -> None:
    state = zerotier.access_status()

    if state == "not_installed":
        if messagebox.askyesno(
            "ZeroTier no instalado",
            "Necesitas ZeroTier para conectar a este servidor.\n¿Abrir la página de descarga?",
            parent=parent,
        ):
            webbrowser.open(DOWNLOAD_URL)
        return

    if state == "authorized":
        messagebox.showinfo("ZeroTier", "Ya estás en la red. Puedes conectar al servidor.", parent=parent)
        return

    if state == "pending":
        # Ya hay una solicitud enviada: no reenviar, solo recordar que está pendiente.
        user = config.get_username()
        suffix = f" como «{user}»" if user else ""
        messagebox.showinfo(
            "Solicitud pendiente",
            f"Ya enviaste tu solicitud{suffix}. Está pendiente de que el admin te autorice; "
            "no hace falta reenviarla.",
            parent=parent,
        )
        return

    # state == "not_joined" → onboarding completo (primera vez).
    node = zerotier.node_id()
    if not node:
        messagebox.showerror(
            "ZeroTier", "No pude leer tu ID de ZeroTier. ¿Está arrancado el servicio?", parent=parent
        )
        return

    name = _ask_name(parent, config.get_username())
    if not name:
        return
    # Si aún no había username, el nombre de la solicitud pasa a ser el username.
    if not config.get_username():
        config.set_username(name)

    try:
        zerotier.join()
    except Exception as e:  # noqa: BLE001
        messagebox.showerror(
            "ZeroTier",
            f"No pude unirme a la red: {e}\n\nProbablemente haya que ejecutar la app como administrador.",
            parent=parent,
        )
        return

    try:
        api.zt_request(key, node, name)
    except api.PubError as e:
        messagebox.showerror("ZeroTier", f"No pude enviar la solicitud: {e}", parent=parent)
        return

    # Marca que ya se hizo onboarding: a partir de ahora «Desconectar» + «Conectar»
    # reconecta sin volver a pedir nombre ni reenviar solicitud.
    config.set_zt_onboarded(True)
    messagebox.showinfo(
        "Solicitud enviada",
        f"Enviada como «{name}». Cuando el admin te autorice, podrás conectar al servidor.",
        parent=parent,
    )
