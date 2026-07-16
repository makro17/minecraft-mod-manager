"""C4 · onboarding ZeroTier en el cliente.

Parte pura (parseo) testeable + wrappers finos sobre `zerotier-cli` (Windows).
Las operaciones de unión requieren privilegios de administrador.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

# Red privada auto-alojada del panel.
NWID = "acf3c66fcf5b7449"
SUBNET_PREFIX = "10.147.20."

# En Windows el CLI vive junto al servicio.
_CLI_CANDIDATES = [
    r"C:\Program Files (x86)\ZeroTier\One\zerotier-cli.bat",
    r"C:\ProgramData\ZeroTier\One\zerotier-cli.bat",
]


def cli_path() -> Optional[str]:
    found = shutil.which("zerotier-cli")
    if found:
        return found
    for c in _CLI_CANDIDATES:
        if Path(c).exists():
            return c
    return None


def is_installed() -> bool:
    return cli_path() is not None


def parse_node_id(info_output: str) -> Optional[str]:
    """De la salida de `zerotier-cli info`: `200 info <addr> <ver> ONLINE`."""
    parts = (info_output or "").split()
    if len(parts) >= 3 and parts[0] == "200" and parts[1] == "info":
        return parts[2].lower()
    return None


def _run(*args: str) -> str:
    cli = cli_path()
    if not cli:
        raise RuntimeError("ZeroTier no está instalado")
    return subprocess.run(
        [cli, *args], capture_output=True, text=True, timeout=20
    ).stdout


def node_id() -> Optional[str]:
    try:
        return parse_node_id(_run("info"))
    except Exception:
        return None


def join(nwid: str = NWID) -> None:
    _run("join", nwid)


def leave(nwid: str = NWID) -> None:
    """Desconecta de la red (rápido). Al volver a unirse reconecta sin re-autorizar."""
    _run("leave", nwid)


def parse_networks(output: str) -> dict:
    """`zerotier-cli listnetworks` → {nwid: {status, ips}}.

    Formato: `200 listnetworks <nwid> <name> <mac> <status> <type> <dev> <ips>`.
    La cabecera lleva literal `<nwid>` y se ignora.
    """
    nets: dict[str, dict] = {}
    for line in (output or "").splitlines():
        parts = line.split()
        if len(parts) >= 9 and parts[0] == "200" and parts[1] == "listnetworks" and parts[2] != "<nwid>":
            nets[parts[2].lower()] = {"status": parts[5], "ips": parts[8]}
    return nets


def network_state(nets: dict, nwid: str = NWID, prefix: str = SUBNET_PREFIX) -> str:
    """Estado de acceso a partir de las redes parseadas.

    'not_joined' | 'pending' (unido pero sin autorizar/sin IP) | 'authorized'.
    """
    n = nets.get(nwid.lower())
    if not n:
        return "not_joined"
    if n.get("status") == "OK" and prefix in n.get("ips", ""):
        return "authorized"
    return "pending"


def access_status(nwid: str = NWID) -> str:
    """Estado completo: 'not_installed' | 'not_joined' | 'pending' | 'authorized'."""
    if not is_installed():
        return "not_installed"
    try:
        nets = parse_networks(_run("listnetworks"))
    except Exception:
        return "not_installed"
    return network_state(nets, nwid)


def is_authorized(nwid: str = NWID, prefix: str = SUBNET_PREFIX) -> bool:
    """True si ya estamos autorizados y con IP en la red (listo para jugar)."""
    try:
        nets = parse_networks(_run("listnetworks"))
    except Exception:
        return False
    return network_state(nets, nwid, prefix) == "authorized"
