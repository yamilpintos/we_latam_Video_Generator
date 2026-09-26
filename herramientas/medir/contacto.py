"""Hoja de contacto: un cuadro por plano, en grillas de 5x4, para mirar la
continuidad visual de un tiro. python contacto.py <medida.json> <video> <prefijo>"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

med = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
v, pre = Path(sys.argv[2]), Path(sys.argv[3])
COLS, FILAS, W = 5, 4, 384
cap = cv2.VideoCapture(str(v))
H = int(W * med["alto"] / med["ancho"])
imgs = []
for p in med["detalle"]:
    cap.set(cv2.CAP_PROP_POS_MSEC, (p["ini"] + p["dur"] / 2) * 1000)
    ok, fr = cap.read()
    im = cv2.resize(fr, (W, H)) if ok else np.zeros((H, W, 3), np.uint8)
    cv2.putText(im, f'{int(p["ini"]//60)}:{int(p["ini"]%60):02d} {p["dur"]:.1f}s', (6, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 4)
    cv2.putText(im, f'{int(p["ini"]//60)}:{int(p["ini"]%60):02d} {p["dur"]:.1f}s', (6, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    imgs.append(im)
cap.release()
por = COLS * FILAS
for k in range(0, len(imgs), por):
    g = imgs[k:k + por]
    g += [np.zeros((H, W, 3), np.uint8)] * (por - len(g))
    hoja = np.vstack([np.hstack(g[i * COLS:(i + 1) * COLS]) for i in range(FILAS)])
    n = pre.parent / f"{pre.name}_{k // por + 1}.jpg"
    cv2.imwrite(str(n), hoja, [cv2.IMWRITE_JPEG_QUALITY, 72])
    print(n)
