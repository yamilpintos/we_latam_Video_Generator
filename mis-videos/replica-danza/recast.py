"""Los 82 cuadros del original con el reparto nuevo: misma toma, otros actores.

    /c/Python314/python -X utf8 mis-videos/replica-danza/recast.py --gpt [T01 T02 …]   # → recast-gpt/
    /c/Python314/python -X utf8 mis-videos/replica-danza/recast.py [--flash] [T01 …]   # Nano Banana → recast/

15/9: Nano Banana Pro hizo 29 y se acabó el crédito de Gemini; el usuario pidió
arrancar de nuevo, todo con GPT (un solo generador para los 82: la consistencia
entre tomas depende de eso). `--gpt` usa gpt-image-2.5-sunburst con 4 hilos
(Tier 1: 5 imágenes/min) y escribe en recast-gpt/.

Por cada toma: el cuadro limpio del original (assets/sb_T*.png) es la plantilla
—encuadre, pose, ropa, luz y fondo se conservan— y las hojas del reparto nuevo
(reparto-nuevo/*.png) dicen quién es cada persona. Luka lleva además las fotos
del usuario. Salida en recast/sb_T*.png; los que el filtro bloquea quedan
anotados en recast/bloqueados.txt (se resuelven aparte). Hojas de control en
recast/hoja-*.jpg, con el original a la izquierda de cada par.
"""
import json
import sys
import time
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parents[1]))
import tomas as T  # noqa: E402
from h3pipeline import frames, config  # noqa: E402

OUT = AQUI / "recast"
REP = AQUI / "reparto-nuevo"
ASSETS = AQUI / "assets"
FOTOS = [REP / "_refs" / "images.jpg", REP / "_refs" / "1780924384434.jpg"]

# personaje de tomas.py → (hoja del reparto nuevo, cómo se lo nombra)
HOJA = {
    "hannah": ("hannah-1", "Hannah, the young woman in the plaid flannel shirt"),
    "jack_camisa": ("jack-1", "Jack, the man in the white shirt and black shoulder harness"),
    "jack_abrigo": ("jack-1", "Jack, the man in the long black coat (same actor as the reference, "
                              "here wearing a black fedora and coat)"),
    "luka": ("luka-1", "Luka, the heavy man in the brown leather bomber jacket with the rifle"),
    "wady": ("wady-1", "Wady, the man in the olive field jacket"),
    "matones": ("matones-1", "the gang gunmen"),
    "pasajeros": (None, "the train passengers"),
}
# Los pasajeros tienen dos hojas (ella con anteojos, él calvo): se eligen por toma.
# Sin esto, T34 salió sin referencia de cara y GPT le quitó los anteojos (16/9).
PASAJERO_HOJA = {"34": ("pasajera-1", "the screaming woman passenger with round glasses"),
                 "58": ("pasajero-1", "the bald passenger in the grey sweater"),
                 "59": ("pasajero-1", "the bald passenger in the grey sweater")}

BASE = ("Image 1 is a frame from a live-action series. Recreate this exact frame: keep the framing, "
        "the camera angle, every pose and body position, the wardrobe, the hairstyle shapes, the "
        "lighting, the colours and the background identical. Replace ONLY the identity of the people "
        "with the actors shown in the other reference images, as listed below; each actor must be "
        "clearly recognisable as the same person as in their reference. People not listed keep a "
        "generic, different face from the original. Do NOT turn anyone towards the camera: a person "
        "seen from behind, in profile or out of focus in Image 1 stays exactly so, same head angle, "
        "same amount of face visible; the reference images give the identity only where a face is "
        "already visible. Photorealistic, natural skin texture, cinematic, no text or logos. Vertical "
        "9:16 frame.")


# El filtro de GPT rechaza siempre estas dos (a horcajadas; grito con la cabeza
# atrás). Se agrega una lectura inocente de la escena; si igual no pasa, quedan
# con el cuadro del original.
SUAVIZADO = {
    # 16/9: el recast de T34 salió sin anteojos y H3 se los puso a mitad de clip
    # porque el texto los nombra (REGLAS 64): el cuadro tiene que traerlos.
    "34": "The screaming woman wears round wire-rimmed glasses, exactly like the woman in the "
          "reference image; keep the glasses on her face.",
    "77": "Context: a staged, fully clothed scene from a TV drama, seen from behind the woman; a "
          "hug on a sofa in a train cabin. Nothing explicit.",
    "81": "Context: a woman's face in profile, startled, mouth open as she turns towards a noise "
          "at the door; a staged scene from a TV thriller.",
}


def prompt_y_refs(t):
    # Plantilla alternativa (zona sensible desenfocada) si existe: _plantilla_T77.png
    alt = OUT / f"_plantilla_T{t[0]}.png"
    refs = [alt if alt.exists() else ASSETS / f"sb_T{t[0]}.png"]
    lineas = [SUAVIZADO[t[0]]] if t[0] in SUAVIZADO else []
    for n in t[5]:
        hoja, nombre = HOJA[n]
        if hoja is None:
            if t[0] in PASAJERO_HOJA:
                hoja, nombre = PASAJERO_HOJA[t[0]]
            else:
                continue
        if n == "luka":
            refs += [REP / f"{hoja}.png", *FOTOS]
            lineas.append(f"Images {len(refs) - 2}, {len(refs) - 1} and {len(refs)} show the actor who "
                          f"plays {nombre}: the last two are photos of the real man; his face must be his.")
        else:
            refs.append(REP / f"{hoja}.png")
            lineas.append(f"Image {len(refs)} shows the actor who plays {nombre}.")
    return BASE + "\n\n" + "\n".join(lineas), refs


def hojas():
    fs = [t for t in T.TOMAS if (OUT / f"sb_T{t[0]}.png").exists()]
    for i in range(0, len(fs), 7):
        g = fs[i:i + 7]
        s = Image.new("RGB", (len(g) * 2 * 150, 267), "black")
        for c, t in enumerate(g):
            a = Image.open(ASSETS / f"sb_T{t[0]}.png").convert("RGB").resize((150, 267))
            b = Image.open(OUT / f"sb_T{t[0]}.png").convert("RGB").resize((150, 267))
            s.paste(a, (c * 300, 0))
            s.paste(b, (c * 300 + 150, 0))
        s.save(OUT / f"hoja-{i // 7 + 1:02d}.jpg", quality=88)
    print(f"{len(fs)} recreados · hojas en {OUT}")


def main():
    global OUT
    gpt = "--gpt" in sys.argv
    if gpt:
        OUT = AQUI / "recast-gpt"
    OUT.mkdir(exist_ok=True)
    flash = "--flash" in sys.argv
    modelo = frames.MODELO if flash else frames.MODELO_PRO
    solo = {a for a in sys.argv[1:] if a.startswith("T")}
    clave = config.leer_env("OPENAI_API_KEY") if gpt else config.leer_env("nanobanana")
    bloq = OUT / "bloqueados.txt"
    bloqueados = set(bloq.read_text().split()) if bloq.exists() else set()
    pendientes = []
    for t in T.TOMAS:
        k = f"T{t[0]}"
        if solo and k not in solo:
            continue
        dst = OUT / f"sb_{k}.png"
        if dst.exists():
            continue
        if not t[5]:                     # sin personas: el cuadro limpio sirve tal cual
            Image.open(ASSETS / f"sb_{k}.png").save(dst)
            continue
        pendientes.append((k, t, dst))

    def uno(item):
        k, t, dst = item
        p, refs = prompt_y_refs(t)
        t0 = time.time()
        try:
            if gpt:
                b = frames.generar_openai(p, refs, clave, aspecto="9:16",
                                          modelo="gpt-image-2.5-sunburst", log=lambda m: None)
            else:
                b = frames.generar(p, refs, clave, aspecto="9:16", intentos=2, log=lambda m: None,
                                   modelo=modelo)
            dst.write_bytes(b)
            print(f"  {k:5} ok {time.time() - t0:3.0f}s · {len(refs)} refs", flush=True)
            return k, True
        except Exception as e:
            print(f"  {k:5} BLOQUEADO {type(e).__name__} {str(e)[:70]}", flush=True)
            return k, False

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(4 if gpt else 1) as ex:
        res = list(ex.map(uno, pendientes))
    for k, ok in res:
        (bloqueados.discard if ok else bloqueados.add)(k)
    bloq.write_text(" ".join(sorted(bloqueados)))
    print(f"{sum(ok for _k, ok in res)} generados · bloqueados: {' '.join(sorted(bloqueados)) or '-'}")
    hojas()


if __name__ == "__main__":
    main()
