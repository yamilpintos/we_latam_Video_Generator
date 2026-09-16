"""LA MÁQUINA: una 4×RTX 5090 encendida, con H3 instalado, esperando trabajo.

Hasta ahora cada proyecto alquilaba su propia instancia y la instalación (59 GB
de modelos) se pagaba cada vez. Acá la máquina es una cosa aparte: se enciende
una vez, se instala una vez, y los proyectos se generan en ella uno tras otro
(como se hizo a mano el 13/9 con el koi y el invernadero). El estado vive en
`app/maquina.json`:

    fase        arrancando | instalando | lista | fallo | apagada
    instancia   id en Vast
    dph         $/h
    inicio/fin  timestamps; `gasto_final` al apagar
    proyecto    slug del proyecto que está generando ahora (o null)

Las fases las escribe `encender.py` (tarea) y las lee el servidor; el avance de
la instalación se mide por SSH: bytes en /workspace/ComfyUI/models contra los
~59 GB esperados, y el «Listo. Ahora:» que imprime setup.sh al terminar.
"""
from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

from .. import vast

AQUI = Path(__file__).resolve().parent
ESTADO = AQUI / "maquina.json"
ZIP_SETUP = AQUI / "h3-setup.zip"
REMOTO = AQUI.parent / "remoto"
BYTES_MODELOS = 59e9          # perfil max, SOLO_FL=1 (COSTOS §12, VAST.md)
TECHO_DPH = 4.0


def leer() -> dict:
    if not ESTADO.exists():
        return {"fase": "apagada"}
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        return {"fase": "apagada"}


def escribir(**cambios) -> dict:
    d = leer()
    d.update(cambios)
    ESTADO.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def zip_setup() -> Path:
    """Sólo los scripts de la máquina: setup.sh baja los modelos sin necesitar
    planos (SOLO_FL=1 por defecto cuando no hay planos.json)."""
    with zipfile.ZipFile(ZIP_SETUP, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("setup.sh", "lanzar.sh", "rescate.sh", "runner.py"):
            z.write(REMOTO / n, n)
    return ZIP_SETUP


def apta(o: vast.Oferta) -> tuple[bool, list[str]]:
    motivos = []
    if o.verificacion != "verified":
        motivos.append("desverificada" if o.verificacion == "deverified" else "sin verificar")
    if o.dph > TECHO_DPH:
        motivos.append("precio absurdo")
    if o.fiabilidad < 0.995:
        motivos.append("fiabilidad < 0,995")
    if "shanghai" in o.geo.lower():
        motivos.append("Shanghái")
    if o.inet_down < 800:
        motivos.append("enlace < 800 Mbps")
    if "5090" not in o.gpu:
        motivos.append("no es 5090")
    return not motivos, motivos


def mejor_oferta() -> vast.Oferta | None:
    """La 4×5090 apta de mayor fiabilidad; a igual fiabilidad, más enlace."""
    lista = [o for o in vast.buscar(gpu="RTX 5090") if apta(o)[0]]
    if not lista:
        return None
    return max(lista, key=lambda o: (round(o.fiabilidad, 3), o.inet_down))


_cache: dict = {"t": 0, "v": None}


def progreso_instalacion(inst: dict, cada: float = 15.0) -> dict:
    """{gb, pct, listo, ultimo} por SSH, cacheado `cada` segundos."""
    ahora = time.time()
    if _cache["v"] and ahora - _cache["t"] < cada:
        return _cache["v"]
    try:
        salida = vast.ejecutar(
            inst, "du -sb /workspace/ComfyUI/models 2>/dev/null | cut -f1; "
                  "grep -c 'Listo. Ahora' /root/corrida.log 2>/dev/null; "
                  "tail -n 2 /root/corrida.log 2>/dev/null", timeout=40)
        lineas = salida.splitlines()
        b = float(lineas[0]) if lineas and lineas[0].strip().isdigit() else 0.0
        listo = len(lineas) > 1 and lineas[1].strip().isdigit() and int(lineas[1]) > 0
        v = {"gb": round(b / 1e9, 1), "pct": min(99, int(b / BYTES_MODELOS * 100)) if not listo else 100,
             "listo": listo, "ultimo": "\n".join(lineas[2:])[-400:]}
    except Exception as e:
        v = {"gb": None, "pct": None, "listo": False, "ultimo": f"(sin respuesta: {e})"}
    _cache.update(t=ahora, v=v)
    return v


def gasto(d: dict) -> dict:
    if not d.get("inicio"):
        return {"minutos": 0, "acumulado": 0.0}
    fin = d.get("fin") or time.time()
    horas = (fin - d["inicio"]) / 3600
    return {"minutos": round(horas * 60), "acumulado": round(d.get("dph", 0) * horas, 2)}
