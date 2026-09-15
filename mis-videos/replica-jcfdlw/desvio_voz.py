# -*- coding: utf-8 -*-
"""Mide las 92 líneas ya sintetizadas contra su ventana del original.

El texto de la réplica es fijo: si una línea no entra, **no se reescribe** —
se anota el desvío, que es parte de lo que el benchmark tiene que decir. La
pregunta que contesta este archivo es una sola: *¿cuánto más lenta es nuestra
voz que la de ellos, línea por línea?*

    python mis-videos/replica-jcfdlw/desvio_voz.py
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI / "../.."))
from h3pipeline import tts, voz as vozmod                     # noqa: E402
from h3pipeline.proyecto import Proyecto                      # noqa: E402


def main():
    p = Proyecto.cargar(AQUI / "proyecto.json")
    lineas = [x for x in p.lineas_de_voz() if x.tipo == "off"]
    cache = AQUI / "voz"
    filas, faltan = [], []
    for x in lineas:
        import hashlib
        h = hashlib.sha1(x.texto.encode("utf-8")).hexdigest()[:8]
        mp3 = cache / f"{x.id}_{h}.mp3"
        if not mp3.exists():
            faltan.append(x.id)
            continue
        d = tts.duracion_util(mp3)
        filas.append({"id": x.id, "t": x.t, "ventana": x.ventana, "dur": round(d, 2),
                      "factor": round(d / x.ventana, 3) if x.ventana else 9.9,
                      "chars": vozmod.caracteres(x.texto), "texto": x.texto})
    if faltan:
        print(f"!! faltan {len(faltan)} mp3: {' '.join(faltan[:8])}")

    dur_total = sum(f["dur"] for f in filas)
    ven_total = sum(f["ventana"] for f in filas)
    chars = sum(f["chars"] for f in filas)
    peor = sorted(filas, key=lambda f: -f["factor"])
    entra = [f for f in filas if f["factor"] <= vozmod.MAX_RAPIDO]
    duro = [f for f in filas if f["factor"] > vozmod.MAX_RAPIDO_DURO]

    L = ["# Desvío de voz — Kate contra la voz del original", "",
         "El texto es el de ellos, literal. Lo que se mide acá es **cuánto se pasa "
         "nuestra voz de la ventana que el original le da a cada frase**. Ninguna línea "
         "se reescribió: el desvío es el resultado del benchmark, no un defecto a tapar.",
         "",
         "| | |", "|---|---|",
         f"| líneas medidas | {len(filas)} de {len(lineas)} |",
         f"| caracteres | {chars} |",
         f"| ventana total del original | {ven_total:.1f} s |",
         f"| duración total con Kate | **{dur_total:.1f} s** |",
         f"| factor global | **{dur_total/ven_total:.3f}×** |",
         f"| líneas que entran sin tocar (≤ {vozmod.MAX_RAPIDO:.2f}×) | "
         f"{len(entra)} ({100*len(entra)/len(filas):.0f} %) |",
         f"| líneas por encima del tope duro ({vozmod.MAX_RAPIDO_DURO:.2f}×) | {len(duro)} |",
         f"| cps de Kate (medido) | {chars/dur_total:.1f} |",
         "",
         "## Las quince peores", "",
         "| línea | t | ventana | Kate | factor | texto |",
         "|---|---|---|---|---|---|"]
    for f in peor[:15]:
        L.append(f"| {f['id']} | {f['t']:.1f} s | {f['ventana']:.2f} s | {f['dur']:.2f} s | "
                 f"**{f['factor']:.2f}×** | {f['texto'][:60]} |")
    L += ["", "## Todas", "",
          "| línea | t | ventana | Kate | factor | ch | texto |", "|---|---|---|---|---|---|---|"]
    for f in filas:
        L.append(f"| {f['id']} | {f['t']:.1f} | {f['ventana']:.2f} | {f['dur']:.2f} | "
                 f"{f['factor']:.2f} | {f['chars']} | {f['texto']} |")
    (AQUI / "DESVIO-VOZ.md").write_text("\n".join(L), encoding="utf-8")
    (AQUI / "desvio_voz.json").write_text(
        json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(filas)} líneas · ventana {ven_total:.1f} s · Kate {dur_total:.1f} s "
          f"· factor global {dur_total/ven_total:.3f}× · entran {len(entra)} "
          f"· sobre 1,30× {len(duro)}")


if __name__ == "__main__":
    main()
