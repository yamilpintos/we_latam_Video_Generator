"""Cuántos ENCUADRES DISTINTOS tiene un video y cuánto dura cada uno.

Un corte duro entre dos imágenes casi iguales no se ve; lo que importa para la
continuidad es cuántas veces cambia de verdad lo que el espectador mira. Se
muestrea a 1 cuadro por segundo y se compara el histograma de color de cada uno
con el anterior: cuando la correlación cae, hay encuadre nuevo.

    python encuadres.py <video…>
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

FF = r"C:\Users\Yamil\Desktop\youtube proyect\.venv-depthflow\Scripts\ffmpeg.exe"
W, H = 160, 90
UMBRAL = 0.80          # correlación por debajo de esto = encuadre nuevo


def tira(v: Path) -> np.ndarray:
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-i", str(v),
                        "-vf", f"scale={W}:{H},fps=1", "-pix_fmt", "bgr24", "-f", "rawvideo", "-"],
                       capture_output=True)
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    n = len(a) // (W * H * 3)
    return a[: n * W * H * 3].reshape(n, H, W, 3).astype(np.float32)


def firma(f: np.ndarray) -> np.ndarray:
    """Histograma de color grueso + mapa de brillo en rejilla: sensible al
    encuadre y a la paleta, tolerante al movimiento dentro del plano."""
    h = np.concatenate([np.histogram(f[:, :, c], bins=12, range=(0, 255))[0] for c in range(3)])
    g = f.mean(axis=2)
    rej = g.reshape(6, H // 6, 8, W // 8).mean(axis=(1, 3)).ravel()
    x = np.concatenate([h / (h.sum() + 1e-6), rej / 255.0 * 0.5])
    return x / (np.linalg.norm(x) + 1e-6)


def analizar(v: Path) -> dict:
    t = tira(v)
    if len(t) < 3:
        return {}
    fs = np.array([firma(f) for f in t])
    cor = (fs[1:] * fs[:-1]).sum(axis=1)
    cambios = [0] + [i + 1 for i, c in enumerate(cor) if c < UMBRAL]
    dur = [b - a for a, b in zip(cambios, cambios[1:] + [len(t)])]
    return {"archivo": v.name, "segundos": len(t), "encuadres": len(dur),
            "seg_por_encuadre": round(len(t) / len(dur), 1),
            "mediana": float(np.median(dur)), "max": max(dur), "min": min(dur),
            "duraciones": dur}


if __name__ == "__main__":
    out = []
    for a in sys.argv[1:]:
        r = analizar(Path(a))
        if r:
            out.append(r)
            print(f'{r["archivo"][:44]:46s} {r["segundos"]:5d}s  {r["encuadres"]:4d} encuadres  '
                  f'{r["seg_por_encuadre"]:6.1f} s c/u  mediana {r["mediana"]:.0f}s  max {r["max"]}s')
    if out:
        e = [r["seg_por_encuadre"] for r in out]
        print(f"\npromedio del lote: {np.mean(e):.1f} s por encuadre")
