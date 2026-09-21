"""Sintetizar con ElevenLabs `eleven_v3`, y elegir entre varias redacciones.

Por qué varias redacciones y no una
  La densidad (~17 cps) sirve para **estimar**, pero a nivel toma el error llega
  al 30 %: la misma cantidad de caracteres dura distinto según las sílabas, la
  puntuación y cómo la actúe el modelo. Escribir una sola redacción y esperar
  que entre es apostar.

  Sintetizar dos o tres y quedarse con la que mide mejor es barato: las 19
  líneas de una película de cinco minutos suman ~500 caracteres, así que probar
  tres variantes de cada una cuesta el 0,1 % de la cuota. Y elige mejor que el
  criterio propio — en producción eligió sola `[yawns]` sobre `[sighs]`, y
  descartó un suspiro que se comía el bloque entero.

Todo se cachea por **hash del texto**, así que cambiar una redacción invalida
sólo esa variante y no vuelve a pagar por las demás.

Dos trampas de v3, ya cubiertas acá:
  · rechaza con 400 un texto que sea **sólo una etiqueta**: `[sighs]` necesita
    al menos una vocalización;
  · mete hasta 200 ms de silencio al inicio de cada clip, y eso atrasa la voz
    respecto de los labios en todas las líneas. Por eso se mide la duración
    **útil**, sin los bordes: es la que va a sonar después del recorte.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from . import config, voz

API = "https://api.elevenlabs.io/v1/text-to-speech"
MODELO = "eleven_v3"
SR = 48000
UMBRAL_DB = -45.0     # qué se considera silencio de borde

AJUSTES = {"stability": 0.5, "similarity_boost": 0.8, "use_speaker_boost": True}


class ErrorTTS(RuntimeError):
    pass


def _clave(clave: str | None = None) -> str:
    return clave or config.leer_env("ELEVENLABS_API_KEY", obligatorio=False) \
        or config.leer_env("elevenlabs")


def sintetizar(texto: str, voz_id: str, clave: str | None = None,
               con_tiempos: bool = False, ajustes: dict | None = None):
    """Devuelve los bytes del MP3. Con `con_tiempos`, además las palabras con
    sus tiempos: `(mp3, [(palabra, ini, fin), ...])`."""
    if not voz.limpiar(texto):
        raise ErrorTTS(f"texto sólo con etiqueta ({texto!r}): v3 lo rechaza con 400")
    config.certificados()
    cuerpo = json.dumps({"text": texto, "model_id": MODELO,
                         "voice_settings": ajustes or AJUSTES}).encode()
    ruta = f"{API}/{voz_id}" + ("/with-timestamps" if con_tiempos else "")
    datos = None
    # 192 kbps pide el tier Creator; si el plan de la cuenta no llega,
    # ElevenLabs contesta 403 `output_format_not_allowed` y se cae a 128, que
    # está en todos los planes. Para una voz que después se masteriza a
    # -14 LUFS la diferencia es inaudible; quedarse sin voz no.
    for formato in ("mp3_44100_192", "mp3_44100_128"):
        req = urllib.request.Request(
            f"{ruta}?output_format={formato}", data=cuerpo,
            headers={"xi-api-key": _clave(clave), "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=240) as r:
                datos = r.read()
            break
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:300]
            if e.code == 403 and "output_format" in detalle \
                    and formato == "mp3_44100_192":
                continue
            raise ErrorTTS(f"ElevenLabs HTTP {e.code}: {detalle}") from e
    if not con_tiempos:
        return datos
    d = json.loads(datos.decode())
    return base64.b64decode(d["audio_base64"]), _palabras(d["alignment"])


def _palabras(al: dict) -> list[tuple[str, float, float]]:
    """Agrupa los tiempos por carácter que devuelve v3 en palabras."""
    pals, cur = [], None
    for c, a, b in zip(al["characters"], al["character_start_times_seconds"],
                       al["character_end_times_seconds"]):
        if c.isspace():
            if cur:
                pals.append(tuple(cur))
                cur = None
        elif cur is None:
            cur = [c, a, b]
        else:
            cur[0] += c
            cur[2] = b
    if cur:
        pals.append(tuple(cur))
    return pals


def duracion_util(mp3: Path) -> float:
    """Segundos de audio **sin** el silencio de los extremos. Es la que importa:
    v3 mete hasta 200 ms al inicio y eso se recorta antes de montar.
    Python puro (21/9: en Render no hay numpy ni soundfile y el primer largo
    murió acá con ModuleNotFoundError)."""
    import wave
    from array import array
    with tempfile.TemporaryDirectory() as td:
        w = Path(td) / "d.wav"
        subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-i", str(mp3),
                        "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(w)],
                       check=True, stdin=subprocess.DEVNULL)
        with wave.open(str(w), "rb") as f:
            datos = f.readframes(f.getnframes())
    x = array("h")
    x.frombytes(datos[: len(datos) - len(datos) % 2])
    if not len(x):
        return 0.0
    pico = max(abs(v) for v in x)
    if pico <= 0:
        return 0.0
    umbral = pico * (10 ** (UMBRAL_DB / 20))
    primero = next((i for i, v in enumerate(x) if abs(v) > umbral), None)
    if primero is None:
        return len(x) / SR
    ultimo = next(i for i in range(len(x) - 1, -1, -1) if abs(x[i]) > umbral)
    return float(ultimo - primero) / SR


def _puntaje(factor: float) -> float:
    """Menor es mejor; 0 entra exacta. Las que caen fuera del rango tolerable se
    penalizan fuerte pero no se descartan, por si ninguna entra."""
    base = abs(math.log(factor)) if factor > 0 else 9.9
    fuera = factor > voz.MAX_RAPIDO or factor < 1.0 / voz.MAX_LENTO
    return base + (1.0 if fuera else 0.0)


def elegir(linea: voz.Linea, cache: Path, clave: str | None = None,
           log=print) -> dict:
    """Sintetiza cada redacción de la línea, la mide, y devuelve la que mejor
    entra en la ventana.

        factor = duración útil / ventana
          1,00  entra exacta
          > 1   hay que comprimir (se tolera hasta 1,15)
          < 1   habría que ralentizar (sólo hasta 1,08, o sea 0,926)

    Devuelve `{"mp3", "texto", "factor", "tabla"}`. La tabla completa queda para
    poder mostrar **por qué** ganó.
    """
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    variantes = [linea.texto] + [v for v in linea.variantes if v != linea.texto]
    tabla = []
    for texto in variantes:
        # El hash en el nombre hace que cambiar una redacción invalide sólo esa.
        h = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:8]
        mp3 = cache / f"{linea.id}_{h}.mp3"
        nuevo = not mp3.exists()
        if nuevo:
            mp3.write_bytes(sintetizar(texto, linea.voz_id, clave))
        d = duracion_util(mp3)
        f = d / linea.ventana if linea.ventana > 0 else 9.9
        tabla.append({"texto": texto, "mp3": mp3, "dur": d, "factor": f,
                      "puntaje": _puntaje(f), "nuevo": nuevo})
    tabla.sort(key=lambda r: r["puntaje"])
    for r in tabla:
        log(f"      {r['factor']:5.2f}×  {r['dur']:4.2f}s  {len(r['texto']):3d}ch  "
            f"\"{r['texto'][:52]}\"{'   <-- entra' if r is tabla[0] else ''}")
    g = tabla[0]
    return {"mp3": g["mp3"], "texto": g["texto"], "factor": g["factor"], "tabla": tabla}


def generar(lineas: list[voz.Linea], cache: Path, clave: str | None = None,
            log=print) -> list[dict]:
    """Todas las líneas, con selección de variantes y caché. Una línea que falla
    no frena el lote: se anota y se sigue."""
    out = []
    for x in lineas:
        if not x.voz_id:
            log(f"  X  {x.id}: sin voz asignada (declarala en `voces` del proyecto)")
            continue
        log(f"  ·  {x.id} {x.personaje} · ventana {x.ventana:.1f} s")
        try:
            r = elegir(x, cache, clave, log)
        except ErrorTTS as e:
            log(f"     !! {e}")
            continue
        r["linea"] = x
        # En voz en OFF quedarse corto no es un defecto: el silencio entre
        # líneas es parte del guion. Sólo importa que no se pase de su hueco.
        malo = (r["factor"] > voz.MAX_RAPIDO if x.tipo == "off"
                else not voz.factor_ok(r["factor"]))
        if malo:
            # Fuera de rango se corrige el TEXTO y se regenera; no se fuerza el
            # audio. Regenerar sale casi gratis; deformar se escucha.
            log(f"     !! factor {r['factor']:.2f}× fuera de rango: reescribir la línea")
        out.append(r)
    return out
