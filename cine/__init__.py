"""Orquestador de cortometrajes: LLM → MiniMax H3 → FFmpeg → Ableton.

Fases y dónde vive cada una:

    1  preproducción      guion.py    valida el JSON del LLM y los assets madre
    2  render             render.py   bucle contra ComfyUI, Ref2VA / FL2VA
    3  postproducción     —           pendiente: FFmpeg, SRT, hoja de sonido
    4  alineación         —           pendiente: whisper-timestamped
    5  puente Ableton     —           pendiente: python-osc

Piezas de apoyo: comfy.py (API de ComfyUI), frames.py (OpenCV).
"""

from . import comfy, frames, guion  # noqa: F401

__all__ = ["comfy", "frames", "guion", "render"]
