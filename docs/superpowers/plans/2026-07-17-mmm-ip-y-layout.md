# MMM: IP en lista/detalles + fix de layout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mostrar y copiar la dirección del servidor en la lista y en los detalles de MakroModManager, y evitar que se corten los botones en detalles con la ventana pequeña.

**Architecture:** El panel expone la dirección (`host`/`port`/`address`) en `/pub/resolve`; MMM la cachea vía `apply_resolve_meta` y la pinta con un widget reutilizable `AddressBar` (con botón Copiar) en la lista y en los detalles. El layout de detalles se envuelve en un Canvas scrolleable y la ventana raíz gana un `minsize`.

**Tech Stack:** Panel: Python 3.10 + FastAPI (repo `c:\Users\marco\minecraft-server`). MMM: Python + Tkinter (repo `C:\Users\marco\proyectos makro\minecraft-mod-manager`).

## Global Constraints

- **Dos repos.** Task 1 se ejecuta en el **panel** (`c:\Users\marco\minecraft-server`); Tasks 2-4 en **MMM** (`C:\Users\marco\proyectos makro\minecraft-mod-manager`). Cada comando indica su CWD.
- Tests panel: `./.venv/Scripts/python.exe -m pytest -q` (desde el repo del panel).
- Tests MMM: `py -3 -m pytest -q` (desde el repo de MMM).
- MMM GUI no testeable headless → smoke de imports `py -3 -c "import mmm.ui.widgets, mmm.ui.server_view, mmm.ui.app_window"`.
- Formato de dirección: `host:port` siempre; si no hay host, `address = None`.
- Commits en **español**, estilo `MMM · …` (repo MMM) y `Panel · …` (repo panel). **NUNCA** mencionar Claude/Anthropic ni `Co-Authored-By`.
- Ramas de trabajo: panel `feat/pub-resolve-address`; MMM `feat/mmm-ip-y-layout` (ya creada, spec ya commiteada ahí).

---

## Task 1: Panel — `/pub/resolve` expone la dirección

**Repo/CWD:** `c:\Users\marco\minecraft-server` · **Rama:** crear `feat/pub-resolve-address` desde `master`.

**Files:**
- Modify: `app/pub_api.py` (import `netinfo`, helper `_address`, endpoint `resolve`)
- Test: `tests/test_pub_resolve.py`

**Interfaces:**
- Consumes: `netinfo.resolve_host() -> Optional[str]` (ya existe en `app/netinfo.py`).
- Produces: `pub_api._address(server: dict) -> dict` con claves `host`, `port`, `address`. `/pub/resolve` incluye esas tres claves.

- [ ] **Step 1: Crear la rama**

Run: `cd "c:\Users\marco\minecraft-server" && git checkout master && git checkout -b feat/pub-resolve-address`
Expected: `Switched to a new branch 'feat/pub-resolve-address'`.

- [ ] **Step 2: Escribir el test que falla**

Añadir al final de `tests/test_pub_resolve.py`:

```python
def test_address_con_host(monkeypatch):
    monkeypatch.setattr(pub_api.netinfo, "resolve_host", lambda: "10.147.20.29")
    assert pub_api._address({"port": 25565}) == {
        "host": "10.147.20.29", "port": 25565, "address": "10.147.20.29:25565",
    }


def test_address_sin_host_address_none(monkeypatch):
    monkeypatch.setattr(pub_api.netinfo, "resolve_host", lambda: None)
    a = pub_api._address({"port": 25565})
    assert a["host"] is None
    assert a["port"] == 25565
    assert a["address"] is None
```

- [ ] **Step 3: Ejecutar y ver que falla**

Run: `cd "c:\Users\marco\minecraft-server" && ./.venv/Scripts/python.exe -m pytest tests/test_pub_resolve.py -q -k address`
Expected: FAIL — `AttributeError: module 'app.pub_api' has no attribute 'netinfo'` (o `_address`).

- [ ] **Step 4: Implementar**

En `app/pub_api.py`, añadir el import (junto a `from . import distribution as dist`):

```python
from . import netinfo
```

Añadir el helper antes del endpoint `resolve` (tras `_resolved_versions`):

```python
def _address(server: dict) -> dict:
    host = netinfo.resolve_host()
    port = server.get("port")
    return {"host": host, "port": port, "address": f"{host}:{port}" if host else None}
```

Modificar el `return` del endpoint `resolve` para incluir la dirección:

```python
@router.get("/resolve")
async def resolve(key: str = Query(...)) -> dict:
    slug = _slug_or_403(key)
    server = dist.get_server(slug)
    latest = dist.latest_release(slug)
    v = _resolved_versions(server, latest)
    resp = {
        "server_name": server["name"],
        "minecraft_version": v["minecraft_version"],
        "loader": v["loader"],
        "loader_version": v["loader_version"],
        "latest_version": latest["version"] if latest else 0,
        "motd": server["motd"],
    }
    resp.update(_address(server))
    return resp
```

- [ ] **Step 5: Ejecutar y ver que pasa**

Run: `cd "c:\Users\marco\minecraft-server" && ./.venv/Scripts/python.exe -m pytest tests/test_pub_resolve.py -q`
Expected: PASS (los 2 previos + 2 nuevos).

- [ ] **Step 6: Commit**

```bash
cd "c:\Users\marco\minecraft-server"
git add app/pub_api.py tests/test_pub_resolve.py
git commit -m "Panel · /pub/resolve expone la dirección del servidor (host/port/address)"
```

---

## Task 2: MMM — `config.apply_resolve_meta` cachea `address`

**Repo/CWD:** `C:\Users\marco\proyectos makro\minecraft-mod-manager` · **Rama:** `feat/mmm-ip-y-layout` (ya activa).

**Files:**
- Modify: `mmm/config.py` (`_RESOLVE_META`)
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: tras `apply_resolve_meta(server, info)`, `server["address"]` = `info["address"]` (si viene).

- [ ] **Step 1: Escribir el test que falla**

Añadir al final de `tests/test_config.py`:

```python
def test_apply_resolve_meta_cachea_address():
    server = {"loader": "neoforge", "minecraft_version": "1.21.1",
              "loader_version": "21.1.238", "name": "P", "motd": "x"}
    info = {"loader": "neoforge", "minecraft_version": "1.21.1", "loader_version": "21.1.238",
            "server_name": "P", "motd": "x", "address": "10.147.20.29:25565"}
    assert config.apply_resolve_meta(server, info) is True
    assert server["address"] == "10.147.20.29:25565"
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `cd "C:\Users\marco\proyectos makro\minecraft-mod-manager" && py -3 -m pytest tests/test_config.py -q -k cachea_address`
Expected: FAIL — `KeyError: 'address'` / assert (no se guarda `address`).

- [ ] **Step 3: Implementar**

En `mmm/config.py`, añadir la tupla a `_RESOLVE_META`:

```python
_RESOLVE_META = (
    ("loader", "loader"),
    ("minecraft_version", "minecraft_version"),
    ("loader_version", "loader_version"),
    ("name", "server_name"),
    ("motd", "motd"),
    ("address", "address"),
)
```

- [ ] **Step 4: Ejecutar y ver que pasa**

Run: `cd "C:\Users\marco\proyectos makro\minecraft-mod-manager" && py -3 -m pytest tests/test_config.py -q`
Expected: PASS (todos, incluido el nuevo).

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\marco\proyectos makro\minecraft-mod-manager"
git add mmm/config.py tests/test_config.py
git commit -m "MMM · cachear la dirección del servidor desde /pub/resolve"
```

---

## Task 3: MMM — fix de layout de detalles (minsize + scroll exterior)

**Repo/CWD:** `C:\Users\marco\proyectos makro\minecraft-mod-manager` · **Rama:** `feat/mmm-ip-y-layout`.

**Files:**
- Modify: `mmm/ui/app_window.py` (`minsize`)
- Modify: `mmm/ui/server_view.py` (`__init__`: Canvas scrolleable + repuntar widgets a `self.body`)

**Interfaces:**
- Produces: `ServerView.body` (ttk.Frame interior scrolleable) donde se empaquetan todos los widgets del detalle. Los métodos existentes (`_show_action`, `_set_zt_button`, `_clear_content`, etc.) siguen usando esos widgets sin cambios (mismo padre `self.body`).

- [ ] **Step 1: `minsize` en la ventana raíz**

En `mmm/ui/app_window.py`, en `AppWindow.__init__`, tras `self.geometry("720x480")` (línea 19):

```python
        self.minsize(680, 520)
```

- [ ] **Step 2: Envolver `ServerView` en un Canvas scrolleable**

En `mmm/ui/server_view.py`, reemplazar el bloque de `__init__` desde `super().__init__(...)` hasta la creación/empaquetado de `self.content` por:

```python
    def __init__(self, parent, server: dict, on_back, auto_update: bool = False):
        super().__init__(parent)
        self.server = server
        self.on_back = on_back
        self.worker: InstallWorker | None = None
        self._mirror_shaders = tk.IntVar(value=0)  # 0 = añadir, 1 = sobrescribir

        # ── Área scrolleable: canvas + scrollbar + frame interior (self.body) ──
        canvas = tk.Canvas(self, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(canvas, padding=16)
        win = canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
        # Rueda del ratón solo mientras el puntero está sobre el canvas (sin binding global permanente).
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(int(-ev.delta / 120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self.back_button = ttk.Button(self.body, text="← Volver", command=self._back)
        self.back_button.pack(anchor="w")
        ttk.Label(self.body, text=server["name"], font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(8, 0))
        ttk.Label(self.body, text=server.get("motd", "")).pack(anchor="w")
        self.version_label = ttk.Label(
            self.body,
            text=f'{server.get("loader","")} {server.get("minecraft_version","")} '
                 f'(loader {server.get("loader_version","")})',
        )
        self.version_label.pack(anchor="w", pady=(4, 4))

        self.status_label = ttk.Label(self.body, text="Comprobando estado…", foreground="gray")
        self.status_label.pack(anchor="w", pady=(0, 8))

        self.progress = ProgressPanel(self.body)
        self.progress.pack(fill="x")

        # El botón se muestra según el estado (oculto cuando ya está al día).
        self.action = ttk.Button(self.body, text="Instalar", command=self._do_install)

        self.zt_button = ttk.Button(self.body, text="Unirse a la red (ZeroTier)", command=self._join_network)
        self.zt_button.pack(pady=(0, 4))

        self.zt_status = ttk.Label(self.body, text="ZeroTier: comprobando…", foreground="gray")
        self.zt_status.pack(anchor="w", pady=(0, 6))

        self.hint = ttk.Label(self.body, text="", wraplength=560, foreground="gray")
        self.hint.pack(anchor="w")

        # Lista del contenido del modpack, SIEMPRE visible bajo los botones.
        self.content = ttk.Frame(self.body)
        self.content.pack(fill="both", expand=True, pady=(10, 0))

        self._poll_zt()
        self._refresh_status()
        self._load_content()

        if auto_update:  # "Actualizar" desde la lista: usa el modo de shaders efectivo
            self.after(300, lambda: self._start_install(config.resolve_shaders_mirror(self.server)))
```

> Nota: solo cambia `__init__`. El resto de métodos (`_show_action` con `pack(before=self.zt_button)`, `_set_zt_button`, `_clear_content` sobre `self.content`) sigue igual porque los widgets ahora son hijos de `self.body`.

- [ ] **Step 3: Smoke de imports (headless)**

Run: `cd "C:\Users\marco\proyectos makro\minecraft-mod-manager" && py -3 -c "import mmm.ui.server_view, mmm.ui.app_window; print('ok')"`
Expected: imprime `ok` sin trazas (no crea `Tk()`, solo valida sintaxis/imports).

- [ ] **Step 4: Suite MMM verde**

Run: `cd "C:\Users\marco\proyectos makro\minecraft-mod-manager" && py -3 -m pytest -q`
Expected: PASS (nada roto por el cambio de UI).

- [ ] **Step 5: Commit**

```bash
cd "C:\Users\marco\proyectos makro\minecraft-mod-manager"
git add mmm/ui/app_window.py mmm/ui/server_view.py
git commit -m "MMM · detalles scrolleables + minsize de ventana (botones no se cortan)"
```

---

## Task 4: MMM — widget `AddressBar` + IP en lista y detalles

**Repo/CWD:** `C:\Users\marco\proyectos makro\minecraft-mod-manager` · **Rama:** `feat/mmm-ip-y-layout`.

**Files:**
- Modify: `mmm/ui/widgets.py` (nuevo `AddressBar` + fila en `ServerRow`)
- Modify: `mmm/ui/server_view.py` (import `AddressBar` + fila en `ServerView`)

**Interfaces:**
- Consumes: `server["address"]` (Task 2), `ServerView.body` (Task 3).
- Produces: `widgets.AddressBar(parent, address: str | None)`.

- [ ] **Step 1: Widget `AddressBar` en `widgets.py`**

En `mmm/ui/widgets.py`, añadir la clase (tras la clase `Tooltip`, antes de `ServerRow`):

```python
class AddressBar(ttk.Frame):
    """Muestra la dirección del servidor con un botón para copiarla."""

    def __init__(self, parent, address: str | None):
        super().__init__(parent)
        ttk.Label(self, text=f"🌐 {address or 'IP no disponible'}").pack(side="left")
        self._addr = address
        if address:
            self._btn = ttk.Button(self, text="Copiar", width=8, command=self._copy)
            self._btn.pack(side="left", padx=(6, 0))

    def _copy(self):
        self.clipboard_clear()
        self.clipboard_append(self._addr)
        self._btn.config(text="¡Copiado!")
        self.after(1200, lambda: self._btn.winfo_exists() and self._btn.config(text="Copiar"))
```

- [ ] **Step 2: Fila de dirección en `ServerRow`**

En `mmm/ui/widgets.py`, dentro de `ServerRow.__init__`, entre el bloque `info` (que termina en el `for w in (info, *labels): … w.bind("<Button-1>", _open)`) y el bloque `actions` (`actions = ttk.Frame(self)`), insertar:

```python
        # ── Dirección del servidor (copiable, sin entrar a detalles) ─────────
        AddressBar(self, server.get("address")).pack(fill="x", pady=(6, 0))
```

- [ ] **Step 3: Dirección en los detalles (`ServerView`)**

En `mmm/ui/server_view.py`, ampliar el import de widgets:

```python
from .widgets import AddressBar, ProgressPanel
```

En `ServerView.__init__`, justo después de `self.status_label.pack(anchor="w", pady=(0, 8))`, añadir:

```python
        AddressBar(self.body, server.get("address")).pack(anchor="w", pady=(0, 8))
```

- [ ] **Step 4: Smoke de imports (headless)**

Run: `cd "C:\Users\marco\proyectos makro\minecraft-mod-manager" && py -3 -c "import mmm.ui.widgets, mmm.ui.server_view, mmm.ui.app_window; print('ok')"`
Expected: `ok` sin trazas.

- [ ] **Step 5: Suite MMM verde**

Run: `cd "C:\Users\marco\proyectos makro\minecraft-mod-manager" && py -3 -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd "C:\Users\marco\proyectos makro\minecraft-mod-manager"
git add mmm/ui/widgets.py mmm/ui/server_view.py
git commit -m "MMM · mostrar y copiar la IP del servidor en lista y detalles"
```

---

## Verificación final (usuario)

- **Panel**: deploy `app/pub_api.py` → `/opt/papulandia-panel/app/`; `systemctl restart papulandia-panel.service`; comprobar `GET /pub/resolve?key=…` incluye `address`.
- **MMM (visual, ejecutando la app)**: la IP aparece en cada fila de la lista con botón Copiar; dentro de detalles también; con la ventana pequeña, el detalle scrollea y se ven todos los botones.
- **MMM (publicar)**: subir `AppVersion` en `mmm/version.py` e `installer.iss`; recompilar (`py -3 -m PyInstaller MakroModManager.spec --noconfirm` + ISCC); publicar el instalador en el panel (MODPACK → App cliente).

## Self-Review

**Spec coverage:**
- Panel expone dirección → Task 1. ✓
- MMM cachea address → Task 2. ✓
- Fix layout (minsize + scroll) → Task 3. ✓
- AddressBar en lista y detalles → Task 4. ✓
- Tests panel `_address` + MMM `apply_resolve_meta` → Tasks 1-2. ✓
- Degradación limpia sin host ("IP no disponible") → Task 4 (`AddressBar` con `address=None`). ✓

**Placeholder scan:** sin TBD/TODO; todo el código presente. ✓

**Type/nombre consistency:** `_address` (host/port/address), `AddressBar(parent, address)`, `server["address"]`, `ServerView.body`, `from .widgets import AddressBar, ProgressPanel` — consistentes entre tareas. ✓

**Orden de dependencias:** Task 3 crea `self.body` antes de que Task 4 empaquete el `AddressBar` en él; Task 2 provee `server["address"]` que Task 4 consume. ✓
