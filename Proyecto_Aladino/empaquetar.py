"""Arma SUBIR_A_VAST: los dibujos normalizados, la lista de planos y los
scripts. Se corre despues de revisar el storyboard y antes de alquilar nada.

Lo unico no obvio que hace es NORMALIZAR los dibujos a 1344x768 exactos, que es
la resolucion a la que renderiza H3. nanobanana devuelve lo que le parece: en
esta tanda salieron tres relaciones de aspecto distintas, y siete dibujos en
cinemascope de 2.36:1. Si esos entran asi, H3 los aplasta a 1.75:1 y los
personajes salen gordos. Recortando al centro se pierde algo de ancho, pero no
se deforma a nadie.
"""
import json
import pathlib
import shutil

import cv2

RAIZ = pathlib.Path(__file__).parent
PROY = RAIZ.parent
DEST = PROY / "SUBIR_A_VAST"
W, H = 1344, 768


def normalizar(origen, destino):
    """Recorta al centro a 1344x768 y devuelve cuanto hubo que recortar."""
    im = cv2.imread(str(origen))
    alto, ancho = im.shape[:2]
    objetivo = W / H
    if ancho / alto > objetivo:          # muy panoramico: recorto a los costados
        nuevo = int(alto * objetivo)
        x = (ancho - nuevo) // 2
        im = im[:, x:x + nuevo]
    else:                                 # muy alto: recorto arriba y abajo
        nuevo = int(ancho / objetivo)
        y = (alto - nuevo) // 2
        im = im[y:y + nuevo]
    perdido = 1 - (im.shape[1] * im.shape[0]) / (ancho * alto)
    inter = cv2.INTER_AREA if im.shape[1] > W else cv2.INTER_CUBIC
    cv2.imwrite(str(destino), cv2.resize(im, (W, H), interpolation=inter))
    return perdido


def main():
    planos = json.loads((RAIZ / "planos.json").read_text(encoding="utf-8"))["planos"]
    assets = DEST / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    # Los dibujos viejos del metodo encadenado no van: el runner de planos solo
    # lee sb_*.png y de paso la subida por Jupyter pesa menos.
    for viejo in assets.glob("*.png"):
        viejo.unlink()

    recortados = []
    for p in planos:
        origen = RAIZ / p["first_frame"]
        if not origen.exists():
            raise SystemExit(f"!! falta el dibujo de {p['id']}: {origen.name}")
        perdido = normalizar(origen, assets / origen.name)
        if perdido > 0.02:
            recortados.append((p["id"], perdido))

    shutil.copy(RAIZ / "planos.json", DEST / "planos.json")
    shutil.copy(PROY / "scripts" / "vast-setup-h3.sh", DEST / "vast-setup-h3.sh")

    peso = sum(f.stat().st_size for f in DEST.rglob("*")) / 1e6
    print(f"{len(planos)} dibujos normalizados a {W}x{H}")
    if recortados:
        print(f"\n  {len(recortados)} venian en otra relacion de aspecto y se "
              f"recortaron al centro:")
        for pid, q in sorted(recortados, key=lambda x: -x[1]):
            print(f"    {pid}  se perdio el {q*100:.0f}% del cuadro")
        print("  Si alguno pierde algo importante, se regenera ese dibujo y "
              "se vuelve a empaquetar.")
    print(f"\nSUBIR_A_VAST: {peso:.0f} MB")
    for f in sorted(DEST.iterdir()):
        if f.is_file():
            print(f"  {f.name}")
    print(f"  assets/  ({len(list(assets.glob('*.png')))} dibujos)")


if __name__ == "__main__":
    main()
