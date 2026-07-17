# Verificación de hash en descargas ejecutables — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El cliente MakroModManager nunca ejecuta un binario descargado (instalador de auto-update, jar de NeoForge) sin verificar antes su sha256 contra un valor de confianza.

**Architecture:** El panel calcula y almacena el sha256 del instalador de la app y lo publica en `/pub/app/version`. El cliente verifica ese hash antes de ejecutar el instalador, y verifica el jar de NeoForge contra el `.sha256` que publica el maven. Un único helper compartido (`mmm/hashing.py`) hace el hashing y la verificación (fail-closed).

**Tech Stack:** Python 3.10 (panel: FastAPI, SQLite), Python 3.14 (cliente: requests, tkinter), pytest en ambos.

## Global Constraints

- **Política fail-closed:** si el hash esperado es vacío/None o no se puede obtener, se **rechaza** y no se ejecuta nada.
- **Panel** — repo `c:\Users\marco\minecraft-server`; tests: `./.venv/Scripts/python.exe -m pytest -q`.
- **Cliente** — repo `C:\Users\marco\proyectos makro\minecraft-mod-manager`; tests: `py -3 -m pytest -q`.
- **Git:** el usuario controla git. Los pasos "Commit" quedan **pendientes de su visto bueno**; no ejecutar `git commit` sin que lo pida.
- **Artefactos como obra propia:** ningún commit/comentario/mensaje menciona Claude/Anthropic ni herramientas de IA. Sin `Co-Authored-By`.
- Los tests existentes de ambos repos deben seguir verdes tras cada tarea.

---

### Task 1: Panel — almacenar sha256 del instalador de la app

**Files:**
- Modify: `app/db.py` (CREATE TABLE `app_release` + migración idempotente)
- Modify: `app/distribution.py` (`publish_app`, `publish_app_stream`)
- Test: `tests/test_distribution.py`

**Interfaces:**
- Produces: `app_release.sha256` (columna TEXT, nullable). `publish_app(version, filename, data) -> dict` y `publish_app_stream(version, filename, upload_file) -> dict` devuelven un dict con clave `"sha256"` = hex sha256 del contenido.

- [ ] **Step 1: Write the failing tests**

En `tests/test_distribution.py`, junto a `test_app_release_latest` (~línea 145):

```python
def test_publish_app_guarda_sha256(tmp_db, monkeypatch):
    monkeypatch.setattr(dist, "app_releases_dir", lambda: tmp_db / "app_releases")
    data = b"exe-bytes"
    row = dist.publish_app("1.0.0", "MMM.exe", data)
    assert row["sha256"] == hashlib.sha256(data).hexdigest()


def test_publish_app_stream_guarda_sha256(tmp_db, monkeypatch):
    from starlette.datastructures import UploadFile
    monkeypatch.setattr(dist, "app_releases_dir", lambda: tmp_db / "app_releases")
    data = b"MZ" + b"\x00" * 3000
    uf = UploadFile(io.BytesIO(data), filename="MMM-setup.exe")
    row = asyncio.run(dist.publish_app_stream("1.2.0", "MMM-setup.exe", uf))
    assert row["sha256"] == hashlib.sha256(data).hexdigest()
```

(`hashlib`, `io`, `asyncio` ya se importan en la sección de streaming del mismo archivo, ~líneas 172-174.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_distribution.py::test_publish_app_guarda_sha256 tests/test_distribution.py::test_publish_app_stream_guarda_sha256 -q`
Expected: FAIL — `KeyError: 'sha256'` (la fila aún no tiene esa columna).

- [ ] **Step 3: Añadir la columna en el schema + migración**

En `app/db.py`, sustituir el `CREATE TABLE IF NOT EXISTS app_release (...)` (líneas 183-190) por:

```python
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_release (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                version            TEXT    NOT NULL,
                installer_path     TEXT    NOT NULL,
                installer_filename TEXT    NOT NULL,
                sha256             TEXT,
                notes              TEXT    NOT NULL DEFAULT '',
                published_at       TEXT    NOT NULL
            )
        """)
        app_cols = {
            r["name"] for r in conn.execute("PRAGMA table_info(app_release)").fetchall()
        }
        if "sha256" not in app_cols:
            conn.execute("ALTER TABLE app_release ADD COLUMN sha256 TEXT")
```

- [ ] **Step 4: Calcular y guardar el sha256 en ambos publish**

En `app/distribution.py`, `publish_app` (líneas 370-386) — añadir el digest y meterlo en el INSERT:

```python
def publish_app(version: str, filename: str, data: bytes) -> dict:
    d = app_releases_dir()
    d.mkdir(parents=True, exist_ok=True)
    filename = Path(filename).name
    dest = d / f"{version}__{filename}"
    dest.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    published_at = _now_iso()
    with db() as conn:
        conn.execute(
            """INSERT INTO app_release (version, installer_path, installer_filename, sha256, notes, published_at)
               VALUES (?, ?, ?, ?, '', ?)""",
            (version, str(dest), filename, digest, published_at),
        )
        row = conn.execute(
            "SELECT * FROM app_release ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return dict(row)
```

En `publish_app_stream` (líneas 389-417) — hashear al vuelo mientras se escriben los trozos:

```python
async def publish_app_stream(version: str, filename: str, upload_file) -> dict:
    d = app_releases_dir()
    d.mkdir(parents=True, exist_ok=True)
    filename = Path(filename).name
    dest = d / f"{version}__{filename}"
    tmp = d / f".{version}__{filename}.{secrets.token_hex(4)}.tmp"
    h = hashlib.sha256()
    try:
        with open(tmp, "wb") as out:
            while True:
                chunk = await upload_file.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                h.update(chunk)
        os.replace(tmp, dest)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    digest = h.hexdigest()
    published_at = _now_iso()
    with db() as conn:
        conn.execute(
            """INSERT INTO app_release (version, installer_path, installer_filename, sha256, notes, published_at)
               VALUES (?, ?, ?, ?, '', ?)""",
            (version, str(dest), filename, digest, published_at),
        )
        row = conn.execute("SELECT * FROM app_release ORDER BY id DESC LIMIT 1").fetchone()
    return dict(row)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_distribution.py -q`
Expected: PASS (los nuevos + todos los previos de distribución).

- [ ] **Step 6: Full panel suite verde**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS (todo).

- [ ] **Step 7: Commit (pendiente de visto bueno del usuario)**

```bash
git add app/db.py app/distribution.py tests/test_distribution.py
git commit -m "Panel · app_release almacena el sha256 del instalador"
```

---

### Task 2: Panel — exponer sha256 en `/pub/app/version`

**Files:**
- Modify: `app/pub_api.py` (`app_version`)
- Test: `tests/test_pub_api.py`

**Interfaces:**
- Consumes: `dist.latest_app()` (dict con clave `"sha256"` de la Task 1).
- Produces: `GET /pub/app/version` → dict con clave `"sha256"` (hex o `None`).

- [ ] **Step 1: Write the failing test**

En `tests/test_pub_api.py`, añadir `import hashlib` al inicio y este test, y ampliar el existente:

```python
def test_app_version_incluye_sha256(tmp_db, monkeypatch):
    monkeypatch.setattr(dist, "app_releases_dir", lambda: tmp_db / "app_releases")
    data = b"installer-bytes"
    dist.publish_app("1.0.0", "MMM.exe", data)
    out = _run(pub_api.app_version())
    assert out["version"] == "1.0.0"
    assert out["sha256"] == hashlib.sha256(data).hexdigest()
```

Y en `test_app_version_sin_release` (línea 43) añadir una aserción:

```python
def test_app_version_sin_release(tmp_db):
    out = _run(pub_api.app_version())
    assert out["version"] is None
    assert out["sha256"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pub_api.py::test_app_version_incluye_sha256 tests/test_pub_api.py::test_app_version_sin_release -q`
Expected: FAIL — `KeyError: 'sha256'` (la respuesta aún no incluye la clave).

- [ ] **Step 3: Devolver sha256 en el endpoint**

En `app/pub_api.py`, `app_version` (líneas 102-111):

```python
@router.get("/app/version")
async def app_version() -> dict:
    latest = dist.latest_app()
    if latest is None:
        return {"version": None, "download_url": None, "sha256": None, "notes": ""}
    return {
        "version": latest["version"],
        "download_url": "/pub/app/download",
        "sha256": latest.get("sha256"),
        "notes": latest.get("notes", ""),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_pub_api.py -q`
Expected: PASS.

- [ ] **Step 5: Full panel suite verde**

Run: `./.venv/Scripts/python.exe -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit (pendiente de visto bueno del usuario)**

```bash
git add app/pub_api.py tests/test_pub_api.py
git commit -m "Panel · /pub/app/version expone el sha256 del instalador"
```

---

### Task 3: Cliente — helper de hashing compartido + consolidar sync

**Files:**
- Create: `mmm/hashing.py`
- Create: `tests/test_hashing.py`
- Modify: `mmm/sync.py` (usar el helper compartido; quitar el `sha256_file` local)
- Test: `tests/test_hashing.py`, `tests/test_sync.py` (debe seguir verde sin cambios)

**Interfaces:**
- Produces: `mmm.hashing.sha256_file(path) -> str`; `mmm.hashing.verify_sha256(path, expected) -> None` (lanza `mmm.hashing.HashInvalido` si `expected` es vacío/None o no coincide, case-insensitive); `mmm.hashing.HashInvalido(Exception)`.

- [ ] **Step 1: Write the failing tests**

Crear `tests/test_hashing.py`:

```python
import hashlib

import pytest

from mmm import hashing


def test_sha256_file(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"contenido")
    assert hashing.sha256_file(p) == hashlib.sha256(b"contenido").hexdigest()


def test_verify_ok_no_lanza(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    hashing.verify_sha256(p, hashlib.sha256(b"x").hexdigest())


def test_verify_mismatch_lanza(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    with pytest.raises(hashing.HashInvalido):
        hashing.verify_sha256(p, "deadbeef")


@pytest.mark.parametrize("vacio", [None, ""])
def test_verify_sin_esperado_falla(tmp_path, vacio):
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    with pytest.raises(hashing.HashInvalido):
        hashing.verify_sha256(p, vacio)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_hashing.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mmm.hashing'`.

- [ ] **Step 3: Crear el módulo**

Crear `mmm/hashing.py`:

```python
"""Hashing y verificación de integridad de archivos descargados."""
from __future__ import annotations

import hashlib
from pathlib import Path


class HashInvalido(Exception):
    """El hash de un archivo no coincide con el esperado (o no hay esperado)."""


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path, expected) -> None:
    """Verifica `path` contra `expected` (hex). Fail-closed: si `expected` es
    vacío/None se considera inválido. Lanza `HashInvalido` si algo no cuadra."""
    if not expected:
        raise HashInvalido("no se proporcionó hash esperado (fail-closed)")
    actual = sha256_file(path)
    if actual.lower() != str(expected).lower():
        raise HashInvalido(f"hash no coincide: esperado {expected}, obtenido {actual}")
```

- [ ] **Step 4: Run hashing tests to verify they pass**

Run: `py -3 -m pytest tests/test_hashing.py -q`
Expected: PASS.

- [ ] **Step 5: Consolidar sync.py**

En `mmm/sync.py`: eliminar `import hashlib` (línea 4) y la función `sha256_file` (líneas 16-21), y añadir el import compartido en la cabecera de imports:

```python
from pathlib import Path

from .hashing import sha256_file
```

(El resto de `sync.py` llama a `sha256_file(...)` sin cambios; ahora resuelve al helper compartido, re-exportado en el namespace de `sync`.)

- [ ] **Step 6: Run sync + hashing tests to verify still green**

Run: `py -3 -m pytest tests/test_sync.py tests/test_hashing.py -q`
Expected: PASS (los 22 de sync + los de hashing, sin cambios de comportamiento).

- [ ] **Step 7: Commit (pendiente de visto bueno del usuario)**

```bash
git add mmm/hashing.py tests/test_hashing.py mmm/sync.py
git commit -m "Cliente · helper de hashing compartido (verify_sha256) + consolidar sync"
```

---

### Task 4: Cliente — verificar el instalador de auto-update antes de ejecutarlo

**Files:**
- Modify: `mmm/__main__.py` (`_download_and_launch` + import de `hashing`)
- Test: `tests/test_main_helpers.py`

**Interfaces:**
- Consumes: `mmm.hashing.verify_sha256`/`HashInvalido` (Task 3); `info["sha256"]` de `/pub/app/version` (Task 2).

- [ ] **Step 1: Write the failing tests**

En `tests/test_main_helpers.py`, añadir al inicio `from pathlib import Path` y estos tests:

```python
def test_download_and_launch_rechaza_hash_malo(tmp_path, monkeypatch):
    dest = tmp_path / "MakroModManager_setup.exe"
    monkeypatch.setattr(m.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(m.api, "download_app",
                        lambda d, progress=None: Path(d).write_bytes(b"malicioso"))
    calls = {"popen": 0}
    monkeypatch.setattr(m.subprocess, "Popen",
                        lambda *a, **k: calls.__setitem__("popen", calls["popen"] + 1))
    monkeypatch.setattr(m.messagebox, "showerror", lambda *a, **k: None)
    m._download_and_launch({"version": "2.0.0", "sha256": "deadbeef"})
    assert calls["popen"] == 0        # nunca se ejecuta
    assert not dest.exists()          # y se borra el archivo descargado


def test_download_and_launch_ok_ejecuta(tmp_path, monkeypatch):
    import hashlib
    data = b"instalador-bueno"
    monkeypatch.setattr(m.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(m.api, "download_app",
                        lambda d, progress=None: Path(d).write_bytes(data))
    calls = {"popen": 0}
    monkeypatch.setattr(m.subprocess, "Popen",
                        lambda *a, **k: calls.__setitem__("popen", calls["popen"] + 1))
    m._download_and_launch({"version": "2.0.0", "sha256": hashlib.sha256(data).hexdigest()})
    assert calls["popen"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_main_helpers.py::test_download_and_launch_rechaza_hash_malo -q`
Expected: FAIL — `Popen` se llama (calls["popen"] == 1) porque aún no hay verificación.

- [ ] **Step 3: Implementar la verificación**

En `mmm/__main__.py`, cambiar el import (línea 10) para incluir `hashing`:

```python
from . import api, config, hashing, updater
```

Y `_download_and_launch` (líneas 31-34):

```python
def _download_and_launch(info) -> None:
    dest = Path(tempfile.gettempdir()) / "MakroModManager_setup.exe"
    api.download_app(dest)
    try:
        hashing.verify_sha256(dest, info.get("sha256"))
    except hashing.HashInvalido as e:
        try:
            dest.unlink()
        except OSError:
            pass
        messagebox.showerror(
            "Actualización cancelada",
            "El instalador descargado no superó la verificación de integridad "
            f"y no se ejecutará.\n\n{e}",
        )
        return
    subprocess.Popen([str(dest)])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_main_helpers.py -q`
Expected: PASS (los 2 nuevos + los 2 previos).

- [ ] **Step 5: Commit (pendiente de visto bueno del usuario)**

```bash
git add mmm/__main__.py tests/test_main_helpers.py
git commit -m "Cliente · verificar sha256 del instalador antes de auto-actualizar"
```

---

### Task 5: Cliente — verificar el jar de NeoForge antes de ejecutarlo

**Files:**
- Modify: `mmm/loaders/neoforge.py` (import de `hashing`, `sha256_url`, `expected_sha256`, verificación en `download_installer`)
- Test: `tests/test_neoforge.py`

**Interfaces:**
- Consumes: `mmm.hashing.verify_sha256`/`HashInvalido` (Task 3).
- Produces: `neoforge.sha256_url(v) -> str`; `neoforge.expected_sha256(v) -> str` (lanza `RuntimeError` si HTTP ≠ 200); `download_installer` deja el jar solo si verifica, si no lo borra y relanza.

- [ ] **Step 1: Write the failing tests**

En `tests/test_neoforge.py`, añadir `from mmm import hashing` al inicio y estos tests:

```python
def test_expected_sha256_parsea(monkeypatch):
    class _R:
        status_code = 200
        text = "  abc123def\n"
    monkeypatch.setattr(neoforge.SESSION, "get", lambda url, timeout=60: _R())
    assert neoforge.expected_sha256("21.1.224") == "abc123def"


def test_expected_sha256_status_no_200_lanza(monkeypatch):
    class _R:
        status_code = 404
        text = ""
    monkeypatch.setattr(neoforge.SESSION, "get", lambda url, timeout=60: _R())
    with pytest.raises(RuntimeError):
        neoforge.expected_sha256("21.1.224")


def test_download_installer_verifica_ok(tmp_path, monkeypatch):
    import hashlib
    data = b"jar-bytes"

    class _R:
        status_code = 200
        def iter_content(self, n):
            yield data

    monkeypatch.setattr(neoforge.SESSION, "get",
                        lambda url, stream=False, timeout=120: _R())
    monkeypatch.setattr(neoforge, "expected_sha256",
                        lambda ver: hashlib.sha256(data).hexdigest())
    dest = tmp_path / "inst.jar"
    neoforge.download_installer("21.1.224", dest)
    assert dest.read_bytes() == data


def test_download_installer_hash_malo_borra_y_lanza(tmp_path, monkeypatch):
    data = b"jar-bytes"

    class _R:
        status_code = 200
        def iter_content(self, n):
            yield data

    monkeypatch.setattr(neoforge.SESSION, "get",
                        lambda url, stream=False, timeout=120: _R())
    monkeypatch.setattr(neoforge, "expected_sha256", lambda ver: "deadbeef")
    dest = tmp_path / "inst.jar"
    with pytest.raises(hashing.HashInvalido):
        neoforge.download_installer("21.1.224", dest)
    assert not dest.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_neoforge.py::test_expected_sha256_parsea -q`
Expected: FAIL — `AttributeError: module 'mmm.loaders.neoforge' has no attribute 'expected_sha256'`.

- [ ] **Step 3: Implementar checksum + verificación**

En `mmm/loaders/neoforge.py`, añadir el import (tras `from .. import procutil`, línea 9):

```python
from .. import hashing, procutil
```

Añadir las funciones de checksum (tras `installer_url`, línea 23):

```python
def sha256_url(loader_version: str) -> str:
    return installer_url(loader_version) + ".sha256"


def expected_sha256(loader_version: str) -> str:
    r = SESSION.get(sha256_url(loader_version), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(
            f"No se pudo obtener el checksum de NeoForge (HTTP {r.status_code})."
        )
    return r.text.strip()
```

Y verificar al final de `download_installer` (líneas 31-39):

```python
def download_installer(loader_version: str, dest: Path) -> None:
    r = SESSION.get(installer_url(loader_version), stream=True, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"No se pudo descargar el instalador de NeoForge (HTTP {r.status_code}).")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 16):
            if chunk:
                f.write(chunk)
    try:
        hashing.verify_sha256(dest, expected_sha256(loader_version))
    except (hashing.HashInvalido, RuntimeError):
        try:
            dest.unlink()
        except OSError:
            pass
        raise
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_neoforge.py -q`
Expected: PASS (los 4 nuevos + los 5 previos; los previos monkeypatchean `download_installer` entero, así no tocan la verificación real).

- [ ] **Step 5: Full client suite verde**

Run: `py -3 -m pytest -q`
Expected: PASS (todo).

- [ ] **Step 6: Commit (pendiente de visto bueno del usuario)**

```bash
git add mmm/loaders/neoforge.py tests/test_neoforge.py
git commit -m "Cliente · verificar sha256 del jar de NeoForge antes de ejecutarlo"
```

---

## Seguimiento manual (post-implementación, acción del usuario)

No son tareas TDD; se listan para no perderlas:

1. **Deploy panel** (por LAN `192.168.0.183`): `scp app/db.py app/distribution.py app/pub_api.py root@192.168.0.183:/opt/papulandia-panel/app/` + `systemctl restart papulandia-panel.service`. La migración `app_release.sha256` corre al reiniciar (idempotente).
2. **Recompilar el instalador del cliente** una sola vez (incluye también Seguridad #1 y el reorden de UI ya hechos): `py -3 -m PyInstaller MakroModManager.spec --noconfirm` + `& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss` → `installer_output\`. Subir versión en `mmm/version.py` + `installer.iss` **solo si** ya hay una publicada anterior.
3. **Republicar** por la UI del panel (MODPACK → App cliente → subir el `.exe`). El panel calculará y guardará el sha256; el auto-update ya lo verificará.
4. **Verificación end-to-end de NeoForge** (`--install-client` 21.1.x) sigue pendiente aparte (no cubierto por estos tests unitarios).

## Self-review

- **Cobertura del spec:** #2 panel (Task 1 storage + Task 2 endpoint), #2 cliente (Task 4), #3 (Task 5), consolidación del helper (Task 3), fail-closed (verify_sha256 + tests en Tasks 3/4/5). ✓
- **Placeholders:** ninguno; todo el código está explícito. ✓
- **Consistencia de tipos:** `verify_sha256(path, expected)`, `HashInvalido`, `expected_sha256(loader_version)`, `sha256_url` usados igual en todas las tareas. ✓
