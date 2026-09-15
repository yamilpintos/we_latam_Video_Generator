"""
Genera N clips encadenados: cada uno arranca en el último frame del anterior.

Se ejecuta DENTRO de la instancia de Vast, después de `vast-setup-h3.sh`.

    python h3-cadena.py <segundos> <pasos> <prefijo>

    TURBO=0            desactiva la LoRA turbo (calidad máxima, 5× más lento)
    ENC=<archivo>      cambia el text encoder
    DIT=<archivo>      cambia el modelo que genera
    SHIFT_AUDIO=<n>    ajusta el cronograma de ruido del audio (default 3.0)
    SHIFT_VIDEO=<n>    ídem para el video (default 12.0)
    REF1..REF9=<png>   imágenes de referencia para la etapa 1
    REF_SIZE=max       máxima fidelidad de identidad, varias veces más lento
    PORT=<n>           ComfyUI de otra GPU (18188 por defecto)

Los prompts salen de /root/p1.txt, p2.txt, p3.txt … uno por etapa. Si no existen,
usa los de ejemplo de abajo.

Cómo funciona el encadenado
  La etapa 1 usa **Ref2VA** (`MiniMaxH3ReferenceToVideo`) sin imágenes de
  referencia, o sea texto puro. Las siguientes usan **FL2VA**
  (`MiniMaxH3ImageToVideo`) con `first_frame` = el último fotograma del clip
  anterior, extraído con ffmpeg y subido por /upload/image.

  Son dos modelos distintos y cada uno tiene su LoRA turbo: la de referencias es
  v0.1 y la de primer/último frame es v1.0, más madura.
"""
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request

# Cada GPU corre su propio ComfyUI en un puerto distinto: PORT elige cuál.
API = os.environ.get("API", "http://127.0.0.1:" + os.environ.get("PORT", "18188"))
OUT = os.environ.get("OUT", "/workspace/ComfyUI/output/video")
W, H = 1344, 768

SEG = float(sys.argv[1]) if len(sys.argv) > 1 else 10
PASOS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
PREF = sys.argv[3] if len(sys.argv) > 3 else "CADENA"
TURBO = os.environ.get("TURBO", "1") == "1"

DIT_REF = os.environ.get("DIT", "MiniMax-H3-Ref2VA-Q5_K_M.gguf")
DIT_FL = os.environ.get("DIT_FL", "MiniMax-H3-FL2VA-Q5_K_M.gguf")
ENC = os.environ.get("ENC", "qwen3vl_32b_minimax_h3_int8_convrot.safetensors")
LORA_REF = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
LORA_FL = "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"
WF = "/root/h3_r2v_api.json"


def construir_workflow():
    """Convierte la plantilla oficial de ComfyUI a formato API.

    La plantilla viene en formato de editor (nodos + links). El endpoint /prompt
    quiere otra cosa: un dict de nodos con sus entradas ya resueltas. Mapeamos
    cada cable por su link y cada widget contra el esquema real de la instancia,
    así nunca inventamos un nombre de campo.
    """
    import glob
    oi = json.load(urllib.request.urlopen(API + "/object_info", timeout=120))
    # Rutas donde suele estar, en orden. El glob recursivo desde / es el último
    # recurso: con 100 GB de modelos en el disco tarda varios minutos.
    REL = "comfyui_workflow_templates_json/templates/video_minimax_h3_r2v.json"
    cand = []
    if os.environ.get("PLANTILLA"):
        cand = [os.environ["PLANTILLA"]]
    else:
        for base in glob.glob("/venv/*/lib/python3.*/site-packages") + \
                    glob.glob("/usr/lib/python3/dist-packages") + \
                    glob.glob("/usr/local/lib/python3.*/site-packages") + \
                    glob.glob("/opt/*/lib/python3.*/site-packages"):
            p = os.path.join(base, REL)
            if os.path.exists(p):
                cand = [p]
                break
        if not cand:
            print("  buscando la plantilla en todo el disco (puede tardar)...")
            cand = glob.glob("/**/" + REL, recursive=True)
    if not cand:
        raise SystemExit("!! no encontré la plantilla. Pasala con PLANTILLA=<ruta>")
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
    # widgets_values conserva valores de campos que ahora son cable: este queda "".
    if "136" in api:
        api["136"]["inputs"]["ref_image_size"] = "match"
    json.dump(api, open(WF, "w"), indent=1, ensure_ascii=False)
    print(f"  workflow armado: {WF} ({len(api)} nodos)")


if not os.path.exists(WF):
    construir_workflow()

# Prompts: uno por etapa. Se leen de /root/pN.txt si existen.
P = []
for i in range(1, 21):
    f = f"/root/p{i}.txt"
    if not os.path.exists(f):
        break
    P.append(open(f, encoding="utf-8").read())
if P:
    print(f"usando {len(P)} prompts de /root/p1..{len(P)}.txt")
else:
    P = ["Epic cinematic anamorphic 35mm shot of a vast desert at dawn, slow crane up. "
         "[Ambient] Wind. NO MUSIC, no speech, no text."]
    print("sin /root/pN.txt: usando el prompt de ejemplo")


def post(ruta, cuerpo):
    q = urllib.request.Request(API + ruta, data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(q, timeout=180))


def esperar(pid, etq):
    t0 = time.time()
    while True:
        hi = json.load(urllib.request.urlopen(f"{API}/history/{pid}", timeout=60))
        if pid in hi:
            st = hi[pid].get("status", {})
            if st.get("status_str") == "error":
                print(f"\n{etq} FALLÓ:", json.dumps(st.get("messages"))[:1800])
                sys.exit(1)
            print(f"\n  {etq} listo en {(time.time()-t0)/60:.1f} min")
            for _n, o in hi[pid].get("outputs", {}).items():
                for im in o.get("images", []):
                    return im["filename"]
            return None
        print(f"  {etq} generando... {time.time()-t0:.0f}s", end="\r", flush=True)
        time.sleep(5)


def subir(ruta):
    """POST /upload/image. Devuelve el nombre con el que ComfyUI lo guardó."""
    b = "----x" + secrets.token_hex(8)
    n = os.path.basename(ruta)
    cuerpo = b"".join([
        f"--{b}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{n}"\r\n'.encode(),
        b"Content-Type: image/png\r\n\r\n", open(ruta, "rb").read(),
        f"\r\n--{b}\r\n".encode(),
        b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
        f"--{b}--\r\n".encode()])
    q = urllib.request.Request(API + "/upload/image", data=cuerpo, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    r = json.load(urllib.request.urlopen(q, timeout=300))
    return f"{r['subfolder']}/{r['name']}" if r.get("subfolder") else r["name"]


def base(modelo, lora):
    """Grafo común: modelo, LoRA opcional y el SigmaShift que controla el audio."""
    wf = json.load(open(WF))
    # Los .gguf necesitan el cargador de ComfyUI-GGUF: mismo campo, otra clase.
    wf["127"]["class_type"] = "UnetLoaderGGUF" if modelo.endswith(".gguf") else "UNETLoader"
    wf["127"]["inputs"] = {"unet_name": modelo}
    if not modelo.endswith(".gguf"):
        wf["127"]["inputs"]["weight_dtype"] = "default"
    wf["128"]["inputs"]["clip_name"] = ENC
    wf["128"]["inputs"]["device"] = "default"

    fuente = "127"
    if TURBO:
        wf["200"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["127", 0], "lora_name": lora, "strength_model": 1.0}}
        fuente = "200"

    # Video y audio tienen cronogramas de ruido separados. Es la palanca dedicada
    # a la calidad del audio, que con pocos pasos sale sucio.
    wf["201"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {
        "model": [fuente, 0],
        "shift_video": float(os.environ.get("SHIFT_VIDEO", "12.0")),
        "shift_audio": float(os.environ.get("SHIFT_AUDIO", "3.0"))}}
    wf["124"]["inputs"]["model"] = ["201", 0]
    wf["126"]["inputs"]["model"] = ["201", 0]
    wf["124"]["inputs"]["steps"] = PASOS
    wf["132"]["inputs"]["value"] = SEG
    return wf


T0 = time.time()
salidas = []
for i, prompt in enumerate(P):
    print(f"== ETAPA {i+1}/{len(P)} ==")
    if i == 0:
        wf = base(DIT_REF, LORA_REF)
        for k in ("ref_images.ref_image_0", "ref_images.ref_image_1"):
            wf["136"]["inputs"].pop(k, None)
        # REF1, REF2, ... hasta REF9: imágenes de referencia para la etapa 1.
        # En el prompt se las nombra <Picture 1>, <Picture 2>, en ese orden.
        for j in range(1, 10):
            ruta = os.environ.get(f"REF{j}")
            if not ruta:
                break
            nodo = str(300 + j)
            wf[nodo] = {"class_type": "LoadImage", "inputs": {"image": subir(ruta)}}
            wf["136"]["inputs"][f"ref_images.ref_image_{j-1}"] = [nodo, 0]
            print(f"  <Picture {j}> = {os.path.basename(ruta)}")
        # "max" usa 2048px de lado corto y da la mejor fidelidad de identidad,
        # pero los tokens de referencia atraviesan cada paso: es varias veces
        # más lento. Con "match" alcanza para probar.
        wf["136"]["inputs"]["ref_image_size"] = os.environ.get("REF_SIZE", "match")
        wf["136"]["inputs"].update({"width": W, "height": H})
    else:
        prev = os.path.join(OUT, salidas[-1])
        fr = f"/root/frame_{i}.png"
        # -sseof -0.15 busca desde el final; -update 1 deja el último frame leído.
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-sseof", "-0.15", "-i", prev, "-update", "1", "-q:v", "1", fr],
                       check=True)
        nom = subir(fr)
        print(f"  frame de continuidad: {nom}")
        wf = base(DIT_FL, LORA_FL)
        wf["300"] = {"class_type": "LoadImage", "inputs": {"image": nom}}
        wf["136"] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["128", 0], "vae": ["119", 0], "prompt": ["138", 0],
            "width": W, "height": H, "length": ["131", 1], "first_frame": ["300", 0]}}

    wf["138"]["inputs"]["value"] = prompt
    wf["129"]["inputs"]["noise_seed"] = 777 + i
    wf["92"]["inputs"]["filename_prefix"] = f"video/{PREF}_{i+1}"
    salidas.append(esperar(post("/prompt", {"prompt": wf, "client_id": "cad"})["prompt_id"],
                           f"E{i+1}"))

lista = "/root/lista_concat.txt"
open(lista, "w").write("".join(f"file '{os.path.join(OUT, s)}'\n" for s in salidas))
final = os.path.join(OUT, f"{PREF}_COMPLETO.mp4")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                "-safe", "0", "-i", lista, "-c", "copy", final], check=True)

t = time.time() - T0
print(f"\n=== {PREF}_COMPLETO.mp4 · {SEG*len(P):.0f}s de video en {t/60:.1f} min ===")
print(f"  {PASOS} pasos · turbo={TURBO} · {t/60/len(P):.1f} min por clip")
print("  anotalo en COSTOS-H3.md")
for s in salidas:
    print("  ", s)
