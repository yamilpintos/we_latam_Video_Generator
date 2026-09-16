"""Tarea: generar un proyecto en LA MÁQUINA ya encendida e instalada.

    python -X utf8 -u -m h3pipeline.app.generar_en mis-videos/<slug>/proyecto.json

Aparta las salidas del proyecto anterior en la máquina, sube el ZIP del
proyecto, lo descomprime y lanza `lanzar.sh` (sin volver a correr setup.sh: los
modelos ya están). Escribe `corrida.json` en el proyecto para el taxímetro.
"""
import json
import sys
import time
from pathlib import Path

from .. import costos, vast
from ..proyecto import Proyecto
from . import maquina


def main() -> int:
    ruta = Path(sys.argv[1])
    p = Proyecto.cargar(ruta)
    c = ruta.parent
    zip_ = c / f"{p.slug}-para-vast.zip"
    if not zip_.exists():
        print("!! falta el ZIP: empaquetá primero")
        return 1
    m = maquina.leer()
    if m.get("fase") != "lista" or not m.get("instancia"):
        print(f"!! la máquina no está lista (fase {m.get('fase')})")
        return 1
    inst = vast.instancia(int(m["instancia"]))
    anterior = m.get("proyecto")
    if anterior and anterior != p.slug:
        print(f"apartando las salidas de {anterior}…")
        vast.ejecutar(inst, f"cd {vast.SALIDA_REMOTA} 2>/dev/null && mkdir -p _{anterior} && "
                            f"mv *.mp4 *.json _{anterior}/ 2>/dev/null; true", timeout=60)
    vast.subir(inst, zip_)
    vast.ejecutar(inst, f"export PATH=/venv/main/bin:$PATH && cd /workspace/refs && unzip -oq {zip_.name} && "
                        f"sed -i 's/\\r$//' *.sh *.py && cp planos.json /root/planos.json", timeout=180)
    vast.lanzar(inst, "export PATH=/venv/main/bin:$PATH && cd /workspace/refs && PASOS=8 GPUS=4 bash lanzar.sh",
                log=vast.LOG_CORRIDA)
    planos = p.construir()[1]["planos"]
    est = costos.estimar(planos, costos.Maquina(dph=float(m.get("dph", 2.0))))
    (c / "corrida.json").write_text(json.dumps(
        {"instancia": int(m["instancia"]), "dph": float(m.get("dph", 0)), "inicio": time.time(),
         "estimado": round(est.costo_generacion, 2), "maquina_compartida": True}), encoding="utf-8")
    maquina.escribir(proyecto=p.slug, generando_desde=time.time())
    print(f"{p.titulo}: {len(planos)} planos lanzados en la instancia {m['instancia']} · "
          f"estimado de generación ${est.costo_generacion:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
