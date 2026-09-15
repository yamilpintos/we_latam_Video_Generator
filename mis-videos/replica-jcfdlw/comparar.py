# -*- coding: utf-8 -*-
"""El lado a lado: original a la izquierda, réplica a la derecha.

Es para lo que existe todo esto. La réplica no se publica; se mira contra el
original y se saca una conclusión. Dos salidas:

  COMPARACION.mp4    los dos videos sincronizados en la misma pantalla, con el
                     audio del nuestro (el de ellos ya lo conocemos)
  COMPARACION-*.jpg  hojas de contacto pareadas: la misma toma de los dos,
                     una arriba de la otra, para comparar encuadre por encuadre

Los dos duran 181,40 s y arrancan en el mismo cuadro, así que no hace falta
alinear nada: el timing de la réplica se construyó contra el del original.

El original es 1080x1440 dentro de 1080x1920 (barras negras); la réplica es
768x1344 a sangre. Para el lado a lado se lleva a los dos a la misma altura y
se acepta que uno sea más angosto: deformarlos para que coincidan sería
mentirle al ojo justo en lo que se está comparando.

    python mis-videos/replica-jcfdlw/comparar.py
"""
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI / "../.."))
from h3pipeline import config, montaje                       # noqa: E402

# El limpio de 1080x1920: el .full es 576x1024 y el recorte 1080:1440 no le
# entra. El audio del original no hace falta: se conoce, y el lado a lado
# lleva el nuestro.
ORIGINAL = AQUI / "../../referencias/jcfdlw/7678030150944001310.mp4"
REPLICA = AQUI / "REPLICA - final.mp4"
ALTO = 960          # alto común del lado a lado


def _ff(*args):
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", *args],
                   check=True)


def video():
    salida = AQUI / "COMPARACION.mp4"
    _ff("-i", str(ORIGINAL), "-i", str(REPLICA),
        "-filter_complex",
        # el original recortado a su cuadro real, para no comparar contra barras negras
        f"[0:v]crop=1080:1440:0:240,scale=-2:{ALTO}[a];"
        f"[1:v]scale=-2:{ALTO}[b];"
        f"[a][b]hstack=2,pad=ceil(iw/2)*2:ceil(ih/2)*2[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", str(salida))
    print(f"COMPARACION.mp4   {salida.stat().st_size/1e6:.1f} MB")
    return salida


def hojas(por_hoja=6):
    """Una fila por toma: original arriba, réplica abajo, en el mismo segundo."""
    import json
    planos = json.loads((AQUI / "planos.json").read_text(encoding="utf-8"))["planos"]
    tmp = AQUI / "cmp"
    tmp.mkdir(exist_ok=True)
    for viejo in tmp.glob("*.png"):
        viejo.unlink()
    i = 0
    for p in planos:
        a, b = p["en_linea_de_tiempo"]
        t = (a + b) / 2
        i += 1
        _ff("-ss", f"{t:.2f}", "-i", str(ORIGINAL), "-frames:v", "1",
            "-vf", "crop=1080:1440:0:240,scale=240:420:force_original_aspect_ratio=decrease,"
                   "pad=240:420:(ow-iw)/2:(oh-ih)/2:color=black", str(tmp / f"{i:04d}.png"))
        i += 1
        _ff("-ss", f"{t:.2f}", "-i", str(REPLICA), "-frames:v", "1",
            "-vf", "scale=240:420", str(tmp / f"{i:04d}.png"))
    _ff("-framerate", "1", "-i", str(tmp / "%04d.png"),
        "-vf", f"tile=2x{por_hoja}:padding=4:color=white", "-q:v", "3",
        str(AQUI / "COMPARACION-%02d.jpg"))
    n = len(list(AQUI.glob("COMPARACION-*.jpg")))
    print(f"{i//2} pares en {n} hojas · columna izquierda ELLOS, derecha NOSOTROS")


def main():
    for f in (ORIGINAL, REPLICA):
        if not Path(f).exists():
            raise SystemExit(f"!! falta {f}")
    d1, d2 = montaje.duracion(ORIGINAL), montaje.duracion(REPLICA)
    print(f"original {d1:.2f} s · réplica {d2:.2f} s · diferencia {d2-d1:+.2f} s")
    video()
    hojas()


if __name__ == "__main__":
    main()
