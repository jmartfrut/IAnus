@echo off
chcp 65001 > nul
title Asistente — Crear Nuevo Grado (Janux)
cd /d "%~dp0.."
echo ----------------------------------------
echo  Janux - Asistente de Nuevo Grado
echo ----------------------------------------
REM Detectar comando Python (python o py launcher de Windows)
set "PYTHON_CMD="
python --version > nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"
if not defined PYTHON_CMD (
    py --version > nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py"
)
if not defined PYTHON_CMD (
    echo.
    echo [ERROR] Python no esta instalado o no esta en el PATH.
    echo.
    echo  1. Ve a https://www.python.org/downloads/
    echo  2. Descarga Python 3.9 o superior
    echo  3. En el instalador marca "Add Python to PATH"
    echo  4. Completa la instalacion y vuelve a ejecutar este fichero
    echo.
    pause
    exit /b 1
)
REM Verificar e instalar dependencias Python (openpyxl necesario para importar Excel)
echo [INFO] Verificando dependencias...
%PYTHON_CMD% -m pip install -r requirements.txt --quiet 2>nul
if errorlevel 1 (
    echo [AVISO] No se pudieron instalar algunas dependencias. Continuando...
)

echo [INFO] Arrancando asistente en http://localhost:8092 ...
%PYTHON_CMD% tools\nuevo_grado.py
pause
