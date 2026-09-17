"""LA COLA: varios proyectos, una sola máquina encendida.

`app/cola.json`:
    items: [{slug, estado: pendiente|generando|bajando|bajado|error, nota}]
    apagar_al_final: bool
    corriendo: bool

`correr_cola.py` (tarea): enciende la máquina si hace falta y espera la
instalación; después, por cada pendiente: genera, espera los clips, baja; al
final apaga si se pidió. Un proyecto que falla no frena a los demás.
"""
from __future__ import annotations

import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
# En mis-videos/_estado (disco persistente en un servidor); ver maquina.ESTADO.
ESTADO = AQUI.parent.parent / "mis-videos" / "_estado" / "cola.json"
_ESTADO_VIEJO = AQUI / "cola.json"


def leer() -> dict:
    if not ESTADO.exists() and _ESTADO_VIEJO.exists():
        try:
            ESTADO.parent.mkdir(parents=True, exist_ok=True)
            _ESTADO_VIEJO.replace(ESTADO)
        except Exception:
            pass
    if not ESTADO.exists():
        return {"items": [], "apagar_al_final": True, "corriendo": False}
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        return {"items": [], "apagar_al_final": True, "corriendo": False}


def escribir(d: dict) -> dict:
    ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ESTADO.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def agregar(slug: str) -> dict:
    d = leer()
    if not any(i["slug"] == slug for i in d["items"]):
        d["items"].append({"slug": slug, "estado": "pendiente", "nota": ""})
    return escribir(d)


def quitar(slug: str) -> dict:
    d = leer()
    d["items"] = [i for i in d["items"] if i["slug"] != slug or i["estado"] == "generando"]
    return escribir(d)


def marcar(slug: str, estado: str, nota: str = "") -> dict:
    d = leer()
    for i in d["items"]:
        if i["slug"] == slug:
            i["estado"] = estado
            i["nota"] = nota
    return escribir(d)


def pendientes() -> list[str]:
    return [i["slug"] for i in leer()["items"] if i["estado"] in ("pendiente", "error")]
