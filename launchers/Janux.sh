#!/bin/bash
# ─────────────────────────────────────────────
#  Janux — Asistente de Nuevo Grado
# ─────────────────────────────────────────────
cd "$(dirname "$0")/.."
echo "🔍  Verificando dependencias..."
python3 -m pip install -r requirements.txt --quiet 2>/dev/null || true
echo "🚀  Arrancando asistente en http://localhost:8091 ..."
python3 tools/nuevo_grado.py
