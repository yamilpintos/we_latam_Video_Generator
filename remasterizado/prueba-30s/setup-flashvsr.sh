#!/bin/bash
# Instala FlashVSR v1.1 (Full) en una instancia de Vast con imagen
# vastai/base-image cuda-12.4.1 devel py311. Pensado para A100 (sm_80).
# Todo desatendido; el log va a /root/setup.log. Termina escribiendo SETUP_OK o SETUP_FALLO.
set -uxo pipefail
T0=$(date +%s)
PY=/venv/main/bin/python; [ -x "$PY" ] || PY=$(command -v python3)
echo "python: $PY"; $PY -V; nvcc --version | tail -1; nvidia-smi --query-gpu=name,memory.total --format=csv; nproc; free -g | head -2
export HF_HUB_ENABLE_HF_TRANSFER=1 PIP_DISABLE_PIP_VERSION_CHECK=1
mkdir -p /workspace && cd /workspace

# 1) código
git clone --depth 1 https://github.com/OpenImagingLab/FlashVSR || exit 1
git clone --depth 1 https://github.com/mit-han-lab/Block-Sparse-Attention || exit 1

# 2) pesos (7 GB) en segundo plano mientras se instala lo demás
$PY -m pip install -q "huggingface_hub[hf_transfer]" 
( $PY -m huggingface_hub.commands.huggingface_cli download JunhaoZhuang/FlashVSR-v1.1 \
    --local-dir /workspace/FlashVSR/examples/WanVSR/FlashVSR-v1.1 > /root/pesos.log 2>&1 \
  || hf download JunhaoZhuang/FlashVSR-v1.1 --local-dir /workspace/FlashVSR/examples/WanVSR/FlashVSR-v1.1 >> /root/pesos.log 2>&1 ; echo "PESOS_FIN rc=$?" >> /root/pesos.log ) &
PID_PESOS=$!

# 3) torch pineado por el repo (2.6.0 cu124 = mismo CUDA que el nvcc de la imagen)
$PY -m pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124 || exit 1
cd /workspace/FlashVSR
grep -v -i -E "^(torch|torchvision|torchaudio)" requirements.txt > /root/req-sin-torch.txt
$PY -m pip install -r /root/req-sin-torch.txt || exit 1
$PY -m pip install -e . --no-deps || exit 1
$PY -m pip install packaging ninja

# 4) Block-Sparse-Attention sólo para sm_80 (A100): compilar todo tarda mucho más
cd /workspace/Block-Sparse-Attention
export MAX_JOBS=$(nproc) TORCH_CUDA_ARCH_LIST="8.0" FLASH_ATTN_CUDA_ARCHS="80"
T1=$(date +%s)
$PY setup.py install > /root/bsa-build.log 2>&1; RC=$?
echo "BSA build rc=$RC en $(( $(date +%s) - T1 )) s"; tail -5 /root/bsa-build.log
$PY -c "import block_sparse_attn, torch; print('block_sparse_attn OK', torch.__version__, torch.version.cuda)" || { echo "SETUP_FALLO bsa"; exit 1; }

# 5) esperar pesos
wait $PID_PESOS; tail -3 /root/pesos.log
ls -la /workspace/FlashVSR/examples/WanVSR/FlashVSR-v1.1/
$PY -c "
import torch, diffsynth
from diffsynth import ModelManager, FlashVSRFullPipeline
print('diffsynth OK; cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))" || { echo "SETUP_FALLO diffsynth"; exit 1; }
echo "SETUP_OK en $(( $(date +%s) - T0 )) s"
