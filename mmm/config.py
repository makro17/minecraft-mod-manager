"""Estado persistente de la app: biblioteca de servidores en state.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

_APPDATA = os.environ.get("APPDATA") or str(Path.home())
STATE_DIR = Path(_APPDATA) / "MakroModManager"

_DEFAULT = {
    "app_version": None,
    "official_minecraft_dir": None,
    "servers": [],
    "prank_enabled": True,
    "username": "",
    "shaders_mirror_default": False,  # False = mantener los del usuario y añadir; True = sobrescribir
    "dark_mode": False,
}


def state_path() -> Path:
    return STATE_DIR / "state.json"


def load_state() -> dict:
    p = state_path()
    if not p.exists():
        return json.loads(json.dumps(_DEFAULT))
    data = json.loads(p.read_text(encoding="utf-8"))
    for k, v in _DEFAULT.items():
        data.setdefault(k, v)
    return data


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = state_path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, state_path())


def list_servers() -> list[dict]:
    return load_state()["servers"]


def get_server(slug: str) -> dict | None:
    for s in list_servers():
        if s["slug"] == slug:
            return s
    return None


def upsert_server(server: dict) -> None:
    state = load_state()
    servers = [s for s in state["servers"] if s["slug"] != server["slug"]]
    servers.append(server)
    state["servers"] = servers
    save_state(state)


def remove_server(slug: str) -> None:
    state = load_state()
    state["servers"] = [s for s in state["servers"] if s["slug"] != slug]
    save_state(state)


def server_status(server: dict | None, latest_version: int) -> str:
    if not server or not server.get("installed_version"):
        return "no_instalado"
    if int(server["installed_version"]) >= int(latest_version):
        return "al_dia"
    return "actualizacion"


def get_username() -> str:
    return (load_state().get("username") or "").strip()


def set_username(name: str) -> None:
    state = load_state()
    state["username"] = (name or "").strip()
    save_state(state)


def get_shaders_mirror_default() -> bool:
    return bool(load_state().get("shaders_mirror_default", False))


def set_shaders_mirror_default(value: bool) -> None:
    state = load_state()
    state["shaders_mirror_default"] = bool(value)
    save_state(state)


def resolve_shaders_mirror(server: dict) -> bool:
    """Modo efectivo para un servidor: el override del servidor manda; si no, el default."""
    v = server.get("shaders_mirror")
    return bool(v) if isinstance(v, bool) else get_shaders_mirror_default()


def get_dark_mode() -> bool:
    return bool(load_state().get("dark_mode", False))


def set_dark_mode(value: bool) -> None:
    state = load_state()
    state["dark_mode"] = bool(value)
    save_state(state)


def get_prank_enabled() -> bool:
    return bool(load_state().get("prank_enabled", True))


def set_prank_enabled(value: bool) -> None:
    state = load_state()
    state["prank_enabled"] = bool(value)
    save_state(state)


def official_minecraft_dir() -> Path | None:
    v = load_state().get("official_minecraft_dir")
    return Path(v) if v else None


def set_official_minecraft_dir(path) -> None:
    state = load_state()
    state["official_minecraft_dir"] = str(path)
    save_state(state)
