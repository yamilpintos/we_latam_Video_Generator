#!/bin/bash
# post_remoto.sh <cruda.mp4> <fuente.mp4> <ancho> <alto> <crf> <final.mp4>
# La salida del modelo (x4 exacto, sin audio, crf 8) se lleva al tamano final de
# entrega (p. ej. 2880x2160 para 4:3: correccion del pixel no cuadrado de PAL, no un
# estirado) y se le pega el audio de la fuente preparada. Se hace EN la maquina
# porque la cruda de un capitulo pesa decenas de GB y no conviene bajarla.
# La A100 no tiene NVENC: x264 por CPU, con todos los nucleos del host.
# Avance en /root/post-progreso.txt (frame=N). Termina con POST_OK <bytes> o POST_FALLO <motivo>.
set -uo pipefail
PY=/venv/main/bin/python
FF=$($PY -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null)
[ -n "$FF" ] && [ -x "$FF" ] || FF=$(command -v ffmpeg || true)
[ -n "$FF" ] || { echo POST_FALLO sin-ffmpeg; exit 1; }
CRUDA=$1; FUENTE=$2; W=$3; H=$4; CRF=$5; FINAL=$6
MAPA=""
if "$FF" -hide_banner -i "$FUENTE" 2>&1 | grep -q "Audio:"; then MAPA="-map 1:a -c:a copy"; fi
rm -f /root/post-progreso.txt
"$FF" -hide_banner -y -nostats -progress /root/post-progreso.txt -i "$CRUDA" -i "$FUENTE" \
  -filter_complex "[0:v]scale=$W:$H:flags=lanczos,setsar=1,format=yuv420p[v]" -map "[v]" $MAPA \
  -c:v libx264 -preset medium -crf "$CRF" -shortest -movflags +faststart "$FINAL" 2>/root/post-ffmpeg.err
RC=$?
if [ $RC -eq 0 ] && [ -s "$FINAL" ]; then
  echo "POST_OK $(stat -c %s "$FINAL")"
else
  tail -n 5 /root/post-ffmpeg.err
  echo "POST_FALLO codificacion rc=$RC"
  exit 1
fi
