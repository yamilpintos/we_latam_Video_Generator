"""REMASTERIZAR: una película o un capítulo en definición estándar (576i / 480p)
a 4K con FlashVSR v1.1 Full, en una A100 de 80 GB alquilada en Vast.

Es OTRA máquina, aparte de la 4×5090 de H3: otra imagen Docker (CUDA 12.4, sin
ComfyUI), otra instalación (`remoto/remaster/setup-flashvsr.sh`, ~13 min) y su
propio estado en `mis-videos/_estado/remaster.json`. Todo lo de acá sale de las
dos corridas reales del 17 y 18/9/2026 (`remasterizado/REMASTER-4K-HANDOFF.md`).

El flujo, en orden, con la GPU apagada hasta el paso 4:

  1. origen     el archivo (subido, o una ruta en el servidor) → sondeo con ffmpeg:
                tamaño, entrelazado (idet), bitrate, audio; hoja de 6 cuadros;
                avisos («bitrate bajo = caras inventadas»).
  2. opciones   rango, recorte (VBI y blanking del máster), desentrelazar.
  3. preparar   ffmpeg local: recorte + bwdif + x264 crf 8 4:2:2 + audio estéreo
                → `fuentes/R<id>.mp4`. Lo que el modelo va a ver.
  4. correr     alquila la A100 apta, instala, sube la fuente, corre la inferencia
                por trozos (mirando `escritos a/N`), codifica el 4K final EN la
                máquina con el audio, lo baja, destruye la instancia, hace el QC.
  5. uhd        opcional y local: 3840×2160 con barras a partir del 4K.

Números que mandan (medidos): 60 s de GPU por segundo de video en A100 (Full,
tiles grandes); instalación 770 s; $0,87-1,06/h. Una hora de película ≈ $52.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from .. import config, montaje, vast
from . import maquina

DIR = maquina.MIS / "_remaster"
TRABAJOS = DIR / "trabajos.json"
ESTADO = maquina.MIS / "_estado" / "remaster.json"
SCRIPTS = maquina.REMOTO / "remaster"                 # h3pipeline/remoto/remaster
ETIQUETA = maquina.ETIQUETA_REMASTER
IMAGEN = vast.IMAGEN_CUDA124
REMOTO = "/workspace/remaster"
PY = "/venv/main/bin/python"
DISCO_GB = 60
PRECIO_MAX = 1.30
FIABILIDAD_MIN = 0.98
INET_MIN = 500
VRAM_MIN_GB = 70
# Segundos de GPU por segundo de video. Full con tiles grandes: 1794 s por 30 s
# (18/9, A100 PCIe). Se actualiza con cada corrida real (costo.real).
FACTOR_GPU = {"full": 60.0}
SETUP_SEG = 13 * 60           # 770 s de instalación + 1,5 min de arranque
LIMITE_SETUP_MIN = 30
ALTO_MAX_ORIGEN = 720         # FlashVSR es ×4 nativo: más de esto pasa de 4K
CRF_FINAL = 15
ACTIVOS = ("descargando", "preparando", "alquilando", "arrancando", "instalando", "remasterizando", "codificando", "bajando", "qc")


# ───────────────────────────────────────────────────────────── trabajos

def _leer() -> list[dict]:
    if not TRABAJOS.exists():
        return []
    try:
        return json.loads(TRABAJOS.read_text(encoding="utf-8"))
    except Exception:
        return []


def _escribir(ts: list[dict]) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    TRABAJOS.write_text(json.dumps(ts, ensure_ascii=False, indent=2), encoding="utf-8")


def trabajos() -> list[dict]:
    return sorted(_leer(), key=lambda t: t["creado"], reverse=True)


def trabajo(tid: str) -> dict:
    for t in _leer():
        if t["id"] == tid:
            return t
    raise KeyError(tid)


def guardar(t: dict) -> dict:
    ts = [x for x in _leer() if x["id"] != t["id"]] + [t]
    _escribir(ts)
    return t


def actualizar(tid: str, **cambios) -> dict:
    t = trabajo(tid)
    t.update(cambios)
    return guardar(t)


def ocupada() -> bool:
    return any(t["estado"] in ACTIVOS for t in _leer())


# ───────────────────────────────────────────────────────────── la máquina A100

def leer_maquina() -> dict:
    if not ESTADO.exists():
        return {"fase": "apagada"}
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        return {"fase": "apagada"}


def escribir_maquina(**cambios) -> dict:
    d = leer_maquina()
    d.update(cambios)
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def gasto(d: dict) -> dict:
    if not d.get("inicio"):
        return {"minutos": 0, "acumulado": 0.0}
    fin = d.get("fin") or time.time()
    horas = (fin - d["inicio"]) / 3600
    return {"minutos": round(horas * 60), "acumulado": round(d.get("dph", 0) * horas, 2)}


def sincronizar_maquina() -> dict:
    """El estado de la A100 puesto al día: si dice encendida pero Vast ya no la
    tiene, pasa a apagada (misma lección que maquina.desaparecida, 18/9)."""
    m = leer_maquina()
    if m.get("fase") not in ("apagada", "fallo") and m.get("instancia"):
        try:
            vast.instancia(int(m["instancia"]))
        except vast.ErrorVast as e:
            if "no existe" in str(e):
                m = escribir_maquina(fase="apagada", fin=None, gasto_final=None,
                                     error=f"la instancia {m.get('instancia')} ya no existe en Vast (destruida desde otro lado)")
        except Exception:
            pass
    return m


def maquina_dict() -> dict:
    m = sincronizar_maquina()
    return {**m, **gasto(m)}


def apagar(log=print) -> dict:
    """Destruye la A100 si está viva y cierra el trabajo que tuviera."""
    m = leer_maquina()
    iid = m.get("instancia")
    if iid and m.get("fase") not in ("apagada",):
        try:
            vast.destruir(int(iid), confirmar=True)
            log(f"instancia {iid} destruida")
        except Exception as ex:
            if "no existe" not in str(ex):
                raise
    g = gasto(m)
    d = escribir_maquina(fase="apagada", fin=time.time(), gasto_final=g["acumulado"] if m.get("inicio") else None)
    for t in _leer():
        if t["estado"] in ACTIVOS and t["estado"] != "preparando":
            t.update(estado="error", nota="la máquina se apagó antes de terminar")
            t.setdefault("costo", {})["real"] = g["acumulado"]
            guardar(t)
        elif t["estado"] == "sin_bajar":
            t.update(estado="error", nota="la máquina se apagó con la salida sin bajar: el 4K se perdió")
            guardar(t)
    return {"apagada": iid, "gasto_final": d.get("gasto_final"), "minutos": g["minutos"]}


# ───────────────────────────────────────────────────────────── ffmpeg local

def _ffmpeg_stderr(*args: str, timeout: int = 120) -> str:
    r = subprocess.run([config.ffmpeg(), "-hide_banner", *args], capture_output=True, timeout=timeout)
    return r.stderr.decode("utf-8", "replace")


def _ffmpeg(*args: str, timeout: int | None = None, log=None) -> None:
    cmd = [config.ffmpeg(), "-hide_banner", "-y", *args]
    if log is None:
        r = subprocess.run([*cmd[:2], "-loglevel", "error", *cmd[2:]], capture_output=True, timeout=timeout)
        if r.returncode:
            raise RuntimeError("ffmpeg: " + r.stderr.decode("utf-8", "replace").strip()[-500:])
        return
    # Con `log`, el avance de ffmpeg va al log de la tarea (stderr heredado).
    r = subprocess.run([*cmd[:2], "-stats", "-loglevel", "warning", *cmd[2:]], timeout=timeout)
    if r.returncode:
        raise RuntimeError(f"ffmpeg terminó con código {r.returncode}")


def sondear(ruta: Path) -> dict:
    """Lo que hay que saber del origen antes de gastar: tamaño, aspecto (DAR),
    fps, bitrate, audio y si está entrelazado (idet sobre 4 s del medio)."""
    err = _ffmpeg_stderr("-i", str(ruta))
    s = {"w": 0, "h": 0, "sar": None, "dar": None, "fps": 25.0, "dur": 0.0, "kbps": 0, "kbps_total": 0,
         "codec": "", "pix": "", "canales": 0, "audio_codec": "", "entrelazado": False, "campo": "auto",
         "idet": None}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", err)
    if m:
        s["dur"] = round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 3)
    m = re.search(r"bitrate:\s*(\d+)\s*kb/s", err)
    if m:
        s["kbps_total"] = int(m.group(1))
    for linea in err.splitlines():
        if "Video:" in linea and not s["w"]:
            m = re.search(r"Video:\s*(\w+)", linea)
            s["codec"] = m.group(1) if m else ""
            m = re.search(r"(\d{2,5})x(\d{2,5})(?:\s*\[SAR\s*(\d+):(\d+)\s*DAR\s*(\d+):(\d+)\])?", linea)
            if m:
                s["w"], s["h"] = int(m.group(1)), int(m.group(2))
                if m.group(3):
                    s["sar"] = f"{m.group(3)}:{m.group(4)}"
                    s["dar"] = f"{m.group(5)}:{m.group(6)}"
            m = re.search(r",\s*(yuv\w+|rgb\w+|gray\w*)", linea)
            s["pix"] = m.group(1) if m else ""
            m = re.search(r"(\d+)\s*kb/s", linea)
            s["kbps"] = int(m.group(1)) if m else 0
            m = re.search(r"([\d.]+)\s*fps", linea) or re.search(r"([\d.]+)\s*tbr", linea)
            if m:
                try:
                    s["fps"] = float(m.group(1))
                except ValueError:
                    pass
        elif "Audio:" in linea and not s["canales"]:
            m = re.search(r"Audio:\s*(\w+)", linea)
            s["audio_codec"] = m.group(1) if m else ""
            if "mono" in linea:
                s["canales"] = 1
            elif "stereo" in linea:
                s["canales"] = 2
            elif re.search(r"\b7\.1", linea):
                s["canales"] = 8
            elif re.search(r"\b5\.1", linea):
                s["canales"] = 6
            else:
                m = re.search(r"(\d+)\s*channels", linea)
                s["canales"] = int(m.group(1)) if m else 2
    if not s["kbps"]:
        s["kbps"] = s["kbps_total"]
    if s["w"] and s["dur"] > 0:
        medio = max(0.0, min(s["dur"] / 2, s["dur"] - 5))
        det = _ffmpeg_stderr("-ss", f"{medio:.2f}", "-t", "4", "-i", str(ruta), "-vf", "idet", "-an", "-f", "null", "-", timeout=180)
        m = None
        for m in re.finditer(r"Multi frame detection:\s*TFF:\s*(\d+)\s*BFF:\s*(\d+)\s*Progressive:\s*(\d+)\s*Undetermined:\s*(\d+)", det):
            pass
        if m:
            tff, bff, prog, und = (int(x) for x in m.groups())
            s["idet"] = {"tff": tff, "bff": bff, "progresivo": prog, "indeterminado": und}
            s["entrelazado"] = (tff + bff) > prog
            s["campo"] = "tff" if tff >= bff else "bff"
    return s


def _hoja(ruta: Path, dur: float, destino: Path, n: int = 6, ancho: int = 480) -> None:
    dur = max(dur, 0.5)
    _ffmpeg("-i", str(ruta), "-vf", f"fps={n / dur:.6f},scale={ancho}:-2,tile=3x2", "-frames:v", "1", "-q:v", "3", str(destino), timeout=600)


def recorte_sugerido(w: int, h: int) -> str:
    """El máster IMX (D-10) trae 32 líneas de VBI arriba y blanking lateral: medido
    el 18/9 sobre Chiquititas (720×608 → crop 704:576:12:32). El PAL/NTSC de 720
    de ancho suele traer 8 px de blanking por lado."""
    if (w, h) == (720, 608):
        return "704:576:12:32"
    if (w, h) == (720, 576):
        return "704:576:8:0"
    if (w, h) == (720, 480):
        return "704:480:8:0"
    return ""


def avisos_de(s: dict) -> list[dict]:
    a = []
    if s["h"] > ALTO_MAX_ORIGEN:
        a.append({"nivel": "bad", "texto": f"el origen mide {s['w']}×{s['h']}: FlashVSR multiplica ×4 y pasaría de 4K. Esta herramienta es para SD (hasta 720 de alto)."})
    if s["kbps"] and s["kbps"] < 5000:
        a.append({"nivel": "warn", "texto": f"bitrate de {s['kbps']} kb/s: es un origen pobre. Medido el 17/9: con 302 kb/s las caras lejanas salen inventadas; con el máster de 50 Mb/s salen limpias. Si tenés un máster o un DVD, usá eso."})
    if s["entrelazado"]:
        a.append({"nivel": "info", "texto": f"entrelazado ({s['campo'].upper()}): se desentrelaza antes del modelo con bwdif. Nunca escalar entrelazado: el modelo fija el peinado como detalle."})
    if not s["canales"]:
        a.append({"nivel": "info", "texto": "sin audio: el 4K sale mudo."})
    elif s["canales"] > 2:
        a.append({"nivel": "info", "texto": f"{s['canales']} canales de audio: se toman los dos primeros como estéreo (así viene el máster IMX)."})
    if s["dur"] > 15 * 60:
        a.append({"nivel": "warn", "texto": f"{s['dur'] / 60:.0f} min de video: a 60× tiempo real son ~{s['dur'] / 60:.0f} h de A100 (~${s['dur'] / 3600 * 60 * 0.9:.0f}). Conviene probar antes un rango de 30 s."})
    return a


def _trabajo_nuevo(tid: str, nombre: str, origen: str | None, subido: bool) -> dict:
    return {"id": tid, "creado": time.time(), "nombre": Path(nombre).name if nombre else "", "origen": origen,
            "subido": subido, "sonda": None, "hoja": None, "avisos": [], "drive": None,
            "opciones": {"inicio": 0.0, "fin": None, "recorte": "", "desentrelazar": False, "campo": "auto", "variante": "full"},
            "estado": "origen", "fuente": None, "hoja_fuente": None, "segundos_fuente": None, "cuadros": None,
            "final": None, "salidas": {}, "qc": [], "costo": {}, "progreso": None, "nota": "", "instancia": None}


def _analizar(t: dict, origen: Path) -> dict:
    """Sondeo + hoja + avisos + opciones sugeridas sobre un archivo ya en disco."""
    s = sondear(origen)
    if not s["w"] or s["dur"] <= 0:
        raise ValueError("no pude leer el video (¿es un archivo de video completo?)")
    (DIR / "hojas").mkdir(parents=True, exist_ok=True)
    hoja = DIR / "hojas" / f"{t['id']}-origen.jpg"
    try:
        _hoja(origen, s["dur"], hoja)
    except Exception:
        hoja = None
    t.update(origen=str(origen), sonda=s, hoja=f"hojas/{hoja.name}" if hoja else None, avisos=avisos_de(s),
             opciones={**t["opciones"], "recorte": recorte_sugerido(s["w"], s["h"]),
                       "desentrelazar": bool(s["entrelazado"]), "campo": s["campo"]},
             estado="origen", nota="", progreso=None)
    return guardar(t)


# ───────────────────────────────────────────────────────────── Google Drive

def _drive_id(url: str) -> str:
    """El id del archivo de un link de Drive, en cualquiera de sus formas
    (`/file/d/<id>/view`, `open?id=`, `uc?id=`). Las carpetas no: hay que
    pasar el link del archivo."""
    u = url.strip()
    m = re.search(r"/file/d/([A-Za-z0-9_-]{10,})", u) or re.search(r"[?&]id=([A-Za-z0-9_-]{10,})", u)
    if m:
        return m.group(1)
    if "/folders/" in u:
        raise ValueError("es el link de una carpeta: abrí el archivo en Drive y pegá el link del archivo")
    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", u):
        return u
    raise ValueError("no reconozco ese link de Drive (esperaba …/file/d/<id>/… o …?id=<id>)")


def nuevo_origen_drive(url: str) -> dict:
    """Registra un trabajo que todavía no tiene el archivo: la tarea `descargar`
    lo baja con gdown (como se bajó el máster el 17/9: 22,7 GB, con reanudación)
    y lo analiza al terminar."""
    fid = _drive_id(url)
    tid = "R" + time.strftime("%m%d%H%M%S")
    t = _trabajo_nuevo(tid, "", None, subido=True)
    t.update(drive={"url": url.strip(), "id": fid}, estado="descargando", nombre="(Drive) bajando…",
             progreso={"fase": "descargando", "hechos": 0, "total": None, "pct": 0, "ultimo": "conectando con Drive", "t": time.time()})
    return guardar(t)


def descargar(tid: str, log=print) -> dict:
    """Baja el archivo de Drive a `origenes/` y lo analiza. gdown reanuda si ya
    había una parte (`resume=True`). Avast rompe TLS en esta PC: se prueba con
    el bundle del proyecto (`config.certificados()`) y si igual falla, sin
    verificar el certificado, como hizo `gdown --no-check-certificate`."""
    import gdown
    t = trabajo(tid)
    fid = t["drive"]["id"]
    (DIR / "origenes").mkdir(parents=True, exist_ok=True)
    config.certificados()
    actualizar(tid, estado="descargando", nota="")
    info = None
    for verify in (True, False):
        try:
            info = gdown.download(id=fid, skip_download=True, quiet=True, verify=verify)
            break
        except Exception as e:
            log(f"consulta a Drive (verify={verify}): {e}")
            if verify is False:
                raise RuntimeError(f"Drive no contestó: {e}")
    # gdown 6.1: GoogleDriveFileToDownload(id, path, local_path); `path` es el nombre en Drive
    nombre = Path(getattr(info, "path", None) or getattr(info, "local_path", None) or getattr(info, "name", None) or f"{tid}.bin").name
    destino = DIR / "origenes" / f"{tid}-{nombre}"
    log(f"Drive: {nombre} → {destino.name} (verify={verify})")
    actualizar(tid, nombre=nombre)
    ultimo = {"t": 0.0}

    def avance(bajado: int, total: int | None):
        if time.time() - ultimo["t"] < 5:
            return
        ultimo["t"] = time.time()
        p = {"fase": "descargando", "hechos": bajado, "total": total, "t": time.time(),
             "pct": min(99, int(bajado / total * 100)) if total else 0,
             "ultimo": f"{bajado / 1e9:.2f} de {total / 1e9:.2f} GB" if total else f"{bajado / 1e6:.0f} MB"}
        actualizar(tid, progreso=p)
        log(p["ultimo"])

    salida = gdown.download(id=fid, output=str(destino), quiet=True, resume=True, verify=verify, progress=avance)
    if not salida or not destino.exists() or destino.stat().st_size < 1000:
        raise RuntimeError("la descarga no dejó un archivo")
    log(f"bajado: {destino.stat().st_size / 1e9:.2f} GB · analizando")
    t = trabajo(tid)
    return _analizar(t, destino)


def nuevo_origen(nombre: str = "", b64: str | None = None, ruta: str | None = None) -> dict:
    """Registra un origen: un archivo subido (base64) o una ruta en este servidor
    (para másters de varios GB que no pasan por el navegador). Sondea, hace la
    hoja y deja las opciones sugeridas. No gasta nada."""
    tid = "R" + time.strftime("%m%d%H%M%S")
    (DIR / "origenes").mkdir(parents=True, exist_ok=True)
    (DIR / "hojas").mkdir(parents=True, exist_ok=True)
    if ruta:
        origen = Path(ruta.strip().strip('"'))
        if not origen.is_absolute():
            origen = maquina.RAIZ / origen
        if not origen.exists() or not origen.is_file():
            raise ValueError(f"no encuentro el archivo {origen}")
        nombre = nombre or origen.name
    elif b64:
        ext = Path(nombre).suffix.lower() or ".mp4"
        if ext not in (".mp4", ".mov", ".m4v", ".mkv", ".avi", ".mxf", ".mpg", ".mpeg", ".ts", ".vob", ".webm", ".wmv"):
            raise ValueError("subí un video (mp4, mov, mkv, avi, mxf, mpg, ts, vob)")
        if "," in b64[:64]:
            b64 = b64.split(",", 1)[1]
        origen = DIR / "origenes" / f"{tid}{ext}"
        origen.write_bytes(base64.b64decode(b64))
    else:
        raise ValueError("subí un archivo, pegá una ruta o un link de Drive")
    t = _trabajo_nuevo(tid, nombre, str(origen), subido=bool(b64))
    try:
        return _analizar(t, origen)
    except ValueError:
        if b64:
            origen.unlink(missing_ok=True)
        raise


# ───────────────────────────────────────────────────────────── preparar

def _validar_recorte(recorte: str, w: int, h: int) -> str:
    recorte = (recorte or "").strip()
    if not recorte:
        return ""
    m = re.fullmatch(r"(\d+):(\d+):(\d+):(\d+)", recorte)
    if not m:
        raise ValueError("el recorte va como ancho:alto:x:y, por ejemplo 704:576:12:32")
    cw, ch, cx, cy = (int(x) for x in m.groups())
    if cw <= 0 or ch <= 0 or cx + cw > w or cy + ch > h:
        raise ValueError(f"el recorte {recorte} no entra en {w}×{h}")
    return recorte


def fijar_opciones(tid: str, **op) -> dict:
    t = trabajo(tid)
    if t["estado"] in ACTIVOS:
        raise RuntimeError("el trabajo está en curso; esperá a que termine")
    if not t.get("sonda"):
        raise RuntimeError("este trabajo todavía no tiene el archivo (la descarga no terminó)")
    s = t["sonda"]
    o = dict(t["opciones"])
    if "recorte" in op:
        o["recorte"] = _validar_recorte(op["recorte"], s["w"], s["h"])
    if "inicio" in op:
        o["inicio"] = max(0.0, float(op["inicio"] or 0))
    if "fin" in op:
        f = op["fin"]
        o["fin"] = None if f in (None, "", 0) else float(f)
        if o["fin"] is not None and o["fin"] <= o["inicio"] + 1:
            raise ValueError("el fin tiene que ser al menos 1 s después del inicio")
        if o["fin"] is not None and o["fin"] > s["dur"] + 0.5:
            o["fin"] = None
    if "desentrelazar" in op:
        o["desentrelazar"] = bool(op["desentrelazar"])
    if "campo" in op and op["campo"] in ("auto", "tff", "bff"):
        o["campo"] = op["campo"]
    if "variante" in op and op["variante"] in FACTOR_GPU:
        o["variante"] = op["variante"]
    t["opciones"] = o
    return guardar(t)


def segundos_pedidos(t: dict) -> float:
    o = t["opciones"]
    fin = o["fin"] if o.get("fin") else t["sonda"]["dur"]
    return max(0.0, fin - o["inicio"])


def preparar(tid: str, log=print) -> dict:
    """La fuente que ve el modelo: recorte + desentrelazado + x264 casi sin
    pérdida en 4:2:2 + audio estéreo. Corre como tarea (un capítulo tarda)."""
    t = trabajo(tid)
    s, o = t["sonda"], t["opciones"]
    (DIR / "fuentes").mkdir(parents=True, exist_ok=True)
    fuente = DIR / "fuentes" / f"{tid}.mp4"
    vf = []
    if o.get("recorte"):
        vf.append("crop=" + o["recorte"].replace(":", ":", 3))
    if o.get("desentrelazar"):
        par = o.get("campo") if o.get("campo") in ("tff", "bff") else "auto"
        vf.append(f"bwdif=mode=send_frame:parity={par}:deint=all")
    vf.append("format=yuv422p")
    args = []
    if o["inicio"] > 0:
        args += ["-ss", f"{o['inicio']:.3f}"]
    args += ["-i", t["origen"]]
    if o.get("fin"):
        args += ["-t", f"{o['fin'] - o['inicio']:.3f}"]
    args += ["-vf", ",".join(vf), "-c:v", "libx264", "-preset", "medium", "-crf", "8", "-pix_fmt", "yuv422p"]
    if s["canales"] >= 2:
        args += ["-af", "pan=stereo|c0=c0|c1=c1", "-c:a", "aac", "-b:a", "256k", "-ar", "48000"]
    elif s["canales"] == 1:
        args += ["-af", "pan=stereo|c0=c0|c1=c0", "-c:a", "aac", "-b:a", "256k", "-ar", "48000"]
    else:
        args += ["-an"]
    args += ["-map_metadata", "-1", "-movflags", "+faststart", str(fuente)]
    log(f"preparando {t['nombre']}: {' '.join(vf)} · {segundos_pedidos(t):.1f} s")
    actualizar(tid, estado="preparando", nota="")
    _ffmpeg(*args, log=log)
    sf = sondear(fuente)
    hoja = DIR / "hojas" / f"{tid}-fuente.jpg"
    _hoja(fuente, sf["dur"], hoja)
    cuadros = int(round(sf["dur"] * sf["fps"]))
    t = actualizar(tid, estado="preparado", fuente=f"fuentes/{fuente.name}", hoja_fuente=f"hojas/{hoja.name}",
                   segundos_fuente=round(sf["dur"], 3), cuadros=cuadros, sonda_fuente=sf,
                   final=dimensiones_finales(s, sf), progreso=None)
    log(f"fuente lista: {sf['w']}×{sf['h']} · {sf['dur']:.1f} s · {cuadros} cuadros · {fuente.stat().st_size / 1e6:.0f} MB · "
        f"final {t['final']['w']}×{t['final']['h']}")
    return t


def dimensiones_finales(s_origen: dict, s_fuente: dict) -> dict:
    """El tamaño de entrega: alto 2160 y el ancho que pide el aspecto de
    PANTALLA del origen (PAL tiene píxel no cuadrado: 704×576 se ve 4:3, así que
    el ×4 = 2816×2304 se lleva a 2880×2160; es corrección de aspecto, no
    estirado). Si el origen declara 16:9 anamórfico, sale 3840×2160."""
    w, h = s_fuente["w"], s_fuente["h"]
    dar = None
    if s_origen.get("dar"):
        a, b = (int(x) for x in s_origen["dar"].split(":"))
        if a and b:
            dar = a / b
    sd = s_origen["h"] in (480, 486, 576, 608) and s_origen["w"] in (704, 720)
    if sd and (dar is None or dar < 1.5):
        dar = 4 / 3
    elif sd and dar >= 1.5:
        dar = 16 / 9
    elif dar is None:
        dar = w / h
    H = 2160
    W = int(round(H * dar / 2) * 2)
    if W > 3840:
        W = 3840
        H = int(round(3840 / dar / 2) * 2)
    return {"w": W, "h": H, "dar": round(dar, 4), "x4": {"w": w * 4, "h": h * 4}}


# ───────────────────────────────────────────────────────────── ofertas y costo

def apta(o: vast.Oferta) -> tuple[bool, list[str]]:
    motivos = []
    if "A100" not in o.gpu.upper():
        motivos.append("no es A100")
    if o.vram_gb < VRAM_MIN_GB:
        motivos.append("menos de 80 GB")
    if o.verificacion != "verified":
        motivos.append("desverificada" if o.verificacion == "deverified" else "sin verificar")
    if o.dph > PRECIO_MAX:
        motivos.append(f"> ${PRECIO_MAX}/h")
    if o.fiabilidad < FIABILIDAD_MIN:
        motivos.append(f"fiabilidad < {FIABILIDAD_MIN}")
    if maquina.china_continental(o.geo):
        motivos.append("China continental")
    if o.inet_down < INET_MIN:
        motivos.append(f"enlace < {INET_MIN} Mbps")
    return not motivos, motivos


def ofertas(solo_aptas: bool = False) -> list[dict]:
    """A100 de 80 GB, 1 placa. La licencia de H3 no aplica (FlashVSR es Apache):
    entran EE.UU. y la UE, que es donde están casi todas."""
    lista = vast.buscar(gpus=1, vram_gb=VRAM_MIN_GB, disco_gb=DISCO_GB, inet_mbps=INET_MIN,
                        fiabilidad=FIABILIDAD_MIN, respetar_licencia=False, solo_verificadas=False)
    lista = [o for o in lista if "A100" in o.gpu.upper() or "H100" in o.gpu.upper()]
    out = []
    for o in lista:
        ok, motivos = apta(o)
        if solo_aptas and not ok:
            continue
        out.append({"id": o.id, "gpu": o.gpu, "vram_gb": o.vram_gb, "dph": round(o.dph, 3), "geo": o.geo,
                    "inet": round(o.inet_down), "fiabilidad": round(o.fiabilidad, 4), "verificacion": o.verificacion,
                    "apta": ok, "motivos": motivos, "_o": o})
    out.sort(key=lambda d: (not d["apta"], -round(d["fiabilidad"], 2), d["dph"]))
    return out


def mejor_oferta() -> vast.Oferta | None:
    """La apta de mayor fiabilidad; a igual fiabilidad (dos decimales), la más
    barata. El 18/9 la más barata que cumplía ($0,873, Oklahoma) anduvo bien."""
    for d in ofertas(solo_aptas=True):
        return d["_o"]
    return None


def estimar(segundos: float, dph: float, variante: str = "full") -> dict:
    """Minutos de máquina y dólares, antes de encender. Modelo: instalación fija +
    inferencia a `FACTOR_GPU` + codificación final (~1× tiempo real en CPU) +
    bajada. Tope = ×1,5 (un reintento de trozo, un host lento)."""
    f = FACTOR_GPU.get(variante, FACTOR_GPU["full"])
    seg_maquina = SETUP_SEG + segundos * f + segundos * 1.0 + 180
    costo = dph * seg_maquina / 3600
    return {"minutos": round(seg_maquina / 60), "minutos_inferencia": round(segundos * f / 60),
            "costo": round(costo, 2), "tope": round(costo * 1.5, 2), "dph": round(dph, 3), "factor": f}


def estimacion(tid: str) -> dict:
    t = trabajo(tid)
    seg = t.get("segundos_fuente") or segundos_pedidos(t)
    ofs = ofertas()
    mejor = next((d for d in ofs if d["apta"]), None)
    est = estimar(seg, mejor["dph"], t["opciones"]["variante"]) if mejor else estimar(seg, 1.0, t["opciones"]["variante"])
    for d in ofs:
        d.pop("_o", None)
        d["estimado"] = estimar(seg, d["dph"], t["opciones"]["variante"])["costo"]
    return {"segundos": round(seg, 1), "estimado": est, "mejor": mejor, "ofertas": ofs[:12], "saldo": vast.saldo()}


# ───────────────────────────────────────────────────────────── ssh de bajo nivel

def _ssh(inst: dict, cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    """Como vast.ejecutar pero devolviendo el código y decodificando con
    `errors="replace"`: los logs traen barras de progreso y el 18/9 `text=True`
    reventó en Windows con cp1252."""
    _h, p, u = vast._ssh_args(inst)
    r = subprocess.run(["ssh", "-p", p, "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=25", u, cmd],
                       capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def _scp_desde(inst: dict, remoto: str, local: Path, timeout: int = 4 * 3600) -> tuple[int, str]:
    _h, p, u = vast._ssh_args(inst)
    local.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["scp", "-P", p, "-o", "StrictHostKeyChecking=accept-new", f"{u}:{remoto}", str(local)],
                       capture_output=True, timeout=timeout)
    return r.returncode, r.stderr.decode("utf-8", "replace")[-300:]


def _esperar_marca(inst: dict, archivo: str, ok: str, fallo: str, minutos: float, log,
                   avance: str | None = None, al_avance=None, cada: int = 30) -> bool:
    """Espera a que un log remoto tenga la marca `ok` o `fallo`. Con `grep -F`:
    «[listo]» como expresión regular es una clase de caracteres y el 18/9 el
    driver nunca vio el Traceback. Los marcadores son texto literal."""
    t0 = time.time()
    ultimo = ""
    while time.time() - t0 < minutos * 60:
        rc, out, err = _ssh(inst, f"grep -a -F -e '{ok}' -e '{fallo}' {archivo} 2>/dev/null | tail -2; "
                                  + (f"grep -a -E '{avance}' {archivo} 2>/dev/null | tail -1" if avance else "true"), timeout=90)
        out = out.strip()
        if out and out != ultimo:
            log("   " + out.replace("\n", " | ")[:300])
            ultimo = out
            if al_avance:
                try:
                    al_avance(out)
                except Exception:
                    pass
        if ok in out and fallo not in out:
            return True
        if fallo in out:
            return False
        time.sleep(cada)
    log(f"   tiempo límite de {minutos:.0f} min esperando {archivo}")
    return False


# ───────────────────────────────────────────────────────────── correr

def _progreso(tid: str, fase: str, hechos: int | None = None, total: int | None = None, ultimo: str = ""):
    t = trabajo(tid)
    p = t.get("progreso") or {}
    p.update(fase=fase, ultimo=ultimo[-220:], t=time.time())
    if hechos is not None:
        p["hechos"] = hechos
    if total:
        p["total"] = total
    if p.get("total") and p.get("hechos") is not None:
        p["pct"] = min(99, int(p["hechos"] / p["total"] * 100))
    actualizar(tid, progreso=p)


def _fallar(tid: str, nota: str, log, destruir_iid: int | None = None):
    log("!! " + nota)
    if destruir_iid:
        try:
            vast.destruir(destruir_iid, confirmar=True)
            log(f"instancia {destruir_iid} destruida")
        except Exception as e:
            log(f"destruir falló: {e}")
        m = leer_maquina()
        g = gasto(m)
        escribir_maquina(fase="apagada", fin=time.time(), gasto_final=g["acumulado"], error=nota)
        t = trabajo(tid)
        t.setdefault("costo", {})["real"] = g["acumulado"]
        guardar(t)
    else:
        escribir_maquina(fase="fallo", fin=time.time(), error=nota)
    actualizar(tid, estado="error", nota=nota, progreso=None)


def correr(tid: str, oferta_id: int | None = None, log=print) -> bool:
    """Todo el camino con plata, desatendido: alquilar → instalar → subir →
    inferir → codificar → bajar → destruir → QC. Devuelve True si terminó con el
    4K bajado. Cualquier fallo destruye la instancia, salvo que la salida ya
    esté hecha y no se pueda bajar: ahí la deja viva (estado `sin_bajar`)."""
    t = trabajo(tid)
    if not t.get("fuente") or not (DIR / t["fuente"]).exists():
        _fallar(tid, "la fuente no está preparada", log)
        return False
    m = leer_maquina()
    if m.get("fase") not in ("apagada", "fallo"):
        _fallar(tid, f"ya hay una A100 en fase {m.get('fase')} (instancia {m.get('instancia')}); apagala primero", log)
        return False
    d = vast.diagnostico_ssh()
    log("SSH del servidor: " + json.dumps(d, ensure_ascii=False))
    if not (d["privada_valida"] and d["publica_coincide"]):
        _fallar(tid, f"la clave SSH de este servidor no sirve ({d['error']}); no alquilo nada", log)
        return False
    fuente = DIR / t["fuente"]
    seg = float(t["segundos_fuente"])
    cuadros = int(t["cuadros"] or round(seg * 25))
    variante = t["opciones"].get("variante", "full")

    # 1 · la oferta
    actualizar(tid, estado="alquilando", nota="", progreso={"fase": "alquilando", "t": time.time()})
    escribir_maquina(fase="buscando", instancia=None, trabajo=tid, fin=None, gasto_final=None, error=None)
    oferta = None
    if oferta_id:
        oferta = next((x["_o"] for x in ofertas() if x["id"] == int(oferta_id)), None)
        if oferta is None:
            log(f"la oferta {oferta_id} ya no está; busco la mejor apta")
    if oferta is None:
        try:
            oferta = mejor_oferta()
        except Exception as e:
            _fallar(tid, f"no pude consultar las ofertas: {e}", log)
            return False
    if oferta is None:
        _fallar(tid, "no hay ninguna A100 de 80 GB apta ahora (verificada, ≤ $1,30/h, fuera de China); probá más tarde", log)
        return False
    est = estimar(seg, oferta.dph, variante)
    log(f"ALQUILANDO {oferta.id} · {oferta.gpu} {oferta.vram_gb:.0f} GB · {oferta.geo} · ${oferta.dph:.3f}/h · "
        f"{oferta.inet_down:.0f} Mbps · fiab {oferta.fiabilidad:.3f} · estimado ${est['costo']} ({est['minutos']} min)")
    try:
        r = vast.crear_con_imagen(oferta.id, imagen=IMAGEN, confirmar=True, disco_gb=DISCO_GB, etiqueta=ETIQUETA)
    except Exception as e:
        _fallar(tid, f"Vast no alquiló: {e}", log)
        return False
    iid = int(r.get("new_contract") or r.get("id"))
    t0 = time.time()
    escribir_maquina(fase="arrancando", instancia=iid, dph=float(oferta.dph), inicio=t0, fin=None, gasto_final=None,
                     trabajo=tid, error=None,
                     oferta={"id": oferta.id, "geo": oferta.geo, "gpu": oferta.gpu, "vram_gb": oferta.vram_gb,
                             "inet": round(oferta.inet_down), "fiabilidad": round(oferta.fiabilidad, 4)})
    t = actualizar(tid, estado="arrancando", instancia=iid, costo={**t.get("costo", {}), "estimado": est["costo"], "tope": est["tope"], "dph": oferta.dph})
    log(f"instancia {iid} creada; cobrando desde ahora")

    exito = False
    dejar_viva = False
    try:
        try:
            vast.autorizar_clave(iid)
        except Exception as e:
            log(f"autorizar clave: {e}")
        try:
            inst = vast.esperar_lista(iid, minutos=20, log=log)
        except Exception as e:
            _fallar(tid, f"no arrancó en 20 min: {e}", log, destruir_iid=iid)
            return False

        # 2 · instalar (y mientras, subir la fuente)
        escribir_maquina(fase="instalando")
        actualizar(tid, estado="instalando")
        _progreso(tid, "instalando", 0, 1, "subiendo los scripts")
        for n in ("setup-flashvsr.sh", "infer_trozos.py", "post_remoto.sh"):
            vast.subir(inst, SCRIPTS / n, REMOTO + "/", log=log)
        _ssh(inst, f"sed -i 's/\\r$//' {REMOTO}/*.sh {REMOTO}/*.py; chmod +x {REMOTO}/*.sh")
        vast.lanzar(inst, f"bash {REMOTO}/setup-flashvsr.sh", log="/root/setup.log")
        log("instalación lanzada (FlashVSR + Block-Sparse-Attention + pesos, ~13 min)")
        _progreso(tid, "instalando", 0, 1, f"subiendo la fuente ({fuente.stat().st_size / 1e6:.0f} MB)")
        vast.subir(inst, fuente, REMOTO + "/", log=log)
        log("fuente subida")
        if not _esperar_marca(inst, "/root/setup.log", "SETUP_OK", "SETUP_FALLO", LIMITE_SETUP_MIN, log,
                              avance="BSA build rc|bsa OK|diffsynth OK|PESOS_FIN",
                              al_avance=lambda s: _progreso(tid, "instalando", 0, 1, s)):
            rc, out, _ = _ssh(inst, "tail -n 25 /root/setup.log | cut -c1-200")
            log(out)
            _fallar(tid, "la instalación falló (mirá el log de la tarea)", log, destruir_iid=iid)
            return False
        log(f"instalación OK a los {(time.time() - t0) / 60:.0f} min")

        # 3 · inferir
        escribir_maquina(fase="remasterizando")
        actualizar(tid, estado="remasterizando")
        _progreso(tid, "remasterizando", 0, cuadros, "cargando el modelo")
        cmd = (f"cd /workspace/FlashVSR/examples/WanVSR && cp {REMOTO}/infer_trozos.py . && "
               f"PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True {PY} infer_trozos.py "
               f"{REMOTO}/{fuente.name} {REMOTO}/cruda.mp4 --cuadros {cuadros}")
        vast.lanzar(inst, cmd, log="/root/infer.log")
        limite = max(90.0, est["minutos_inferencia"] * 2.5)
        log(f"inferencia lanzada · {cuadros} cuadros · estimado {est['minutos_inferencia']} min · límite {limite:.0f} min")

        def avance_infer(s: str):
            m = re.search(r"escritos (\d+)/(\d+)", s)
            if m:
                _progreso(tid, "remasterizando", int(m.group(1)), int(m.group(2)), s.split("|")[-1].strip())
            else:
                _progreso(tid, "remasterizando", None, None, s.split("|")[-1].strip())

        if not _esperar_marca(inst, "/root/infer.log", "[listo]", "Traceback", limite, log,
                              avance=r"\[trozo|\[entrada\]|\[tiempo\]", al_avance=avance_infer):
            rc, out, _ = _ssh(inst, "grep -a -v -E 'it/s' /root/infer.log | tail -n 30 | cut -c1-220")
            log(out)
            _fallar(tid, "la inferencia falló o pasó el tiempo límite (mirá el log de la tarea)", log, destruir_iid=iid)
            return False
        rc, out, _ = _ssh(inst, r"grep -a -E '\[trozo|\[listo\]' /root/infer.log | cut -c1-220")
        log("resumen:\n" + out)
        min_gpu = (time.time() - t0) / 60
        log(f"inferencia OK a los {min_gpu:.0f} min de máquina")

        # 4 · codificar el final en la máquina (la cruda pesa demasiado para bajarla)
        escribir_maquina(fase="codificando")
        actualizar(tid, estado="codificando")
        fin = t["final"] or dimensiones_finales(t["sonda"], t.get("sonda_fuente") or t["sonda"])
        _progreso(tid, "codificando", 0, cuadros, f"x264 a {fin['w']}×{fin['h']}")
        vast.lanzar(inst, f"bash {REMOTO}/post_remoto.sh {REMOTO}/cruda.mp4 {REMOTO}/{fuente.name} {fin['w']} {fin['h']} {CRF_FINAL} {REMOTO}/final.mp4",
                    log="/root/post.log")
        lim_post = max(30.0, seg / 60 * 3)

        def avance_post(_s: str):
            rc2, pr, _ = _ssh(inst, "grep -a '^frame=' /root/post-progreso.txt 2>/dev/null | tail -1", timeout=60)
            m = re.search(r"frame=(\d+)", pr)
            if m:
                _progreso(tid, "codificando", int(m.group(1)), cuadros, f"cuadro {m.group(1)} de {cuadros}")

        # el log de post casi no escribe: el avance sale del archivo -progress
        t_post = time.time()
        ok_post = False
        while time.time() - t_post < lim_post * 60:
            rc, out, _ = _ssh(inst, "grep -a -F -e POST_OK -e POST_FALLO /root/post.log 2>/dev/null | tail -1", timeout=60)
            if "POST_OK" in out:
                ok_post = True
                break
            if "POST_FALLO" in out:
                break
            avance_post("")
            time.sleep(20)
        if not ok_post:
            rc, out, _ = _ssh(inst, "tail -n 12 /root/post.log; tail -n 5 /root/post-ffmpeg.err 2>/dev/null")
            log(out)
            _fallar(tid, "la codificación final falló", log, destruir_iid=iid)
            return False
        log(f"final codificado a los {(time.time() - t0) / 60:.0f} min")

        # 5 · bajar
        escribir_maquina(fase="bajando")
        actualizar(tid, estado="bajando")
        _progreso(tid, "bajando", None, None, "scp del 4K")
        (DIR / "salidas").mkdir(exist_ok=True)
        (DIR / "logs").mkdir(exist_ok=True)
        local = DIR / "salidas" / f"{tid}-4K.mp4"
        rc, err = _scp_desde(inst, f"{REMOTO}/final.mp4", local)
        if rc or not local.exists() or local.stat().st_size < 1e6:
            log(f"scp falló ({err}); reintento")
            rc, err = _scp_desde(inst, f"{REMOTO}/final.mp4", local)
        _scp_desde(inst, "/root/infer.log", DIR / "logs" / f"{tid}-infer.log", timeout=300)
        if not (local.exists() and local.stat().st_size > 1e6):
            dejar_viva = True
            escribir_maquina(fase="lista", error="la salida está en la máquina pero no se pudo bajar")
            actualizar(tid, estado="sin_bajar", nota="el 4K está hecho en la máquina pero la bajada falló; "
                       "tocá «bajar de nuevo» (la máquina sigue cobrando) o «apagar» para perderlo", progreso=None)
            log("!! NO se pudo bajar la salida; dejo la instancia viva para reintentar")
            return False
        log(f"bajado {local.name}: {local.stat().st_size / 1e6:.0f} MB")
        exito = True
    except Exception as e:
        log(f"ERROR: {e!r}")
        actualizar(tid, nota=f"error inesperado: {e}")
    finally:
        if not dejar_viva:
            try:
                vast.destruir(iid, confirmar=True)
                g = gasto(leer_maquina())
                escribir_maquina(fase="apagada", fin=time.time(), gasto_final=g["acumulado"], trabajo=None)
                t = trabajo(tid)
                t.setdefault("costo", {})["real"] = g["acumulado"]
                t["costo"]["minutos"] = g["minutos"]
                guardar(t)
                log(f"instancia {iid} destruida · {g['minutos']} min · ${g['acumulado']} · saldo {vast.saldo()}")
            except Exception as e:
                log(f"destruir falló: {e}")
    if not exito:
        if trabajo(tid)["estado"] not in ("error", "sin_bajar"):
            actualizar(tid, estado="error", progreso=None)
        return False
    # factor medido de esta corrida, para el estimador de la próxima
    t = trabajo(tid)
    t["costo"]["factor_medido"] = round((t["costo"]["minutos"] * 60 - SETUP_SEG) / max(seg, 1), 1)
    t["salidas"] = {"4k": f"salidas/{tid}-4K.mp4"}
    t["estado"] = "qc"
    guardar(t)
    try:
        qc(tid, log=log)
    except Exception as e:
        log(f"QC falló: {e}")
    actualizar(tid, estado="listo", terminado=time.time(), progreso=None)
    return True


def bajar_de_nuevo(tid: str, log=print) -> bool:
    t = trabajo(tid)
    m = leer_maquina()
    if not m.get("instancia"):
        _fallar(tid, "no hay máquina viva de la que bajar", log)
        return False
    inst = vast.instancia(int(m["instancia"]))
    local = DIR / "salidas" / f"{tid}-4K.mp4"
    actualizar(tid, estado="bajando")
    rc, err = _scp_desde(inst, f"{REMOTO}/final.mp4", local)
    if not (local.exists() and local.stat().st_size > 1e6):
        actualizar(tid, estado="sin_bajar", nota=f"la bajada volvió a fallar: {err}")
        return False
    log(f"bajado {local.name}: {local.stat().st_size / 1e6:.0f} MB")
    apagar(log=log)
    t = trabajo(tid)
    t["salidas"] = {"4k": f"salidas/{tid}-4K.mp4"}
    t["estado"] = "qc"
    guardar(t)
    qc(tid, log=log)
    actualizar(tid, estado="listo", terminado=time.time(), nota="", progreso=None)
    return True


# ───────────────────────────────────────────────────────────── qc y uhd

def qc(tid: str, log=print, n: int = 6) -> list[str]:
    """Pares antes/después en `n` instantes (origen escalado con `neighbor`, para
    ver los píxeles tal cual, contra el 4K) y dos recortes con zoom ×3 al centro:
    es donde se ve cualquier invento del modelo (caras lejanas)."""
    t = trabajo(tid)
    fuente = DIR / t["fuente"]
    final = DIR / t["salidas"]["4k"]
    (DIR / "qc").mkdir(exist_ok=True)
    dur = float(t["segundos_fuente"])
    salidas = []
    for k in range(n):
        ti = dur * (k + 0.5) / n
        out = DIR / "qc" / f"{tid}-par{k + 1}.jpg"
        _ffmpeg("-ss", f"{ti:.3f}", "-i", str(fuente), "-ss", f"{ti:.3f}", "-i", str(final),
                "-filter_complex", "[0:v]scale=-2:720:flags=neighbor[a];[1:v]scale=-2:720:flags=lanczos[b];[a][b]hstack",
                "-frames:v", "1", "-q:v", "3", str(out), timeout=600)
        salidas.append(f"qc/{out.name}")
    for k, frac in enumerate((0.3, 0.7)):
        ti = dur * frac
        out = DIR / "qc" / f"{tid}-zoom{k + 1}.jpg"
        _ffmpeg("-ss", f"{ti:.3f}", "-i", str(fuente), "-ss", f"{ti:.3f}", "-i", str(final),
                "-filter_complex", "[0:v]crop=iw/3:ih/3:iw/3:ih/6,scale=-2:720:flags=neighbor[a];"
                                   "[1:v]crop=iw/3:ih/3:iw/3:ih/6,scale=-2:720:flags=lanczos[b];[a][b]hstack",
                "-frames:v", "1", "-q:v", "3", str(out), timeout=600)
        salidas.append(f"qc/{out.name}")
    actualizar(tid, qc=salidas)
    log(f"QC: {len(salidas)} imágenes")
    return salidas


def uhd(tid: str, log=print) -> dict:
    """3840×2160 con barras negras a partir del 4K ya bajado. Local y gratis."""
    t = trabajo(tid)
    final = DIR / t["salidas"]["4k"]
    out = DIR / "salidas" / f"{tid}-UHD.mp4"
    fin = t["final"]
    log(f"UHD: {fin['w']}×{fin['h']} → 3840×2160 con barras")
    _ffmpeg("-i", str(final), "-vf", "pad=3840:2160:(ow-iw)/2:(oh-ih)/2:black,setsar=1", "-c:v", "libx264",
            "-preset", "medium", "-crf", str(CRF_FINAL), "-c:a", "copy", "-movflags", "+faststart", str(out), log=log)
    t = trabajo(tid)
    t["salidas"]["uhd"] = f"salidas/{out.name}"
    return guardar(t)


def borrar(tid: str) -> None:
    t = trabajo(tid)
    if t["estado"] in ACTIVOS or t["estado"] == "sin_bajar":
        raise RuntimeError("el trabajo está en curso")
    for k in ("fuente", "hoja", "hoja_fuente"):
        if t.get(k):
            (DIR / t[k]).unlink(missing_ok=True)
    for v in (t.get("salidas") or {}).values():
        (DIR / v).unlink(missing_ok=True)
    for v in t.get("qc") or []:
        (DIR / v).unlink(missing_ok=True)
    if t.get("subido") and t.get("origen"):
        Path(t["origen"]).unlink(missing_ok=True)
    _escribir([x for x in _leer() if x["id"] != tid])


def refrescar() -> list[dict]:
    """Los trabajos, cerrando los que quedaron «activos» sin tarea viva (el
    servidor se reinició a mitad de una corrida)."""
    from . import tareas
    ts = _leer()
    if any(t["estado"] in ACTIVOS for t in ts) and not tareas.corriendo("_remaster"):
        m = leer_maquina()
        for t in ts:
            if t["estado"] in ACTIVOS and t["estado"] != "preparando":
                if m.get("fase") not in ("apagada", "fallo") and m.get("trabajo") == t["id"]:
                    t.update(nota="la tarea que la seguía murió; la máquina puede seguir viva: apagala si no la vas a rescatar")
                t.update(estado="error", nota=t.get("nota") or "la tarea murió (¿se reinició el servidor?)", progreso=None)
            elif t["estado"] == "preparando":
                t.update(estado="origen", nota="la preparación se cortó; volvé a prepararla")
            elif t["estado"] == "descargando":
                t.update(estado="error", nota="la descarga se cortó; «reintentar descarga» la retoma donde quedó", progreso=None)
        _escribir(ts)
    return trabajos()
