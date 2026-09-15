"""
Arma la carpeta de entrega: los documentos de las cuatro capas más el audio
producido, convertido a MP3 para que se pueda subir.

    python tools/build_entrega.py

No mueve nada: copia. Los archivos de trabajo quedan intactos.
"""

import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import retime  # noqa: E402
import timing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "output" / "mars-climate-orbiter"
DEST = ROOT / "ENTREGA-MCO-5min"
CAL_ALTA, CAL_MEDIA = 0.05, 0.30   # compression_level de libsndfile: menor = mejor


def a_mp3(origen: Path, destino: Path, calidad: float) -> int:
    x, sr = sf.read(origen, dtype="float32", always_2d=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    sf.write(destino, x.mean(axis=1), sr, format="MP3", compression_level=calidad)
    return destino.stat().st_size


def copiar(origen: Path, destino: Path) -> int:
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(origen, destino)
    return destino.stat().st_size


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST)
    total = {}

    def sumar(cap, n):
        total[cap] = total.get(cap, 0) + n

    # 0 · base
    for f in ("01-guion.md", "02-timeline.md"):
        sumar("0-BASE", copiar(BASE / f, DEST / "0-BASE" / f))

    # 1 · imágenes
    for f in ("03-biblia.md", "04-imagenes.md"):
        sumar("1-IMAGENES", copiar(BASE / f, DEST / "1-IMAGENES" / f))

    # 2 · movimiento
    sumar("2-MOVIMIENTO", copiar(BASE / "05-movimiento.md",
                                 DEST / "2-MOVIMIENTO" / "05-movimiento.md"))
    for f in ("shotlist-mco.csv", "depthflow_scenes.py", "depthflow_batch.py"):
        sumar("2-MOVIMIENTO", copiar(ROOT / "tools" / f,
                                     DEST / "2-MOVIMIENTO" / "herramientas" / f))

    # 3 · voz
    sumar("3-VOZ", copiar(BASE / "06-voz.md", DEST / "3-VOZ" / "06-voz.md"))
    sumar("3-VOZ", a_mp3(BASE / "voz" / "VO_TRACK_FINAL.wav",
                         DEST / "3-VOZ" / "VO_TRACK_FINAL.mp3", CAL_ALTA))
    for bid, _d, _m, takes in timing.BLOCKS:
        for i in range(1, len(takes) + 1):
            f = retime.take_file(bid, i)
            if f:
                sumar("3-VOZ", a_mp3(f, DEST / "3-VOZ" / "tomas" / f"VO_{bid}_T{i}.mp3",
                                     CAL_MEDIA))

    # 4 · sonido
    sumar("4-SONIDO", copiar(BASE / "07-sfx.md", DEST / "4-SONIDO" / "07-sfx.md"))
    sumar("4-SONIDO", a_mp3(BASE / "audio" / "MIX_COMPLETO.wav",
                            DEST / "4-SONIDO" / "MIX_COMPLETO.mp3", CAL_ALTA))
    for f in sorted((BASE / "audio").glob("STEM_*.wav")):
        sumar("4-SONIDO", a_mp3(f, DEST / "4-SONIDO" / "stems" / f"{f.stem}.mp3", CAL_MEDIA))
    for f in sorted((BASE / "audio").glob("*.mp3")):
        sumar("4-SONIDO", copiar(f, DEST / "4-SONIDO" / "fuentes" / f.name))

    print(f"{DEST}\n")
    for cap in sorted(total):
        n = len(list((DEST / cap).rglob("*.*")))
        print(f"  {cap:14s} {total[cap]/1048576:7.1f} MB   {n:3d} archivos")
    tot = sum(total.values())
    print(f"  {'TOTAL':14s} {tot/1048576:7.1f} MB   "
          f"{len(list(DEST.rglob('*.*')))} archivos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
