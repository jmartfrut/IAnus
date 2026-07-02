#!/usr/bin/env python3
"""
reparar_codigos_finales.py — Rellena asig_codigo en examenes_finales

Los exámenes creados a mano en la vista Finales solo guardan el nombre de la
asignatura, dejando asig_codigo vacío. Eso impide que sync_dtie.py los copie
a los dobles grados DTIE. Este script empareja esos exámenes por nombre
normalizado (mayúsculas, acentos, puntos, espacios) contra la tabla
asignaturas de la misma BD y rellena el código.

Uso:
    python3 tools/reparar_codigos_finales.py horarios/GIM
    python3 tools/reparar_codigos_finales.py horarios/GIDI --dry-run

Solo escribe en la columna asig_codigo de examenes_finales; no toca fechas,
turnos ni ninguna otra tabla. Con --dry-run muestra lo que haría sin escribir.
"""

import argparse
import io
import sqlite3
import sys
import unicodedata
from pathlib import Path

# Forzar UTF-8 en stdout/stderr (Windows cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding and sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.parent


def norm_nombre(s):
    """Normaliza un nombre de asignatura para comparaciones tolerantes:
    mayúsculas, sin acentos, sin puntos y con espacios colapsados."""
    s = unicodedata.normalize('NFD', s or '')
    s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
    return ' '.join(s.upper().replace('.', ' ').split())


def main():
    parser = argparse.ArgumentParser(
        description='Rellena asig_codigo vacío en examenes_finales emparejando '
                    'por nombre contra la tabla asignaturas.')
    parser.add_argument('grado_dir', help='Carpeta del grado (ej. horarios/GIM)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Muestra los cambios sin escribir en la BD.')
    args = parser.parse_args()

    grado_dir = BASE_DIR / args.grado_dir
    db_path = grado_dir / 'horarios.db'
    if not db_path.exists():
        print(f"❌ No se encuentra la BD: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    try:
        # Mapa nombre normalizado -> código (detectando ambigüedades)
        nombres = {}
        ambiguos = set()
        for cod, nom in conn.execute("SELECT codigo, nombre FROM asignaturas"):
            k = norm_nombre(nom)
            if k in nombres and nombres[k] != str(cod):
                ambiguos.add(k)
            nombres[k] = str(cod)

        pendientes = conn.execute(
            "SELECT id, asig_nombre, fecha FROM examenes_finales "
            "WHERE asig_codigo IS NULL OR TRIM(asig_codigo) = '' "
            "ORDER BY fecha").fetchall()

        if not pendientes:
            print("✅ No hay exámenes sin código. Nada que hacer.")
            return

        print(f"🔎 {len(pendientes)} examen(es) sin asig_codigo en {args.grado_dir}\n")
        n_ok = n_sin_match = n_ambiguos = 0
        for ef_id, nom, fecha in pendientes:
            # Ignorar sufijos ' (1C)' / ' (2C)' de asignaturas anuales
            base = nom or ''
            for suf in (' (1C)', ' (2C)'):
                if base.endswith(suf):
                    base = base[:-len(suf)]
            k = norm_nombre(base)
            if k in ambiguos:
                print(f"  ⚠️  id={ef_id} {fecha} «{nom}»: nombre ambiguo "
                      f"(varios códigos), se omite")
                n_ambiguos += 1
                continue
            cod = nombres.get(k)
            if not cod:
                print(f"  ❌ id={ef_id} {fecha} «{nom}»: sin coincidencia en asignaturas")
                n_sin_match += 1
                continue
            print(f"  ✅ id={ef_id} {fecha} «{nom}» → {cod}")
            if not args.dry_run:
                conn.execute(
                    "UPDATE examenes_finales SET asig_codigo = ? WHERE id = ?",
                    (cod, ef_id))
            n_ok += 1

        if not args.dry_run:
            conn.commit()

        print(f"\n{'[DRY RUN] ' if args.dry_run else ''}"
              f"Resumen: {n_ok} rellenados, {n_sin_match} sin coincidencia, "
              f"{n_ambiguos} ambiguos")
        if n_sin_match or n_ambiguos:
            print("   Revisa los no emparejados y corrígelos desde la vista Finales.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
