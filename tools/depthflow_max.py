"""
Escenas de movimiento máximo para DepthFlow: hasta dónde se puede llevar una
imagen fija antes de que se rompa.

No son para producción — el pipeline usa las de depthflow_scenes.py, que son
mucho más contenidas. Esto es para ver el techo de la herramienta.

    .venv-depthflow/Scripts/python.exe tools/depthflow_max.py --imagen RUTA --escena max

Requiere el entorno .venv-depthflow (Python 3.12): moderngl no compila en 3.14.
"""

import argparse
import math
import sys
from pathlib import Path

# El proxy TLS de esta máquina firma con una CA que está en el almacén de Windows
# pero no en el bundle de certifi que usa `requests`. Sin esto, la descarga del
# modelo de profundidad desde HuggingFace falla con SSLCertVerificationError.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from depthflow.scene import DepthScene


def smooth(t):
    return t * t * (3.0 - 2.0 * t)


class MaxMotion(DepthScene):
    """Todo a la vez: órbita completa + empuje continuo + perspectiva que se abre.

    Nota: `inpaint.limit` NO rellena los huecos que deja el desplazamiento, los
    PINTA DE VERDE para que los mandes a una herramienta de inpainting externa.
    Con el parámetro activo el render sale con parches verdes. Queda en cero.
    """

    def update(self):
        t, a = self.tau, self.cycle
        self.state.height = 0.18 + 0.42 * smooth(t)
        self.state.offset = (0.55 * math.sin(a), 0.26 * math.cos(a) - 0.26)
        self.state.isometric = 0.30 + 0.35 * math.sin(a * 0.5)
        self.state.dolly = 0.45 * smooth(t)
        self.state.zoom = 1.0 + 0.10 * smooth(t)
        self.state.focus = 0.30
        self.state.steady = 0.22
        self.state.vignette.intensity = 0.22
        self.state.blur.intensity = 0.30
        self.state.lens.intensity = 0.06


class OrbitaFuerte(DepthScene):
    """Solo órbita, pero amplia. El parallax puro, sin zoom que lo enmascare."""

    def update(self):
        a = self.cycle
        self.state.height = 0.28
        self.state.steady = 0.28
        self.state.focus = 0.32
        self.state.zoom = 1.06
        self.state.isometric = 0.55 * math.cos(a) + 0.70
        self.state.offset = (0.62 * math.sin(a), 0.0)
        self.state.vignette.intensity = 0.18


class DollyFuerte(DepthScene):
    """Dolly zoom marcado: el fondo se comprime mientras el sujeto se mantiene."""

    def update(self):
        t = smooth(self.tau)
        self.state.height = 0.34
        self.state.steady = 0.35
        self.state.focus = 0.35
        self.state.zoom = 1.0 + 0.18 * t
        self.state.isometric = 0.95 * t
        self.state.dolly = 0.8 * t
        self.state.blur.intensity = 0.25
        self.state.vignette.intensity = 0.20


ESCENAS = {"max": MaxMotion, "orbita": OrbitaFuerte, "dolly": DollyFuerte}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagen", required=True)
    ap.add_argument("--escena", default="max", choices=list(ESCENAS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--time", type=float, default=8.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--ancho", type=int, default=1920)
    ap.add_argument("--alto", type=int, default=1080)
    ap.add_argument("--ssaa", type=float, default=2.0)
    args = ap.parse_args()

    salida = Path(args.out or f"output/movimiento-prueba/ANTENA_{args.escena}.mp4")
    salida.parent.mkdir(parents=True, exist_ok=True)

    escena = ESCENAS[args.escena](backend="headless")
    escena.ffmpeg.h264(preset="slow", crf=16)
    escena.input(image=Path(args.imagen))
    escena.main(output=salida, time=args.time, fps=args.fps,
                width=args.ancho, height=args.alto, ssaa=args.ssaa)
    print(f"\n{salida}  ({salida.stat().st_size/1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
