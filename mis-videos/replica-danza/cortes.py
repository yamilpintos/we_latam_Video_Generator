"""¿H3 metió un corte adentro del clip? Detector de escena de ffmpeg por clip.

    /c/Python314/python -X utf8 mis-videos/replica-danza/cortes.py <proyecto.json> <carpeta_clips>

REGLAS 54 y 57: nombrar lo que no está en cuadro (ropa, un segundo sujeto) hace
que H3 corte a mitad de clip para mostrarlo. Un clip de un solo plano no debería
tener ningún salto de escena; se listan los que sí, con el instante, para
mirarlos y rehacerlos. Escribe cortes.json al lado de los clips.

Sólo cuenta lo que pasa DENTRO del tramo que el montaje usa (`usa`, ampliado
con las tomas que reusan el clip, +0,3 s): en la corrida del 14/9, 22 de 53
clips cortaban a otro plano, casi todos después de su tramo, y ninguno adentro.
"""
import json
import re

import numpy as np
import subprocess
import sys
from pathlib import Path

FF = "C:/ffmpeg-2026-04-09-git-d3d0b7a5ee-essentials_build/bin/ffmpeg.exe"
UMBRAL = 0.30


def cortes(mp4, hasta):
    r = subprocess.run([FF, "-hide_banner", "-t", f"{hasta:.2f}", "-i", str(mp4), "-vf",
                        f"select='gt(scene,{UMBRAL})',showinfo", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return [round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def parecido(mp4, desde, hasta):
    """Correlación mínima de cada cuadro (gris, 36×64) con el primero. El
    detector de escena no ve los fundidos; esto sí. Calibrado con las muestras
    del 14/9: los que cortaron dan -0,13 a 0,43; los que no, 0,60 a 0,96."""
    r = subprocess.run([FF, "-v", "error", "-i", str(mp4), "-vf", "scale=36:64,format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    a = np.frombuffer(r.stdout, np.uint8).reshape(-1, 64, 36).astype(float)
    a = a[int(desde * 24): int(hasta * 24) + 1]
    f0 = a[0] - a[0].mean()
    return round(min(float(((x - x.mean()) * f0).sum()
                           / np.sqrt(((x - x.mean()) ** 2).sum() * (f0 ** 2).sum()))
                     for x in a), 2)


def main():
    g = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    carpeta = Path(sys.argv[2])
    usa = {p["id"]: list(p.get("usa") or [0, p.get("corta", 5)]) for p in g["planos"]
           if not p.get("clip_de")}
    for p in g["planos"]:
        if p.get("clip_de") in usa and p.get("usa"):
            a, b = usa[p["clip_de"]]
            usa[p["clip_de"]] = [min(a, p["usa"][0]), max(b, p["usa"][1])]
    res = {}
    for mp4 in sorted(carpeta.glob("*_00001_.mp4")):
        k = mp4.name.split("_0000")[0]
        desde, hasta = usa.get(k, [0.0, 5.17])
        hasta += 0.3
        c = [t for t in cortes(mp4, hasta) if t >= desde]
        s = parecido(mp4, desde, hasta)
        # Con el tramo acotado, los que se mueven mucho (una corrida, una puerta)
        # bajan hasta ~0,3 sin cortar: el umbral va más abajo que en el clip entero.
        mal = bool(c) or s < 0.1
        res[k] = {"tramo": [desde, round(hasta, 2)], "cortes": c, "parecido": s, "revisar": mal}
        if mal:
            print(f"{mp4.name:20} REVISAR · cortes {c} · parecido con el cuadro 0: {s}")
    (carpeta / "cortes.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"{len(res)} clips · {sum(1 for v in res.values() if v['revisar'])} a revisar")


if __name__ == "__main__":
    main()
