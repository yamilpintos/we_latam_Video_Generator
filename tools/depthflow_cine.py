"""
Cuatro movimientos de cámara cinematográficos para DepthFlow.

Qué los diferencia de las escenas "de exhibición":

1. `isometric` casi FIJO. Barrerlo de 0,15 a 1,25 cambia la proyección durante el
   plano y el resultado se lee como una plataforma giratoria de producto, no como
   una cámara. Es lo que hacía raro el preset de órbita.

2. UNIDIRECCIONALES. Nada de sin(cycle): el movimiento arranca en un extremo y
   termina en el otro. Un plano que vuelve al punto de partida se siente indeciso
   y el corte pierde dirección.

3. Con FLOTACIÓN. Una deriva mínima de baja frecuencia sobre el movimiento
   principal. Es la diferencia entre una cámara y un riel motorizado: nadie sostiene
   un encuadre perfectamente quieto.

4. Con la PROFUNDIDAD DE CAMPO trabajando. El desenfoque cambia durante el plano,
   igual que en una toma real donde el foco sigue al sujeto.

    .venv-depthflow/Scripts/python.exe tools/depthflow_cine.py --imagen RUTA --escena pushin

Requiere el entorno .venv-depthflow (Python 3.12).
"""

import argparse
import math
from pathlib import Path

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from depthflow.scene import DepthScene

ISO = 0.45   # proyección de referencia. Se mueve poco y a propósito.

# Multiplicador global de amplitud.
INTENSIDAD = 1.0

# CÓMO SE REPARTE EL MOVIMIENTO
#
# Medido sobre esta imagen, los cuatro parámetros no se comportan igual:
#
#   zoom    campo de visión     NO desgarra nunca. OJO: va AL REVÉS — 0.75 acerca,
#                               1.30 aleja. Es el FOV, no la escala del sujeto.
#                               Acercar cuesta nitidez si la fuente es chica.
#   center  paneo plano         NO desgarra nunca.
#   height  empuje en profundidad   SÍ desgarra: el plano más cercano se estira.
#   offset  paralaje lateral        SÍ desgarra, y es el más visible (chorros horizontales).
#
# Por eso la magnitud del movimiento la llevan zoom y center, y height/offset se
# usan en dosis moderada, que es de donde sale la sensación de profundidad real.
# Subir height/offset para "que se note más" es lo que rompe el primer plano.
#
# `steady` alto protege al plano cercano: mueve hacia la cámara el plano que
# queda fijo, así lo que está adelante se desplaza menos.


def smooth(t):
    """Arranca y frena. El movimiento lineal se lee como barato."""
    return t * t * (3.0 - 2.0 * t)


def ease_out(t):
    """Arranca decidido y se asienta. Para revelaciones."""
    return 1.0 - (1.0 - t) ** 2.5


def ease_in(t):
    """Entra despacio y gana. Para tensión."""
    return t ** 1.8


def flotacion(seg, amp=0.011):
    """Deriva orgánica: senoidales de frecuencias no múltiplas, amplitud mínima."""
    return (amp * math.sin(seg * 1.7) + 0.55 * amp * math.sin(seg * 0.83),
            0.70 * amp * math.sin(seg * 1.31 + 1.1) + 0.45 * amp * math.sin(seg * 2.17))


class PushIn(DepthScene):
    """1 · Acercamiento lento. El plano de documental por defecto: la cámara entra
    en la escena mientras el foco se cierra sobre el sujeto."""

    def update(self):
        t, k = smooth(self.tau), INTENSIDAD
        fx, fy = flotacion(self.time)
        self.state.isometric = ISO
        self.state.focus = 0.30
        self.state.steady = 0.38
        self.state.zoom = 1.02 - 0.30 * k * t
        self.state.center = (0.10 * k * t, -0.05 * k * t)
        self.state.height = 0.12 + 0.36 * k * t
        self.state.offset = (0.05 * k * t + fx, -0.03 * k * t + fy)
        self.state.blur.intensity = 0.14 + 0.30 * t
        self.state.vignette.intensity = 0.18 + 0.10 * t


class Grua(DepthScene):
    """2 · Grúa ascendente. La cámara sube y el sujeto gana altura sobre el
    encuadre. Es el movimiento que da escala."""

    def update(self):
        t, k = ease_out(self.tau), INTENSIDAD
        fx, fy = flotacion(self.time, 0.008)
        self.state.isometric = ISO + 0.14 * t
        self.state.focus = 0.33
        self.state.steady = 0.34
        self.state.zoom = 1.00 - 0.16 * k * t
        self.state.center = (0.0, 0.34 * k * t)
        self.state.height = 0.18 + 0.18 * k * t
        self.state.offset = (fx, -0.30 * k * t + fy)
        self.state.blur.intensity = 0.22
        self.state.vignette.intensity = 0.20


class Travelling(DepthScene):
    """3 · Travelling lateral. La cámara se desplaza en paralelo y el primer plano
    barre por delante del sujeto. El paralaje puro, pero con dirección."""

    def update(self):
        t, k = smooth(self.tau), INTENSIDAD
        fx, fy = flotacion(self.time, 0.009)
        self.state.isometric = ISO
        self.state.focus = 0.36
        self.state.steady = 0.36
        self.state.zoom = 0.88
        self.state.center = (k * (-0.34 + 0.68 * t), 0.0)
        self.state.height = 0.26
        self.state.offset = (k * (-0.22 + 0.44 * t) + fx, fy)
        self.state.blur.intensity = 0.26
        self.state.vignette.intensity = 0.20


class Retirada(DepthScene):
    """4 · Retroceso. La cámara se aleja y el sujeto se hunde en el paisaje.
    Cierra secuencia y deja sensación de soledad."""

    def update(self):
        t, k = ease_out(self.tau), INTENSIDAD
        fx, fy = flotacion(self.time, 0.010)
        self.state.isometric = ISO - 0.07 * t
        self.state.focus = 0.30
        self.state.steady = 0.34
        self.state.zoom = 1.06 - 0.34 * k * (1.0 - t)
        self.state.center = (0.12 * k * (1.0 - t), 0.06 * k * t)
        self.state.height = 0.14 + 0.34 * k * (1.0 - t)
        self.state.offset = (-0.06 * k * (1.0 - t) + fx, -0.05 * k * t + fy)
        self.state.blur.intensity = 0.38 - 0.22 * t
        self.state.vignette.intensity = 0.26 - 0.08 * t


class Acercar(DepthScene):
    """5 · Acercamiento puro. Un solo eje: la cámara entra y nada más.

    Sin desplazamiento lateral ni vertical, sin cambio de perspectiva. Solo el
    encuadre que se cierra, con la pizca justa de paralaje para que no se lea como
    un zoom digital sobre una foto plana.

    Es el movimiento por defecto de un documental: no se nota, se siente.
    """

    def update(self):
        t, k = smooth(self.tau), INTENSIDAD
        fx, fy = flotacion(self.time, 0.006)
        self.state.isometric = ISO
        self.state.steady = 0.40
        self.state.focus = 0.32
        self.state.zoom = 1.0 - 0.30 * k * t       # 0.70 = acercamiento máximo
        self.state.height = 0.16 + 0.22 * k * t    # el paralaje, en dosis mínima
        self.state.offset = (fx, fy)               # solo la flotación
        self.state.center = (0.0, 0.0)
        self.state.blur.intensity = 0.12 + 0.14 * t
        self.state.vignette.intensity = 0.16 + 0.06 * t


ESCENAS = {"pushin": PushIn, "grua": Grua,
           "travelling": Travelling, "retirada": Retirada,
           "acercar": Acercar}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagen", required=True)
    ap.add_argument("--escena", default="pushin", choices=list(ESCENAS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--time", type=float, default=8.0)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--ancho", type=int, default=1920)
    ap.add_argument("--alto", type=int, default=1080)
    ap.add_argument("--ssaa", type=float, default=2.0)
    ap.add_argument("--intensidad", type=float, default=1.0,
                    help="multiplicador de amplitud. 1.4 empieza a estirar los bordes")
    args = ap.parse_args()

    global INTENSIDAD
    INTENSIDAD = args.intensidad

    salida = Path(args.out or f"output/movimiento-prueba/CINE_{args.escena}.mp4")
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
