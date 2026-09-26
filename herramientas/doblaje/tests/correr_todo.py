# -*- coding: utf-8 -*-
"""Todas las pruebas de Doblaje, una atrás de otra. 0 créditos, 0 USD, nada prendido (DOBLAJE_GPU=off).

    cd herramientas/doblaje && python -X utf8 -u -m tests.correr_todo      → exit 0 si pasan todas
"""
import os
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PRUEBAS = ["test_creditos", "test_gpu_vast", "test_sep_vast", "test_procesar_sin_gastar"]
env = dict(os.environ, DOBLAJE_GPU="off", PYTHONUTF8="1")
malas = []
for p in PRUEBAS:
    print(f"\n================ {p}", flush=True)
    r = subprocess.run([sys.executable, "-X", "utf8", "-u", "-m", f"tests.{p}"], cwd=str(AQUI.parent), env=env)
    if r.returncode != 0:
        malas.append(p)
print("\nTODAS PASAN" if not malas else f"\nFALLAN: {malas}")
sys.exit(1 if malas else 0)
