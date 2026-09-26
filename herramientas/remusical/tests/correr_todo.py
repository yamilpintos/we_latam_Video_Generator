# -*- coding: utf-8 -*-
"""
Corre TODAS las pruebas y devuelve 0 si pasan todas.

    cd apps/remusical && python -m tests.correr_todo

Ninguna de estas pruebas gasta un peso: no llaman a ElevenLabs, no alquilan una máquina
en Vast, no tocan Drive ni el bucket. Todo lo de afuera está reemplazado por dobles.
Se pueden correr en cualquier momento, sin credenciales.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

PRUEBAS = [
    ("test_vast_falso", "Vast: elige la verificada más barata y DESTRUYE la máquina siempre"),
    ("test_selector_tandas", "el selector de la web: costo antes de gastar, topes intactos"),
    ("test_drive_bucket", "Drive por cuenta de servicio → bucket por URL firmada"),
    ("test_takes_bajo_demanda", "un solo take, y otro sólo si el primero se descalifica"),
    ("test_guardas_replicate", "guardas de gasto de Replicate (camino PARADO, se prueba igual)"),
]


def main() -> int:
    print(f"Corriendo {len(PRUEBAS)} pruebas desde {RAIZ}\n")
    fallaron = []
    for mod, que in PRUEBAS:
        t0 = time.time()
        r = subprocess.run([sys.executable, "-m", f"tests.{mod}"], cwd=str(RAIZ),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = r.returncode == 0
        print(f"  {'PASA ' if ok else 'FALLA'}  {mod:<26} {time.time()-t0:>5.1f}s   {que}")
        if not ok:
            fallaron.append(mod)
            for linea in (r.stdout or "").splitlines():
                if "FALLA" in linea:
                    print(f"           {linea.strip()}")
            if r.stderr.strip():
                print(f"           {r.stderr.strip().splitlines()[-1]}")
    print()
    if fallaron:
        print(f"FALLARON {len(fallaron)}: {', '.join(fallaron)}")
        return 1
    print(f"LAS {len(PRUEBAS)} PRUEBAS PASAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
