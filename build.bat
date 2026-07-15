@echo off
setlocal
set PYTHON=python
set INNO="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="C:\Program Files\Inno Setup 6\ISCC.exe"

echo [1/4] Verificando JRE bundleado (runtime\bin\java.exe)...
if not exist "runtime\bin\java.exe" (
    echo [ERROR] Falta la carpeta runtime\ con el JRE.
    echo         Genera el JRE con jlink (ver INSTRUCCIONES.md) antes de compilar.
    pause & exit /b 1
)

echo [2/4] Instalando dependencias...
%PYTHON% -m pip install -r requirements-dev.txt

echo [3/4] Compilando con PyInstaller...
%PYTHON% -m PyInstaller MakroModManager.spec --noconfirm
if %errorlevel% neq 0 ( echo [ERROR] PyInstaller fallo. & pause & exit /b 1 )

echo [4/4] Creando instalador con Inno Setup...
if not exist %INNO% (
    echo [!] Inno Setup no encontrado. El exe esta en dist\MakroModManager\
    pause & exit /b 1
)
call %INNO% installer.iss
if %errorlevel% neq 0 ( echo [ERROR] Inno Setup fallo. & pause & exit /b 1 )

echo LISTO: installer_output\MakroModManager_setup.exe
pause
