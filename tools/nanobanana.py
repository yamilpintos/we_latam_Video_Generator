"""
Genera imágenes madre con Gemini (nano banana), heredando el estilo de referencias.

    python tools/nanobanana.py assets.json salida/

El JSON lleva una lista de assets; cada uno con `id`, `prompt` y opcionalmente
`refs` (rutas de imágenes que definen el estilo). Escribe `<id>.png` en la carpeta.

`aspecto` ("16:9", "9:16"…) va suelto en el asset o global en el plan, y se pide
por parámetro de la API. Describirlo en el prompt no alcanza: en una tanda de 42
imágenes pidiendo 16:9 por texto salieron tres relaciones de aspecto distintas.

Por qué pasar referencias y no solo describir el estilo
  Describir "animación 2D con sombreado plano" da algo distinto en cada llamada.
  Mandando las dos imágenes que ya existen del castillo y la princesa, el modelo
  ancla paleta, grosor de línea y diseño de personaje, y todos los assets salen
  del mismo mundo. Es lo mismo que Ref2VA hace después con el video.
"""

import base64
import json
import mimetypes
import pathlib
import sys
import time
import urllib.error
import urllib.request

MODELO = "gemini-3-pro-image"
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}"


class Bloqueado(RuntimeError):
    """El modelo no devolvió imagen. Casi siempre el filtro de contenido."""


def clave(nombre="nanobanana"):
    env = pathlib.Path(__file__).resolve().parent.parent / ".env"
    for linea in env.read_text(encoding="utf-8", errors="replace").splitlines():
        if linea.startswith(nombre + "="):
            return linea.split("=", 1)[1].strip()
    raise SystemExit(f"!! falta {nombre} en .env")


def parte_imagen(ruta):
    p = pathlib.Path(ruta)
    tipo = mimetypes.guess_type(p.name)[0] or "image/png"
    return {"inline_data": {"mime_type": tipo,
                            "data": base64.b64encode(p.read_bytes()).decode()}}


def generar(prompt, refs, key, intentos=3, aspecto=None):
    """`aspecto` es "16:9", "9:16", etc. Pedirlo por parametro y no solo por
    texto es la unica forma fiable: describiendolo en el prompt, nano banana
    devolvio tres relaciones distintas en una misma tanda de 42 imagenes."""
    partes = [parte_imagen(r) for r in refs] + [{"text": prompt}]
    gen = {"responseModalities": ["IMAGE"]}
    if aspecto:
        gen["imageConfig"] = {"aspectRatio": aspecto}
    cuerpo = {"contents": [{"parts": partes}], "generationConfig": gen}
    req = urllib.request.Request(
        API.format(MODELO, key), data=json.dumps(cuerpo).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    for i in range(intentos):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=300))
        except urllib.error.HTTPError as e:
            detalle = e.read().decode()[:400]
            if e.code == 400 and aspecto and "imageConfig" in detalle:
                # Esta version de la API no acepta el campo: seguimos sin el y
                # que el prompt haga lo que pueda.
                print("      la API rechazo aspectRatio, sigo sin el")
                return generar(prompt, refs, key, intentos - i, None)
            if e.code in (429, 500, 503) and i < intentos - 1:
                espera = 20 * (i + 1)
                print(f"      HTTP {e.code}, reintento en {espera}s")
                time.sleep(espera)
                continue
            raise SystemExit(f"!! HTTP {e.code}: {detalle}")
        for cand in r.get("candidates", []):
            for parte in cand.get("content", {}).get("parts", []):
                dato = parte.get("inline_data") or parte.get("inlineData")
                if dato:
                    return base64.b64decode(dato["data"])
        # Sin imagen suele ser el filtro de contenido, que es INTERMITENTE: el
        # mismo prompt pasa en el segundo o tercer intento. Vale la pena reintentar.
        razon = r.get("candidates", [{}])[0].get("finishReason", "?")
        if i < intentos - 1:
            print(f"      {razon}, reintento", end=" ", flush=True)
            time.sleep(5)
            continue
        raise Bloqueado(f"finishReason={razon}")
    raise Bloqueado("agotados los reintentos")


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    plan = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    destino = pathlib.Path(sys.argv[2])
    destino.mkdir(parents=True, exist_ok=True)
    key = clave()
    raiz = pathlib.Path(sys.argv[1]).resolve().parent
    fallidos = []

    for a in plan["assets"]:
        salida = destino / f"{a['id']}.png"
        if salida.exists() and "--force" not in sys.argv:
            print(f"  =   {a['id']} ya existe")
            continue
        refs = [raiz / r if not pathlib.Path(r).is_absolute() else pathlib.Path(r)
                for r in a.get("refs", plan.get("refs", []))]
        faltan = [r for r in refs if not r.exists()]
        if faltan:
            raise SystemExit(f"!! faltan referencias: {faltan}")
        print(f"  ·   {a['id']} …", end=" ", flush=True)
        t0 = time.time()
        try:
            salida.write_bytes(generar(a["prompt"], refs, key, intentos=5,
                                       aspecto=a.get("aspecto", plan.get("aspecto"))))
        except Bloqueado as e:
            # Un asset bloqueado no puede frenar el lote: se anota y se sigue.
            fallidos.append(a["id"])
            print(f"BLOQUEADO ({e})")
            continue
        print(f"{salida.stat().st_size // 1024} KB en {time.time() - t0:.0f}s")

    print(f"\n{len(list(destino.glob('*.png')))} imágenes en {destino}")


if __name__ == "__main__":
    main()
