# C4 · Onboarding ZeroTier con elevación — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que MMM obtenga permisos de administrador bajo demanda (un solo UAC) e instale ZeroTier automáticamente, de modo que un usuario no técnico complete el onboarding sin salir de la app.

**Architecture:** Nuevo módulo `mmm/elevation.py` (detección de elevación + relanzamiento vía `ShellExecuteW "runas"`, todo aislado tras `_shell32()` para poder mockearlo en cualquier SO). `mmm/zerotier.py` gana `MSI_URL` + `install(download, run, sleep, …)` con dependencias inyectables (descarga la MSI oficial, lanza `msiexec /qn /norestart`, hace polling de `is_installed()`). La UI añade una puerta de elevación en la sección ZeroTier de `ServerView` (no se consulta `zerotier-cli` sin permisos, para no mostrar un falso "no instalado") y sustituye el `webbrowser.open` de `zt_dialog.ensure_access` por auto-instalación con diálogo de progreso y fallback a la página.

**Tech Stack:** Python 3.14, Tkinter/ttk, `ctypes` (shell32), `requests`, pytest, PyInstaller + Inno Setup.

**Spec de referencia:** `docs/superpowers/specs/2026-07-18-c4-onboarding-zerotier-elevacion-design.md`

## Global Constraints

- Repo: `C:\Users\marco\proyectos makro\minecraft-mod-manager`, rama `main`.
- Tests: `py -3 -m pytest -q` (104 verdes antes de empezar). TDD estricto: test que falla → implementación mínima → test verde → commit.
- La GUI (Tkinter) no es testeable headless: para los cambios de UI la verificación es el smoke import `py -3 -c "import mmm.ui.widgets, mmm.ui.server_view, mmm.ui.app_window, mmm.ui.zt_dialog, mmm.ui.dialogs"` + verificación visual manual posterior.
- Windows-only real; en no-Windows las funciones degradan a defaults mockeables (nunca romper los tests en otra plataforma).
- URL de la MSI, literal: `https://download.zerotier.com/dist/ZeroTier%20One.msi`. Sin sha256 pin (ZeroTier re-publica la MSI).
- Comando de instalación, literal: `msiexec /i <ruta.msi> /qn /norestart`.
- Fallback siempre disponible: si algo falla, abrir `https://www.zerotier.com/download/` (constante `zt_dialog.DOWNLOAD_URL`).
- **Sin cambios en `MakroModManager.spec`** (elevación por relanzamiento en runtime, no manifest).
- Versión final: **1.2.0** en `mmm/version.py` e `installer.iss`.
- Todo el texto de UI, comentarios y mensajes de commit en español. **Nunca** mencionar herramientas de IA ni añadir `Co-Authored-By` en los commits.

---

### Task 1: `mmm/elevation.py` — detección de elevación y relanzamiento

**Files:**
- Create: `mmm/elevation.py`
- Test: `tests/test_elevation.py`

**Interfaces:**
- Consumes: `mmm.jre.is_frozen() -> bool` (ya existe, `mmm/jre.py:9`).
- Produces:
  - `elevation.is_elevated() -> bool`
  - `elevation.relaunch_as_admin() -> bool`
  - `elevation._shell32()` (punto de mock en tests)
  - `elevation.SW_SHOWNORMAL = 1`

- [ ] **Step 1: Escribir el test que falla**

Crear `tests/test_elevation.py`:

```python
"""C4 · elevación bajo demanda (Windows)."""
from mmm import elevation


class FakeShell:
    """Doble de `shell32`: registra las llamadas y devuelve códigos fijos."""

    def __init__(self, admin=1, rc=42):
        self.admin = admin
        self.rc = rc
        self.calls = []

    def IsUserAnAdmin(self):
        return self.admin

    def ShellExecuteW(self, hwnd, verb, file, params, cwd, show):
        self.calls.append((hwnd, verb, file, params, cwd, show))
        return self.rc


def _win(monkeypatch, shell, frozen=True):
    """Simula Windows + app empaquetada, con shell32 mockeado."""
    monkeypatch.setattr(elevation.sys, "platform", "win32")
    monkeypatch.setattr(elevation, "_shell32", lambda: shell)
    monkeypatch.setattr(elevation, "is_frozen", lambda: frozen)


def test_is_elevated_true(monkeypatch):
    _win(monkeypatch, FakeShell(admin=1))
    assert elevation.is_elevated() is True


def test_is_elevated_false(monkeypatch):
    _win(monkeypatch, FakeShell(admin=0))
    assert elevation.is_elevated() is False


def test_is_elevated_fuera_de_windows(monkeypatch):
    monkeypatch.setattr(elevation.sys, "platform", "linux")
    assert elevation.is_elevated() is False


def test_is_elevated_error_no_rompe(monkeypatch):
    class Boom:
        def IsUserAnAdmin(self):
            raise OSError("no shell32")

    _win(monkeypatch, Boom())
    assert elevation.is_elevated() is False


def test_relaunch_lanza_runas_y_devuelve_true(monkeypatch):
    shell = FakeShell(rc=42)
    _win(monkeypatch, shell)
    monkeypatch.setattr(elevation.sys, "executable", r"C:\app\MakroModManager.exe")
    monkeypatch.setattr(elevation.sys, "argv", [r"C:\app\MakroModManager.exe"])
    assert elevation.relaunch_as_admin() is True
    hwnd, verb, file, params, cwd, show = shell.calls[0]
    assert verb == "runas"
    assert file == r"C:\app\MakroModManager.exe"
    assert params is None
    assert show == elevation.SW_SHOWNORMAL


def test_relaunch_conserva_argumentos(monkeypatch):
    shell = FakeShell(rc=42)
    _win(monkeypatch, shell)
    monkeypatch.setattr(elevation.sys, "executable", r"C:\app\MakroModManager.exe")
    monkeypatch.setattr(elevation.sys, "argv", [r"C:\app\MakroModManager.exe", "--foo", "bar baz"])
    assert elevation.relaunch_as_admin() is True
    assert shell.calls[0][3] == '--foo "bar baz"'


def test_relaunch_uac_cancelado(monkeypatch):
    # ShellExecuteW devuelve <= 32 → error (5 = acceso denegado / UAC cancelado).
    _win(monkeypatch, FakeShell(rc=5))
    assert elevation.relaunch_as_admin() is False


def test_relaunch_en_dev_no_hace_nada(monkeypatch):
    shell = FakeShell(rc=42)
    _win(monkeypatch, shell, frozen=False)
    assert elevation.relaunch_as_admin() is False
    assert shell.calls == []


def test_relaunch_fuera_de_windows(monkeypatch):
    shell = FakeShell(rc=42)
    _win(monkeypatch, shell)
    monkeypatch.setattr(elevation.sys, "platform", "linux")
    assert elevation.relaunch_as_admin() is False
    assert shell.calls == []


def test_relaunch_error_no_rompe(monkeypatch):
    class Boom:
        def ShellExecuteW(self, *a):
            raise OSError("fallo")

    _win(monkeypatch, Boom())
    assert elevation.relaunch_as_admin() is False
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

Run: `py -3 -m pytest tests/test_elevation.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'mmm.elevation'` (error de colección).

- [ ] **Step 3: Implementación mínima**

Crear `mmm/elevation.py`:

```python
"""C4 · elevación bajo demanda.

La app arranca como usuario normal (`asInvoker`): gestionar modpacks no pide
permisos. En Windows, TODAS las operaciones de ZeroTier (info/listnetworks/
join/leave) necesitan administrador, así que cuando hacen falta relanzamos la
propia app elevada (un solo UAC) en vez de exigir permisos en cada arranque.
"""
from __future__ import annotations

import ctypes
import subprocess
import sys

from .jre import is_frozen

SW_SHOWNORMAL = 1


def _shell32():
    """Handle de shell32, aislado para poder mockearlo en los tests."""
    return ctypes.windll.shell32


def is_elevated() -> bool:
    """True si el proceso corre con permisos de administrador."""
    if sys.platform != "win32":
        return False
    try:
        return bool(_shell32().IsUserAnAdmin())
    except Exception:  # noqa: BLE001 — sin shell32 asumimos «sin permisos»
        return False


def relaunch_as_admin() -> bool:
    """Relanza la app elevada. True si el relanzamiento arrancó.

    El llamador debe cerrar esta instancia si devuelve True. Devuelve False si
    el usuario canceló el UAC, si falló, o si estamos en dev/no-Windows (donde
    no hay un .exe que relanzar): en ese caso se avisa al usuario.
    """
    if sys.platform != "win32" or not is_frozen():
        return False
    params = subprocess.list2cmdline(sys.argv[1:]) or None
    try:
        rc = _shell32().ShellExecuteW(None, "runas", sys.executable, params, None, SW_SHOWNORMAL)
    except Exception:  # noqa: BLE001
        return False
    return int(rc) > 32
```

- [ ] **Step 4: Ejecutar los tests y ver que pasan**

Run: `py -3 -m pytest tests/test_elevation.py -q`
Expected: PASS (10 tests).

Run también la suite completa: `py -3 -m pytest -q`
Expected: 114 passed.

- [ ] **Step 5: Commit**

```bash
git add mmm/elevation.py tests/test_elevation.py
git commit -m "C4: deteccion de elevacion y relanzamiento como administrador"
```

---

### Task 2: `zerotier.install` — descarga e instalación silenciosa de la MSI

**Files:**
- Modify: `mmm/zerotier.py` (añadir al final: `MSI_URL`, `download_msi`, `run_installer`, `install`)
- Test: `tests/test_zerotier.py` (añadir tests al final)

**Interfaces:**
- Consumes: `zerotier.is_installed()`, `procutil.no_window_kwargs()` (ya existen).
- Produces:
  - `zerotier.MSI_URL: str`
  - `zerotier.download_msi(url: str, dest: Path) -> None`
  - `zerotier.run_installer(cmd: list[str]) -> int` (devuelve el returncode)
  - `zerotier.install(download=download_msi, run=run_installer, sleep=time.sleep, *, url=MSI_URL, attempts=20, delay=1.0) -> bool`

- [ ] **Step 1: Escribir los tests que fallan**

Añadir al final de `tests/test_zerotier.py` (el fichero ya importa `subprocess`, `sys`, y `from mmm import api, zerotier`; añadir arriba `from pathlib import Path` y `import pytest`):

```python
def _fake_download(store):
    def download(url, dest):
        store["url"] = url
        store["dest"] = Path(dest)
        Path(dest).write_bytes(b"msi")
    return download


def test_install_ok(monkeypatch):
    store = {}

    def run(cmd):
        store["cmd"] = cmd
        return 0

    monkeypatch.setattr(zerotier, "is_installed", lambda: True)
    assert zerotier.install(_fake_download(store), run, sleep=lambda s: None) is True
    assert store["url"] == zerotier.MSI_URL
    assert store["cmd"][0] == "msiexec"
    assert store["cmd"][1] == "/i"
    assert store["cmd"][2].endswith(".msi")
    assert store["cmd"][3:] == ["/qn", "/norestart"]


def test_install_hace_polling_hasta_que_aparece_el_cli(monkeypatch):
    store = {}
    sleeps = []
    llamadas = {"n": 0}

    def is_installed():
        llamadas["n"] += 1
        return llamadas["n"] >= 3

    monkeypatch.setattr(zerotier, "is_installed", is_installed)
    ok = zerotier.install(_fake_download(store), lambda cmd: 0, sleep=sleeps.append, attempts=5, delay=0.5)
    assert ok is True
    assert sleeps == [0.5, 0.5]  # durmió entre los 3 intentos


def test_install_timeout(monkeypatch):
    store = {}
    sleeps = []
    monkeypatch.setattr(zerotier, "is_installed", lambda: False)
    ok = zerotier.install(_fake_download(store), lambda cmd: 0, sleep=sleeps.append, attempts=3, delay=1.0)
    assert ok is False
    assert len(sleeps) == 3


def test_install_msiexec_codigo_distinto_de_cero(monkeypatch):
    store = {}
    monkeypatch.setattr(zerotier, "is_installed", lambda: pytest.fail("no debe consultarse"))
    assert zerotier.install(_fake_download(store), lambda cmd: 1618, sleep=lambda s: None) is False


def test_install_error_de_descarga_propaga():
    def download(url, dest):
        raise RuntimeError("sin red")

    with pytest.raises(RuntimeError):
        zerotier.install(download, lambda cmd: 0, sleep=lambda s: None)


def test_run_installer_evita_ventana_de_consola(monkeypatch):
    captured = {}

    class R:
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: (captured.update(kw), R())[1])
    assert zerotier.run_installer(["msiexec", "/i", "x.msi"]) == 0
    if sys.platform == "win32":
        assert captured.get("creationflags", 0) & subprocess.CREATE_NO_WINDOW
    else:
        assert "creationflags" not in captured
```

- [ ] **Step 2: Ejecutar los tests y ver que fallan**

Run: `py -3 -m pytest tests/test_zerotier.py -q`
Expected: FAIL — `AttributeError: module 'mmm.zerotier' has no attribute 'MSI_URL'` / `install`.

- [ ] **Step 3: Implementación mínima**

En `mmm/zerotier.py`, añadir a los imports de cabecera:

```python
import tempfile
import time

import requests
```

(quedando junto a los ya existentes `shutil`, `subprocess`, `Path`, `Optional`, `procutil`).

Y añadir al final del fichero:

```python
# Instalador oficial. Sin sha256 pin: ZeroTier re-publica la MSI en cada versión
# y habría que re-pinar el hash; HTTPS da la integridad de transporte.
MSI_URL = "https://download.zerotier.com/dist/ZeroTier%20One.msi"


def download_msi(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                if chunk:
                    f.write(chunk)


def run_installer(cmd: list[str]) -> int:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=600, **procutil.no_window_kwargs()
    ).returncode


def install(download=download_msi, run=run_installer, sleep=time.sleep, *,
            url: str = MSI_URL, attempts: int = 20, delay: float = 1.0) -> bool:
    """Instala ZeroTier en silencio. True si el CLI aparece antes del timeout.

    Requiere que el proceso ya esté elevado (así no hay un segundo UAC).
    `download`/`run`/`sleep` son inyectables para los tests.
    """
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "ZeroTierOne.msi"
        download(url, dest)
        if run(["msiexec", "/i", str(dest), "/qn", "/norestart"]) != 0:
            return False
    # El servicio tarda un poco en dejar el CLI en su sitio: polling.
    for _ in range(attempts):
        if is_installed():
            return True
        sleep(delay)
    return False
```

- [ ] **Step 4: Ejecutar los tests y ver que pasan**

Run: `py -3 -m pytest tests/test_zerotier.py -q`
Expected: PASS.

Run: `py -3 -m pytest -q`
Expected: 120 passed.

- [ ] **Step 5: Commit**

```bash
git add mmm/zerotier.py tests/test_zerotier.py
git commit -m "C4: instalacion silenciosa de ZeroTier desde la MSI oficial"
```

---

### Task 3: Diálogo de progreso modal (`dialogs.run_busy`) + auto-instalación en `zt_dialog`

**Files:**
- Modify: `mmm/ui/dialogs.py` (añadir `run_busy`)
- Modify: `mmm/ui/zt_dialog.py:32-39` (rama `not_installed`)

**Interfaces:**
- Consumes: `zerotier.install()` (Task 2).
- Produces: `dialogs.run_busy(parent, title, message, fn) -> tuple[object | None, Exception | None]` — ejecuta `fn()` en un hilo mostrando un modal indeterminado; devuelve `(resultado, error)`.

No hay test automático posible (Tkinter necesita display); la verificación es el smoke import y la prueba manual del Task 6.

- [ ] **Step 1: Añadir `run_busy` a `mmm/ui/dialogs.py`**

Cambiar la cabecera del fichero a:

```python
"""Diálogos tkinter: añadir clave, errores, espera modal."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from .format import valid_key
```

Y añadir al final:

```python
def run_busy(parent, title: str, message: str, fn):
    """Ejecuta `fn()` en un hilo con un modal indeterminado. Devuelve (resultado, error)."""
    top = tk.Toplevel(parent)
    top.title(title)
    top.transient(parent)
    top.resizable(False, False)
    top.protocol("WM_DELETE_WINDOW", lambda: None)  # no cancelable: dejaría el MSI a medias
    ttk.Label(top, text=message, padding=16).pack()
    bar = ttk.Progressbar(top, mode="indeterminate", length=280)
    bar.pack(padx=16, pady=(0, 16))
    bar.start(12)
    top.grab_set()

    box: dict = {}

    def work():
        try:
            box["result"] = fn()
        except Exception as e:  # noqa: BLE001 — se devuelve al llamador
            box["error"] = e
        finally:
            top.after(0, top.destroy)

    threading.Thread(target=work, daemon=True).start()
    parent.wait_window(top)
    return box.get("result"), box.get("error")
```

- [ ] **Step 2: Sustituir la rama `not_installed` en `mmm/ui/zt_dialog.py`**

Cambiar el import de cabecera a:

```python
from .. import api, config, zerotier
from . import dialogs
```

Y sustituir el bloque `if state == "not_installed": …` (líneas 32-39) por:

```python
    if state == "not_installed":
        if not messagebox.askyesno(
            "ZeroTier no instalado",
            "Necesitas ZeroTier para conectar a este servidor.\n"
            "¿Lo instalo ahora? (tarda un minuto, no hace falta que toques nada)",
            parent=parent,
        ):
            return
        ok, error = dialogs.run_busy(
            parent, "Instalando ZeroTier", "Descargando e instalando ZeroTier…", zerotier.install
        )
        if error is not None or not ok:
            detalle = f"\n\n({error})" if error is not None else ""
            messagebox.showerror(
                "ZeroTier",
                "No pude instalar ZeroTier automáticamente. Abro la página de descarga "
                "para que lo instales a mano." + detalle,
                parent=parent,
            )
            webbrowser.open(DOWNLOAD_URL)
            return
        # Ya instalado: reevalúa el estado y sigue el onboarding normal (join → solicitud).
        return ensure_access(parent, key)
```

- [ ] **Step 3: Smoke import**

Run: `py -3 -c "import mmm.ui.dialogs, mmm.ui.zt_dialog"`
Expected: sin salida (exit 0).

- [ ] **Step 4: Suite completa**

Run: `py -3 -m pytest -q`
Expected: 120 passed (sin regresiones).

- [ ] **Step 5: Commit**

```bash
git add mmm/ui/dialogs.py mmm/ui/zt_dialog.py
git commit -m "C4: instalar ZeroTier desde la app con progreso y fallback a la pagina"
```

---

### Task 4: Puerta de elevación en la sección ZeroTier de `ServerView`

**Files:**
- Modify: `mmm/ui/server_view.py:8` (import), `:137-146` (`_poll_zt`), y añadir `_show_elevation_gate` / `_restart_elevated`

**Interfaces:**
- Consumes: `elevation.is_elevated()`, `elevation.relaunch_as_admin()` (Task 1); `self._set_zt_button(text, command)` (ya existe en `server_view.py:148`).
- Produces: nada para tareas posteriores.

- [ ] **Step 1: Importar `elevation`**

En `mmm/ui/server_view.py:8`, cambiar:

```python
from .. import api, config, instances, jre, launcher, zerotier
```

por:

```python
from .. import api, config, elevation, instances, jre, launcher, zerotier
```

- [ ] **Step 2: Añadir la puerta en `_poll_zt`**

Sustituir `_poll_zt` (líneas 137-146) por:

```python
    def _poll_zt(self):
        if not self.winfo_exists():
            return
        # Sin permisos, `zerotier-cli` no puede leer authtoken.secret y todo
        # parecería «no instalado»: mejor no consultarlo y pedir la elevación.
        if not elevation.is_elevated():
            self._show_elevation_gate()
            return

        def run():
            state = zerotier.access_status()
            if self.winfo_exists():
                self.after(0, lambda: self._apply_zt_state(state))

        threading.Thread(target=run, daemon=True).start()
```

- [ ] **Step 3: Añadir los métodos de la puerta**

Justo después de `_set_zt_button` (antes de `_apply_zt_state`), añadir:

```python
    def _show_elevation_gate(self):
        self.zt_status.config(
            text="ZeroTier: para gestionar la red necesito permisos de administrador",
            foreground="#b0894a",
        )
        self._set_zt_button("Reiniciar con permisos", self._restart_elevated)
        # No se reprograma el polling: la elevación solo cambia reiniciando la app.

    def _restart_elevated(self):
        if elevation.relaunch_as_admin():
            self.winfo_toplevel().destroy()
            return
        from tkinter import messagebox
        messagebox.showerror(
            "Permisos",
            "No se obtuvieron permisos de administrador. Cierra la app y ábrela con "
            "«Ejecutar como administrador».",
            parent=self,
        )
```

- [ ] **Step 4: Smoke import**

Run: `py -3 -c "import mmm.ui.widgets, mmm.ui.server_view, mmm.ui.app_window, mmm.ui.zt_dialog, mmm.ui.dialogs"`
Expected: sin salida (exit 0).

- [ ] **Step 5: Suite completa**

Run: `py -3 -m pytest -q`
Expected: 120 passed.

- [ ] **Step 6: Commit**

```bash
git add mmm/ui/server_view.py
git commit -m "C4: puerta de elevacion en la seccion ZeroTier del detalle de servidor"
```

---

### Task 5: Subir versión a 1.2.0 (con guarda de coherencia)

**Files:**
- Modify: `mmm/version.py:2`
- Modify: `installer.iss:3`
- Test: `tests/test_version.py`

**Interfaces:**
- Consumes: `mmm.__version__`.
- Produces: nada.

- [ ] **Step 1: Escribir el test que falla**

Sustituir `tests/test_version.py` por:

```python
import re
from pathlib import Path

import mmm


def test_version_semver():
    assert re.match(r"^\d+\.\d+\.\d+$", mmm.__version__)


def test_installer_iss_usa_la_misma_version():
    """El .iss y mmm/version.py deben ir a la par: el auto-update compara esta versión."""
    iss = Path(__file__).resolve().parents[1] / "installer.iss"
    m = re.search(r'#define\s+AppVersion\s+"([^"]+)"', iss.read_text(encoding="utf-8"))
    assert m, "no encontré AppVersion en installer.iss"
    assert m.group(1) == mmm.__version__


def test_version_minima_1_2_0():
    """C4 se publica como 1.2.0 (ya hay una 1.1.0 publicada)."""
    partes = tuple(int(p) for p in mmm.__version__.split("."))
    assert partes >= (1, 2, 0)
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

Run: `py -3 -m pytest tests/test_version.py -q`
Expected: FAIL en `test_version_minima_1_2_0` — `assert (1, 1, 0) >= (1, 2, 0)`.

- [ ] **Step 3: Subir la versión**

`mmm/version.py` línea 2:

```python
__version__ = "1.2.0"
```

`installer.iss` línea 3:

```
#define AppVersion "1.2.0"
```

- [ ] **Step 4: Ejecutar los tests y ver que pasan**

Run: `py -3 -m pytest -q`
Expected: 122 passed.

- [ ] **Step 5: Commit**

```bash
git add mmm/version.py installer.iss tests/test_version.py
git commit -m "Version 1.2.0 (onboarding ZeroTier)"
```

---

### Task 6: Recompilar, verificar a mano y publicar

Sin código. Pasos manuales del usuario (ejecutar desde `C:\Users\marco\proyectos makro\minecraft-mod-manager`).

- [ ] **Step 1: Suite completa antes de compilar**

Run: `py -3 -m pytest -q`
Expected: 122 passed.

- [ ] **Step 2: Compilar el ejecutable y el instalador**

```powershell
py -3 -m PyInstaller --noconfirm MakroModManager.spec
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```
Expected: `installer_output\MakroModManager_setup.exe` regenerado.

- [ ] **Step 3: Verificación visual (instalando el setup recién hecho)**

1. Abrir la app **sin** elevar → entrar en un servidor: la sección ZeroTier debe decir *"para gestionar la red necesito permisos de administrador"* con el botón **"Reiniciar con permisos"** (y ningún estado falso de "no instalado").
2. Pulsar el botón → **un solo UAC** → la app se cierra y reabre elevada; la sección ZeroTier ya muestra el estado real.
3. Cancelar el UAC en otra prueba → la app sigue abierta y muestra el aviso de permisos.
4. En una máquina/VM sin ZeroTier: pulsar "Unirse a la red" → confirmar → modal "Instalando ZeroTier…" → al terminar continúa el onboarding (nombre → join → solicitud enviada).
5. Pendientes arrastrados de la sesión anterior: IP + botón Copiar en filas y detalle; scroll del detalle con la ventana pequeña; `%APPDATA%\MakroModManager\state.json` con la clave como token `dpapi:v1:…` y el estado 🔒 al corromper el token.

- [ ] **Step 4: Publicar**

Subir `installer_output\MakroModManager_setup.exe` por la UI del panel (MODPACK → App cliente). El auto-update ofrecerá 1.2.0 a los clientes en 1.1.0, verificando el sha256.

- [ ] **Step 5: Push**

```bash
git push origin main
```

---

## Notas de cierre

- Sin cambios en el panel ni en `MakroModManager.spec`.
- Queda fuera de este plan (cola aplazada): firmar el instalador (Seg #5), NeoForge `--install-client` 21.1.x end-to-end, restyle del panel.
