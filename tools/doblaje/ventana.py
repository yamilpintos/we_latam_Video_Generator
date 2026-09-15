# -*- coding: utf-8 -*-
"""Mide la ventana REAL de cada linea sobre el stem de voz del original.

POR QUE NO ALCANZA EL ASR
  Scribe da los tiempos del habla que transcribio, y se equivoca en los dos
  bordes: llega tarde al inicio y corta temprano al final —hasta 0,79 s medido
  en este material, p75 +0,48 s medido por DubAI sobre 149 clips—. Usar esos
  tiempos como ventana produce exactamente los dos defectos que se oyen: el
  doblaje arranca despues de que los labios empezaron, y se sigue oyendo
  despues de que pararon.

EL METODO, TOMADO DE dubai_v2/src/pipeline/sync.py
  Energia RMS en tramos de 10 ms sobre el stem de voz (demucs), con dos
  guardas que son lo que hace confiable al detector:

  · INICIO — exige 0,15 s de silencio ANTES del candidato. Si la linea
    anterior todavia suena en la ventana de busqueda, el detector engancharia
    su cola y adelantaria de mas: en ese caso no opina y se queda con el ASR.
  · FIN — exige 0,15 s de silencio DESPUES. Si la voz sigue hasta el borde de
    la busqueda (otro hablante encadenado), tampoco opina.

  Un detector que se abstiene cuando no esta seguro vale mas que uno que
  siempre responde: las lineas dudosas caen al tiempo del ASR, que es
  imperfecto pero no inventa.

Los parametros son los de DubAI, sin cambiar.
"""
from __future__ import annotations

import numpy as np
import soundfile as sf

SR = 48000
HOP = 0.010          # resolucion del detector
BACK = 0.60          # SYNC_ONSET_BACK
FWD = 0.40           # SYNC_ONSET_FWD
END_FWD = 0.80       # SYNC_END_FWD
UMBRAL = 0.18        # fraccion del pico local que cuenta como voz
GUARDA = 0.15        # silencio exigido antes del inicio / despues del fin


def _rms(x):
    n = len(x) // int(SR * HOP)
    if n < 20:
        return None
    h = int(SR * HOP)
    return np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(axis=1))


def _tramo(voz, a, b):
    i, j = max(0, int(a * SR)), min(len(voz), int(b * SR))
    return voz[i:j] if j > i else np.zeros(0, np.float32)


def inicio(voz, t):
    """Ataque real de la voz cerca de t. None si no hay un ataque limpio."""
    a = max(0.0, t - BACK)
    r = _rms(_tramo(voz, a, t + FWD))
    if r is None:
        return None
    pico = float(r.max())
    if pico < 1e-4:
        return None
    arriba = r > max(pico * UMBRAL, 1e-4)
    g = int(GUARDA / HOP)
    for i in range(len(r) - 2):
        if arriba[i] and arriba[i + 1] and arriba[i + 2]:
            # Sin silencio previo suficiente no hay ataque limpio: puede ser la
            # cola del hablante anterior. El detector se abstiene.
            if i < g or arriba[max(0, i - g):i].any():
                return None
            return a + i * HOP
    return None


def fin(voz, t):
    """Fin real de la voz cerca de t. None si la voz sigue hasta el borde."""
    a = max(0.0, t - 0.6)
    r = _rms(_tramo(voz, a, t + END_FWD + 0.2))
    if r is None:
        return None
    pico = float(r.max())
    if pico < 1e-4:
        return None
    arriba = r > max(pico * UMBRAL, 1e-4)
    g = int(GUARDA / HOP)
    for i in range(len(r) - 3, 1, -1):
        if arriba[i] and arriba[i - 1] and arriba[i - 2]:
            post = arriba[i + 1:i + 1 + g]
            if len(post) < g or post.any():
                return None          # la voz sigue: no hay fin limpio
            return a + (i + 1) * HOP
    return None


def bloques(voz, a, b, fusion=0.25, minimo=0.15):
    """Bloques de habla contigua dentro de [a,b]. Devuelve [(ini, fin), ...].

    Los huecos menores a `fusion` se fusionan: son las pausas naturales entre
    palabras, no separaciones de linea.
    """
    from scipy.ndimage import uniform_filter1d
    seg = _tramo(voz, a, b)
    if not len(seg):
        return []
    r = uniform_filter1d(np.abs(seg).astype(np.float32), int(SR * 0.03))
    pico = float(r.max())
    if pico < 1e-4:
        return []
    act = r > pico * UMBRAL
    d = np.diff(act.astype(np.int8))
    ini = list(np.where(d == 1)[0] + 1)
    fin = list(np.where(d == -1)[0] + 1)
    if act[0]:
        ini.insert(0, 0)
    if act[-1]:
        fin.append(len(act))
    bl = [(a + i0 / SR, a + i1 / SR) for i0, i1 in zip(ini, fin)]
    fus = []
    for x, y in bl:
        if fus and x - fus[-1][1] < fusion:
            fus[-1] = (fus[-1][0], y)
        else:
            fus.append((x, y))
    return [(x, y) for x, y in fus if y - x >= minimo]


def medir(voz, t0_asr, t1_asr, tope=None):
    """Ventana REAL de una linea. Devuelve (inicio, fin, activo, bloques).

    El ASR agrupa en frases y esas frases se comen silencios enteros. Medido
    sobre este material: la linea del vendedor abarcaba 8,63 s de los cuales
    2,8 s finales eran silencio —la voz doblada seguia sonando casi tres
    segundos despues de que la boca paraba— y la primera pregunta arrancaba
    1,0 s tarde porque el habla empezaba recien ahi.

    La linea abarca TODOS los bloques que se superponen con el rango del ASR,
    no solo el mayor: una frase puede llevar una pausa dramatica adentro y
    sigue siendo una frase (el genio arrastra "durmiendo" 1,2 s). Quedarse con
    el bloque mayor le comia el arranque.

      inicio  = arranque del primer bloque   -> corrige el "entra tarde"
      fin     = final del ultimo bloque      -> corrige el "se sigue oyendo"
      activo  = segundos de habla real       -> es lo que manda la densidad

    El texto se escribe contra `activo`, no contra el span: si se escribe para
    el span, el sobrante del silencio interno se convierte en desborde.
    """
    bl = bloques(voz, max(0.0, t0_asr - BACK), t1_asr + END_FWD)
    if tope is not None:
        bl = [(x, min(y, tope - 0.06)) for x, y in bl if x < tope - 0.06]
    prop = [b for b in bl if min(b[1], t1_asr) - max(b[0], t0_asr) > 0]
    if not prop:
        return t0_asr, t1_asr, t1_asr - t0_asr, 0
    ini = prop[0][0]
    fin = prop[-1][1]
    activo = sum(y - x for x, y in prop)
    return ini, fin, activo, len(prop)


def cargar(ruta="vocals.wav"):
    v, _ = sf.read(ruta, dtype="float32")
    return v.mean(1) if v.ndim > 1 else v
