"""
EXPERIMENTO A · Una imagen máster → varios planos.

El pipeline pide 42 imágenes y el riesgo es que 42 generaciones no se parezcan
entre sí. Este experimento prueba lo contrario: generar UNA imagen por locación
y derivar los planos con recortes distintos + un movimiento de cámara distinto
en cada uno.

Ventajas si funciona:
  · La continuidad es perfecta por construcción: misma luz, misma paleta, mismo
    encuadre del mundo. No hay deriva posible.
  · Menos generaciones. Tres planos de una locación pasan de 3 imágenes a 1.
  · Se puede decidir el découpage DESPUÉS de tener la imagen.

El límite es la resolución: cada recorte usa una fracción del máster y se escala
a 1920. El script lo reporta para que sepas cuándo parar.

    .venv-depthflow/Scripts/python.exe tools/exp_master_a_planos.py --imagen RUTA
"""

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from depthflow.scene import DepthScene
sys.path.insert(0, str(Path(__file__).parent))
from depthflow_cine import ESCENAS  # noqa: E402

SALIDA = Path("output/experimentos")

# (nombre, (x, y, ancho, alto) en fracción del máster, escena, duración)
PLANOS = [
    ("1_general", (0.00, 0.00, 1.00, 1.00), "retirada", 5.0),
    ("2_medio", (0.18, 0.02, 0.62, 0.62), "pushin", 5.0),
    ("3_detalle", (0.33, 0.42, 0.34, 0.34), "travelling", 5.0),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagen", required=True)
    ap.add_argument("--ancho", type=int, default=1920)
    ap.add_argument("--alto", type=int, default=1080)
    args = ap.parse_args()

    SALIDA.mkdir(parents=True, exist_ok=True)
    master = Image.open(args.imagen).convert("RGB")
    W, H = master.size
    print(f"máster: {W}×{H}\n")

    recortes = []
    for nombre, (fx, fy, fw, fh), _e, _d in PLANOS:
        # el recorte se ajusta a 16:9 antes de escalar
        w = int(W * fw)
        h = int(w * args.alto / args.ancho)
        if h > H * fh:
            h = int(H * fh)
            w = int(h * args.ancho / args.alto)
        x, y = int(W * fx), int(H * fy)
        x, y = min(x, W - w), min(y, H - h)
        crop = master.crop((x, y, x + w, y + h))
        factor = args.ancho / w
        aviso = "  <-- por debajo de la resolución de salida" if factor > 1.35 else ""
        print(f"  {nombre:11s} recorte {w}×{h}  escala ×{factor:.2f}{aviso}")
        p = SALIDA / f"crop_{nombre}.png"
        crop.resize((args.ancho, args.alto), Image.LANCZOS).save(p)
        recortes.append(p)

    print()
    clips = []
    for (nombre, _c, escena, dur), src in zip(PLANOS, recortes):
        dst = SALIDA / f"PLANO_{nombre}.mp4"
        s = ESCENAS[escena](backend="headless")
        s.ffmpeg.h264(preset="slow", crf=16)
        s.input(image=src)
        s.main(output=dst, time=dur, fps=24,
               width=args.ancho, height=args.alto, ssaa=2.0)
        print(f"  {nombre:11s} {escena:11s} {dur:.0f}s -> {dst.name}")
        clips.append(dst)

    # secuencia montada, para ver si los tres cortan entre sí
    lista = SALIDA / "_concat.txt"
    lista.write_text("".join(f"file '{c.resolve().as_posix()}'\n" for c in clips),
                     encoding="utf-8")
    seq = SALIDA / "SECUENCIA_master.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat",
                    "-safe", "0", "-i", str(lista), "-c", "copy", str(seq)], check=True)
    lista.unlink()
    print(f"\n{seq}  ({seq.stat().st_size/1048576:.1f} MB · "
          f"{sum(d for _n, _c, _e, d in PLANOS):.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
