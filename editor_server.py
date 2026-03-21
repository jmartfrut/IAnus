#!/usr/bin/env python3
"""
editor_server.py — Servidor local para el Editor Gráfico de Configuración

Arranca un servidor en http://localhost:8090 que sirve config_editor.html
y permite guardar config.json y generar la base de datos desde el navegador.

Uso (carpeta raíz):
  python3 editor_server.py
  → Abre automáticamente http://localhost:8090 en el navegador
  → Lee/guarda config.json en la carpeta raíz

Uso (estructura por grados):
  python3 editor_server.py grados/GIDI
  → Lee/guarda config.json en grados/GIDI/config.json
  → Genera la BD en grados/GIDI/
"""

import csv
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).parent
PORT       = 8090
HTML_FILE  = SCRIPT_DIR / 'config_editor.html'
SETUP_SCRIPT = SCRIPT_DIR / 'setup_grado.py'

# Detectar carpeta de grado desde argumento de línea de comandos
_args = [a for a in sys.argv[1:] if not a.startswith('--')]
if _args:
    _grado_dir = Path(_args[0])
    if not _grado_dir.is_absolute():
        _grado_dir = SCRIPT_DIR / _grado_dir
    if _grado_dir.is_dir():
        GRADO_DIR   = _grado_dir
        CONFIG_FILE = _grado_dir / 'config.json'
    else:
        print(f"AVISO: '{_args[0]}' no es una carpeta válida. Usando carpeta raíz.")
        GRADO_DIR   = None
        CONFIG_FILE = SCRIPT_DIR / 'config.json'
else:
    GRADO_DIR   = None
    CONFIG_FILE = SCRIPT_DIR / 'config.json'


class EditorHandler(http.server.BaseHTTPRequestHandler):

    # ── GET ───────────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/index.html', '/config_editor.html'):
            self._serve_file(HTML_FILE, 'text/html; charset=utf-8')
        elif path == '/api/ping':
            self._json({'ok': True, 'mode': 'editor_server'})
        elif path == '/api/config':
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, encoding='utf-8') as f:
                    self._json(json.load(f))
            else:
                self._json({})
        else:
            self._respond(404, b'Not found')

    # ── POST ──────────────────────────────────────────────────
    def do_POST(self):
        path   = urlparse(self.path).path
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length) if length else b'{}'
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        if path == '/api/save-config':
            self._save_config(data)
        elif path == '/api/setup':
            self._run_setup(data)
        else:
            self._respond(404, b'Not found')

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    # ── Handlers ─────────────────────────────────────────────
    def _save_config(self, data):
        cfg = data.get('config', data)  # acepta {config: {...}} o directamente el objeto
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f'  [editor] config.json guardado')
        self._json({'ok': True, 'message': 'config.json guardado'})

    def _run_setup(self, data):
        config      = data.get('config', {})
        asignaturas = data.get('asignaturas', [])

        if not asignaturas:
            self._json({'ok': False, 'error': 'La tabla de asignaturas está vacía.'})
            return

        # 1. Guardar config.json
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f'  [editor] config.json guardado')

        # 2. Escribir CSV temporal
        tf = tempfile.NamedTemporaryFile(
            mode='w', suffix='.csv', delete=False,
            encoding='utf-8', newline=''
        )
        try:
            writer = csv.DictWriter(
                tf,
                fieldnames=['codigo', 'nombre', 'curso', 'cuatrimestre', 'creditos', 'af1', 'af2', 'af4', 'af5', 'af6'],
                extrasaction='ignore'
            )
            writer.writeheader()
            writer.writerows(asignaturas)
            tf.close()
            csv_path = tf.name

            print(f'  [editor] Ejecutando setup_grado.py con {len(asignaturas)} asignaturas…')

            # 3. Ejecutar setup_grado.py
            # Si hay carpeta de grado, pasarla como primer argumento
            if GRADO_DIR:
                cmd = [sys.executable, str(SETUP_SCRIPT), str(GRADO_DIR), csv_path, '--force']
            else:
                cmd = [sys.executable, str(SETUP_SCRIPT), csv_path, '--force']
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(SCRIPT_DIR),
                timeout=120
            )
            stdout = result.stdout or ''
            stderr = result.stderr or ''
            ok     = result.returncode == 0

            if ok:
                print(f'  [editor] ✅ Base de datos generada correctamente')
            else:
                print(f'  [editor] ❌ Error al generar la BD:\n{stderr}')

            self._json({'ok': ok, 'output': stdout, 'error': stderr})

        except subprocess.TimeoutExpired:
            self._json({'ok': False, 'error': 'Tiempo de espera agotado (>120s)'})
        except Exception as e:
            self._json({'ok': False, 'error': str(e)})
        finally:
            try: os.unlink(csv_path)
            except: pass

    # ── Helpers ───────────────────────────────────────────────
    def _serve_file(self, path, content_type):
        try:
            with open(path, 'rb') as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self._respond(404, b'File not found')

    def _json(self, data):
        content = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(content))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def _respond(self, code, body=b''):
        self.send_response(code)
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, fmt, *args):
        pass  # Silenciar log HTTP por defecto


# ── MAIN ─────────────────────────────────────────────────────
def main():
    url = f'http://localhost:{PORT}'

    if not HTML_FILE.exists():
        print(f'ERROR: No se encuentra {HTML_FILE.name}')
        print(f'  Asegúrate de ejecutar este script desde la misma carpeta.')
        sys.exit(1)
    if not SETUP_SCRIPT.exists():
        print(f'AVISO: No se encuentra setup_grado.py — la generación de BD no estará disponible.')

    server = http.server.HTTPServer(('localhost', PORT), EditorHandler)

    print('=' * 52)
    print('  Editor de Configuración — Gestor de Horarios')
    print('=' * 52)
    print(f'\n  🌐 URL: {url}')
    if GRADO_DIR:
        print(f'  📁 Grado: {GRADO_DIR.name}  ({GRADO_DIR})')
    else:
        print(f'  📁 Carpeta: {SCRIPT_DIR}')
    print(f'  📄 Config: {CONFIG_FILE}')
    print(f'\n  Pulsa Ctrl+C para detener el servidor.\n')

    # Abrir navegador tras medio segundo
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n  Servidor detenido.')


if __name__ == '__main__':
    main()
