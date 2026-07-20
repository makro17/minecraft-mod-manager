# Diseño — C4 · Onboarding completo de ZeroTier con elevación bajo demanda

> Fecha: 2026-07-18
> Repo: `minecraft-mod-manager` (cliente MakroModManager)
> Estado: aprobado, pendiente de plan de implementación.

## Problema

Hoy MMM no instala ZeroTier: cuando no está presente, solo abre la página de descarga
(`zt_dialog.ensure_access` → `webbrowser.open`). Además, en Windows **todas** las operaciones
de ZeroTier (`info`/`listnetworks` para el estado, `join`, `leave`) requieren privilegios de
administrador porque leen `authtoken.secret` (solo admin). La app corre `asInvoker` (el
`.spec` no tiene `uac_admin`), así que sin permisos el estado/join fallan y el código ya
avisa de "ejecutar como administrador".

## Objetivo

Onboarding de ZeroTier que "simplemente funcione" para un amigo no técnico: la app obtiene
permisos **bajo demanda** (solo al conectar), instala ZeroTier automáticamente si falta, y
completa el join. Un solo UAC en todo el proceso.

## Decisiones de diseño

1. **Elevación bajo demanda por relanzamiento** (no manifest). La app arranca normal
   (`asInvoker`). Gestionar modpacks no pide permisos. Cuando se necesita ZeroTier, si no
   está elevada, ofrece "Reiniciar con permisos" y se **relanza a sí misma elevada** (1 UAC).
   Descartado el manifest `requireAdministrator` (UAC en cada arranque, mala UX para un
   lanzador).
2. **Instalación de ZeroTier desde el CDN oficial**, directa:
   `https://download.zerotier.com/dist/ZeroTier%20One.msi` (verificado: HTTP 200, ~12 MB,
   HTTPS). Sin espejo por el panel ni sha256 pin: ZeroTier actualiza la MSI y habría que
   re-pinar el hash en cada versión; la TLS de ZeroTier da integridad de transporte.
3. **Fallback siempre disponible**: si la descarga o `msiexec` fallan, se abre la página de
   descarga (comportamiento actual) para no dejar al usuario atascado.
4. **Solo Windows** (MMM es Windows-only). En no-Windows, las funciones degradan a defaults
   mockeables para desarrollo/tests.

## Arquitectura

### Componente nuevo: `mmm/elevation.py`

Encapsula la detección y el relanzamiento elevado. Windows-only real; parte pura testeable.

- `is_elevated() -> bool` → `ctypes.windll.shell32.IsUserAnAdmin()` (en no-Windows: `False`).
- `relaunch_as_admin() -> bool` → `ctypes.windll.shell32.ShellExecuteW(None, "runas",
  sys.executable, params, None, SW_SHOWNORMAL)`. Devuelve `True` si el relanzamiento se
  inició (retorno > 32) — el caller entonces cierra la instancia actual; `False` si el
  usuario canceló el UAC o falló (el caller no cierra y avisa). En dev (no frozen) o
  no-Windows, devuelve `False` sin hacer nada (se muestra el aviso de "ejecuta como admin").

### `mmm/zerotier.py` — nueva función `install`

- Constante `MSI_URL = "https://download.zerotier.com/dist/ZeroTier%20One.msi"`.
- `install(download, run, sleep=time.sleep, *, url=MSI_URL, attempts=20, delay=1.0) -> bool`:
  1. Descarga la MSI a un archivo temporal con `download(url, dest)` (inyectable; en
     producción usa `api`/`requests`).
  2. Ejecuta `run(["msiexec", "/i", str(dest), "/qn", "/norestart"])` (inyectable; en
     producción `subprocess.run` con `procutil.no_window_kwargs()`). Como ya estamos
     elevados, **no** hay segundo UAC.
  3. **Polling**: hasta `attempts` veces, `is_installed()`; entre intentos `sleep(delay)`.
     Devuelve `True` si aparece el CLI; `False` si agota el timeout.
  - Errores de descarga o de `run` (código ≠ 0) → propaga/`return False`; el llamador hace
    fallback a la página.

### UI — `mmm/ui/server_view.py` y `mmm/ui/zt_dialog.py`

**Puerta de elevación** en la sección ZeroTier de `ServerView`:
- Si `elevation.is_elevated()` es `False`: no se llama a `zerotier-cli` (evita el estado
  falso "no instalado"). La sección muestra *"Para gestionar ZeroTier necesito permisos de
  administrador"* + botón **"Reiniciar con permisos"** → `elevation.relaunch_as_admin()`; si
  devuelve `True`, cierra la app (`self.winfo_toplevel().destroy()`); si `False`, avisa.
- Si `is_elevated()` es `True`: flujo normal (estado auto-refrescado + acciones), que ahora
  funciona.

**Auto-instalación** en `zt_dialog.ensure_access` (rama `not_installed`, ya elevada):
- Sustituye el `webbrowser.open` por: confirmar → `zerotier.install(...)` con progreso →
  si `True`, continúa el onboarding actual (node_id → `join` → `api.zt_request`); si `False`
  o excepción → `messagebox` + fallback `webbrowser.open(DOWNLOAD_URL)`.

## Flujo de datos

```
Usuario entra a un server (no elevado)
  → sección ZeroTier: "Reiniciar con permisos"
  → relaunch_as_admin() (1 UAC) → cierra instancia actual
Nueva instancia (elevada)
  → is_elevated()=True → lee estado ZeroTier
     ├─ not_installed → install() [descarga MSI + msiexec /qn + poll] → join → request
     └─ not_joined    → join → request
```

## Manejo de errores

- UAC cancelado en el relaunch → `relaunch_as_admin()` devuelve `False`; la app sigue abierta
  y muestra "no se obtuvieron permisos".
- Descarga de la MSI falla / `msiexec` código ≠ 0 / polling agota timeout → `install`
  devuelve `False`/excepción → aviso + fallback a la página de descarga.
- Dev (no frozen) o no-Windows → `is_elevated()`/`relaunch_as_admin()` degradan; se muestra
  el aviso actual de ejecutar como admin (sin romper).

## Estrategia de tests (TDD)

- `tests/test_elevation.py`: `is_elevated` mockeando `IsUserAnAdmin` (True/False);
  `relaunch_as_admin` mockeando `ShellExecuteW` (retorno > 32 → True; ≤ 32 → False); gate a
  Windows con `skipif` para cualquier prueba que toque `ctypes.windll` real.
- `tests/test_zerotier.py` (ampliado): `install` con `download`/`run`/`sleep` inyectados:
  instala OK (CLI aparece al 1.er poll), timeout (nunca aparece → `False`), `run` con código
  ≠ 0 → `False`/excepción. Sin tocar `msiexec` real.
- UI (Tkinter, no headless): smoke import `import mmm.ui.server_view, mmm.ui.zt_dialog` +
  verificación visual manual (tras recompilar).

## Build / deploy

- **Sin cambios en `MakroModManager.spec`** (elevación por relaunch en runtime, no manifest).
- **Subir versión a `1.2.0`** en `mmm/version.py` y `installer.iss` (ya hay una **1.1.0**
  publicada, así que el auto-update debe ver la nueva). Recompilar (PyInstaller + ISCC) y
  publicar el instalador por la UI (MODPACK → App cliente); el auto-update ofrecerá 1.2.0 a
  los clientes en 1.1.0, verificando el sha256.
- Sin cambios en el panel.

## Archivos

- **NUEVO** `mmm/elevation.py`
- **NUEVO** `tests/test_elevation.py`
- **MODIFICADO** `mmm/zerotier.py` (`MSI_URL` + `install`)
- **MODIFICADO** `tests/test_zerotier.py` (tests de `install`)
- **MODIFICADO** `mmm/ui/server_view.py` (puerta de elevación en la sección ZeroTier)
- **MODIFICADO** `mmm/ui/zt_dialog.py` (auto-instalación + fallback)
- **MODIFICADO** `mmm/version.py` + `installer.iss` (1.1.0 → 1.2.0)
