"""Retoma una instancia ya alquilada por cazar.py desde «autorizar clave».

    python -X utf8 -u mis-videos/replica-danza/retomar.py <instancia> <maquina> <geo>

El 14/9 el cazador alquiló 51065897 (Taiwán, máquina 41285) justo cuando se lo
detenía para cambiarle los filtros: la instancia quedó creada y sin lanzar.
Esto hace el resto del camino de cazar.py, sin destruir al terminar.
"""
import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1]))
from h3pipeline import vast  # noqa: E402

ZIP = AQUI / "replica-danza-muestra-a-para-vast.zip"
iid, maquina, geo = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
log = lambda m: print(m, flush=True)  # noqa: E731

vast.autorizar_clave(iid)
inst = vast.esperar_lista(iid, minutos=10, log=log)
salida = vast.ejecutar(inst, "curl -s -o /dev/null -m 20 -w '%{http_code}' "
                             "https://huggingface.co/api/models/Comfy-Org/MiniMax-H3", timeout=60)
if not salida.strip().endswith("200"):
    log(f"SIN SALIDA A HUGGING FACE ({salida.strip()!r}): decidir a mano, no se destruye")
    sys.exit(3)
log("Hugging Face responde 200")
(AQUI / "corrida.json").write_text(json.dumps(
    {"instancia": iid, "dph": float(inst.get("dph_total") or 0), "inicio": time.time(),
     "estimado": 9.0, "maquina": maquina, "geo": geo}), encoding="utf-8")
vast.subir(inst, ZIP, log=log)
vast.generar(inst, ZIP.name, pasos=8, ref2va=True, log=log)
log(f"LISTO: muestra A lanzada en la instancia {iid}. NO se destruye al terminar.")
