"""Recorta todas las caras de los dibujos de un proyecto y las pone en una tira,
para ver de un vistazo cuánto deriva la identidad de dibujo en dibujo.

    python caras.py <carpeta de assets> <salida.jpg> [prefijo]
"""
import glob
import os
import sys
from pathlib import Path

import cv2
import numpy as np

YUNET = Path(__file__).with_name("yunet.onnx")
LADO = 190


def caras_de(f: str) -> list[np.ndarray]:
    im = cv2.imread(f)
    if im is None:
        return []
    h, w = im.shape[:2]
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.55, 0.3, 5000)
    _, caras = det.detect(im)
    out = []
    for c in (caras if caras is not None else []):
        x, y, cw, ch = (int(v) for v in c[:4])
        m = int(ch * 0.35)
        x0, y0 = max(0, x - m), max(0, y - m)
        x1, y1 = min(w, x + cw + m), min(h, y + ch + m)
        if x1 - x0 < 40 or y1 - y0 < 40:
            continue
        out.append((ch, cv2.resize(im[y0:y1, x0:x1], (LADO, LADO))))
    # la cara más grande primero: en nuestros planos es la del que habla
    return [im for _, im in sorted(out, key=lambda t: -t[0])]


A, SAL = sys.argv[1], sys.argv[2]
pre = sys.argv[3] if len(sys.argv) > 3 else "sb_"
archivos = sorted(glob.glob(os.path.join(A, pre + "*.png")),
                  key=lambda f: int("".join(ch for ch in os.path.basename(f) if ch.isdigit()) or 0))
fila = []
for f in archivos:
    cs = caras_de(f)
    n = os.path.basename(f)[:-4].replace("sb_", "")
    for k, c in enumerate(cs[:2]):
        c = c.copy()
        cv2.putText(c, n, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 4)
        cv2.putText(c, n, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        fila.append(c)
    print(f"{n}: {len(cs)} cara(s)")
COLS = 8
filas = []
for k in range(0, len(fila), COLS):
    g = fila[k:k + COLS] + [np.zeros((LADO, LADO, 3), np.uint8)] * (COLS - len(fila[k:k + COLS]))
    filas.append(np.hstack(g))
cv2.imwrite(SAL, np.vstack(filas), [cv2.IMWRITE_JPEG_QUALITY, 82])
print(SAL, f"· {len(fila)} caras")
