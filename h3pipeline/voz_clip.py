"""LA BOCA MANDA EL CORTE: medir dónde habla de verdad un clip de H3.

Los seis primeros shorts del mono (19/9) salieron con los diálogos cortados
porque el montaje recortaba cada clip donde decía el plan (`corta`), y H3
arranca a hablar recién al segundo y termina cuando termina. En la réplica de
«danza peligrosa» eso no pasó porque el corte seguía a la voz medida (REGLAS
48 y 63). Esto trae ese método a la web, sin librosa ni numpy (Render sólo
tiene Pillow): ffmpeg pasa el audio a 16 kHz mono filtrado a la banda de voz,
la energía se calcula en Python puro, y las palabras con sus tiempos vienen
del Whisper de OpenAI (`whisper-1`, verbose_json, palabra por palabra;
~$0,0005 por clip). Si la API falla, manda la energía sola.

    ini, fin = ventana(clip, "Buenas tardes, soy su piloto Monky.")

`ini` = arranque de la voz (energía, porque Whisper pone 0,0 a la primera
palabra cuando hay silencio antes); `fin` = fin de la N-ésima palabra de
Whisper (N = palabras de la línea), para no llevarse el balbuceo que a veces
sigue (T53, T55 de la réplica).
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
import wave
from array import array
from pathlib import Path

from . import config
from .prompts import IDIOMAS

API_TRANSCRIBIR = "https://api.openai.com/v1/audio/transcriptions"
MODELO = "whisper-1"
SR = 16000
PASO = 0.01            # s por ventana de energía
UMBRAL_DB = 18.0       # sobre el piso (percentil 20)
MIN_TRAMO = 0.06       # s
HUECO = 0.25           # s entre palabras que se unen


def _wav(clip: Path, destino: Path) -> None:
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(clip), "-vn",
                    "-af", "highpass=f=250,lowpass=f=4000", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(destino)],
                   check=True)


def _muestras(w: Path) -> list[int]:
    with wave.open(str(w), "rb") as f:
        datos = f.readframes(f.getnframes())
    a = array("h")
    a.frombytes(datos[: len(datos) - len(datos) % 2])
    return a.tolist()


def energia_db(muestras: list[int], paso: float = PASO) -> list[float]:
    n = max(1, int(SR * paso))
    out = []
    for i in range(0, len(muestras) - n + 1, n):
        s = 0
        for x in muestras[i:i + n]:
            s += x * x
        out.append(10 * math.log10(s / n + 1e-9))
    return out


def tramos_de_voz(e: list[float], paso: float = PASO) -> list[tuple[float, float]]:
    """[(ini, fin)] donde hay voz: UMBRAL_DB sobre el piso, ≥ MIN_TRAMO, huecos < HUECO unidos."""
    if not e:
        return []
    piso = sorted(e)[int(len(e) * 0.2)]
    on = [x > piso + UMBRAL_DB for x in e]
    out, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            if (j - i) * paso >= MIN_TRAMO:
                out.append((round(i * paso, 2), round(j * paso, 2)))
            i = j
        else:
            i += 1
    unidos: list[tuple[float, float]] = []
    for a, b in out:
        if unidos and a - unidos[-1][1] < HUECO:
            unidos[-1] = (unidos[-1][0], b)
        else:
            unidos.append((a, b))
    return unidos


def palabras(w: Path, idioma: str = "es", clave: str | None = None) -> list[tuple[str, float, float]]:
    """[(palabra, ini, fin)] por Whisper de OpenAI. Vacío si falla."""
    try:
        config.certificados()
        k = clave or config.leer_env("OPENAI_API_KEY")
    except Exception:
        return []
    if not k:
        return []
    borde = "----h3" + uuid.uuid4().hex
    campos = [("model", MODELO), ("response_format", "verbose_json"), ("timestamp_granularities[]", "word"),
              ("language", (idioma or "es")[:2])]
    cuerpo = b""
    for nombre, valor in campos:
        cuerpo += f"--{borde}\r\nContent-Disposition: form-data; name=\"{nombre}\"\r\n\r\n{valor}\r\n".encode()
    cuerpo += (f"--{borde}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{w.name}\"\r\n"
               "Content-Type: audio/wav\r\n\r\n").encode() + w.read_bytes() + f"\r\n--{borde}--\r\n".encode()
    req = urllib.request.Request(API_TRANSCRIBIR, data=cuerpo,
                                 headers={"Authorization": f"Bearer {k}", "Content-Type": f"multipart/form-data; boundary={borde}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
    except (urllib.error.URLError, OSError, ValueError):
        return []
    return [(str(x.get("word", "")).strip(), float(x.get("start", 0)), float(x.get("end", 0))) for x in d.get("words") or []]


def _n_palabras(texto: str) -> int:
    t = texto.split(":", 1)[1] if re.match(r"^\s*[^:\n]{1,40}:\s", texto) else texto
    return len(re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ']+", t))


def medir(clip: Path, dialogo: str | None = None, idioma: str = "es", cache: bool = True) -> dict:
    """{ini, fin, dur, tramos, palabras, fuente}. Con `dialogo` el fin se ajusta a
    la última palabra de la línea (o de todas las líneas si hay varias). Se
    guarda al lado del clip (`<clip>.voz.json`) para no pagar dos veces."""
    clip = Path(clip)
    guardado = clip.with_suffix(".voz.json")
    if cache and guardado.exists():
        try:
            v = json.loads(guardado.read_text(encoding="utf-8"))
            if v.get("dialogo") == (dialogo or "") and v.get("fin"):
                return v
        except Exception:
            pass
    tmp = Path(tempfile.mkdtemp(prefix="h3voz_")) / "a.wav"
    try:
        _wav(clip, tmp)
        m = _muestras(tmp)
        dur = len(m) / SR
        e = energia_db(m)
        tr = tramos_de_voz(e)
        w = palabras(tmp, idioma)
    finally:
        try:
            tmp.unlink()
            tmp.parent.rmdir()
        except OSError:
            pass
    lineas = [l for l in (dialogo or "").splitlines() if l.strip()]
    n_total = sum(_n_palabras(l) for l in lineas) or (len(w) if w else 0)
    fuente = "energía"
    if not tr and not w:
        ini, fin = 0.0, dur
        fuente = "nada"
    elif w:
        fuente = "whisper+energía" if tr else "whisper"
        fin_palabra = w[min(n_total, len(w)) - 1][2] if n_total else w[-1][2]
        w0 = w[0][1]
        if tr:
            cand = [a for a, b in tr if a <= w0 + 0.05] or [tr[0][0]]
            ini = cand[-1]
            if w0 > 0.3:
                ini = max(ini, w0 - 0.4)
            fin = max(fin_palabra, min(max([b for a, b in tr if a < fin_palabra] or [fin_palabra]), fin_palabra + 0.3))
        else:
            ini, fin = w0, fin_palabra
    else:
        ini, fin = tr[0][0], tr[-1][1]
    v = {"ini": round(max(0.0, ini), 2), "fin": round(min(dur, fin), 2), "dur": round(dur, 3), "tramos": tr,
         "palabras": [(p, round(a, 2), round(b, 2)) for p, a, b in w], "fuente": fuente, "dialogo": dialogo or ""}
    if cache:
        try:
            guardado.write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return v


def ventana(clip: Path, dialogo: str | None = None, idioma: str = "es") -> tuple[float, float]:
    v = medir(clip, dialogo, idioma)
    return v["ini"], v["fin"]


def lineas_en_tiempo(v: dict, dialogo: str) -> list[tuple[float, float, str]]:
    """Cada línea del diálogo con su (ini, fin) dentro del clip, repartiendo las
    palabras de Whisper por la cuenta de palabras de cada línea. Sin palabras,
    reparte el tramo hablado proporcionalmente."""
    lineas = [l for l in (dialogo or "").splitlines() if l.strip()]
    if not lineas:
        return []
    w = v.get("palabras") or []
    out, k = [], 0
    if w:
        for l in lineas:
            n = _n_palabras(l)
            if k >= len(w):
                out.append((v["fin"], v["fin"], l))
                continue
            j = min(len(w), k + max(1, n))
            out.append((w[k][1] if k else v["ini"], w[j - 1][2], l))
            k = j
        return out
    total = sum(_n_palabras(l) for l in lineas) or len(lineas)
    t = v["ini"]
    for l in lineas:
        d = (v["fin"] - v["ini"]) * (_n_palabras(l) or 1) / total
        out.append((round(t, 2), round(t + d, 2), l))
        t += d
    return out
