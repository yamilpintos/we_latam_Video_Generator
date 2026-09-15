#!/usr/bin/env bash
# Descarga SOLO el transformer de FL2VA (~66.3 GB).
# El text_encoder (66.7 GB) y los VAE son byte-identicos a los de Ref2VA
# (verificado por sha256), asi que se enlazan con hardlinks: 0 bytes extra.
set -u

PROJ="C:/Users/Yamil/Desktop/youtube proyect"
export SSL_CERT_FILE="$PROJ/certs/ca-bundle-avast.pem"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"

HF="$PROJ/.venv-depthflow/Scripts/hf"
DEST="$PROJ/models/MiniMax-H3"
LOG="$PROJ/models/fl2va-download.log"

echo "=== inicio: $(date) ===" | tee -a "$LOG"

for i in $(seq 1 200); do
  echo "--- intento $i : $(date) ---" | tee -a "$LOG"

  "$HF" download MiniMaxAI/MiniMax-H3 \
    --include "FL2VA/model_index.json" \
    --include "FL2VA/transformer/*" \
    --local-dir "$DEST" >>"$LOG" 2>&1

  if [ $? -eq 0 ]; then
    echo "=== TRANSFORMER COMPLETO: $(date) ===" | tee -a "$LOG"
    # Enlaza los componentes compartidos desde Ref2VA (hardlinks, sin copiar).
    python "$PROJ/scripts/link-h3-shared.py" >>"$LOG" 2>&1
    echo "=== FL2VA LISTO: $(date) ===" | tee -a "$LOG"
    exit 0
  fi

  FREE_MB=$(df -m "$PROJ" | awk 'NR==2 {print $4}')
  echo "libre: ${FREE_MB} MB" | tee -a "$LOG"
  if [ "$FREE_MB" -lt 3072 ]; then
    echo "=== ABORTADO: disco casi lleno (${FREE_MB} MB) ===" | tee -a "$LOG"
    exit 1
  fi

  echo "fallo, reintento en 60s..." | tee -a "$LOG"
  sleep 60
done

echo "=== agotados los reintentos: $(date) ===" | tee -a "$LOG"
exit 1
