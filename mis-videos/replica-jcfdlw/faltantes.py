# -*- coding: utf-8 -*-
"""Qué fuente le falta al montaje y con qué se cubre, sin gastar GPU.

En la carpeta `clips/` conviven los clips de la corrida limpia (los que bajó
`bajar` ahora) y los de la corrida anterior, que tienen el mismo nombre para
los mismos ids. Para cada fuente que la corrida limpia NO produjo hay dos
salidas, en este orden:

  1. el clip de la corrida anterior, si existe y es lo bastante largo para
     el tramo que las tomas le consumen (más 0,3 s de colchón);
  2. el dibujo con zoom (`mezclar_replica.dibujo_con_zoom`), que siempre
     alcanza porque se renderiza de 6,0 s.

Imprime la decisión por id y devuelve la lista para `mezclar_replica.py`.

    python mis-videos/replica-jcfdlw/faltantes.py
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI / "../.."))
from h3pipeline import montaje                                # noqa: E402

CLIPS = AQUI / "clips"
COLCHON = 0.30


def main():
    planos = json.loads((AQUI / "planos.json").read_text(encoding="utf-8"))["planos"]
    metricas = {}
    mf = CLIPS / "metricas.json"
    if mf.exists():
        metricas = {m["id"]: m for m in json.loads(mf.read_text(encoding="utf-8"))}

    necesita = {}
    for p in planos:
        src = montaje.clip_fuente(p)
        if src == "PLACA":
            continue
        a, b = p.get("usa", [0, p["segundos"]])
        necesita[src] = max(necesita.get(src, 0.0), float(b))

    zoom, viejos, ok = [], [], []
    for src, fin in sorted(necesita.items()):
        clip = montaje.buscar_clip(CLIPS, src)
        if clip is None:
            zoom.append(src)
            continue
        if src in metricas:
            ok.append(src)
            continue
        d = montaje.duracion(clip) or 0.0
        if d >= fin + COLCHON:
            viejos.append((src, round(d, 2), round(fin, 2)))
        else:
            zoom.append(src)

    print(f"fuentes de la corrida limpia: {len(ok)}")
    if viejos:
        print("cubiertas con el clip de la corrida anterior (largo suficiente):")
        for s, d, f in viejos:
            print(f"   {s}: clip de {d} s para un tramo de {f} s")
    if zoom:
        print("plan B, dibujo con zoom: " + " ".join(zoom))
    (AQUI / "faltantes.json").write_text(json.dumps(
        {"limpia": ok, "anterior": [v[0] for v in viejos], "zoom": zoom},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return zoom


if __name__ == "__main__":
    main()
