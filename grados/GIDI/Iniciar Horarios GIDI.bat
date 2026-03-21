@echo off
chcp 65001 > nul
title Gestor de Horarios GIDI — UPCT (2026-2027)

cd /d "%~dp0"
set "GRADO_DIR=%~dp0"
set "ROOT_DIR=%~dp0..\.."
set "DB_NAME=horariosGIDI.db"
set "TMP_DB=%TEMP%\horarios_gidi.db"

echo ----------------------------------------
echo  Gestor de Horarios GIDI  (2026-2027)
echo  UPCT
echo ----------------------------------------

REM Verificar que Python esta instalado
python --version > nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo.
    echo  Para instalar Python:
    echo  1. Ve a https://www.python.org/downloads/
    echo  2. Descarga la version mas reciente (3.9 o superior)
    echo  3. En el instalador, marca "Add Python to PATH"  ^<-- MUY IMPORTANTE
    echo  4. Completa la instalacion y vuelve a ejecutar este fichero
    echo.
    pause
    exit /b 1
)

REM Matar proceso anterior en puerto 8080
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /r ":8080 "') do (
    taskkill /F /PID %%a > nul 2>&1
)

REM Verificar que existe la BD
if not exist "%DB_NAME%" (
    echo [ERROR] No se encuentra %DB_NAME% en %GRADO_DIR%
    echo         Ejecuta primero el editor de configuracion para generar la BD.
    pause
    exit /b 1
)

REM Copiar la BD a TEMP para evitar errores de I/O en rutas de red
echo [INFO] Copiando base de datos a directorio local...
copy "%DB_NAME%" "%TMP_DB%" > nul
if errorlevel 1 (
    echo [ERROR] No se pudo copiar %DB_NAME%
    pause
    exit /b 1
)
echo [OK]   Base de datos lista en %TMP_DB%

REM Arrancar servidor en segundo plano
echo [INFO] Arrancando servidor de horarios GIDI (2026-2027)...
set DB_PATH_OVERRIDE=%TMP_DB%
set CURSO_LABEL=2026-2027
set CONFIG_PATH_OVERRIDE=%GRADO_DIR%config.json

start /b python "%ROOT_DIR%\servidor_horarios.py"

REM Esperar a que el servidor este listo (max 5 seg)
set /a intentos=0
:esperar
timeout /t 1 /nobreak > nul
set /a intentos+=1
curl -s --noproxy "*" http://localhost:8080 > nul 2>&1
if not errorlevel 1 goto listo
if %intentos% LSS 5 (
    echo    Esperando... (%intentos%/5)
    goto esperar
)
:listo
echo [OK]   Servidor listo en http://localhost:8080
start "" http://localhost:8080

echo.
echo ----------------------------------------
echo  Servidor corriendo
echo  Grado: GIDI   Curso: 2026-2027
echo  Cierra esta ventana para detenerlo
echo ----------------------------------------

REM Mantener la ventana abierta hasta que el usuario la cierre
pause > nul

REM Al salir: guardar la BD actualizada de vuelta al directorio del grado
echo.
echo [INFO] Guardando BD actualizada...
copy "%TMP_DB%" "%DB_NAME%" > nul
if errorlevel 1 (
    echo [ERROR] No se pudo guardar %DB_NAME%
) else (
    echo [OK]   %DB_NAME% guardado correctamente.
)

REM Cerrar el servidor
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /r ":8080 "') do (
    taskkill /F /PID %%a > nul 2>&1
)
pause
