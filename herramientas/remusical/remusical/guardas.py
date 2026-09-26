# -*- coding: utf-8 -*-
"""
Las seis guardas. Deciden solas si un entregable sale o se rechaza.

Cada una nace de un defecto real, y se validaron contra el entregable que el usuario
rechazó (v2: RECHAZADO por 3 guardas) y el que aprobó (v4: ENTREGABLE).

  1 alcance          fuera de las regiones, bit a bit idéntico
  2 voz intacta      desfase ≤ 1 ms (los stems a 44100 indexados como 48000)
  3 región completa  sin música justo AFUERA de cada región ("vuelve la intro")
  4 música presente  con música ADENTRO (el retumbe; el outro mudo a −76 dB)
  5 nivel            POR PISTA, ±3 dB contra la música original, con y sin narración
                     (la mediana global pasaba mientras pistas sueltas se iban ±9 dB)
  6 pico             sin clipeo DENTRO de las regiones (el original ya venía a 0 dBFS)

Una guarda que rechaza algo bueno bloquea todas las entregas: por eso cada una se
valida contra un caso malo Y uno bueno antes de cablearse.
"""
from __future__ import annotations

import numpy as np

from . import config as C
from .audio import a16k, db, mono
from .mapa import Region, p_musica_media

MARGEN_FUERA = 12.0


def auditar(orig: np.ndarray, sal: np.ndarray, voz: np.ndarray, regs: list[Region],
            inst: np.ndarray | None = None, musica: np.ndarray | None = None) -> list[dict]:
    n = min(len(orig), len(sal))
    o, s = orig[:n], sal[:n]
    mo_, ms_ = mono(o), mono(s)
    sr = C.SR
    dur = n / sr
    res = []

    dentro = np.zeros(n, bool)
    for r in regs:
        dentro[int(r.inicio * sr):int(r.fin * sr)] = True

    # 1
    d = np.abs(o - s).max(axis=1)
    fuera = float(d[~dentro].max()) if (~dentro).any() else 0.0
    fuera_db = 20 * np.log10(fuera + 1e-12)
    res.append(dict(n=1, nombre="alcance", ok=bool(fuera_db <= -60),
                    detalle=f"fuera de las regiones {fuera_db:.0f} dBFS (límite -60)"))

    # 2
    peor = 0.0
    for r in regs:
        a, b = int(r.inicio * sr), int(r.fin * sr)
        if b - a < 3 * sr:
            continue
        x, y = mo_[a:b] - mo_[a:b].mean(), ms_[a:b] - ms_[a:b].mean()
        M = int(0.05 * sr)
        c = np.correlate(y[M:-M], x, mode="valid")
        peor = max(peor, abs((np.argmax(c) - M) / sr * 1000))
    res.append(dict(n=2, nombre="voz intacta", ok=bool(peor <= 1.0),
                    detalle=f"peor desfase {peor:.2f} ms (límite 1,00)"))

    # 3 — "no quedó música vieja justo afuera de la región"
    # ★ La ventana de afuera se RECORTA a lo que no pertenece a otra región nuestra. En
    #   'La ruta de la seda' la región 11 terminaba 6 s antes de la 12: la mitad de la
    #   ventana "antes de la 12" era nuestra propia música nueva, la guarda la tomó por
    #   música vieja y el orquestador amplió la región hasta pisar a la vecina. Tres veces.
    peor_p, donde, lado_malo = 0.0, "", None
    for i, r in enumerate(regs):
        otros = [o for o in regs if o is not r]
        for lado in ("antes", "despues"):
            if lado == "antes":
                t1 = r.inicio
                t0 = max([r.inicio - MARGEN_FUERA, 0.0] + [o.fin for o in otros if o.fin <= r.inicio + 0.5])
            else:
                t0 = r.fin
                t1 = min([r.fin + MARGEN_FUERA, dur] + [o.inicio for o in otros if o.inicio >= r.fin - 0.5])
            if t1 - t0 < 4:
                continue                                  # no hay 4 s libres: nada que mirar
            p = p_musica_media(a16k(s[int(t0 * sr):int(t1 * sr)]))
            if p is not None and p > peor_p:
                peor_p, donde, lado_malo = p, f"{lado} de la región {i+1} ({t0:.0f}-{t1:.0f}s)", (i, lado)
    res.append(dict(n=3, nombre="región completa", ok=bool(peor_p <= C.U_MUSICA),
                    detalle=f"p(música) {peor_p:.3f} justo {donde} (límite {C.U_MUSICA})",
                    region_lado=lado_malo))

    # 4 — "adentro hay música de verdad"
    # ★ El umbral es RELATIVO a lo que medía el original en esa región. Una cama a −46 dB
    #   bajo narración al 100 % daba p=0,27 en el original; exigirle 0,30 al reemplazo
    #   es pedirle más presencia que la que tenía, y ningún take lo iba a pasar.
    peor_in, donde_in, reg_mala = 1.0, "", None
    peor_lim = C.U_MUSICA
    for i, r in enumerate(regs):
        if r.largo < 4:
            continue
        p = p_musica_media(a16k(s[int(r.inicio * sr):int(r.fin * sr)]))
        lim = min(C.U_MUSICA, 0.8 * float(getattr(r, "p_musica", C.U_MUSICA) or C.U_MUSICA))
        if p is not None and (p - lim) < (peor_in - peor_lim):
            peor_in, peor_lim, donde_in, reg_mala = p, lim, f"región {i+1}", i
    res.append(dict(n=4, nombre="música presente", ok=bool(peor_in >= peor_lim),
                    detalle=f"p(música) mínima {peor_in:.3f} en {donde_in} (límite {peor_lim:.3f}: "
                            f"el original ahí medía {peor_lim/0.8:.3f})" if peor_lim < C.U_MUSICA else
                            f"p(música) mínima {peor_in:.3f} en {donde_in} (límite {C.U_MUSICA})",
                    region=reg_mala))

    # 5 — nivel POR PISTA, con y sin narración, en la banda de la música (250-8000 Hz)
    # ★ La versión anterior comparaba la MEZCLA en los huecos de voz y tomaba la mediana
    #   de todo el video: pasó con +0,2 dB mientras pista por pista la música nueva se iba
    #   de −9 a +8 dB. "Los volúmenes de las pistas nuevas no son iguales a los originales"
    #   — tenían razón. Ahora cada pista tiene que dar ±3 dB en las dos condiciones, contra
    #   la MÚSICA original (stem instrumental), no contra la mezcla. Si no hay stems (uso
    #   sin separación), queda la versión vieja por mediana.
    h = int(0.5 * sr)
    if inst is not None and musica is not None:
        from .audio import nivel_banda
        peor, donde, por_pista = 0.0, "", {}
        for i, r in enumerate(regs):
            a, b = int(r.inicio * sr), int(r.fin * sr)
            con, sin = [], []
            for k in range(a, b - h, h):
                (con if db(voz[k:k + h]) > C.U_VOZ_DB else sin).append(k)
            difs = {}
            for nom, ks in (("bajo voz", con), ("sin voz", sin)):
                if len(ks) < 2:
                    continue
                o_ = nivel_banda(np.concatenate([inst[k:k + h] for k in ks]))
                if o_ < -60:
                    continue                              # el original ahí no tenía música medible
                difs[nom] = nivel_banda(np.concatenate([musica[k:k + h] for k in ks])) - o_
            if difs:
                por_pista[i] = difs
                peor_i = max(difs.values(), key=abs)
                if abs(peor_i) > abs(peor):
                    peor, donde = peor_i, f"pista {i+1} ({max(difs, key=lambda k: abs(difs[k]))})"
        dentro_tol = sum(1 for d in por_pista.values() if all(abs(v) <= C.TOL_NIVEL_DB for v in d.values()))
        res.append(dict(n=5, nombre="nivel", ok=bool(abs(peor) <= C.TOL_NIVEL_DB),
                        detalle=f"peor pista {peor:+.1f} dB en {donde} (límite ±{C.TOL_NIVEL_DB}; "
                                f"{dentro_tol}/{len(por_pista)} pistas dentro)",
                        desvio=peor, por_pista=por_pista))
    else:
        difs = []
        for r in regs:
            a, b = int(r.inicio * sr), int(r.fin * sr)
            for k in range(a, b - h, h):
                if db(voz[k:k + h]) > -45:
                    continue
                do, ds = db(mo_[k:k + h]), db(ms_[k:k + h])
                if do < -55:
                    continue
                difs.append(ds - do)
        medio = float(np.median(difs)) if difs else 0.0
        res.append(dict(n=5, nombre="nivel", ok=bool(abs(medio) <= C.TOL_NIVEL_DB),
                        detalle=f"desvío mediano {medio:+.1f} dB sobre {len(difs)} tramos "
                                f"(límite ±{C.TOL_NIVEL_DB})", desvio=medio))

    # 6
    pk = 20 * np.log10(np.abs(s[dentro]).max() + 1e-12) if dentro.any() else -99
    res.append(dict(n=6, nombre="pico", ok=bool(pk <= -0.05),
                    detalle=f"{pk:.2f} dBFS dentro de las regiones"))
    return res


def entregable(res: list[dict]) -> bool:
    return all(g["ok"] for g in res)
