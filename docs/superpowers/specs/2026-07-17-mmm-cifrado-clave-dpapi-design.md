# Diseño — Cifrado de la clave de distribución con DPAPI (Seguridad #4)

> Fecha: 2026-07-17
> Repo: `minecraft-mod-manager` (cliente MakroModManager)
> Estado: aprobado, pendiente de plan de implementación.

## Problema

La clave de distribución de cada servidor (`PPL-XXXX-XXXX-XXXX`) se guarda **en claro**
dentro del array `servers` de `%APPDATA%\MakroModManager\state.json` (campo
`server["key"]`). Es el único secreto del archivo: permite resolver el modpack, bajar el
manifiesto y descargar los ficheros. Cualquiera que lea ese JSON (otra cuenta de Windows
en el mismo PC, una copia del archivo en un backup / sync en la nube / adjunto) obtiene la
clave utilizable.

## Objetivo

Cifrar en reposo el campo `key` de cada servidor usando **DPAPI** (Windows Data Protection
API, user-scope), de forma que el `state.json` en disco no contenga la clave en claro.

## Alcance del cifrado (qué protege DPAPI, honestamente)

DPAPI user-scope liga el cifrado a la cuenta de Windows actual. Por tanto **sí** protege
cuando el `state.json`:
- se copia a otra máquina,
- lo lee otra cuenta de Windows del mismo equipo.

En esos casos la clave queda **inservible** (no descifra). **No** protege contra malware
ejecutándose como el *propio* usuario (podría llamar a `CryptUnprotectData` igual). Es un
endurecimiento razonable para una clave de distribución, no un secreto de alto valor.

## No objetivos (YAGNI)

- Cifrar el resto de `state.json` (username, rutas, flags): no es sensible.
- Entropía secundaria / passphrase adicional en DPAPI.
- Rotación de blobs.
- Firmar el instalador (eso es Seguridad #5, aparte) ni cifrar nada del panel.

## Decisiones de diseño

1. **DPAPI vía `ctypes` a `crypt32.dll`** (`CryptProtectData` / `CryptUnprotectData` con
   `DATA_BLOB`). Sin dependencia nueva: hoy `requirements.txt` es solo `requests`. Evita
   añadir `pywin32` (pesado y con fricción en el bundling de PyInstaller). User-scope, sin
   entropía extra.

2. **El cifrado vive en el borde de `config.py`: descifrar al cargar, cifrar al guardar.**
   El `server["key"]` en memoria es **siempre texto plano**, así que ningún consumidor
   (`worker.py`, `ui/app_window.py`, `ui/server_view.py`) cambia. Solo cambia la forma en
   disco.

3. **Clave ilegible → marcar "reintroduce la clave"** (decisión del usuario). Si el blob no
   descifra, se conserva la fila del servidor y se pide al usuario re-pegar la clave; no se
   borra nada ni se pierden otros servidores.

## Arquitectura

### Componente nuevo: `mmm/secretstore.py`

Único módulo que conoce DPAPI. Interfaz mínima:

- `protect(plaintext: str) -> str`
  Devuelve un **token** `"dpapi:v1:<base64>"`. En no-Windows, modo degradado
  `"plain:v1:<base64>"` (ver abajo).
- `unprotect(token: str) -> str`
  Descifra el token a texto plano. Lanza `CannotDecrypt` si el blob no descifra (p. ej.
  procede de otra máquina/usuario) o si el token está corrupto/mal formado.
- Excepción `CannotDecrypt(Exception)`.

Detalles:
- Formato del token: `"<esquema>:v1:<base64(blob)>"`, con esquema `dpapi` (Windows) o
  `plain` (fallback no-Windows).
- `ctypes`: struct `DATA_BLOB {DWORD cbData; LPBYTE pbData;}`; `CryptProtectData(pDataIn,
  None, None, None, None, 0, pDataOut)` y su inverso; liberar con `LocalFree`; en fallo,
  `unprotect` lanza `CannotDecrypt`.
- **Modo degradado (no-Windows):** `protect` codifica `plain:v1:<base64(utf8)>` y
  `unprotect` lo revierte. La app sigue funcionando fuera de Windows (útil solo para
  desarrollo; producción es Windows-only). Se registra un aviso una sola vez. Un token
  `dpapi:` recibido en no-Windows → `CannotDecrypt` (no hay cómo descifrarlo).

### Cambios en `mmm/config.py`

El cifrado se aplica **solo al campo `key`** de cada elemento de `servers`, en el borde de
E/S:

**`load_state()`** — tras leer el JSON y aplicar defaults, por cada server con `key`:
- si `key` empieza por `dpapi:` o `plain:` → `unprotect(key)`:
  - éxito → `server["key"]` pasa a texto plano.
  - `CannotDecrypt` → `server["key"] = None`, `server["key_locked"] = True`, y se conserva
    el token original en `server["_key_cipher"]` (para no perderlo al re-guardar).
- si `key` es una `PPL-...` en claro (legado, sin prefijo) → se deja tal cual; se migrará
  en el próximo guardado.

**`save_state()`** — antes de serializar, se produce una copia con el `key` transformado
por server; el estado en memoria no se muta:
- si `key_locked` y hay `_key_cipher` → se re-escribe el token original **intacto** (así, si
  el archivo vuelve a la máquina original, la clave se recupera).
- elif `key` es texto plano no vacío → `protect(key)`.
- se omiten los campos transitorios `key_locked` y `_key_cipher` del JSON persistido
  (`_key_cipher` se colapsa de vuelta al campo `key`).

**Migración:** transparente e idempotente. La primera vez que se guarde el estado (cualquier
`save_state`, p. ej. al refrescar metadatos), las `PPL-...` en claro pasan a `dpapi:...`.

`config.py` referencia `secretstore.protect` / `secretstore.unprotect` a nivel de módulo
para que los tests puedan monkeypatchearlos (mismo estilo que la inyección de dependencias
existente en `worker.py`).

### UX de clave bloqueada

- `mmm/ui/format.py`: añadir al mapa `_STATUS` la entrada
  `"clave_bloqueada": ("🔒", "Reintroduce la clave")`.
- `mmm/ui/app_window.py` `_status_for(server)`: si `server.get("key_locked")` → devolver
  `"clave_bloqueada"` **sin** llamar a `api.resolve` (evita pasar `key=None`).
- `mmm/ui/widgets.py` `ServerRow`: cuando el status es `clave_bloqueada`, en lugar del botón
  Instalar/Actualizar mostrar **"Reintroducir clave"**, que dispara un callback nuevo
  (`on_reenter_key`) inyectado desde `app_window`.
- El callback reusa `dialogs.ask_key`; con una clave válida hace
  `server["key"] = nueva; server.pop("key_locked", None); server.pop("_key_cipher", None);
  config.upsert_server(server)` → al guardar se re-cifra y el bloqueo desaparece. Refrescar
  la lista.

## Flujo de datos

```
Añadir servidor  → server["key"]=PPL-... (plano en memoria) → upsert_server
                 → save_state → protect() → disco: "dpapi:v1:..."

Arranque         → load_state → unprotect() → server["key"]=PPL-... (plano en memoria)
                 → consumidores usan server["key"] igual que hoy

state.json de    → load_state → unprotect() lanza CannotDecrypt
otra máquina       → server["key"]=None, key_locked=True, _key_cipher conservado
                 → UI muestra 🔒 "Reintroduce la clave" → ask_key → re-cifra
```

## Manejo de errores

- `unprotect` en carga: `CannotDecrypt` no rompe el arranque; degrada ese server a bloqueado
  y conserva su blob.
- `protect` no debería fallar en Windows para una entrada válida. Si `CryptProtectData`
  devuelve error, `secretstore.protect` lanza `CannotDecrypt` y `save_state` **propaga** la
  excepción (el guardado falla de forma ruidosa): nunca se escribe la clave en claro ni un
  valor corrupto en disco, y el estado en memoria (con la clave en plano) se conserva.
- Token mal formado (base64 inválido, esquema desconocido) → `CannotDecrypt`.

## Estrategia de tests (TDD)

**`tests/test_secretstore.py`**
- round-trip `protect → unprotect` (con monkeypatch del backend o en modo `plain`).
- token corrupto / esquema desconocido → `CannotDecrypt`.
- **gated a Windows** (`@pytest.mark.skipif(sys.platform != "win32")`): round-trip real
  contra `crypt32` para cazar errores de firma en `ctypes`.

**`tests/test_config.py` (ampliado)** — monkeypatch de `secretstore.protect`/`unprotect` con
fakes reversibles + uno que lanza `CannotDecrypt`, para no depender de blobs reales:
- guardar cifra el `key` en disco (el JSON no contiene la `PPL-...`); cargar lo devuelve en
  plano.
- **migración**: `state.json` con `key` en claro → tras `save_state` queda cifrado; el resto
  de campos del server intactos.
- `unprotect` que falla → server con `key_locked=True`, `key=None`; al re-guardar el blob
  original se **preserva** (no se escribe `null`).
- server sin `key` (p. ej. entradas antiguas) no rompe carga/guardado.

Suites de referencia hoy: MMM 93 verdes. La feature añade tests nuevos sin tocar los
existentes salvo el `test_config.py` ampliado.

## Impacto en build / deploy

- **Sin dependencia nueva** → `requirements.txt`, `MakroModManager.spec` e `installer.iss`
  no cambian por esto.
- Toca el cliente → entra en la **recompilación única** del instalador que ya estaba
  pendiente (agrupa Seg #1/#2/#3, reorden UI, IP/scroll y este Seg #4).
- Sin cambios en el panel.

## Archivos

- **NUEVO** `mmm/secretstore.py`
- **NUEVO** `tests/test_secretstore.py`
- **MODIFICADO** `mmm/config.py` (cifrado en `load_state`/`save_state`)
- **MODIFICADO** `mmm/ui/format.py` (`_STATUS["clave_bloqueada"]`)
- **MODIFICADO** `mmm/ui/app_window.py` (`_status_for` + callback re-entrada)
- **MODIFICADO** `mmm/ui/widgets.py` (`ServerRow` botón "Reintroducir clave")
- **MODIFICADO** `tests/test_config.py` (tests de cifrado/migración/bloqueo)
