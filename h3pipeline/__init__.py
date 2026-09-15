"""h3pipeline — de una idea a un video generado con MiniMax H3, en GPU alquilada.

Es un **módulo**, no un programa: no tiene main propio más allá del CLI de
conveniencia (`python -m h3pipeline`). La app llama a estas funciones.

Los dos flujos, que son el mismo pipeline con distinta estructura y formato:

    SHORT  9:16 · 768×1344 · ~60 s · sin voz de H3, voz en off encima
    LARGO  16:9 · 1344×768 · 5-8 min · diálogo dentro del plano + narración

    ┌ estructura ─────────────────────────────────────────────────────────┐
    │  qué tiene que pasar en cada segundo, ANTES de escribir un plano.    │
    │  short: los primeros 3 s son un evento llamativo; de 3 a 6, la       │
    │  promesa; … · largo: apertura fría, planteo, detonante, …            │
    └──────────────────────────┬──────────────────────────────────────────┘
                               │  brief() ── se lo das al director (o a un LLM)
                               ▼
        proyecto.json  (estilo, reparto, locaciones, la lista de planos)
                               │
                               ▼  construir()
        storyboard.json ──► frames.generar_storyboard()  ── nano banana, local
                               │                              GPU apagada
                               ▼  se revisa entero acá
        planos.json ──► empaquetar() ──► ZIP ──► Vast ──► setup.sh, lanzar.sh
                               │                          runner.py (N placas)
                               ▼
                       montaje / runner --montar ──► MP4 + SRT
                               │
        voz.py  densidad y emoción de cada línea ANTES de sintetizar
        tts.py  eleven_v3, varias redacciones, gana la que mejor entra

Uso mínimo desde la app:

    from h3pipeline import Proyecto, empaquetar, vast

    p = Proyecto.cargar("mis-videos/profundidad/proyecto.json")
    print(p.brief())                  # la estructura, para escribir los planos
    p.escribir()                      # storyboard.json + planos.json + brief.md
    frames.generar_storyboard(...)    # los primeros fotogramas
    empaquetar.empaquetar(p)          # el ZIP para subir
    vast.buscar(planos=...)           # dónde correrlo, ordenado por costo total

Las reglas que sostienen todo esto y por qué, en `REGLAS.md`.
"""
from __future__ import annotations

from . import (config, costos, doblaje, empaquetar, estructura, frames, grilla,
               montaje, prompts, proyecto, tts, vast, voz)
from .estructura import Estructura, Tramo
from .grilla import GRILLA, MAXIMO, MINIMO, encajar
from .proyecto import Locacion, Personaje, Proyecto, Voz

__version__ = "1.0"

__all__ = [
    "Proyecto", "Personaje", "Locacion", "Voz",
    "Estructura", "Tramo",
    "encajar", "GRILLA", "MINIMO", "MAXIMO",
    "config", "costos", "doblaje", "empaquetar", "estructura", "frames",
    "grilla", "montaje", "prompts", "proyecto", "tts", "vast", "voz",
]
