# CLAUDE.md — Gestor de Horarios GIM (UPCT)
Última actualización: 2026-03-15 (sesión 5b) — Detalle técnico en TECHNICAL.md

## Proyecto
Visualización de horarios del Grado en Ingeniería Mecánica (UPCT). 4 cursos, 2 cuatrimestres, 15 grupos, 57 asignaturas, 3325 clases. Servidor Python + HTML/JS en un solo fichero, BD SQLite, web en `http://localhost:8080`.

## Ficheros clave
- `servidor_horarios.py` — servidor + frontend completo
- `rebuild_db.py` — parsea EXCELS/ → `horarios.db`
- `rebuild_fichas.py` — parsea `fichas.pdf` → tabla `fichas` en la BD
- `update_calendario.py` — genera `horarios_2627.db` desde `horarios.db` (nunca modifica el original)
- `horarios.db` — **SAGRADA, nunca modificar directamente**
- `horarios_2627.db` — calendario 2026-2027 (regenerable con `update_calendario.py`)

## Arrancar el servidor
Doble clic en el `.command` correspondiente (recomendado — evita problemas de I/O con Dropbox):
- `Iniciar Horarios GIM.command` → copia `horarios.db` a `/tmp` y arranca (2025-2026). **Los cambios se guardan de vuelta al cerrar la ventana.**
- `Iniciar Horarios GIM 2627.command` → copia `horarios_2627.db` a `/tmp` y arranca (2026-2027). **Los cambios se guardan de vuelta al cerrar la ventana.**

⚠ **Los launchers ya NO reconstruyen desde Excel automáticamente.** Para reconstruir (perderás ediciones manuales):
```bash
python3 rebuild_db.py && python3 rebuild_fichas.py   # reconstruir 2025-2026 desde Excel
python3 update_calendario.py                          # regenerar 2026-2027 desde 2025-2026
```

Manual:
```bash
python3 servidor_horarios.py                                          # 2025-2026
DB_PATH_OVERRIDE="horarios_2627.db" CURSO_LABEL="2026-2027" python3 servidor_horarios.py  # 2026-2027
kill $(lsof -ti:8080) && python3 servidor_horarios.py                 # si el puerto está ocupado
```

## Regenerar datos
```bash
# Horarios cambian (nuevos Excel):
python3 rebuild_db.py && python3 rebuild_fichas.py && python3 update_calendario.py

# Solo fichas cambian (nuevo PDF):
python3 rebuild_fichas.py && python3 update_calendario.py

# Solo calendario 2026-2027 cambia (editar CAL_1C/CAL_2C en update_calendario.py):
python3 update_calendario.py
```

## BD — resumen
6 tablas: `asignaturas`, `grupos`, `semanas`, `clases`, `fichas`, `franjas`. Tipo de actividad en campo `aula` de `clases`: vacío=AF1(teoría), LAB=AF2, INFO/Aula:=AF4, otro=PS. `es_no_lectivo=1` bloquea la columna entera en la vista. Cada franja = 2 horas. Claves de grupo: `{curso}_{cuat}_grupo_{num}`, ej. `1_1C_grupo_1`.

## Vistas
- **Semana**: grilla L-V × 6 franjas + panel acumulado + export PDF
- **Todas**: scroll vertical de las 16 semanas + export PDF multipágina
- **Estadísticas**: horas reales vs fichas por asignatura/subgrupo, badges verde/rojo
- **Parciales**: calendario global de exámenes, chequeo de conflictos de turno entre cursos consecutivos (1º-2º, 2º-3º, 3º-4º)

## Advertencias críticas
- `horarios.db` es la fuente de verdad. Si Dropbox la sobreescribe: `python3 rebuild_db.py && python3 rebuild_fichas.py`
- Dropbox causa `sqlite3.OperationalError: disk I/O error` — los launchers copian la BD a `/tmp` antes de arrancar
- `update_calendario.py` NUNCA toca `horarios.db`; siempre genera `horarios_2627.db` aparte
- AF5 = eval. continua en horario lectivo; AF6 = eval. final/continua fuera de horario (solo referencia, no verificadas contra horario)
- Para cambiar calendario 2026-2027: editar `CAL_1C`/`CAL_2C` en `update_calendario.py` y reejecutar

## Detalle técnico
Ver `TECHNICAL.md` para: esquema SQL completo, lista de grupos, franjas, API JSON, funciones JS, lógica de scripts, histórico de sesiones.
