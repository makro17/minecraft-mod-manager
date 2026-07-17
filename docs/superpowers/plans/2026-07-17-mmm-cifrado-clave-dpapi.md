# Cifrado de la clave de distribución con DPAPI (Seguridad #4) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cifrar en reposo el campo `key` (clave de distribución `PPL-…`) de cada servidor en `state.json` usando DPAPI user-scope, de forma transparente para el resto de la app.

**Architecture:** Un módulo nuevo `mmm/secretstore.py` encapsula DPAPI (vía `ctypes` a `crypt32.dll`) exponiendo `protect`/`unprotect`/`CannotDecrypt`. `config.py` aplica el cifrado en el borde de E/S: descifra al cargar y cifra al guardar, de modo que `server["key"]` en memoria es siempre texto plano y ningún consumidor cambia. Si un blob no descifra (state.json de otra máquina/usuario), ese servidor se marca `key_locked` y la UI pide reintroducir la clave.

**Tech Stack:** Python 3.14, stdlib (`ctypes`, `base64`), pytest, Tkinter (UI).

## Global Constraints

- **Sin dependencia nueva:** solo stdlib (`ctypes`, `base64`). `requirements.txt`, `MakroModManager.spec` e `installer.iss` NO cambian.
- **Producción es Windows-only.** En no-Windows, `protect` usa un modo degradado `plain:v1:<b64>` (sin cifrado real) para que la app siga funcionando en desarrollo.
- **Formato de token:** `"dpapi:v1:<base64>"` (Windows) o `"plain:v1:<base64>"` (fallback). El `key` en memoria es SIEMPRE texto plano.
- **Cifrar solo el campo `key`** de cada server; nada más de `state.json`.
- **Tests:** MMM corre con `py -3 -m pytest -q` (Python 3.14). Base actual: **93 verdes**.
- **Artefactos como obra propia:** los mensajes de commit NO mencionan herramientas ni IA; sin `Co-Authored-By`. En español.

---

### Task 1: Módulo `secretstore.py` (DPAPI vía ctypes)

**Files:**
- Create: `mmm/secretstore.py`
- Test: `tests/test_secretstore.py`

**Interfaces:**
- Consumes: nada (solo stdlib).
- Produces:
  - `protect(plaintext: str) -> str` → token `"dpapi:v1:<b64>"` (Windows) o `"plain:v1:<b64>"`.
  - `unprotect(token: str) -> str` → texto plano; lanza `CannotDecrypt`.
  - `class CannotDecrypt(Exception)`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_secretstore.py`:

```python
import sys

import pytest

from mmm import secretstore


def test_round_trip_devuelve_el_texto_original():
    token = secretstore.protect("PPL-ABCD-1234-WXYZ")
    assert token.startswith(("dpapi:v1:", "plain:v1:"))
    assert secretstore.unprotect(token) == "PPL-ABCD-1234-WXYZ"


def test_esquema_desconocido_lanza_cannot_decrypt():
    with pytest.raises(secretstore.CannotDecrypt):
        secretstore.unprotect("PPL-ABCD-1234-WXYZ")  # sin prefijo de esquema


def test_base64_corrupto_lanza_cannot_decrypt():
    with pytest.raises(secretstore.CannotDecrypt):
        secretstore.unprotect("plain:v1:no-es-base64-!!!")


def test_token_dpapi_fuera_de_windows_lanza(monkeypatch):
    monkeypatch.setattr(secretstore.sys, "platform", "linux")
    with pytest.raises(secretstore.CannotDecrypt):
        secretstore.unprotect("dpapi:v1:AAAA")


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI solo existe en Windows")
def test_dpapi_real_es_opaco_y_reversible():
    secreto = "PPL-SECR-ETO0-9999"
    token = secretstore.protect(secreto)
    assert token.startswith("dpapi:v1:")
    assert secreto not in token  # el secreto no aparece en claro en el token
    assert secretstore.unprotect(token) == secreto
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_secretstore.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mmm.secretstore'`.

- [ ] **Step 3: Write minimal implementation**

Create `mmm/secretstore.py`:

```python
"""Cifrado en reposo de secretos con DPAPI (Windows), sin dependencias externas.

En Windows usa CryptProtectData/CryptUnprotectData (user-scope) vía ctypes.
Fuera de Windows degrada a un modo `plain` (sin cifrado) para que la app siga
funcionando en desarrollo; producción es Windows-only.
"""
from __future__ import annotations

import base64
import ctypes
import sys

_DPAPI = "dpapi:v1:"
_PLAIN = "plain:v1:"


class CannotDecrypt(Exception):
    """El token no se pudo descifrar (otra máquina/usuario, o corrupto)."""


def protect(plaintext: str) -> str:
    raw = plaintext.encode("utf-8")
    if sys.platform == "win32":
        blob = _dpapi_transform(raw, _crypt_protect)
        return _DPAPI + base64.b64encode(blob).decode("ascii")
    return _PLAIN + base64.b64encode(raw).decode("ascii")


def unprotect(token: str) -> str:
    if not isinstance(token, str):
        raise CannotDecrypt("el token no es una cadena")
    if token.startswith(_PLAIN):
        return _b64_to_bytes(token[len(_PLAIN):]).decode("utf-8")
    if token.startswith(_DPAPI):
        if sys.platform != "win32":
            raise CannotDecrypt("token dpapi fuera de Windows")
        blob = _b64_to_bytes(token[len(_DPAPI):])
        try:
            raw = _dpapi_transform(blob, _crypt_unprotect)
        except OSError as e:  # llamada ctypes falló
            raise CannotDecrypt("CryptUnprotectData falló") from e
        return raw.decode("utf-8")
    raise CannotDecrypt("esquema de token desconocido")


def _b64_to_bytes(s: str) -> bytes:
    try:
        return base64.b64decode(s, validate=True)
    except Exception as e:  # noqa: BLE001
        raise CannotDecrypt("base64 inválido") from e


# ── DPAPI vía ctypes (solo se ejecuta en Windows) ────────────────────────────
class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _crypt_protect():
    return ctypes.windll.crypt32.CryptProtectData


def _crypt_unprotect():
    return ctypes.windll.crypt32.CryptUnprotectData


def _dpapi_transform(data: bytes, which) -> bytes:
    fn = which()
    buf = ctypes.create_string_buffer(data, len(data))  # mantener viva hasta el return
    blob_in = _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = _DATA_BLOB()
    ok = fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise OSError(ctypes.get_last_error(), "DPAPI falló")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_secretstore.py -q`
Expected: PASS (5 passed en Windows; en no-Windows el último test se marca `skipped`).

- [ ] **Step 5: Commit**

```bash
git add mmm/secretstore.py tests/test_secretstore.py
git commit -m "Seguridad #4 · secretstore: cifrado de secretos con DPAPI (ctypes)"
```

---

### Task 2: `config.py` cifra/descifra la clave en el borde

**Files:**
- Modify: `mmm/config.py` (imports + `load_state` + `save_state` + helpers nuevos)
- Test: `tests/test_config.py` (añadir tests; la fixture `tmp_state` existente se reutiliza)

**Interfaces:**
- Consumes: `secretstore.protect`, `secretstore.unprotect`, `secretstore.CannotDecrypt` (Task 1).
- Produces (comportamiento observable):
  - En disco, `servers[].key` queda como token `dpapi:`/`plain:`.
  - En memoria, `server["key"]` es texto plano; si el token no descifra, `server["key"]=None`, `server["key_locked"]=True`, blob preservado en `server["_key_cipher"]`.

- [ ] **Step 1: Write the failing test**

Añade al final de `tests/test_config.py`:

```python
from mmm import secretstore


@pytest.fixture
def fake_dpapi(monkeypatch):
    """Cifrado reversible y determinista, con prefijo reconocible por config."""
    def protect(s):
        return "dpapi:v1:" + s

    def unprotect(t):
        if not t.startswith("dpapi:v1:"):
            raise secretstore.CannotDecrypt("prefijo malo")
        return t[len("dpapi:v1:"):]

    monkeypatch.setattr(config.secretstore, "protect", protect)
    monkeypatch.setattr(config.secretstore, "unprotect", unprotect)


def _raw_state(tmp_state_dir):
    import json
    return json.loads((tmp_state_dir / "state.json").read_text(encoding="utf-8"))


def test_guardar_cifra_la_clave_en_disco(fake_dpapi):
    config.upsert_server({"slug": "papulandia", "name": "P", "key": "PPL-AAAA-BBBB-CCCC"})
    raw = _raw_state(config.STATE_DIR)
    assert raw["servers"][0]["key"] == "dpapi:v1:PPL-AAAA-BBBB-CCCC"  # token, no plano


def test_cargar_descifra_la_clave(fake_dpapi):
    config.upsert_server({"slug": "papulandia", "name": "P", "key": "PPL-AAAA-BBBB-CCCC"})
    assert config.get_server("papulandia")["key"] == "PPL-AAAA-BBBB-CCCC"


def test_migracion_de_clave_en_claro(fake_dpapi):
    # Simula un state.json legado con la clave en claro (sin prefijo de esquema).
    config.save_state({**config._DEFAULT,
                       "servers": []})  # crea el directorio
    import json
    legacy = {**config._DEFAULT,
              "servers": [{"slug": "papulandia", "name": "P", "key": "PPL-AAAA-BBBB-CCCC"}]}
    config.state_path().write_text(json.dumps(legacy), encoding="utf-8")
    # Al cargar, la clave en claro se deja tal cual (sin prefijo aún).
    st = config.load_state()
    assert st["servers"][0]["key"] == "PPL-AAAA-BBBB-CCCC"
    # Al guardar, se migra a token cifrado.
    config.save_state(st)
    raw = _raw_state(config.STATE_DIR)
    assert raw["servers"][0]["key"].startswith("dpapi:v1:")


def test_clave_ilegible_marca_bloqueado_y_preserva_blob(monkeypatch):
    def unprotect_falla(t):
        raise secretstore.CannotDecrypt("de otra máquina")

    monkeypatch.setattr(config.secretstore, "unprotect", unprotect_falla)
    import json
    stored = {**config._DEFAULT,
              "servers": [{"slug": "papulandia", "name": "P", "key": "dpapi:v1:BLOBORIGINAL"}]}
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    config.state_path().write_text(json.dumps(stored), encoding="utf-8")

    st = config.load_state()
    s = st["servers"][0]
    assert s["key"] is None
    assert s["key_locked"] is True

    # Al re-guardar, el blob original se conserva intacto y no se filtran transitorios.
    config.save_state(st)
    raw = _raw_state(config.STATE_DIR)
    assert raw["servers"][0]["key"] == "dpapi:v1:BLOBORIGINAL"
    assert "key_locked" not in raw["servers"][0]
    assert "_key_cipher" not in raw["servers"][0]


def test_guardar_no_muta_el_estado_en_memoria(fake_dpapi):
    st = {**config._DEFAULT,
          "servers": [{"slug": "papulandia", "name": "P", "key": "PPL-AAAA-BBBB-CCCC"}]}
    config.save_state(st)
    assert st["servers"][0]["key"] == "PPL-AAAA-BBBB-CCCC"  # sigue en claro en memoria
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_config.py -q`
Expected: FAIL — `AttributeError: module 'mmm.config' has no attribute 'secretstore'` (y los asserts nuevos).

- [ ] **Step 3: Write minimal implementation**

En `mmm/config.py`, añade el import (junto a los `import` de arriba):

```python
from . import secretstore
```

Reemplaza `load_state` y `save_state` por estas versiones y añade los helpers justo después de `save_state`:

```python
def load_state() -> dict:
    p = state_path()
    if not p.exists():
        return json.loads(json.dumps(_DEFAULT))
    data = json.loads(p.read_text(encoding="utf-8"))
    for k, v in _DEFAULT.items():
        data.setdefault(k, v)
    for server in data.get("servers", []):
        _decrypt_key(server)
    return data


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    to_write = {**state, "servers": [_encrypt_server(s) for s in state.get("servers", [])]}
    tmp = state_path().with_suffix(".json.tmp")
    tmp.write_text(json.dumps(to_write, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, state_path())


def _decrypt_key(server: dict) -> None:
    """Descifra en sitio el `key` de un server cargado. Deja las claves en claro
    legadas (sin prefijo) intactas para migrarlas al guardar. Si el token no
    descifra, marca el server como bloqueado conservando el blob original."""
    token = server.get("key")
    if not isinstance(token, str) or not token.startswith(("dpapi:", "plain:")):
        return
    try:
        server["key"] = secretstore.unprotect(token)
    except secretstore.CannotDecrypt:
        server["_key_cipher"] = token
        server["key"] = None
        server["key_locked"] = True


def _encrypt_server(server: dict) -> dict:
    """Copia del server lista para persistir: `key` cifrada y transitorios fuera.
    No muta el server en memoria."""
    out = {k: v for k, v in server.items() if k not in ("key_locked", "_key_cipher")}
    if server.get("key_locked") and server.get("_key_cipher"):
        out["key"] = server["_key_cipher"]  # preserva el blob original intacto
        return out
    key = server.get("key")
    if isinstance(key, str) and key:
        out["key"] = secretstore.protect(key)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_config.py -q`
Expected: PASS (todos los tests de config, nuevos y previos).

- [ ] **Step 5: Run the full suite**

Run: `py -3 -m pytest -q`
Expected: PASS — todo verde (base 93 + tests nuevos de Task 1 y Task 2).

- [ ] **Step 6: Commit**

```bash
git add mmm/config.py tests/test_config.py
git commit -m "Seguridad #4 · config: cifra la clave en state.json (migracion + bloqueo)"
```

---

### Task 3: Estado `clave_bloqueada` en `format.py`

**Files:**
- Modify: `mmm/ui/format.py:8-12` (mapa `_STATUS`)
- Test: `tests/test_ui_format.py`

**Interfaces:**
- Consumes: nada.
- Produces: `status_label("clave_bloqueada") == ("🔒", "Reintroduce la clave")`.

- [ ] **Step 1: Write the failing test**

Añade a `tests/test_ui_format.py`:

```python
def test_status_label_clave_bloqueada():
    from mmm.ui.format import status_label
    assert status_label("clave_bloqueada") == ("🔒", "Reintroduce la clave")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_ui_format.py::test_status_label_clave_bloqueada -q`
Expected: FAIL — devuelve `("?", "clave_bloqueada")` (fallback), no la tupla esperada.

- [ ] **Step 3: Write minimal implementation**

En `mmm/ui/format.py`, añade la entrada al dict `_STATUS`:

```python
_STATUS = {
    "no_instalado": ("○", "No instalado"),
    "al_dia": ("●", "Actualizado"),
    "actualizacion": ("⬆", "Actualización disponible"),
    "clave_bloqueada": ("🔒", "Reintroduce la clave"),
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_ui_format.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add mmm/ui/format.py tests/test_ui_format.py
git commit -m "Seguridad #4 · UI: estado 'clave_bloqueada' en format"
```

---

### Task 4: UI — botón "Reintroducir clave" y corte en `_status_for`

**Files:**
- Modify: `mmm/ui/widgets.py:55-92` (`ServerRow`: nuevo parámetro `on_reenter_key` + rama del botón)
- Modify: `mmm/ui/app_window.py` (`_status_for` corta si `key_locked`; llamada a `ServerRow` pasa el callback; método `_reenter_key` nuevo)

**Interfaces:**
- Consumes: `status_label("clave_bloqueada")` (Task 3); `config.upsert_server`, `dialogs.ask_key`, `api.resolve` (existentes); el flag `server["key_locked"]` (Task 2).
- Produces: la fila de un server bloqueado muestra "Reintroducir clave"; al reintroducir, re-cifra y refresca. Sin cambios de firma para otros consumidores de `config`.

> **Nota:** la UI (Tkinter) no es testeable headless. La verificación de esta task es el **smoke import** + la verificación visual manual, que ya está agendada para la fase de recompilación del instalador. No se añaden unit tests aquí.

- [ ] **Step 1: Modificar `ServerRow` en `mmm/ui/widgets.py`**

Cambia la firma del constructor (línea 56) para añadir `on_reenter_key`:

```python
class ServerRow(ttk.Frame):
    def __init__(self, parent, server: dict, status: str, on_open, on_update, on_delete, on_reveal, on_reenter_key):
```

Y reemplaza el bloque del botón de acción izquierdo (actualmente el `if status != "al_dia":`, líneas ~89-92) por:

```python
        if status == "clave_bloqueada":
            ttk.Button(actions, text="Reintroducir clave", width=18,
                       command=lambda: on_reenter_key(server)).pack(side="left", padx=4)
        elif status != "al_dia":
            label = "Instalar" if status == "no_instalado" else "Actualizar"
            ttk.Button(actions, text=label, width=11,
                       command=lambda: on_update(server)).pack(side="left", padx=4)
```

- [ ] **Step 2: Modificar `_status_for` y la llamada a `ServerRow` en `mmm/ui/app_window.py`**

En `_status_for` (línea ~140), corta antes de llamar a la API si el server está bloqueado:

```python
    def _status_for(self, server: dict) -> str:
        if server.get("key_locked"):
            return "clave_bloqueada"
        try:
            info = api.resolve(server["key"])
            # refresca los metadatos cacheados con la versión del modpack publicado
            if config.apply_resolve_meta(server, info):
                config.upsert_server(server)
            return config.server_status(server, info["latest_version"])
        except Exception:
            # sin red o clave caducada: se muestra según lo instalado
            return "al_dia" if server.get("installed_version") else "no_instalado"
```

Actualiza la construcción de `ServerRow` (líneas ~134-135) para pasar el callback nuevo:

```python
            ServerRow(body, server, status, self._open_server,
                      self._update_server, self._delete_server, self._reveal_server,
                      self._reenter_key).pack(fill="x", pady=2)
```

- [ ] **Step 3: Añadir el método `_reenter_key` en `mmm/ui/app_window.py`**

Añádelo junto a los otros callbacks de fila (p. ej. tras `_reveal_server`, ~línea 211):

```python
    def _reenter_key(self, server: dict):
        key = dialogs.ask_key(self)
        if not key:
            return
        try:
            api.resolve(key)
        except api.PubError as e:
            msg = "Clave inválida o caducada." if e.status == 403 else str(e)
            dialogs.show_error(self, "No se pudo actualizar", msg)
            return
        server["key"] = key
        server.pop("key_locked", None)
        server.pop("_key_cipher", None)
        config.upsert_server(server)
        self.refresh()
```

- [ ] **Step 4: Smoke import de la UI**

Run: `py -3 -c "import mmm.ui.widgets, mmm.ui.app_window, mmm.ui.server_view; print('ok')"`
Expected: imprime `ok`, sin trazas (verifica que no hay errores de sintaxis ni de firma).

- [ ] **Step 5: Run the full suite**

Run: `py -3 -m pytest -q`
Expected: PASS — todo verde (los cambios de UI no rompen tests existentes).

- [ ] **Step 6: Commit**

```bash
git add mmm/ui/widgets.py mmm/ui/app_window.py
git commit -m "Seguridad #4 · UI: boton 'Reintroducir clave' para clave bloqueada"
```

---

## Verificación visual manual (fuera de las tasks, en la fase de recompilación)

Al recompilar y probar la app (fase ya agendada), verificar:
- Un servidor normal se lista y funciona igual que antes (la clave sigue resolviendo).
- Inspeccionar `%APPDATA%\MakroModManager\state.json`: el campo `key` de cada server es un token `dpapi:v1:…`, no una `PPL-…` en claro.
- Simular clave bloqueada (editar a mano el `key` de un server a `dpapi:v1:XXXX` inválido) → la fila muestra 🔒 "Reintroduce la clave"; el botón pide la clave y, tras pegar una válida, la fila vuelve a la normalidad y el `state.json` guarda un token nuevo.
