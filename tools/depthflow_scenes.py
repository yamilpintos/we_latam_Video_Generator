"""
Movimiento de los planos de imagen animada. Tres decisiones, no nueve técnicas.

EL CRITERIO
===========
La cámara se mueve en la dirección en la que va la atención del espectador.

  ACERCAR  el plano CONCENTRA. Hay una cosa que mirar y la cámara va hacia ella.
  ALEJAR   el plano AMPLÍA. Importa el contexto, la escala o lo que implica.
  QUIETO   el peso está en otro lado —la voz, un dato— y moverse distraería.

Cómo decidir, leyendo el prompt con el que se generó la imagen:

  → ACERCAR si el prompt dice: plano detalle, inserto, primer plano, primerísimo,
    macro, "un documento", "una pieza", "el rostro de". También cuando el plano
    presenta por primera vez un objeto que la historia va a usar.

  → ALEJAR si el prompt dice: plano general, establishing, vista orbital, cenital,
    "la sala entera", "el paisaje". También en cierres de secuencia, y cuando el
    sujeto tiene que verse pequeño: soledad, abandono, escala.

  → QUIETO si el plano es una placa contemplativa, si el sujeto ya tiene movimiento
    propio (una impresora imprimiendo, datos corriendo) o si la frase que suena
    encima es la más importante del bloque.

Y una regla de montaje que está por encima del criterio: NO REPETIR EL SENTIDO EN
PLANOS CONSECUTIVOS. Dos acercamientos seguidos y el video respira en una sola
dirección. `depthflow_batch.py --dry-run` lo verifica y falla si pasa.

CÓMO SE REPARTE EL MOVIMIENTO
=============================
Medido sobre imágenes reales:

  zoom    campo de visión     NO desgarra. OJO: va al revés, 0.75 acerca y 1.30 aleja.
  center  paneo plano         NO desgarra.
  height  empuje en profundidad   SÍ desgarra: estira el plano más cercano.
  offset  paralaje lateral        SÍ desgarra, y es el más visible.

La magnitud la lleva `zoom`. `height` entra en dosis mínima y es lo que diferencia
esto de escalar la imagen en el editor: el primer plano se abre más rápido que el
fondo. `steady` alto protege lo cercano.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["depthflow"]
# ///

import math
import sys

from attrs import define
from depthflow.scene import DepthScene

INTENSIDAD = 0.45   # calibrado a ojo sobre la antena de la DSN. No subirlo sin mirar.
ISO = 0.45          # proyección fija: moverla convierte la cámara en plataforma giratoria


def smooth(t):
    return t * t * (3.0 - 2.0 * t)


def flotacion(seg, amp=0.006):
    """Deriva mínima para que no se lea como un zoom digital sobre una foto."""
    return (amp * math.sin(seg * 1.7) + 0.55 * amp * math.sin(seg * 0.83),
            0.70 * amp * math.sin(seg * 1.31 + 1.1) + 0.45 * amp * math.sin(seg * 2.17))


@define
class Acercar(DepthScene):
    """El plano concentra: hay algo que mirar."""

    def update(self):
        t, k = smooth(self.tau), INTENSIDAD
        fx, fy = flotacion(self.time)
        self.state.isometric = ISO
        self.state.steady = 0.40
        self.state.focus = 0.32
        self.state.zoom = 1.0 - 0.30 * k * t
        self.state.height = 0.16 + 0.22 * k * t
        self.state.offset = (fx, fy)
        self.state.blur.intensity = 0.12 + 0.14 * t
        self.state.vignette.intensity = 0.16 + 0.06 * t


@define
class Alejar(DepthScene):
    """El plano amplía: importa el contexto o la escala."""

    def update(self):
        t, k = smooth(self.tau), INTENSIDAD
        fx, fy = flotacion(self.time)
        self.state.isometric = ISO
        self.state.steady = 0.40
        self.state.focus = 0.32
        self.state.zoom = (1.0 - 0.30 * k) + 0.30 * k * t
        self.state.height = (0.16 + 0.22 * k) - 0.22 * k * t
        self.state.offset = (fx, fy)
        self.state.blur.intensity = 0.26 - 0.14 * t
        self.state.vignette.intensity = 0.22 - 0.06 * t


@define
class Quieto(DepthScene):
    """El peso está en la voz o el sujeto ya se mueve solo. Solo respira."""

    def update(self):
        t, k = smooth(self.tau), INTENSIDAD
        fx, fy = flotacion(self.time, 0.009)
        self.state.isometric = ISO
        self.state.steady = 0.42
        self.state.focus = 0.32
        self.state.zoom = 1.0 - 0.05 * k * t
        self.state.height = 0.18 + 0.04 * k * t
        self.state.offset = (fx, fy)
        self.state.blur.intensity = 0.18
        self.state.vignette.intensity = 0.18


SCENES = {"acercar": Acercar, "alejar": Alejar, "quieto": Quieto}

# Movimientos especiales (grúa, travelling, retirada amplia) viven en
# depthflow_cine.py. No entran en el reparto por defecto: son excepciones que se
# eligen a mano cuando un plano concreto las justifica.
