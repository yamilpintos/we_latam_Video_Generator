# -*- coding: utf-8 -*-
"""
Sub-segmenta una región larga de música en las PISTAS que la componen.

Por qué existe: en "La ruta de la seda" el 93 % del video es música, en regiones de
hasta 12 minutos sin un solo hueco. Una región así no es una música: son varias
pistas seguidas. El pedido es "similar pero distinto en cada parte", así que hay que
encontrar dónde cambia la música. Y además Eleven Music no genera más de 600 s por
pedido: una región de 751 s daría 422.

Cómo se detecta el cambio: sobre el stem INSTRUMENTAL (sin la voz encima), rasgos de
timbre y armonía por ventana (MFCC + croma + contraste espectral, estandarizados), y
una novedad = distancia coseno entre el promedio de los 16 s anteriores y el de los
16 s siguientes. Un pico de novedad = cambio de pista. Después se imponen largos
mínimo y máximo: nada menor a MIN_S (una pista real dura más) ni mayor a MAX_S (por
el tope de Eleven Music y porque una pista de 4 min ya es larga).

Cada sub-región lleva `contiguo=True` si arranca donde terminó la anterior: el
montaje hace crossfade ahí en vez de fundir a silencio.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import librosa

from . import config as C
from .audio import mono
from .mapa import Region

VENT_S = 4.0          # ventana de rasgos
CONTEXTO_S = 16.0     # a cada lado, para la novedad
MIN_S = 45.0          # sub-región mínima
MAX_S = 240.0         # sub-región máxima (< 600 s de Eleven Music, y ≈ una pista)
SOLO_SI_MAYOR_A = 150.0   # regiones más cortas no se parten


@dataclass
class SubRegion(Region):
    contiguo: bool = False
    madre: int = -1


def _rasgos(y: np.ndarray, sr: int) -> np.ndarray:
    """Matriz (ventanas × rasgos), una fila cada VENT_S segundos."""
    y = mono(y).astype(np.float32)
    h = int(VENT_S * sr)
    filas = []
    for k in range(0, len(y) - h + 1, h):
        seg = y[k:k + h]
        mf = librosa.feature.mfcc(y=seg, sr=sr, n_mfcc=20).mean(axis=1)
        ch = librosa.feature.chroma_stft(y=seg, sr=sr).mean(axis=1)
        sc = librosa.feature.spectral_contrast(y=seg, sr=sr).mean(axis=1)
        filas.append(np.concatenate([mf, ch, sc]))
    X = np.array(filas)
    if len(X) > 1:
        X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-9)
    return X


def _novedad(X: np.ndarray) -> np.ndarray:
    c = max(1, int(CONTEXTO_S / VENT_S))
    n = np.zeros(len(X))
    for i in range(c, len(X) - c):
        a, b = X[i - c:i].mean(axis=0), X[i:i + c].mean(axis=0)
        n[i] = 1.0 - float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    return n


def _cortes(nov: np.ndarray, largo_s: float) -> list[float]:
    """Picos de novedad, con distancia mínima MIN_S y umbral adaptativo."""
    if len(nov) < 3:
        return []
    umbral = nov.mean() + 1.0 * nov.std()
    dist = max(1, int(MIN_S / VENT_S))
    cand = [i for i in range(1, len(nov) - 1)
            if nov[i] > umbral and nov[i] >= nov[i - 1] and nov[i] >= nov[i + 1]]
    cand.sort(key=lambda i: -nov[i])
    elegidos: list[int] = []
    for i in cand:
        if all(abs(i - j) >= dist for j in elegidos):
            elegidos.append(i)
    cortes = sorted(i * VENT_S for i in elegidos)
    return [c for c in cortes if MIN_S <= c <= largo_s - MIN_S]


def _imponer_largos(cortes: list[float], largo: float, nov: np.ndarray) -> list[float]:
    """Ningún tramo > MAX_S: se parte en su pico de novedad interno, o parejo."""
    bordes = [0.0] + cortes + [largo]
    out = [0.0]
    for a, b in zip(bordes[:-1], bordes[1:]):
        while b - out[-1] > MAX_S:
            lo, hi = out[-1] + MIN_S, min(b - MIN_S, out[-1] + MAX_S)
            if hi <= lo:
                break
            i0, i1 = int(lo / VENT_S), int(hi / VENT_S)
            if i1 > i0 and len(nov) > i1:
                corte = (i0 + int(np.argmax(nov[i0:i1]))) * VENT_S
            else:
                corte = out[-1] + MAX_S
            out.append(float(corte))
        out.append(float(b))
    # dedup y orden
    out = sorted(set(round(x, 2) for x in out))
    return out[1:-1]


def subdividir(regs: list[Region], inst48: np.ndarray, log=print) -> list[SubRegion]:
    sr = C.SR
    salida: list[SubRegion] = []
    for i, r in enumerate(regs):
        if r.largo <= SOLO_SI_MAYOR_A:
            salida.append(SubRegion(r.inicio, r.fin, r.etiqueta, r.p_musica, False, i))
            continue
        y = inst48[int(r.inicio * sr):int(r.fin * sr)]
        X = _rasgos(y, sr)
        nov = _novedad(X)
        cortes = _cortes(nov, r.largo)
        cortes = _imponer_largos(cortes, r.largo, nov)
        bordes = [0.0] + cortes + [r.largo]
        log(f"  region {i+1} ({r.largo:.0f}s) -> {len(bordes)-1} pistas: "
            + ", ".join(f"{b-a:.0f}s" for a, b in zip(bordes[:-1], bordes[1:])))
        for k, (a, b) in enumerate(zip(bordes[:-1], bordes[1:])):
            if r.etiqueta == "INTRO":
                et = "INTRO" if k == 0 else "CAMA"
            elif r.etiqueta == "OUTRO":
                et = "OUTRO" if k == len(bordes) - 2 else "CAMA"
            else:
                et = r.etiqueta
            salida.append(SubRegion(round(r.inicio + a, 2), round(r.inicio + b, 2), et,
                                    r.p_musica, k > 0, i))
    return salida
