# MakroModManager — Compilación y publicación

## 1. Generar el JRE bundleado (una vez por versión de Java)

Requiere un JDK 21 instalado. Genera un JRE recortado con jlink en `runtime/`:

```bat
jlink --add-modules java.base,java.desktop,java.logging,java.naming,java.net.http,jdk.crypto.ec,java.security.jgss,java.instrument,java.management,java.sql,jdk.unsupported,jdk.zipfs ^
      --strip-debug --no-header-files --no-man-pages --compress=2 ^
      --output runtime
```

> Verifica: `runtime\bin\java.exe -version`. Los módulos deben cubrir lo que usan
> los *processors* de NeoForge (crypto, zipfs, etc.). Ajusta la lista si el
> instalador de NeoForge falla por un módulo ausente.

## 2. Compilar

```bat
build.bat
```

Genera `installer_output\MakroModManager_setup.exe`.
`clean.bat` borra `build/`, `dist/`, `installer_output/`.

## 3. Publicar en el panel (para el auto-update)

El auto-update lee `/pub/app/version` y descarga `/pub/app/download`, que sirve el
instalador registrado en el panel. Para publicar una versión nueva:

1. Sube `MakroModManager_setup.exe` en el panel: tab **MODPACK** → sección global
   **App cliente** → subir instalador + versión (semver, igual que `mmm/version.py`) + notas.
2. La primera instalación se distribuye a mano (no hay auto-update previo).

## 4. Actualizar la versión

Sube el número en `mmm/version.py` **y** en `AppVersion` de `installer.iss` antes de compilar.
