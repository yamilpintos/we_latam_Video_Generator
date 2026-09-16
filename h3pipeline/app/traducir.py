"""Tarea: guion.json → proyecto.json validado (corre como subproceso de la Fábrica).

    python -X utf8 -u -m h3pipeline.app.traducir mis-videos/<slug>/guion.json
"""
import json
import sys
from pathlib import Path

from .. import guionista
from ..proyecto import Proyecto


def main() -> int:
    ruta = Path(sys.argv[1])
    g = json.loads(ruta.read_text(encoding="utf-8"))
    c = ruta.parent
    print(f"guion: {len(g['guion'])} caracteres · {g['formato']}/{g['estructura']} · voz {g.get('voz')}")
    r = guionista.traducir(
        g["guion"], formato=g["formato"], estructura=g["estructura"], estilo_imagen=g["estilo_imagen"],
        estilo_video=g.get("estilo_video", ""), cierre_video=g.get("cierre_video", ""),
        medio=g.get("medio", ""), voz=g.get("voz"), titulo=g.get("titulo", ""),
        negativos=g.get("negativos", True), notas=g.get("notas", ""), duracion=g.get("duracion"))
    d = r["proyecto"]
    d["slug"] = g["slug"]
    (c / "proyecto.json").write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    p = Proyecto.cargar(c / "proyecto.json")
    p.escribir(log=lambda *_: None)
    print(f"\nproyecto.json escrito: {len(d['planos'])} planos · {len(d.get('voz', []))} líneas de voz · "
          f"{r['intentos']} llamada(s)")
    if r["avisos"]:
        print(f"{len(r['avisos'])} aviso(s) que quedaron:")
        for a in r["avisos"]:
            print("  ⚠", a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
