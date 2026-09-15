#!/usr/bin/env bash
# Ejecutar DENTRO de la instancia Vast.ai (no en Windows).
# Baja MiniMax-H3 Ref2VA directo del Hub a velocidad de datacenter (~10-40 min).
#
#   scp scripts/vast-fetch-h3.sh root@<IP>:-P <PUERTO> /root/
#   ssh root@<IP> -p <PUERTO> 'bash /root/vast-fetch-h3.sh'
#
# OJO licencia: la MiniMax H3 Community License excluye EE.UU., UE, Reino Unido
# y Corea del Sur de los derechos de despliegue local. Elige la region del
# datacenter en Vast teniendo eso en cuenta.
set -euo pipefail

DEST="${DEST:-/workspace/models/MiniMax-H3}"
VARIANT="${VARIANT:-Ref2VA}"   # Ref2VA (9 imgs de referencia) | FL2VA (primer/ultimo frame)

pip install -q -U "huggingface_hub[cli,hf_transfer]"
export HF_HUB_ENABLE_HF_TRANSFER=1   # descarga acelerada en Rust

# Con HF_TOKEN los limites de rate son mas altos: export HF_TOKEN=hf_xxx
echo ">> bajando $VARIANT a $DEST"
df -h "$(dirname "$DEST")"

hf download MiniMaxAI/MiniMax-H3 \
  --include "model_index.json" \
  --include "${VARIANT}/*" \
  --local-dir "$DEST" \
  --max-workers 16

echo ">> listo"
du -sh "$DEST"
