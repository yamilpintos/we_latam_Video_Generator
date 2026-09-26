"""Hoja de contacto por tiempo fijo, sin depender de detectar cortes.
    python muestreo.py <video> <prefijo> [segundos_entre_cuadros] [cols] [filas]"""
import sys
from pathlib import Path

import cv2
import numpy as np

v, pre = Path(sys.argv[1]), Path(sys.argv[2])
paso = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
COLS = int(sys.argv[4]) if len(sys.argv) > 4 else 6
FILAS = int(sys.argv[5]) if len(sys.argv) > 5 else 4
cap = cv2.VideoCapture(str(v))
fps = cap.get(cv2.CAP_PROP_FPS) or 30
dur = (cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) / fps
w0, h0 = cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
W = 300
H = int(W * h0 / w0)
imgs = []
t = 0.0
while t < dur:
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, fr = cap.read()
    if ok:
        im = cv2.resize(fr, (W, H))
        et = f"{int(t // 60)}:{int(t % 60):02d}"
        cv2.putText(im, et, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
        cv2.putText(im, et, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        imgs.append(im)
    t += paso
cap.release()
por = COLS * FILAS
for k in range(0, len(imgs), por):
    g = imgs[k:k + por] + [np.zeros((H, W, 3), np.uint8)] * (por - len(imgs[k:k + por]))
    hoja = np.vstack([np.hstack(g[i * COLS:(i + 1) * COLS]) for i in range(FILAS)])
    n = pre.parent / f"{pre.name}_{k // por + 1}.jpg"
    cv2.imwrite(str(n), hoja, [cv2.IMWRITE_JPEG_QUALITY, 70])
    print(n)
