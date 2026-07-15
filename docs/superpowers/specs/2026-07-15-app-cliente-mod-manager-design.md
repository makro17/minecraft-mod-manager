# Sub-proyecto B — App cliente "Minecraft Mod Manager" (MMM)

> Diseño validado. Fecha: 2026-07-15.
> Parte del proyecto "Minecraft Mod Manager" (panel productor + app cliente).
> Reescritura completa del repo `minecraft-mod-manager` (hoy un script trivial de copia
> de carpeta `mods/`). Este spec cubre **solo la app cliente** (consumidor). Depende del
> contrato de la API pública `/pub` definido por el Sub-proyecto A (panel).

## Contexto

El panel Papulandia (Sub-proyecto A, rama `feat/panel-distribucion-mods`, 50 tests verdes,
sin desplegar) expone una **API pública key-gated `/pub`** en `https://maincra.newsik.net`.
La app cliente permite a un jugador, con una **clave de servidor** (`PPL-XXXX-XXXX-XXXX`),
instalar en su PC el loader (NeoForge), los mods de cliente y los shaders del modpack de
ese servidor, en una **instancia aislada** que no pisa su `.minecraft`, y mantenerlos al día.

La app **nunca** habla con la API de admin del panel; solo con `/pub/*`.

## Contrato de la API `/pub` (del Sub-proyecto A)

Base: `https://maincra.newsik.net`.

- `GET /pub/resolve?key=PPL-...` → `{server_name, minecraft_version, loader, loader_version, latest_version, motd}` | **403** si clave inválida/rotada.
- `GET /pub/manifest?key=PPL-...` → manifiesto de la última release | 403/404. Formato:
  ```json
  {
    "server": "papulandia", "server_name": "Papulandia", "version": 3,
    "minecraft_version": "1.21.1", "loader": "neoforge", "loader_version": "21.1.224",
    "files": [
      {"kind":"mod","filename":"jei.jar","sha256":"…","size":123,"target_dir":"mods","url":"/pub/file/<sha256>"},
      {"kind":"shader","filename":"comp.zip","sha256":"…","size":456,"target_dir":"shaderpacks","url":"/pub/file/<sha256>"}
    ],
    "published_at":"…","notes":"…"
  }
  ```
  `files` solo incluye lo que el cliente necesita (mods `both`+`client` + todos los shaders); nunca los `server`.
- `GET /pub/file/{sha256}?key=PPL-...` → descarga del `.jar`/`.zip` (con `Content-Disposition`) | 403/404.
- `GET /pub/app/version` → `{version, download_url, notes}` (público, sin clave) — auto-update.
- `GET /pub/app/download` → instalador de la app (público, sin clave).

Cambios en este contrato obligan a revisar este sub-proyecto.

## Objetivos

1. Entrada por **clave** → resolver y mostrar el servidor (nombre, MOTD, loader/versión, estado local).
2. Instalar/actualizar en una **instancia aislada** por servidor: loader (headless) + mods de cliente + shaders.
3. **Biblioteca** de varios servidores (cada uno por su clave/slug), con estado: no instalado / al día / actualización disponible.
4. Integración **no destructiva** con el launcher **oficial** (perfil auto); TLauncher/otros con instrucciones.
5. **Auto-update** de la propia app (no bloqueante) vía `/pub/app/*`.
6. Empaquetado a **`.exe`** con instalador (molde backtask), **JRE bundleado**.

## No-objetivos (v1)

- Login con cuenta Newsik (aparcado; se deja hueco en la pantalla de entrada).
- Auth de Microsoft / descarga del Minecraft base (lo hace el launcher del jugador).
- Loaders **Fabric** y **Vanilla**: la arquitectura los deja enchufables, pero **v1 implementa solo NeoForge** (único loader en uso). Otros loaders → mensaje "aún no soportado".
- Gestión de `saves/` o `config/` del jugador (nunca se tocan).

---

## Decisiones de diseño (cerradas en brainstorming)

1. **Modelo de arranque:** perfil automático en el **launcher oficial**. El loader se instala en el `.minecraft` oficial (`versions/` + `libraries/`, no destructivo) y se registra un perfil en `launcher_profiles.json` con `gameDir` → la instancia aislada. TLauncher/otros: con instrucciones.
2. **Java:** **JRE bundleado** en el instalador (jlink de Temurin 21 recortado). La app no depende del PATH ni del Java del jugador; funciona offline tras instalar.
3. **Loaders v1:** dirigido por el manifiesto; **NeoForge** implementado y probado. Fabric/Vanilla enchufables después con el mismo contrato.
4. **Multi-servidor:** **biblioteca**. Cada servidor por su clave/slug, con su instancia `.minecraft-<slug>` y su perfil en el launcher.
5. **Concurrencia:** paquete Python modular + **hilo worker** para red/instalación + cola de eventos hacia la UI tkinter (GUI fluida, progreso, cancelación).
6. **Estilo UI:** tkinter/ttk **plano/normal** (no la piel medieval del panel).
7. **Sincronización:** **mirror** del manifiesto — borra de `mods/` y `shaderpacks/` lo que ya no está; nunca toca `saves/`/`config/`.

---

## Arquitectura y estructura del repo

Reescritura del repo `minecraft-mod-manager` (git, rama `main`). Se sustituye el script actual.

```
minecraft-mod-manager/
  mmm/
    __main__.py            # arranque; flags de mantenimiento (p.ej. limpieza post-update)
    version.py             # semver, fuente única (la usan el .iss y el auto-update)
    api.py                 # cliente /pub (resolve, manifest, file, app/version, app/download)
    config.py              # estado/biblioteca en %APPDATA%\MinecraftModManager\state.json
    instances.py           # rutas: instancia .minecraft-<slug>
    launcher.py            # detectar .minecraft oficial + leer/escribir launcher_profiles.json
    loaders/
      base.py              # interfaz LoaderInstaller (contrato común)
      neoforge.py          # implementado en v1
      # fabric.py, vanilla.py  -> después, mismo contrato
    jre.py                 # localiza el JRE bundleado junto al exe
    sync.py                # motor: descarga + verificación sha256 + mirror del manifiesto
    updater.py             # auto-update de la propia app
    worker.py              # hilo worker + cola de eventos hacia la UI
    ui/
      app_window.py        # ventana principal (biblioteca)
      server_view.py       # detalle de servidor + instalar/actualizar
      dialogs.py           # diálogo "añadir clave", ajustes, errores
      widgets.py           # widgets reutilizables (fila de servidor, barra de progreso)
  assets/                  # icono (placeholder hasta tener el definitivo)
  build.bat  clean.bat  installer.iss  MinecraftModManager.spec
  requirements.txt  requirements-dev.txt  INSTRUCCIONES.md
  tests/
```

**Constante clave:** `BASE_URL = "https://maincra.newsik.net"`. `/pub` va por Cloudflare, disponible aunque el server MC esté dormido por lazymc.

**Dependencias runtime:** `requests` + tkinter (stdlib). **Dev:** `pytest`, `pyinstaller`.

---

## Modelo de instancia e integración con el launcher

Por servidor (slug), dos ubicaciones:

- **`.minecraft` oficial** (`%APPDATA%\.minecraft`, detectable, con override manual): recibe el loader de forma **no destructiva** → `versions/neoforge-<ver>/` + `libraries/`. Se **añade/actualiza** un perfil en `launcher_profiles.json`:
  - `name` = nombre del servidor, `lastVersionId` = id del loader (`neoforge-<ver>`), `gameDir` = ruta de la instancia aislada, `type` = `custom`, `created`/`lastUsed` ISO.
  - Preserva los perfiles existentes del jugador (merge por clave, no reescritura total).
- **Instancia aislada** `%APPDATA%\.minecraft-<slug>\`: `mods/`, `shaderpacks/`, `config/`, `saves/`, `options.txt`. El `gameDir` del perfil apunta aquí → mundos y mods del jugador nunca se pisan.

La app **posee** `mods/` y `shaderpacks/` de la instancia (los sincroniza al manifiesto). **Nunca** toca `saves/` ni `config/`.

**TLauncher/otros:** tras instalar, la app muestra instrucciones: "apunta el directorio de juego a `…\.minecraft-<slug>` y selecciona la versión `neoforge-<ver>`".

---

## Motor de instalación del loader (headless)

Interfaz `LoaderInstaller` en `loaders/base.py`:
- `ensure_installed(mc_version: str, loader_version: str, official_dir: Path) -> str` (devuelve el `version_id` instalado; idempotente).
- Selección por `loader` del manifiesto (factory). Loader no implementado → excepción `LoaderNoSoportado` con mensaje claro.

**NeoForge (`loaders/neoforge.py`), v1:**
1. Descargar el **installer oficial** del maven de NeoForge:
   `https://maven.neoforged.net/releases/net/neoforged/neoforge/<ver>/neoforge-<ver>-installer.jar` (público; no pasa por el panel). Cachear en `%APPDATA%\MinecraftModManager\cache\`.
2. Garantizar `launcher_profiles.json` en el `.minecraft` oficial (crear stub mínimo si falta; el installer lo exige).
3. Ejecutar **headless** con el **JRE bundleado**:
   `<runtime>\bin\java.exe -jar <installer.jar> --install-client <official_dir>`
   (flag exacto a verificar en implementación; el installer descarga el jar vanilla + libraries y corre los *processors*). Los *assets* los baja el launcher al pulsar Jugar.
4. Devolver `version_id = "neoforge-<ver>"`.
5. **Idempotente:** si `versions/neoforge-<ver>/` ya existe y es válido, se salta.

Captura de `stdout`/`stderr` del proceso; si falla, log en `%APPDATA%\MinecraftModManager\logs\` + resumen en UI.

---

## Motor de sincronización (descarga + verificación + mirror)

Dado el manifiesto (`GET /pub/manifest?key=`):

- Para cada `file`: destino = `instancia/<target_dir>/<filename>`.
  - Si existe y **sha256 coincide** → se salta (updates incrementales baratos).
  - Si no → descarga de `GET /pub/file/<sha256>?key=` a `<destino>.tmp`, **verifica sha256**, `os.replace` atómico.
- **Mirror:** al terminar, borra de `mods/` y `shaderpacks/` los ficheros **no** presentes en el manifiesto (por nombre). Solo esas dos carpetas.
- Registra `installed_version` en el estado **solo al completar** loader + sync (nunca estado a medias).
- Reintentos con backoff por fichero; no deja `.tmp` sueltos.

---

## Estado / biblioteca (config de la app)

`%APPDATA%\MinecraftModManager\state.json`:
```json
{
  "app_version": "1.0.0",
  "official_minecraft_dir": "C:/Users/…/AppData/Roaming/.minecraft",
  "servers": [
    {
      "slug": "papulandia", "name": "Papulandia", "key": "PPL-XXXX-XXXX-XXXX",
      "loader": "neoforge", "minecraft_version": "1.21.1", "loader_version": "21.1.224",
      "installed_version": 3, "instance_path": "C:/Users/…/AppData/Roaming/.minecraft-papulandia"
    }
  ]
}
```
- La clave se guarda **en claro** (proyecto personal; anotado como decisión consciente).
- "Añadir servidor" = meter otra clave → `resolve` → alta en la lista.
- **Estado por servidor** = comparar `installed_version` (local) con `latest_version` (de `resolve`):
  - sin fila / sin `installed_version` → **no instalado**.
  - `installed_version == latest_version` → **al día**.
  - `installed_version < latest_version` → **actualización disponible**.

---

## UI y flujo de pantallas

Estilo tkinter/ttk plano. Ventana ~700×480.

**Pantalla A — Biblioteca** (arranque):
```
  Minecraft Mod Manager                         [ ⚙ ]  [ ? ]
  ───────────────────────────────────────────────────────────
   Papulandia      NeoForge 1.21.1     ● Al día      [ Jugar ]
   OtroServer      NeoForge 1.21.1     ⬆ Actualizar  [Instalar]
  ───────────────────────────────────────────────────────────
                    [ + Añadir servidor (clave) ]
```
- Sin servidores → directo al diálogo "meter clave" (hueco futuro para login Newsik, sin implementar).
- Fila: nombre, loader/versión, estado (● al día / ⬆ actualización / ○ no instalado), botón contextual.

**Pantalla B — Detalle del servidor:**
- MOTD + nombre + loader/versión + estado local.
- Botón grande **Instalar / Actualizar** → worker con barra de progreso ("Instalando loader…", "Descargando mods (3/12)…", "Sincronizando…") + **Cancelar**.
- Al terminar: instrucciones de arranque (perfil creado en el launcher oficial; nota TLauncher). **Quitar servidor** (borra fila + opcionalmente la instancia, con confirmación).

**Diálogo — Añadir clave:** campo `PPL-XXXX-XXXX-XXXX`, valida formato en cliente y luego `resolve`. 403 → "clave inválida o caducada; pide una nueva".

---

## Auto-update de la app (no bloqueante)

Al arrancar, en segundo plano: `GET /pub/app/version` → `{version, download_url, notes}`.
- Si `version` (semver) > `app_version` local: aviso no bloqueante ("Nueva versión X. ¿Actualizar?" + notas). Si acepta → descarga `GET /pub/app/download` a `%TEMP%`, **lanza** el instalador y la app **se cierra** (Inno con `UsePreviousAppDir` actualiza en sitio). Si rechaza → sigue con la actual.
- Sin conexión / error → se ignora silenciosamente.

---

## Manejo de errores

- **Red/descarga:** reintentos con backoff; timeouts. 403 → "clave inválida/caducada". 404 manifest → "el servidor aún no ha publicado ningún modpack".
- **sha256 no coincide:** reintenta; si persiste, aborta ese fichero, reporta cuál falló, sin `.tmp` sueltos.
- **Instalador de loader falla:** captura salida del proceso, resumen en UI + log en disco. La instancia no queda "instalada" a medias (solo se marca al completar loader + sync).
- **Disco lleno / permisos:** mensaje claro; el `.minecraft` oficial nunca queda inconsistente (el installer oficial es transaccional respecto a su versión).
- **Cancelar:** el worker atiende un flag entre ficheros; conserva lo ya bajado (válido por sha256), no corrompe estado.

---

## Empaquetado (molde backtask)

- **PyInstaller** `--onedir --windowed --icon`, con el **JRE bundleado** (jlink Temurin 21 recortado) incluido como `datas` en `runtime/` junto al exe. `MinecraftModManager.spec` versionado.
- **Inno Setup** `installer.iss`: instala en `{localappdata}\MinecraftModManager`, `PrivilegesRequired=lowest`, acceso directo en escritorio, español, **`UsePreviousAppDir=yes`** (clave para el auto-update). Salida `installer_output\MinecraftModManager_setup.exe`.
- **`build.bat`** (compila spec + Inno) y **`clean.bat`** (borra build/dist/installer_output/__pycache__), calcados de backtask.
- **`INSTRUCCIONES.md`**: cómo compilar, cómo generar el JRE con jlink, y cómo **publicar el instalador al panel** (tab MODPACK global → `app_release`, que es lo que sirve `/pub/app/download`).
- `mmm/version.py` = fuente única de la versión (la leen el `.iss` y el auto-update).

---

## Testing

`pytest`, sin tocar Minecraft real ni red:
- `api.py`: parseo de respuestas, construcción de URLs con clave, manejo de 403/404 (`requests` mockeado).
- `sync.py`: skip por sha256 coincidente, descarga+verificación, **mirror** (borra lo ausente; no toca `saves/`), sha256 fallida.
- `launcher.py`: leer/escribir `launcher_profiles.json` preservando perfiles existentes; stub si falta.
- `config.py`: alta/baja de servidores, cálculo de estado.
- `loaders/neoforge.py`: idempotencia (salta si ya instalado) y construcción del comando (subprocess Java mockeado; no se ejecuta Java en tests).
- `updater.py`: comparación semver.

---

## Dependencia del despliegue del panel

La app es inútil hasta que el **Sub-proyecto A esté desplegado** en `maincra.newsik.net` (rutas `/pub/*` activas) y exista al menos:
- una **release** publicada del servidor (para `manifest`),
- un **`app_release`** publicado (para `/pub/app/download` y el auto-update).

El primer instalador de la app se sube a mano al panel (no hay auto-update para la primera instalación).

## Riesgos y notas

- **Flag exacto del installer NeoForge headless** (`--install-client` / `--installClient`) a verificar en implementación con la versión 21.1.x.
- **Tamaño del JRE bundleado**: jlink debe recortar a los módulos que usan los *processors* de NeoForge; verificar que la instalación real funciona con el JRE recortado (no solo `java -version`).
- **`launcher_profiles.json`**: formato del launcher oficial actual; preservar campos desconocidos al hacer merge.
- Clave en claro en `state.json` (aceptado para uso personal).
