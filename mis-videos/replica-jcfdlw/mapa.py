# -*- coding: utf-8 -*-
"""Escribe MAPA-ORIGINAL.md cruzando las tomas medidas con la transcripción."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tomas import TOMAS, DURACION  # noqa: E402

AQUI = Path(__file__).parent
TXT = AQUI / "../../referencias/jcfdlw/7678030150944001310.txt"


def lineas():
    out = []
    for l in TXT.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*\[\s*([0-9.]+)s\]\s*(.*)", l)
        if m:
            out.append((float(m.group(1)), m.group(2).strip()))
    return out


def main():
    lin = lineas()
    chars = sum(len(t) for _, t in lin)
    dur = [b - a for _, a, b, *_ in TOMAS]
    L = []
    L.append("# Mapa medido del original — 7678030150944001310 (@jcfdlw)")
    L.append("")
    L.append("Video objetivo de la réplica. **Nada de acá es estimado**: los cortes salen de")
    L.append("la detección de escenas de ffmpeg sobre el mp4 limpio (`select=gt(scene,0.20)`)")
    L.append("y se verificaron mirando el fotograma medio de cada toma; la voz sale del `.txt`")
    L.append("tal cual, sin tocar una coma.")
    L.append("")
    L.append("| | |")
    L.append("|---|---|")
    L.append(f"| duración del archivo | **{DURACION:.2f} s** — el limpio y el `.full` miden lo mismo |")
    L.append("| cuadro real | 1080×1440 centrado dentro de 1080×1920 (barras negras de 240 px) |")
    L.append("| fps | 30 |")
    L.append(f"| tomas | **{len(TOMAS)}** · media {DURACION/len(TOMAS):.2f} s · "
             f"min {min(dur):.2f} s · max {max(dur):.2f} s |")
    L.append(f"| líneas de voz | **{len(lin)}** · {chars} caracteres · "
             f"{chars/DURACION:.1f} cps |")
    L.append("| última marca de la transcripción | 179,6 s |")
    L.append("")
    L.append("Los tramos de menos de 0,5 s son destellos de transición, no tomas: se suman a")
    L.append("la toma anterior. Sin esa fusión el detector devuelve 104 tramos.")
    L.append("")
    L.append("## Las 77 tomas, con lo que se dice encima de cada una")
    L.append("")
    for n, a, b, tipo, loc, pers, ve in TOMAS:
        quien = " · " + ", ".join(pers) if pers else ""
        L.append(f"### {n:02d} · {a:.2f} → {b:.2f} s ({b-a:.2f} s) · {tipo} · {loc}{quien}")
        L.append(ve)
        for t, x in lin:
            if a - 0.001 <= t < b:
                L.append(f"- `{t:6.1f}s` {x}")
        L.append("")
    (AQUI / "MAPA-ORIGINAL.md").write_text("\n".join(L), encoding="utf-8")
    print(f"MAPA-ORIGINAL.md · {len(TOMAS)} tomas · {len(lin)} líneas · {chars} caracteres")


if __name__ == "__main__":
    main()
