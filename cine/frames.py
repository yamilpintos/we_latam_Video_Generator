"""
Extracción de frames con OpenCV — la bisagra entre un clip y el siguiente.

Para qué existe
  Cuando dos clips van encadenados (`continuous_frame`), el segundo tiene que
  arrancar exactamente donde terminó el primero. Eso se hace sacando el último
  fotograma del MP4 anterior y metiéndolo como imagen de primer frame en el nodo
  FL2VA. Si el frame sale corrido aunque sea uno, el corte se nota.

Por qué no es `cap.set(POS_FRAMES, total-1)` y listo
  Dos razones, las dos habituales en MP4 salidos de un modelo de video:

  1. `CAP_PROP_FRAME_COUNT` es una estimación derivada de duración × fps, y con
     fps variable o un contenedor mal cerrado miente por varios frames.
  2. Saltar a un frame arbitrario aterriza en el keyframe anterior y algunos
     decoders devuelven `False` cerca del final del archivo.

  Por eso la estrategia es: saltar a un margen antes del final y **leer hacia
  adelante** quedándose con el último frame que decodificó bien. Si el salto
  falla, se lee el archivo entero de corrido. Es más lento pero nunca miente.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import cv2

# Cuántos frames antes del final estimado empezar a leer. Suficiente para cubrir
# el error típico de FRAME_COUNT sin releer medio clip.
MARGEN = 60


class InfoVideo(NamedTuple):
    frames: int
    fps: float
    ancho: int
    alto: int

    @property
    def duracion(self) -> float:
        return self.frames / self.fps if self.fps else 0.0


def info(video: Path) -> InfoVideo:
    """Metadatos del contenedor. `frames` puede ser estimado — ver el módulo."""
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"OpenCV no pudo abrir {video}")
    try:
        return InfoVideo(
            frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            fps=float(cap.get(cv2.CAP_PROP_FPS)),
            ancho=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            alto=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    finally:
        cap.release()


def ultimo_frame(video: Path, destino: Path) -> Path:
    """Escribe el último fotograma decodificable de `video` en `destino` (PNG).

    Devuelve `destino`. Lanza ValueError si el archivo no abre o no tiene frames.
    """
    video, destino = Path(video), Path(destino)
    if not video.exists():
        raise ValueError(f"No existe el video {video}")

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"OpenCV no pudo abrir {video}")

    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Arranque optimista: saltar cerca del final. Si el contenedor no soporta
        # seek, `set` devuelve False o el read posterior falla, y caemos al plan B.
        if total > MARGEN:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total - MARGEN)

        ultimo = None
        leidos = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            ultimo = frame
            leidos += 1

        # Plan B: el seek dejó el cursor en un lugar del que no se pudo leer nada.
        # Rebobinar y pasar el archivo entero de corrido.
        if ultimo is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                ultimo = frame
                leidos += 1

        if ultimo is None:
            raise ValueError(f"{video.name} no tiene ningún frame decodificable")
    finally:
        cap.release()

    destino.parent.mkdir(parents=True, exist_ok=True)
    # PNG sin pérdida: este frame es la semilla del clip siguiente, comprimirlo
    # con JPEG le mete artefactos que el modelo después propaga.
    if not cv2.imwrite(str(destino), ultimo):
        raise ValueError(f"No pude escribir {destino}")
    return destino


def primer_frame(video: Path, destino: Path) -> Path:
    """El primer fotograma. Útil para contactos y para verificar continuidad."""
    video, destino = Path(video), Path(destino)
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"OpenCV no pudo abrir {video}")
    try:
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"{video.name} no tiene un primer frame legible")
    finally:
        cap.release()

    destino.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(destino), frame):
        raise ValueError(f"No pude escribir {destino}")
    return destino
