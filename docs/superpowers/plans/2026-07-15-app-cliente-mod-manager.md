# App cliente "MakroModManager" (Sub-proyecto B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reescribir el repo `minecraft-mod-manager` como una app de escritorio (Python + tkinter) que, con una clave `PPL-XXXX-XXXX-XXXX`, instala y mantiene al día en una instancia aislada el loader (NeoForge) + mods de cliente + shaders de un servidor, integrándose de forma no destructiva con el launcher oficial.

**Architecture:** Paquete Python modular con un **hilo worker** para red/instalación y cola de eventos hacia la UI tkinter. Capas puras y testeables (`api`, `config`, `sync`, `launcher`, `loaders`, `updater`) + una orquestación (`worker.install_server`) + UI fina encima. Consume solo la API pública `/pub` del panel (Sub-proyecto A).

**Tech Stack:** Python 3.x, `requests`, tkinter (stdlib), `pytest` (dev), PyInstaller + Inno Setup (empaquetado), JRE bundleado (jlink Temurin 21).

## Global Constraints

- **Idioma:** todo el texto de UI, comentarios, docs y mensajes de commit en **español**.
- **Sin referencias a Claude/Anthropic** en ningún artefacto (código, commits, docs). Commits SIN línea `Co-Authored-By`.
- **Solo `/pub`:** la app nunca llama a la API de admin del panel. Base: `BASE_URL = "https://maincra.newsik.net"`.
- **Formato de clave:** `PPL-XXXX-XXXX-XXXX`, alfabeto `A-Z0-9`. Regex: `^PPL-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$`.
- **No destructivo:** nunca se tocan `saves/` ni `config/` de la instancia; el `.minecraft` oficial solo recibe `versions/`, `libraries/` y un perfil (merge, preservando los del jugador).
- **Loader v1:** solo **NeoForge** implementado; otros loaders lanzan `LoaderNoSoportado` con mensaje claro.
- **Estado:** `%APPDATA%\MakroModManager\state.json` (biblioteca de servidores). Clave guardada en claro (uso personal, decisión consciente).
- **Tests sin red ni Minecraft real:** `requests`, `subprocess` y descargas se mockean; se usa `tmp_path`.

---

## File Structure

**Nuevos (paquete `mmm/`):**
- `mmm/__init__.py` — expone `__version__`.
- `mmm/version.py` — semver, fuente única.
- `mmm/api.py` — cliente `/pub` (resolve, manifest, file, app/version, app/download) + `PubError`.
- `mmm/config.py` — estado/biblioteca en `state.json`; alta/baja de servidores; cálculo de estado.
- `mmm/instances.py` — derivación de rutas de instancia.
- `mmm/launcher.py` — `.minecraft` oficial por defecto + leer/escribir `launcher_profiles.json` (merge).
- `mmm/jre.py` — localizar el `java.exe` (bundleado cuando `frozen`, override en dev).
- `mmm/loaders/base.py` — interfaz `LoaderInstaller`, `LoaderNoSoportado`, factory `get_installer`.
- `mmm/loaders/neoforge.py` — instalador NeoForge headless.
- `mmm/sync.py` — motor descarga + verificación sha256 + mirror.
- `mmm/updater.py` — comparación semver + decisión de auto-update.
- `mmm/worker.py` — `install_server` (orquestación testeable) + `InstallWorker` (hilo + cola).
- `mmm/ui/format.py` — helpers puros de presentación (etiquetas de estado/botón).
- `mmm/ui/widgets.py` — widgets reutilizables (fila de servidor, panel de progreso).
- `mmm/ui/dialogs.py` — diálogo "añadir clave", ajustes, error.
- `mmm/ui/app_window.py` — ventana principal (biblioteca).
- `mmm/ui/server_view.py` — detalle de servidor + instalar/actualizar.
- `mmm/__main__.py` — arranque, wiring, chequeo de auto-update.
- `tests/conftest.py` + `tests/test_*.py`.
- Empaquetado: `MakroModManager.spec`, `build.bat`, `clean.bat`, `installer.iss`, `INSTRUCCIONES.md`, `requirements.txt`, `requirements-dev.txt`.

**Eliminados:** `zazaland_mod_manager.py`, `MakroModManager.spec` viejo, carpetas `build/` y `dist/` generadas.

---

## Task 1: Scaffolding del paquete + limpieza del repo viejo

**Files:**
- Create: `mmm/__init__.py`, `mmm/version.py`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, `tests/__init__.py`, `tests/test_version.py`
- Delete: `zazaland_mod_manager.py`, `MakroModManager.spec`, `build/`, `dist/`

**Interfaces:**
- Produces: `mmm.__version__: str` (== `mmm.version.__version__`), valor inicial `"1.0.0"`.

- [ ] **Step 1: Escribir el test**

Create `tests/test_version.py`:

```python
import re

import mmm


def test_version_semver():
    assert re.match(r"^\d+\.\d+\.\d+$", mmm.__version__)
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_version.py -v`
Expected: FAIL (`No module named 'mmm'`).

- [ ] **Step 3: Crear el paquete**

Create `mmm/version.py`:

```python
"""Versión de la app. Fuente única (la leen el instalador .iss y el auto-update)."""
__version__ = "1.0.0"
```

Create `mmm/__init__.py`:

```python
from .version import __version__

__all__ = ["__version__"]
```

Create `tests/__init__.py` (vacío).

Create `requirements.txt`:

```
requests>=2.31
```

Create `requirements-dev.txt`:

```
-r requirements.txt
pytest>=8.0
pyinstaller>=6.0
```

Create `.gitignore`:

```
__pycache__/
*.pyc
build/
dist/
installer_output/
.venv/
*.spec.bak
```

- [ ] **Step 4: Borrar lo viejo**

```bash
git rm zazaland_mod_manager.py MakroModManager.spec
rm -rf build dist
```

- [ ] **Step 5: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_version.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add mmm requirements.txt requirements-dev.txt .gitignore tests
git commit -m "App cliente: scaffolding del paquete mmm + limpieza del script viejo"
```

---

## Task 2: Cliente de la API pública `/pub` (`api.py`)

**Files:**
- Create: `mmm/api.py`
- Test: `tests/conftest.py` (nuevo), `tests/test_api.py`

**Interfaces:**
- Produces:
  - `BASE_URL: str = "https://maincra.newsik.net"`
  - `SESSION: requests.Session` (module-level; los tests lo sustituyen)
  - `class PubError(Exception)` con atributo `.status: int | None`
  - `resolve(key: str) -> dict`
  - `get_manifest(key: str) -> dict`
  - `download_file(sha256: str, key: str, dest: Path, progress: callable | None = None) -> None`
  - `app_version() -> dict`
  - `download_app(dest: Path, progress: callable | None = None) -> None`

- [ ] **Step 1: Escribir fixtures + tests**

Create `tests/conftest.py`:

```python
"""Fixtures y dobles de prueba compartidos."""
import pytest


class FakeResp:
    def __init__(self, status=200, json_data=None, content=b"", headers=None):
        self.status_code = status
        self._json = json_data if json_data is not None else {}
        self._content = content
        self.headers = headers or {}

    def json(self):
        return self._json

    def iter_content(self, chunk_size):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]


class FakeSession:
    """Devuelve respuestas encoladas por (método) y registra las llamadas."""
    def __init__(self, resp):
        self.resp = resp
        self.calls = []

    def get(self, url, params=None, stream=False, timeout=None):
        self.calls.append({"url": url, "params": params, "stream": stream})
        return self.resp


@pytest.fixture
def official_dir(tmp_path):
    d = tmp_path / ".minecraft"
    d.mkdir()
    return d
```

Create `tests/test_api.py`:

```python
from pathlib import Path

import pytest

from mmm import api
from tests.conftest import FakeResp, FakeSession


def test_resolve_ok(monkeypatch):
    resp = FakeResp(json_data={"server_name": "Papulandia", "loader": "neoforge"})
    fake = FakeSession(resp)
    monkeypatch.setattr(api, "SESSION", fake)
    out = api.resolve("PPL-AAAA-BBBB-CCCC")
    assert out["server_name"] == "Papulandia"
    assert fake.calls[0]["url"].endswith("/pub/resolve")
    assert fake.calls[0]["params"] == {"key": "PPL-AAAA-BBBB-CCCC"}


# Nota: los dobles FakeResp/FakeSession viven en tests/conftest.py.


def test_resolve_403(monkeypatch):
    monkeypatch.setattr(api, "SESSION", FakeSession(FakeResp(status=403)))
    with pytest.raises(api.PubError) as e:
        api.resolve("PPL-ZZZZ-ZZZZ-ZZZZ")
    assert e.value.status == 403


def test_download_file_escribe_contenido(monkeypatch, tmp_path):
    resp = FakeResp(content=b"hola-mundo", headers={"Content-Length": "10"})
    monkeypatch.setattr(api, "SESSION", FakeSession(resp))
    dest = tmp_path / "mods" / "x.jar"
    api.download_file("abc", "PPL-AAAA-BBBB-CCCC", dest)
    assert dest.read_bytes() == b"hola-mundo"


def test_app_version_ok(monkeypatch):
    monkeypatch.setattr(api, "SESSION", FakeSession(FakeResp(json_data={"version": "1.2.0"})))
    assert api.app_version()["version"] == "1.2.0"
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL (`No module named 'mmm.api'`).

- [ ] **Step 3: Implementar `mmm/api.py`**

```python
"""Cliente de la API pública `/pub` del panel. La app SOLO usa estas rutas."""
from __future__ import annotations

from pathlib import Path

import requests

BASE_URL = "https://maincra.newsik.net"
TIMEOUT = 30
SESSION = requests.Session()


class PubError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _get(path: str, params: dict | None = None, stream: bool = False):
    r = SESSION.get(BASE_URL + path, params=params, stream=stream, timeout=TIMEOUT)
    if r.status_code != 200:
        raise PubError(f"HTTP {r.status_code} en {path}", status=r.status_code)
    return r


def _stream_to(r, dest: Path, progress) -> None:
    total = int(r.headers.get("Content-Length", 0) or 0)
    done = 0
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if not chunk:
                continue
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)


def resolve(key: str) -> dict:
    return _get("/pub/resolve", params={"key": key}).json()


def get_manifest(key: str) -> dict:
    return _get("/pub/manifest", params={"key": key}).json()


def download_file(sha256: str, key: str, dest: Path, progress=None) -> None:
    _stream_to(_get(f"/pub/file/{sha256}", params={"key": key}, stream=True), dest, progress)


def app_version() -> dict:
    return _get("/pub/app/version").json()


def download_app(dest: Path, progress=None) -> None:
    _stream_to(_get("/pub/app/download", stream=True), dest, progress)
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_api.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mmm/api.py tests/conftest.py tests/test_api.py
git commit -m "App cliente: cliente de la API pública /pub"
```

---

## Task 3: Estado / biblioteca de servidores (`config.py`)

**Files:**
- Create: `mmm/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `STATE_DIR: Path` (module-level; los tests lo sustituyen por `tmp_path`)
  - `state_path() -> Path`
  - `load_state() -> dict` (default `{"app_version": None, "official_minecraft_dir": None, "servers": []}`)
  - `save_state(state: dict) -> None`
  - `list_servers() -> list[dict]`
  - `get_server(slug: str) -> dict | None`
  - `upsert_server(server: dict) -> None` (clave: `slug`)
  - `remove_server(slug: str) -> None`
  - `server_status(server: dict | None, latest_version: int) -> str` (`"no_instalado"` | `"al_dia"` | `"actualizacion"`)
  - `official_minecraft_dir() -> Path | None`, `set_official_minecraft_dir(path) -> None`

- [ ] **Step 1: Escribir tests**

Create `tests/test_config.py`:

```python
import pytest

from mmm import config


@pytest.fixture(autouse=True)
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE_DIR", tmp_path / "MakroModManager")


def test_load_state_por_defecto():
    st = config.load_state()
    assert st["servers"] == []


def test_upsert_y_get_server():
    config.upsert_server({"slug": "papulandia", "name": "Papulandia", "installed_version": 2})
    config.upsert_server({"slug": "papulandia", "name": "Papulandia", "installed_version": 3})
    assert config.get_server("papulandia")["installed_version"] == 3
    assert len(config.list_servers()) == 1


def test_remove_server():
    config.upsert_server({"slug": "a", "name": "A"})
    config.remove_server("a")
    assert config.get_server("a") is None


def test_server_status():
    assert config.server_status(None, 3) == "no_instalado"
    assert config.server_status({"installed_version": None}, 3) == "no_instalado"
    assert config.server_status({"installed_version": 3}, 3) == "al_dia"
    assert config.server_status({"installed_version": 2}, 3) == "actualizacion"
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/config.py`**

```python
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
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mmm/config.py tests/test_config.py
git commit -m "App cliente: estado/biblioteca de servidores (state.json)"
```

---

## Task 4: Rutas de instancia (`instances.py`)

**Files:**
- Create: `mmm/instances.py`
- Test: `tests/test_instances.py`

**Interfaces:**
- Produces:
  - `instance_dir(slug: str, official_dir: Path) -> Path` (hermano del oficial: `official_dir.with_name(".minecraft-<slug>")`)
  - `mods_dir(instance: Path) -> Path`, `shaderpacks_dir(instance: Path) -> Path`

- [ ] **Step 1: Escribir tests**

Create `tests/test_instances.py`:

```python
from pathlib import Path

from mmm import instances


def test_instance_dir_es_hermano_del_oficial():
    official = Path("C:/Users/x/AppData/Roaming/.minecraft")
    inst = instances.instance_dir("papulandia", official)
    assert inst.name == ".minecraft-papulandia"
    assert inst.parent == official.parent


def test_subdirs():
    inst = Path("C:/x/.minecraft-papulandia")
    assert instances.mods_dir(inst).name == "mods"
    assert instances.shaderpacks_dir(inst).name == "shaderpacks"
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_instances.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/instances.py`**

```python
"""Derivación de rutas de la instancia aislada por servidor."""
from __future__ import annotations

from pathlib import Path


def instance_dir(slug: str, official_dir: Path) -> Path:
    return Path(official_dir).with_name(f".minecraft-{slug}")


def mods_dir(instance: Path) -> Path:
    return Path(instance) / "mods"


def shaderpacks_dir(instance: Path) -> Path:
    return Path(instance) / "shaderpacks"
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_instances.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/instances.py tests/test_instances.py
git commit -m "App cliente: rutas de la instancia aislada"
```

---

## Task 5: Perfiles del launcher oficial (`launcher.py`)

**Files:**
- Create: `mmm/launcher.py`
- Test: `tests/test_launcher.py`

**Interfaces:**
- Produces:
  - `default_official_dir() -> Path` (`%APPDATA%/.minecraft`)
  - `ensure_launcher_profiles(official_dir: Path) -> Path` (crea stub si falta)
  - `read_profiles(official_dir: Path) -> dict`
  - `write_profile(official_dir: Path, profile_key: str, name: str, version_id: str, game_dir: Path, icon: str = "Furnace") -> None` (merge, preserva otros perfiles)

- [ ] **Step 1: Escribir tests**

Create `tests/test_launcher.py`:

```python
import json

from mmm import launcher


def test_ensure_crea_stub(official_dir):
    (official_dir / "launcher_profiles.json").unlink(missing_ok=True)
    p = launcher.ensure_launcher_profiles(official_dir)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "profiles" in data


def test_write_profile_preserva_existentes(official_dir):
    p = official_dir / "launcher_profiles.json"
    p.write_text(json.dumps({"profiles": {"mio": {"name": "Mio"}}, "version": 3}), encoding="utf-8")
    launcher.write_profile(official_dir, "mmm-papulandia", "Papulandia",
                           "neoforge-21.1.224", official_dir.with_name(".minecraft-papulandia"))
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "mio" in data["profiles"]  # no se pisa el del jugador
    prof = data["profiles"]["mmm-papulandia"]
    assert prof["lastVersionId"] == "neoforge-21.1.224"
    assert prof["gameDir"].endswith(".minecraft-papulandia")
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_launcher.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/launcher.py`**

```python
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
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_launcher.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/launcher.py tests/test_launcher.py
git commit -m "App cliente: perfil en launcher_profiles.json (merge no destructivo)"
```

---

## Task 6: Localización del JRE (`jre.py`)

**Files:**
- Create: `mmm/jre.py`
- Test: `tests/test_jre.py`

**Interfaces:**
- Produces:
  - `is_frozen() -> bool`
  - `java_exe() -> Path` (override `MMM_JAVA` > runtime bundleado si `frozen` > `java` del sistema en dev)

- [ ] **Step 1: Escribir tests**

Create `tests/test_jre.py`:

```python
from pathlib import Path

from mmm import jre


def test_override_env(monkeypatch, tmp_path):
    fake = tmp_path / "java.exe"
    monkeypatch.setenv("MMM_JAVA", str(fake))
    assert jre.java_exe() == fake


def test_frozen_usa_runtime(monkeypatch, tmp_path):
    monkeypatch.delenv("MMM_JAVA", raising=False)
    monkeypatch.setattr(jre.sys, "frozen", True, raising=False)
    monkeypatch.setattr(jre.sys, "executable", str(tmp_path / "MakroModManager.exe"))
    assert jre.java_exe() == tmp_path / "runtime" / "bin" / "java.exe"
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_jre.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/jre.py`**

```python
"""Localiza el ejecutable de Java (JRE bundleado en producción, override en dev)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def java_exe() -> Path:
    override = os.environ.get("MMM_JAVA")
    if override:
        return Path(override)
    if is_frozen():
        return Path(sys.executable).parent / "runtime" / "bin" / "java.exe"
    return Path("java")  # dev: Java del sistema en el PATH
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_jre.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/jre.py tests/test_jre.py
git commit -m "App cliente: localización del JRE bundleado"
```

---

## Task 7: Interfaz de loader + factory (`loaders/base.py`)

**Files:**
- Create: `mmm/loaders/__init__.py`, `mmm/loaders/base.py`
- Test: `tests/test_loaders_base.py`

**Interfaces:**
- Produces:
  - `class LoaderNoSoportado(Exception)`
  - `class LoaderInstaller(ABC)` con `ensure_installed(self, mc_version: str, loader_version: str, official_dir: Path, java: Path, progress=None) -> str`
  - `get_installer(loader: str) -> LoaderInstaller` (raises `LoaderNoSoportado` si no implementado)

- [ ] **Step 1: Escribir tests**

Create `tests/test_loaders_base.py`:

```python
import pytest

from mmm.loaders import base
from mmm.loaders.neoforge import NeoForgeInstaller


def test_get_installer_neoforge():
    assert isinstance(base.get_installer("neoforge"), NeoForgeInstaller)


def test_get_installer_no_soportado():
    with pytest.raises(base.LoaderNoSoportado):
        base.get_installer("fabric")
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_loaders_base.py -v`
Expected: FAIL (`No module named 'mmm.loaders'`).

- [ ] **Step 3: Implementar**

Create `mmm/loaders/__init__.py` (vacío).

Create `mmm/loaders/base.py`:

```python
"""Contrato común de instaladores de loader + selección por nombre."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class LoaderNoSoportado(Exception):
    pass


class LoaderInstaller(ABC):
    @abstractmethod
    def ensure_installed(self, mc_version: str, loader_version: str,
                         official_dir: Path, java: Path, progress=None) -> str:
        """Instala el loader (idempotente) y devuelve el version_id resultante."""


def get_installer(loader: str) -> LoaderInstaller:
    if loader == "neoforge":
        from .neoforge import NeoForgeInstaller
        return NeoForgeInstaller()
    raise LoaderNoSoportado(f"Loader no soportado todavía: {loader}")
```

> `neoforge.py` se crea en la Task 8. Este test importa `NeoForgeInstaller`, así que las Tasks 7 y 8 pueden implementarse juntas; el commit de la Task 7 puede hacerse tras crear el esqueleto de `neoforge.py` de la Task 8 o dejar el import dentro de `get_installer` (ya es perezoso). Para que el test de esta task pase, crea también el esqueleto mínimo de `mmm/loaders/neoforge.py` de la Task 8 antes de ejecutar.

- [ ] **Step 4: Ejecutar (debe pasar)** — tras crear el esqueleto de la Task 8.

Run: `python -m pytest tests/test_loaders_base.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/loaders/__init__.py mmm/loaders/base.py tests/test_loaders_base.py
git commit -m "App cliente: interfaz de loader + factory get_installer"
```

---

## Task 8: Instalador NeoForge headless (`loaders/neoforge.py`)

**Files:**
- Create: `mmm/loaders/neoforge.py`
- Test: `tests/test_neoforge.py`

**Interfaces:**
- Consumes: `mmm.loaders.base.LoaderInstaller`, `mmm.launcher.ensure_launcher_profiles`.
- Produces:
  - `version_id(loader_version: str) -> str` (`f"neoforge-{loader_version}"`)
  - `installer_url(loader_version: str) -> str`
  - `build_command(java: Path, installer_path: Path, official_dir: Path) -> list[str]`
  - `download_installer(loader_version: str, dest: Path) -> None` (module-level; se mockea en tests)
  - `_run(cmd: list[str])` (module-level; se mockea en tests) → objeto con `.returncode`, `.stdout`, `.stderr`
  - `class NeoForgeInstaller(LoaderInstaller)`

- [ ] **Step 1: Escribir tests**

Create `tests/test_neoforge.py`:

```python
from pathlib import Path

import pytest

from mmm.loaders import neoforge
from mmm.loaders.neoforge import NeoForgeInstaller


class _RunResult:
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_build_command():
    cmd = neoforge.build_command(Path("java.exe"), Path("inst.jar"), Path("C:/mc"))
    assert cmd == ["java.exe", "-jar", "inst.jar", "--install-client", "C:/mc"]


def test_version_id_e_url():
    assert neoforge.version_id("21.1.224") == "neoforge-21.1.224"
    assert "21.1.224/neoforge-21.1.224-installer.jar" in neoforge.installer_url("21.1.224")


def test_ensure_idempotente_no_reinstala(official_dir, monkeypatch):
    (official_dir / "versions" / "neoforge-21.1.224").mkdir(parents=True)

    def _boom(*a, **k):
        raise AssertionError("no debía descargar/instalar")

    monkeypatch.setattr(neoforge, "download_installer", _boom)
    monkeypatch.setattr(neoforge, "_run", _boom)
    vid = NeoForgeInstaller().ensure_installed("1.21.1", "21.1.224", official_dir, Path("java"))
    assert vid == "neoforge-21.1.224"


def test_ensure_instala_y_verifica(official_dir, monkeypatch):
    monkeypatch.setattr(neoforge, "download_installer", lambda ver, dest: dest.parent.mkdir(parents=True, exist_ok=True) or dest.write_bytes(b"jar"))

    def fake_run(cmd):
        # simula el installer creando la carpeta de versión
        (official_dir / "versions" / "neoforge-21.1.224").mkdir(parents=True, exist_ok=True)
        return _RunResult(rc=0)

    monkeypatch.setattr(neoforge, "_run", fake_run)
    vid = NeoForgeInstaller().ensure_installed("1.21.1", "21.1.224", official_dir, Path("java"))
    assert vid == "neoforge-21.1.224"


def test_ensure_falla_si_installer_error(official_dir, monkeypatch):
    monkeypatch.setattr(neoforge, "download_installer", lambda ver, dest: dest.parent.mkdir(parents=True, exist_ok=True) or dest.write_bytes(b"jar"))
    monkeypatch.setattr(neoforge, "_run", lambda cmd: _RunResult(rc=1, err="boom"))
    with pytest.raises(RuntimeError):
        NeoForgeInstaller().ensure_installed("1.21.1", "21.1.224", official_dir, Path("java"))
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_neoforge.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/loaders/neoforge.py`**

```python
"""Instalador headless de NeoForge (cliente)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import requests

from ..launcher import ensure_launcher_profiles
from .base import LoaderInstaller

MAVEN = "https://maven.neoforged.net/releases/net/neoforged/neoforge"
SESSION = requests.Session()


def version_id(loader_version: str) -> str:
    return f"neoforge-{loader_version}"


def installer_url(loader_version: str) -> str:
    return f"{MAVEN}/{loader_version}/neoforge-{loader_version}-installer.jar"


def build_command(java: Path, installer_path: Path, official_dir: Path) -> list[str]:
    # NOTA: verificar el flag exacto con NeoForge 21.1.x en la verificación manual
    # (histórico Forge/NeoForge: --install-client <dir>).
    return [str(java), "-jar", str(installer_path), "--install-client", str(official_dir)]


def download_installer(loader_version: str, dest: Path) -> None:
    r = SESSION.get(installer_url(loader_version), stream=True, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"No se pudo descargar el instalador de NeoForge (HTTP {r.status_code}).")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk:
                f.write(chunk)


def _run(cmd: list[str]):
    return subprocess.run(cmd, capture_output=True, text=True)


class NeoForgeInstaller(LoaderInstaller):
    def ensure_installed(self, mc_version: str, loader_version: str,
                         official_dir: Path, java: Path, progress=None) -> str:
        official_dir = Path(official_dir)
        vid = version_id(loader_version)
        if (official_dir / "versions" / vid).is_dir():
            return vid
        ensure_launcher_profiles(official_dir)
        installer = official_dir / "mmm-cache" / f"neoforge-{loader_version}-installer.jar"
        if progress:
            progress("Descargando instalador de NeoForge…")
        download_installer(loader_version, installer)
        if progress:
            progress("Instalando NeoForge (puede tardar)…")
        result = _run(build_command(java, installer, official_dir))
        if result.returncode != 0:
            raise RuntimeError(
                "El instalador de NeoForge falló.\n"
                f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
            )
        if not (official_dir / "versions" / vid).is_dir():
            raise RuntimeError("El instalador terminó pero no se creó la versión esperada.")
        return vid
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_neoforge.py tests/test_loaders_base.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/loaders/neoforge.py tests/test_neoforge.py
git commit -m "App cliente: instalador NeoForge headless"
```

---

## Task 9: Motor de sincronización (`sync.py`)

**Files:**
- Create: `mmm/sync.py`
- Test: `tests/test_sync.py`

**Interfaces:**
- Consumes: firma de descarga compatible con `api.download_file(sha256, key, dest, progress=None)`.
- Produces:
  - `class Cancelado(Exception)`
  - `sha256_file(path: Path) -> str`
  - `sync_manifest(manifest: dict, instance_dir: Path, key: str, download, cancel=None, progress=None, attempts: int = 3) -> None`

- [ ] **Step 1: Escribir tests**

Create `tests/test_sync.py`:

```python
import hashlib
from pathlib import Path

import pytest

from mmm import sync


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _fake_download(payloads):
    """Devuelve una función download(sha, key, dest) que escribe payloads[sha]."""
    def download(sha256, key, dest, progress=None):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(payloads[sha256])
    return download


def _manifest(files):
    return {"files": files}


def test_descarga_y_verifica(tmp_path):
    data = b"jar-bytes"
    sha = _sha(data)
    man = _manifest([{"kind": "mod", "filename": "jei.jar", "sha256": sha,
                      "size": len(data), "target_dir": "mods", "url": f"/pub/file/{sha}"}])
    sync.sync_manifest(man, tmp_path, "PPL-AAAA-BBBB-CCCC", _fake_download({sha: data}))
    assert (tmp_path / "mods" / "jei.jar").read_bytes() == data


def test_skip_si_sha_coincide(tmp_path):
    data = b"ya-esta"
    sha = _sha(data)
    dest = tmp_path / "mods" / "jei.jar"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(data)

    def _boom(*a, **k):
        raise AssertionError("no debía descargar")

    man = _manifest([{"filename": "jei.jar", "sha256": sha, "target_dir": "mods"}])
    sync.sync_manifest(man, tmp_path, "k", _boom)


def test_mirror_borra_lo_ausente(tmp_path):
    (tmp_path / "mods").mkdir()
    (tmp_path / "mods" / "viejo.jar").write_bytes(b"x")
    (tmp_path / "saves").mkdir()
    (tmp_path / "saves" / "mundo").write_bytes(b"no-tocar")
    data = b"nuevo"
    sha = _sha(data)
    man = _manifest([{"filename": "nuevo.jar", "sha256": sha, "target_dir": "mods"}])
    sync.sync_manifest(man, tmp_path, "k", _fake_download({sha: data}))
    assert not (tmp_path / "mods" / "viejo.jar").exists()
    assert (tmp_path / "mods" / "nuevo.jar").exists()
    assert (tmp_path / "saves" / "mundo").read_bytes() == b"no-tocar"  # saves intacto


def test_sha_no_coincide_falla(tmp_path):
    man = _manifest([{"filename": "x.jar", "sha256": "deadbeef", "target_dir": "mods"}])

    def download(sha256, key, dest, progress=None):
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"contenido-que-no-corresponde")

    with pytest.raises(ValueError):
        sync.sync_manifest(man, tmp_path, "k", download, attempts=1)
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_sync.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/sync.py`**

```python
"""Motor de sincronización: descarga + verificación sha256 + mirror del manifiesto."""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

_MIRROR_DIRS = ("mods", "shaderpacks")


class Cancelado(Exception):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_verified(download, sha256, key, dest, attempts):
    last = None
    for a in range(attempts):
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        try:
            download(sha256, key, tmp)
            if sha256_file(tmp) == sha256:
                os.replace(tmp, dest)
                return
            last = ValueError(f"sha256 no coincide: {dest.name}")
        except Exception as e:  # red u otro fallo transitorio
            last = e
        finally:
            if tmp.exists():
                tmp.unlink()
        if a < attempts - 1:
            time.sleep(0.5 * (a + 1))
    raise last if last else RuntimeError("descarga fallida")


def sync_manifest(manifest, instance_dir, key, download, cancel=None,
                  progress=None, attempts: int = 3) -> None:
    instance_dir = Path(instance_dir)
    files = manifest.get("files", [])
    total = len(files)
    kept: dict[str, set] = {d: set() for d in _MIRROR_DIRS}
    for i, f in enumerate(files):
        if cancel and cancel():
            raise Cancelado()
        target_dir = f["target_dir"]
        dest = instance_dir / target_dir / f["filename"]
        kept.setdefault(target_dir, set()).add(f["filename"])
        if progress:
            progress(i, total, f["filename"])
        if dest.exists() and sha256_file(dest) == f["sha256"]:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        _fetch_verified(download, f["sha256"], key, dest, attempts)
    _mirror(instance_dir, kept)
    if progress:
        progress(total, total, "")


def _mirror(instance_dir: Path, kept: dict) -> None:
    for sub in _MIRROR_DIRS:
        d = instance_dir / sub
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.is_file() and p.name not in kept.get(sub, set()):
                p.unlink()
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_sync.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add mmm/sync.py tests/test_sync.py
git commit -m "App cliente: motor de sincronización (descarga+sha256+mirror)"
```

---

## Task 10: Auto-update de la app (`updater.py`)

**Files:**
- Create: `mmm/updater.py`
- Test: `tests/test_updater.py`

**Interfaces:**
- Produces:
  - `parse_semver(s: str) -> tuple[int, int, int]`
  - `is_newer(remote: str, local: str) -> bool`
  - `check_for_update(local_version: str, app_version_fn) -> dict | None`

- [ ] **Step 1: Escribir tests**

Create `tests/test_updater.py`:

```python
from mmm import updater


def test_is_newer():
    assert updater.is_newer("1.2.0", "1.1.9")
    assert not updater.is_newer("1.0.0", "1.0.0")
    assert not updater.is_newer("0.9.0", "1.0.0")


def test_check_devuelve_info_si_nueva():
    info = {"version": "2.0.0", "download_url": "/pub/app/download", "notes": "x"}
    assert updater.check_for_update("1.0.0", lambda: info) == info


def test_check_none_si_igual_o_error():
    assert updater.check_for_update("2.0.0", lambda: {"version": "2.0.0"}) is None

    def boom():
        raise RuntimeError("sin red")

    assert updater.check_for_update("1.0.0", boom) is None
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_updater.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/updater.py`**

```python
"""Auto-update de la propia app (no bloqueante)."""
from __future__ import annotations


def parse_semver(s: str) -> tuple[int, int, int]:
    parts = str(s).split(".")
    nums = [int(p) for p in (parts + ["0", "0", "0"])[:3]]
    return (nums[0], nums[1], nums[2])


def is_newer(remote: str, local: str) -> bool:
    try:
        return parse_semver(remote) > parse_semver(local)
    except (ValueError, TypeError):
        return False


def check_for_update(local_version: str, app_version_fn) -> dict | None:
    try:
        info = app_version_fn()
    except Exception:
        return None
    remote = info.get("version") if isinstance(info, dict) else None
    if remote and is_newer(remote, local_version):
        return info
    return None
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_updater.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/updater.py tests/test_updater.py
git commit -m "App cliente: auto-update (comparación semver + decisión)"
```

---

## Task 11: Orquestación de instalación (`worker.install_server`)

**Files:**
- Create: `mmm/worker.py`
- Test: `tests/test_worker.py`

**Interfaces:**
- Consumes: `api.get_manifest`, `api.download_file`, `loaders.base.get_installer`, `launcher.write_profile`, `sync.sync_manifest`.
- Produces:
  - `install_server(server: dict, official_dir: Path, *, java: Path, events, cancel, get_manifest=..., installer_for=..., sync_fn=..., write_profile=..., download_file=...) -> int` (devuelve `installed_version`; `events(kind: str, **kw)` recibe `("status", text=...)` y `("progress", done=, total=, label=)`)
  - `class InstallWorker` con `start(server, official_dir, java)`, `cancel()`, `poll() -> list[tuple[str, dict]]`

- [ ] **Step 1: Escribir tests**

Create `tests/test_worker.py`:

```python
from pathlib import Path

from mmm import worker


class _FakeInstaller:
    def ensure_installed(self, mc, lv, official_dir, java, progress=None):
        if progress:
            progress("instalando loader")
        return f"neoforge-{lv}"


def test_install_server_orquesta(tmp_path):
    events = []
    server = {"slug": "papulandia", "name": "Papulandia", "key": "PPL-AAAA-BBBB-CCCC",
              "instance_path": str(tmp_path / ".minecraft-papulandia")}
    manifest = {"version": 5, "loader": "neoforge", "minecraft_version": "1.21.1",
                "loader_version": "21.1.224", "files": []}
    written = {}

    def fake_sync(man, inst, key, dl, cancel=None, progress=None):
        written["sync"] = (man is manifest, str(inst))

    def fake_write_profile(official_dir, pk, name, vid, game_dir, icon="Furnace"):
        written["profile"] = (pk, vid, str(game_dir))

    version = worker.install_server(
        server, tmp_path / ".minecraft", java=Path("java"),
        events=lambda k, **kw: events.append((k, kw)), cancel=lambda: False,
        get_manifest=lambda key: manifest,
        installer_for=lambda loader: _FakeInstaller(),
        sync_fn=fake_sync, write_profile=fake_write_profile,
        download_file=lambda *a, **k: None,
    )
    assert version == 5
    assert written["sync"][0] is True
    assert written["profile"][0] == "mmm-papulandia"
    assert written["profile"][1] == "neoforge-21.1.224"
    assert any(k == "status" for k, _ in events)
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_worker.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/worker.py`**

```python
"""Orquestación de instalación + hilo worker con cola de eventos hacia la UI."""
from __future__ import annotations

import queue
import threading
from pathlib import Path

from . import api, launcher, sync
from .loaders.base import get_installer


def install_server(server: dict, official_dir: Path, *, java: Path, events, cancel,
                   get_manifest=api.get_manifest, installer_for=get_installer,
                   sync_fn=sync.sync_manifest, write_profile=launcher.write_profile,
                   download_file=api.download_file) -> int:
    def status(text):
        events("status", text=text)

    key = server["key"]
    slug = server["slug"]
    official_dir = Path(official_dir)
    instance = Path(server["instance_path"])

    status("Obteniendo manifiesto…")
    manifest = get_manifest(key)

    inst = installer_for(manifest["loader"])
    status("Instalando loader…")
    version_id = inst.ensure_installed(
        manifest["minecraft_version"], manifest["loader_version"],
        official_dir, java, progress=status,
    )

    status("Descargando modpack…")
    sync_fn(manifest, instance, key, download_file, cancel=cancel,
            progress=lambda d, t, l: events("progress", done=d, total=t, label=l))

    write_profile(official_dir, f"mmm-{slug}", server["name"], version_id, instance)
    status("Completado")
    return int(manifest["version"])


class InstallWorker:
    """Ejecuta install_server en un hilo; expone eventos por una cola."""
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None
        self.result: int | None = None

    def start(self, server: dict, official_dir: Path, java: Path) -> None:
        def emit(kind, **kw):
            self.q.put((kind, kw))

        def run():
            try:
                self.result = install_server(
                    server, official_dir, java=java, events=emit,
                    cancel=self._cancel.is_set,
                )
                self.q.put(("done", {"version": self.result}))
            except Exception as e:  # noqa: BLE001 — se reporta a la UI
                self.q.put(("error", {"message": str(e)}))

        self._cancel.clear()
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def poll(self) -> list[tuple[str, dict]]:
        out = []
        while True:
            try:
                out.append(self.q.get_nowait())
            except queue.Empty:
                break
        return out
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_worker.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/worker.py tests/test_worker.py
git commit -m "App cliente: orquestación de instalación + hilo worker"
```

---

## Task 12: Helpers de presentación de la UI (`ui/format.py`)

**Files:**
- Create: `mmm/ui/__init__.py`, `mmm/ui/format.py`
- Test: `tests/test_ui_format.py`

**Interfaces:**
- Produces:
  - `KEY_RE` (regex de clave)
  - `valid_key(key: str) -> bool`
  - `status_label(status: str) -> tuple[str, str]` (símbolo, texto) para `no_instalado`/`al_dia`/`actualizacion`
  - `action_label(status: str) -> str` (texto del botón: Instalar/Jugar/Actualizar)

- [ ] **Step 1: Escribir tests**

Create `tests/test_ui_format.py`:

```python
from mmm.ui import format as fmt


def test_valid_key():
    assert fmt.valid_key("PPL-AAAA-BBBB-CCCC")
    assert not fmt.valid_key("ppl-aaaa")
    assert not fmt.valid_key("PPL-AAAA-BBBB")


def test_status_label():
    assert fmt.status_label("al_dia")[1]
    assert fmt.status_label("actualizacion")[1]
    assert fmt.status_label("no_instalado")[1]


def test_action_label():
    assert fmt.action_label("no_instalado") == "Instalar"
    assert fmt.action_label("actualizacion") == "Actualizar"
    assert fmt.action_label("al_dia") == "Jugar"
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_ui_format.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar**

Create `mmm/ui/__init__.py` (vacío).

Create `mmm/ui/format.py`:

```python
"""Helpers puros de presentación (sin tkinter): validación y etiquetas."""
from __future__ import annotations

import re

KEY_RE = re.compile(r"^PPL-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$")

_STATUS = {
    "no_instalado": ("○", "No instalado"),
    "al_dia": ("●", "Al día"),
    "actualizacion": ("⬆", "Actualización disponible"),
}
_ACTION = {"no_instalado": "Instalar", "al_dia": "Jugar", "actualizacion": "Actualizar"}


def valid_key(key: str) -> bool:
    return bool(KEY_RE.match(key or ""))


def status_label(status: str) -> tuple[str, str]:
    return _STATUS.get(status, ("?", status))


def action_label(status: str) -> str:
    return _ACTION.get(status, "Instalar")
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_ui_format.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/ui/__init__.py mmm/ui/format.py tests/test_ui_format.py
git commit -m "App cliente: helpers de presentación de la UI"
```

---

## Task 13: UI — diálogos y widgets (`ui/dialogs.py`, `ui/widgets.py`)

**Files:**
- Create: `mmm/ui/dialogs.py`, `mmm/ui/widgets.py`
- Verificación: manual (tkinter no se testea en CI).

**Interfaces:**
- Produces:
  - `dialogs.ask_key(parent) -> str | None` (valida formato con `format.valid_key`)
  - `dialogs.show_error(parent, title, message) -> None`
  - `widgets.ServerRow(parent, server, status, on_open)` (fila: nombre, loader/versión, estado, botón)
  - `widgets.ProgressPanel(parent)` con `set_status(text)`, `set_progress(done, total)`

- [ ] **Step 1: Implementar `mmm/ui/dialogs.py`**

```python
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
```

- [ ] **Step 2: Implementar `mmm/ui/widgets.py`**

```python
"""Widgets reutilizables de la biblioteca."""
from __future__ import annotations

import tkinter as tk
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
```

- [ ] **Step 3: Verificación manual (smoke)**

Run:
```bash
python -c "import tkinter as tk; from mmm.ui import widgets, dialogs; r=tk.Tk(); widgets.ProgressPanel(r).pack(); widgets.ServerRow(r, {'name':'Papulandia','loader':'neoforge','minecraft_version':'1.21.1'}, 'al_dia', lambda s: None).pack(); r.after(400, r.destroy); r.mainloop(); print('OK')"
```
Expected: abre y cierra una ventana sin error, imprime `OK`.

- [ ] **Step 4: Commit**

```bash
git add mmm/ui/dialogs.py mmm/ui/widgets.py
git commit -m "App cliente: diálogos y widgets de la UI"
```

---

## Task 14: UI — ventana principal y detalle (`ui/app_window.py`, `ui/server_view.py`)

**Files:**
- Create: `mmm/ui/app_window.py`, `mmm/ui/server_view.py`
- Verificación: manual.

**Interfaces:**
- Consumes: `config`, `api`, `instances`, `launcher`, `jre`, `worker.InstallWorker`, `widgets`, `dialogs`, `format`.
- Produces:
  - `app_window.AppWindow(tk.Tk)` con `refresh()` (recarga la biblioteca) y flujo "añadir clave".
  - `server_view.ServerView(parent, server, on_back)` con botón Instalar/Actualizar que lanza `InstallWorker` y consume `poll()` vía `after`.

- [ ] **Step 1: Implementar `mmm/ui/server_view.py`**

```python
"""Vista de detalle de un servidor: instalar/actualizar con progreso."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .. import api, config, instances, jre, launcher
from ..worker import InstallWorker
from . import dialogs
from .format import status_label
from .widgets import ProgressPanel


class ServerView(ttk.Frame):
    def __init__(self, parent, server: dict, on_back):
        super().__init__(parent, padding=16)
        self.server = server
        self.on_back = on_back
        self.worker: InstallWorker | None = None

        ttk.Button(self, text="← Volver", command=on_back).pack(anchor="w")
        ttk.Label(self, text=server["name"], font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(8, 0))
        ttk.Label(self, text=server.get("motd", "")).pack(anchor="w")
        ttk.Label(self, text=f'{server.get("loader","")} {server.get("minecraft_version","")} '
                             f'(loader {server.get("loader_version","")})').pack(anchor="w", pady=(4, 8))

        self.progress = ProgressPanel(self)
        self.progress.pack(fill="x")

        self.action = ttk.Button(self, text="Instalar / Actualizar", command=self._start)
        self.action.pack(pady=8)

        self.hint = ttk.Label(self, text="", wraplength=560, foreground="gray")
        self.hint.pack(anchor="w")

    def _start(self):
        official = config.official_minecraft_dir() or launcher.default_official_dir()
        instance = instances.instance_dir(self.server["slug"], official)
        self.server["instance_path"] = str(instance)
        config.upsert_server(self.server)
        self.action.config(state="disabled")
        self.worker = InstallWorker()
        self.worker.start(self.server, official, jre.java_exe())
        self.after(200, self._poll)

    def _poll(self):
        if not self.worker:
            return
        for kind, kw in self.worker.poll():
            if kind == "status":
                self.progress.set_status(kw["text"])
            elif kind == "progress":
                self.progress.set_progress(kw["done"], kw["total"])
                self.progress.set_status(f'Descargando {kw.get("label","")}…')
            elif kind == "done":
                self.server["installed_version"] = kw["version"]
                config.upsert_server(self.server)
                self.progress.set_status("¡Listo! Abre el launcher oficial y elige el perfil "
                                         f'"{self.server["name"]}".')
                self.hint.config(text="TLauncher/otros: apunta el directorio de juego a "
                                       f'{self.server["instance_path"]} y elige la versión instalada.')
                self.action.config(state="normal")
                return
            elif kind == "error":
                self.progress.set_status("Error en la instalación.")
                dialogs.show_error(self, "Error", kw["message"])
                self.action.config(state="normal")
                return
        self.after(200, self._poll)
```

- [ ] **Step 2: Implementar `mmm/ui/app_window.py`**

```python
"""Ventana principal: biblioteca de servidores."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import api, config, instances, launcher
from . import dialogs
from .server_view import ServerView
from .widgets import ServerRow


class AppWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MakroModManager")
        self.geometry("720x480")
        self.container = ttk.Frame(self)
        self.container.pack(fill="both", expand=True)
        self.refresh()

    def _clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def refresh(self):
        self._clear()
        header = ttk.Frame(self.container, padding=12)
        header.pack(fill="x")
        ttk.Label(header, text="MakroModManager",
                  font=("Segoe UI", 14, "bold")).pack(side="left")

        body = ttk.Frame(self.container, padding=8)
        body.pack(fill="both", expand=True)

        servers = config.list_servers()
        if not servers:
            ttk.Label(body, text="No hay servidores. Añade uno con su clave.").pack(pady=20)
        for server in servers:
            status = self._status_for(server)
            ServerRow(body, server, status, self._open_server).pack(fill="x", pady=2)

        ttk.Button(self.container, text="+ Añadir servidor (clave)",
                   command=self._add_server).pack(pady=10)

    def _status_for(self, server: dict) -> str:
        try:
            info = api.resolve(server["key"])
            return config.server_status(server, info["latest_version"])
        except Exception:
            # sin red o clave caducada: se muestra según lo instalado
            return "al_dia" if server.get("installed_version") else "no_instalado"

    def _add_server(self):
        key = dialogs.ask_key(self)
        if not key:
            return
        try:
            info = api.resolve(key)
        except api.PubError as e:
            msg = "Clave inválida o caducada." if e.status == 403 else str(e)
            dialogs.show_error(self, "No se pudo añadir", msg)
            return
        slug = info.get("server") or info["server_name"].lower().replace(" ", "-")
        server = {
            "slug": slug, "name": info["server_name"], "key": key,
            "loader": info["loader"], "minecraft_version": info["minecraft_version"],
            "loader_version": info["loader_version"], "motd": info.get("motd", ""),
            "installed_version": None,
            "instance_path": str(instances.instance_dir(
                slug, config.official_minecraft_dir() or launcher.default_official_dir())),
        }
        config.upsert_server(server)
        self.refresh()

    def _open_server(self, server: dict):
        self._clear()
        ServerView(self.container, server, on_back=self.refresh).pack(fill="both", expand=True)
```

> Nota: `/pub/resolve` no devuelve el `slug` según el contrato actual; se deriva del `server_name`. Si el panel añade `server` a `resolve`, se usa directamente (ya contemplado con `info.get("server")`).

- [ ] **Step 3: Verificación manual (smoke)**

Run:
```bash
python -c "from mmm.ui.app_window import AppWindow; w=AppWindow(); w.after(500, w.destroy); w.mainloop(); print('OK')"
```
Expected: abre la ventana de biblioteca (vacía), se cierra, imprime `OK`.

- [ ] **Step 4: Commit**

```bash
git add mmm/ui/app_window.py mmm/ui/server_view.py
git commit -m "App cliente: ventana principal (biblioteca) + vista de servidor"
```

---

## Task 15: Punto de entrada + auto-update al arrancar (`__main__.py`)

**Files:**
- Create: `mmm/__main__.py`
- Test: `tests/test_main_helpers.py`

**Interfaces:**
- Consumes: `config`, `updater`, `api`, `version`, `ui.app_window.AppWindow`.
- Produces:
  - `maybe_self_update(local_version, ask, download_and_launch, app_version_fn=api.app_version) -> bool` (testeable; devuelve True si lanzó actualización)
  - `main() -> None`

- [ ] **Step 1: Escribir test del helper**

Create `tests/test_main_helpers.py`:

```python
from mmm import __main__ as m


def test_maybe_self_update_lanza_si_acepta():
    launched = {}
    ok = m.maybe_self_update(
        "1.0.0",
        ask=lambda info: True,
        download_and_launch=lambda info: launched.setdefault("v", info["version"]),
        app_version_fn=lambda: {"version": "2.0.0", "download_url": "/pub/app/download"},
    )
    assert ok is True and launched["v"] == "2.0.0"


def test_maybe_self_update_no_si_rechaza_o_igual():
    assert m.maybe_self_update("2.0.0", ask=lambda i: True,
                               download_and_launch=lambda i: None,
                               app_version_fn=lambda: {"version": "2.0.0"}) is False
    assert m.maybe_self_update("1.0.0", ask=lambda i: False,
                               download_and_launch=lambda i: None,
                               app_version_fn=lambda: {"version": "2.0.0"}) is False
```

- [ ] **Step 2: Ejecutar (debe fallar)**

Run: `python -m pytest tests/test_main_helpers.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementar `mmm/__main__.py`**

```python
"""Arranque de la app: auto-update no bloqueante + ventana principal."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from tkinter import messagebox

from . import api, config, updater
from .version import __version__


def maybe_self_update(local_version, ask, download_and_launch, app_version_fn=api.app_version) -> bool:
    info = updater.check_for_update(local_version, app_version_fn)
    if not info:
        return False
    if not ask(info):
        return False
    download_and_launch(info)
    return True


def _ask(info) -> bool:
    return messagebox.askyesno(
        "Actualización disponible",
        f'Hay una nueva versión ({info["version"]}).\n\n{info.get("notes", "")}\n\n¿Actualizar ahora?',
    )


def _download_and_launch(info) -> None:
    dest = Path(tempfile.gettempdir()) / "MakroModManager_setup.exe"
    api.download_app(dest)
    subprocess.Popen([str(dest)])


def main() -> None:
    # registra la versión actual en el estado
    state = config.load_state()
    state["app_version"] = __version__
    config.save_state(state)

    if maybe_self_update(__version__, _ask, _download_and_launch):
        sys.exit(0)  # el instalador toma el relevo

    from .ui.app_window import AppWindow
    AppWindow().mainloop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar (debe pasar)**

Run: `python -m pytest tests/test_main_helpers.py -v`
Expected: PASS.

- [ ] **Step 5: Verificación manual + suite completa**

Run: `python -m pytest -v` (toda la suite verde).
Run (opcional, requiere red y panel desplegado): `python -m mmm` — abre la app.

- [ ] **Step 6: Commit**

```bash
git add mmm/__main__.py tests/test_main_helpers.py
git commit -m "App cliente: punto de entrada + auto-update al arrancar"
```

---

## Task 16: Empaquetado (PyInstaller + Inno Setup + JRE bundleado)

**Files:**
- Create: `MakroModManager.spec`, `build.bat`, `clean.bat`, `installer.iss`, `INSTRUCCIONES.md`
- Verificación: manual (build real en Windows).

**Interfaces:**
- Consumes: el paquete `mmm/` completo, `assets/icon.ico` (placeholder), `runtime/` (JRE generado por jlink).
- Produces: `installer_output/MakroModManager_setup.exe`.

- [ ] **Step 1: Crear icono placeholder**

Coloca un `assets/icon.ico` provisional (cualquier `.ico` 256×256). Se sustituye cuando el usuario dé el definitivo.

- [ ] **Step 2: Crear `MakroModManager.spec`**

```python
# -*- mode: python ; coding: utf-8 -*-
# Empaqueta la app en dist/MakroModManager/ (onedir).
# El JRE bundleado (carpeta runtime/) se añade como datos junto al exe.

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('runtime', 'runtime')],   # JRE jlink -> se copia junto al exe
    hiddenimports=['tkinter', 'tkinter.ttk'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='MakroModManager',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon='assets/icon.ico',
)
coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, upx_exclude=[], name='MakroModManager',
)
```

- [ ] **Step 3: Crear `run.py`** (entry point para PyInstaller)

```python
from mmm.__main__ import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Crear `clean.bat`**

```bat
@echo off
echo Limpiando compilaciones...
if exist build            rmdir /s /q build
if exist dist             rmdir /s /q dist
if exist installer_output rmdir /s /q installer_output
for /d /r %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
echo Limpieza completada.
pause
```

- [ ] **Step 5: Crear `build.bat`**

```bat
@echo off
setlocal
set PYTHON=python
set INNO="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="C:\Program Files\Inno Setup 6\ISCC.exe"

echo [1/4] Verificando JRE bundleado (runtime\bin\java.exe)...
if not exist "runtime\bin\java.exe" (
    echo [ERROR] Falta la carpeta runtime\ con el JRE.
    echo         Genera el JRE con jlink (ver INSTRUCCIONES.md) antes de compilar.
    pause & exit /b 1
)

echo [2/4] Instalando dependencias...
%PYTHON% -m pip install -r requirements-dev.txt

echo [3/4] Compilando con PyInstaller...
%PYTHON% -m PyInstaller MakroModManager.spec --noconfirm
if %errorlevel% neq 0 ( echo [ERROR] PyInstaller fallo. & pause & exit /b 1 )

echo [4/4] Creando instalador con Inno Setup...
if not exist %INNO% (
    echo [!] Inno Setup no encontrado. El exe esta en dist\MakroModManager\
    pause & exit /b 1
)
call %INNO% installer.iss
if %errorlevel% neq 0 ( echo [ERROR] Inno Setup fallo. & pause & exit /b 1 )

echo LISTO: installer_output\MakroModManager_setup.exe
pause
```

- [ ] **Step 6: Crear `installer.iss`**

```iss
; MakroModManager — Inno Setup
#define AppName    "MakroModManager"
#define AppVersion "1.0.0"
#define AppExe     "MakroModManager.exe"
#define BuildDir   "dist\MakroModManager"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={localappdata}\MakroModManager
DisableProgramGroupPage=yes
DisableDirPage=no
CreateAppDir=yes
DirExistsWarning=no
UsePreviousAppDir=yes
OutputDir=installer_output
OutputBaseFilename=MakroModManager_setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=assets\icon.ico
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ShowLanguageDialog=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir MakroModManager"; Flags: nowait postinstall skipifsilent
```

> Mantener `AppVersion` en el `.iss` sincronizado con `mmm/version.py` en cada release.

- [ ] **Step 7: Crear `INSTRUCCIONES.md`**

```markdown
# MakroModManager — Compilación y publicación

## 1. Generar el JRE bundleado (una vez por versión de Java)

Requiere un JDK 21 instalado. Genera un JRE recortado con jlink en `runtime/`:

```bat
jlink --add-modules java.base,java.desktop,java.logging,java.naming,java.net.http,jdk.crypto.ec,java.security.jgss,java.instrument,java.management,java.sql,jdk.unsupported,jdk.zipfs ^
      --strip-debug --no-header-files --no-man-pages --compress=2 ^
      --output runtime
```

> Verifica: `runtime\bin\java.exe -version`. Los módulos deben cubrir lo que usan
> los *processors* de NeoForge (crypto, zipfs, etc.). Ajusta la lista si el
> instalador de NeoForge falla por un módulo ausente.

## 2. Compilar

```bat
build.bat
```

Genera `installer_output\MakroModManager_setup.exe`.
`clean.bat` borra `build/`, `dist/`, `installer_output/`.

## 3. Publicar en el panel (para el auto-update)

El auto-update lee `/pub/app/version` y descarga `/pub/app/download`, que sirve el
instalador registrado en el panel. Para publicar una versión nueva:

1. Sube `MakroModManager_setup.exe` en el panel: tab **MODPACK** → sección global
   **App cliente** → subir instalador + versión (semver, igual que `mmm/version.py`) + notas.
2. La primera instalación se distribuye a mano (no hay auto-update previo).

## 4. Actualizar la versión

Sube el número en `mmm/version.py` **y** en `AppVersion` de `installer.iss` antes de compilar.
```

- [ ] **Step 8: Verificación manual (build real)**

En Windows con Python 3, JDK 21 e Inno Setup:
1. Genera `runtime/` (paso 1).
2. `build.bat` → produce `installer_output\MakroModManager_setup.exe`.
3. Instala, abre la app, añade una clave real, instala el modpack y comprueba que el
   perfil aparece en el launcher oficial y arranca.

> **Verificación crítica:** confirmar el flag real del instalador NeoForge 21.1.x
> (`--install-client`) y que el JRE recortado completa los *processors* sin error.

- [ ] **Step 9: Commit**

```bash
git add MakroModManager.spec run.py build.bat clean.bat installer.iss INSTRUCCIONES.md assets
git commit -m "App cliente: empaquetado (PyInstaller + Inno Setup + JRE bundleado)"
```

---

## Self-Review (cobertura del spec)

- **Entrada por clave + resolve** → Tasks 2, 12, 14.
- **Instalar/actualizar en instancia aislada (loader + mods + shaders)** → Tasks 4, 8, 9, 11, 14.
- **Biblioteca multi-servidor + estados** → Tasks 3, 12, 14.
- **Integración no destructiva con launcher oficial** → Tasks 5, 11.
- **JRE bundleado / localización de Java** → Tasks 6, 16.
- **Instalador NeoForge headless (dirigido por manifiesto, extensible)** → Tasks 7, 8, 11.
- **Sync mirror + verificación sha256 (no toca saves/config)** → Task 9.
- **Auto-update no bloqueante** → Tasks 10, 15.
- **UI plana** → Tasks 12, 13, 14.
- **Manejo de errores** → Tasks 8 (installer), 9 (sha256/reintentos), 14/15 (UI), 2 (403/404).
- **Empaquetado molde backtask + publicación al panel** → Task 16.

Riesgos pendientes de verificación manual (Task 16): flag exacto del instalador NeoForge y módulos del JRE recortado; ambos anotados en el spec.
