"""Sintetizar una línea con ElevenLabs y dejarla limpia de silencios de borde.

Dos trampas de `eleven_v3`, las dos cubiertas acá:

1. Rechaza con **400** un texto que sea sólo una etiqueta. `[sighs]` solo no
   es sintetizable: necesita al menos una vocalización.
2. Mete hasta **200 ms de silencio** al principio de cada clip, y a veces una
   cola al final. Si no se recortan, las pausas que arma `guion.py` dejan de
   valer y el episodio suena arrastrado.

Todo se cachea por hash del texto + la voz + los ajustes: cambiar una frase
invalida sólo esa frase y no se vuelve a pagar por el resto del episodio.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from .config import API_TTS, FORMATOS, SR, UMBRAL_SILENCIO_DB, Ajustes, clave

RE_TAG = re.compile(r"\[([a-zA-Z_ ]+)\]")


class ErrorTTS(RuntimeError):
    pass


def sin_tags(texto: str) -> str:
    return RE_TAG.sub("", texto).strip()


def _hash(texto: str, a: Ajustes) -> str:
    firma = json.dumps([texto, a.voz_id, a.modelo, a.voice_settings()], sort_keys=True)
    return hashlib.sha1(firma.encode()).hexdigest()[:16]


def sintetizar(texto: str, a: Ajustes, cache: Path | None = None,
               api_key: str | None = None) -> bytes:
    """Los bytes del MP3 de una línea. Con `cache`, guarda y reusa por hash."""
    if not sin_tags(texto):
        raise ErrorTTS(f"texto sólo con etiqueta ({texto!r}): v3 lo rechaza con 400")
    guardado = (cache / f"{_hash(texto, a)}.mp3") if cache else None
    if guardado and guardado.exists():
        return guardado.read_bytes()

    cuerpo = json.dumps({"text": texto, "model_id": a.modelo,
                         "voice_settings": a.voice_settings()}).encode()
    k = clave(api_key)
    ultimo = None
    for formato in FORMATOS:
        req = urllib.request.Request(
            f"{API_TTS}/{a.voz_id}?output_format={formato}", data=cuerpo,
            headers={"xi-api-key": k, "Content-Type": "application/json"})
        try:
            datos = urllib.request.urlopen(req, timeout=180).read()
            break
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:300]
            ultimo = f"HTTP {e.code}: {detalle}"
            if e.code == 403 and "output_format" in detalle:
                continue          # el plan no llega a 192 kbps: se prueba 128
            raise ErrorTTS(ultimo) from e
    else:
        raise ErrorTTS(ultimo or "ElevenLabs no devolvió audio")

    if guardado:
        guardado.parent.mkdir(parents=True, exist_ok=True)
        guardado.write_bytes(datos)
    return datos


def a_wav(mp3: bytes, destino: Path, recortar: bool = True) -> float:
    """Pasa el MP3 a WAV 48 kHz mono y le saca los silencios de los bordes.
    Devuelve la duración útil en segundos, que es la que dura al sonar."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    crudo = destino.with_suffix(".crudo.mp3")
    crudo.write_bytes(mp3)
    filtros = [f"aresample={SR}"]
    if recortar:
        # `silenceremove` en los dos extremos: quita el arranque tardío de v3 y
        # la cola, sin tocar las pausas de adentro de la frase.
        filtros.append(
            f"silenceremove=start_periods=1:start_threshold={UMBRAL_SILENCIO_DB}dB:"
            f"start_silence=0.02:detection=peak,areverse,"
            f"silenceremove=start_periods=1:start_threshold={UMBRAL_SILENCIO_DB}dB:"
            f"start_silence=0.02:detection=peak,areverse")
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(crudo),
                        "-af", ",".join(filtros), "-ac", "1", "-ar", str(SR),
                        "-c:a", "pcm_s16le", str(destino)], capture_output=True, text=True)
    crudo.unlink(missing_ok=True)
    if r.returncode:
        raise ErrorTTS("ffmpeg: " + (r.stderr or "")[-400:])
    return duracion(destino)


def duracion(archivo: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(archivo)],
                       capture_output=True, text=True)
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0
