# -*- coding: utf-8 -*-
"""
Elige entre varios takes generados el que más se parece a la música ORIGINAL.

La voz no se elige: queda la original. Lo único que el sistema crea es la música, y
para eso sí hay vara: la que estaba ahí. Validado: reproduce las 5 decisiones que
se habían tomado a mano (incluida la descalificación de dos retumbes).

★ La referencia se toma SÓLO donde la música original suena SOLA (voz < -45 dB).
Medida sobre la región entera está contaminada con viento y huecos de narración, y
contra esa referencia gana un drone.
"""
from __future__ import annotations

import numpy as np
import librosa

from . import config as C
from .audio import a16k, db, mono
from .mapa import p_musica_media

U_MUSICA_TAKE = 0.40
U_ONSETS = 1.0
PESOS = dict(densidad=0.30, onsets=0.30, dinamica=0.20, tempo=0.10, brillo=0.10)


def rasgos(y: np.ndarray, sr: int = C.SR) -> dict:
    b = mono(y).astype(np.float32)
    h = int(0.25 * sr)
    n = max(1, len(b) // h)
    d = np.array([20 * np.log10(np.sqrt(np.mean(b[i*h:(i+1)*h] ** 2)) + 1e-9) for i in range(n)])
    pico = np.percentile(d, 95)
    densidad = float((d > pico - 25).mean())
    dinamica = float(d[d > pico - 35].std()) if (d > pico - 35).any() else 0.0
    try:
        t, _ = librosa.beat.beat_track(y=b, sr=sr)
        tempo = float(np.atleast_1d(t)[0])
    except Exception:
        tempo = float("nan")
    S = np.abs(librosa.stft(b, n_fft=2048)) ** 2
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    m = (f >= 250) & (f < 8000)
    brillo = float((f[m][:, None] * S[m]).sum() / (S[m].sum() + 1e-12))
    env = librosa.onset.onset_strength(y=b, sr=sr)
    onsets = len(librosa.onset.onset_detect(onset_envelope=env, sr=sr)) / max(0.1, len(b) / sr)
    return dict(densidad=densidad, dinamica=dinamica, tempo=tempo, brillo=brillo, onsets=float(onsets))


def _d_tempo(a, b):
    if not (np.isfinite(a) and np.isfinite(b) and a > 0 and b > 0):
        return 1.0
    r = a / b
    return float(min(abs(np.log2(r * k)) for k in (0.25, 0.5, 1, 2, 4)))


def distancia(rt: dict, ro: dict) -> tuple[float, dict]:
    d = dict(densidad=abs(rt["densidad"] - ro["densidad"]),
             onsets=abs(rt["onsets"] - ro["onsets"]) / 4.0,
             dinamica=abs(rt["dinamica"] - ro["dinamica"]) / 6.0,
             tempo=_d_tempo(rt["tempo"], ro["tempo"]),
             brillo=abs(np.log2((rt["brillo"] + 1e-9) / (ro["brillo"] + 1e-9))) / 2.0)
    return float(sum(PESOS[k] * min(v, 1.5) for k, v in d.items())), d


def referencia(mezcla48: np.ndarray, voz48: np.ndarray, inst48: np.ndarray) -> np.ndarray:
    """La música original donde suena sola. Si no hay 2 s de eso, el instrumental entero."""
    h = int(0.5 * C.SR)
    trozos = [mezcla48[k:k + h] for k in range(0, len(mezcla48) - h, h)
              if db(voz48[k:k + h]) < -45 and db(mezcla48[k:k + h]) > -55]
    if len(trozos) * 0.5 >= 2.0:
        return np.concatenate(trozos)
    return inst48


def elegir(ref48: np.ndarray, takes: dict[str, np.ndarray], log=print) -> tuple[list[str], list[dict]]:
    """Devuelve los nombres ordenados de mejor a peor (los descalificados no aparecen)
    y la tabla completa para el informe."""
    ro = rasgos(ref48)
    log(f"    referencia: densidad {ro['densidad']:.2f} ataques/s {ro['onsets']:.1f} "
        f"tempo {ro['tempo']:.0f} brillo {ro['brillo']:.0f} Hz")
    tabla = []
    for nom, y in takes.items():
        r = rasgos(y)
        pm = p_musica_media(a16k(y)) or 0.0
        fila = dict(take=nom, p_musica=round(pm, 3), **{k: round(float(v), 3) for k, v in r.items()})
        if pm < U_MUSICA_TAKE or r["onsets"] < U_ONSETS:
            fila["veredicto"] = ("descalificado: p(musica) baja" if pm < U_MUSICA_TAKE
                                 else f"descalificado: drone ({r['onsets']:.2f} ataques/s)")
            fila["distancia"] = None
        else:
            dist, det = distancia(r, ro)
            fila["veredicto"] = "candidato"
            fila["distancia"] = round(dist, 3)
        tabla.append(fila)
        log(f"    {nom:<10} p(mus) {pm:.2f}  dens {r['densidad']:.2f}  ataques {r['onsets']:.1f}  "
            f"-> {fila['veredicto']}{'' if fila['distancia'] is None else f' dist {fila['distancia']:.3f}'}")
    orden = sorted([f for f in tabla if f["distancia"] is not None], key=lambda f: f["distancia"])
    return [f["take"] for f in orden], tabla
