# -*- coding: utf-8 -*-
"""
Monta la música nueva sobre la voz original, región por región.

  salida[region] = voz + musica_nueva · ganancia(t)
  ganancia = nivel_base − DUCK · presencia_de_voz(t)

  nivel_base: lo que mide el ORIGINAL donde la música suena sola (voz < −45 dB).
              No se usa la envolvente del original: sale del instrumental, que trae
              viento, y una ráfaga hundía todo lo demás. La música nueva es OTRA y
              tiene otra forma; lo que tiene que coincidir es cuánto suena, no cuándo.
  fade:       para un OUTRO, el punto de fade del tema generado se ancla al punto de
              fade del original.
  crossfade:  cuando una región arranca donde terminó la anterior (dos pistas seguidas
              sin hueco, ver segmentar.py), no se funde a silencio y se vuelve a subir:
              se cruzan XF segundos a potencia constante. Un corte seco o un bache
              entre pistas es lo que delata un montaje.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import maximum_filter1d, uniform_filter1d

from . import config as C
from .audio import db, mono
from .mapa import Region

XF_S = 3.0            # crossfade entre pistas contiguas


def nivel_musica_sola(mezcla: np.ndarray, voz: np.ndarray, inst: np.ndarray, r: Region) -> float:
    a, b = int(r.inicio * C.SR), int(r.fin * C.SR)
    h = int(0.5 * C.SR)
    vals = [db(mezcla[k:k + h]) for k in range(a, b - h, h)
            if db(voz[k:k + h]) < -45 and db(mezcla[k:k + h]) > -55]
    if len(vals) >= 3:
        return float(np.median(vals))
    return db(inst[a:b])


def _presencia_voz(voz_reg: np.ndarray) -> np.ndarray:
    v = np.abs(mono(voz_reg))
    h = int(0.02 * C.SR)
    n_h = max(1, len(v) // h)
    env = np.array([20 * np.log10(np.sqrt(np.mean(v[i*h:(i+1)*h] ** 2)) + 1e-9) for i in range(n_h)])
    p = np.clip((env - C.U_VOZ_DB) / 12.0, 0.0, 1.0)
    p = maximum_filter1d(p, max(1, int(C.ATAQUE_S / 0.02)))
    p = uniform_filter1d(p, max(1, int(C.SALIDA_S / 0.02)), mode="nearest")
    return np.interp(np.arange(len(v)), np.arange(n_h) * h + h / 2, p)


def _punto_de_fade(y: np.ndarray) -> float:
    """Segundos donde el nivel cae 6 dB bajo su mediana y no vuelve."""
    h = int(0.5 * C.SR)
    m = mono(y)
    d = np.array([db(m[k:k + h]) for k in range(0, len(m) - h, h)])
    if len(d) < 4:
        return len(m) / C.SR
    med = np.median(d[: max(2, int(len(d) * 0.8))])
    bajo = d < med - 6
    k = len(d)
    while k > 0 and bajo[k - 1]:
        k -= 1
    return k * 0.5


def _vecinos(r: Region, regs: list[Region]) -> tuple[bool, bool]:
    antes = any(o is not r and abs(o.fin - r.inicio) < 0.5 for o in regs)
    despues = any(o is not r and abs(o.inicio - r.fin) < 0.5 for o in regs)
    return antes, despues


def montar(mezcla: np.ndarray, voz: np.ndarray, inst: np.ndarray, regs: list[Region],
           takes: dict[int, np.ndarray], ajuste_db: dict[int, float] | None = None,
           log=print) -> tuple[np.ndarray, list[dict], np.ndarray]:
    ajuste_db = ajuste_db or {}
    n = len(mezcla)
    sr = C.SR
    xf = int(XF_S * sr)
    musica = np.zeros_like(mezcla)
    tocado = np.zeros(n, bool)
    detalle = []

    for i, r in enumerate(regs):
        a, b = int(r.inicio * sr), int(r.fin * sr)
        ant, desp = _vecinos(r, regs)
        a2 = max(0, a - xf // 2) if ant else a          # la región se extiende medio crossfade
        b2 = min(n, b + xf // 2) if desp else b         # hacia cada vecina contigua
        m = b2 - a2
        t = takes[i]
        base = nivel_musica_sola(mezcla, voz, inst, r) + ajuste_db.get(i, 0.0)

        if r.etiqueta == "OUTRO":
            fade_film = _punto_de_fade(mezcla[a:b]) + (a - a2) / sr
            fade_tema = _punto_de_fade(t)
            d0 = int(round((fade_tema - fade_film) * sr))
            d0 = max(0, min(d0, max(0, len(t) - m)))
        else:
            d0 = 0
        trozo = t[d0:d0 + m]
        if len(trozo) < m:
            trozo = np.pad(trozo, ((0, m - len(trozo)), (0, 0)))

        pres = _presencia_voz(voz[a2:b2])
        g_db = base - C.DUCK_DB * pres
        mus = trozo / (np.sqrt(np.mean(trozo ** 2)) + 1e-12)
        mus = mus * (10 ** (g_db / 20))[:, None]

        al_final = r.fin > n / sr - 1.0
        sub = xf if ant else int((0.03 if r.inicio < 1.0 else 1.0) * sr)
        baj = xf if desp else int((1.6 if al_final else 2.5) * sr)
        sub, baj = min(sub, m // 2), min(baj, m // 2)
        w = np.ones(m)
        if sub:
            w[:sub] = np.linspace(0, 1, sub) ** 0.5           # potencia constante con la vecina
        if baj:
            w[-baj:] = np.linspace(1, 0, baj) ** 0.5
        mus *= w[:, None]

        musica[a2:b2] += mus
        tocado[a2:b2] = True
        detalle.append(dict(region=i, etiqueta=r.etiqueta, inicio=r.inicio, fin=r.fin,
                            nivel_base_db=round(base, 1), desde_s=round(d0 / sr, 2),
                            voz_presente=round(float((pres > 0.5).mean()), 2),
                            crossfade_antes=ant, crossfade_despues=desp))
        log(f"    región {i+1:>2} {r.etiqueta:<7} {r.inicio:7.1f}-{r.fin:7.1f}s  nivel {base:6.1f} dB  "
            f"tema desde {d0/sr:5.1f}s  voz {float((pres>0.5).mean())*100:3.0f}%"
            f"{'  <-xf' if ant else ''}{'  xf->' if desp else ''}")

    sal = mezcla.copy()
    sal[tocado] = voz[tocado] + musica[tocado]
    # limitador sólo sobre lo tocado
    pk = float(np.abs(sal[tocado]).max()) if tocado.any() else 0.0
    if pk > 0.99:
        sal[tocado] *= 0.99 / pk
        musica[tocado] *= 0.99 / pk
    return sal, detalle, musica


# ---------------------------------------------------------------------------------
# NIVELAR: la música nueva al volumen exacto de la original, pista por pista
# ---------------------------------------------------------------------------------
# Por qué existe: el montaje ponía la música nueva al nivel de la MEZCLA en los huecos
# de voz (que incluye viento) y bajaba 9 dB fijos bajo la narración. Medido en 'La ruta
# de la seda': pista por pista la música nueva se iba de −9 a +8 dB respecto de la
# original, y bajo la voz de −9 a +12 dB. La mediana daba +0,2 y la guarda pasaba.
#
# Qué hace: por pista, mide la MÚSICA ORIGINAL (stem instrumental, banda 250-8000 Hz)
# en dos condiciones — con narración encima y sin — y la música nueva en las mismas
# dos, y le aplica a la nueva la ganancia que iguala cada condición. El "ducking" deja
# de ser un número fijo: es el que hacía el original.
from .audio import nivel_banda


def _ventanas(voz: np.ndarray, a: int, b: int, h: int) -> tuple[list[int], list[int]]:
    con, sin = [], []
    for k in range(a, b - h, h):
        (con if db(voz[k:k + h]) > C.U_VOZ_DB else sin).append(k)
    return con, sin


def _nivel_en(x: np.ndarray, ks: list[int], h: int) -> float | None:
    if not ks:
        return None
    return nivel_banda(np.concatenate([x[k:k + h] for k in ks]))


def nivelar(mezcla: np.ndarray, voz: np.ndarray, inst: np.ndarray, musica: np.ndarray,
            regs: list[Region], tope_db: float = 12.0, log=print) -> tuple[np.ndarray, np.ndarray, list[dict]]:
    """Devuelve (salida, musica_corregida, detalle). No toca nada fuera de las regiones."""
    sr = C.SR
    h = int(0.5 * sr)
    n = len(mezcla)
    g = np.zeros(n)                       # ganancia en dB por muestra (0 = sin cambio)
    tocado = np.zeros(n, bool)
    detalle = []
    for i, r in enumerate(regs):
        a, b = int(r.inicio * sr), int(r.fin * sr)
        con, sin = _ventanas(voz, a, b, h)
        o_con, o_sin = _nivel_en(inst, con, h), _nivel_en(inst, sin, h)
        n_con, n_sin = _nivel_en(musica, con, h), _nivel_en(musica, sin, h)
        g_con = (o_con - n_con) if (o_con is not None and n_con is not None) else None
        g_sin = (o_sin - n_sin) if (o_sin is not None and n_sin is not None) else None
        if g_con is None and g_sin is None:
            detalle.append(dict(region=i, g_con=None, g_sin=None))
            continue
        if g_con is None:
            g_con = g_sin
        if g_sin is None:
            g_sin = g_con
        g_con, g_sin = float(np.clip(g_con, -tope_db, tope_db)), float(np.clip(g_sin, -tope_db, tope_db))
        curva = np.full(b - a, g_sin)
        for k in con:
            curva[k - a:k - a + h] = g_con
        # suavizado de 0,5 s para que el cambio con/sin voz no se escuche como un salto
        curva = uniform_filter1d(curva, h, mode="nearest")
        g[a:b] = curva
        tocado[a:b] = True
        detalle.append(dict(region=i, g_con=round(g_con, 1), g_sin=round(g_sin, 1),
                            orig_con=o_con and round(o_con, 1), orig_sin=o_sin and round(o_sin, 1)))
        log(f"    pista {i+1:>2} {r.inicio:7.1f}-{r.fin:7.1f}s  ganancia sin voz {g_sin:+5.1f} dB · bajo voz {g_con:+5.1f} dB")
    mus2 = musica * (10 ** (g / 20))[:, None]
    sal = mezcla.copy()
    sal[tocado] = voz[tocado] + mus2[tocado]
    # ★ Limitador que recorta SÓLO las muestras que pasan de 0,99. Escalar todas las
    #   regiones por un pico aislado (lo que hacía antes) bajaba todas las pistas a la vez
    #   y deshacía la nivelación recién hecha: la guarda 5 daba −3,7 dB en pistas que
    #   acababan de corregirse.
    exceso = np.abs(sal[tocado]) > 0.99
    if exceso.any():
        sal[tocado] = np.clip(sal[tocado], -0.99, 0.99)
        log(f"    limitador: {int(exceso.sum())} muestras recortadas ({exceso.sum()/sr*1000:.0f} ms)")
    return sal, mus2, detalle


def nivelar_hasta(mezcla, voz, inst, musica, regs, pasadas: int = 3, log=print):
    """Itera nivelar() hasta que todas las pistas queden dentro de ±TOL o se agoten
    las pasadas. Cada pasada corrige el residuo de la anterior (suavizados, bordes)."""
    from .guardas import auditar
    sal, mus, det = None, musica, []
    for p in range(pasadas):
        sal, mus, det = nivelar(mezcla, voz, inst, mus, regs, log=log if p == 0 else (lambda m: None))
        g5 = next(g for g in auditar(mezcla, sal, voz, regs, inst=inst, musica=mus) if g["n"] == 5)
        log(f"    pasada {p+1}: {g5['detalle']}")
        if g5["ok"]:
            break
    return sal, mus, det
