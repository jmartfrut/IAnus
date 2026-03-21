# TECHNICAL.md — Gestor de Horarios GIM (UPCT)
Referencia técnica detallada. Ver CLAUDE.md para lo operativo.

---

## Esquema SQL

```sql
CREATE TABLE asignaturas (id INTEGER PRIMARY KEY AUTOINCREMENT, codigo TEXT NOT NULL, nombre TEXT NOT NULL);
CREATE TABLE grupos (id INTEGER PRIMARY KEY AUTOINCREMENT, curso INTEGER, cuatrimestre TEXT, grupo TEXT, aula TEXT, clave TEXT);
CREATE TABLE franjas (id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT, orden INTEGER);
CREATE TABLE semanas (id INTEGER PRIMARY KEY AUTOINCREMENT, grupo_id INTEGER REFERENCES grupos(id), numero INTEGER, descripcion TEXT);
CREATE TABLE clases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semana_id INTEGER REFERENCES semanas(id),
    dia TEXT,             -- 'LUNES'..'VIERNES'
    franja_id INTEGER REFERENCES franjas(id),
    asignatura_id INTEGER REFERENCES asignaturas(id),  -- NULL si es_no_lectivo
    aula TEXT,            -- ''=teoria, 'LAB'=lab, 'INFO'/'Aula:'=info, otro=PS
    subgrupo TEXT,
    observacion TEXT,     -- 'Parcial 1', 'Parcial 2', etc.
    es_no_lectivo INTEGER,
    contenido TEXT
);
CREATE TABLE fichas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asignatura_id INTEGER NOT NULL UNIQUE REFERENCES asignaturas(id) ON DELETE CASCADE,
    creditos REAL DEFAULT 0,
    af1 INTEGER DEFAULT 0,  -- Clases teóricas (horas)
    af2 INTEGER DEFAULT 0,  -- Prácticas laboratorio
    af4 INTEGER DEFAULT 0,  -- Prácticas informática/aula
    af5 INTEGER DEFAULT 0,  -- Eval. continua en horario lectivo
    af6 INTEGER DEFAULT 0   -- Eval. final/continua fuera de horario
);
```

## Grupos (15 total)

`1_1C_grupo_1`, `1_1C_grupo_2`, `1_2C_grupo_1`, `1_2C_grupo_2`,
`2_1C_grupo_1`, `2_1C_grupo_2`, `2_2C_grupo_1`, `2_2C_grupo_2`,
`3_1C_grupo_1`, `3_1C_grupo_2`, `3_2C_grupo_1`, `3_2C_grupo_2`,
`4_1C_grupo_1`, `4_1C_grupo_2`, `4_2C_grupo_unico`

## Franjas horarias

| ID | Horario | Turno |
|----|---------|-------|
| 1 | 9:00–10:50 | mañana |
| 2 | 11:10–13:00 | mañana |
| 3 | 13:10–15:00 | mañana |
| 4 | 15:00–16:50 | tarde |
| 5 | 17:10–19:00 | tarde |
| 6 | 19:10–21:00 | tarde |

Turno: `franja_orden ≤ 3` = mañana, `≥ 4` = tarde. Cada franja = 2 horas.

---

## API — `GET /api/schedule`

```json
{
  "franjas": [{"id":1,"label":"9:00 - 10:50","orden":1}, ...],
  "asignaturas": [{"id":1,"codigo":"508101005","nombre":"Expresión Gráfica"}, ...],
  "grupos": {
    "1_1C_grupo_1": {
      "semanas": [{
        "semana_id":17, "numero":1, "descripcion":"SEMANA 1: ...",
        "clases": [{"id":203,"dia":"LUNES","franja_id":1,"asignatura_id":2,
                    "aula":"","subgrupo":"","observacion":null,"es_no_lectivo":0,
                    "contenido":"[508101005] Expresión Gráfica",
                    "franja_label":"9:00 - 10:50","franja_orden":1,
                    "asig_codigo":"508101005","asig_nombre":"Expresión Gráfica"}, ...]
      }]
    }
  },
  "fichas": {"508101005": {"creditos":6.0,"af1":45,"af2":0,"af4":15,"af5":0,"af6":7}}
}
```

Otros endpoints: `POST /api/clase/update`, `POST /api/clase/create`, `POST /api/clase/delete`, `POST /api/asignatura`.

---

## Variables de entorno del servidor

| Variable | Descripción |
|----------|-------------|
| `DB_PATH_OVERRIDE` | Ruta alternativa a la BD (evita I/O Dropbox) |
| `CURSO_LABEL` | Año mostrado en el título (defecto: `"2025-2026"`) |

---

## Frontend JS — funciones clave

| Función | Descripción |
|---------|-------------|
| `loadData()` | Llama `/api/schedule`, rellena `DB`, resetea `_subjectColorCache`, llama `render()` |
| `render()` | Despacha a `renderWeek/AllWeeks/Stats/Parciales()` |
| `computeGroupStats(weeks)` | Horas por asignatura/subgrupo |
| `buildActTable(allAsigs)` | Tabla AF1/AF2/AF4 real vs ficha |
| `buildCumulativePanel()` | Panel horas acumuladas |
| `getActType(cls)` | Tipo actividad desde campo `aula` |
| `getTurno(franjaOrden)` | `'mañana'` (1-3) o `'tarde'` (4-6) |
| `renderParciales()` | Calendario parciales + chequeo conflictos |
| `exportPDF()` / `exportAllPDF()` | html2canvas + jsPDF sin diálogo |
| `buildSubjectColorCache()` | Construye mapa `asig_codigo → clase CSS color-N` agrupando por curso |
| `getSubjectColor(codigo)` | Devuelve clase CSS de color; llama a `buildSubjectColorCache()` si no está inicializado |

**`computeGroupStats`**: teoría/PS/parcial deduplicados por `(asig_codigo, tipo, sem, dia, franja_id)`; INFO/LAB deduplicados por subgrupo en `infoBySubgrupo`/`labBySubgrupo`.

**`buildActTable`**: compara `AF1real=teoria×2`, `AF2real=max(lab subgrupos)×2`, `AF4real=max(info subgrupos)×2` contra ficha. AF5/AF6 solo referencia. Fila roja si falla, verde si ok.

**`noLectivoDays`**: `dc.some(c => c.es_no_lectivo)` — cualquier día con entrada no-lectiva bloquea la columna entera.

**Sistema de colores por curso**: `COLORS` contiene 15 clases CSS (`color-0` … `color-14`) con colores muy diferenciados (espaciados 24° en el círculo cromático: rojo→naranja→amarillo→verde→cian→azul→violeta→rosa). `buildSubjectColorCache()` recorre `DB.grupos`, mapea cada `asig_codigo` a su `curso`, ordena los códigos alfabéticamente dentro de cada curso y asigna `COLORS[idx % 15]`. El índice se reinicia en cada curso, por lo que los colores pueden repetirse entre cursos distintos pero son únicos dentro del mismo. La caché (`_subjectColorCache`) se invalida en cada `loadData()`.

---

## Scripts de mantenimiento

### rebuild_db.py
- Lee `EXCELS/1º-4º GIM.xlsx`, detecta columna tiempo (regex HH:MM) y columnas días
- Deduplica con `seen_franja_ids` para celdas con span de filas
- Resultado: 57 asignaturas, 15 grupos, 240 semanas, 3325 clases

### rebuild_fichas.py
Matching PDF→BD: override manual → normalización → exacta → prefijo → tokens (≥60%).
Resultado esperado: 57/57. Acepta `db_path`: `from rebuild_fichas import rebuild; rebuild(db_path='...')`.

### update_calendario.py
Genera `horarios_2627.db` desde `horarios.db` sin tocarlo.
- Trabaja en `/tmp/horarios_2627_work.db`, escribe resultado con `fsync`
- Funciones: `build_semana_dates()`, `festivos_por_semana()`, `postlectivos_por_semana()`, `nota_vacaciones()`
- `postlectivos_por_semana()`: días de Sem16 tras `fin_lectivo` → NO LECTIVO

**Calendario 2026-2027:**

| Cuat | Inicio | Fin | Vacaciones | Festivos |
|------|--------|-----|------------|---------|
| 1C | 7-sep-2026 | 22-dic-2026 | — | 18-sep, 25-sep, 1-oct, 12-oct, 7-dic, 8-dic |
| 2C | 1-feb-2027 | 28-may-2027 | 22-26 feb | 12-feb, 19-feb, 29-mar, 30-mar |

Post-lectivos 1C Sem16: mié 23-dic, jue 24-dic, vie 25-dic.

---

## Dependencias

```bash
pip install pdfplumber openpyxl --break-system-packages
# JS (CDN): html2canvas 1.4.1, jsPDF 2.5.1 — cdnjs.cloudflare.com
```

---

## Histórico de sesiones

**Sesión 1**: diseño inicial, rebuild_db.py, vistas semana/todas/stats básica.
**Sesión 2**: fix duplicados (`seen_franja_ids`), stats por subgrupo, panel acumulado, PDF directo, verificación fichas.
**Sesión 3**: fichas a BD SQLite (`rebuild_fichas.py`), AF5/AF6, verificación presencial, banner estado.
**Sesión 4**: corrección AF5/AF6, vista Parciales, chequeo conflictos de turno (1 conflicto en 1C Sem9 mié tarde).
**Sesión 5**: dos BD/dos cursos, `update_calendario.py`, post-lectivos automáticos, dos launchers, `CURSO_LABEL`, fix `noLectivoDays`, fix I/O Dropbox.
**Sesión 6**: nuevo sistema de colores — paleta de 15 colores diferenciados (24° entre sí en HSC) asignados por curso; colores se reinician en cada curso y pueden repetirse entre cursos distintos.
