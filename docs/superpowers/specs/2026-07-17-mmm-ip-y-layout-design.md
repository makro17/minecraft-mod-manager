# Diseño — MMM: IP en lista/detalles + fix de layout de detalles

> Fecha: 2026-07-17 · Rama base: `main` (rama de trabajo `feat/mmm-ip-y-layout`)
> Estado: diseño **aprobado** por el usuario en conversación. Pendiente implementación (TDD donde aplica) + build/publicación del instalador.

App cliente MakroModManager (Tkinter) en `C:\Users\marco\proyectos makro\minecraft-mod-manager`.
Dos mejoras en las pantallas de servidor, más un cambio pequeño de apoyo en el **panel** (repo aparte
`c:\Users\marco\minecraft-server`).

## Problema

1. **No se ve la IP del servidor.** El usuario quiere ver la dirección de cada servidor y copiarla
   sin entrar a los detalles, y también dentro de los detalles. Hoy MMM **no tiene** la dirección:
   `/pub/resolve` del panel devuelve nombre/versiones/motd, sin host ni puerto. La dirección
   conectable es `IP-ZeroTier : puerto-del-servidor` (lo que el panel muestra en Overview con
   `netinfo.resolve_host()` + `server.port`).
2. **Botones cortados en detalles con ventana pequeña.** `ServerView` (`mmm/ui/server_view.py`)
   apila todo con `.pack()` vertical **sin scroll exterior**, y la ventana raíz (720×480,
   `mmm/ui/app_window.py`) **no tiene `minsize`**. Al encoger la ventana, el contenido de abajo
   (radios de shaders, lista, botones ZeroTier/acción) se recorta y no hay forma de alcanzarlo.

## Objetivos

- Mostrar la dirección del servidor + botón **Copiar** en la **lista** (sin entrar a detalles) y en
  los **detalles**.
- Que en detalles no se corten botones/contenido con la ventana pequeña.
- Origen de la dirección **robusto**: el panel la expone (no hardcodear en MMM — ya causó un bug en el
  panel una IP hardcodeada).

## Parte A — Panel (repo aparte, cambio pequeño)

`app/pub_api.py`:
- Nuevo helper puro `_address(server: dict) -> dict`:
  ```python
  from . import netinfo
  def _address(server: dict) -> dict:
      host = netinfo.resolve_host()
      port = server.get("port")
      return {"host": host, "port": port, "address": f"{host}:{port}" if host else None}
  ```
- El endpoint `GET /pub/resolve` añade esos tres campos a su respuesta (junto a los actuales
  `server_name`, versiones, `latest_version`, `motd`). Es público key-gated: quien tiene la clave ya
  necesita la IP para conectar, así que exponerla es correcto y consistente con el Overview del panel.
- **Tests** en `tests/test_pub_resolve.py` (funciones puras, estilo del fichero): `_address` con
  `netinfo.resolve_host` mockeado → host+puerto+address; y sin host → `address = None`.

> Consecuencia operativa: el panel necesita **redeploy** de `app/pub_api.py` para que `/pub/resolve`
> emita la dirección. Sin ese deploy, MMM mostrará "IP no disponible" (degradación limpia).

## Parte B — MMM · dato de la dirección

`mmm/config.py`:
- Añadir `("address", "address")` a `_RESOLVE_META` → `apply_resolve_meta(server, info)` cachea
  `server["address"]` desde `/pub/resolve`. Como el bucle solo escribe cuando `val is not None`, si el
  panel aún no emite la dirección (o es `None`), no se pisa una dirección previamente cacheada.
- **Test** en `tests/test_config.py`: `apply_resolve_meta` con `info` que incluye `address` guarda
  `server["address"]` y devuelve `True`.

La dirección se rellena en `AppWindow._status_for()` (que ya llama `api.resolve` + `apply_resolve_meta`
+ `upsert_server` por servidor antes de render) y en `ServerView._apply_status()` (que también resuelve).
Sin cambios de flujo: solo se añade el campo cacheado.

## Parte C — MMM · UI (widget reutilizable + colocación)

`mmm/ui/widgets.py` — nuevo widget reutilizable:
```python
class AddressBar(ttk.Frame):
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
- **Lista** (`ServerRow`): añadir `AddressBar(self, server.get("address"))` en su **propia fila** entre
  `info` y `actions` (así el botón Copiar no dispara el click-para-abrir de las etiquetas de info).
- **Detalles** (`ServerView`): añadir `AddressBar(self.body, server.get("address"))` bajo el
  `status_label`, arriba.

Formato de la dirección: `host:port` siempre (lo que devuelve el panel en `address`). Copiar pone esa
cadena en el portapapeles.

## Parte D — MMM · fix de layout de detalles (minsize + scroll exterior)

`mmm/ui/app_window.py`:
- En `AppWindow.__init__`, tras `self.geometry("720x480")`: `self.minsize(680, 520)`.

`mmm/ui/server_view.py` — envolver `ServerView` en un área scrolleable:
- En `__init__`, en vez de empaquetar los widgets sobre `self` (con `padding=16`), crear:
  - `canvas = tk.Canvas(self, highlightthickness=0)` + `vsb = ttk.Scrollbar(self, orient="vertical",
    command=canvas.yview)`; `canvas.configure(yscrollcommand=vsb.set)`; `vsb.pack(side="right",
    fill="y")`, `canvas.pack(side="left", fill="both", expand=True)`.
  - `self.body = ttk.Frame(canvas, padding=16)`; `win = canvas.create_window((0,0),
    window=self.body, anchor="nw")`.
  - `self.body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))`.
  - `canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))` (el interior sigue
    el ancho del canvas → los widgets con `fill="x"` se ven bien).
  - Rueda del ratón **sin binding global**: en `<Enter>` del canvas, `bind_all("<MouseWheel>", …)`; en
    `<Leave>`, `unbind_all("<MouseWheel>")`. Handler: `canvas.yview_scroll(int(-e.delta/120), "units")`.
    La **scrollbar** es la vía garantizada de scroll; la rueda es best-effort (al pasar sobre la lista
    de mods interior, esa lista captura su propia rueda, comportamiento aceptable).
- Repuntar **todas** las creaciones de widgets del cuerpo de `self` → `self.body`: `back_button`,
  labels (nombre, motd, version_label, status_label), `progress`, `action`, `zt_button`, `zt_status`,
  `hint`, `content`. Los `pack(..., before=self.zt_button)` de `_show_action`/`_set_zt_button` siguen
  funcionando (mismo padre `self.body`).

## Testing / verificación

- **Panel (pytest, `./.venv/Scripts/python.exe -m pytest -q`)**: `_address` (con/ sin host).
- **MMM (pytest, `py -3 -m pytest -q`)**: `apply_resolve_meta` cachea `address`. Suite completa verde
  (65 previos + 1 nuevo).
- **MMM GUI** (no testeable headless): smoke de imports `py -3 -c "import mmm.ui.widgets,
  mmm.ui.server_view, mmm.ui.app_window"` (no crea `Tk()`). La verificación visual (IP en lista,
  copiar, scroll en detalles con ventana pequeña) la hace el usuario ejecutando la app.

## Deploy / publicación

- **Panel**: `scp app/pub_api.py` → `/opt/papulandia-panel/app/` + `systemctl restart
  papulandia-panel.service`. (Verificar `/pub/resolve` devuelve `address`.)
- **MMM**: subir `AppVersion` en `mmm/version.py` e `installer.iss`; recompilar
  (`py -3 -m PyInstaller MakroModManager.spec --noconfirm` + ISCC) → `installer_output/…`; publicar en
  el panel (MODPACK → App cliente).

## Fuera de alcance

- Reestructurar otras pantallas de MMM (solo lista + detalles de servidor).
- Cambiar el flujo de resolución de estado/versiones (solo se añade el campo `address`).
