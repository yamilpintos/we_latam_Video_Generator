# -*- coding: utf-8 -*-
"""
Describe la música ORIGINAL de una región en términos MUSICALES para el prompt.

★ Regla: el prompt describe música (instrumentos, género, tempo, carácter). NUNCA el
espectro medido. Pasarle "casi nada arriba de 5 kHz" al generador devolvió retumbe —
porque ese espectro venía de un stem de campo contaminado con viento.

De dónde salen los términos: de AudioSet, que además de "Music" tiene ~130 clases de
instrumentos y géneros (Acoustic guitar, Piano, Strings, Folk music, Ambient music…).
Se corre sobre el instrumental de la región y se toman las clases más probables.
Eso es "mismo estilo artístico": los mismos instrumentos y el mismo género, con
otra melodía.
"""
from __future__ import annotations

import numpy as np
import librosa

from .audio import a16k, mono
from .mapa import modelo, probabilidades

# Clases AudioSet que son instrumentos o géneros (por nombre). Se excluyen las
# genéricas y las vocales, porque el score pedido es instrumental.
_EXCLUIR = {"music", "musical instrument", "singing", "vocal music", "choir", "song",
            "male singing", "female singing", "child singing", "synthetic singing",
            "rapping", "chant", "mantra", "yodeling", "humming", "a capella",
            "background music", "theme music", "soundtrack music", "video game music",
            "christmas music", "music of asia", "music of africa", "music of latin america",
            "music of bollywood", "middle eastern music", "musical ensemble",
            "plucked string instrument", "bowed string instrument", "keyboard (musical)",
            "brass instrument", "wind instrument, woodwind instrument", "percussion"}

_GENERO_PALABRAS = ("music", "rock", "jazz", "blues", "folk", "country", "ambient",
                    "electronic", "classical", "opera", "pop", "hip hop", "reggae",
                    "ska", "soul", "funk", "swing", "disco", "house", "techno", "dubstep",
                    "drum and bass", "trance", "new-age", "flamenco", "salsa", "tango",
                    "gospel", "traditional", "lullaby", "march", "wedding", "carnatic")


# ★ Géneros y ánimos: LISTA BLANCA con los nombres exactos de la ontología de AudioSet.
#   Buscar subcadenas dejaba pasar "Fly, housefly" (house) y "Burst, pop" (pop) como
#   géneros del prompt. Un nombre está o no está; no se adivina.
_GENEROS = {n.lower() for n in [
    "Pop music", "Hip hop music", "Beatboxing", "Rock music", "Heavy metal", "Punk rock",
    "Grunge", "Progressive rock", "Rock and roll", "Psychedelic rock", "Rhythm and blues",
    "Soul music", "Reggae", "Country", "Swing music", "Bluegrass", "Funk", "Folk music",
    "Middle Eastern music", "Jazz", "Disco", "Classical music", "Opera", "Electronic music",
    "House music", "Techno", "Dubstep", "Drum and bass", "Electronica", "Electronic dance music",
    "Ambient music", "Trance music", "Music of Latin America", "Salsa music", "Flamenco",
    "Blues", "Music for children", "New-age music", "Music of Africa", "Afrobeat",
    "Christian music", "Gospel music", "Music of Asia", "Carnatic music", "Music of Bollywood",
    "Ska", "Traditional music", "Independent music",
    # ánimos: también sirven en un prompt
    "Happy music", "Funny music", "Sad music", "Tender music", "Exciting music",
    "Angry music", "Scary music",
]}


def _es_instrumento(nombre: str) -> bool:
    n = nombre.lower()
    return n not in _GENEROS and n not in _EXCLUIR


def _es_genero(nombre: str) -> bool:
    return nombre.lower() in _GENEROS


def describir(inst48: np.ndarray, fraccion: float = 0.02) -> dict:
    """Instrumentos, géneros y tempo de la música original (de su stem instrumental).

    ★ El piso es RELATIVO a p(Music), no absoluto. Sobre un stem de campo AudioSet
    reparte poca masa en las clases finas: en el intro del viajero "Guitar" dio 0,012
    con "Music" en 0,43. Un umbral fijo de 0,12 devolvía listas vacías y el prompt
    caía al genérico. Con piso = 2 % de p(Music) (≈0,009) Guitar entra y el ruido no."""
    _, mo, g, L = modelo()
    y16 = a16k(inst48)
    v = int(4 * 16000)
    acc = np.zeros(len(L))
    n = 0
    for k in range(0, max(1, len(y16) - 16000), v):
        seg = y16[k:k + v]
        if len(seg) < 2 * 16000:
            break
        acc += probabilidades(seg)
        n += 1
    if n == 0:
        return dict(instrumentos=[], generos=[], tempo=None, p_musica=0.0)
    p = acc / n
    p_mus = float(p[g["musica"]].max())
    umbral_clase = max(0.006, fraccion * p_mus)
    ids_i = [(p[i], L[i]) for i in range(len(L)) if p[i] > umbral_clase and _es_instrumento(L[i])
             and i not in g["motor"] + g["viento"] + g["habla"]]
    ids_g = [(p[i], L[i]) for i in range(len(L)) if p[i] > umbral_clase and _es_genero(L[i])]
    # sólo lo que AudioSet considera música: filtra clases de ruido que pasan el umbral
    musicales = set()
    for i, nom in L.items():
        nm = nom.lower()
        if any(k in nm for k in ("guitar", "piano", "string", "violin", "cello", "harp", "flute",
                                 "organ", "synth", "drum", "bass", "trumpet", "sax", "clarinet",
                                 "accordion", "harmonica", "banjo", "mandolin", "ukulele",
                                 "marimba", "xylophone", "vibraphone", "bell", "harpsichord",
                                 "orchestra", "electric", "acoustic", "steel", "bagpipe",
                                 "didgeridoo", "sitar", "tabla", "cymbal", "timpani",
                                 "glockenspiel", "chime", "gong", "shofar", "theremin")):
            musicales.add(nom)
    ids_i = [(pp, nm) for pp, nm in ids_i if nm in musicales]
    ids_i.sort(reverse=True)
    ids_g.sort(reverse=True)
    try:
        t, _ = librosa.beat.beat_track(y=mono(inst48).astype(np.float32), sr=48000)
        tempo = float(np.atleast_1d(t)[0])
    except Exception:
        tempo = None
    return dict(instrumentos=[nm for _, nm in ids_i[:3]],
                generos=[nm for _, nm in ids_g[:2]],
                tempo=tempo, p_musica=float(p[g["musica"]].max()))


def prompt(desc: dict, etiqueta: str, largo_s: float) -> str:
    """Arma el pedido para Eleven Music. Sólo términos musicales."""
    inst = ", ".join(desc["instrumentos"]).lower() if desc["instrumentos"] else "acoustic instruments"
    gen = ", ".join(desc["generos"]).lower() if desc["generos"] else "cinematic underscore"
    # el estimador de tempo confunde octavas (312 = 156 = 78 bpm); se pliega a 55-190
    t = desc.get("tempo")
    if t and t > 0:
        while t > 190:
            t /= 2
        while t < 55:
            t *= 2
    tempo = f" around {t:.0f} BPM." if t else ""
    rol = {
        "INTRO": "Opening title theme. Starts immediately on the downbeat, states a clear "
                 "melody and keeps developing it without repeating itself.",
        "OUTRO": "Closing theme. Begins quietly, grows steadily, restates the main melody "
                 "in full near the end, then resolves and fades out.",
        "CORTINA": "Short transitional cue. Simple, self-contained, with a clear ending.",
        "CAMA": "Quiet underscore bed meant to sit under spoken narration: sparse, "
                "restrained, no foreground melody, no sudden accents.",
    }[etiqueta]
    return (f"{rol} Instrumental piece featuring {inst}, in the style of {gen}.{tempo} "
            f"Same mood and pacing as a {largo_s:.0f}-second cue. "
            f"Instrumental only, no vocals, no singing.")
