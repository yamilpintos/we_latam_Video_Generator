"""La voz de referencia de un personaje para Ref2VA, sacada de un clip de H3.

La voz tiene que salir de MiniMax y ser la misma en todos los clips de un
personaje. H3 no tiene memoria de voces, pero Ref2VA acepta hasta tres audios de
referencia de timbre. El flujo: se generan con H3 dos o tres tomas de cada
personaje hablando (el casting), se elige la voz, y de ese clip se recorta un
tramo limpio que pasa a ser `<Audio 1>` en todos sus clips.

Lo que exige el nodo y lo que dice la documentación, que este script cumple:
  - 2 a 15 s (límite del modelo; el nodo de ComfyUI no lo valida y deja pasar
    cualquier largo, issue #15667)
  - 32 kHz y estéreo: el nodo remuestrea y duplica el mono, mejor entregarlo listo
  - largo múltiplo exacto de 800 muestras: si no, un recorte centrado del VAE se
    come ~12 ms del principio (issue #15970)
  - el audio de H3 viene clipeado (+2,68 dBFS medido): se baja a -3 dBFS de pico
    para no enseñarle distorsión como si fuera timbre

    python -m h3pipeline.voz_ref <clip.mp4> <inicio_s> <fin_s> <salida.wav>
"""
from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

from . import config

TASA = 32000
BLOQUE = 800          # muestras: 0,025 s a 32 kHz
MINIMO, MAXIMO = 2.0, 15.0


def recortar(origen: Path, ini: float, fin: float, salida: Path) -> float:
    """Recorta, remuestrea, normaliza el pico y ajusta el largo. Devuelve los
    segundos finales."""
    dur = fin - ini
    if not (MINIMO <= dur <= MAXIMO):
        raise ValueError(f"la voz de referencia tiene que durar entre {MINIMO} y {MAXIMO} s "
                         f"(pediste {dur:.2f})")
    salida = Path(salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    crudo = salida.with_suffix(".crudo.wav")
    # A archivo y no por tubería: leer ffmpeg por tubería se cuelga en Windows.
    subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{ini:.3f}", "-t", f"{dur:.3f}", "-i", str(origen),
                    "-vn", "-ac", "2", "-ar", str(TASA),
                    # pico a -3 dBFS sin comprimir: sólo ganancia
                    "-af", "volume=0dB,alimiter=limit=0.708:level=disabled:attack=5:release=50",
                    "-c:a", "pcm_s16le", str(crudo)], check=True)
    with wave.open(str(crudo), "rb") as w:
        canales, ancho, n = w.getnchannels(), w.getsampwidth(), w.getnframes()
        datos = w.readframes(n)
    n_ok = (n // BLOQUE) * BLOQUE
    with wave.open(str(salida), "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(ancho)
        w.setframerate(TASA)
        w.writeframes(datos[:n_ok * canales * ancho])
    crudo.unlink()
    return n_ok / TASA


def main(argv=None):
    a = argv or sys.argv[1:]
    if len(a) != 4:
        print(__doc__)
        return 1
    seg = recortar(Path(a[0]), float(a[1]), float(a[2]), Path(a[3]))
    print(f"{a[3]} · {seg:.3f} s · {TASA} Hz estéreo · múltiplo de {BLOQUE} muestras")
    return 0


if __name__ == "__main__":
    sys.exit(main())
