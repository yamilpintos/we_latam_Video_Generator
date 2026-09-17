"""La música: una pista compuesta para el video, con ElevenLabs Music.

Es la tercera capa de audio y la última en entrar. El orden importa y no es
arbitrario:

    1. lo que generó H3    viento, estática, metal, pasos. Nace y muere dentro
                           del plano, y es lo que el modelo hace distinto.
    2. la voz              de ElevenLabs, porque cruza el corte.
    3. la música           debajo de todo, y con el ducking más fuerte de los
                           tres: es la que se corre para que se entienda la voz.

La música se pide **por la duración exacta del video** y con un prompt que
describe el papel que cumple, no el género. Un prompt de género ("ambient
drone") devuelve algo genérico; uno que dice qué tiene que hacer la pista
("sostener la tensión sin tapar una voz baja") devuelve algo que sirve.

Ojo con el largo: el endpoint acepta hasta unos minutos por llamada. Para un
video largo se piden cues por movimiento narrativo, no una pista única — así
está resuelto en el doblaje de Aladino, con cinco cues.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from . import config

API = "https://api.elevenlabs.io/v1/music"

# Cómo se le pide a cada formato. La diferencia es real: en un short la música
# entra desde el segundo cero y no tiene tiempo de desarrollarse; en un largo
# puede tener movimientos.
PROMPT_BASE = (
    "Instrumental score for a {dur:.0f}-second {formato}. {tono} "
    "It must sit UNDER a low, close male narration without ever competing with "
    "it: no melody in the vocal range, no sudden peaks, nothing that pulls "
    "attention. Sparse, patient, mostly texture. No drums that mark a beat, no "
    "vocals, no lyrics, no risers, no stingers, no cinematic braams. "
    "Start almost from silence and grow only slightly toward the end."
)


class ErrorMusica(RuntimeError):
    pass


def componer(duracion_s: float, tono: str, formato: str = "vertical short film",
             clave: str | None = None, prompt: str | None = None,
             instrumental: bool | None = None) -> bytes:
    """Devuelve los bytes del MP3 de una pista de `duracion_s` segundos.
    `instrumental=True` fuerza sin voz (force_instrumental de la API); None deja
    que el modelo decida según el prompt (así una letra en el prompt se canta)."""
    config.certificados()
    k = clave or config.leer_env("ELEVENLABS_API_KEY", obligatorio=False) \
        or config.leer_env("elevenlabs")
    texto = prompt or PROMPT_BASE.format(dur=duracion_s, formato=formato, tono=tono)
    pedido = {"prompt": texto, "music_length_ms": int(round(duracion_s * 1000))}
    if instrumental is not None:
        pedido["force_instrumental"] = bool(instrumental)
    cuerpo = json.dumps(pedido).encode()
    req = urllib.request.Request(API, data=cuerpo,
                                 headers={"xi-api-key": k, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise ErrorMusica(f"ElevenLabs Music HTTP {e.code}: "
                          f"{e.read().decode('utf-8', 'replace')[:300]}") from e


def para_proyecto(proyecto, duracion_s: float, destino: Path, tono: str | None = None,
                  force: bool = False, log=print) -> Path:
    """Compone la pista del proyecto y la cachea. Si ya existe, no vuelve a pagar."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and not force:
        log(f"  = la música ya está en {destino.name}")
        return destino
    formato = ("vertical short film" if proyecto.formato == "short"
               else "long-form narrative film")
    log(f"  · componiendo {duracion_s:.0f} s de música…")
    destino.write_bytes(componer(duracion_s, tono or "", formato))
    log(f"    {destino.stat().st_size / 1024:.0f} KB en {destino.name}")
    return destino
