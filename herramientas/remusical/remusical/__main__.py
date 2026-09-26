# -*- coding: utf-8 -*-
"""
Uso:
  python -m remusical VIDEO [VIDEO ...] [--salida DIR] [--completo] [--takes N]

Deja, al lado de cada video, la carpeta `re-musical/` con el MP4 nuevo, los stems
y el informe. Con --completo separa el archivo entero (stems completos, más lento).
"""
import argparse
import sys
from pathlib import Path

# La consola de Windows es cp1252: cualquier "→" o "−" en un log tiraba el proceso
# entero DESPUÉS de 30 min de trabajo. Los dos puntos de entrada fuerzan UTF-8.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)   # con salida a archivo, sin esto el log aparece recién al final
    except Exception:
        pass

from .orquestador import procesar


def main():
    ap = argparse.ArgumentParser(prog="remusical", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="+", type=Path)
    ap.add_argument("--salida", type=Path, default=None, help="carpeta de salida (default: re-musical/ junto al video)")
    ap.add_argument("--completo", action="store_true", help="separar el archivo entero para entregar stems completos")
    ap.add_argument("--takes", type=int, default=None,
                    help="MÁXIMO de takes por pista (default 3). Se genera 1 y sólo se piden más si no convence")
    a = ap.parse_args()
    fallos = 0
    for v in a.videos:
        if not v.exists():
            print(f"no existe: {v}", file=sys.stderr)
            fallos += 1
            continue
        kw = dict(salida_dir=a.salida, separar_completo=a.completo)
        if a.takes:
            kw["takes_por_region"] = a.takes
        try:
            inf = procesar(v, **kw)
            print(f"{inf['estado']}: {v.name}")
        except Exception as e:
            print(f"ERROR {v.name}: {e}", file=sys.stderr)
            fallos += 1
    sys.exit(1 if fallos else 0)


if __name__ == "__main__":
    main()
