#!/bin/bash
# FlashVSR v1.1 Full en Vast: imagen vastai/base-image cuda-12.4.1 devel py311, A100 80 GB (sm_80).
# Es la receta que funciono el 18/9/2026 (remasterizado/REMASTER-4K-HANDOFF.md, seccion 6), con
# las seis trampas de la primera noche ya resueltas. Idempotente: si /root/SETUP_OK existe, sale.
# Log: /root/setup.log. Termina con SETUP_OK o SETUP_FALLO <motivo>.
set -uxo pipefail
T0=$(date +%s)
PY=/venv/main/bin/python
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
if [ -f /root/SETUP_OK ]; then echo "SETUP_OK ya instalado"; exit 0; fi
$PY -V; nvcc --version | tail -1; nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; nproc
mkdir -p /workspace && cd /workspace
[ -d FlashVSR ] || git clone --depth 1 https://github.com/OpenImagingLab/FlashVSR || { echo SETUP_FALLO clone; exit 1; }
[ -d Block-Sparse-Attention ] || git clone --depth 1 https://github.com/mit-han-lab/Block-Sparse-Attention || { echo SETUP_FALLO clone-bsa; exit 1; }
# pesos en segundo plano (el binario hf vive en /venv/main/bin, fuera del PATH)
$PY -m pip install -q "huggingface_hub[hf_transfer]"
( HF_HUB_ENABLE_HF_TRANSFER=1 /venv/main/bin/hf download JunhaoZhuang/FlashVSR-v1.1 --local-dir /workspace/FlashVSR/examples/WanVSR/FlashVSR-v1.1 > /root/pesos.log 2>&1; echo "PESOS_FIN rc=$?" >> /root/pesos.log ) &
PID_PESOS=$!
# torch exactamente como lo pinea el repo (su setup.py lee requirements.txt)
$PY -m pip install -q torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124 || { echo SETUP_FALLO torch; exit 1; }
cd /workspace/FlashVSR
grep -v -i -E "^(torch|torchvision|torchaudio)" requirements.txt > /root/req-sin-torch.txt
$PY -m pip install -q -r /root/req-sin-torch.txt || { echo SETUP_FALLO requirements; exit 1; }
$PY -m pip install -q modelscope "setuptools<80" packaging ninja imageio imageio-ffmpeg
$PY -m pip install -q -e . --no-deps --no-build-isolation || { echo SETUP_FALLO pip-e; exit 1; }
# atencion dispersa solo para sm_80; sin la variable mete compute_120 y nvcc 12.4 muere
cd /workspace/Block-Sparse-Attention
export BLOCK_SPARSE_ATTN_CUDA_ARCHS=${BSA_ARCHS:-80} MAX_JOBS=64 NVCC_THREADS=4
T1=$(date +%s)
$PY setup.py install > /root/bsa-build.log 2>&1; RC=$?
echo "BSA build rc=$RC en $(( $(date +%s) - T1 )) s"
cd /workspace/FlashVSR/examples/WanVSR
$PY -c 'import torch, block_sparse_attn; print("bsa OK", torch.__version__)' || { echo SETUP_FALLO bsa; tail -20 /root/bsa-build.log; exit 1; }
$PY -c 'import torch; from diffsynth import ModelManager, FlashVSRFullPipeline; print("diffsynth OK", torch.cuda.get_device_name(0))' || { echo SETUP_FALLO diffsynth; exit 1; }
wait $PID_PESOS; tail -1 /root/pesos.log
[ -f FlashVSR-v1.1/diffusion_pytorch_model_streaming_dmd.safetensors ] || { echo SETUP_FALLO pesos; exit 1; }
du -sh FlashVSR-v1.1
touch /root/SETUP_OK
echo "SETUP_OK en $(( $(date +%s) - T0 )) s"
