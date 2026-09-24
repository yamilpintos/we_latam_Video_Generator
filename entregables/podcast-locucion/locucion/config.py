"""Toda la configuración medida, en un solo lugar.

Los valores de este archivo NO son preferencias: cada uno se midió produciendo
video con locución y corrigiendo lo que sonaba mal. Cambiarlos se puede, pero
conviene saber qué se rompe. El porqué de cada uno está al lado.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────── ElevenLabs

API_TTS = "https://api.elevenlabs.io/v1/text-to-speech"
API_VOCES = "https://api.elevenlabs.io/v1/voices"

# `eleven_v3` es el que actúa: respeta las etiquetas de emoción ([sighs],
# [whispers]…) y cambia la intención según la puntuación. Los modelos
# anteriores (multilingual_v2, turbo) leen parejo y suenan a lector, no a
# locutor. Es la diferencia más grande entre «se entiende» y «engancha».
MODELO = "eleven_v3"

# Medido: subir `stability` por encima de 0,6 apaga la actuación y vuelve a
# sonar a lector; bajarlo de 0,4 la vuelve errática entre tomas de la misma
# voz. `similarity_boost` alto mantiene el timbre reconocible entre episodios.
AJUSTES = {"stability": 0.5, "similarity_boost": 0.8, "use_speaker_boost": True}

# 192 kbps pide el tier Creator de ElevenLabs. Si la cuenta no llega, la API
# contesta 403 `output_format_not_allowed`: se cae sola a 128, que está en
# todos los planes. Para una voz que después se masteriza a -14 LUFS la
# diferencia es inaudible; quedarse sin voz no.
FORMATOS = ("mp3_48000_192", "mp3_48000_128")

# ─────────────────────────────────────────────────────────── el ritmo

# Segundos de silencio que se dejan entre unidades de texto. Son lo que hace
# que suene a locución y no a lectura corrida. Medido contra locutores reales.
PAUSA_ORACION = 0.25     # entre oraciones
PAUSA_PARRAFO = 0.70     # entre párrafos: es la respiración que marca un tema nuevo
ARRANQUE = 0.40          # silencio antes de la primera palabra del episodio

# `eleven_v3` mete hasta 200 ms de silencio propio al principio de cada clip, y
# a veces una cola al final. Si no se recortan, cada línea entra tarde y las
# pausas de arriba se descontrolan. Se recorta por energía, no por tiempo fijo.
UMBRAL_SILENCIO_DB = -45.0
SR = 48000

# ─────────────────────────────────────────────────────────── el máster

# -14 LUFS / -1 dBTP es el estándar de YouTube y de Spotify para podcast.
# NO es opcional: sin masterizar, una voz fuerte y una suave en el mismo
# episodio llegan al oyente con 10 dB de diferencia.
LOUDNORM = "loudnorm=I=-14:TP=-1.0:LRA=11"

# Ducking: la música baja sola cuando entra la voz. `threshold` bajo (0,02) y
# `ratio` alto (16) para que la voz gane siempre; `release` largo (500 ms) para
# que la música vuelva suave y no «bombee» entre frase y frase.
DUCKING = "sidechaincompress=threshold=0.02:ratio=16:attack=25:release=500:makeup=1"
MUSICA_DB = -12.0        # cuánto se baja la música antes del ducking

# ─────────────────────────────────────────────────────────── las etiquetas

# Las que `eleven_v3` interpreta de verdad, con cuándo usar cada una. Van
# dentro del texto: "No sé qué decirte. [sighs] Tal vez tengas razón."
# OJO: un texto que sea SÓLO una etiqueta lo rechaza con 400.
TAGS = {
    "whispers": "secreto, confidencia, miedo contenido",
    "sighs": "resignación, cansancio, antes de ceder",
    "yawns": "sueño, aburrimiento, despertar",
    "nervously": "mentira, incomodidad, súplica",
    "curious": "pregunta genuina, descubrimiento",
    "excited": "euforia, hallazgo, urgencia positiva",
    "surprised": "sorpresa real, no reacción menor",
    "angry": "enojo sostenido",
    "shouting": "grito de verdad, con volumen",
    "sad": "duelo, pérdida — sólo en intensidad alta",
    "laughs": "risa",
}


@dataclass
class Ajustes:
    """Lo que la app puede cambiar por episodio o por usuario."""
    voz_id: str
    modelo: str = MODELO
    estabilidad: float = AJUSTES["stability"]
    similitud: float = AJUSTES["similarity_boost"]
    speaker_boost: bool = AJUSTES["use_speaker_boost"]
    pausa_oracion: float = PAUSA_ORACION
    pausa_parrafo: float = PAUSA_PARRAFO
    arranque: float = ARRANQUE
    masterizar: bool = True

    def voice_settings(self) -> dict:
        return {"stability": self.estabilidad, "similarity_boost": self.similitud,
                "use_speaker_boost": self.speaker_boost}


def clave(valor: str | None = None) -> str:
    """La API key de ElevenLabs: por parámetro, o de ELEVENLABS_API_KEY."""
    k = valor or os.environ.get("ELEVENLABS_API_KEY", "")
    if not k:
        raise RuntimeError("falta ELEVENLABS_API_KEY")
    return k
