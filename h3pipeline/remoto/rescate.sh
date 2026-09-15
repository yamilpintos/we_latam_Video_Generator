#!/usr/bin/env bash
# ============================================================================
# Rescate de los planos que el runner dio por caídos tras sus tres pasadas.
#
#   bash /workspace/refs/rescate.sh          (lo deja esperando lanzar.sh)
#
# Espera a que los runners terminen. Si alguno anotó "fallaron tras 3 pasadas",
# casi siempre es VRAM fragmentada en un plano de 7,3 s (31/8: S30 cayó SEIS
# veces con `/free` entre medio, y salió a la primera con un ComfyUI recién
# arrancado). `/free` no alcanza: hay que matar el proceso de esa placa,
# levantar uno fresco y volver a correr el runner, que sólo rehace lo que falta.
#
# Matar y arrancar van en pasos separados y sin ningún literal del comando de
# arranque en el patrón del pkill: hoy tres scripts se mataron a sí mismos.
# ============================================================================
set -uo pipefail
export PATH=/venv/main/bin:$PATH
AQUI=$(cd "$(dirname "$0")" && pwd)
GPUS="${GPUS:-4}"
RUNNER="${RUNNER:-/root/runner.py}"
COMFY="${COMFY:-/workspace/ComfyUI}"
[ -f "$COMFY/main.py" ] || COMFY=/opt/workspace-internal/ComfyUI
export ASSETS="${ASSETS:-$AQUI/assets}" PLANOS="${PLANOS:-/root/planos.json}"
export PASOS="${PASOS:-8}" TURBO="${TURBO:-1}"
[ -z "${PLANTILLA:-}" ] && [ -f /root/plantilla_h3.json ] && export PLANTILLA=/root/plantilla_h3.json
# lanzar.sh exporta COLA y este script la hereda: con ella, los runners de
# rescate encontrarían todo ya reclamado y no rehacerían nada.
unset COLA

# ── esperar a los runners ───────────────────────────────────────────────────
while pgrep -f "[r]unner.py --gpu" >/dev/null; do sleep 30; done
echo "== runners terminados $(date +%T) =="

for g in $(seq 0 $((GPUS - 1))); do
  LOG="/root/gpu$g.log"
  grep -q "fallaron tras 3 pasadas" "$LOG" 2>/dev/null || continue
  CAIDOS=$(grep -h "fallaron tras 3 pasadas" "$LOG" | tail -1 | sed 's/.*pasadas: //')
  echo "== placa $g: caídos $CAIDOS · reinicio con VRAM limpia =="
  P=$((18188 + g))
  # Paso 1, sólo matar (patrón con corchete y puerto en variable).
  pkill -f "[d]isable-auto-launch --port $P" 2>/dev/null; sleep 5
  # Paso 2, sólo arrancar.
  if [ "$g" = "0" ]; then
    supervisorctl restart comfyui >/dev/null 2>&1 || \
      (cd "$COMFY" && CUDA_VISIBLE_DEVICES=0 setsid nohup python main.py --disable-auto-launch \
        --port "$P" --enable-cors-header > /root/comfy0.log 2>&1 < /dev/null &)
  else
    (cd "$COMFY" && CUDA_VISIBLE_DEVICES=$g setsid nohup python main.py --disable-auto-launch \
      --port "$P" --enable-cors-header > "/root/comfy$g.log" 2>&1 < /dev/null &)
  fi
  for _ in $(seq 1 80); do
    curl -s -m 3 "http://127.0.0.1:$P/object_info" >/dev/null 2>&1 && break; sleep 3
  done
  # Paso 3: el runner rehace sólo lo que falta de su reparto.
  python "$RUNNER" --gpu "$g" --total "$GPUS" >> "/root/gpu${g}_rescate.log" 2>&1
  echo "   placa $g: $(tail -n 3 "/root/gpu${g}_rescate.log" | grep -E 'termin|fallaron' | tr -d '\r' | tr '\n' ' ')"
done

faltan () {
python - <<'PY'
import json, os
g = json.load(open(os.environ["PLANOS"], encoding="utf-8"))
out = "/workspace/ComfyUI/output/video"
hay = os.listdir(out) if os.path.isdir(out) else []
print(" ".join(p["id"] for p in g["planos"] if not any(f.startswith(p["id"] + "_") for f in hay)))
PY
}

# Pasada atrapa-todo. El reparto es por carga: si `planos.json` cambió a
# mitad de corrida (31/8: dos planos acortados a 6,6 s), los planos se
# rebarajan entre placas y alguno puede quedar sin runner que lo reclame.
# Una sola placa recorre TODA la lista y hace lo que falte, sea de quien sea.
FALTAN=$(faltan)
if [ -n "$FALTAN" ]; then
  echo "== atrapa-todo en la placa 0: $FALTAN =="
  python "$RUNNER" --gpu 0 --total 1 >> /root/gpu_atrapatodo.log 2>&1
  FALTAN=$(faltan)
fi
if [ -z "$FALTAN" ]; then echo "== RESCATE: están los $(ls /workspace/ComfyUI/output/video/*.mp4 | wc -l) clips =="
else echo "== RESCATE: siguen faltando $FALTAN — bajar la duración de esos planos a 6,6 s o menos =="; fi
