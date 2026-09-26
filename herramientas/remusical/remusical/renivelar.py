# -*- coding: utf-8 -*-
"""
Re-nivela una entrega YA HECHA desde sus stems, sin volver a separar ni a generar.

  python -m remusical.renivelar "<carpeta re-musical>" "<video original.mp4>"

Lee voz.flac, musica original.flac y musica nueva.flac de la carpeta, más el informe
(para las pistas), iguala la música nueva a la original pista por pista (con y sin
narración), vuelve a pasar las guardas, y reescribe el MP4 y `musica nueva.flac`.
Deja `informe.json` con la sección `renivelado`.

Existe porque la primera entrega de 'La ruta de la seda' salió con la música nueva de
−9 a +8 dB respecto de la original según la pista, y arreglarlo no puede costar 3 h
de separación ni créditos de generación.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from . import config as C
from .audio import escribir, extraer_audio, leer48
from .mapa import Region
from .montar import nivelar_hasta
from .guardas import auditar, entregable


def main():
    carpeta, video = Path(sys.argv[1]), Path(sys.argv[2])
    nombre = video.stem
    inf_p = carpeta / f"{nombre} - informe.json"
    inf = json.loads(inf_p.read_text(encoding="utf-8"))
    regs = [Region(p["inicio"], p["fin"], p["etiqueta"], p.get("p_musica", 0.5))
            for p in inf.get("regiones_finales") or inf["pistas"]]
    tmp = C.TRABAJO / "renivelar" / nombre
    tmp.mkdir(parents=True, exist_ok=True)
    print(f"[{nombre}] {len(regs)} pistas")
    mezcla = leer48(extraer_audio(video, tmp / "orig48.wav"))
    voz = leer48(carpeta / f"{nombre} - voz.flac")
    inst = leer48(carpeta / f"{nombre} - musica original.flac")
    musica = leer48(carpeta / f"{nombre} - musica nueva.flac")
    n = min(len(mezcla), len(voz), len(inst), len(musica))
    mezcla, voz, inst, musica = mezcla[:n], voz[:n], inst[:n], musica[:n]

    print("  nivelando pista por pista contra la música original:")
    sal, mus2, detalle = nivelar_hasta(mezcla, voz, inst, musica, regs)
    print("  guardas:")
    res = auditar(mezcla, sal, voz, regs, inst=inst, musica=mus2)
    for g in res:
        print(f"    {'PASA   ' if g['ok'] else 'RECHAZA'} {g['n']} {g['nombre']:<16} {g['detalle']}")
    ok = entregable(res)

    wav = tmp / "audio_renivelado.wav"
    escribir(wav, sal)
    pref = C.PREFIJO if ok else "REVISAR"
    mp4 = carpeta / f"{pref} {nombre}.mp4"
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(video), "-i", str(wav),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k",
                    "-movflags", "+faststart", str(mp4)], check=True)
    escribir(carpeta / f"{nombre} - musica nueva.flac", mus2, formato="PCM_16")
    inf["renivelado"] = dict(fecha=time.strftime("%Y-%m-%d %H:%M:%S"), estado="ENTREGABLE" if ok else "REVISAR",
                             pistas=detalle, guardas=[{k: v for k, v in g.items() if k in ("n", "nombre", "ok", "detalle")} for g in res])
    inf["estado"] = "ENTREGABLE" if ok else "REVISAR"
    inf_p.write_text(json.dumps(inf, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  {'ENTREGABLE' if ok else 'REVISAR'} -> {mp4}")


if __name__ == "__main__":
    main()
