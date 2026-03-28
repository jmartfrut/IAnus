#!/bin/bash
# ─────────────────────────────────────────────
#  Janux — Asistente de Nuevo Grado
# ─────────────────────────────────────────────
cd "$(dirname "$0")/.."
echo "🚀  Arrancando asistente en http://localhost:8091 ..."
python3 tools/nuevo_grado.py
