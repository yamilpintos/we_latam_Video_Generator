"""Reimagina el reparto: cada personaje con OTRO actor, mismo vestuario, misma
escena. Luka lleva la cara del usuario (fotos en «referencias personaje/»).

    /c/Python314/python -X utf8 mis-videos/replica-danza/reparto_nuevo.py          # candidatos
    /c/Python314/python -X utf8 mis-videos/replica-danza/reparto_nuevo.py hoja     # sólo la hoja

Decisión del usuario (15/9, noche): rehacer el video con otros personajes,
manteniéndolos por escena, y él como un secundario (eligió Luka). El cuadro del
original es la plantilla de cada candidato: encuadre, pose, ropa, pelo y luz se
conservan; cambia la persona. Nano Banana Pro, ~$0,13 por imagen.

Salida en reparto-nuevo/<personaje>-<n>.png y reparto-nuevo/HOJA.jpg.
"""
import sys
import time
from pathlib import Path

from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1]))
from h3pipeline import frames, config  # noqa: E402

OUT = AQUI / "reparto-nuevo"
FOTOS = AQUI / "referencias personaje"
ORIG = AQUI / "assets"   # sb_T*.png: los 82 cuadros limpios (Nano Banana u OpenCV), ya normalizados

BASE = ("Image 1 is a frame from a live-action series. Use it as an exact template: keep the framing, "
        "the pose, the body position, the wardrobe, the hairstyle shape, the lighting, the colours and "
        "the background identical, pixel for pixel where possible. Replace ONLY the person's identity: "
        "the face and skin must belong to a different actor, described below. Photorealistic, natural "
        "skin texture, cinematic. Vertical 9:16 frame.")

# (personaje, cuadro plantilla, [descripciones de actor nuevo])
CANDIDATOS = {
    "hannah": ("T20", [
        # 15/9: la pelirroja no convenció; «rubia y distinta».
        "A young woman in her early twenties, Scandinavian look: pale skin, platinum-blonde hair in "
        "the same messy low bun with loose strands, light blue eyes, a slim straight nose, defined "
        "cheekbones and a small pointed chin.",
        "A young woman in her early twenties with warm olive skin, dark brown eyes, black hair in the "
        "same messy low bun, strong eyebrows and a soft oval face.",
    ]),
    "jack": ("T53", [
        "A man in his early thirties with Mediterranean features: black hair slicked back the same way, "
        "a short dark beard, dark brown eyes, a strong brow and a sharp jaw; keep the blood spatter and "
        "the neck tattoo.",
        "A man in his early thirties with Nordic features: ash-blond hair slicked back the same way, "
        "clean-shaven, ice-blue eyes, high cheekbones; keep the blood spatter and the neck tattoo.",
    ]),
    "wady": ("T64", [
        "A man in his early thirties with dark hair shaved short at the sides and curly on top, a "
        "black goatee, tan skin and dark eyes; same olive field jacket.",
        "A man in his early thirties with ginger hair and a full ginger beard, pale skin, light eyes; "
        "same olive field jacket.",
    ]),
}
# Luka: la cara del usuario. Las fotos van como imágenes 2 y 3.
LUKA_BASE = "T37"
LUKA = ("Images 2 and 3 are photos of a real man. The person in Image 1 must become HIM: his exact "
        "face, facial structure, skin tone and dark curly hair, recognisable as the same man. Keep his "
        "face clean-shaven like in the photos. Everything else stays from Image 1: the brown leather "
        "bomber jacket with the shearling collar, the black shirt, the rifle, the pose, the corridor, "
        "the lighting, the hard furious expression.")
LUKA_FOTOS = ["images.jfif", "1780924384434.jfif"]

SECUNDARIOS = {
    # 15/9: el usuario no quiere al matón pelado: con pelo y bigote.
    "matones": ("T66", ["Different gang members: replace every face with a different man's face, "
                        "keeping tattoos, clothes, weapons and poses. The man in the black tank top in "
                        "front is NOT bald any more: he has short dark hair and a thick dark moustache."]),
    "pasajera": ("T34", ["A different woman in her thirties, same curly hair shape and round glasses, "
                         "same cardigan, same screaming expression."]),
    "pasajero": ("T59", ["A different bald man in his fifties, same grey sweater, same frightened "
                         "pose, replace the face of the bearded man too."]),
}


def jpg(ruta: Path) -> Path:
    """Los .jfif no siempre se reconocen por extensión: a JPEG de verdad."""
    dst = OUT / "_refs" / (ruta.stem + ".jpg")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        Image.open(ruta).convert("RGB").save(dst, "JPEG", quality=95)
    return dst


def generar(nombre, plantilla, texto, refs_extra=(), modelo=frames.MODELO_PRO):
    dst = OUT / f"{nombre}.png"
    if dst.exists():
        return dst
    clave = config.leer_env("nanobanana")
    refs = [ORIG / f"sb_{plantilla}.png", *refs_extra]
    t0 = time.time()
    try:
        b = frames.generar(f"{BASE}\n\n{texto}", refs, clave, aspecto="9:16", intentos=3,
                           log=lambda m: None, modelo=modelo)
        dst.write_bytes(b)
        print(f"  {nombre:12} ok  {time.time() - t0:4.0f}s", flush=True)
    except Exception as e:
        print(f"  {nombre:12} FALLO {type(e).__name__}: {str(e)[:80]}", flush=True)
        return None
    return dst


def hoja():
    filas = []
    for grupo in (list(CANDIDATOS) + ["luka"] + list(SECUNDARIOS)):
        fs = sorted(OUT.glob(f"{grupo}-*.png"))
        if not fs:
            continue
        base = {**CANDIDATOS, **SECUNDARIOS}.get(grupo, (LUKA_BASE,))[0]
        ims = [Image.open(ORIG / f"sb_{base}.png").convert("RGB")] + [Image.open(f).convert("RGB") for f in fs]
        ims = [i.resize((240, 427)) for i in ims]
        filas.append((grupo, ims))
    ancho = max(len(ims) for _g, ims in filas) * 240
    s = Image.new("RGB", (ancho, 427 * len(filas)), "black")
    for r, (_g, ims) in enumerate(filas):
        for c, im in enumerate(ims):
            s.paste(im, (c * 240, r * 427))
    s.save(OUT / "HOJA.jpg", quality=88)
    print("hoja:", OUT / "HOJA.jpg", "· filas:", [g for g, _ in filas], "· columna 1 = original")


def main():
    OUT.mkdir(exist_ok=True)
    if len(sys.argv) > 1 and sys.argv[1] == "hoja":
        return hoja()
    for quien, (plantilla, textos) in {**CANDIDATOS, **SECUNDARIOS}.items():
        # Un solo candidato por personaje (15/9: «no quiero dos candidatos, elegí vos»).
        generar(f"{quien}-1", plantilla, textos[0])
    fotos = [jpg(FOTOS / f) for f in LUKA_FOTOS]
    generar("luka-1", LUKA_BASE, LUKA, refs_extra=fotos)
    hoja()


if __name__ == "__main__":
    main()
