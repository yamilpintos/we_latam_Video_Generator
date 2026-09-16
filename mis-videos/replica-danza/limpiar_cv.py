"""Borra subtítulos, placas y logo de un cuadro del original con OpenCV (inpaint).

    /c/Python314/python -X utf8 limpiar_cv.py T76 T77 T81      # → original/limpio/

Es el respaldo para los cuadros que Nano Banana rechaza (poses sensuales: la
limpieza pasa por el mismo filtro que la generación). Detecta el texto por lo
que es —blanco casi puro con borde oscuro— sólo en las franjas donde el original
lo pone (subtítulo en el tercio inferior, placa a la izquierda del centro, logo
en las esquinas) y rellena con INPAINT_TELEA. No toca nada fuera de esas franjas.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

AQUI = Path(__file__).resolve().parent
# (y0, y1, x0, x1) en el cuadro de 720×1280: el logo alterna entre arriba a la
# izquierda (41 tomas) y abajo a la derecha (41), medido sobre una grilla el 15/9.
LOGO = [(74, 156, 52, 130), (1118, 1198, 586, 666)]


def limpiar(src: Path, dst: Path, placa: bool = False, solo_logo: bool = False) -> int:
    im = cv2.imread(str(src))
    h, w = im.shape[:2]
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    V, S = hsv[:, :, 2], hsv[:, :, 1]
    mask = np.zeros((h, w), bool)
    # Subtítulo: blanco casi puro, sólo en su franja.
    blanco = (V > 215) & (S < 40)
    zona = np.zeros((h, w), bool)
    zona[int(h * 0.62):int(h * 0.80), int(w * 0.08):int(w * 0.92)] = True
    if not solo_logo:
        mask |= blanco & zona
    # Placa de nombre: itálica blanca SEMITRANSPARENTE (V llega a ~190 sobre
    # fondo oscuro), así que no sirve el umbral fijo: se toma lo que sobresale
    # 45 niveles por encima de la mediana local.
    if placa and not solo_logo:
        local = cv2.medianBlur(V, 31).astype(int)
        sobresale = (V.astype(int) - local > 28) & (S < 90)
        zona = np.zeros((h, w), bool)
        zona[int(h * 0.36):int(h * 0.66), :] = True     # la placa va a la izquierda o a la derecha
        mask |= sobresale & zona
    mask = mask.astype(np.uint8) * 255
    # el borde oscuro del texto queda pegado al blanco: se engorda la máscara
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)), iterations=1)
    # Logo de la app: posición fija en una esquina y brillo variable (blanco sobre
    # cielo, gris sobre madera): no se detecta, se tapa siempre el rectángulo.
    # LOGO está medido en 720×1280; se escala al tamaño del cuadro (los de Nano
    # Banana vienen en 768×1344).
    fy, fx = h / 1280, w / 720
    for (y0, y1, x0, x1) in LOGO:
        mask[int(y0 * fy):int(y1 * fy), int(x0 * fx):int(x1 * fx)] = 255
    n = int((mask > 0).sum())
    out = cv2.inpaint(im, mask, 5, cv2.INPAINT_TELEA) if n else im
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), out)
    return n


if __name__ == "__main__":
    PLACAS = {"T04", "T19", "T30", "T33"}
    for k in sys.argv[1:]:
        # A limpio-cv/, no a limpio/: ahí escribe Nano Banana y no hay que pisarse.
        n = limpiar(AQUI / "original" / "crudo" / f"{k}.png", AQUI / "original" / "limpio-cv" / f"{k}.png",
                    placa=k in PLACAS)
        print(f"{k}: {n} píxeles rellenados")
