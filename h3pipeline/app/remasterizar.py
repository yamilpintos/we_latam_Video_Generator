"""Tarea: los pasos largos del remaster (ver app/remaster.py).

    python -X utf8 -u -m h3pipeline.app.remasterizar descargar <id>          # el link de Drive, con gdown
    python -X utf8 -u -m h3pipeline.app.remasterizar preparar <id>
    python -X utf8 -u -m h3pipeline.app.remasterizar correr   <id> [id_de_oferta]   # alquila y cobra
    python -X utf8 -u -m h3pipeline.app.remasterizar bajar    <id>
    python -X utf8 -u -m h3pipeline.app.remasterizar uhd      <id>
"""
import sys

from . import remaster


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    que, tid = sys.argv[1], sys.argv[2]
    log = lambda s: print(s, flush=True)
    if que == "descargar":
        try:
            remaster.descargar(tid, log=log)
            return 0
        except Exception as e:
            remaster.actualizar(tid, estado="error", nota=f"la descarga falló: {e}", progreso=None)
            log(f"!! {e}")
            return 1
    if que == "preparar":
        try:
            remaster.preparar(tid, log=log)
            return 0
        except Exception as e:
            remaster.actualizar(tid, estado="origen", nota=f"no pude preparar: {e}")
            log(f"!! {e}")
            return 1
    if que == "correr":
        oferta = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else None
        return 0 if remaster.correr(tid, oferta, log=log) else 1
    if que == "bajar":
        return 0 if remaster.bajar_de_nuevo(tid, log=log) else 1
    if que == "uhd":
        remaster.uhd(tid, log=log)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
