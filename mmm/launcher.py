"""Integración con el launcher oficial: launcher_profiles.json (merge no destructivo)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def default_official_dir() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home())
    return Path(appdata) / ".minecraft"


def ensure_launcher_profiles(official_dir: Path) -> Path:
    official_dir = Path(official_dir)
    official_dir.mkdir(parents=True, exist_ok=True)
    p = official_dir / "launcher_profiles.json"
    if not p.exists():
        p.write_text(json.dumps({"profiles": {}, "settings": {}, "version": 3}),
                     encoding="utf-8")
    return p


def read_profiles(official_dir: Path) -> dict:
    p = Path(official_dir) / "launcher_profiles.json"
    if not p.exists():
        return {"profiles": {}}
    return json.loads(p.read_text(encoding="utf-8"))


def write_profile(official_dir: Path, profile_key: str, name: str, version_id: str,
                  game_dir: Path, icon: str = "Furnace") -> None:
    p = ensure_launcher_profiles(official_dir)
    data = json.loads(p.read_text(encoding="utf-8"))
    profiles = data.setdefault("profiles", {})
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    existing = profiles.get(profile_key, {})
    profiles[profile_key] = {
        **existing,
        "name": name,
        "type": "custom",
        "icon": icon,
        "lastVersionId": version_id,
        "gameDir": str(game_dir),
        "created": existing.get("created", now),
        "lastUsed": now,
    }
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, p)
