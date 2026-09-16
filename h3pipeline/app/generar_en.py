"""Tarea: generar un proyecto en la máquina ya lista (ver maquina.generar_proyecto).

    python -X utf8 -u -m h3pipeline.app.generar_en mis-videos/<slug>/proyecto.json
"""
import sys
from pathlib import Path

from . import maquina


def main() -> int:
    slug = Path(sys.argv[1]).parent.name
    try:
        maquina.generar_proyecto(slug, log=lambda s: print(s, flush=True))
    except Exception as e:
        print(f"!! {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
