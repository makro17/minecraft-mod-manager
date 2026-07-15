"""Estado persistente de la app: biblioteca de servidores en state.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

_APPDATA = os.environ.get("APPDATA") or str(Path.home())
STATE_DIR = Path(_APPDATA) / "MakroModManager"

_DEFAULT = {"app_version": None, "official_minecraft_dir": None, "servers": []}


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


def official_minecraft_dir() -> Path | None:
    v = load_state().get("official_minecraft_dir")
    return Path(v) if v else None


def set_official_minecraft_dir(path) -> None:
    state = load_state()
    state["official_minecraft_dir"] = str(path)
    save_state(state)
