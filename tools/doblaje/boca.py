# -*- coding: utf-8 -*-
"""Detecta cuando empieza a moverse la boca, mirando la imagen.

LA REGLA QUE IMPLEMENTA
  El doblaje tiene que arrancar donde arranca la BOCA, no donde arranca el
  audio de H3. Son cosas distintas: H3 no sincroniza su propio audio con su
  propia animacion. En el plano del genio la boca empieza en 176,54 y su voz
  recien en 177,24 —0,70 s de boca moviendose muda—, y como las anclas salian
  del audio, el doblaje heredaba el error entero.

COMO
  Sin deteccion de caras, que sobre dibujo animado estilizado no es fiable.
  Se aprovecha que en un plano de dialogo el personaje esta bastante quieto y
  lo que mas cambia entre fotogramas es la boca:

  1. Se decodifica la ventana a gris chico (160x90) y se mide la diferencia
     absoluta entre fotogramas consecutivos.
  2. Se acumula esa diferencia en el tiempo y se busca la REGION de mayor
     actividad. Esa region es la boca.
  3. La serie temporal dentro de esa region es la senal de "boca moviendose".
  4. El ataque es el primer cruce sostenido del umbral.

  Falla previsible: si la camara se mueve o hay humo, efectos o varios
  personajes, la region de mayor actividad no es la boca. Por eso el detector
  EXIGE que la actividad este localizada —la region tiene que destacar contra
  el resto del cuadro— y que haya quietud antes del ataque. Si no se cumple,
  devuelve None y quien llama se queda con el tiempo del audio. Un detector
  que se abstiene vale mas que uno que siempre contesta.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

FPS = 12
ANCHO, ALTO = 160, 90
CAJA = 9            # lado de la region que se considera "la boca"
UMBRAL = 0.35       # cuanto tiene que subir sobre el piso para contar
SOSTEN = 2          # fotogramas seguidos por encima para aceptar el ataque
CALMA = 0.20        # segundos previos que tienen que estar por debajo, EN PROMEDIO
LOCAL_MIN = 2.0     # cuanto tiene que destacar la region contra la mediana


def _senal(pel, a, dur, ff, tmp):
    """Serie de movimiento de la region mas activa. Devuelve (senal, localidad)."""
    crudo = tmp / "_boca.gray"
    subprocess.run([str(ff), "-y", "-v", "error", "-i", str(pel),
                    "-ss", f"{a:.3f}", "-t", f"{dur:.3f}",
                    "-vf", f"fps={FPS},scale={ANCHO}:{ALTO},format=gray",
                    "-f", "rawvideo", str(crudo)],
                   check=True, stdin=subprocess.DEVNULL)
    x = np.fromfile(crudo, np.uint8)
    n = len(x) // (ANCHO * ALTO)
    if n < 4:
        return None, 0.0
    x = x[:n * ANCHO * ALTO].reshape(n, ALTO, ANCHO).astype(np.float32)
    d = np.abs(np.diff(x, axis=0))
    acc = d.sum(0)
    from scipy.ndimage import uniform_filter
    suave = uniform_filter(acc, size=CAJA)
    iy, ix = np.unravel_index(int(suave.argmax()), suave.shape)
    med = float(np.median(suave)) + 1e-6
    localidad = float(suave[iy, ix]) / med
    r = CAJA // 2
    sig = d[:, max(0, iy - r):iy + r + 1, max(0, ix - r):ix + r + 1].mean((1, 2))
    return sig, localidad


def inicio(pel, t_audio, ff, tmp, atras=1.5, adelante=0.4):
    """Instante en que la boca empieza a moverse, o None si no es confiable.

    Se busca desde `atras` segundos antes del ataque del audio: el caso que
    importa es la boca adelantandose, no atrasandose.
    """
    a = max(0.0, t_audio - atras)
    dur = atras + adelante
    try:
        sig, loc = _senal(pel, a, dur, ff, tmp)
    except Exception:
        return None, "error"
    if sig is None or len(sig) < 6:
        return None, "corto"
    if loc < LOCAL_MIN:
        # La actividad esta repartida por todo el cuadro: camara, humo, varios
        # personajes. No se puede afirmar que sea una boca.
        return None, f"disperso({loc:.1f})"
    # En animacion el personaje nunca esta del todo quieto: exigir quietud
    # absoluta antes del ataque hacia que el detector se abstuviera en 15 de 19
    # planos. Lo que se busca es el SALTO de actividad sobre el piso propio de
    # la ventana, no el silencio.
    piso = float(np.percentile(sig, 25))
    techo = float(np.percentile(sig, 90))
    if techo - piso <= 1e-3:
        return None, "sin movimiento"
    umb = piso + UMBRAL * (techo - piso)
    arriba = sig > umb
    g = max(1, int(CALMA * FPS))
    for i in range(len(sig) - SOSTEN):
        if arriba[i:i + SOSTEN].all():
            if i < g:
                continue                      # el ataque queda fuera de la ventana
            if sig[i - g:i].mean() >= umb:
                continue                      # ya venia moviendose: no es el ataque
            return a + i / FPS, f"ok(loc {loc:.1f})"
    return None, "sin ataque claro"
