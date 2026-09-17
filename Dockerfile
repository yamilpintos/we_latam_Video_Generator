# La Fábrica en un contenedor (Render, o cualquier host con Docker).
#
# Necesita, además de Python: ffmpeg (corte y máster) y el cliente SSH (hablar
# con la máquina de Vast). Los modelos de H3 NO van acá: viven en la GPU
# alquilada. Los videos generados se bajan a /data/mis-videos: montá un disco
# persistente ahí o se pierden en cada deploy.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg openssh-client unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1 \
    FABRICA_HOST=0.0.0.0 PORT=8787
EXPOSE 8787
CMD ["python", "-X", "utf8", "-u", "-m", "h3pipeline.app"]
