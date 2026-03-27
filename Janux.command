#!/bin/bash
# ─────────────────────────────────────────────
#  Janux — Configuración de Grados
#  Doble clic para abrir el asistente en el navegador
#  Opciones: Grado nuevo · Doble Grado (PCEO)
# ─────────────────────────────────────────────
cd "$(dirname "$0")"

# Matar proceso anterior en puerto 8091 si existe
if lsof -ti:8091 &>/dev/null; then
    echo "⚠  Puerto 8091 ocupado — cerrando proceso anterior..."
    lsof -ti:8091 | xargs kill -9 2>/dev/null || true
    sleep 2
fi

echo "🚀  Arrancando Janux en http://127.0.0.1:8091 ..."
python3 nuevo_grado.py
