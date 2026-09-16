"""Pone los cuadros del ORIGINAL (limpios de texto) como primeros fotogramas y
como hojas de modelo, en lugar de las imágenes de GPT.

    /c/Python314/python -X utf8 mis-videos/replica-danza/usar_originales.py

Decisión del usuario (15/9): las imágenes de GPT no respetaban la puesta en
escena (la escena final a horcajadas salió de pie), así que el primer fotograma
de cada toma es el cuadro del original en ese instante. Fuente por toma:
original/limpio/ (Nano Banana) y, si ese falta —el filtro bloquea las poses
sensuales—, original/limpio-cv/ (OpenCV). Las versiones de GPT quedaron en
_descartados/gpt-sunburst/.
"""
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import tomas as T  # noqa: E402
sys.path.insert(0, str(AQUI.parents[1]))
from limpiar_cv import limpiar  # noqa: E402

# Hoja de modelo → cuadro del original que mejor muestra al personaje.
HOJAS = {"m_hannah": "T20", "m_jack_camisa": "T53", "m_jack_abrigo": "T21",
         "m_luka": "T37", "m_wady": "T64", "m_matones": "T66", "m_pasajeros": "T59"}
PLACAS = {"T04", "T19", "T30", "T33"}


def fuente(k):
    nb = AQUI / "original" / "limpio" / f"{k}.png"
    if nb.exists():
        return nb, "nb"
    cv = AQUI / "original" / "limpio-cv" / f"{k}.png"
    if not cv.exists():
        limpiar(AQUI / "original" / "crudo" / f"{k}.png", cv, placa=k in PLACAS)
    return cv, "cv"


def main():
    por = {"nb": 0, "cv": 0}
    for t in T.TOMAS:
        k = f"T{t[0]}"
        src, como = fuente(k)
        shutil.copy(src, AQUI / "assets" / f"sb_{k}.png")
        por[como] += 1
    for hoja, k in HOJAS.items():
        src, _ = fuente(k)
        shutil.copy(src, AQUI / "assets" / f"{hoja}.png")
    print(f"{len(T.TOMAS)} primeros fotogramas: {por['nb']} de Nano Banana, {por['cv']} de OpenCV · "
          f"{len(HOJAS)} hojas")


if __name__ == "__main__":
    main()
