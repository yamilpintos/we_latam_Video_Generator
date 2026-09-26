# -*- coding: utf-8 -*-
"""
Prueba la generación de takes BAJO DEMANDA sin gastar un crédito: se inyectan un
generador y un selector falsos, y se cuenta cuántas veces se "paga".

  A. el primer take sirve            → 1 generación
  B. el primero es un drone          → 2 generaciones, se usa el segundo
  C. todos se parecen poco           → llega a TAKES_MAX y devuelve el menos malo
  D. exclusión (guarda 4 rechazó uno)→ no lo vuelve a elegir; genera otro
  E. takes ya en disco no se pagan   → 0 generaciones

Correr:  cd apps/remusical && python -m tests.test_takes_bajo_demanda
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from remusical.orquestador import takes_bajo_demanda  # noqa: E402

fallos = []


def check(cond, msg):
    print(("  OK   " if cond else "  FALLA") + " " + msg)
    if not cond:
        fallos.append(msg)


class Falso:
    """Generador + selector falsos, guiados por una lista de 'calidades' por take."""

    def __init__(self, calidades):
        self.calidades = calidades      # take1, take2, ... -> distancia (None = descalificado)
        self.generadas = 0

    def generar(self, prompt, largo, dst, log=print):
        self.generadas += 1
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"x")

    def leer(self, ruta):
        return np.zeros((10, 2))

    def elegir(self, ref, takes, log=print):
        tabla = []
        for nom in takes:
            d = self.calidades[int(nom[4:]) - 1]
            tabla.append(dict(take=nom, p_musica=0.6 if d is not None else 0.2, distancia=d,
                              veredicto="candidato" if d is not None else "descalificado: drone"))
        orden = [f["take"] for f in sorted([f for f in tabla if f["distancia"] is not None],
                                           key=lambda f: f["distancia"])]
        return orden, tabla


def corrida(calidades, excluir=None, pre=0):
    tmp = Path(tempfile.mkdtemp())
    f = Falso(calidades)
    for k in range(pre):                          # takes que ya estaban en disco
        (tmp / "takes").mkdir(exist_ok=True)
        (tmp / "takes" / f"r1_take{k+1}.wav").write_bytes(b"x")
    takes, orden, tabla = takes_bajo_demanda(0, "p", 30, np.zeros(10), tmp, takes_max=3, dist_max=0.45,
                                             excluir=excluir, log=lambda m: None,
                                             _generar=f.generar, _elegir=f.elegir, _leer=f.leer)
    shutil.rmtree(tmp, ignore_errors=True)
    return f.generadas, orden, len(takes)


print("\nA. el primer take sirve")
g, o, n = corrida([0.20, 0.10, 0.10])
check(g == 1 and o[0] == "take1", f"generadas {g}, elegido {o[0]}")

print("\nB. el primero es un drone")
g, o, n = corrida([None, 0.25, 0.10])
check(g == 2 and o[0] == "take2", f"generadas {g}, elegido {o[0]}")

print("\nC. ninguno se parece: llega al máximo y va el menos malo")
g, o, n = corrida([0.70, 0.60, 0.55])
check(g == 3 and o[0] == "take3", f"generadas {g}, elegido {o[0]} (el de menor distancia)")

print("\nD. exclusión: la guarda 4 rechazó take1")
g, o, n = corrida([0.20, 0.30, 0.10], excluir={"take1"}, pre=1)
check(g == 1 and o[0] == "take2", f"generadas {g} (una nueva), elegido {o[0]}, take1 excluido")

print("\nE. takes ya en disco no se vuelven a pagar")
g, o, n = corrida([0.20, 0.30, 0.10], pre=2)
check(g == 0 and o[0] == "take1" and n == 2, f"generadas {g}, {n} en disco, elegido {o[0]}")

print()
if fallos:
    print(f"FALLARON {len(fallos)}:", *fallos, sep="\n  ")
    sys.exit(1)
print("TAKES BAJO DEMANDA: TODO PASA")
