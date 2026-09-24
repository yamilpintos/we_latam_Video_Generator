"""Locución para podcast: de un texto a un episodio masterizado.

    from locucion import narrar, Ajustes

    ep = narrar(texto, Ajustes(voz_id="JXKQ929SO0LLl7spbEAI"),
                salida=Path("episodio.mp3"))
    print(ep.total, "segundos")
    Path("episodio.srt").write_text(ep.srt(), encoding="utf-8")

El pipeline completo, en orden:

    texto  →  guion.partir()      parte en oraciones y párrafos
           →  tts.sintetizar()    una llamada por oración (con caché)
           →  tts.a_wav()         recorta el silencio que mete el modelo
           →  guion.anclar()      calcula el segundo de cada línea
           →  audio.pegar()       arma el episodio con los silencios exactos
           →  audio.masterizar()  mezcla la música y lleva todo a -14 LUFS
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from . import audio, guion, tts, voces
from .config import TAGS, Ajustes
from .guion import Episodio, Linea

__all__ = ["narrar", "Ajustes", "Episodio", "Linea", "TAGS",
           "audio", "guion", "tts", "voces"]


def narrar(texto: str, ajustes: Ajustes, salida: Path, *, musica: Path | None = None,
           cache: Path | None = None, api_key: str | None = None,
           progreso=None) -> Episodio:
    """Texto → episodio masterizado en `salida`. Devuelve el `Episodio` con la
    línea de tiempo real (para subtítulos, capítulos o transcripción).

    `progreso(i, total, texto)` se llama antes de sintetizar cada línea.
    """
    lineas = guion.partir(texto)
    if not lineas:
        raise ValueError("el texto está vacío")
    tmp = Path(tempfile.mkdtemp(prefix="locucion_"))
    try:
        wavs: list[Path] = []
        for i, l in enumerate(lineas):
            if progreso:
                progreso(i + 1, len(lineas), l.texto)
            mp3 = tts.sintetizar(l.texto, ajustes, cache=cache, api_key=api_key)
            w = tmp / f"l_{i:04d}.wav"
            l.dur = tts.a_wav(mp3, w)
            wavs.append(w)

        ep = guion.anclar(lineas, ajustes.pausa_oracion, ajustes.pausa_parrafo, ajustes.arranque)
        con_pausas = []
        for i, (l, w) in enumerate(zip(lineas, wavs)):
            if i + 1 < len(lineas):
                cambia = lineas[i + 1].parrafo != l.parrafo
                con_pausas.append((w, ajustes.pausa_parrafo if cambia else ajustes.pausa_oracion))
            else:
                con_pausas.append((w, 0.0))
        crudo = audio.pegar(con_pausas, ajustes.arranque, tmp / "voz.wav", tmp / "partes")
        if ajustes.masterizar or musica:
            audio.masterizar(crudo, salida, musica=musica)
        else:
            shutil.copy(crudo, salida)
        return ep
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
