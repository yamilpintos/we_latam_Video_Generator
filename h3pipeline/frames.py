"""Los primeros fotogramas: generarlos con nano banana y dejarlos a la
resolución exacta que H3 renderiza.

Por qué pasar referencias y no solo describir el estilo
  Describir "animación 2D con sombreado plano" da algo distinto en cada
  llamada. Mandando las imágenes que ya existen, el modelo ancla paleta,
  grosor de línea y diseño de personaje, y todos los fotogramas salen del
  mismo mundo.

Por qué normalizar
  nano banana devuelve la relación de aspecto que le parece aunque se la pidas
  por parámetro: en una tanda de 42 salieron tres distintas, siete de ellas en
  cinemascope. Si un dibujo entra a H3 en otra relación, lo aplasta y los
  personajes salen gordos. Recortar al centro pierde algo de borde pero no
  deforma a nadie.

  Y hay un recorte de ~2 % que es inevitable: **la resolución nativa de H3 no es
  16:9 exacto**. 1344/768 = 1,750 contra 1,778, y nano banana devuelve 1376 de
  lado largo. Por eso el aviso de `empaquetar` recién salta arriba del 5 %.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import config

# Cuál de los dos «nano banana». La diferencia es de precio, no de interfaz, y
# el nombre común los tapa a los dos: hasta el 31/8/2026 el módulo llamaba al
# Pro sin que nadie lo hubiera decidido, y un video de 4 minutos pagaba ~$6,5 de
# dibujos donde podía pagar ~$2.
#
#   gemini-2.5-flash-image   el nano banana común   ~$0,039 por imagen
#   gemini-3-pro-image       Nano Banana Pro        ~$0,13 (1K/2K) · ~$0,24 (4K)
#
# El Flash alcanza de sobra para un primer fotograma que después re-dibuja H3.
# El Pro se reserva para lo que sostiene la identidad —hojas de modelo y
# locaciones— y se pide con `motor="nanobanana-pro"`.
MODELO = "gemini-2.5-flash-image"
MODELO_PRO = "gemini-3-pro-image"
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}"


class SinCredito(RuntimeError):
    """Se acabaron los créditos de la API de imágenes. Reintentar no sirve."""


class Bloqueado(RuntimeError):
    """El modelo no devolvió imagen. Casi siempre es el filtro de contenido, que
    es intermitente: el mismo prompt pasa en el segundo o tercer intento."""


def _parte_imagen(ruta: Path) -> dict:
    tipo = mimetypes.guess_type(ruta.name)[0] or "image/png"
    return {"inline_data": {"mime_type": tipo,
                            "data": base64.b64encode(ruta.read_bytes()).decode()}}


def generar(prompt: str, refs: list[Path], clave: str, aspecto: str | None = None,
            intentos: int = 5, log=print, modelo: str = MODELO) -> bytes:
    config.certificados()
    partes = [_parte_imagen(Path(r)) for r in refs] + [{"text": prompt}]
    gen: dict = {"responseModalities": ["IMAGE"]}
    if aspecto:
        gen["imageConfig"] = {"aspectRatio": aspecto}
    cuerpo = {"contents": [{"parts": partes}], "generationConfig": gen}
    req = urllib.request.Request(API.format(modelo, clave), data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    for i in range(intentos):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=300))
        except urllib.error.HTTPError as e:
            detalle = e.read().decode()[:400]
            if e.code == 400 and aspecto and "imageConfig" in detalle:
                log("      la API rechazó aspectRatio, sigo sin él")
                return generar(prompt, refs, clave, None, intentos - i, log, modelo)
            # Un 429 puede ser dos cosas muy distintas: límite de tasa, que se
            # arregla esperando, o crédito agotado, que no se arregla nunca.
            # Reintentar el segundo sólo hace perder minutos.
            if "depleted" in detalle or "billing" in detalle or "quota" in detalle.lower():
                raise SinCredito(
                    "se acabaron los créditos de nano banana (Gemini). "
                    "Recargá en https://ai.studio/projects y volvé a correr `frames`: "
                    "los dibujos que ya existen no se rehacen.") from e
            if e.code in (429, 500, 503) and i < intentos - 1:
                espera = 20 * (i + 1)
                log(f"      HTTP {e.code}, reintento en {espera}s")
                time.sleep(espera)
                continue
            raise RuntimeError(f"{modelo} HTTP {e.code}: {detalle}")
        for cand in r.get("candidates", []):
            for parte in cand.get("content", {}).get("parts", []):
                dato = parte.get("inline_data") or parte.get("inlineData")
                if dato:
                    return base64.b64decode(dato["data"])
        razon = r.get("candidates", [{}])[0].get("finishReason", "?")
        if i < intentos - 1:
            log(f"      {razon}, reintento")
            time.sleep(5)
            continue
        raise Bloqueado(f"finishReason={razon}")
    raise Bloqueado("agotados los reintentos")


# ─────────────────────────── el otro generador ───────────────────────────
# OpenAI como alternativa a nano banana. Sirve de respaldo cuando se acaban los
# créditos de uno, y a veces resuelve mejor un encuadre que el otro se niega a
# dar. La interfaz es la misma, así que se elige con `motor=`.
API_OPENAI = "https://api.openai.com/v1/images"
MODELO_OPENAI = "gpt-image-1"
# Los únicos tamaños que acepta la API, y ninguno da la relación de H3:
# 1024×1536 es 1:1,50 y H3 quiere 1:1,75. `normalizar()` recorta los costados y
# **se pierde ~14 % del ancho**, contra el ~2 % de nano banana. No es evitable
# desde acá: hay que componer con el sujeto centrado y sin nada importante
# pegado a los bordes laterales.
TAMANO_OPENAI = {"9:16": "1024x1536", "16:9": "1536x1024"}


def generar_openai(prompt: str, refs: list[Path], clave: str, aspecto: str | None = None,
                   modelo: str = MODELO_OPENAI, log=print) -> bytes:
    """Lo mismo que `generar()`, con OpenAI.

    Con referencias usa `/images/edits`, que es el endpoint que acepta imágenes
    de entrada; sin ellas, `/images/generations`.
    """
    config.certificados()
    tam = TAMANO_OPENAI.get(aspecto or "9:16", "1024x1536")
    if refs:
        import secrets
        borde = "----h3-" + secrets.token_hex(12)
        partes = []
        for campo, valor in (("model", modelo), ("prompt", prompt),
                             ("size", tam), ("n", "1")):
            partes += [f"--{borde}\r\n".encode(),
                       f'Content-Disposition: form-data; name="{campo}"\r\n\r\n'.encode(),
                       f"{valor}\r\n".encode()]
        for r in refs:
            r = Path(r)
            tipo = mimetypes.guess_type(r.name)[0] or "image/png"
            partes += [f"--{borde}\r\n".encode(),
                       f'Content-Disposition: form-data; name="image[]"; '
                       f'filename="{r.name}"\r\n'.encode(),
                       f"Content-Type: {tipo}\r\n\r\n".encode(),
                       r.read_bytes(), b"\r\n"]
        partes.append(f"--{borde}--\r\n".encode())
        req = urllib.request.Request(
            API_OPENAI + "/edits", data=b"".join(partes), method="POST",
            headers={"Authorization": f"Bearer {clave}",
                     "Content-Type": f"multipart/form-data; boundary={borde}"})
    else:
        cuerpo = json.dumps({"model": modelo, "prompt": prompt,
                             "size": tam, "n": 1}).encode()
        req = urllib.request.Request(
            API_OPENAI + "/generations", data=cuerpo, method="POST",
            headers={"Authorization": f"Bearer {clave}",
                     "Content-Type": "application/json"})
    # Medido el 14/9/2026: la cuenta tiene un tope de 5 imágenes por minuto con
    # gpt-image-2.5-sunburst y contesta 429 `rate_limit_exceeded` con «try again
    # in 12s». Eso no es falta de saldo (`insufficient_quota`, también 429): se
    # espera lo que dice y se reintenta, en vez de tirar abajo el lote entero.
    for intento in range(12):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=420))
            break
        except urllib.error.HTTPError as e:
            detalle = e.read().decode("utf-8", "replace")[:400]
            if e.code == 429 and "rate_limit_exceeded" in detalle and intento < 11:
                m = re.search(r"try again in ([\d.]+)s", detalle)
                espera = (float(m.group(1)) if m else 20.0) + 2 + intento * 3
                log(f"      límite de velocidad, espero {espera:.0f}s")
                time.sleep(espera)
                continue
            if "billing" in detalle or "quota" in detalle.lower() or "insufficient" in detalle:
                raise SinCredito(f"sin créditos en OpenAI: {detalle[:200]}") from e
            if e.code == 400 and ("safety" in detalle or "moderation" in detalle):
                raise Bloqueado(f"filtro de contenido: {detalle[:160]}") from e
            raise RuntimeError(f"OpenAI HTTP {e.code}: {detalle}")
    # La API no devuelve el precio: devuelve tokens. Se loguean para sacar el
    # costo real después, contra la tarifa del modelo.
    if d.get("usage"):
        u = d["usage"]
        log(f"      tokens {modelo}: entrada {u.get('input_tokens')} · "
            f"salida {u.get('output_tokens')}")
    dato = d["data"][0]
    if dato.get("b64_json"):
        return base64.b64decode(dato["b64_json"])
    with urllib.request.urlopen(dato["url"], timeout=300) as r:
        return r.read()


def generar_storyboard(storyboard: dict, destino: Path, raiz: Path, force: bool = False,
                       clave: str | None = None, log=print,
                       motor: str = "nanobanana", modelo_openai: str = MODELO_OPENAI,
                       hilos: int = 1) -> tuple[list[Path], list[str]]:
    """Un PNG por asset del storyboard.json. Devuelve (hechos, bloqueados).

    `motor` elige el generador: `"nanobanana"` (Gemini Flash, el barato y el que
    conviene para un primer fotograma), `"nanobanana-pro"` (Gemini 3 Pro, ~3,4×
    más caro: para hojas de modelo y locaciones) u `"openai"` (con
    `modelo_openai`). Los que ya existen se saltean salvo `force`, así que se
    puede empezar con uno y terminar con el otro sin volver a pagar lo hecho.
    Un asset bloqueado no frena el lote: se anota y se sigue.

    `hilos` > 1 genera en paralelo. Medido el 14/9/2026: gpt-image-2.5-sunburst
    tarda ~85 s por imagen con referencias, así que 86 imágenes en fila son dos
    horas. Las referencias de un asset tienen que existir antes de su tanda:
    las madres van en una llamada y los fotogramas en otra.
    """
    from concurrent.futures import ThreadPoolExecutor
    if motor == "openai":
        clave = clave or config.leer_env("OPENAI_API_KEY")
    else:
        clave = clave or config.leer_env("nanobanana")
    modelo = MODELO_PRO if motor == "nanobanana-pro" else MODELO
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    hechos, bloqueados, pendientes = [], [], []
    for a in storyboard["assets"]:
        salida = destino / f"{a['id']}.png"
        if salida.exists() and not force:
            log(f"  =   {a['id']} ya existe")
            hechos.append(salida)
            continue
        refs = [Path(r) if Path(r).is_absolute() else Path(raiz) / r
                for r in a.get("refs", storyboard.get("refs", []))]
        faltan = [r for r in refs if not r.exists()]
        if faltan:
            raise FileNotFoundError(f"{a['id']}: faltan referencias {faltan}")
        pendientes.append((a, salida, refs))

    def uno(tarea):
        a, salida, refs = tarea
        t0 = time.time()
        log(f"  ·   {a['id']} …")
        asp = a.get("aspecto", storyboard.get("aspecto"))
        try:
            if motor == "openai":
                datos = generar_openai(a["prompt"], refs, clave, asp, log=log,
                                       modelo=modelo_openai)
            else:
                datos = generar(a["prompt"], refs, clave, asp, log=log, modelo=modelo)
        except Bloqueado as e:
            log(f"      BLOQUEADO {a['id']} ({e})")
            return a["id"], None
        except RuntimeError as e:
            # Un error suelto de la API no tira abajo las otras imágenes del lote
            # (se vio con un 429 el 14/9/2026). SinCredito sí corta: sigue de largo.
            log(f"      FALLÓ {a['id']} ({str(e)[:200]})")
            return a["id"], None
        salida.write_bytes(datos)
        log(f"      {a['id']}: {salida.stat().st_size // 1024} KB en {time.time() - t0:.0f}s")
        return a["id"], salida

    with ThreadPoolExecutor(max(1, hilos)) as ex:
        for aid, salida in ex.map(uno, pendientes):
            (hechos.append(salida) if salida else bloqueados.append(aid))
    return hechos, bloqueados


def normalizar(origen: Path, destino: Path, ancho: int, alto: int) -> float:
    """Recorta al centro a la relación pedida y escala a ancho×alto exactos.
    Devuelve la fracción del cuadro que se perdió (0 si ya venía bien)."""
    from PIL import Image
    im = Image.open(origen).convert("RGB")
    w, h = im.size
    objetivo = ancho / alto
    if w / h > objetivo:
        nuevo = int(h * objetivo)
        x = (w - nuevo) // 2
        im = im.crop((x, 0, x + nuevo, h))
    else:
        nuevo = int(w / objetivo)
        y = (h - nuevo) // 2
        im = im.crop((0, y, w, y + nuevo))
    perdido = 1 - (im.size[0] * im.size[1]) / (w * h)
    im = im.resize((ancho, alto), Image.LANCZOS)
    Path(destino).parent.mkdir(parents=True, exist_ok=True)
    im.save(destino, "PNG")
    return perdido
