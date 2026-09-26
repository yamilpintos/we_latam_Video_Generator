"""Mide un video: cortes, largo de cada plano, escala de plano (cuán cerca está
la cara), cuánto se mueve la imagen dentro del plano, y cuánto cambia el color
de un plano al siguiente. Sirve igual para los videos de referencia y para los
nuestros, así la comparación es la misma regla para todos.

    python analizar_video.py <video.mp4> [salida.json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

FF = r"C:\Users\Yamil\Desktop\youtube proyect\.venv-depthflow\Scripts\ffmpeg.exe"
YUNET = Path(__file__).with_name("yunet.onnx")
ANCHO, ALTO, FPS = 320, 180, 8          # tira chica para movimiento y color
UMBRAL_CORTE = 0.30                     # escena nueva según ffmpeg


def meta(v: Path) -> dict:
    c = cv2.VideoCapture(str(v))
    f = c.get(cv2.CAP_PROP_FPS) or 0
    n = c.get(cv2.CAP_PROP_FRAME_COUNT) or 0
    d = {"ancho": int(c.get(cv2.CAP_PROP_FRAME_WIDTH)), "alto": int(c.get(cv2.CAP_PROP_FRAME_HEIGHT)),
         "fps": round(f, 3), "dur": round(n / f, 2) if f else 0.0}
    c.release()
    return d


def cortes(v: Path, dur: float) -> list[float]:
    r = subprocess.run([FF, "-hide_banner", "-i", str(v), "-vf",
                        f"select='gt(scene,{UMBRAL_CORTE})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True, errors="replace")
    t = sorted({round(float(m.group(1)), 2) for m in re.finditer(r"pts_time:([\d.]+)", r.stderr)})
    return [x for x in t if 0.25 < x < dur - 0.25]


def tira(v: Path) -> np.ndarray:
    """Todo el video como cuadros chicos en gris + color, a FPS bajo."""
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-i", str(v),
                        "-vf", f"scale={ANCHO}:{ALTO},fps={FPS}", "-pix_fmt", "bgr24",
                        "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    n = len(a) // (ANCHO * ALTO * 3)
    return a[: n * ANCHO * ALTO * 3].reshape(n, ALTO, ANCHO, 3)


def caras(v: Path, tiempos: list[float], ancho: int, alto: int) -> list[dict]:
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (ancho, alto), 0.6, 0.3, 5000)
    cap = cv2.VideoCapture(str(v))
    out = []
    for t in tiempos:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            out.append({"caras": 0, "alto_cara": 0.0})
            continue
        _, f = det.detect(fr)
        cajas = [] if f is None else [x for x in f]
        out.append({"caras": len(cajas),
                    "alto_cara": round(max((float(x[3]) / alto for x in cajas), default=0.0), 3)})
    cap.release()
    return out


def escala(h: float, n: int) -> str:
    if n == 0:
        return "sin gente"
    if h >= 0.28:
        return "primer plano"
    if h >= 0.14:
        return "plano medio"
    if h >= 0.06:
        return "plano general"
    return "plano lejano"


def analizar(v: Path) -> dict:
    m = meta(v)
    cs = cortes(v, m["dur"])
    bordes = [0.0] + cs + [m["dur"]]
    planos = [(a, b) for a, b in zip(bordes, bordes[1:]) if b - a > 0.2]
    t = tira(v)
    gris = t.mean(axis=3)
    # movimiento cuadro a cuadro, normalizado 0-100
    dif = np.abs(np.diff(gris, axis=0)).mean(axis=(1, 2)) if len(t) > 1 else np.zeros(1)
    medios = [round((a + b) / 2, 2) for a, b in planos]
    cr = caras(v, medios, m["ancho"], m["alto"])
    fila = []
    for (a, b), c in zip(planos, cr):
        i, j = int(a * FPS), max(int(a * FPS) + 1, int(b * FPS))
        seg = t[i:j]
        mov = float(dif[i:max(i + 1, j - 1)].mean()) if j - 1 > i else 0.0
        fila.append({"ini": round(a, 2), "dur": round(b - a, 2),
                     "caras": c["caras"], "alto_cara": c["alto_cara"],
                     "escala": escala(c["alto_cara"], c["caras"]),
                     "movimiento": round(mov, 2),
                     "color": [round(float(x), 1) for x in seg.reshape(-1, 3).mean(axis=0)] if len(seg) else [0, 0, 0],
                     "brillo": round(float(seg.mean()), 1) if len(seg) else 0.0})
    # salto de color entre planos seguidos: mide si la paleta se mantiene
    saltos = [round(float(np.abs(np.array(x["color"]) - np.array(y["color"])).mean()), 1)
              for x, y in zip(fila, fila[1:])]
    d = [x["dur"] for x in fila]
    esc = {}
    for x in fila:
        esc[x["escala"]] = esc.get(x["escala"], 0) + 1
    return {"archivo": v.name, **m, "planos": len(fila),
            "corte_promedio": round(float(np.mean(d)), 2) if d else 0,
            "corte_mediana": round(float(np.median(d)), 2) if d else 0,
            "corte_min": round(min(d), 2) if d else 0, "corte_max": round(max(d), 2) if d else 0,
            "movimiento_promedio": round(float(np.mean([x["movimiento"] for x in fila])), 2) if fila else 0,
            "movimiento_mediana": round(float(np.median([x["movimiento"] for x in fila])), 2) if fila else 0,
            "salto_color_promedio": round(float(np.mean(saltos)), 1) if saltos else 0,
            "escalas": esc, "detalle": fila}


if __name__ == "__main__":
    v = Path(sys.argv[1])
    r = analizar(v)
    sal = Path(sys.argv[2]) if len(sys.argv) > 2 else v.with_suffix(".medida.json")
    sal.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: x for k, x in r.items() if k != "detalle"}, ensure_ascii=False, indent=1))
