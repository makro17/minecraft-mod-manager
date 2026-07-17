# Verificación de hash en descargas ejecutables — diseño

> Endurecimiento de seguridad del cliente (MakroModManager) + panel Papulandia.
> Cierra Seguridad #2 y #3 de la cola. #5 (firmar el instalador) queda aplazado
> (requiere certificado de code-signing; un self-signed no evita SmartScreen).
> Fecha: 2026-07-17.

## Problema

El cliente ejecuta binarios descargados **sin verificar su integridad**:

1. **Auto-update** (`mmm/__main__.py`): descarga `MakroModManager_setup.exe` de
   `/pub/app/download` y hace `subprocess.Popen([exe])` sin comprobar hash. Un
   MITM o un servidor comprometido puede sustituir el instalador → RCE.
2. **NeoForge** (`mmm/loaders/neoforge.py`): descarga
   `neoforge-<v>-installer.jar` del maven y lo ejecuta con `java -jar` sin
   verificar hash. Mismo riesgo.

## Política transversal: fail-closed

Si el hash esperado **no está disponible** (el panel no lo publica, el maven no
sirve el `.sha256`, o viene vacío/None), se **rechaza** la operación y no se
ejecuta nada. Nunca se ejecuta un binario cuyo hash no se pudo verificar.

## Seguridad #2 — Integridad del instalador de auto-update

### Panel (`minecraft-server`)

- **`db.py`**: migración idempotente que añade la columna `sha256 TEXT` a
  `app_release` (mismo patrón `PRAGMA table_info` + `ALTER TABLE ADD COLUMN`
  usado para `servers.dist_key`). Nullable (releases antiguas sin hash).
- **`distribution.py`**:
  - `publish_app(version, filename, data)`: calcula
    `hashlib.sha256(data).hexdigest()` y lo inserta en `app_release.sha256`.
  - `publish_app_stream(...)`: calcula el sha256 **al vuelo** mientras vuelca los
    trozos a disco (igual que `add_upload_stream`), y lo inserta.
  - `latest_app()` ya hace `SELECT *` → arrastra `sha256` sin cambios.
- **`pub_api.py`**: `GET /pub/app/version` añade `"sha256": latest["sha256"]`
  (o `null` si no hay app publicada).

### Cliente (MakroModManager)

- **`mmm/hashing.py`** (NUEVO, helper compartido):
  - `sha256_file(path) -> str`.
  - `verify_sha256(path, expected)`: lanza `HashInvalido` si `expected` es
    vacío/None (fail-closed) o si `sha256_file(path) != expected`
    (case-insensitive).
- **`mmm/__main__.py`** · `_download_and_launch(info)`: tras `download_app(dest)`,
  llama `verify_sha256(dest, info.get("sha256"))`. Si lanza → borra el archivo,
  muestra `messagebox.showerror` y **no** hace `Popen`.

## Seguridad #3 — Integridad del jar de NeoForge

### Cliente (`mmm/loaders/neoforge.py`)

- `expected_sha256(loader_version) -> str`: `GET installer_url()+".sha256"`,
  `.strip()`. (Verificado: el maven devuelve 64 hex planos, sin nombre ni
  espacios.) Si el status no es 200 → lanza (fail-closed).
- `download_installer(loader_version, dest)`: tras escribir el jar, verifica con
  `hashing.verify_sha256(dest, expected_sha256(loader_version))`. Si falla →
  borra el jar y lanza `RuntimeError`. Así nunca se ejecuta un jar no verificado.

## Consolidación del helper de hashing

`mmm/sync.py` ya tiene su propio `sha256_file`. Se **elimina** y se importa
`from .hashing import sha256_file`, manteniendo el comportamiento idéntico (los
tests existentes de `sync` deben seguir verdes sin cambios). Único punto de
verdad para hashing en el cliente: `mmm/hashing.py`.

## Testing (TDD)

**Panel** (`tests/test_distribution.py`, `tests/test_pub_api.py`):
- `publish_app` almacena `sha256 == hashlib.sha256(data).hexdigest()`.
- `publish_app_stream` almacena el sha256 correcto del contenido subido.
- `GET /pub/app/version` devuelve el `sha256` de la última release (y `null`
  cuando no hay ninguna).

**Cliente #2** (`tests/`):
- `verify_sha256`: pasa con hash correcto; lanza con hash incorrecto; lanza con
  `expected` None/"" (fail-closed).
- `_download_and_launch`: con `api.download_app` y `subprocess.Popen`
  monkeypatcheados, un `sha256` que no coincide → **no** se llama a `Popen` y se
  borra el archivo descargado.

**Cliente #3** (`tests/`):
- `expected_sha256`: parsea el `.sha256` (mock de `SESSION.get`); status ≠ 200
  → lanza.
- `download_installer`: hash correcto → deja el jar; hash incorrecto → borra y
  lanza.

## Fuera de alcance

- #5 (firmar el instalador con signtool): aplazado, requiere certificado.
- Consolidar el `sha256_file` del panel (`app/distribution.py`) — es otro repo y
  no aporta al objetivo actual.

## Cierre

Al terminar #2+#3: recompilar y **republicar el instalador una sola vez**, junto
con Seguridad #1 (path traversal) y el reorden de UI ya hechos en esta sesión.
El panel se despliega aparte (scp + restart de `papulandia-panel.service`).
