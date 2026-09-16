"""Control ANTES de generar video: ¿cada cuadro rehecho sigue siendo la misma toma?

    /c/Python314/python -X utf8 mis-videos/replica-danza/control_cuadros.py [umbral=0.70]

Compara con CLIP (sentence-transformers/clip-ViT-B-32, local) cada cuadro de
assets/ contra el cuadro del original en assets-original/. Un recast legítimo
cambia la cara y conserva la composición: parecido 0,8-1,0. Cuando el generador
alucina otra escena, baja de 0,7 (16/9: T09 0,55 la cara en vez de los pies,
T26 0,62 la cara de Jack en el cerrojo, T78 0,66 y T79 0,61). Los cambios de
cara grandes (Luka con la cara del usuario) dan 0,70-0,80: se listan aparte
para mirarlos, no se rechazan.

Es la regla 70: un cuadro que no muestra lo que el texto describe es un clip
roto seguro, porque H3 fabrica una mezcla para cumplir con los dos.
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
from PIL import Image  # noqa: E402

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import tomas as T  # noqa: E402


def main():
    umbral = float(sys.argv[1]) if len(sys.argv) > 1 else 0.70
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("sentence-transformers/clip-ViT-B-32")
    filas = []
    for t in T.TOMAS:
        k = f"T{t[0]}"
        a, b = AQUI / "assets-original" / f"sb_{k}.png", AQUI / "assets" / f"sb_{k}.png"
        if not (a.exists() and b.exists()):
            continue
        ea, eb = m.encode([Image.open(a).convert("RGB"), Image.open(b).convert("RGB")],
                          normalize_embeddings=True)
        filas.append((float((ea * eb).sum()), k, t[7][:50]))
    filas.sort()
    malos = [f for f in filas if f[0] < umbral]
    dudosos = [f for f in filas if umbral <= f[0] < 0.80]
    print(f"{len(filas)} cuadros · mediana {filas[len(filas) // 2][0]:.3f}")
    print(f"RECHAZAR (< {umbral}): " + (", ".join(f"{k} {s:.2f} «{d}»" for s, k, d in malos) or "-"))
    print("MIRAR (0,70-0,80): " + (", ".join(f"{k} {s:.2f}" for s, k, _d in dudosos) or "-"))
    return 1 if malos else 0


if __name__ == "__main__":
    sys.exit(main())
