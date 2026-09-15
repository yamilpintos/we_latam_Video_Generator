# -*- coding: utf-8 -*-
"""Elige, entre varias redacciones de la misma linea, la que mejor entra.

POR QUE HACE FALTA
  La densidad del espanol (~17 caracteres/segundo) sirve para ESTIMAR, pero el
  error a nivel toma llega al 30 %: la misma cantidad de caracteres dura
  distinto segun las silabas, la puntuacion y como la actue el modelo. Escribir
  una sola redaccion y esperar que entre es apostar.

  La alternativa es barata: sintetizar dos o tres redacciones de la misma linea
  y quedarse con la que mide mejor. Las 19 lineas del doblaje suman ~500
  caracteres; probar tres variantes de cada una cuesta el 0,1 % de la cuota.
  Deformar el audio para tapar una mala eleccion sale mucho mas caro en calidad.

COMO PUNTUA
  factor = duracion util / span de la ventana.
    · factor 1,00  -> entra exacta
    · factor > 1   -> hay que comprimir (se tolera hasta 1,15)
    · factor < 1   -> habria que ralentizar (solo hasta 1,08, o sea 0,926)
  Gana la mas cercana a 1,00; las que caen fuera del rango se penalizan fuerte
  pero no se descartan, por si ninguna entra.

  Se mide la duracion UTIL —sin el silencio de bordes que mete ElevenLabs—
  porque es la que va a sonar despues del recorte.
"""
from __future__ import annotations

import hashlib
import math
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 48000
LENTO = 1.08          # tope de ralentizacion (DubAI SYNC_MAX_SLOW)
RAPIDO = 1.15         # tope suave de compresion
UMBRAL_DB = -45.0     # que se considera silencio de borde


def duracion_util(mp3: Path, ff: Path, tmp: Path) -> float:
    """Segundos de audio sin el silencio de los extremos."""
    w = tmp / (mp3.stem + "_dur.wav")
    subprocess.run([str(ff), "-y", "-v", "error", "-i", str(mp3), "-ac", "1",
                    "-ar", str(SR), "-c:a", "pcm_f32le", str(w)],
                   check=True, stdin=subprocess.DEVNULL)
    x, _ = sf.read(w, dtype="float32")
    if not len(x):
        return 0.0
    pico = float(np.abs(x).max())
    if pico <= 0:
        return 0.0
    idx = np.where(np.abs(x) > pico * (10 ** (UMBRAL_DB / 20)))[0]
    return (idx[-1] - idx[0]) / SR if len(idx) else len(x) / SR


def puntaje(factor: float) -> float:
    """Menor es mejor. 0 = entra exacta."""
    base = abs(math.log(factor)) if factor > 0 else 9.9
    fuera = factor > RAPIDO or factor < 1.0 / LENTO
    return base + (1.0 if fuera else 0.0)


def elegir(variantes, voz_id, span, sintetizar, dcache: Path, prefijo: str,
           ff: Path, tmp: Path, log=print):
    """Sintetiza cada variante (con cache), mide y devuelve la mejor.

    variantes: lista de textos. El primero es la propuesta principal; con una
    sola variante la funcion sigue sirviendo (mide y reporta, sin elegir).

    Devuelve (mp3_ganador, texto_ganador, factor, tabla) donde tabla es la
    lista completa para poder mostrar por que gano.
    """
    tabla = []
    for k, txt in enumerate(variantes):
        # El hash del texto en el nombre hace que cambiar una redaccion
        # invalide solo esa variante y no vuelva a pagar por las demas.
        h = hashlib.sha1(txt.encode("utf-8")).hexdigest()[:8]
        mp3 = dcache / f"{prefijo}_{h}.mp3"
        if not mp3.exists():
            audio, _ = sintetizar(txt, voz_id)
            mp3.write_bytes(audio)
            nuevo = True
        else:
            nuevo = False
        d = duracion_util(mp3, ff, tmp)
        f = d / span if span > 0 else 9.9
        tabla.append({"i": k, "texto": txt, "mp3": mp3, "dur": d,
                      "factor": f, "puntaje": puntaje(f), "nuevo": nuevo})
    tabla.sort(key=lambda r: r["puntaje"])
    g = tabla[0]
    for r in tabla:
        marca = "  <-- entra" if r is g else ""
        log(f"      {r['factor']:5.2f}x  {r['dur']:4.2f}s  {len(r['texto']):3d}ch  "
            f"\"{r['texto'][:52]}\"{marca}")
    return g["mp3"], g["texto"], g["factor"], tabla
