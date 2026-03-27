# ── Gestor de Horarios UPCT ─────────────────────────────────────────────────
# Imagen de producción: python 3.12 slim
# Puerto por defecto: 8765  (configurable via PORT env var)
# Base de datos:       /app/data/horarios.db (configurable via DB_PATH env var)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim

# Metadatos
LABEL maintainer="UPCT" \
      description="Gestor de Horarios UPCT — servidor web de horarios"

# Evitar prompts interactivos en apt
ENV DEBIAN_FRONTEND=noninteractive

# Dependencias del sistema (librerías que necesita pdfplumber/pdfminer)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias Python antes de copiar el código
# (aprovechar caché de capas cuando solo cambia el código fuente)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el proyecto completo
COPY . .

# Directorio donde se montará el volumen de datos (bases de datos)
# El servidor buscará la BD en DB_PATH; si no se define, usará el fallback
RUN mkdir -p /app/data

# Puerto de escucha del servidor WebSocket/HTTP
EXPOSE 8765

# Variables de entorno con valores por defecto para Docker
ENV PORT=8765 \
    DB_PATH=/app/data/horarios.db \
    CURSO_LABEL=2025-2026

CMD ["python", "servidor_horarios.py"]
