# -*- coding: utf-8 -*-
"""Control visual de los clips bajados, ANTES de destruir la instancia.

El 31/8 se destruyó una instancia sin mirar los clips y once eran ruido puro de
una placa defectuosa: rehacerlos costó un segundo alquiler. `bajar` ya escanea
ruido por tamaño de archivo, pero un clip puede estar mal sin ser ruido —el
personaje equivocado, el encuadre derivado, la acción que no pasa— y eso sólo
se ve mirando.

Esto arma hojas de contacto con TRES fotogramas de cada clip (principio, medio y
final del tramo que realmente se usa) para poder mirarlos todos rápido. El final
importa tanto como el principio: es donde H3 deriva.

    python mis-videos/replica-jcfdlw/qc_clips.py <carpeta-de-clips>
"""
import json
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI / "../.."))
from h3pipeline import config, montaje                      # noqa: E402

POR_HOJA = 8   # clips por hoja · 3 fotogramas cada uno = 24 celdas


def main(carpeta):
    carpeta = Path(carpeta)
    planos = json.loads((AQUI / "planos.json").read_text(encoding="utf-8"))["planos"]
    salida = AQUI / "qc"
    salida.mkdir(exist_ok=True)
    for viejo in salida.glob("*.jpg"):
        viejo.unlink()

    ff = config.ffmpeg()
    tmp = salida / "_f"
    tmp.mkdir(exist_ok=True)
    for viejo in tmp.glob("*.png"):
        viejo.unlink()

    # Con reuso (`clip_de`), varias tomas salen del mismo clip: se mira una vez
    # cada FUENTE, con el tramo total que le consumen sus tomas.
    fuentes = {}
    for p in planos:
        src = montaje.clip_fuente(p)
        if src == "PLACA":
            continue
        a, b = p.get("usa", [0, p["segundos"]])
        f = fuentes.setdefault(src, dict(p, id=src, usa=[a, b]))
        f["usa"] = [min(f["usa"][0], a), max(f["usa"][1], b)]
    planos = list(fuentes.values())
    faltan, ruido, i = [], [], 0
    for p in planos:
        clip = montaje.buscar_clip(carpeta, p["id"])
        if clip is None:
            faltan.append(p["id"])
            continue
        if montaje.es_ruido(clip):
            ruido.append(p["id"])
        a, b = p.get("usa", [0, p["segundos"]])
        for t in (a + 0.05, (a + b) / 2, max(a, b - 0.15)):
            i += 1
            subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y",
                            "-ss", f"{t:.2f}", "-i", str(clip), "-frames:v", "1",
                            "-vf", "scale=200:-1", str(tmp / f"{i:04d}.png")], check=True)

    subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y",
                    "-framerate", "1", "-i", str(tmp / "%04d.png"),
                    "-vf", f"tile=3x{POR_HOJA}:padding=3:color=white",
                    "-q:v", "3", str(salida / "qc-%02d.jpg")], check=True)

    hojas = sorted(salida.glob("qc-*.jpg"))
    print(f"{i//3} clips · {len(hojas)} hojas en {salida}")
    print("cada fila es un clip: entrada · medio · salida del tramo que se usa")
    if ruido:
        print(f"!! RUIDO detectado en {len(ruido)}: {' '.join(ruido)}")
    if faltan:
        print(f"!! faltan {len(faltan)} clips: {' '.join(faltan)}")
    if not ruido and not faltan:
        print("sin ruido y sin faltantes — igual hay que MIRAR las hojas antes de destruir")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
