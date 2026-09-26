# -*- coding: utf-8 -*-
"""
UN TEMA POR ESTILO: la palanca de costo grande, y también la de coherencia.

Antes: una generación por pista. En "La ruta de la seda" eran 20 pistas, pero 10 eran
country con guitarra y 3 rock con eléctrica: 20 canciones sueltas que costaban 57 min
de música generada por hora de video y no tenían nada que ver entre sí.

Ahora: las pistas se agrupan por FAMILIA de género (country/folk, rock, clásica,
electrónica, funk, un ánimo…), se genera UN tema por familia, de hasta TEMA_MAX_S, y
cada pista toma un TRAMO DISTINTO de su tema. Una banda sonora real repite temas:
suena a leitmotiv, no a compilado.

★ La primera versión agrupaba por instrumentos + género exactos y el tema duraba la
  suma de sus pistas: 13 temas para 20 pistas, 26 min a generar para 25 de música —
  no ahorraba nada. La agrupación tiene que ser gruesa y el tema, corto.

Reglas:
  · INTRO y OUTRO: tema propio siempre (arrancan en el downbeat / terminan en fade).
  · largo del tema = min(TEMA_MAX_S, max(pista más larga + holgura, suma de pistas)).
    Un grupo de una pista genera justo lo que necesita; uno de diez pistas genera
    4 min y las pistas se reparten a lo largo (se solapan: es el mismo tema, a propósito).
  · Las pistas inaudibles en el original (< −45 dB bajo narración) usan el tema de su
    grupo igual: ya no cuestan nada aparte.
"""
from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from . import config as C
from .mapa import Region

HOLGURA = {"INTRO": 6.0, "OUTRO": 10.0, "CAMA": 3.0, "CORTINA": 3.0}
TOPE_S = 600.0
TEMA_MAX_S = float(os.getenv("REMUSICAL_TEMA_MAX_S", "240"))

# familia de género <- palabras clave en los nombres de AudioSet (en minúsculas)
FAMILIAS = [
    ("folk", ("country", "folk", "bluegrass", "traditional", "music of latin america", "flamenco", "salsa")),
    ("rock", ("rock", "punk", "grunge", "heavy metal", "independent")),
    ("electronic", ("electronic", "techno", "house", "ambient", "trance", "dubstep", "drum and bass", "new-age")),
    ("funk", ("funk", "soul", "disco", "rhythm and blues", "reggae", "ska", "afrobeat")),
    ("classical", ("classical", "opera", "carnatic", "middle eastern", "music of asia")),
    ("jazz", ("jazz", "swing", "blues")),
    ("pop", ("pop", "hip hop", "christian", "gospel")),
]
_MOODS = ("scary", "tender", "sad", "happy", "exciting", "angry", "funny")
FRASE = {"folk": "country and folk", "rock": "rock", "electronic": "electronic and ambient",
         "funk": "funk and soul", "classical": "classical and traditional", "jazz": "jazz and blues",
         "pop": "pop", "otro": "cinematic underscore"}


def familia(desc: dict) -> str:
    for g in (desc.get("generos") or []):
        n = g.lower()
        for m in _MOODS:
            if n.startswith(m):
                return "mood:" + m
        for fam, claves in FAMILIAS:
            if any(k in n for k in claves):
                return fam
    return "otro"


@dataclass
class Grupo:
    clave: tuple
    etiqueta: str                   # INTRO / OUTRO / CAMA
    pistas: list[int] = field(default_factory=list)
    largo_tema: float = 0.0
    desde: dict[int, float | None] = field(default_factory=dict)   # región -> offset en el tema
    prompt: str = ""
    desc: dict = field(default_factory=dict)


def agrupar(regs: list[Region], descs: list[dict]) -> list[Grupo]:
    grupos: dict[tuple, Grupo] = {}
    for i, (r, d) in enumerate(zip(regs, descs)):
        k = (r.etiqueta, i) if r.etiqueta in ("INTRO", "OUTRO") else ("CAMA", familia(d))
        g = grupos.setdefault(k, Grupo(k, "CAMA" if k[0] == "CAMA" else r.etiqueta))
        g.pistas.append(i)

    out = []
    for g in grupos.values():
        # descripción del grupo: los instrumentos más frecuentes entre sus pistas, la familia como género
        inst = Counter(x for i in g.pistas for x in (descs[i].get("instrumentos") or []))
        tempos = [descs[i].get("tempo") for i in g.pistas if descs[i].get("tempo")]
        fam = g.clave[1] if g.clave[0] == "CAMA" else familia(descs[g.pistas[0]])
        gen = ("Mood: " + fam[5:]) if fam.startswith("mood:") else FRASE.get(fam, FRASE["otro"])
        g.desc = dict(instrumentos=[x for x, _ in inst.most_common(3)], generos=[gen],
                      tempo=float(np.median(tempos)) if tempos else None, familia=fam)

        largos = {i: regs[i].largo + HOLGURA.get(regs[i].etiqueta, 3.0) for i in g.pistas}
        g.largo_tema = float(min(TOPE_S, max(max(largos.values()), min(sum(largos.values()), TEMA_MAX_S))))
        k = len(g.pistas)
        for n, i in enumerate(sorted(g.pistas, key=lambda i: regs[i].inicio)):
            if regs[i].etiqueta == "OUTRO":
                g.desde[i] = None                     # el outro se ancla por su fade en montar()
                continue
            libre = max(0.0, g.largo_tema - largos[i])
            g.desde[i] = 0.0 if k == 1 else round(libre * n / (k - 1), 2)
        out.append(g)
    return out


def tramo(tema: np.ndarray, desde: float | None, largo_s: float) -> np.ndarray:
    """El pedazo del tema que va a una pista (con su holgura). None = el tema entero."""
    if desde is None:
        return tema
    a = int(desde * C.SR)
    b = a + int(largo_s * C.SR)
    if b > len(tema):
        b = len(tema)
        a = max(0, b - int(largo_s * C.SR))
    return tema[a:b]


def resumen(grupos: list[Grupo], regs: list[Region]) -> str:
    lineas = []
    for g in grupos:
        d = g.desc
        est = ", ".join(d.get("instrumentos", [])[:2]) + " · " + (d.get("generos") or ["?"])[0]
        lineas.append(f"    {g.etiqueta:<6} {len(g.pistas):>2} pista(s)  tema {g.largo_tema:5.0f}s  {est}")
    gen = sum(g.largo_tema for g in grupos)
    mus = sum(r.largo for r in regs)
    lineas.append(f"    -> {gen/60:.1f} min a generar para {mus/60:.1f} min de musica "
                  f"({len(grupos)} temas en vez de {len(regs)} pistas)")
    return "\n".join(lineas)
