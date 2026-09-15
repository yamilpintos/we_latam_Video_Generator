# -*- coding: utf-8 -*-
"""Hojas de control: el cuadro del original al lado de nuestro primer fotograma.

Un par por ENCUADRE (la primera toma de cada uno): a la izquierda el cuadro
medio de esa toma en el original (`referencias/danza-peligrosa/cuadros/NNN-m.jpg`),
a la derecha `assets/sb_T…png` recortado a 9:16 como lo va a recibir H3 (a GPT
se le pierde ~14 % del ancho: lo que quede fuera del recorte no existe).

    /c/Python314/python -X utf8 mis-videos/replica-danza/revisar.py
    → revision/control-01.jpg …
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))
from tomas import TOMAS  # noqa: E402

CUADROS = AQUI / "../../referencias/danza-peligrosa/cuadros"
W, H, POR_HOJA = 300, 533, 8


def recorte_916(im):
    w, h = im.size
    nuevo = int(h * 9 / 16)
    x = (w - nuevo) // 2
    return im.crop((x, 0, x + nuevo, h))


def main():
    vistos, pares = set(), []
    for tid, a, b, tipo, loc, pers, k, que in TOMAS:
        if k in vistos:
            continue
        vistos.add(k)
        n = int("".join(c for c in tid if c.isdigit()))
        pares.append((tid, k, tipo, que, CUADROS / f"{n:03d}-m.jpg", AQUI / "assets" / f"sb_T{tid}.png"))
    salida = AQUI / "revision"
    salida.mkdir(exist_ok=True)
    faltan = []
    for h in range(0, len(pares), POR_HOJA):
        grupo = pares[h:h + POR_HOJA]
        filas = (len(grupo) + 3) // 4
        hoja = Image.new("RGB", (4 * (2 * W + 16), filas * (H + 40)), "black")
        d = ImageDraw.Draw(hoja)
        for i, (tid, k, tipo, que, orig, nuestro) in enumerate(grupo):
            x0, y0 = (i % 4) * (2 * W + 16), (i // 4) * (H + 40)
            d.text((x0 + 4, y0 + 4), f"T{tid} · {k} · {tipo}", fill="yellow")
            d.text((x0 + 4, y0 + 20), que[:78], fill="white")
            if orig.exists():
                hoja.paste(Image.open(orig).convert("RGB").resize((W, H)), (x0, y0 + 40))
            if nuestro.exists():
                hoja.paste(recorte_916(Image.open(nuestro).convert("RGB")).resize((W, H)), (x0 + W, y0 + 40))
            else:
                faltan.append(tid)
                d.text((x0 + W + 20, y0 + 250), "FALTA", fill="red")
        hoja.save(salida / f"control-{h // POR_HOJA + 1:02d}.jpg", quality=85)
    print(f"{len(pares)} encuadres · {(len(pares) + POR_HOJA - 1) // POR_HOJA} hojas en {salida}"
          + (f" · faltan: {' '.join(faltan)}" if faltan else ""))


if __name__ == "__main__":
    main()
