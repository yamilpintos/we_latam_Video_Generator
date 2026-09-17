"""EDITAR: subís un video y H3 lo rehace con un cambio (la ropa, el fondo, un
objeto, una frase nueva), conservando encuadre, movimiento y tiempos.

Es el modo de referencia completa de MiniMax H3 (Ref2VA) con el video como
`<Video 1>` y la tarea oficial «video editing»: el nodo de ComfyUI acepta hasta
tres videos de referencia (fotogramas a 24 fps, con su audio). Límites del
modelo: el video fuente de 2 a 15 s, la salida de 5,17 a 15,08 s, y H3 NO
conserva cada cuadro ni el timing exacto: reinterpreta con fidelidad, no filtra.

Todo vive en `mis-videos/_editar/`: `turnos.json`, `fuentes/E<id>.mp4` (el
video ya a 24 fps y al lienzo de H3), `fuentes/E<id>-hoja.jpg` (8 fotogramas,
lo que GPT mira para describir el video), `assets/E<id>-ref.png` (imagen de
referencia opcional: la prenda, el fondo), `clips/E<id>_00001_.mp4`.

En la máquina hace falta el modelo Ref2VA (24 GB más la LoRA turbo). Si la
máquina se instaló sólo con FL2VA, la primera edición lo baja (`SOLO_FL=0
bash setup.sh`, ~5 min a 1 Gbps) y recién después genera.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
import time
import zipfile
from pathlib import Path

from .. import config, grilla, montaje, reescritor, vast
from . import libre, maquina

DIR = maquina.MIS / "_editar"
TURNOS = DIR / "turnos.json"
RES = {"16:9": (1344, 768), "9:16": (768, 1344)}
MODELOS_REF = ("unet/MiniMax-H3-Ref2VA-Q5_K_M.gguf", "loras/minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors")
ARBOLES = ("/opt/workspace-internal/ComfyUI/models", "/workspace/ComfyUI/models")
LOG_REF2VA = "/root/ref2va.log"
LOG_EDITAR = "/root/editar.log"


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
    ts = [x for x in _leer() if x["id"] != t["id"]] + [t]
    _escribir(ts)
    return t


# ───────────────────────────────────────────────────────────── el video fuente

def _ffmpeg(*args: str, timeout: int = 600) -> None:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"ffmpeg: {r.stderr.strip()[-400:]}")


def _sonda(ruta: Path) -> dict:
    """ancho, alto, duración y si tiene audio, del stderr de ffmpeg (sin ffprobe)."""
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-i", str(ruta)], capture_output=True, text=True)
    m = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", r.stderr)
    rot = re.search(r"rotate\s*:\s*(-?\d+)|displaymatrix.*?(-?\d+\.\d+) degrees", r.stderr)
    w, h = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    if rot:
        g = abs(float(rot.group(1) or rot.group(2) or 0))
        if 45 < g < 135 or 225 < g < 315:
            w, h = h, w
    return {"w": w, "h": h, "dur": montaje.duracion(ruta), "audio": "Audio:" in r.stderr}


def subir_video(nombre: str, b64: str, ajuste: str = "encajar", desde: float = 0.0) -> dict:
    """Guarda el video del usuario ya preparado para H3: 24 fps, el lienzo
    según su orientación (entero con fondo desenfocado, o recortado), y como
    mucho 15,08 s en la grilla de H3. Deja también la hoja de fotogramas."""
    tid = "E" + time.strftime("%m%d%H%M%S")
    (DIR / "fuentes").mkdir(parents=True, exist_ok=True)
    ext = Path(nombre).suffix.lower() or ".mp4"
    if ext not in (".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"):
        raise ValueError("subí un video (mp4, mov, webm, mkv)")
    if "," in b64[:64]:
        b64 = b64.split(",", 1)[1]
    crudo = DIR / "fuentes" / f"{tid}-crudo{ext}"
    crudo.write_bytes(base64.b64decode(b64))
    s = _sonda(crudo)
    if not s["w"] or s["dur"] <= 0:
        crudo.unlink(missing_ok=True)
        raise ValueError("no pude leer el video")
    util = s["dur"] - float(desde)
    if util < 2.0:
        crudo.unlink(missing_ok=True)
        raise ValueError(f"el video dura {s['dur']:.1f} s; H3 necesita al menos 2 s de referencia")
    aspecto = "9:16" if s["h"] > s["w"] * 1.1 else "16:9"
    w, h = RES[aspecto]
    length, real = grilla.encajar(min(util, grilla.MAXIMO))
    frames = min(int(round(min(util, grilla.MAXIMO) * grilla.FPS)), length)
    if ajuste == "recortar":
        vf = f"fps={grilla.FPS},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        filtro = ["-vf", vf]
    else:
        fc = (f"[0:v]fps={grilla.FPS},split=2[a][b];"
              f"[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=28,eq=brightness=-0.18[bg];"
              f"[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2:format=auto,format=yuv420p[v]")
        filtro = ["-filter_complex", fc, "-map", "[v]"] + (["-map", "0:a?"] if s["audio"] else [])
    fuente = DIR / "fuentes" / f"{tid}.mp4"
    args = ["-ss", f"{float(desde):.3f}", "-i", str(crudo), *filtro, "-frames:v", str(frames),
            "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p", "-r", str(grilla.FPS)]
    if s["audio"]:
        args += ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-t", f"{frames / grilla.FPS:.3f}"]
    else:
        args += ["-an"]
    _ffmpeg(*args, str(fuente))
    hoja = DIR / "fuentes" / f"{tid}-hoja.jpg"
    dur_f = frames / grilla.FPS
    _ffmpeg("-i", str(fuente), "-vf", f"fps={8 / dur_f:.4f},scale=320:-2,tile=4x2", "-frames:v", "1", "-q:v", "3", str(hoja))
    crudo.unlink(missing_ok=True)
    t = {"id": tid, "creado": time.time(), "nombre": Path(nombre).name, "fuente": f"fuentes/{tid}.mp4",
         "hoja": f"fuentes/{tid}-hoja.jpg", "aspecto": aspecto, "ajuste": ajuste, "original": {"w": s["w"], "h": s["h"], "dur": round(s["dur"], 2)},
         "segundos_fuente": round(dur_f, 3), "length": length, "tiene_audio": bool(s["audio"]), "ref": None,
         "estado": "fuente", "cambio": None, "prompt_video": None, "segundos": None, "clip": None, "nota": "", "progreso": None}
    if s["dur"] > grilla.MAXIMO + 0.05:
        t["nota"] = f"el video dura {s['dur']:.1f} s: se usan los primeros {dur_f:.1f} (H3 admite hasta 15,08)"
    return _guardar(t)


def referencia(tid: str, b64: str) -> dict:
    """La imagen de referencia del cambio (la prenda, el fondo, el objeto): <Picture 1>."""
    from PIL import Image
    import io
    t = _turno(tid)
    (DIR / "assets").mkdir(parents=True, exist_ok=True)
    if "," in b64[:64]:
        b64 = b64.split(",", 1)[1]
    im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    im.thumbnail((1344, 1344))
    f = DIR / "assets" / f"{tid}-ref.png"
    im.save(f, "PNG")
    t["ref"] = f"assets/{tid}-ref.png"
    return _guardar(t)


def quitar_referencia(tid: str) -> dict:
    t = _turno(tid)
    if t.get("ref"):
        (DIR / t["ref"]).unlink(missing_ok=True)
    t["ref"] = None
    return _guardar(t)


# ───────────────────────────────────────────────────────────── el prompt

def pedido(t: dict, cambio: str, segundos: float, audio_original: bool, dialogo: str = "") -> dict:
    return {"duracion": round(float(segundos), 3), "aspecto": t["aspecto"], "segundos_fuente": t["segundos_fuente"],
            "cambio": cambio.strip(), "imagen_ref": str(DIR / t["ref"]) if t.get("ref") else None,
            "hoja": str(DIR / t["hoja"]), "audio_original": bool(audio_original and t.get("tiene_audio")),
            "dialogo": {"texto": dialogo, "idioma": "es"} if dialogo.strip() else None,
            "notas": "The user writes in Spanish; the change is what they describe."}


def es_oficial(texto: str) -> bool:
    return texto.strip().startswith("subject_definitions:") and "detailed_description:" in texto


def armar_prompt(tid: str, cambio: str, segundos: float, audio_original: bool = True, dialogo: str = "", log=print) -> dict:
    t = _turno(tid)
    if es_oficial(cambio):
        return {"prompt": cambio.strip(), "origen": "ya venía en formato oficial", "problemas": []}
    if len(cambio.strip()) < 6:
        raise ValueError("decí qué querés cambiar")
    r = reescritor.reescribir_edicion(pedido(t, cambio, segundos, audio_original, dialogo), log=log)
    t["cambio"] = cambio.strip()
    _guardar(t)
    return r


# ───────────────────────────────────────────────────────────── la máquina

def _cmd_ref2va_presente() -> str:
    partes = []
    for m in MODELOS_REF:
        partes.append("( " + " || ".join(f"test -f {a}/{m}" for a in ARBOLES) + " )")
    return " && ".join(partes) + " && echo SI || echo NO"


def ref2va_presente(inst: dict) -> bool:
    try:
        return vast.ejecutar(inst, _cmd_ref2va_presente(), timeout=40).strip().endswith("SI")
    except Exception:
        return False


def instalar_ref2va(inst: dict, log=print) -> None:
    """Baja Ref2VA (y su LoRA) en la máquina ya instalada: setup.sh es idempotente
    y con SOLO_FL=0 agrega lo que falta sin tocar lo que está."""
    vast.lanzar(inst, "export PATH=/venv/main/bin:$PATH && cd /workspace/refs && SOLO_FL=0 bash setup.sh", log=LOG_REF2VA)
    log("instalando Ref2VA en la máquina (24 GB + LoRA)")


def progreso_ref2va(inst: dict) -> dict:
    """GB bajados del modelo Ref2VA (24 GB) y última línea del log."""
    try:
        s = vast.ejecutar(inst, "for a in " + " ".join(ARBOLES) + "; do du -sb $a/unet/MiniMax-H3-Ref2VA-Q5_K_M.gguf 2>/dev/null | cut -f1; "
                          "ls $a/unet/.cache/huggingface/download/MiniMax-H3-Ref2VA-Q5_K_M.gguf.*.incomplete 2>/dev/null | head -1 | xargs -r du -sb | cut -f1; done | sort -n | tail -1; "
                          f"tail -n 1 {LOG_REF2VA} 2>/dev/null | tr '\\r' '\\n' | tail -n 1 | cut -c1-160", timeout=40)
        l = s.splitlines()
        b = float(l[0]) if l and l[0].strip().isdigit() else 0.0
        return {"gb": round(b / 1e9, 1), "pct": min(99, int(b / 23.9e9 * 100)), "ultimo": l[1] if len(l) > 1 else ""}
    except Exception as e:
        return {"gb": None, "pct": None, "ultimo": f"(sin respuesta: {e})"}


def _zip_turno(t: dict, prompt_video: str, segundos: float, seed: int | None, audio_original: bool) -> Path:
    length, real = grilla.encajar(float(segundos))
    w, h = RES[t["aspecto"]]
    plano = {"id": t["id"], "escena": "EDITAR", "tramo": None, "tipo": "PM", "loc": None, "personajes": [],
             "length": length, "segundos": round(real, 3), "funcion": "edición de un video",
             "modo": "ref2va", "first_frame": None, "ref_video": f"assets/{t['id']}.mp4",
             "ref_video_audio": bool(audio_original and t.get("tiene_audio")),
             "refs_extra": [f"assets/{t['id']}-ref.png"] if t.get("ref") else [],
             "clip_de": None, "sigue_de": None, "prompt": prompt_video, "dialogo": None}
    if seed is not None:
        plano["seed"] = int(seed)
    doc = {"titulo": "EDITAR", "slug": "_editar", "formato": "largo" if t["aspecto"] == "16:9" else "short",
           "fps": grilla.FPS, "ancho": w, "alto": h, "estructura": "libre", "planos": [plano]}
    (DIR / "zips").mkdir(exist_ok=True)
    z = DIR / "zips" / f"{t['id']}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("planos.json", json.dumps(doc, ensure_ascii=False, indent=2))
        zf.write(DIR / t["fuente"], f"assets/{t['id']}.mp4")
        if t.get("ref"):
            zf.write(DIR / t["ref"], f"assets/{t['id']}-ref.png")
        for n in ("setup.sh", "lanzar.sh", "rescate.sh", "runner.py"):
            zf.write(maquina.REMOTO / n, n)
    return z


def _lanzar(t: dict, inst: dict, log=print) -> dict:
    z = _zip_turno(t, t["prompt_video"], t["segundos"], t.get("seed"), t.get("audio_original", True))
    vast.subir(inst, z)
    # Ref2VA con video de referencia es lo más pesado que corre en 32 GB:
    # siempre con la VRAM limpia.
    vast.ejecutar(inst, "supervisorctl restart comfyui >/dev/null 2>&1 || true", timeout=60)
    vast.ejecutar(inst, f"export PATH=/venv/main/bin:$PATH && cd /workspace/refs && unzip -oq {z.name} && "
                        f"sed -i 's/\\r$//' *.sh *.py && cp planos.json /root/planos.json", timeout=180)
    vast.lanzar(inst, "export PATH=/venv/main/bin:$PATH && cd /workspace/refs && PASOS=8 GPUS=1 bash lanzar.sh", log=LOG_EDITAR)
    maquina.escribir(proyecto="_editar", generando_desde=time.time())
    t.update(estado="generando", lanzado=time.time())
    log(f"{t['id']} lanzado en la máquina")
    return _guardar(t)


def video(tid: str, texto: str, segundos: float, seed: int | None = None, audio_original: bool = True,
          dialogo: str = "", log=print) -> dict:
    """Edita: si el texto no es un prompt oficial, pasa por el reescritor; si la
    máquina no tiene Ref2VA, lo instala y deja el turno esperando (refrescar()
    lo lanza cuando termina)."""
    t = _turno(tid)
    m = maquina.sincronizar()
    if m.get("fase") != "lista" or not m.get("instancia"):
        raise RuntimeError(f"la máquina no está lista (fase {m.get('fase')}); encendela desde el inicio")
    if libre.ocupada() or ocupada():
        raise RuntimeError("hay un turno generando; esperá a que termine")
    segundos = min(float(segundos), grilla.MAXIMO)
    if not es_oficial(texto):
        r = reescritor.reescribir_edicion(pedido(t, texto, segundos, audio_original, dialogo), log=log)
        t["cambio"] = texto.strip()
        t["prompt_origen"] = r["origen"]
        texto = r["prompt"]
    t.update(prompt_video=texto, segundos=float(segundos), seed=seed, audio_original=bool(audio_original and t.get("tiene_audio")))
    inst = vast.instancia(int(m["instancia"]))
    if not ref2va_presente(inst):
        instalar_ref2va(inst, log=log)
        t.update(estado="instalando_ref2va", lanzado=time.time(), nota="la máquina baja el modelo Ref2VA (24 GB, ~5 min); el clip arranca solo después")
        return _guardar(t)
    return _lanzar(t, inst, log=log)


def progreso(t: dict, ultimo: str = "") -> dict:
    trans = int(time.time() - t.get("lanzado", time.time()))
    # Ref2VA con video: sin medición propia todavía; se asume un 30 % más que FL2VA.
    est = int(libre.estimado_seg(t.get("segundos") or grilla.MINIMO) * 1.3)
    return {"transcurrido": trans, "estimado": est, "pct": min(95, int(trans / est * 100)) if est else 0, "ultimo": ultimo}


def refrescar() -> list[dict]:
    ts = _leer()
    activos = [t for t in ts if t["estado"] in ("generando", "instalando_ref2va")]
    if not activos:
        return turnos()
    m = maquina.leer()
    if not m.get("instancia") or m.get("fase") in ("apagada", "fallo"):
        for t in activos:
            t.update(estado="error", nota="la máquina se apagó antes de terminar", progreso=None)
        _escribir(ts)
        return turnos()
    try:
        inst = vast.instancia(int(m["instancia"]))
    except Exception:
        return turnos()
    for t in [t for t in activos if t["estado"] == "instalando_ref2va"]:
        if ref2va_presente(inst):
            t["nota"] = ""
            _lanzar(t, inst, log=lambda *_: None)
            t.update(estado="generando", lanzado=time.time())
        else:
            p = progreso_ref2va(inst)
            t["progreso"] = {"transcurrido": int(time.time() - t.get("lanzado", time.time())), "estimado": 6 * 60,
                             "pct": p.get("pct") or 0, "ultimo": f"Ref2VA: {p.get('gb') or 0} de 23,9 GB · {p.get('ultimo') or ''}"}
            if time.time() - t.get("lanzado", 0) > 40 * 60:
                t.update(estado="error", nota="Ref2VA no terminó de bajar en 40 min: mirá el log de la máquina", progreso=None)
    gen = [t for t in ts if t["estado"] == "generando"]
    if gen:
        try:
            arch = vast.archivos_remotos(inst)
        except Exception:
            arch = []
        (DIR / "clips").mkdir(exist_ok=True)
        ultimo = libre._ultima_linea(inst)
        for t in gen:
            mios = [a for a in arch if a.startswith(t["id"] + "_") and a.endswith(".mp4")]
            if mios:
                try:
                    vast.bajar(inst, mios[:1], DIR / "clips", log=lambda *_: None)
                    t.update(estado="listo", clip=f"clips/{mios[0]}", terminado=time.time(), progreso=None)
                except Exception as e:
                    t.update(nota=f"bajando… ({e})")
            elif time.time() - t.get("lanzado", 0) > 30 * 60:
                t.update(estado="error", nota="no salió en 30 min: mirá el log de la máquina (Ref2VA con video puede quedarse sin memoria)", progreso=None)
            else:
                t["progreso"] = progreso(t, ultimo)
    _escribir(ts)
    return turnos()


def ocupada() -> bool:
    return any(t["estado"] in ("generando", "instalando_ref2va") for t in _leer())
