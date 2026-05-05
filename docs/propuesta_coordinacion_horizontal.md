# Propuesta Técnica — Calendario de Coordinación Horizontal
**Janux · UPCT** | Versión destino: **1.38.0** | Fecha: 2026-05-05

---

## 1. Resumen ejecutivo

El Calendario de Coordinación Horizontal es una nueva vista de la aplicación que
muestra una **matriz semana × asignatura** para un grupo concreto, permitiendo
registrar y visualizar las actividades evaluables y de carga especial de cada
semana. Las actividades de tipo LAB, INF y EXP se sincronizan automáticamente
desde el horario; el resto se introducen manualmente.

---

## 2. Modelo de datos

### 2.1 Nueva tabla: `coordinacion_actividades`

```sql
CREATE TABLE IF NOT EXISTS coordinacion_actividades (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    grupo_key        TEXT    NOT NULL,   -- ej. '1_1C_grupo_1'
    semana_num       INTEGER NOT NULL,   -- matches semanas.numero
    asignatura_id    INTEGER NOT NULL REFERENCES asignaturas(id) ON DELETE CASCADE,
    tipo_actividad   TEXT    NOT NULL,   -- 'LAB'|'INF'|'SEM'|'EXP'|'EXF'|'TE'|'EO'|'OA'
    notas            TEXT    DEFAULT '',
    sincronizado     INTEGER DEFAULT 0, -- 0=manual, 1=auto desde horario (no editable)
    ts               TEXT    DEFAULT ''  -- ISO timestamp última modificación
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_coord_unique
    ON coordinacion_actividades(grupo_key, semana_num, asignatura_id, tipo_actividad);
```

**Diseño deliberado:**
- La clave única `(grupo_key, semana_num, asignatura_id, tipo_actividad)` impide
  duplicados mientras permite múltiples tipos distintos en la misma celda.
- `sincronizado=1` marca las entradas generadas automáticamente; el frontend las
  renderiza como "solo lectura" con un icono de candado.
- `grupo_key` es consistente con el resto de tablas dinámicas (p. ej.
  `fichas_override`, `comentarios_horario`).

### 2.2 Migración `_m19`

Añadir al final de `tools/migrate_db.py`:

```python
def _m19_coordinacion_actividades(conn, **ctx):
    """Crea la tabla de actividades del calendario de coordinación horizontal."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS coordinacion_actividades (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            grupo_key      TEXT    NOT NULL,
            semana_num     INTEGER NOT NULL,
            asignatura_id  INTEGER NOT NULL
                               REFERENCES asignaturas(id) ON DELETE CASCADE,
            tipo_actividad TEXT    NOT NULL,
            notas          TEXT    DEFAULT '',
            sincronizado   INTEGER DEFAULT 0,
            ts             TEXT    DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_coord_unique
        ON coordinacion_actividades(grupo_key, semana_num, asignatura_id, tipo_actividad)
    """)
```

Y añadir `_m19_coordinacion_actividades` al array `MIGRATIONS`.

> ⚠️ También añadir el `CREATE TABLE` a `setup_grado.py` y `nuevo_dtie.py` en su
> sección `create_tables()` para que las BDs nuevas arranquen con el esquema correcto.

### 2.3 Catálogo de actividades

Integrar en `config/tipos_actividad.json` (o leer desde el servidor como constante):

```json
{
  "COORD_ACTIVITY_TYPES": [
    { "codigo": "LAB", "descripcion": "Prácticas de laboratorio",         "sync": true  },
    { "codigo": "INF", "descripcion": "Prácticas de informática",         "sync": true  },
    { "codigo": "SEM", "descripcion": "Seminarios / visitas externas",    "sync": false },
    { "codigo": "EXP", "descripcion": "Exámenes parciales",               "sync": true  },
    { "codigo": "EXF", "descripcion": "Exámenes finales",                 "sync": false },
    { "codigo": "TE",  "descripcion": "Trabajos escritos / memorias",     "sync": false },
    { "codigo": "EO",  "descripcion": "Exposición oral",                  "sync": false },
    { "codigo": "OA",  "descripcion": "Otras actividades de evaluación",  "sync": false }
  ]
}
```

---

## 3. API — Nuevos endpoints

Todos los endpoints siguen el patrón existente: responden JSON con `{ ok: true/false, ... }`.

### `GET /api/coordinacion`

Devuelve todas las actividades de un grupo junto con los metadatos necesarios
para renderizar la matriz.

**Parámetros query:** `curso`, `cuatrimestre`, `grupo`

**Respuesta:**
```json
{
  "ok": true,
  "grupo_key": "1_1C_grupo_1",
  "semanas": [
    { "numero": 1, "descripcion": "SEMANA 1: 7 sep – 11 sep" },
    { "numero": 2, "descripcion": "SEMANA 2: 14 sep – 18 sep" }
  ],
  "asignaturas": [
    { "id": 1, "codigo": "508101001", "nombre": "Expresión Gráfica" },
    { "id": 2, "codigo": "508101002", "nombre": "Fundamentos Matemáticos" }
  ],
  "actividades": [
    {
      "id": 12,
      "semana_num": 3,
      "asignatura_id": 1,
      "tipo_actividad": "LAB",
      "notas": "",
      "sincronizado": 1
    },
    {
      "id": 13,
      "semana_num": 5,
      "asignatura_id": 2,
      "tipo_actividad": "EXP",
      "notas": "Parcial temas 1-4",
      "sincronizado": 1
    }
  ]
}
```

**Implementación Python:**
```python
@app.route("/api/coordinacion")
def api_get_coordinacion():
    curso      = request.args.get("curso",       type=int)
    cuatrimestre = request.args.get("cuatrimestre")
    grupo      = request.args.get("grupo")
    grupo_key  = f"{curso}_{cuatrimestre}_grupo_{grupo}"

    with get_db() as conn:
        # Semanas del grupo
        g = conn.execute(
            "SELECT id FROM grupos WHERE curso=? AND cuatrimestre=? AND grupo=?",
            (curso, cuatrimestre, grupo)
        ).fetchone()
        if not g:
            return jsonify({"ok": False, "error": "Grupo no encontrado"}), 404

        semanas = conn.execute(
            "SELECT numero, descripcion FROM semanas WHERE grupo_id=? ORDER BY numero",
            (g["id"],)
        ).fetchall()

        # Asignaturas del cuatrimestre y curso
        asigs = conn.execute(
            """SELECT DISTINCT a.id, a.codigo, a.nombre
               FROM asignaturas a
               JOIN clases cl ON cl.asignatura_id = a.id
               JOIN semanas s ON cl.semana_id = s.id
               WHERE s.grupo_id = ? AND a.curso = ? AND a.cuatrimestre = ?
               ORDER BY a.nombre""",
            (g["id"], curso, cuatrimestre)
        ).fetchall()

        # Actividades registradas
        actividades = conn.execute(
            """SELECT id, semana_num, asignatura_id, tipo_actividad, notas, sincronizado
               FROM coordinacion_actividades
               WHERE grupo_key = ?
               ORDER BY semana_num, asignatura_id""",
            (grupo_key,)
        ).fetchall()

    return jsonify({
        "ok":          True,
        "grupo_key":   grupo_key,
        "semanas":     [dict(s) for s in semanas],
        "asignaturas": [dict(a) for a in asigs],
        "actividades": [dict(x) for x in actividades],
    })
```

---

### `POST /api/coordinacion/set`

Añade o elimina una actividad manual. Las actividades `sincronizado=1` no pueden
modificarse por esta vía.

**Body JSON:**
```json
{
  "grupo_key":      "1_1C_grupo_1",
  "semana_num":     5,
  "asignatura_id":  2,
  "tipo_actividad": "TE",
  "notas":          "Memoria del proyecto",
  "action":         "add"   // "add" | "remove"
}
```

**Implementación Python:**
```python
@app.route("/api/coordinacion/set", methods=["POST"])
def api_set_coordinacion():
    data          = request.json
    grupo_key     = data["grupo_key"]
    semana_num    = int(data["semana_num"])
    asignatura_id = int(data["asignatura_id"])
    tipo          = data["tipo_actividad"]
    notas         = data.get("notas", "")
    action        = data.get("action", "add")
    ts            = datetime.utcnow().isoformat()

    with get_db() as conn:
        # Proteger actividades sincronizadas
        existing = conn.execute(
            """SELECT sincronizado FROM coordinacion_actividades
               WHERE grupo_key=? AND semana_num=? AND asignatura_id=? AND tipo_actividad=?""",
            (grupo_key, semana_num, asignatura_id, tipo)
        ).fetchone()

        if existing and existing["sincronizado"] == 1:
            return jsonify({"ok": False, "error": "Actividad sincronizada, no editable"}), 400

        if action == "remove":
            conn.execute(
                """DELETE FROM coordinacion_actividades
                   WHERE grupo_key=? AND semana_num=? AND asignatura_id=? AND tipo_actividad=?""",
                (grupo_key, semana_num, asignatura_id, tipo)
            )
        else:
            conn.execute(
                """INSERT INTO coordinacion_actividades
                       (grupo_key, semana_num, asignatura_id, tipo_actividad, notas, sincronizado, ts)
                   VALUES (?, ?, ?, ?, ?, 0, ?)
                   ON CONFLICT(grupo_key, semana_num, asignatura_id, tipo_actividad)
                   DO UPDATE SET notas=excluded.notas, ts=excluded.ts""",
                (grupo_key, semana_num, asignatura_id, tipo, notas, ts)
            )
        conn.commit()
    return jsonify({"ok": True})
```

---

### `POST /api/coordinacion/sync`

Re-sincroniza las actividades automáticas (LAB, INF, EXP) desde el horario actual.
Llamar al arrancar la vista y cuando el horario cambie.

**Body JSON:**
```json
{ "grupo_key": "1_1C_grupo_1" }
```

**Implementación Python:**
```python
COORD_SYNC_TIPOS = {"LAB", "INF", "EXP"}

@app.route("/api/coordinacion/sync", methods=["POST"])
def api_sync_coordinacion():
    grupo_key = request.json["grupo_key"]
    # Descomponer grupo_key → curso, cuatrimestre, grupo
    # formato: '{curso}_{cuatrimestre}_grupo_{grupo_num}'
    parts = grupo_key.split("_")
    curso, cuatrimestre, grupo_num = parts[0], parts[1], parts[3]

    with get_db() as conn:
        g = conn.execute(
            "SELECT id FROM grupos WHERE curso=? AND cuatrimestre=? AND grupo=?",
            (curso, cuatrimestre, grupo_num)
        ).fetchone()
        if not g:
            return jsonify({"ok": False, "error": "Grupo no encontrado"}), 404

        # Eliminar solo las actividades auto-sincronizadas anteriores
        conn.execute(
            "DELETE FROM coordinacion_actividades WHERE grupo_key=? AND sincronizado=1",
            (grupo_key,)
        )

        # Obtener clases relevantes del horario
        # LAB e INF: solo subgrupo 1 (subgrupo vacío o que termine en '1')
        # EXP: todos
        clases = conn.execute(
            """SELECT s.numero AS semana_num, cl.asignatura_id, cl.tipo, cl.subgrupo
               FROM clases cl
               JOIN semanas s ON cl.semana_id = s.id
               WHERE s.grupo_id = ?
                 AND cl.tipo IN ('LAB', 'INF', 'EXP')
                 AND cl.es_no_lectivo = 0
                 AND cl.asignatura_id IS NOT NULL""",
            (g["id"],)
        ).fetchall()

        ts = datetime.utcnow().isoformat()
        inserted = set()
        for cl in clases:
            tipo     = cl["tipo"]
            subgrupo = (cl["subgrupo"] or "").strip()

            # LAB e INF: solo subgrupo principal (vacío, '1', o que termine en '-1')
            if tipo in ("LAB", "INF"):
                if subgrupo and subgrupo != "1" and not subgrupo.endswith("-1"):
                    continue

            key = (grupo_key, cl["semana_num"], cl["asignatura_id"], tipo)
            if key in inserted:
                continue
            inserted.add(key)

            conn.execute(
                """INSERT OR IGNORE INTO coordinacion_actividades
                       (grupo_key, semana_num, asignatura_id, tipo_actividad,
                        notas, sincronizado, ts)
                   VALUES (?, ?, ?, ?, '', 1, ?)""",
                (grupo_key, cl["semana_num"], cl["asignatura_id"], tipo, ts)
            )

        conn.commit()

    return jsonify({"ok": True, "insertadas": len(inserted)})
```

> ⚠️ **Consecuencia en `servidor_horarios.py`**: Los endpoints
> `/api/clase/update`, `/api/clase/create`, `/api/clase/delete` y `/api/clase/move`
> deberían llamar a `_trigger_coord_sync(grupo_key)` (función interna) cuando el
> tipo de la clase afectada sea LAB, INF o EXP, para mantener la coordinación
> sincronizada en tiempo real sin requerir recarga manual.

---

## 4. Lógica de sincronización — Detalle

```
Horario (tabla clases)
        │
        │  tipo IN ('LAB','INF','EXP')
        │  LAB/INF: subgrupo vacío, '1' o '*-1'
        ▼
coordinacion_actividades  (sincronizado=1)
        │
        ├─ No editables manualmente (frontend bloquea)
        ├─ Se borran y reinsertan en cada sync
        └─ Se actualizan automáticamente al editar el horario

Actividades manuales  (sincronizado=0)
        │
        ├─ Creadas por el usuario desde la matriz
        ├─ Editables y borrables
        └─ NO se tocan en el sync
```

**Regla de subgrupos para LAB e INF:**

| Valor `subgrupo` en `clases` | ¿Se sincroniza? |
|------------------------------|-----------------|
| `''` (vacío, grupo único)    | ✅ Sí           |
| `'1'`                        | ✅ Sí           |
| `'LAB-1'`, `'INF-1'`         | ✅ Sí           |
| `'2'`, `'LAB-2'`, `'INF-2'` | ❌ No           |

---

## 5. Frontend — Estructura de componentes

### 5.1 Nueva vista en el despachador

En `static/horarios.js`, dentro de `render()`:

```javascript
function render() {
    if (currentView === 'semana')         renderWeek();
    else if (currentView === 'todas')     renderAllWeeks();
    else if (currentView === 'stats')     renderStats();
    else if (currentView === 'parciales') renderParciales();
    else if (currentView === 'finales')   renderFinales();    // ya existe
    else if (currentView === 'festivos')  renderFestivos();   // ya existe
    else if (currentView === 'coord')     renderCoordinacion(); // ← NUEVA
}
```

En `setView()`, añadir la carga diferida (igual que `loadFinales`):

```javascript
if (v === 'coord' && !_coordLoaded) {
    loadCoordinacion();
    _coordLoaded = true;
} else if (v === 'coord') {
    syncCoordinacion(); // re-sync silencioso cada vez que se abre la vista
}
```

### 5.2 Variables globales nuevas

```javascript
let COORD_DATA       = null;   // respuesta de /api/coordinacion
let _coordLoaded     = false;  // carga diferida (igual que finales)
const COORD_TIPOS = [
    { codigo: 'LAB', desc: 'Prácticas laboratorio',       color: '#4CAF50', sync: true  },
    { codigo: 'INF', desc: 'Prácticas informática',        color: '#2196F3', sync: true  },
    { codigo: 'SEM', desc: 'Seminarios / visitas',         color: '#9C27B0', sync: false },
    { codigo: 'EXP', desc: 'Examen parcial',               color: '#F44336', sync: true  },
    { codigo: 'EXF', desc: 'Examen final',                 color: '#E91E63', sync: false },
    { codigo: 'TE',  desc: 'Trabajo escrito / memoria',    color: '#FF9800', sync: false },
    { codigo: 'EO',  desc: 'Exposición oral',              color: '#795548', sync: false },
    { codigo: 'OA',  desc: 'Otra actividad evaluación',    color: '#607D8B', sync: false },
];
```

### 5.3 Función `loadCoordinacion()`

```javascript
async function loadCoordinacion() {
    const params = new URLSearchParams({
        curso: currentCurso,
        cuatrimestre: currentCuat,
        grupo: currentGroup
    });
    const r = await fetch(`/api/coordinacion?${params}`);
    COORD_DATA = await r.json();
    await syncCoordinacion();   // sync automático al cargar
    renderCoordinacion();
}

async function syncCoordinacion() {
    const grupoKey = `${currentCurso}_${currentCuat}_grupo_${currentGroup}`;
    await fetch('/api/coordinacion/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ grupo_key: grupoKey })
    });
    // Recargar datos tras sync
    const params = new URLSearchParams({
        curso: currentCurso, cuatrimestre: currentCuat, grupo: currentGroup
    });
    const r = await fetch(`/api/coordinacion?${params}`);
    COORD_DATA = await r.json();
}
```

### 5.4 Función `renderCoordinacion()`

```javascript
function renderCoordinacion() {
    const container = document.getElementById('main-content');
    if (!COORD_DATA || !COORD_DATA.ok) {
        container.innerHTML = '<p class="error">Error cargando datos de coordinación.</p>';
        return;
    }

    const { semanas, asignaturas, actividades } = COORD_DATA;

    // Indexar actividades: Map[(semana_num, asignatura_id)] → [tipos...]
    const actMap = new Map();
    for (const act of actividades) {
        const k = `${act.semana_num}_${act.asignatura_id}`;
        if (!actMap.has(k)) actMap.set(k, []);
        actMap.get(k).push(act);
    }

    // Calcular carga por semana (para resaltar sobrecargas)
    const cargaSemana = {};
    for (const act of actividades) {
        cargaSemana[act.semana_num] = (cargaSemana[act.semana_num] || 0) + 1;
    }

    let html = `
    <div class="coord-toolbar">
        <button onclick="syncCoordinacion().then(renderCoordinacion)" class="btn-secondary">
            ↻ Sincronizar horario
        </button>
        <button onclick="exportCoordPDF()" class="btn-secondary">
            ⬇ Exportar PDF
        </button>
        <div class="coord-leyenda">
            ${COORD_TIPOS.map(t => `
                <span class="coord-badge" style="background:${t.color}">
                    ${t.sync ? '🔒' : ''}${t.codigo}
                </span> ${t.desc}
            `).join(' &nbsp; ')}
        </div>
    </div>

    <div class="coord-table-wrapper">
    <table class="coord-table">
        <thead>
            <tr>
                <th class="coord-semana-header">Semana</th>
                ${asignaturas.map(a => `
                    <th class="coord-asig-header ${getSubjectColor(a.codigo)}"
                        title="${a.nombre}">
                        ${a.nombre.length > 20 ? a.nombre.substring(0,18) + '…' : a.nombre}
                        <br><small>${a.codigo}</small>
                    </th>
                `).join('')}
            </tr>
        </thead>
        <tbody>
            ${semanas.map(sem => {
                const carga = cargaSemana[sem.numero] || 0;
                const sobrecarga = carga >= 4 ? 'coord-row-overload' :
                                   carga >= 2 ? 'coord-row-busy' : '';
                return `
                <tr class="${sobrecarga}">
                    <td class="coord-semana-cell">
                        <span class="coord-sem-num">S${sem.numero}</span>
                        <span class="coord-sem-desc">${sem.descripcion}</span>
                        ${carga >= 4 ? '<span class="coord-alerta" title="Semana sobrecargada">⚠️</span>' : ''}
                    </td>
                    ${asignaturas.map(asig => {
                        const k = `${sem.numero}_${asig.id}`;
                        const acts = actMap.get(k) || [];
                        return `
                        <td class="coord-cell"
                            onclick="openCoordModal(${sem.numero}, ${asig.id}, '${asig.codigo}', '${asig.nombre.replace(/'/g,'\\\'')}')"
                            title="Clic para añadir actividad">
                            ${acts.map(a => {
                                const tipo = COORD_TIPOS.find(t => t.codigo === a.tipo_actividad);
                                const col  = tipo ? tipo.color : '#999';
                                return `<span class="coord-badge"
                                    style="background:${col}"
                                    title="${tipo ? tipo.desc : a.tipo_actividad}${a.notas ? ': ' + a.notas : ''}"
                                    >${a.sincronizado ? '🔒' : ''}${a.tipo_actividad}</span>`;
                            }).join('')}
                        </td>`;
                    }).join('')}
                </tr>`;
            }).join('')}
        </tbody>
    </table>
    </div>`;

    container.innerHTML = html;
}
```

### 5.5 Modal de edición de celda

```javascript
function openCoordModal(semanaNum, asignaturaId, codigo, nombre) {
    const grupoKey = `${currentCurso}_${currentCuat}_grupo_${currentGroup}`;
    const k        = `${semanaNum}_${asignaturaId}`;
    const existing = (COORD_DATA.actividades || []).filter(
        a => a.semana_num === semanaNum && a.asignatura_id === asignaturaId
    );

    const tiposHTML = COORD_TIPOS.map(t => {
        const act  = existing.find(a => a.tipo_actividad === t.codigo);
        const isOn = !!act;
        const isSync = act && act.sincronizado;
        return `
        <label class="coord-tipo-row ${isSync ? 'coord-tipo-sync' : ''}"
               title="${isSync ? 'Sincronizado automáticamente desde el horario' : ''}">
            <input type="checkbox"
                   data-tipo="${t.codigo}"
                   ${isOn ? 'checked' : ''}
                   ${isSync ? 'disabled' : ''}
                   onchange="toggleCoordActividad('${grupoKey}', ${semanaNum}, ${asignaturaId}, '${t.codigo}', this.checked)">
            <span class="coord-badge" style="background:${t.color}">
                ${isSync ? '🔒' : ''}${t.codigo}
            </span>
            ${t.desc}
            ${isSync ? '<small class="coord-sync-label">(automático)</small>' : ''}
        </label>`;
    }).join('');

    const notas = (existing.find(a => !a.sincronizado)?.notas) || '';

    showModal(`
        <h3>Actividades · <em>${nombre}</em></h3>
        <p class="coord-modal-sem">Semana ${semanaNum}</p>
        <div class="coord-tipo-list">${tiposHTML}</div>
        <label class="coord-notas-label">Notas:
            <textarea id="coord-notas" rows="2">${notas}</textarea>
        </label>
        <button onclick="closeModal()" class="btn-primary">Cerrar</button>
    `);
}

async function toggleCoordActividad(grupoKey, semanaNum, asignaturaId, tipo, checked) {
    const notas = document.getElementById('coord-notas')?.value || '';
    await fetch('/api/coordinacion/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            grupo_key:      grupoKey,
            semana_num:     semanaNum,
            asignatura_id:  asignaturaId,
            tipo_actividad: tipo,
            notas:          notas,
            action:         checked ? 'add' : 'remove'
        })
    });
    // Recargar datos y re-renderizar sin cerrar el modal
    const params = new URLSearchParams({
        curso: currentCurso, cuatrimestre: currentCuat, grupo: currentGroup
    });
    const r = await fetch(`/api/coordinacion?${params}`);
    COORD_DATA = await r.json();
    renderCoordinacion();
}
```

---

## 6. CSS — Estilos para la vista

Añadir a `static/horarios.css`:

```css
/* ── Calendario de Coordinación Horizontal ─────────────────────────── */

.coord-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 0 14px;
    flex-wrap: wrap;
}

.coord-leyenda {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    font-size: 0.78rem;
    color: var(--text-secondary, #555);
    align-items: center;
}

.coord-table-wrapper {
    overflow-x: auto;
    max-height: calc(100vh - 180px);
    overflow-y: auto;
}

.coord-table {
    border-collapse: collapse;
    min-width: 100%;
    font-size: 0.82rem;
}

.coord-table th, .coord-table td {
    border: 1px solid var(--border-color, #ddd);
    padding: 4px 6px;
    vertical-align: top;
}

/* Cabecera de semanas: sticky en scroll vertical */
.coord-table thead th {
    position: sticky;
    top: 0;
    background: var(--bg-secondary, #f5f5f5);
    z-index: 2;
    text-align: center;
    font-size: 0.75rem;
    max-width: 90px;
    white-space: normal;
    line-height: 1.2;
}

/* Primera columna: sticky en scroll horizontal */
.coord-semana-cell {
    position: sticky;
    left: 0;
    background: var(--bg-secondary, #f5f5f5);
    z-index: 1;
    white-space: nowrap;
    font-size: 0.78rem;
    min-width: 140px;
}

.coord-sem-num {
    font-weight: bold;
    margin-right: 6px;
    color: var(--primary-color, #1976D2);
}

.coord-sem-desc {
    color: #666;
    font-size: 0.72rem;
}

.coord-cell {
    cursor: pointer;
    min-width: 70px;
    min-height: 32px;
    transition: background 0.15s;
}

.coord-cell:hover {
    background: rgba(25, 118, 210, 0.07);
}

/* Badges de actividad */
.coord-badge {
    display: inline-block;
    color: white;
    font-size: 0.68rem;
    font-weight: bold;
    padding: 2px 5px;
    border-radius: 3px;
    margin: 1px;
    white-space: nowrap;
}

/* Filas con sobrecarga */
.coord-row-busy   { background: rgba(255, 152, 0, 0.07); }
.coord-row-overload { background: rgba(244, 67, 54, 0.10); }

.coord-alerta { font-size: 0.9rem; }

/* Modal de edición */
.coord-modal-sem   { color: var(--primary-color, #1976D2); font-weight: bold; }
.coord-tipo-list   { display: flex; flex-direction: column; gap: 6px; margin: 12px 0; }
.coord-tipo-row    { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.coord-tipo-sync   { opacity: 0.75; }
.coord-sync-label  { color: #888; font-size: 0.72rem; }
.coord-notas-label { display: flex; flex-direction: column; gap: 4px;
                     font-size: 0.82rem; margin-top: 8px; }
.coord-notas-label textarea { resize: vertical; padding: 4px; font-size: 0.82rem; }
```

---

## 7. Manejo de estados — Diagrama

```
        CELDA DE LA MATRIZ
               │
     ┌─────────┴──────────┐
     │  sincronizado=1    │   sincronizado=0
     │  (LAB/INF/EXP)     │   (manual)
     │                    │
     │  🔒 Solo lectura   │  ✏️  Editable
     │  Fondo más oscuro  │  Checkbox activo
     │  Checkbox disabled │  Puede borrarse
     │  Tooltip: "Auto"   │
     └────────────────────┘

    Al hacer sync (al abrir vista / botón ↻):
        1. DELETE WHERE sincronizado=1 AND grupo_key=?
        2. INSERT desde clases (LAB/INF: subgrupo 1; EXP: todos)
        3. Re-render
    Las actividades manuales (sincronizado=0) NO se tocan
```

---

## 8. Validaciones y alertas

### 8.1 Semana sobrecargada (frontend)

Umbral configurable en JS (actualmente `>= 4` actividades en una semana):

```javascript
const COORD_WARN_THRESHOLD     = 2;   // naranja: muchas actividades
const COORD_OVERLOAD_THRESHOLD = 4;   // rojo: sobrecarga severa
```

### 8.2 Misma semana, mismo tipo en varias asignaturas

```javascript
function getCoordWarnings(semanaNum) {
    const acts = COORD_DATA.actividades.filter(a => a.semana_num === semanaNum);
    const byTipo = {};
    for (const a of acts) {
        byTipo[a.tipo_actividad] = (byTipo[a.tipo_actividad] || 0) + 1;
    }
    const warnings = [];
    if ((byTipo['EXP'] || 0) + (byTipo['EXF'] || 0) > 2)
        warnings.push(`${byTipo['EXP']||0} exámenes en una sola semana`);
    return warnings;
}
```

### 8.3 Validación en servidor (POST /api/coordinacion/set)

```python
VALID_TIPOS = {"LAB", "INF", "SEM", "EXP", "EXF", "TE", "EO", "OA"}

if tipo not in VALID_TIPOS:
    return jsonify({"ok": False, "error": f"Tipo '{tipo}' no válido"}), 400
```

---

## 9. Integración con cambios de horario (sincronización reactiva)

Para mantener el calendario actualizado sin que el usuario tenga que pulsar "↻":

En `servidor_horarios.py`, crear una función auxiliar:

```python
def _sync_coord_for_key(conn, grupo_key: str):
    """Resincroniza actividades auto en el calendario de coordinación.
    Llamar después de cualquier INSERT/UPDATE/DELETE en clases con tipo LAB/INF/EXP.
    """
    parts = grupo_key.split("_")
    if len(parts) < 4:
        return
    curso, cuatrimestre, grupo_num = parts[0], parts[1], parts[3]
    g = conn.execute(
        "SELECT id FROM grupos WHERE curso=? AND cuatrimestre=? AND grupo=?",
        (curso, cuatrimestre, grupo_num)
    ).fetchone()
    if not g:
        return

    conn.execute(
        "DELETE FROM coordinacion_actividades WHERE grupo_key=? AND sincronizado=1",
        (grupo_key,)
    )
    clases = conn.execute(
        """SELECT s.numero AS semana_num, cl.asignatura_id, cl.tipo, cl.subgrupo
           FROM clases cl JOIN semanas s ON cl.semana_id = s.id
           WHERE s.grupo_id=? AND cl.tipo IN ('LAB','INF','EXP')
             AND cl.es_no_lectivo=0 AND cl.asignatura_id IS NOT NULL""",
        (g["id"],)
    ).fetchall()

    ts = datetime.utcnow().isoformat()
    seen = set()
    for cl in clases:
        tipo, subgrupo = cl["tipo"], (cl["subgrupo"] or "").strip()
        if tipo in ("LAB", "INF"):
            if subgrupo and subgrupo != "1" and not subgrupo.endswith("-1"):
                continue
        key = (grupo_key, cl["semana_num"], cl["asignatura_id"], tipo)
        if key in seen:
            continue
        seen.add(key)
        conn.execute(
            """INSERT OR IGNORE INTO coordinacion_actividades
               (grupo_key, semana_num, asignatura_id, tipo_actividad, notas, sincronizado, ts)
               VALUES (?,?,?,?,'',1,?)""",
            (*key, ts)
        )
```

Después invocar `_sync_coord_for_key(conn, grupo_key)` en:
- `api_update_clase` → si el `tipo` de la clase es LAB/INF/EXP
- `api_create_clase` → si el `tipo` es LAB/INF/EXP
- `api_delete_clase` → si la clase eliminada era LAB/INF/EXP
- `api_move_clase`   → si el tipo aplica (para actualizar la semana correcta)

---

## 10. Extras opcionales

### 10.1 Exportación a Excel

```javascript
async function exportCoordExcel() {
    // Construir CSV simple con los datos de COORD_DATA
    const { semanas, asignaturas, actividades } = COORD_DATA;
    const actMap = new Map();
    for (const a of actividades) {
        const k = `${a.semana_num}_${a.asignatura_id}`;
        if (!actMap.has(k)) actMap.set(k, []);
        actMap.get(k).push(a.tipo_actividad + (a.sincronizado ? '*' : ''));
    }
    let csv = ['Semana', ...asignaturas.map(a => a.nombre)].join(';') + '\n';
    for (const sem of semanas) {
        const row = [sem.descripcion];
        for (const asig of asignaturas) {
            const acts = actMap.get(`${sem.numero}_${asig.id}`) || [];
            row.push(acts.join(' | '));
        }
        csv += row.join(';') + '\n';
    }
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `coordinacion_${COORD_DATA.grupo_key}.csv`;
    link.click();
}
```

### 10.2 Vista de resumen por columna (asignatura)

Añadir una fila de totales al pie de la tabla:

```javascript
// En renderCoordinacion(), antes de cerrar </table>:
const totalPorAsig = {};
for (const act of actividades) {
    totalPorAsig[act.asignatura_id] = (totalPorAsig[act.asignatura_id] || 0) + 1;
}
const maxActs = Math.max(...Object.values(totalPorAsig), 0);
// Renderizar fila de totales con barra proporcional
```

---

## 11. Plan de implementación

| Paso | Acción | Archivos afectados | Tipo cambio |
|------|--------|-------------------|-------------|
| 1 | Añadir `_m19` a `migrate_db.py` | `tools/migrate_db.py` | — |
| 2 | Añadir `CREATE TABLE` a `setup_grado.py` y `nuevo_dtie.py` | `tools/setup_grado.py`, `tools/nuevo_dtie.py` | — |
| 3 | Añadir endpoints `/api/coordinacion*` | `servidor_horarios.py` | MINOR |
| 4 | Añadir `_sync_coord_for_key` y llamadas reactivas | `servidor_horarios.py` | — |
| 5 | Añadir variables y funciones JS | `static/horarios.js` | — |
| 6 | Añadir estilos CSS | `static/horarios.css` | — |
| 7 | Añadir botón "Coordinación" a la barra de vistas | `templates/index.html` | — |
| 8 | Bump de versión 1.37.10 → **1.38.0** | `VERSION`, `servidor_horarios.py` | MINOR |

> **Nota sobre el bump**: Es MINOR porque incorpora una nueva vista, nuevos endpoints
> y una nueva migración de BD, sin romper compatibilidad.

---

## 12. Posibles problemas y soluciones

| Problema | Solución |
|----------|----------|
| El `subgrupo` en `clases` tiene formatos inconsistentes | Normalizar con `strip()` y comprobar `== '1'`, `endswith('-1')` o vacío |
| Muchas asignaturas → tabla muy ancha | Cabeceras rotadas 45° con CSS `transform: rotate(-45deg)` + scroll horizontal |
| La sync reactiva ralentiza las ediciones de horario | Hacer la llamada a `_sync_coord_for_key` de forma asíncrona / en hilo aparte si es necesario (SQLite WAL lo permite con lectores concurrentes) |
| Actividades manuales con el mismo tipo que una sincronizada | El índice UNIQUE lo previene; el servidor devuelve error si se intenta insertar una duplicada |
| Re-render completo en cada checkbox → parpadeo | Actualizar solo el DOM de la celda afectada en `toggleCoordActividad` en lugar de llamar a `renderCoordinacion()` completo |

---

*Documento generado automáticamente por el asistente Janux. Revisar antes de implementar.*
