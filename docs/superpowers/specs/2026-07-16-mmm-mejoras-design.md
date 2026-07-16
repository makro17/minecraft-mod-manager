# Diseño — Mejoras MakroModManager (Sub-proyecto C)

> Fecha: 2026-07-16 · App cliente Tkinter (`mmm/`).
> Decisiones tomadas con el usuario en conversación. Orden: C3 → C1 → C2 → C4.

## C3 · Versión → 1.1.0
- `mmm/version.py`: `__version__ = "1.1.0"`. La leen el instalador `.iss` y el auto-update.

## C1 · Broma al cerrar la ventana
Al pulsar la **X** de la ventana principal, con una casilla de config (activada por defecto):
- Intento 1: **75%** la ventana se "teletransporta" a una posición aleatoria (visible) en vez de cerrar.
- Intento 2 (tras teleport): **50%**. Intento 3: **25%**.
- Si se produce el **3.er teletransporte**, se abre **otra ventana** con la imagen (`assets/cigarro.png`) y a partir de ahí la X cierra normal.
- Si en cualquier intento la tirada falla, cierra normal.
- **Botón ⚙** en la ventana principal → diálogo con **una casilla sin etiqueta**, activada por defecto (`prank_enabled`, en `state.json`). Desactivada ⇒ la X cierra siempre normal.

**Diseño:**
- `mmm/config.py`: `prank_enabled: True` en `_DEFAULT` + `get_prank_enabled()` / `set_prank_enabled(bool)`.
- `mmm/prank.py` (NUEVO, lógica pura testeable): `should_teleport(teleport_count, rng=random.random)` → probabilidades `(0.75, 0.50, 0.25)` para los 3 primeros; luego `False`.
- `mmm/resources.py` (NUEVO): `resource_path(rel)` que resuelve assets en dev y en PyInstaller (`sys._MEIPASS`).
- `mmm/ui/app_window.py`: `protocol("WM_DELETE_WINDOW", ...)` con estado `_teleport_count`/`_prank_image_shown`; helpers `_teleport_window()` (mueve dentro de pantalla), `_show_prank_image()` (Toplevel con `tk.PhotoImage`, PNG nativo, sin Pillow), `_open_config()` (⚙ → casilla). Botón ⚙ en el header.
- Imagen: el JPG original convertido a `assets/cigarro.png` (Tk 8.6 no lee JPG).
- `MakroModManager.spec`: añadir `('assets', 'assets')` a `datas`.

## C2 · Instalación con vista previa + shaders + update en vivo
- **Vista previa**: al pulsar **Instalar** (1ª vez), la app baja el manifiesto y muestra la **lista de lo que se descargará** (mods + shaders, nombre y tamaño); un 2º botón **Confirmar e instalar** lanza la descarga.
- **Shaders añadir/sobrescribir** (solo shaders; los mods siempre exactos): control en la preview.
  - `mmm/sync.py`: `sync_manifest(..., mirror_shaders=True)`. El `_mirror` borra sobrantes solo en `mods` siempre; en `shaderpacks` solo si `mirror_shaders` (sobrescribir). En modo "añadir", no borra los shaders del usuario.
- **Update en vivo**: la biblioteca revisa cada ~60 s si hay versión nueva de modpack (`api.resolve` por servidor) y actualiza el badge sin reiniciar (`after()` + hilo de red).

## C4 · Onboarding ZeroTier (app + panel)
Modelo elegido: **la app instala+une ZeroTier; el admin autoriza a mano, con nombre para identificar.**
- **App**: al conectar por primera vez → comprueba ZeroTier (instala si falta, UAC) → pide **nombre/alias** → `zerotier-cli join acf3c66fcf5b7449` → manda al panel `node_id + nombre + dist_key`.
- **Panel** (NUEVO endpoint `POST /pub/zt/request`, key-gated): registra la solicitud pendiente (node_id ↔ nombre). Vista admin que **lista pendientes con nombre** y botón **Autorizar** → llama al controlador ZeroTier local (`localhost:9993`, token `ZT_TOKEN` de ztncui, server-side) para autorizar + poner el nombre como descripción del miembro.
- La app detecta la IP `10.147.20.x`, añade el server al Minecraft y conecta.
- Requiere admin/elevación para las operaciones ZeroTier. Verificación real necesita el contenedor + un cliente.

## Testing
- C3: `test_version_semver` (ya existe) sigue verde.
- C1: `test_config` (prank get/set), `test_prank` (should_teleport con rng determinista). GUI: verificación manual.
- C2: `test_sync` ampliado (mirror_shaders on/off), preview y update en vivo: verificación manual.
- C4: lógica de node_id/nombre testeable; ZeroTier real: manual en contenedor.

## Fuera de alcance
- D (panel subidas/descargas), B (restyle panel) — sub-proyectos aparte.
