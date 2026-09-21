"""Genera el video plano por plano. Se ejecuta DENTRO de la instancia alquilada.

    python runner.py --gpu 0 --total 4     # esta placa hace 1 de cada 4 planos
    python runner.py --montar              # corta todo junto y saca el SRT

Cada plano es independiente: arranca de su propio dibujo de storyboard, dura lo
que tiene que durar y se une al resto con un CORTE. Consecuencias, todas buenas:

  - los planos paralelizan de a N sin esperarse entre sí
  - uno que sale mal se rehace solo, no arrastra a nadie
  - la cámara puede moverse todo lo que quiera: el corte tapa cualquier cosa
  - sólo hace falta el modelo FL2VA; Ref2VA no se toca nunca, porque las
    referencias las resolvió el generador de imágenes al dibujar el storyboard

Formato vertical (short): sale de `ancho`/`alto` dentro de planos.json, no hay
que pasar nada. Y si un plano trae `usa`, el montaje recorta ese tramo — es
como se resuelve que H3 no pueda generar clips de menos de 5,17 s.

Variables de entorno
    PASOS=8            pasos de sampleo (8 con turbo, 20 sin)
    TURBO=1            1 usa la LoRA turbo (régimen de 4-8 pasos), 0 la apaga
    ASSETS=            carpeta de los dibujos de storyboard
    PLANOS=            lista de planos, si no /root/planos.json
    ANCHO= ALTO=       fuerzan la resolución por encima de la del JSON
    DIT_FL= DIT_REF= ENC=   modelos, si no los defaults
    SHIFT_AUDIO=3.0    cronograma de ruido del audio (la palanca del audio)
    SHIFT_VIDEO=       ídem para el video; si falta: 6 con turbo 768p, 12 sin turbo

Dos modos por plano (campo `modo` de planos.json), desde el 14/9/2026:
  fl2va   primer fotograma → video. El de siempre.
  ref2va  primer fotograma como <Picture 1> + hojas (`refs_extra`) + voz de
          referencia (`voz_ref`, <Audio 1>). Es lo que sostiene la MISMA voz de un
          personaje entre clips. Ver models/MiniMax-H3/docs-extra/RESUMEN-comfyui.md.
Cada plano puede pisar `pasos`, `turbo`, `shift_video`, `shift_audio`, `scheduler`,
`ref_image_size` y `guia0`: la muestra compara configuraciones en la misma corrida.
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
ASSETS = os.environ.get("ASSETS", "/workspace/refs/assets")
PLANOS = os.environ.get("PLANOS", RAIZ + "/planos.json")
WF = RAIZ + "/h3_fl_api.json"
METRICAS = "/workspace/ComfyUI/output/video/metricas.json"

PASOS = int(os.environ.get("PASOS", "8"))
TURBO = os.environ.get("TURBO", "1") == "1"

DIT_FL = os.environ.get("DIT_FL", "MiniMax-H3-FL2VA-Q5_K_M.gguf")
DIT_REF = os.environ.get("DIT_REF", "MiniMax-H3-Ref2VA-Q5_K_M.gguf")
ENC = os.environ.get("ENC", "qwen3vl_32b_minimax_h3_int8_convrot.safetensors")
# LoRAs turbo de lightx2v (repo lightx2v/Minimax-h3-Turbo). Hasta el 14/9 se usaba
# la de 4 pasos a 8 pasos y shift 12; la tabla oficial dice que las «768p» se
# entrenaron a shift 6/3, y la de 8 pasos es la que usa su propio estudio.
LORA = {
    "fl2va": ("minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors", 6.0),
    # Sin documentar en su tabla (existe en el repo); shift 6 por analogía con
    # las FL2VA 768p. La muestra lo compara contra el modelo completo a 20 pasos.
    "ref2va": ("minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors", 6.0),
}
LORA_FL = LORA["fl2va"][0]


# --------------------------------------------------------------- ComfyUI

def post(api, ruta, cuerpo):
    q = urllib.request.Request(api + ruta, data=json.dumps(cuerpo).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    return json.load(urllib.request.urlopen(q, timeout=180))


def subir(api, ruta):
    """Sube un archivo a input/ de ComfyUI. Sirve también para el WAV de la voz:
    /upload/image acepta cualquier archivo y LoadAudio lo lee de input/.

    Con el puerto de la placa en el nombre: las cuatro comparten input/, y en la
    muestra B (14/9) subieron voz_jack.wav a la vez con overwrite: una placa leyó
    el archivo a medio escribir y LoadAudio dio «Invalid data found»."""
    b = "----x" + secrets.token_hex(8)
    n = f"p{api.rsplit(':', 1)[-1]}_{os.path.basename(ruta)}"
    baja = n.lower()
    tipo = (b"audio/wav" if baja.endswith(".wav") else b"video/mp4" if baja.endswith(".mp4")
            else b"image/png")
    cuerpo = b"".join([
        ("--" + b + "\r\n").encode(),
        ('Content-Disposition: form-data; name="image"; filename="' + n + '"\r\n').encode(),
        b"Content-Type: " + tipo + b"\r\n\r\n", open(ruta, "rb").read(),
        ("\r\n--" + b + "\r\n").encode(),
        b'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n',
        ("--" + b + "--\r\n").encode()])
    q = urllib.request.Request(api + "/upload/image", data=cuerpo, method="POST",
                               headers={"Content-Type": "multipart/form-data; boundary=" + b})
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
        print(f"    {etq} generando... {time.time() - t0:.0f}s", end="\r", flush=True)
        time.sleep(5)


def construir_workflow(api):
    """Convierte la plantilla oficial de ComfyUI a formato API.

    Nunca inventamos nombres de nodo ni de campo: los sacamos de /object_info,
    que es la única fuente de verdad de ESTA instalación. Los nodos de H3 son
    nuevos y cambian; un grafo escrito a mano se rompe sin avisar."""
    import glob
    oi = json.load(urllib.request.urlopen(api + "/object_info", timeout=120))
    REL = "comfyui_workflow_templates_json/templates/video_minimax_h3_r2v.json"
    cand = []
    if os.environ.get("PLANTILLA"):
        cand = [os.environ["PLANTILLA"]]
    else:
        # Las rutas conocidas primero: un glob recursivo desde / se queda colgado
        # varios minutos con 100 GB de modelos en el disco y parece que murió.
        bases = (glob.glob("/venv/*/lib/python3.*/site-packages")
                 + glob.glob("/usr/local/lib/python3.*/site-packages")
                 + glob.glob("/opt/*/lib/python3.*/site-packages"))
        for base in bases:
            p = os.path.join(base, REL)
            if os.path.exists(p):
                cand = [p]
                break
        if not cand:
            # ComfyUI 0.7 partió el paquete de plantillas en varios
            # (`comfyui_workflow_templates_core`, `_media_video`, …): el nombre
            # del paquete cambia, la ruta interna `templates/<archivo>` no. Un
            # glob acotado a site-packages tarda un segundo; el de todo el disco
            # que venía después, varios minutos con la máquina cobrando.
            nombre = os.path.basename(REL)
            for base in bases:
                hits = glob.glob(os.path.join(base, "comfyui_workflow_templates*",
                                              "templates", nombre))
                if hits:
                    cand = hits[:1]
                    break
        if not cand:
            print("  !! no está en las rutas habituales, buscando en todo el disco…")
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
    sanear(api_wf, oi)
    json.dump(api_wf, open(WF, "w"), indent=1, ensure_ascii=False)
    print(f"  workflow armado ({len(api_wf)} nodos)")


def sanear(wf, oi):
    """Corrige los valores que quedaron corridos al convertir la plantilla.

    `widgets_values` es una lista posicional y **no dice a qué campo va cada
    valor**. Cuando un widget se convierte en entrada por cable, la posición
    puede seguir ocupada, y entonces todos los valores que siguen se corren un
    lugar. Pasó de verdad: `BasicScheduler` terminó con `denoise = 20` —que era
    el valor de `steps`— y ComfyUI rechazó el prompt entero con un 400, porque
    denoise tiene máximo 1.0.

    En vez de adivinar el orden, se contrasta cada valor contra el rango que
    declara `/object_info` y el que no entra vuelve a su default. Es barato y
    ataja el próximo desfase, no sólo éste.
    """
    arreglados = []
    for nid, nodo in wf.items():
        req = oi.get(nodo["class_type"], {}).get("input", {}).get("required", {})
        for campo, valor in list(nodo["inputs"].items()):
            cfg = req.get(campo)
            # Los cables son listas [nodo, salida]: ésos no se tocan.
            if not cfg or isinstance(valor, list) or len(cfg) < 2 or not isinstance(cfg[1], dict):
                continue
            tipo, reglas = cfg[0], cfg[1]
            malo = False
            if tipo in ("INT", "FLOAT") and isinstance(valor, (int, float)):
                if "max" in reglas and valor > reglas["max"]:
                    malo = True
                if "min" in reglas and valor < reglas["min"]:
                    malo = True
            elif isinstance(tipo, list) and valor not in tipo:
                malo = True
            if malo and "default" in reglas:
                nodo["inputs"][campo] = reglas["default"]
                arreglados.append(f"{nid}.{campo}: {valor} -> {reglas['default']}")
    if arreglados:
        print("  valores corridos, corregidos contra object_info:")
        for a in arreglados:
            print("    " + a)


def config_plano(p):
    """(modo, pasos, turbo, shift_video, shift_audio, scheduler) de un plano: lo
    que trae el plano pisa las variables de entorno, que pisan los defaults."""
    modo = p.get("modo", "fl2va")
    turbo = bool(p["turbo"]) if p.get("turbo") is not None else TURBO
    pasos = int(p.get("pasos") or (PASOS if turbo else int(os.environ.get("PASOS_SIN_TURBO", "20"))))
    sv = p.get("shift_video") or os.environ.get("SHIFT_VIDEO")
    sv = float(sv) if sv else (LORA[modo][1] if turbo else 12.0)
    sa = float(p.get("shift_audio") or os.environ.get("SHIFT_AUDIO", "3.0"))
    # La plantilla oficial Ref2VA: «beta o normal suele rendir mejor que simple
    # con muchas referencias».
    sched = p.get("scheduler") or ("beta" if modo == "ref2va" and not turbo else "simple")
    return modo, pasos, turbo, sv, sa, sched


def base(modo="fl2va", pasos=None, turbo=None, shift_video=None, shift_audio=3.0,
         scheduler="simple"):
    turbo = TURBO if turbo is None else turbo
    pasos = PASOS if pasos is None else pasos
    dit = DIT_REF if modo == "ref2va" else DIT_FL
    wf = json.load(open(WF))
    # Los .gguf necesitan otro cargador, el de ComfyUI-GGUF: mismo campo, otra clase.
    wf["127"]["class_type"] = "UnetLoaderGGUF" if dit.endswith(".gguf") else "UNETLoader"
    wf["127"]["inputs"] = {"unet_name": dit}
    if not dit.endswith(".gguf"):
        wf["127"]["inputs"]["weight_dtype"] = "default"
    wf["128"]["inputs"]["clip_name"] = ENC
    wf["128"]["inputs"]["device"] = "default"
    fuente = "127"
    if turbo:
        wf["200"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["127", 0], "lora_name": LORA[modo][0], "strength_model": 1.0}}
        fuente = "200"
    # Video y audio tienen cronogramas de ruido separados en H3.
    wf["201"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {
        "model": [fuente, 0],
        "shift_video": float(shift_video if shift_video is not None
                             else (LORA[modo][1] if turbo else 12.0)),
        "shift_audio": float(shift_audio)}}
    wf["124"]["inputs"]["model"] = ["201", 0]
    wf["126"]["inputs"]["model"] = ["201", 0]
    wf["124"]["inputs"]["steps"] = pasos
    wf["124"]["inputs"]["scheduler"] = scheduler
    return wf


# --------------------------------------------------------------- un plano

def ultimo_frame(mp4, destino):
    """Saca el último fotograma de un clip, para encadenar el plano siguiente.

    `-sseof -0.1` busca desde el final: es mucho más rápido que decodificar el
    clip entero, y a 24 fps toma el último cuadro o el anterior, que sirve igual.
    """
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-sseof", "-0.1", "-i", mp4, "-update", "1",
                        "-frames:v", "1", destino],
                       capture_output=True, text=True)
    if r.returncode or not os.path.exists(destino):
        print(f"    !! no pude sacar el último frame de {os.path.basename(mp4)}: "
              f"{r.stderr[-200:]}")
        return None
    return destino


def plano(api, out, p, idx, w, h):
    """Un plano, de su primer fotograma a MP4.

    El fotograma sale de su dibujo de storyboard, o —si el plano encadena— del
    **último fotograma del clip anterior**. Encadenar da continuidad de
    movimiento real, que es lo que una secuencia de acción necesita: sin eso
    cada corte reinicia la inercia. El precio es que la cadena va en serie y que
    cada eslabón se aleja una generación del dibujo original.
    """
    ya = [f for f in os.listdir(out) if f.startswith(p["id"] + "_")] if os.path.isdir(out) else []
    if ya:
        print(f"  =  {p['id']} ya está ({ya[0]})")
        return ya[0], None

    if p.get("sigue_de"):
        previos = sorted(f for f in os.listdir(out)
                         if f.startswith(p["sigue_de"] + "_")) if os.path.isdir(out) else []
        if not previos:
            print(f"  X  {p['id']}: encadena de {p['sigue_de']}, que todavía no existe")
            return None, None
        dibujo = os.path.join(out, f"_enlace_{p['id']}.png")
        if not ultimo_frame(os.path.join(out, previos[0]), dibujo):
            return None, None
        print(f"     {p['id']} arranca en el último frame de {p['sigue_de']}")
    elif p.get("first_frame"):
        dibujo = os.path.join(ASSETS, os.path.basename(p["first_frame"]))
        if not os.path.exists(dibujo):
            print(f"  X  {p['id']}: falta el dibujo {os.path.basename(dibujo)}")
            return None, None
    else:
        # Sin primer fotograma: sólo vale en ref2va con un video de referencia
        # (edición de un video existente, 17/9/2026).
        dibujo = None

    modo, pasos, turbo, sv, sa, sched = config_plano(p)
    if dibujo is None and not (modo == "ref2va" and p.get("ref_video")):
        print(f"  X  {p['id']}: no tiene primer fotograma ni video de referencia")
        return None, None
    wf = base(modo, pasos, turbo, sv, sa, sched)
    if dibujo:
        wf["300"] = {"class_type": "LoadImage", "inputs": {"image": subir(api, dibujo)}}
    if modo == "ref2va":
        # Nombres EXACTOS de las entradas en formato API: clave plana con punto e
        # índice desde 0. Un nombre mal escrito ComfyUI lo DESCARTA SIN ERROR y
        # genera como si no hubiera referencias (issue #15667). ref_image_0 es
        # <Picture 1> en el prompt, ref_audio_0 es <Audio 1>. Orden de las
        # etiquetas: imágenes → videos (su audio justo antes) → audios sueltos.
        entradas = {
            "clip": ["128", 0], "vae": ["119", 0],
            # Sin audio_vae la voz de referencia sólo pone la etiqueta en el texto
            # y no condiciona NADA (código del nodo).
            "audio_vae": ["120", 0],
            "prompt": ["138", 0], "width": w, "height": h, "length": ["131", 1],
            "ref_image_size": p.get("ref_image_size", "match")}
        k = 0
        if dibujo:
            entradas["ref_images.ref_image_0"] = ["300", 0]
            k = 1
        for extra in (p.get("refs_extra") or []):
            ruta = os.path.join(ASSETS, os.path.basename(extra))
            if not os.path.exists(ruta):
                print(f"  X  {p['id']}: falta la referencia {os.path.basename(extra)}")
                return None, None
            nid = str(300 + k)
            wf[nid] = {"class_type": "LoadImage", "inputs": {"image": subir(api, ruta)}}
            entradas[f"ref_images.ref_image_{k}"] = [nid, 0]
            k += 1
        if p.get("ref_video"):
            # Video de referencia (<Video 1>): LoadVideo + GetVideoComponents del
            # núcleo de ComfyUI (la plantilla oficial del ControlNet los usa así).
            # El nodo H3 lo recorta a ≤ length fotogramas y a la grilla 17k+5; ya
            # viene a 24 fps y al lienzo desde la app. Su pista de audio entra
            # como <Audio 1> sólo si se pide (ref_video_audio).
            ruta = os.path.join(ASSETS, os.path.basename(p["ref_video"]))
            if not os.path.exists(ruta):
                print(f"  X  {p['id']}: falta el video {os.path.basename(ruta)}")
                return None, None
            wf["330"] = {"class_type": "LoadVideo", "inputs": {"file": subir(api, ruta)}}
            wf["331"] = {"class_type": "GetVideoComponents", "inputs": {"video": ["330", 0]}}
            entradas["ref_videos.ref_video_0"] = ["331", 0]
            if p.get("ref_video_audio"):
                entradas["ref_video_audios.ref_video_audio_0"] = ["331", 1]
        vozs = p.get("voz_ref") or []
        if isinstance(vozs, str):
            vozs = [vozs]
        for j, voz in enumerate(vozs[:3]):     # el modelo acepta hasta 3 audios
            ruta = os.path.join(ASSETS, os.path.basename(voz))
            if not os.path.exists(ruta):
                print(f"  X  {p['id']}: falta la voz {os.path.basename(voz)}")
                return None, None
            nid = str(310 + j)
            wf[nid] = {"class_type": "LoadAudio", "inputs": {"audio": subir(api, ruta)}}
            entradas[f"ref_audios.ref_audio_{j}"] = [nid, 0]
        wf["136"] = {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": entradas}
        if p.get("guia0") and dibujo:
            # Ancla dura: la misma imagen como fotograma 0 del eje del video (el
            # DiT acepta keyframes y referencias juntos). Sin documentar para
            # ref2va en el cuadro 0: por eso es opcional y se prueba A/B.
            wf["320"] = {"class_type": "MiniMaxH3AddGuide", "inputs": {
                "positive": ["136", 0], "latent": ["136", 1], "vae": ["119", 0],
                "image": ["300", 0], "frame_idx": 0}}
            wf["126"]["inputs"]["conditioning"] = ["320", 0]
    else:
        # FL2VA: el nodo de referencias de la plantilla se reemplaza entero por
        # el de primer fotograma.
        wf["136"] = {"class_type": "MiniMaxH3ImageToVideo", "inputs": {
            "clip": ["128", 0], "vae": ["119", 0], "prompt": ["138", 0],
            "width": w, "height": h, "length": ["131", 1], "first_frame": ["300", 0]}}
    # 132 son segundos y 131 los redondea HACIA ARRIBA a la grilla de 17k+5
    # fotogramas. "segundos" ya viene exactamente sobre la grilla, así que se le
    # resta una pizca para que el redondeo caiga justo ahí y no salte al escalón
    # siguiente, que son 0,7 s de más y descoloca el SRT.
    wf["132"]["inputs"]["value"] = round(p["segundos"] - 0.01, 3)
    wf["138"]["inputs"]["value"] = p["prompt"]
    wf["129"]["inputs"]["noise_seed"] = p.get("seed", 1000 + idx)
    wf["92"]["inputs"]["filename_prefix"] = "video/" + p["id"]

    etq = (f"{p['id']} {p.get('tipo', '')} {p['segundos']:.1f}s {modo} {pasos}p"
           f"{' turbo' if turbo else ''}")
    # Hasta dos intentos, y entre uno y otro se libera la VRAM. El out-of-memory
    # es el fallo más común —el GGUF ocupa 23,9 GB de 32 y la memoria se
    # fragmenta— y casi siempre pasa a la segunda con el modelo recién cargado.
    # Reintentar acá importa más de lo que parece: si el que falla es el primero
    # de una cadena, se lleva puestos a todos los que encadenan de él, y la
    # placa se queda parada mientras el reloj corre.
    for intento in (1, 2):
        pid = post(api, "/prompt", {"prompt": wf, "client_id": "planos"})["prompt_id"]
        nombre, t = esperar(api, pid, etq)
        if nombre and es_ruido(os.path.join(out, nombre)):
            # Una placa defectuosa devuelve un clip de ruido puro con el mismo
            # tiempo y tamaño que uno bueno: el 31/8 la placa 1 de un host hizo
            # ONCE así y nadie lo vio hasta el máster, con la instancia ya
            # destruida. No es la VRAM ni el prompt: es el hardware. Se borra el
            # clip, se avisa y esta placa deja de trabajar (código 3) para que el
            # rescate lo haga otra.
            print(f"\n  !! {p['id']}: la placa devuelve RUIDO. Borro el clip y paro esta "
                  f"placa: es hardware, no vale reintentar acá.")
            os.remove(os.path.join(out, nombre))
            sys.exit(3)
        if nombre:
            if intento > 1:
                print(f"     (salió en el intento {intento})")
            print(f"  OK {etq} en {t / 60:.1f} min  ({nombre})")
            return nombre, {"id": p["id"], "segundos": p["segundos"],
                            "minutos": round(t / 60, 2), "pasos": pasos,
                            "turbo": turbo, "modo": modo, "shift_video": sv,
                            "scheduler": sched, "guia0": bool(p.get("guia0")),
                            "refs": (1 if p.get("first_frame") or p.get("sigue_de") else 0) + len(p.get("refs_extra") or []),
                            "video_ref": bool(p.get("ref_video")),
                            "voz": bool(p.get("voz_ref")), "wh": [w, h],
                            "intentos": intento}
        if intento == 1:
            print(f"     {p['id']} falló; libero la VRAM y reintento")
            liberar_vram(api)
    return None, None


def es_ruido(mp4, umbral=22000):
    """¿El clip es ruido puro? Heurística barata y medida: un fotograma de ruido
    no comprime. A 192 px de ancho y calidad JPEG 5, los 11 clips de ruido del
    31/8 pesaron 25,0-25,6 KB y los 30 buenos entre 4 y 15 KB — salvo una
    textura extrema (ladrillo + carbón + nieve al sol) que dio 21,0 y era
    buena: por eso 22 y no 20. Si ffmpeg falla, se asume bueno: mejor un falso
    negativo que parar una placa sana."""
    import tempfile
    try:
        dst = os.path.join(tempfile.gettempdir(), "_ruido_" + os.path.basename(mp4) + ".jpg")
        r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", "2.5", "-i", mp4, "-frames:v", "1",
                            "-vf", "scale=192:-1", "-q:v", "5", dst],
                           capture_output=True, text=True, timeout=60)
        if r.returncode or not os.path.exists(dst):
            return False
        tam = os.path.getsize(dst)
        os.remove(dst)
        return tam > umbral
    except Exception:
        return False


def liberar_vram(api):
    """Descarga los modelos de la GPU. Es lo que arregla el out-of-memory."""
    for ruta in ("/free", "/interrupt"):
        try:
            post(api, ruta, {"unload_models": True, "free_memory": True})
        except Exception:
            pass
    time.sleep(12)


def costo(p):
    """Lo que pesa un plano para repartir: segundos × pasos / 8. Por segundos a
    secas, la muestra A del 14/9 le dio a una placa el clip de 20 pasos (8,8 min)
    y otro más, y a otra tres de turbo: una terminó a los 8,7 min y la otra a
    los 12,4."""
    _modo, pasos, _turbo, _sv, _sa, _sched = config_plano(p)
    return p["segundos"] * pasos / 8


def reparto(todos, gpu, total):
    """Qué planos le tocan a esta placa. Devuelve `[(indice, plano), ...]`.

    **Reparte cadenas, no planos.** Un plano encadenado necesita el clip
    anterior ya terminado, así que toda la cadena tiene que caer en la misma
    placa y en orden; si se repartieran por índice, una placa esperaría un clip
    que está generando otra y se trabarían las dos.

    Y se reparten por CARGA, no por índice: una cadena de tres clips vale por
    tres, así que repartir `n % total` deja una placa con quince minutos de más
    mientras otra termina y se queda mirando. Se asigna cada cadena —de la más
    larga a la más corta— a la placa que menos segundos acumule.
    """
    cadenas, de_quien = [], {}
    for i, p in enumerate(todos):
        raiz = p.get("sigue_de")
        if raiz and raiz in de_quien:
            cadenas[de_quien[raiz]].append((i, p))
            de_quien[p["id"]] = de_quien[raiz]
        else:
            de_quien[p["id"]] = len(cadenas)
            cadenas.append([(i, p)])

    carga = [0.0] * total
    asignadas = [[] for _ in range(total)]
    # De la más pesada a la más liviana: es lo que hace que el greedy funcione.
    orden = sorted(range(len(cadenas)),
                   key=lambda n: -sum(costo(p) for _i, p in cadenas[n]))
    for n in orden:
        seg = sum(costo(p) for _i, p in cadenas[n])
        d = carga.index(min(carga))
        asignadas[d] += cadenas[n]
        carga[d] += seg
    # Los eslabones encadenados van PRIMERO (trampa 11): el cabeza de cadena es
    # el plano de mayor riesgo de la tanda. Si falla al principio, la placa
    # sigue con los sueltos mientras tanto y la repasada del final lo rescata;
    # si fallara al final, la placa se quedaría parada cobrando, que es
    # exactamente lo que pasó en CONTRAMANO (28 min de una 5090 sin trabajo).
    # Dentro de cada grupo se respeta el orden de aparición, que es lo que una
    # cadena necesita para generarse de principio a fin.
    en_cadena = {i for c in cadenas if len(c) > 1 for i, _p in c}
    # Y dentro de cada placa, agrupados por modo: FL2VA y Ref2VA son DiT
    # distintos de 24 GB, y cambiar de uno a otro entre clips obliga a descargar
    # uno y cargar el otro cada vez.
    return sorted(asignadas[gpu], key=lambda x: (x[0] not in en_cadena,
                                                 x[1].get("modo", "fl2va"), x[0]))


def anotar_metrica(m):
    """El tiempo real de cada plano con su duración al lado. Es lo que permite
    reajustar la curva de costo con 42 puntos entre 5 y 15 s en vez de con los
    dos medidos, que son de 10 y 15."""
    try:
        os.makedirs(os.path.dirname(METRICAS), exist_ok=True)
        datos = json.load(open(METRICAS)) if os.path.exists(METRICAS) else []
        datos = [x for x in datos if x["id"] != m["id"]] + [m]
        json.dump(sorted(datos, key=lambda x: x["id"]), open(METRICAS, "w"), indent=1)
    except Exception as e:      # nunca frenar la generación por el archivo de métricas
        print(f"    (no pude anotar la métrica: {e})")


# ---------------------------------------------------------------- montaje

def _ffmpeg(*args):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("!! ffmpeg: " + r.stderr[-800:])


def montar(out, planos, nombre="VIDEO"):
    """Une los planos en orden.

    Si algún plano trae `usa`, cada clip se recorta y RECODIFICA por separado y
    recién después se concatena: cortar con `-c copy` mueve el corte al keyframe
    más cercano, que puede estar a un segundo, y eso arruina un ritmo pensado al
    décimo. Sin `usa` se concatena copiando el video, que es instantáneo.
    """
    partes, recorta = [], any(p.get("usa") for p in planos)
    for p in planos:
        hay = sorted(f for f in os.listdir(out) if f.startswith(p["id"] + "_"))
        if not hay:
            print("!! falta " + p["id"])
            return None
        partes.append(os.path.join(out, hay[0]))

    if recorta:
        tmp = os.path.join(out, "_recortes")
        os.makedirs(tmp, exist_ok=True)
        nuevas = []
        for p, ruta in zip(planos, partes):
            ini, fin = p.get("usa") or [0.0, p["segundos"]]
            dst = os.path.join(tmp, p["id"] + ".mp4")
            # -ss antes de -i busca rápido; -t después fija la duración exacta.
            _ffmpeg("-ss", str(ini), "-i", ruta, "-t", str(fin - ini),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-ar", "48000", "-ac", "2", dst)
            nuevas.append(dst)
        partes = nuevas

    lista = os.path.join(out, "orden.txt")
    with open(lista, "w") as f:
        for x in partes:
            f.write("file '" + x + "'\n")
    final = os.path.join(out, nombre + ".mp4")
    if recorta:
        _ffmpeg("-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", final)
    else:
        # El audio se recodifica a una sola pista continua: es lo que evita el
        # chasquido en cada corte al concatenar decenas de pistas sueltas.
        _ffmpeg("-f", "concat", "-safe", "0", "-i", lista,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", final)
    os.remove(lista)
    return final


def srt(planos, ruta):
    """Subtítulos a partir de las duraciones. No hace falta Whisper: como
    nosotros elegimos cuánto dura cada plano, el tiempo de cada línea es una
    suma."""
    def t(s):
        h, r = divmod(s, 3600)
        m, r = divmod(r, 60)
        return "%02d:%02d:%02d,%03d" % (h, m, int(r), round(r % 1 * 1000))

    lineas, t0, n = [], 0.0, 0
    for p in planos:
        dur = (p["usa"][1] - p["usa"][0]) if p.get("usa") else p["segundos"]
        if p.get("dialogo"):
            n += 1
            lineas.append("%d\n%s --> %s\n%s\n"
                          % (n, t(t0 + 0.4), t(t0 + dur - 0.3), p["dialogo"]))
        t0 += dur
    # Con BOM: sin él libass lo lee como Latin-1 y destroza los acentos.
    with open(ruta, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lineas))
    return n


# -------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="Genera el video plano por plano")
    ap.add_argument("--gpu", type=int, default=0, help="índice de esta placa (0..total-1)")
    ap.add_argument("--total", type=int, default=1, help="cuántas placas en paralelo")
    ap.add_argument("--puerto", type=int, help="puerto de ComfyUI; default 18188+gpu")
    ap.add_argument("--salida", default="/workspace/ComfyUI/output/video")
    ap.add_argument("--montar", action="store_true", help="corta todo junto y sale")
    ap.add_argument("--nombre", default=None, help="nombre del archivo final")
    a = ap.parse_args()

    g = json.load(open(PLANOS, encoding="utf-8"))
    todos, out = g["planos"], a.salida
    w = int(os.environ.get("ANCHO") or g.get("ancho", 1344))
    h = int(os.environ.get("ALTO") or g.get("alto", 768))
    # Por slug y no por título: sin tildes ni espacios, que viajan mal entre
    # Windows, Linux y el navegador al bajar el archivo.
    nombre = a.nombre or g.get("slug") or "VIDEO"

    if a.montar:
        final = montar(out, todos, nombre)
        if not final:
            sys.exit(1)
        n = srt(todos, os.path.join(out, nombre + ".srt"))
        seg = sum((p["usa"][1] - p["usa"][0]) if p.get("usa") else p["segundos"]
                  for p in todos)
        print(f"== {os.path.basename(final)} · {len(todos)} planos · "
              f"{int(seg // 60)}:{seg % 60:04.1f} · {n} subtítulos ==")
        return

    api = "http://127.0.0.1:%d" % (a.puerto or 18188 + a.gpu)
    mias = reparto(todos, a.gpu, a.total)
    print(f"GPU {a.gpu}/{a.total} en {api} · {len(mias)} planos · "
          f"{sum(p['segundos'] for _i, p in mias):.0f}s de video")
    modos = sorted({p.get("modo", "fl2va") for _i, p in mias})
    print(f"modelos {DIT_FL} / {DIT_REF} · modos {modos} · {PASOS} pasos por defecto · "
          f"turbo={TURBO} · {w}x{h}")

    if not os.path.exists(WF):
        construir_workflow(api)

    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    # Hasta tres pasadas sobre lo que falle. La primera es la corrida normal;
    # las otras son la trampa 11 resuelta: antes, una cadena rota había que
    # relanzarla A MANO en cuanto se veía el error, y mientras tanto la placa
    # cobraba sin trabajar. Ahora el propio runner libera la VRAM y repasa: el
    # cabeza de cadena reintenta primero y sus eslabones —que fallaron rápido
    # con "todavía no existe"— salen detrás, en orden. `plano()` saltea los que
    # ya están, así que repasar lo terminado no cuesta nada.
    # Cola compartida (14/9, muestra A: la placa 3 terminó a los 8,7 min y quedó
    # mirando mientras la 0 seguía hasta los 12,4). Con COLA definida —lanzar.sh
    # la pone con la hora de arranque— cada placa hace primero lo suyo y después
    # recorre lo de las demás; antes de generar, reclama la cadena con un mkdir,
    # que es atómico: si otra ya la tomó, la saltea. El reparto sigue decidiendo
    # quién empieza por dónde; la cola sólo evita que una placa se quede quieta.
    # Sin COLA (rescate.sh, a mano) cada runner hace sólo su reparto, como antes.
    cola = os.environ.get("COLA")
    if cola:
        cabeza = {}
        for p in todos:
            cabeza[p["id"]] = cabeza.get(p.get("sigue_de"), p["id"]) if p.get("sigue_de") else p["id"]
        dir_cola = os.path.join(out, ".cola-" + cola)
        os.makedirs(dir_cola, exist_ok=True)
        propias = {i for i, _p in mias}
        ajenas = [x for g2 in range(1, a.total)
                  for x in reparto(todos, (a.gpu + g2) % a.total, a.total)
                  if x[0] not in propias]
        tomadas = set()

        def reclamar(p):
            c = cabeza[p["id"]]
            if c in tomadas:
                return True
            try:
                os.mkdir(os.path.join(dir_cola, c))
            except FileExistsError:
                return False
            tomadas.add(c)
            return True

        recorrido = list(mias) + ajenas
    else:
        recorrido, reclamar = list(mias), (lambda p: True)

    hechos = 0
    pendientes, fallados = recorrido, []
    for pasada in (1, 2, 3):
        fallados = []
        for i, p in pendientes:
            if pasada == 1 and not reclamar(p):
                continue
            hechos += pasada == 1
            nombre_mp4, metrica = plano(api, out, p, i, w, h)
            if not nombre_mp4:
                fallados.append((i, p))
            elif metrica:
                anotar_metrica(metrica)
        if not fallados:
            break
        if pasada < 3:
            print(f"\n  pasada {pasada}: fallaron "
                  + " ".join(p["id"] for _i, p in fallados)
                  + " — libero la VRAM y repaso")
            liberar_vram(api)
            pendientes = fallados
    t = time.time() - t0
    print(f"\nGPU {a.gpu} terminó {hechos - len(fallados)}/{hechos} planos "
          f"en {t / 60:.1f} min")
    if fallados:
        print("  fallaron tras 3 pasadas: " + " ".join(p["id"] for _i, p in fallados))
        print(f"  para rehacerlos: python runner.py --gpu {a.gpu} --total {a.total}")
        sys.exit(2)


if __name__ == "__main__":
    main()
