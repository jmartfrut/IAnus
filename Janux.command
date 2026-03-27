#!/bin/bash
# ─────────────────────────────────────────────
#  Janux — Configuración de Grados
#  Doble clic para abrir el asistente en el navegador
#  Opciones: Grado nuevo · Doble Grado (PCEO)
# ─────────────────────────────────────────────
cd "$(dirname "$0")"

# Matar proceso anterior en puerto 8091 si existe
OLD_PID=$(lsof -ti:8091 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "⚠  Puerto 8091 ocupado (PID $OLD_PID) — cerrando proceso anterior..."
    kill "$OLD_PID"
    sleep 1
fi

echo "🚀  Arrancando Janux en http://127.0.0.1:8091 ..."
python3 nuevo_grado.py
