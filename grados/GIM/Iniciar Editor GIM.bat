@echo off
chcp 65001 > nul
title Editor de Configuracion GIM — UPCT

cd /d "%~dp0"
set "GRADO_DIR=%~dp0"
set "ROOT_DIR=%~dp0..\.."

echo ----------------------------------------
echo  Editor de Configuracion GIM — UPCT
echo ----------------------------------------

REM Matar proceso anterior en puerto 8090
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr /r ":8090 "') do (
    taskkill /F /PID %%a > nul 2>&1
)

echo [INFO] Arrancando editor de configuracion para GIM...
python "%ROOT_DIR%\editor_server.py" "%GRADO_DIR%"
pause
