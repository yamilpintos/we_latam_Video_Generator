"""Tarea: los pasos de una serie que llaman a una API (ver app/series.py).

    python -X utf8 -u -m h3pipeline.app.serie_tarea hojas      <serie> [--motor openai] [--rehacer] [ids…]
    python -X utf8 -u -m h3pipeline.app.serie_tarea planificar <serie> <n> [pista…]
    python -X utf8 -u -m h3pipeline.app.serie_tarea guion      <serie> <n>
    python -X utf8 -u -m h3pipeline.app.serie_tarea producir   <serie> <n> [--hasta proyecto|dibujos|cola] [--motor openai]
    python -X utf8 -u -m h3pipeline.app.serie_tarea producir-aprobados <serie> [--motor openai]
    python -X utf8 -u -m h3pipeline.app.serie_tarea guiones    <serie>                      # aprueba todo y escribe los guiones que falten
    python -X utf8 -u -m h3pipeline.app.serie_tarea masa       <serie> [--sin-cola] [--no-apagar]   # TODO solo: guiones, producir, máquina, videos, másters (alquila)
    python -X utf8 -u -m h3pipeline.app.serie_tarea dialogos   <serie> <n> [--sin-cola]     # largo narrado: los personajes dicen sus citas (alquila)
"""
import sys

from . import series


def _opt(args: list[str], nombre: str, default: str | None = None) -> str | None:
    if nombre in args:
        i = args.index(nombre)
        v = args[i + 1] if i + 1 < len(args) else default
        del args[i:i + 2]
        return v
    return default


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    que, slug, resto = sys.argv[1], sys.argv[2], list(sys.argv[3:])
    log = lambda s: print(s, flush=True)
    try:
        if que == "hojas":
            motor = _opt(resto, "--motor", "openai")
            rehacer = "--rehacer" in resto
            ids = [x for x in resto if not x.startswith("--")]
            series.generar_hojas(slug, ids or None, motor=motor, rehacer=rehacer, log=log)
        elif que == "planificar":
            n = int(resto[0]) if resto else 10
            series.planificar(slug, n, pista=" ".join(resto[1:]), log=log)
        elif que == "guion":
            series.escribir_guion(slug, int(resto[0]), log=log)
        elif que == "producir":
            hasta = _opt(resto, "--hasta", "cola")
            motor = _opt(resto, "--motor", "openai")
            rehacer = "--rehacer" in resto
            resto = [x for x in resto if x != "--rehacer"]
            series.producir(slug, int(resto[0]), hasta=hasta, motor=motor, log=log, rehacer=rehacer)
        elif que == "guiones":
            series.guiones_todos(slug, log=log)
        elif que == "masa":
            motor = _opt(resto, "--motor", "openai")
            series.masa(slug, motor=motor, correr_cola="--sin-cola" not in resto, apagar="--no-apagar" not in resto, log=log)
        elif que == "dialogos":
            series.dialogos_capitulo(slug, int(resto[0]), correr="--sin-cola" not in resto, apagar="--no-apagar" not in resto, log=log)
        elif que == "producir-aprobados":
            motor = _opt(resto, "--motor", "openai")
            series.producir_aprobados(slug, motor=motor, log=log)
        else:
            print(__doc__)
            return 2
        return 0
    except Exception as e:
        log(f"!! {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
