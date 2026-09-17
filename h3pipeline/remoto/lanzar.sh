#!/usr/bin/env bash
# ============================================================================
# Levanta un ComfyUI por placa y reparte los planos entre ellas.
#
#   bash /workspace/refs/lanzar.sh
#
# Variables (van adelante del comando):
#   GPUS=4          cuántas placas usar
#   PASOS=8         pasos de sampleo
#   TURBO=1         1 usa la LoRA turbo (para 4-8 pasos); 0 la apaga (para 20)
#   PLANOS=         otra lista de planos
#   ASSETS=         otra carpeta de dibujos
#   ANCHO= ALTO=    fuerzan la resolución (si no, sale de planos.json)
#
# Como ningún plano depende de otro, las unidades repartibles son todas y el
# reparto por índice sale parejo solo. Ninguna placa espera a otra.
# ============================================================================
set -uo pipefail

AQUI=$(cd "$(dirname "$0")" && pwd)
GPUS="${GPUS:-4}"
export PASOS="${PASOS:-8}"
export TURBO="${TURBO:-1}"
# Los dibujos están al lado de este script, subas la carpeta donde la subas.
export ASSETS="${ASSETS:-$AQUI/assets}"
export PLANOS="${PLANOS:-$AQUI/planos.json}"
[ -f "$PLANOS" ] || PLANOS="/root/planos.json"
export PLANOS
RUNNER="${RUNNER:-/root/runner.py}"
[ -f "$RUNNER" ] || RUNNER="$AQUI/runner.py"
# La plantilla de H3 que bajó setup.sh del repo de Comfy (trampa 13): el
# paquete de plantillas de la imagen puede no traerla. Si el runner la recibe
# por PLANTILLA no barre el disco buscándola.
if [ -z "${PLANTILLA:-}" ] && [ -f /root/plantilla_h3.json ]; then
  export PLANTILLA=/root/plantilla_h3.json
fi

read -r TOTAL W H NOMBRE <<EOF
$(python - <<'PY'
import json, os
g = json.load(open(os.environ["PLANOS"], encoding="utf-8"))
print(len(g["planos"]),
      os.environ.get("ANCHO") or g.get("ancho", 1344),
      os.environ.get("ALTO") or g.get("alto", 768),
      g.get("titulo", "video"))
PY
)
EOF
export ANCHO="$W" ALTO="$H"

# Dónde vive ComfyUI. Se le pregunta al PROCESO (no al disco: hay dos árboles).
# Pero justo después de `setup.sh` ComfyUI está reiniciándose y puede no haber
# proceso todavía —pasó el 31/8: "no encontré ComfyUI" y la corrida no arrancó
# con la máquina cobrando— así que primero se espera a que el 18188 responda,
# y si el proceso igual no se deja leer, se cae a las rutas conocidas.
for _ in $(seq 1 36); do
  curl -s -m 3 "http://127.0.0.1:18188/system_stats" >/dev/null 2>&1 && break
  sleep 5
done
COMFY=""
for PID in $(pgrep -f "main.py"); do
  C=$(readlink -f "/proc/$PID/cwd" 2>/dev/null)
  if [ -n "$C" ] && [ -f "$C/main.py" ]; then COMFY="$C"; break; fi
done
if [ -z "$COMFY" ]; then
  for C in /workspace/ComfyUI /opt/workspace-internal/ComfyUI; do
    [ -f "$C/main.py" ] && { COMFY="$C"; break; }
  done
fi
if [ -z "$COMFY" ]; then echo "!! no encontré ComfyUI (ni proceso ni rutas conocidas)"; exit 1; fi
echo "== $NOMBRE · ComfyUI en $COMFY · $GPUS placas · $PASOS pasos · turbo=$TURBO · ${W}x${H} · $TOTAL planos =="

# ── ¿faltan dibujos? ────────────────────────────────────────────────────────
# Chequear ahora y no dentro del bucle: un plano sin dibujo se descubriría
# recién después de una hora de generación, con la máquina cobrando.
FALTAN=0
for id in $(python - <<'PY'
import json, os
for p in json.load(open(os.environ["PLANOS"], encoding="utf-8"))["planos"]:
    # Un plano de edición (ref2va con video de referencia) no tiene dibujo:
    # lo que tiene que estar es el video, y la referencia si la hay.
    for k in ("first_frame", "ref_video"):
        if p.get(k):
            print(p[k].split("/")[-1])
    for r in p.get("refs_extra") or []:
        print(r.split("/")[-1])
PY
); do
  [ -f "$ASSETS/$id" ] || { echo "  !! falta el dibujo $id"; FALTAN=1; }
done
[ "$FALTAN" = "1" ] && { echo "!! faltan dibujos en $ASSETS"; exit 1; }
echo "   los $TOTAL dibujos de storyboard están en $ASSETS"

# ── un ComfyUI por placa ────────────────────────────────────────────────────
# La 0 ya la levanta el supervisor en el 18188. Las demás las abrimos nosotros,
# escalonadas para que no peleen por el disco al cargar 24 GB de modelo cada una.
cd "$COMFY"
for g in $(seq 1 $((GPUS - 1))); do
  P=$((18188 + g))
  if curl -s -m 3 "http://127.0.0.1:$P/system_stats" >/dev/null 2>&1; then
    echo "  placa $g ya estaba en el $P"
    continue
  fi
  echo "  levantando placa $g en el $P"
  CUDA_VISIBLE_DEVICES=$g nohup python main.py --disable-auto-launch \
    --port "$P" --enable-cors-header > "/root/comfy$g.log" 2>&1 &
  sleep 25
done

echo "== esperando a que respondan =="
for g in $(seq 0 $((GPUS - 1))); do
  P=$((18188 + g))
  for _ in $(seq 1 40); do
    curl -s -m 3 "http://127.0.0.1:$P/system_stats" >/dev/null 2>&1 && break
    sleep 5
  done
  if curl -s -m 3 "http://127.0.0.1:$P/system_stats" >/dev/null 2>&1; then
    echo "  placa $g OK ($P)"
  else
    echo "  !! placa $g no responde. Mirá /root/comfy$g.log — casi siempre es"
    echo "     que se quedó sin VRAM. Probá con GPUS=$g."
    exit 1
  fi
done

# ── repartir los planos ─────────────────────────────────────────────────────
echo "== lanzando =="
# Cola compartida: una placa que termina lo suyo toma lo que las otras todavía
# no empezaron (ver runner.py, main). El nombre cambia en cada lanzamiento.
export COLA="${COLA:-$(date +%s)}"
for g in $(seq 0 $((GPUS - 1))); do
  nohup python "$RUNNER" --gpu "$g" --total "$GPUS" > "/root/gpu$g.log" 2>&1 &
  echo "  placa $g lanzada"
done

# El rescate queda esperando: cuando los runners terminen, si alguno dejó
# planos caídos tras sus tres pasadas, reinicia esa placa con VRAM limpia y los
# rehace. Es lo que el 31/8 hubo que hacer a mano con S30.
if [ -f "$AQUI/rescate.sh" ]; then
  GPUS="$GPUS" setsid nohup bash "$AQUI/rescate.sh" > /root/rescate.log 2>&1 < /dev/null &
  echo "  rescate en espera (log: /root/rescate.log)"
fi

echo
echo "Seguilo con:   tail -n3 /root/gpu?.log"
echo "Cuántos van:   ls /workspace/ComfyUI/output/video/*.mp4 | wc -l   (de $TOTAL)"
echo "Al terminar:   python $RUNNER --montar"
echo "Los tiempos reales quedan en /workspace/ComfyUI/output/video/metricas.json"
