# -*- coding: utf-8 -*-
"""
Eleven Music: POST /v1/music. Misma cuenta y misma key que el motor de doblaje.

Trampas medidas:
  · `seed` NO se puede usar con `prompt` (422). Sólo con composition_plan.
  · `pcm_48000` devuelve PCM crudo s16le estéreo, sin cabecera: hay que envolverlo.
  · el saldo de /user/subscription tarda en reflejar Music; la atribución real está
    en /usage/character-stats?breakdown_type=product_type.
Precio medido: 902 créditos/min de audio GENERADO = USD 0,150/min (Scale, USD 299 por 1,8 M cr).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import wave
from pathlib import Path

from . import config as C

BASE = "https://api.elevenlabs.io/v1"


def api_key() -> str:
    k = os.getenv("ELEVENLABS_API_KEY", "")
    if k:
        return k
    for env in (C.RAIZ / ".env", C.FOTON / "dubai_v2" / ".env"):      # la app, y el motor si está
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ELEVENLABS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("falta ELEVENLABS_API_KEY (en el entorno o en .env)")


def saldo() -> int:
    r = urllib.request.Request(f"{BASE}/user/subscription", headers={"xi-api-key": api_key()})
    d = json.load(urllib.request.urlopen(r, timeout=30))
    return int(d["character_limit"] - d["character_count"])


def generar(prompt: str, largo_s: float, dst: Path, log=print) -> Path:
    body = {"prompt": prompt, "music_length_ms": int(largo_s * 1000),
            "model_id": C.MODELO_MUSICA, "force_instrumental": True}
    req = urllib.request.Request(f"{BASE}/music?output_format=pcm_48000",
                                 data=json.dumps(body).encode(),
                                 headers={"xi-api-key": api_key(),
                                          "Content-Type": "application/json"},
                                 method="POST")
    try:
        raw = urllib.request.urlopen(req, timeout=600).read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Eleven Music HTTP {e.code}: "
                           f"{e.read()[:300].decode('utf-8', 'replace')}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dst), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(raw)
    log(f"    {dst.name}  {len(raw)/(48000*4):.1f}s")
    return dst
