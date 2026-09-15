"""
Genera un clip con MiniMax H3. Se ejecuta DENTRO de la instancia de Vast.

    python h3-gen.py <ancho> <alto> <segundos> <pasos> <turbo01> <prefijo> [seed]

    DIT=<archivo>   modelo generador. Si termina en .gguf usa UnetLoaderGGUF.
    ENC=<archivo>   text encoder.
    SHIFT_AUDIO=<n> cronograma de ruido del audio (default 3.0). La palanca
                    dedicada a la calidad del audio, que con pocos pasos sale sucio.
    SHIFT_VIDEO=<n> ídem para el video (default 12.0).
    REF=<png>       imagen de referencia; se sube y entra por ref_image_0.

El prompt sale de /root/prompt.txt. Los tags de audio van adentro del mismo
prompt: H3 no tiene entrada separada para audio.

    [Speech] 'texto que el personaje dice, en el idioma final'
    [Foley] pasos, tela. [Ambient] viento. NO MUSIC.
"""
import json
import os
import secrets
import sys
import time
import urllib.request

API = "http://127.0.0.1:18188"

w, h, seg = int(sys.argv[1]), int(sys.argv[2]), float(sys.argv[3])
pasos, turbo, pref = int(sys.argv[4]), sys.argv[5] == "1", sys.argv[6]
seed = int(sys.argv[7]) if len(sys.argv) > 7 else 777

DIT = os.environ.get("DIT", "MiniMax-H3-Ref2VA-Q5_K_M.gguf")
ENC = os.environ.get("ENC", "qwen3vl_32b_minimax_h3_int8_convrot.safetensors")


def post(ruta, cuerpo):
    q = urllib.request.Request(API + ruta, data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(q, timeout=180))


def subir(ruta):
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


wf = json.load(open("/root/h3_r2v_api.json"))

# El nodo 127 carga el modelo. Los .gguf necesitan otro cargador, el de
# ComfyUI-GGUF: mismo nombre de campo, distinta clase.
wf["127"]["class_type"] = "UnetLoaderGGUF" if DIT.endswith(".gguf") else "UNETLoader"
wf["127"]["inputs"] = {"unet_name": DIT}
if not DIT.endswith(".gguf"):
    wf["127"]["inputs"]["weight_dtype"] = "default"

wf["128"]["inputs"]["clip_name"] = ENC
wf["128"]["inputs"]["device"] = "default"

for k in ("ref_images.ref_image_0", "ref_images.ref_image_1"):
    wf["136"]["inputs"].pop(k, None)
if os.environ.get("REF"):
    wf["300"] = {"class_type": "LoadImage", "inputs": {"image": subir(os.environ["REF"])}}
    wf["136"]["inputs"]["ref_images.ref_image_0"] = ["300", 0]
    # "max" da la mejor fidelidad de identidad; el propio tooltip avisa que es
    # varias veces más lento porque los tokens de referencia atraviesan cada paso.
    wf["136"]["inputs"]["ref_image_size"] = os.environ.get("REF_SIZE", "match")

fuente = "127"
if turbo:
    wf["200"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
        "model": ["127", 0], "strength_model": 1.0,
        "lora_name": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"}}
    fuente = "200"

# Video y audio tienen cronogramas de ruido separados en H3.
wf["201"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {
    "model": [fuente, 0],
    "shift_video": float(os.environ.get("SHIFT_VIDEO", "12.0")),
    "shift_audio": float(os.environ.get("SHIFT_AUDIO", "3.0"))}}
wf["124"]["inputs"]["model"] = ["201", 0]
wf["126"]["inputs"]["model"] = ["201", 0]

wf["124"]["inputs"]["steps"] = pasos
wf["136"]["inputs"].update({"width": w, "height": h})
wf["132"]["inputs"]["value"] = seg
wf["129"]["inputs"]["noise_seed"] = seed
wf["92"]["inputs"]["filename_prefix"] = "video/" + pref
wf["138"]["inputs"]["value"] = open("/root/prompt.txt", encoding="utf-8").read()

t0 = time.time()
try:
    pid = post("/prompt", {"prompt": wf, "client_id": "gen"})["prompt_id"]
except urllib.error.HTTPError as e:
    print("RECHAZADO:\n", e.read().decode()[:2000])
    sys.exit(1)
print(f"encolado · {w}x{h} · {seg}s · {pasos} pasos · turbo={turbo}")
print(f"  modelo:  {DIT}")
print(f"  encoder: {ENC}")

while True:
    hi = json.load(urllib.request.urlopen(f"{API}/history/{pid}", timeout=60))
    if pid in hi:
        t = time.time() - t0
        st = hi[pid].get("status", {})
        print(f"\n=== {st.get('status_str')} en {t/60:.1f} min ===")
        if st.get("status_str") == "error":
            print(json.dumps(st.get("messages"))[:2500])
        else:
            print(f"  {t/60:.1f} min por clip · anotalo en COSTOS-H3.md")
        for _n, o in hi[pid].get("outputs", {}).items():
            print("  ", json.dumps(o)[:220])
        break
    print(f"  generando... {time.time()-t0:.0f}s", end="\r", flush=True)
    time.sleep(5)
