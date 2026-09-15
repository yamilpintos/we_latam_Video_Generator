"""
Genera una película entera de escenas encadenadas. Se ejecuta DENTRO de Vast.

    python h3-pelicula.py --gpu 0 --total 4          # esta GPU hace 1 de cada 4 escenas
    python h3-pelicula.py --montar                    # une todas las escenas al final

Cómo reparte el trabajo
  Cada escena son 3 clips **en serie**: el B arranca en el último fotograma del A
  y el C en el del B. Eso no se puede paralelizar.
  Pero las escenas **entre sí son independientes**: cada una abre con su propio
  plano de referencia. Así que con 4 GPUs se corren 4 escenas a la vez, cada
  proceso con su `--gpu N`, y cada uno se queda con las escenas cuyo índice
  cumple `indice % total == gpu`.

  Con 10 escenas y 4 GPUs: la 0 hace E01/E05/E09, la 1 hace E02/E06/E10,
  la 2 hace E03/E07 y la 3 hace E04/E08. Tres tandas y termina.

Variables de entorno
    PASOS=8            pasos de sampleo (8 con turbo, 20 sin)
    TURBO=1            1 usa la LoRA turbo (régimen de 4-8 pasos), 0 la apaga
    SEG=10             segundos por clip
    REF_SIZE=match     'max' da mejor fidelidad de identidad por +8% de tiempo
    DIT= DIT_FL= ENC=  modelos, si no los defaults
    SHIFT_AUDIO=3.0    cronograma de ruido del audio
"""
import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request

RAIZ = "/root"
ASSETS = "/workspace/refs/assets"
GUION = f"{RAIZ}/guion.json"
WF = f"{RAIZ}/h3_r2v_api.json"

SEG = float(os.environ.get("SEG", "10"))
PASOS = int(os.environ.get("PASOS", "8"))
TURBO = os.environ.get("TURBO", "1") == "1"
REF_SIZE = os.environ.get("REF_SIZE", "match")
W, H = 1344, 768

DIT_REF = os.environ.get("DIT", "MiniMax-H3-Ref2VA-Q5_K_M.gguf")
DIT_FL = os.environ.get("DIT_FL", "MiniMax-H3-FL2VA-Q5_K_M.gguf")
ENC = os.environ.get("ENC", "qwen3vl_32b_minimax_h3_int8_convrot.safetensors")
LORA_REF = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"
LORA_FL = "minimax_h3_fl2v_turbo_4step_v1.0_768p_comfyui_bf16.safetensors"


# ───────────────────────── ComfyUI ─────────────────────────

def post(api, ruta, cuerpo):
    q = urllib.request.Request(api + ruta, data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(q, timeout=180))


def subir(api, ruta):
    b = "----x" + secrets.token_hex(8)
    n = os.path.basename(ruta)
    cuerpo = b"".join([
        f"--{b}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{n}"\r\n'.encode(),
        b"Content-Type: image/png\r\n\r\n", open(ruta, "rb").read(),
        f"\r\n--{b}\r\n".encode(),
        b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
        f"--{b}--\r\n".encode()])
    q = urllib.request.Request(api + "/upload/image", data=cuerpo, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    r = json.load(urllib.request.urlopen(q, timeout=300))
    return f"{r['subfolder']}/{r['name']}" if r.get("subfolder") else r["name"]


def esperar(api, pid, etq):
    t0 = time.time()
    while True:
        hi = json.load(urllib.request.urlopen(f"{api}/history/{pid}", timeout=60))
        if pid in hi:
            st = hi[pid].get("status", {})
            if st.get("status_str") == "error":
                print(f"\n  {etq} FALLO: {json.dumps(st.get('messages'))[:900]}")
                return None, time.time() - t0
            for _n, o in hi[pid].get("outputs", {}).items():
                for im in o.get("images", []):
                    return im["filename"], time.time() - t0
            return None, time.time() - t0
        print(f"    {etq} generando... {time.time()-t0:.0f}s", end="\r", flush=True)
        time.sleep(5)


def construir_workflow(api):
    """Convierte la plantilla oficial de ComfyUI a formato API (ver h3-cadena.py)."""
    import glob
    oi = json.load(urllib.request.urlopen(api + "/object_info", timeout=120))
    REL = "comfyui_workflow_templates_json/templates/video_minimax_h3_r2v.json"
    cand = []
    if os.environ.get("PLANTILLA"):
        cand = [os.environ["PLANTILLA"]]
    else:
        for base in (glob.glob("/venv/*/lib/python3.*/site-packages")
                     + glob.glob("/usr/local/lib/python3.*/site-packages")
                     + glob.glob("/opt/*/lib/python3.*/site-packages")):
            p = os.path.join(base, REL)
            if os.path.exists(p):
                cand = [p]
                break
        if not cand:
            cand = glob.glob("/**/" + REL, recursive=True)
    if not cand:
        raise SystemExit("!! no encontré la plantilla de ComfyUI")
    d = json.load(open(cand[0]))
    orig = {l[0]: (l[1], l[2]) for l in d["links"]}
    CABLE = {"MODEL", "CLIP", "VAE", "CONDITIONING", "LATENT", "IMAGE", "AUDIO",
             "NOISE", "GUIDER", "SAMPLER", "SIGMAS", "VIDEO"}
    api_wf = {}
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
        api_wf[str(n["id"])] = {"class_type": t, "inputs": ins}
    if "136" in api_wf:
        api_wf["136"]["inputs"]["ref_image_size"] = REF_SIZE
    json.dump(api_wf, open(WF, "w"), indent=1, ensure_ascii=False)
    print(f"  workflow armado ({len(api_wf)} nodos)")


def base(modelo, lora):
    wf = json.load(open(WF))
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
    wf["201"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {
        "model": [fuente, 0],
        "shift_video": float(os.environ.get("SHIFT_VIDEO", "12.0")),
        "shift_audio": float(os.environ.get("SHIFT_AUDIO", "3.0"))}}
    wf["124"]["inputs"]["model"] = ["201", 0]
    wf["126"]["inputs"]["model"] = ["201", 0]
    wf["124"]["inputs"]["steps"] = PASOS
    wf["132"]["inputs"]["value"] = SEG
    wf["136"]["inputs"].update({"width": W, "height": H})
    return wf


# ───────────────────────── una escena ─────────────────────────

def escena(api, out, e, idx):
    """Los tres clips de una escena, encadenados. Devuelve la lista de MP4."""
    print(f"\n== {e['id']} ({len(e['prompts'])} clips) ==")
    hechos = []
    for i, prompt in enumerate(e["prompts"]):
        pref = f"{e['id']}_{i+1}"
        ya = [f for f in os.listdir(out) if f.startswith(pref + "_")] if os.path.isdir(out) else []
        if ya:
            print(f"  =  clip {i+1} ya está ({ya[0]})")
            hechos.append(ya[0])
            continue

        if i == 0:
            wf = base(DIT_REF, LORA_REF)
            for k in list(wf["136"]["inputs"]):
                if k.startswith("ref_images."):
                    wf["136"]["inputs"].pop(k)
            # Las referencias entran en el orden del guion y el prompt las nombra
            # <Picture 1>, <Picture 2>, … en ese mismo orden.
            for j, ref in enumerate(e["refs"]):
                nodo = str(310 + j)
                wf[nodo] = {"class_type": "LoadImage",
                            "inputs": {"image": subir(api, f"{ASSETS}/{ref}.png")}}
                wf["136"]["inputs"][f"ref_images.ref_image_{j}"] = [nodo, 0]
            wf["136"]["inputs"]["ref_image_size"] = REF_SIZE
            print(f"  refs: {', '.join(f'<Picture {j+1}>={r}' for j, r in enumerate(e['refs']))}")
        else:
            prev = os.path.join(out, hechos[-1])
            fr = f"{RAIZ}/frame_{e['id']}_{i}.png"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-sseof", "-0.15", "-i", prev, "-update", "1", "-q:v", "1", fr],
                           check=True)
            wf = base(DIT_FL, LORA_FL)
            wf["300"] = {"class_type": "LoadImage", "inputs": {"image": subir(api, fr)}}
            wf["136"] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
                "clip": ["128", 0], "vae": ["119", 0], "prompt": ["138", 0],
                "width": W, "height": H, "length": ["131", 1], "first_frame": ["300", 0]}}

        wf["138"]["inputs"]["value"] = prompt
        wf["129"]["inputs"]["noise_seed"] = 1000 + idx * 10 + i
        wf["92"]["inputs"]["filename_prefix"] = f"video/{pref}"
        pid = post(api, "/prompt", {"prompt": wf, "client_id": "peli"})["prompt_id"]
        nombre, t = esperar(api, pid, f"clip {i+1}")
        if not nombre:
            print(f"  X  {e['id']} cortada en el clip {i+1}")
            return hechos
        print(f"  OK clip {i+1} en {t/60:.1f} min  ({nombre})")
        hechos.append(nombre)

    if len(hechos) == len(e["prompts"]):
        unir([os.path.join(out, f) for f in hechos], os.path.join(out, f"{e['id']}.mp4"))
        print(f"  == {e['id']}.mp4 listo ({SEG*len(hechos):.0f}s)")
    return hechos


def unir(partes, salida):
    lista = salida + ".txt"
    open(lista, "w").write("".join(f"file '{p}'\n" for p in partes))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                    "-safe", "0", "-i", lista, "-c", "copy", salida], check=True)
    os.remove(lista)


# ───────────────────────── CLI ─────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Genera la película escena por escena")
    ap.add_argument("--gpu", type=int, default=0, help="índice de esta GPU (0..total-1)")
    ap.add_argument("--total", type=int, default=1, help="cuántas GPUs en paralelo")
    ap.add_argument("--puerto", type=int, help="puerto de ComfyUI; default 18188+gpu")
    ap.add_argument("--salida", default="/workspace/ComfyUI/output/video")
    ap.add_argument("--montar", action="store_true", help="une las escenas y sale")
    a = ap.parse_args()

    g = json.load(open(GUION, encoding="utf-8"))
    out = a.salida

    if a.montar:
        partes = [os.path.join(out, f"{e['id']}.mp4") for e in g["escenas"]]
        faltan = [p for p in partes if not os.path.exists(p)]
        if faltan:
            print("!! faltan escenas:")
            for f in faltan:
                print("   ", os.path.basename(f))
            sys.exit(1)
        final = os.path.join(out, "PELICULA.mp4")
        unir(partes, final)
        seg = len(g["escenas"]) * 3 * SEG
        print(f"== PELICULA.mp4 · {len(partes)} escenas · {seg/60:.0f}:{seg%60:02.0f} ==")
        return

    api = f"http://127.0.0.1:{a.puerto or 18188 + a.gpu}"
    mias = [(i, e) for i, e in enumerate(g["escenas"]) if i % a.total == a.gpu]
    print(f"GPU {a.gpu}/{a.total} en {api} · {len(mias)} escenas: "
          f"{', '.join(e['id'] for _i, e in mias)}")
    print(f"modelo {DIT_REF} · {PASOS} pasos · turbo={TURBO} · refs={REF_SIZE}")

    if not os.path.exists(WF):
        construir_workflow(api)

    t0 = time.time()
    for i, e in mias:
        escena(api, out, e, i)
    t = time.time() - t0
    print(f"\nGPU {a.gpu} terminó sus {len(mias)} escenas en {t/60:.1f} min")


if __name__ == "__main__":
    main()
