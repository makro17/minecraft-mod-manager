@echo off
echo Limpiando compilaciones...
if exist build            rmdir /s /q build
if exist dist             rmdir /s /q dist
if exist installer_output rmdir /s /q installer_output
for /d /r %%d in (__pycache__) do if exist "%%d" rmdir /s /q "%%d"
echo Limpieza completada.
pause
