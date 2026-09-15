#!/usr/bin/env bash
# ============================================================================
# Instala MiniMax H3 en la instancia alquilada. Se ejecuta DENTRO.
#
#   bash /workspace/refs/setup.sh
#
# Por defecto baja SÓLO FL2VA (~59 GB en vez de 106): este pipeline arranca cada
# plano de su propio dibujo de storyboard, así que Ref2VA no se toca nunca.
# Para el método viejo de clips encadenados: SOLO_FL=0.
#
# PERFILES (elegir según la VRAM por placa):
#
#   max    32 GB · el DiT sin podar en GGUF Q5_K_M, 23,9 GB. Lo mejor que entra
#          en una placa de 32 GB. **El default, y lo que se usa.**
#   q6     32 GB · GGUF Q6_K de 28,2 GB. Menos compresión a cambio de 4 GB más.
#          Queda muy justo: si tira out of memory, volvé a max.
#   fp8    32 GB · el pruned_fp8. Más rápido, calidad menor.
#   int8   48 GB · DiT sin podar en int8 nativo.
#   bf16   96 GB · el modelo completo. Sólo en placas de 96 GB (pico medido:
#          90,9 GB de 95,6). En una de 80 GB no entra.
#
# LICENCIA: la MiniMax H3 Community License excluye EE.UU., UE, Reino Unido y
# Corea del Sur del despliegue local. Elegir el país del host ANTES de alquilar.
# ============================================================================
set -uo pipefail

PERFIL="${PERFIL:-max}"
TURBO="${TURBO:-1}"
CO="Comfy-Org/MiniMax-H3"
GG="Abiray/MiniMax-H3-GGUF"
LX="lightx2v/Minimax-h3-Turbo"
# SOLO_FL: si no se dice nada, se decide mirando planos.json — si algún plano
# es `modo: ref2va` (voz de referencia, 14/9/2026) hace falta Ref2VA.
AQUI0=$(cd "$(dirname "$0")" && pwd)
if [ -z "${SOLO_FL:-}" ]; then
  SOLO_FL=1
  if [ -f "$AQUI0/planos.json" ] && grep -q '"modo": *"ref2va"' "$AQUI0/planos.json"; then
    SOLO_FL=0
    echo "== planos.json tiene planos ref2va: bajo también Ref2VA =="
  fi
fi

pip install -q -U "huggingface_hub[cli]" 2>/dev/null
export HF_XET_HIGH_PERFORMANCE=1     # reemplazó a hf_transfer

# ── ¿llega a Hugging Face? ──────────────────────────────────────────────────
# 14/9/2026, host de Shanghái: huggingface.co y github.com no responden, pero
# hf-mirror.com sí (200 en 0,5 s). Sin esto la descarga reintenta para siempre
# con la máquina cobrando. El CLI `hf` respeta HF_ENDPOINT.
if [ -z "${HF_ENDPOINT:-}" ] && ! curl -s -o /dev/null -m 15 https://huggingface.co/api/models/Comfy-Org/MiniMax-H3; then
  if curl -s -o /dev/null -m 15 https://hf-mirror.com/api/models/Comfy-Org/MiniMax-H3; then
    export HF_ENDPOINT=https://hf-mirror.com
    echo "== huggingface.co no responde: uso el espejo $HF_ENDPOINT =="
  else
    echo "!! no llego ni a huggingface.co ni a hf-mirror.com: esta máquina no puede bajar los modelos"
    exit 1
  fi
fi
# Sin GitHub no se instala ComfyUI-GGUF: se cae al perfil int8p (modelos
# oficiales de Comfy-Org, cargador estándar).
if [ "$PERFIL" = "max" ] && ! curl -s -o /dev/null -m 15 https://github.com; then
  echo "== github.com no responde: sin nodo GGUF, paso al perfil int8p =="
  PERFIL=int8p
fi

# ── dónde vive ComfyUI ──────────────────────────────────────────────────────
# La imagen trae dos árboles: /opt/workspace-internal/ComfyUI y /workspace/ComfyUI.
# El proceso corre desde uno y `find` suele encontrar el otro primero — ese error
# nos costó una hora. Así que le preguntamos al proceso, no al disco. Y como
# ComfyUI se lanza como `python main.py` SIN ruta, tampoco sirve mirar la línea
# de comando: hay que leerle el directorio de trabajo.
COMFY="${COMFY:-}"
if [ -z "$COMFY" ]; then
  PID=$(pgrep -f "main.py" | head -1)
  [ -n "$PID" ] && COMFY=$(readlink -f "/proc/$PID/cwd")
  [ -n "$COMFY" ] && [ ! -f "$COMFY/main.py" ] && COMFY=""
fi
if [ -z "$COMFY" ]; then
  COMFY=$(dirname "$(find / -name main.py -path '*ComfyUI*' 2>/dev/null | head -1)")
fi
if [ -z "$COMFY" ] || [ ! -f "$COMFY/main.py" ]; then
  echo "!! no encontré ComfyUI corriendo. ¿La plantilla de la instancia es de ComfyUI?"
  exit 1
fi
echo "== ComfyUI en $COMFY =="
df -h "$COMFY" | tail -1

# ── ¿esta imagen conoce a H3? ───────────────────────────────────────────────
# El 31/8 el host sirvió una imagen con ComfyUI v0.7.0 (diciembre de 2025),
# anterior a los nodos de H3, aunque el tag lo resolvía Vast. Sin nodos no hay
# corrida, y en modo desatendido nadie lo ve hasta que `seguir` muestra 0 clips
# con la máquina cobrando. Se pregunta al servidor y, si faltan, se actualiza
# ComfyUI a master acá mismo (~2 min) en vez de destruir y volver a alquilar.
export PATH=/venv/main/bin:$PATH
for i in $(seq 1 200); do
  curl -s -m 3 http://127.0.0.1:18188/object_info >/dev/null 2>&1 && break; sleep 3
done
# Sólo si ComfyUI RESPONDE y no tiene los nodos. El 14/9 todavía no había
# arrancado (la máquina bajaba su portal) y esto lo tomó por "faltan nodos".
if curl -s -m 5 http://127.0.0.1:18188/system_stats >/dev/null 2>&1 \
   && ! curl -s -m 60 http://127.0.0.1:18188/object_info | grep -q '"MiniMaxH3ImageToVideo"'; then
  echo "== la imagen no tiene los nodos de H3 ($(cd "$COMFY" && git log -1 --format=%ci)): actualizo ComfyUI =="
  (cd "$COMFY" && git stash -q 2>/dev/null; git fetch -q --depth 1 origin master && git reset -q --hard FETCH_HEAD; git stash pop -q 2>/dev/null; git log -1 --format='   ahora en %h · %ci')
  (cd "$COMFY" && pip install -q -r requirements.txt 2>&1 | grep -v WARNING | tail -2)
  [ -d "$COMFY/custom_nodes/ComfyUI-GGUF" ] && (cd "$COMFY/custom_nodes/ComfyUI-GGUF" && git pull -q 2>/dev/null)
  ACTUALIZADO=1
fi
# La plantilla oficial de H3 puede no venir en el paquete de plantillas de la
# imagen: se baja del repo de Comfy y `runner.py` la toma por PLANTILLA.
if [ ! -f /root/plantilla_h3.json ]; then
  curl -s -L -o /root/plantilla_h3.json \
    "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_minimax_h3_r2v.json" \
    && head -c 1 /root/plantilla_h3.json | grep -q '{' && echo "   plantilla de H3 bajada a /root/plantilla_h3.json"
fi

# ── nodo GGUF ───────────────────────────────────────────────────────────────
if [ "$PERFIL" = "max" -o "$PERFIL" = "q6" ] && [ ! -d "$COMFY/custom_nodes/ComfyUI-GGUF" ]; then
  echo "== instalando ComfyUI-GGUF =="
  git clone -q https://github.com/city96/ComfyUI-GGUF "$COMFY/custom_nodes/ComfyUI-GGUF"
  pip install -q gguf
fi

# ── qué bajar ───────────────────────────────────────────────────────────────
REPO=()
ARCH=()
DEST=()
# Tercer argumento opcional: subcarpeta de models/ cuando el repo guarda el
# archivo en la raíz (las LoRAs de lightx2v no vienen dentro de loras/).
add () { REPO+=("$1"); ARCH+=("$2"); DEST+=("${3:-}"); }

case "$PERFIL" in
  q6)
    add "$GG" "unet/MiniMax-H3-Ref2VA-Q6_K.gguf"
    add "$GG" "unet/MiniMax-H3-FL2VA-Q6_K.gguf"
    add "$CO" "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
    ;;
  max)
    add "$GG" "unet/MiniMax-H3-Ref2VA-Q5_K_M.gguf"
    add "$GG" "unet/MiniMax-H3-FL2VA-Q5_K_M.gguf"
    add "$CO" "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
    # (Sale el ref2va_pruned_fp8_scaled: metadatos rotos, issue #15567 de ComfyUI.)
    ;;
  fp8)
    add "$CO" "diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors"
    add "$CO" "diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors"
    add "$CO" "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
    ;;
  int8p)
    # Los de la plantilla oficial de Comfy: podados (tabla precalculada, no poda
    # de capas) e int8 nativo, 21 GB cada uno, cargador estándar sin nodo GGUF.
    add "$CO" "diffusion_models/minimax_h3_ref2va_pruned_int8_convrot.safetensors"
    add "$CO" "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors"
    add "$CO" "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
    ;;
  int8)
    add "$CO" "diffusion_models/minimax_h3_ref2va_int8_convrot.safetensors"
    add "$CO" "diffusion_models/minimax_h3_fl2va_int8_convrot.safetensors"
    add "$CO" "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
    ;;
  bf16)
    add "$CO" "diffusion_models/minimax_h3_ref2va_bf16.safetensors"
    add "$CO" "diffusion_models/minimax_h3_fl2va_bf16.safetensors"
    add "$CO" "text_encoders/qwen3vl_32b_minimax_h3_bf16.safetensors"
    ;;
  *) echo "PERFIL desconocido: $PERFIL (q6, max, fp8, int8, bf16)"; exit 1 ;;
esac

add "$CO" "vae/minimax_h3_video_vae_fp16.safetensors"
add "$CO" "vae/minimax_h3_audio_vae_fp32.safetensors"
if [ "$TURBO" = "1" ]; then
  # Las de 8 pasos entrenadas a 768p (shift 6/3), las que usa runner.py desde
  # el 14/9. La FL2VA 4-step 768p queda por si se vuelve atrás.
  add "$LX" "minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors" loras
  add "$LX" "minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors" loras
  add "$CO" "loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"
fi

# ── SOLO_FL=1: sacar todo lo de Ref2VA ──────────────────────────────────────
# En el perfil max son 45 GB menos. Lo que eso ahorra depende del host mucho más
# de lo que parece: a 800 Mbps son 8 min y $0.25; a 30 Mbps, 209 min y $6.65.
if [ "$SOLO_FL" = "1" ]; then
  keep_r=(); keep_a=(); keep_d=()
  for i in "${!ARCH[@]}"; do
    case "${ARCH[$i]}" in
      *[Rr]ef2[Vv][Aa]*|*ref2v_turbo*) echo "   (salteo ${ARCH[$i]##*/})" ;;
      *) keep_r+=("${REPO[$i]}"); keep_a+=("${ARCH[$i]}"); keep_d+=("${DEST[$i]}") ;;
    esac
  done
  REPO=("${keep_r[@]}"); ARCH=("${keep_a[@]}"); DEST=("${keep_d[@]}")
fi

mkdir -p "$COMFY/models"/{diffusion_models,unet,text_encoders,vae,loras}
for i in "${!ARCH[@]}"; do
  echo ">> ${ARCH[$i]}"
  hf download "${REPO[$i]}" "${ARCH[$i]}" --local-dir "$COMFY/models/${DEST[$i]}" --max-workers 16 \
    || echo "   !! no pude bajar ${ARCH[$i]} de ${REPO[$i]}"
done

# ── enlazar en el otro árbol de ComfyUI ─────────────────────────────────────
# Symlinks y no `mv`: instantáneo aunque estén en discos distintos, sin duplicar.
for OTRO in /workspace/ComfyUI /opt/workspace-internal/ComfyUI; do
  [ -d "$OTRO" ] || continue
  if [ "$(readlink -f "$OTRO")" = "$(readlink -f "$COMFY")" ]; then continue; fi
  echo "== enlazando pesos en $OTRO =="
  for d in diffusion_models unet text_encoders vae loras; do
    mkdir -p "$OTRO/models/$d"
    for f in "$COMFY/models/$d"/*; do
      [ -f "$f" ] && ln -sf "$f" "$OTRO/models/$d/"
    done
  done
  if [ -d "$COMFY/custom_nodes/ComfyUI-GGUF" ]; then
    ln -sfn "$COMFY/custom_nodes/ComfyUI-GGUF" "$OTRO/custom_nodes/ComfyUI-GGUF" 2>/dev/null
  fi
done

# ComfyUI cachea el listado de modelos al arrancar: sin reiniciar, los loaders
# devuelven listas vacías y el /prompt se rechaza con "value_not_in_list".
echo "== reiniciando ComfyUI =="
supervisorctl restart comfyui 2>/dev/null || pkill -f "main.py --disable-auto-launch" || true
# Hasta 10 minutos: con 59 GB de modelos recién bajados el primer arranque
# tarda más de los 3 min que se esperaban antes, y el 31/8 la verificación
# corrió contra un puerto cerrado y `lanzar.sh` arrancó sin ComfyUI.
for i in $(seq 1 200); do
  curl -s -m 3 http://127.0.0.1:18188/object_info >/dev/null 2>&1 && break
  sleep 3
done

python - <<'VERIF'
import json, urllib.request
oi = json.load(urllib.request.urlopen("http://127.0.0.1:18188/object_info", timeout=120))
malas = 0
for nodo, campo in (("UNETLoader", "unet_name"), ("UnetLoaderGGUF", "unet_name"),
                    ("CLIPLoader", "clip_name"), ("VAELoader", "vae_name"),
                    ("LoraLoaderModelOnly", "lora_name")):
    try:
        v = oi[nodo]["input"]["required"][campo][0]
        ok = any("inimax" in str(x) or "H3" in str(x) for x in v)
        malas += 0 if ok else 1
        print(f"  {'OK ' if ok else '!! '}{nodo:22} {v}")
    except KeyError:
        print(f"  -- {nodo:22} (nodo ausente)")
if malas:
    print("\n  !! ComfyUI no ve los modelos. Casi siempre es la caché del arranque:")
    print("     supervisorctl restart comfyui   (esperá un minuto y volvé a correr esto)")
VERIF

# ── copiar lo que se subió junto a este script ──────────────────────────────
AQUI=$(cd "$(dirname "$0")" && pwd)
[ -f "$AQUI/runner.py" ] && cp "$AQUI/runner.py" /root/runner.py && echo "  copiado runner.py -> /root/"
[ -f "$AQUI/planos.json" ] && cp "$AQUI/planos.json" /root/ && echo "  copiado planos.json -> /root/"
if [ -d "$AQUI/assets" ]; then
  echo "  $(ls "$AQUI"/assets/*.png 2>/dev/null | wc -l) dibujos de storyboard en $AQUI/assets"
fi

echo
echo "======================================================================"
echo " Listo. Ahora:"
echo
echo "   PASOS=8 bash $AQUI/lanzar.sh"
echo
echo " Levanta un ComfyUI por placa y reparte los planos. Al terminar:"
echo "   python /root/runner.py --montar"
echo
echo " Variables: PASOS= TURBO=0 GPUS= ASSETS= PLANOS= ANCHO= ALTO= SHIFT_AUDIO="
echo "======================================================================"
