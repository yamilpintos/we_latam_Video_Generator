#!/usr/bin/env bash
# ============================================================================
# Instala MiniMax H3 en una instancia Vast.ai con ComfyUI. Se ejecuta DENTRO.
#
#   Jupyter -> Upload -> este archivo
#   Jupyter Terminal -> PERFIL=max bash ~/vast-setup-h3.sh
#   Para el pipeline de planos, que solo usa primer fotograma:
#   Jupyter Terminal -> SOLO_FL=1 PERFIL=max bash ~/vast-setup-h3.sh
#
# PERFILES (elegir según la VRAM por placa):
#
#   q6     32 GB ·  93 GB · el DiT sin podar en GGUF Q6_K, 28.2 GB. Es el mas
#          grande que entra en una 5090. Menos compresion que el Q5 (6 bits por
#          peso en vez de 5) a cambio de 4 GB mas de VRAM. Queda justo: si tira
#          out of memory, bajar a PERFIL=max.
#   max    32 GB · 106 GB de descarga · el DiT **sin podar** en GGUF Q5_K_M.
#          Es lo mejor que entra en una 5090. Recupera los parámetros que el
#          pruned_fp8 había borrado, a cambio de 3 GB más y algo de velocidad.
#   fp8    32 GB ·  63 GB · el pruned_fp8. Más rápido, calidad menor.
#   int8   48 GB · 101 GB · DiT sin podar en int8 nativo.
#   bf16   96 GB · 190 GB · el modelo completo sin comprimir.
#
# LICENCIA: la MiniMax H3 Community License excluye EE.UU., UE, Reino Unido y
# Corea del Sur del despliegue local. Elegir el datacenter antes de alquilar.
# ============================================================================
set -uo pipefail

PERFIL="${PERFIL:-max}"
TURBO="${TURBO:-1}"
SOLO_FL="${SOLO_FL:-0}"
CO="Comfy-Org/MiniMax-H3"
GG="Abiray/MiniMax-H3-GGUF"

pip install -q -U "huggingface_hub[cli]" 2>/dev/null
export HF_XET_HIGH_PERFORMANCE=1     # reemplazó a hf_transfer

# ── dónde vive ComfyUI ──────────────────────────────────────────────────────
# La imagen de Vast trae dos árboles: /opt/workspace-internal/ComfyUI y
# /workspace/ComfyUI. El proceso corre desde uno y `find` suele encontrar el
# otro primero, que fue exactamente el error que nos costó una hora. Así que
# preguntamos por el proceso que está corriendo, no por el disco.
COMFY="${COMFY:-}"
if [ -z "$COMFY" ]; then
  # ComfyUI se lanza como `python main.py` SIN ruta, así que no sirve mirar la
  # línea de comando: hay que preguntarle el directorio de trabajo al proceso.
  PID=$(pgrep -f "main.py" | head -1)
  [ -n "$PID" ] && COMFY=$(readlink -f "/proc/$PID/cwd")
  [ -n "$COMFY" ] && [ ! -f "$COMFY/main.py" ] && COMFY=""
fi
if [ -z "$COMFY" ]; then
  COMFY=$(dirname "$(find / -name main.py -path '*ComfyUI*' 2>/dev/null | head -1)")
fi
if [ -z "$COMFY" ]; then echo "!! no encontré ComfyUI"; exit 1; fi
echo "== ComfyUI en $COMFY =="
df -h "$COMFY" | tail -1

# ── nodo GGUF ───────────────────────────────────────────────────────────────
if [ "$PERFIL" = "max" -o "$PERFIL" = "q6" ] && [ ! -d "$COMFY/custom_nodes/ComfyUI-GGUF" ]; then
  echo "== instalando ComfyUI-GGUF =="
  git clone -q https://github.com/city96/ComfyUI-GGUF "$COMFY/custom_nodes/ComfyUI-GGUF"
  pip install -q gguf
fi

# ── qué bajar ───────────────────────────────────────────────────────────────
REPO=()
ARCH=()
add () { REPO+=("$1"); ARCH+=("$2"); }

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
    add "$CO" "diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors"
    ;;
  fp8)
    add "$CO" "diffusion_models/minimax_h3_ref2va_pruned_fp8_scaled.safetensors"
    add "$CO" "diffusion_models/minimax_h3_fl2va_pruned_fp8_scaled.safetensors"
    add "$CO" "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
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
  add "$CO" "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
  add "$CO" "loras/minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"
fi

# ── SOLO_FL=1: bajar unicamente el modelo de primer fotograma ───────────────
# El pipeline de planos arranca cada plano de su propio dibujo de storyboard,
# asi que usa FL2VA para todo y no toca Ref2VA nunca. Sacarlo ahorra la mitad
# de la descarga del DiT: en el perfil "max" son 24 GB y unos 15 min menos.
if [ "$SOLO_FL" = "1" ]; then
  keep_r=(); keep_a=()
  for i in "${!ARCH[@]}"; do
    case "${ARCH[$i]}" in
      *[Rr]ef2[Vv][Aa]*|*ref2v_turbo*) echo "   (salteo ${ARCH[$i]##*/})" ;;
      *) keep_r+=("${REPO[$i]}"); keep_a+=("${ARCH[$i]}") ;;
    esac
  done
  REPO=("${keep_r[@]}"); ARCH=("${keep_a[@]}")
fi

mkdir -p "$COMFY/models"/{diffusion_models,unet,text_encoders,vae,loras}
for i in "${!ARCH[@]}"; do
  echo ">> ${ARCH[$i]}"
  hf download "${REPO[$i]}" "${ARCH[$i]}" --local-dir "$COMFY/models" --max-workers 16
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
for i in $(seq 1 60); do
  curl -s -m 3 http://127.0.0.1:18188/object_info >/dev/null 2>&1 && break
  sleep 3
done

python - <<'VERIF'
import json, urllib.request
oi = json.load(urllib.request.urlopen("http://127.0.0.1:18188/object_info", timeout=120))
for nodo, campo in (("UNETLoader", "unet_name"), ("UnetLoaderGGUF", "unet_name"),
                    ("CLIPLoader", "clip_name"), ("VAELoader", "vae_name"),
                    ("LoraLoaderModelOnly", "lora_name")):
    try:
        v = oi[nodo]["input"]["required"][campo][0]
        ok = "OK " if any("inimax" in str(x) or "H3" in str(x) for x in v) else "!! "
        print(f"  {ok}{nodo:22} {v}")
    except KeyError:
        print(f"  -- {nodo:22} (nodo ausente)")
VERIF

# ── plantilla oficial -> formato API ────────────────────────────────────────
echo
echo "== armando el workflow en formato API =="
python - <<'CONV'
import glob, json, os, urllib.request
oi = json.load(urllib.request.urlopen("http://127.0.0.1:18188/object_info", timeout=120))
# Rutas conocidas primero. El glob recursivo desde / tarda VARIOS MINUTOS con
# 100 GB de modelos en el disco y parece que el script se colgó: no usarlo salvo
# que no quede otra.
REL = "comfyui_workflow_templates_json/templates/video_minimax_h3_r2v.json"
cand = []
for base in (glob.glob("/venv/*/lib/python3.*/site-packages")
             + glob.glob("/usr/local/lib/python3.*/site-packages")
             + glob.glob("/usr/lib/python3/dist-packages")
             + glob.glob("/opt/*/lib/python3.*/site-packages")):
    p = os.path.join(base, REL)
    if os.path.exists(p):
        cand = [p]
        break
if not cand:
    print("  !! no está en las rutas habituales, buscando en todo el disco...")
    cand = glob.glob("/**/" + REL, recursive=True)
if not cand:
    raise SystemExit("  !! no encontré la plantilla oficial")
print(f"  plantilla: {cand[0]}")
d = json.load(open(cand[0]))
orig = {l[0]: (l[1], l[2]) for l in d["links"]}
CABLE = {"MODEL", "CLIP", "VAE", "CONDITIONING", "LATENT", "IMAGE", "AUDIO",
         "NOISE", "GUIDER", "SAMPLER", "SIGMAS", "VIDEO"}
api = {}
for n in d["nodes"]:
    t = n["type"]
    if t in ("MarkdownNote", "Note") or t not in oi:
        continue
    ins, conect = {}, set()
    for i in n.get("inputs") or []:
        conect.add(i["name"])
        if i.get("link") is not None and orig.get(i["link"]):
            s = orig[i["link"]]
            ins[i["name"]] = [str(s[0]), s[1]]
    req = oi[t]["input"].get("required", {})
    libres = [k for k, v in req.items()
              if k not in conect and not (isinstance(v[0], str) and v[0] in CABLE)]
    for k, val in zip(libres, n.get("widgets_values") or []):
        ins[k] = val
    api[str(n["id"])] = {"class_type": t, "inputs": ins}
# widgets_values conserva valores de campos que ahora son cable y deja este en "".
if "136" in api:
    api["136"]["inputs"]["ref_image_size"] = "match"
json.dump(api, open("/root/h3_r2v_api.json", "w"), indent=1, ensure_ascii=False)
print(f"  OK  /root/h3_r2v_api.json ({len(api)} nodos)")
CONV

# ── copiar lo que se haya subido junto a este script ────────────────────────
# Todo lo que subas por Jupyter a la misma carpeta queda listo para usar sin
# tener que pegar nada en la terminal.
AQUI=$(cd "$(dirname "$0")" && pwd)
for f in h3-cadena.py h3-gen.py h3-pelicula.py h3-planos.py; do
  [ -f "$AQUI/$f" ] && cp "$AQUI/$f" "/root/${f#h3-}" && echo "  copiado $f -> /root/${f#h3-}"
done
for f in "$AQUI"/p[0-9].txt "$AQUI"/prompt.txt "$AQUI"/guion.json "$AQUI"/planos.json; do
  [ -f "$f" ] && cp "$f" /root/ && echo "  copiado $(basename "$f")"
done
# Las imágenes madre se quedan donde están: h3-pelicula.py las lee de ahí.
if [ -d "$AQUI/assets" ]; then
  echo "  $(ls "$AQUI"/assets/*.png 2>/dev/null | wc -l) imágenes madre en $AQUI/assets"
fi

echo
echo "======================================================================"
echo " Listo."
echo
echo " PELICULA POR PLANOS (lo recomendado):"
echo "   PASOS=8 bash $AQUI/lanzar.sh"
echo "   Levanta un ComfyUI por placa y reparte los 42 planos. Unos 45 min."
echo "   Al terminar:  python /root/planos.py --montar"
echo
echo " Un plano suelto, para probar:"
echo "   python /root/planos.py --gpu 0 --total 42"
echo
echo " Metodo viejo de clips encadenados (ver REGLAS-ENCADENADO.md):"
echo "   python /root/cadena.py 10 4 PRUEBA        # segundos pasos prefijo"
echo
echo " Variables: PASOS= TURBO=0 GPUS= ASSETS= DIT_FL= ENC= SHIFT_AUDIO="
echo "======================================================================"
