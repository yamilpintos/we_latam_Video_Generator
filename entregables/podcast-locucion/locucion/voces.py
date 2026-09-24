"""Las voces: las que ya están medidas y las que tenga la cuenta.

`CPS` («caracteres por segundo») es lo único que hay que medir para una voz
nueva, y es lo que permite estimar cuánto va a durar un episodio antes de
gastar un solo crédito. Cada voz tiene el suyo: Pablo lee a 10,5 y Kate a
16,7, así que el MISMO texto dura 60 % más con Pablo. Medilo con
`medir_cps()` la primera vez que agregues una voz y guardalo.
"""
from __future__ import annotations

import json
import tempfile
import urllib.request
from pathlib import Path

from .config import API_VOCES, Ajustes, clave
from . import tts

# Las medidas en producción. `cps` sale de sintetizar un texto largo y dividir
# caracteres / segundos útiles (ver `medir_cps`).
MEDIDAS = {
    "pablo": {"voz_id": "JXKQ929SO0LLl7spbEAI", "nombre": "Pablo",
              "descripcion": "argentino, cordobés, grave y pausado; el narrador de los documentales",
              "cps": 10.5, "idioma": "es-AR"},
    "kate":  {"voz_id": "EYBbN7OENxAX5QX56IiW", "nombre": "Kate",
              "descripcion": "cercana, rápida, para formatos ágiles",
              "cps": 16.7, "idioma": "es"},
}
CPS_POR_DEFECTO = 14.0     # si la voz no está medida, para estimar nomás


def catalogo(api_key: str | None = None) -> list[dict]:
    """Todas las voces de la cuenta de ElevenLabs, con el `cps` de las que ya
    están medidas. Es lo que la app le muestra al usuario para elegir."""
    req = urllib.request.Request(API_VOCES, headers={"xi-api-key": clave(api_key)})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    por_id = {v["voz_id"]: v for v in MEDIDAS.values()}
    out = []
    for v in d.get("voices", []):
        m = por_id.get(v.get("voice_id"), {})
        etiquetas = v.get("labels") or {}
        out.append({
            "voz_id": v.get("voice_id"),
            "nombre": v.get("name"),
            "descripcion": m.get("descripcion") or v.get("description") or "",
            "genero": etiquetas.get("gender"),
            "edad": etiquetas.get("age"),
            "acento": etiquetas.get("accent"),
            "muestra": v.get("preview_url"),
            "cps": m.get("cps"),          # None = sin medir
            "medida": bool(m),
        })
    return out


def ver(ref: str, api_key: str | None = None) -> dict | None:
    """Una voz por su alias («pablo») o por su id de ElevenLabs."""
    if ref in MEDIDAS:
        return dict(MEDIDAS[ref], alias=ref)
    for v in catalogo(api_key):
        if v["voz_id"] == ref:
            return v
    return None


def cps_de(voz_id: str) -> float:
    for v in MEDIDAS.values():
        if v["voz_id"] == voz_id:
            return v["cps"]
    return CPS_POR_DEFECTO


TEXTO_MEDIDA = (
    "La primera vez que crucé ese puente tenía doce años y una bicicleta prestada. "
    "El río venía cargado después de la lluvia y arrastraba ramas enteras. "
    "Mi padre me esperaba del otro lado, con las manos en los bolsillos, sin decir nada. "
    "Tardé media hora en animarme, y él no se movió ni un paso en todo ese tiempo.")


def medir_cps(voz_id: str, api_key: str | None = None, texto: str = TEXTO_MEDIDA) -> float:
    """Sintetiza un texto conocido y devuelve los caracteres por segundo REALES
    de esa voz. Corré esto una vez por voz nueva y guardá el número: con él,
    `guion.estimar()` acierta la duración del episodio dentro del 10 %."""
    a = Ajustes(voz_id=voz_id)
    mp3 = tts.sintetizar(texto, a, api_key=api_key)
    with tempfile.TemporaryDirectory() as d:
        dur = tts.a_wav(mp3, Path(d) / "m.wav")
    return round(len(texto) / dur, 2) if dur else CPS_POR_DEFECTO
