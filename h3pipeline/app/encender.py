"""Tarea: encender la máquina (ver maquina.encender).

    python -X utf8 -u -m h3pipeline.app.encender [id_de_oferta]
"""
import sys

from . import maquina


def main() -> int:
    pedido = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    inst = maquina.encender(pedido, log=lambda s: print(s, flush=True))
    return 0 if inst else 1


if __name__ == "__main__":
    raise SystemExit(main())
