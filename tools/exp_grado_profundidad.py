"""
EXPERIMENTO B · Graduar el color por distancia usando el mapa de profundidad.

La atmósfera real hace tres cosas con lo que está lejos: le baja el contraste,
lo dessatura y lo enfría. Se llama perspectiva aérea y es la señal de profundidad
más fuerte que tiene el ojo, más que el paralaje.

Una imagen generada por IA suele venir con esto mal resuelto: el fondo tiene el
mismo contraste y la misma temperatura que el primer plano, y por eso al animarla
se ven "capas de cartón deslizándose" en vez de espacio.

Como DepthFlow ya calcula un mapa de profundidad, sale gratis: se aplica el grado
sobre la imagen ANTES de animarla, así queda alineado por construcción.

    .venv-depthflow/Scripts/python.exe tools/exp_grado_profundidad.py --imagen RUTA
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from depthflow.estimators.anything import DepthAnythingV2

SALIDA = Path("output/experimentos")

# CALIBRACIÓN. La primera pasada aplicó el grado a todo lo que el mapa marcaba
# como "no cercano", y eso incluye al sujeto: la antena perdió el dorado y la
# lámpara de sodio se volvió blanca. Dos correcciones:
#
#   1. El grado entra SOLO en el fondo real (profundidad < UMBRAL), no en todo lo
#      que no sea primer plano.
#   2. Las luces quedan protegidas. Una fuente de luz no se enfría con la
#      distancia: se atenúa. Enfriarla es el error que delata el truco.
#
# Y una advertencia de fondo: la perspectiva aérea es un fenómeno DIURNO. De noche
# no hay dispersión que valga (por eso se ven las estrellas). Los valores acá son
# una décima parte de lo que usarías en un paisaje de día.
UMBRAL = 0.22        # por debajo de esto se considera fondo
SUAVE = 0.14         # ancho de la transición
NIEBLA = 0.09
DESATURA = 0.22
FRIO = np.array([0.80, 0.88, 1.00], dtype=np.float32)
CALIDO = np.array([1.0, 1.0, 1.0], dtype=np.float32)
CONTRASTE_LEJOS = 0.88
LUZ = 0.30           # brillo a partir del cual el píxel se protege


def grado(rgb: np.ndarray, prof: np.ndarray) -> np.ndarray:
    """rgb en 0-1, prof en 0-1 donde 1 = cerca."""
    # solo el fondo real, con transición suave
    m = np.clip((UMBRAL + SUAVE - prof) / (2 * SUAVE), 0.0, 1.0)
    m = m * m * (3.0 - 2.0 * m)
    # y las luces no se tocan
    luma = rgb.max(axis=2)
    m = m * (1.0 - np.clip((luma - LUZ) / (1.0 - LUZ), 0.0, 1.0))
    lejos = m[..., None]
    cerca = 1.0 - lejos

    gris = rgb.mean(axis=2, keepdims=True)
    out = rgb + (gris - rgb) * (DESATURA * lejos)               # desatura el fondo
    media = out.mean()
    out = media + (out - media) * (1.0 - (1.0 - CONTRASTE_LEJOS) * lejos)
    out = out * (FRIO * lejos + CALIDO * cerca)                 # temperatura por distancia

    bruma = np.array([0.16, 0.19, 0.26], dtype=np.float32)
    out = out * (1.0 - NIEBLA * lejos) + bruma * (NIEBLA * lejos)
    return np.clip(out, 0.0, 1.0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--imagen", required=True)
    args = ap.parse_args()
    SALIDA.mkdir(parents=True, exist_ok=True)

    im = Image.open(args.imagen).convert("RGB")
    rgb = np.asarray(im, dtype=np.float32) / 255.0

    d = np.asarray(DepthAnythingV2().estimate(np.asarray(im)), dtype=np.float32)
    if d.ndim == 3:
        d = d[..., 0]
    d = (d - d.min()) / (d.max() - d.min() + 1e-9)
    d = np.asarray(Image.fromarray((d * 255).astype("uint8"))
                   .resize(im.size, Image.BILINEAR), dtype=np.float32) / 255.0

    Image.fromarray((d * 255).astype("uint8")).save(SALIDA / "depth_mapa.png")
    out = grado(rgb, d)
    Image.fromarray((out * 255).astype("uint8")).save(SALIDA / "grado_con.png")
    im.save(SALIDA / "grado_sin.png")

    lejos, cerca = d < 0.25, d > 0.60
    def stats(x, m):
        z = x[m]
        sat = (z.max(axis=1) - z.min(axis=1)).mean()
        return z.mean(), sat, z.std()
    for etiqueta, m in [("fondo", lejos), ("primer plano", cerca)]:
        a = stats(rgb, m); b = stats(out, m)
        print(f"  {etiqueta:13s} brillo {a[0]:.3f}->{b[0]:.3f}  "
              f"saturación {a[1]:.3f}->{b[1]:.3f}  contraste {a[2]:.3f}->{b[2]:.3f}")
    print(f"\n  {SALIDA/'grado_con.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
