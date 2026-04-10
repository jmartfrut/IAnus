#!/usr/bin/env python3
"""
sync_festivos.py — Sincroniza la tabla festivos_calendario con los datos del config.json.

Uso:
    python3 tools/sync_festivos.py horarios/GIM
    python3 tools/sync_festivos.py horarios/GIDI

El script actualiza tipo y descripción de los festivos existentes y añade los que
falten. No elimina entradas que estén en la BD pero no en el config (pueden ser
días marcados manualmente desde la interfaz).
"""

import sys, json, sqlite3
from pathlib import Path

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 tools/sync_festivos.py horarios/<GRADO>")
        sys.exit(1)

    grado_dir = Path(sys.argv[1])
    config_path = grado_dir / "config.json"
    db_path = grado_dir / "horarios.db"

    if not config_path.exists():
        print(f"ERROR: no se encuentra {config_path}")
        sys.exit(1)
    if not db_path.exists():
        print(f"ERROR: no se encuentra {db_path}")
        sys.exit(1)

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    cal = config.get("calendario", {})

    # Recopilar todos los festivos del config.json
    festivos = {}  # fecha -> {tipo, descripcion}

    def add(f_list):
        for f in f_list or []:
            if isinstance(f, str):
                fecha, tipo, desc = f, "no_lectivo", ""
            else:
                fecha = f.get("fecha", "")
                tipo  = f.get("tipo", "no_lectivo") or "no_lectivo"
                desc  = f.get("descripcion", "") or ""
            if fecha:
                festivos[fecha] = {"tipo": tipo, "descripcion": desc}

    # 1C y 2C
    add(cal.get("1C", {}).get("festivos", []))
    add(cal.get("2C", {}).get("festivos", []))

    # Periodos de exámenes
    for periodo in cal.get("periodos_examenes", {}).values():
        add(periodo.get("festivos", []))

    if not festivos:
        print("No se encontraron festivos en config.json.")
        return

    print(f"Festivos encontrados en config.json: {len(festivos)}")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS festivos_calendario (
                fecha TEXT PRIMARY KEY,
                tipo TEXT NOT NULL DEFAULT 'no_lectivo',
                descripcion TEXT DEFAULT ''
            )
        """)

        updated = 0
        inserted = 0
        for fecha, data in sorted(festivos.items()):
            existing = conn.execute(
                "SELECT tipo, descripcion FROM festivos_calendario WHERE fecha=?", (fecha,)
            ).fetchone()
            if existing:
                if existing[0] != data["tipo"] or existing[1] != data["descripcion"]:
                    conn.execute(
                        "UPDATE festivos_calendario SET tipo=?, descripcion=? WHERE fecha=?",
                        (data["tipo"], data["descripcion"], fecha)
                    )
                    print(f"  UPDATED  {fecha}  {data['tipo']:12}  {data['descripcion']!r}  (era: {existing[0]!r}, {existing[1]!r})")
                    updated += 1
                else:
                    print(f"  OK       {fecha}  {data['tipo']:12}  {data['descripcion']!r}")
            else:
                conn.execute(
                    "INSERT INTO festivos_calendario (fecha, tipo, descripcion) VALUES (?,?,?)",
                    (fecha, data["tipo"], data["descripcion"])
                )
                print(f"  INSERTED {fecha}  {data['tipo']:12}  {data['descripcion']!r}")
                inserted += 1

        conn.commit()
        print(f"\nResultado: {updated} actualizados, {inserted} insertados.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
