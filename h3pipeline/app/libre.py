"""EL MODO LIBRE: un chat con MiniMax H3, sin estructura ni proyecto.

Cada turno es: un prompt → una imagen (nano banana, o una que subís) → un clip
de H3 generado en la máquina compartida. Sirve para probar una idea, un estilo
o un movimiento antes de escribir un guion, como el playground de Seedance
pero con nuestro modelo y nuestra máquina.

Todo vive en `mis-videos/_libre/`: `turnos.json`, `assets/L<id>.png`,
`clips/L<id>_00001_.mp4`. En la máquina cada turno es un planos.json de un
solo plano que corre con `GPUS=1 bash lanzar.sh`; el id único evita choques
con lo que haya en /workspace/ComfyUI/output/video.
"""
from __future__ import annotations

import base64
import json
import time
import zipfile
from pathlib import Path

from .. import config, frames, grilla, prompts, vast
from . import maquina

DIR = maquina.MIS / "_libre"
TURNOS = DIR / "turnos.json"
RES = {"16:9": (1344, 768), "9:16": (768, 1344)}


def _leer() -> list[dict]:
    if not TURNOS.exists():
        return []
    try:
        return json.loads(TURNOS.read_text(encoding="utf-8"))
    except Exception:
        return []


def _escribir(ts: list[dict]) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    TURNOS.write_text(json.dumps(ts, ensure_ascii=False, indent=2), encoding="utf-8")


def turnos() -> list[dict]:
    return sorted(_leer(), key=lambda t: t["creado"], reverse=True)


def _turno(tid: str) -> dict:
    for t in _leer():
        if t["id"] == tid:
            return t
    raise KeyError(tid)


def _guardar(t: dict) -> dict:
    ts = _leer()
    ts = [x for x in ts if x["id"] != t["id"]] + [t]
    _escribir(ts)
    return t


# ───────────────────────────────────────────────────────────── la imagen

def imagen(prompt: str, aspecto: str = "16:9", b64: str | None = None, estilo: str = "",
           motor: str = "nanobanana", ajuste: str = "encajar") -> dict:
    """Crea el turno con su primer fotograma: subido (`b64`) o generado con
    nano banana Flash a partir del prompt (+ estilo opcional)."""
    aspecto = aspecto if aspecto in RES else "16:9"
    tid = "L" + time.strftime("%m%d%H%M%S")
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "assets").mkdir(exist_ok=True)
    crudo = DIR / "assets" / f"{tid}-crudo.png"
    if b64:
        if "," in b64[:64]:
            b64 = b64.split(",", 1)[1]
        crudo.write_bytes(base64.b64decode(b64))
        origen = "subida"
    else:
        texto = " ".join(x for x in (estilo.strip(), prompt.strip(), prompts.FORMATO[aspecto], prompts.FRAME_LIMPIO) if x)
        if motor == "openai":
            crudo.write_bytes(frames.generar_openai(texto, [], config.leer_env("OPENAI_API_KEY"), aspecto, log=lambda *_: None))
            origen = "OpenAI"
        else:
            try:
                crudo.write_bytes(frames.generar(texto, [], config.leer_env("nanobanana"), aspecto, log=lambda *_: None))
                origen = "nano banana"
            except frames.SinCredito:
                # Sin créditos en Gemini: OpenAI como respaldo (pierde ~14 % del ancho
                # al normalizar; el sujeto va centrado).
                crudo.write_bytes(frames.generar_openai(texto, [], config.leer_env("OPENAI_API_KEY"), aspecto, log=lambda *_: None))
                origen = "OpenAI (sin créditos en nano banana)"
    nota = ""
    if b64:
        # Una imagen subida no se recorta: se elige el cuadro según su
        # orientación y se ENCAJA entera sobre un fondo desenfocado de sí misma.
        from PIL import Image
        with Image.open(crudo) as im:
            iw, ih = im.size
        aspecto_img = "9:16" if ih > iw * 1.1 else "16:9"
        if aspecto_img != aspecto:
            nota = f"la imagen es {'vertical' if aspecto_img == '9:16' else 'horizontal'}: se usó {aspecto_img}"
            aspecto = aspecto_img
        w, h = RES[aspecto]
        final = DIR / "assets" / f"{tid}.png"
        if ajuste == "recortar":
            frames.normalizar(crudo, final, w, h)
        else:
            _encajar(crudo, final, w, h)
            if abs(iw / ih - w / h) > 0.05:
                nota = (nota + " · " if nota else "") + "encajada entera con fondo desenfocado (sin recorte)"
    else:
        w, h = RES[aspecto]
        final = DIR / "assets" / f"{tid}.png"
        frames.normalizar(crudo, final, w, h)
    crudo.unlink(missing_ok=True)
    t = {"id": tid, "creado": time.time(), "prompt_imagen": prompt, "estilo": estilo, "aspecto": aspecto,
         "imagen": f"assets/{tid}.png", "origen_imagen": origen, "estado": "imagen",
         "prompt_video": None, "segundos": None, "clip": None, "nota": nota}
    return _guardar(t)


def duplicar(tid: str) -> dict:
    """Un turno nuevo con la MISMA imagen de uno terminado, y su prompt de
    video como sugerencia: para iterar un prompt sin volver a subir la foto."""
    import shutil
    v = _turno(tid)
    nid = "L" + time.strftime("%m%d%H%M%S")
    shutil.copyfile(DIR / v["imagen"], DIR / "assets" / f"{nid}.png")
    t = {"id": nid, "creado": time.time(), "prompt_imagen": v.get("prompt_imagen"), "estilo": v.get("estilo", ""),
         "aspecto": v["aspecto"], "imagen": f"assets/{nid}.png", "origen_imagen": f"misma imagen que {tid}",
         "estado": "imagen", "prompt_video": None, "segundos": None, "clip": None, "nota": "",
         "sugerido": v.get("prompt_video"), "segundos_sugeridos": v.get("segundos")}
    return _guardar(t)


def _encajar(origen: Path, destino: Path, w: int, h: int) -> None:
    """La imagen entera dentro de w×h: fondo = la misma imagen agrandada hasta
    cubrir, desenfocada y oscurecida; adelante, la imagen a tamaño completo."""
    from PIL import Image, ImageEnhance, ImageFilter
    im = Image.open(origen).convert("RGB")
    iw, ih = im.size
    # fondo que cubre
    esc = max(w / iw, h / ih)
    fondo = im.resize((max(w, int(iw * esc)), max(h, int(ih * esc))), Image.LANCZOS)
    fx, fy = (fondo.width - w) // 2, (fondo.height - h) // 2
    fondo = fondo.crop((fx, fy, fx + w, fy + h)).filter(ImageFilter.GaussianBlur(radius=max(w, h) // 30))
    fondo = ImageEnhance.Brightness(fondo).enhance(0.55)
    # frente que entra entero
    esc = min(w / iw, h / ih)
    frente = im.resize((int(iw * esc), int(ih * esc)), Image.LANCZOS)
    fondo.paste(frente, ((w - frente.width) // 2, (h - frente.height) // 2))
    fondo.save(destino, "PNG")


# ───────────────────────────────────────────────────────────── el video

def _zip_turno(t: dict, prompt_video: str, segundos: float, seed: int | None) -> Path:
    length, real = grilla.encajar(float(segundos))
    w, h = RES[t["aspecto"]]
    plano = {"id": t["id"], "escena": "LIBRE", "tramo": None, "tipo": "PM", "loc": None, "personajes": [],
             "length": length, "segundos": round(real, 3), "funcion": "turno libre",
             "first_frame": f"assets/{t['id']}.png", "clip_de": None, "sigue_de": None,
             "prompt": prompt_video, "dialogo": None}
    if seed is not None:
        plano["seed"] = int(seed)
    doc = {"titulo": "LIBRE", "slug": "_libre", "formato": "largo" if t["aspecto"] == "16:9" else "short",
           "fps": grilla.FPS, "ancho": w, "alto": h, "estructura": "libre", "planos": [plano]}
    (DIR / "zips").mkdir(exist_ok=True)
    z = DIR / "zips" / f"{t['id']}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("planos.json", json.dumps(doc, ensure_ascii=False, indent=2))
        zf.write(DIR / t["imagen"], f"assets/{t['id']}.png")
        for n in ("setup.sh", "lanzar.sh", "rescate.sh", "runner.py"):
            zf.write(maquina.REMOTO / n, n)
    return z


def video(tid: str, prompt_video: str, segundos: float = grilla.MINIMO, seed: int | None = None,
          log=print) -> dict:
    """Manda el turno a la máquina lista y lo deja generando."""
    t = _turno(tid)
    m = maquina.sincronizar()
    if m.get("fase") != "lista" or not m.get("instancia"):
        raise RuntimeError(f"la máquina no está lista (fase {m.get('fase')}); encendela desde el inicio")
    inst = vast.instancia(int(m["instancia"]))
    z = _zip_turno(t, prompt_video, segundos, seed)
    vast.subir(inst, z)
    if float(segundos) > 6.0:
        # Un clip largo sólo entra en 32 GB con la memoria LIMPIA: el 17/8 los
        # de 15 s salieron en 5090 como primer trabajo de un proceso fresco, y
        # los OOM de 6,6-7,3 s fueron siempre el tercer clip de una placa. Así
        # que antes de un clip largo se reinicia el ComfyUI de la placa 0
        # (lanzar.sh espera a que vuelva).
        vast.ejecutar(inst, "supervisorctl restart comfyui >/dev/null 2>&1 || true", timeout=60)
        log("ComfyUI reiniciado para arrancar con la VRAM limpia")
    vast.ejecutar(inst, f"export PATH=/venv/main/bin:$PATH && cd /workspace/refs && unzip -oq {z.name} && "
                        f"sed -i 's/\\r$//' *.sh *.py && cp planos.json /root/planos.json", timeout=180)
    # Log propio: si escribiera sobre corrida.log borraría la marca «Listo. Ahora»
    # de la instalación, y la app dejaría de ver la máquina como lista (17/9).
    vast.lanzar(inst, "export PATH=/venv/main/bin:$PATH && cd /workspace/refs && PASOS=8 GPUS=1 bash lanzar.sh",
                log="/root/libre.log")
    maquina.escribir(proyecto="_libre", generando_desde=time.time())
    t.update(prompt_video=prompt_video, segundos=float(segundos), estado="generando", lanzado=time.time())
    return _guardar(t)


def refrescar() -> list[dict]:
    """Los turnos en `generando`: si el clip ya está en la máquina, lo baja."""
    ts = _leer()
    gen = [t for t in ts if t["estado"] == "generando"]
    if not gen:
        return turnos()
    m = maquina.leer()
    if not m.get("instancia") or m.get("fase") in ("apagada", "fallo"):
        for t in gen:
            t.update(estado="error", nota="la máquina se apagó antes de terminar")
        _escribir(ts)
        return turnos()
    try:
        inst = vast.instancia(int(m["instancia"]))
        arch = vast.archivos_remotos(inst)
    except Exception:
        return turnos()
    (DIR / "clips").mkdir(exist_ok=True)
    ultimo = _ultima_linea(inst)
    for t in gen:
        mios = [a for a in arch if a.startswith(t["id"] + "_") and a.endswith(".mp4")]
        if mios:
            try:
                vast.bajar(inst, mios[:1], DIR / "clips", log=lambda *_: None)
                t.update(estado="listo", clip=f"clips/{mios[0]}", terminado=time.time(), progreso=None)
            except Exception as e:
                t.update(nota=f"bajando… ({e})")
        elif time.time() - t.get("lanzado", 0) > 25 * 60:
            t.update(estado="error", nota="no salió en 25 min: mirá el log de la máquina", progreso=None)
        else:
            t["progreso"] = progreso(t, ultimo)
    _escribir(ts)
    return turnos()


# Minutos de GPU por segundo de clip en una 5090 (COSTOS-H3.md): 0,67-0,81
# medidos entre 5 y 7 s; el de 15,08 s del 17/9/2026 (mono terapeuta, 768×1344)
# tardó 17,2 min = 1,14 min/s. No escala lineal: la atención crece con el largo.
MIN_GPU_POR_SEGUNDO_CORTO = 0.8     # hasta 7,3 s
MIN_GPU_POR_SEGUNDO_LARGO = 1.15    # 10 a 15 s


def estimado_seg(segundos: float) -> int:
    """Cuánto suele tardar un clip de `segundos`, incluida la carga del modelo."""
    s = float(segundos)
    tasa = MIN_GPU_POR_SEGUNDO_CORTO if s <= 7.5 else MIN_GPU_POR_SEGUNDO_LARGO
    return int(60 + s * tasa * 60)


def progreso(t: dict, ultimo: str = "") -> dict:
    trans = int(time.time() - t.get("lanzado", time.time()))
    est = estimado_seg(t.get("segundos") or grilla.MINIMO)
    return {"transcurrido": trans, "estimado": est,
            "pct": min(95, int(trans / est * 100)) if est else 0, "ultimo": ultimo}


def _ultima_linea(inst: dict) -> str:
    """La última línea del log de la placa 0 (el runner escribe «generando… Ns»
    cada 5 s, y «!!» si algo falla), con los retornos de carro deshechos."""
    try:
        return vast.ejecutar(inst, "tail -c 600 /root/gpu0.log 2>/dev/null | tr '\\r' '\\n' | grep . | tail -n 1",
                             timeout=30).strip()[-200:]
    except Exception:
        return ""


def ocupada() -> bool:
    return any(t["estado"] == "generando" for t in _leer())
