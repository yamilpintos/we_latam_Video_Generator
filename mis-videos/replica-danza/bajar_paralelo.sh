#!/usr/bin/env bash
# Baja los clips terminados con 12 ssh en paralelo (14/9: desde Taiwán cada
# conexión rinde ~25 KB/s, pero en paralelo suman). Sólo archivos con más de un
# minuto de antigüedad (ya cerrados); cada uno se valida CONTANDO CUADROS (124)
# antes de quedar en clips/: la duración de la cabecera no alcanza — T11 llegó
# cortado a 21 cuadros y ffprobe igual decía 5,17 s (15/9).
set -uo pipefail
cd "$(dirname "$0")"
S="ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o LogLevel=ERROR -p ${PUERTO:-42710} root@${IP:-211.72.13.201}"
FFPROBE=/c/ffmpeg-2026-04-09-git-d3d0b7a5ee-essentials_build/bin/ffprobe
mkdir -p clips clips/.parcial
LISTA=$(timeout 60 $S "cd /workspace/ComfyUI/output/video && find . -maxdepth 1 -regextype egrep -regex './(T|VO)[0-9a-z]*_0+1_\.mp4' -mmin +1 -printf '%f\n'" | sort)
FALTAN=$(for f in $LISTA; do [ -f "clips/$f" ] || echo "$f"; done)
echo "remotos: $(echo $LISTA | wc -w) · a bajar: $(echo $FALTAN | wc -w)"
uno () {
  f=$1
  timeout 900 $S "cat /workspace/ComfyUI/output/video/$f" > "clips/.parcial/$f" &&
    [ "$("$FFPROBE" -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "clips/.parcial/$f" 2>/dev/null | tr -d '')" = "124" ] &&
    mv "clips/.parcial/$f" "clips/$f" && echo "  ok $f" || { echo "  !! $f"; rm -f "clips/.parcial/$f"; }
}
export -f uno; export S FFPROBE
echo "$FALTAN" | grep . | xargs -P 12 -I{} bash -c 'uno {}'
echo "locales: $(ls clips/*.mp4 | wc -l)"
