# ReMusical — imagen para Vast.ai / RunPod / cualquier Docker con GPU.
# Un solo Python con todo (el separador incluido) y los modelos horneados: la instancia
# arranca y procesa, sin bajar nada.
#   docker build -t ghcr.io/yamilpintos/remusical:latest apps/remusical
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf REMUSICAL_TRABAJO=/tmp/remusical FFMPEG=ffmpeg
# ★ build-essential + python3.11-dev: `diffq` (dependencia del separador) no trae rueda
#   precompilada y se compila desde C. Sin compilador, el build falla con
#   "No such file or directory: 'x86_64-linux-gnu-gcc'".
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3.11-dev python3-pip \
        build-essential ffmpeg libsndfile1 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3.11 /usr/local/bin/python

WORKDIR /src
COPY requirements-gpu.txt .
# se compila lo que haga falta y después se sacan las herramientas (~250 MB menos)
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements-gpu.txt \
    && apt-get purge -y build-essential python3.11-dev && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# modelos horneados en la imagen (AudioSet AST + BS-Roformer)
RUN python -c "from transformers import AutoFeatureExtractor, ASTForAudioClassification; \
  AutoFeatureExtractor.from_pretrained('MIT/ast-finetuned-audioset-10-10-0.4593'); \
  ASTForAudioClassification.from_pretrained('MIT/ast-finetuned-audioset-10-10-0.4593')" \
 && python -c "from audio_separator.separator import Separator; \
  Separator(model_file_dir='/tmp/audio-separator-models').load_model(model_filename='model_bs_roformer_ep_317_sdr_12.9755.ckpt')"

COPY remusical ./remusical
ENV PY311=/usr/bin/python3.11
# por defecto corre una tanda desde el manifiesto que le pasen por entorno
CMD ["python", "-m", "remusical.nube.tanda"]
