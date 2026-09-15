"""Arma el paquete de la segunda corrida: solo los planos que hay que rehacer.

    python Proyecto_Aladino/rehacer.py

De los 42 de la primera corrida, 37 quedaron bien. Este script empaqueta los
que no, con los dibujos y los prompts ya corregidos, para regenerarlos solos.
Es la ventaja concreta de que los planos sean independientes: rehacer 14 no
obliga a tocar los otros 28.

POR QUE ESTA CADA UNO EN LA LISTA
  Inventaron cosas que no estaban en el dibujo. H3 arranca clavado en el primer
  fotograma pero deriva hacia el final del plano:
    P06  el mago quedo como una mancha negra sin cara
    P10  cambio las dunas por un caniadon rocoso y Aladino sonriendo
    P11  el mago envuelto en llamas que no existen
    P20  la oreja y la barba del mago metidas en el primer plano de Aladino
    P40  el mago en un interior con arcadas en vez del patio al amanecer

  Dibujaron el humo como nubes de caricatura, que chocan con el estilo:
    P12 P16 P23 P24

  Tenian mal la mirada o la expresion, y ya se les rehizo el dibujo:
    P07 P33

  No se llegaron a bajar antes de borrar la instancia:
    P39 P41 P42

EL EXPERIMENTO
  Los prompts ahora llevan NO_INVENTES, que antes no estaba. Esta corrida va a
  8 pasos con turbo, igual que la primera, para aislar la variable: si con el
  mismo sampleo y el prompt nuevo desaparecen los inventos, la culpa era del
  prompt y nos quedamos con la configuracion barata. Si siguen, hay que probar
  PASOS=20 TURBO=0, que cuesta 2.4 veces mas.
"""
import json
import pathlib
import shutil
import zipfile

import cv2

RAIZ = pathlib.Path(__file__).parent
PROY = RAIZ.parent
DEST = PROY / "SUBIR_A_VAST" / "rehacer"
W, H = 1344, 768

REHACER = {
    "P06": "el mago quedo como mancha negra sin cara",
    "P07": "dibujo nuevo: mirada a la derecha",
    "P10": "invento un caniadon; dibujo nuevo con dunas y el chico agotado",
    "P11": "invento fuego alrededor del mago",
    "P12": "humo como nubes de caricatura",
    "P16": "humo como nubes de caricatura",
    "P20": "se colo la cara del mago; dibujo nuevo, expresion terca",
    "P23": "humo como nubes de caricatura",
    "P24": "humo como nubes de caricatura",
    "P33": "dibujo nuevo: mirada a la derecha, sobre el hombro",
    "P39": "no se llego a bajar",
    "P40": "invento un interior en vez del patio al amanecer",
    "P41": "no se llego a bajar",
    "P42": "no se llego a bajar",
}


def normalizar(origen, destino):
    im = cv2.imread(str(origen))
    alto, ancho = im.shape[:2]
    obj = W / H
    if ancho / alto > obj:
        n = int(alto * obj); x = (ancho - n) // 2; im = im[:, x:x + n]
    else:
        n = int(ancho / obj); y = (alto - n) // 2; im = im[y:y + n]
    inter = cv2.INTER_AREA if im.shape[1] > W else cv2.INTER_CUBIC
    cv2.imwrite(str(destino), cv2.resize(im, (W, H), interpolation=inter))


def main():
    todos = json.loads((RAIZ / "planos.json").read_text(encoding="utf-8"))
    sel = [p for p in todos["planos"] if p["id"] in REHACER]
    if len(sel) != len(REHACER):
        faltan = set(REHACER) - {p["id"] for p in sel}
        raise SystemExit(f"!! no encontre {faltan} en planos.json")

    assets = DEST / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for viejo in assets.glob("*.png"):
        viejo.unlink()
    for p in sel:
        normalizar(RAIZ / p["first_frame"], assets / f"sb_{p['id']}.png")

    (DEST / "planos.json").write_text(json.dumps(
        {"_comentario": "Solo los planos a rehacer de la primera corrida. "
                        "Los prompts llevan NO_INVENTES, que es la correccion "
                        "que sale de haber medido la deriva.",
         "fps": 24, "planos": sel}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    z = PROY / "SUBIR_A_VAST" / "REHACER-PARA-VAST.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in sorted(DEST.rglob("*")):
            if f.is_file():
                zf.write(f, "rehacer/" + f.relative_to(DEST).as_posix())
        # Los scripts van en la raiz del zip: la instancia puede tener versiones
        # viejas que no aceptan PLANOS ni ANCHO.
        for n in ("lanzar.sh", "h3-planos.py"):
            zf.write(PROY / "SUBIR_A_VAST" / n, n)

    seg = sum(p["segundos"] for p in sel)
    print(f"{len(sel)} planos, {seg:.1f} s de video\n")
    for p in sel:
        print(f"  {p['id']}  {p['tipo']:<4} {p['segundos']:4.1f}s   {REHACER[p['id']]}")
    # 8 pasos con turbo dieron ~1.0 min por segundo de video en la maquina de
    # 4x5090; 20 pasos sin turbo cuesta 2.4 veces mas (COSTOS-H3.md tabla 1).
    for nom, factor, pasos in (("8 pasos turbo", 1.0, "PASOS=8"),
                               ("20 pasos sin turbo", 2.4, "PASOS=20 TURBO=0")):
        gpu = seg * factor
        gpus = {}
        for i, p in enumerate(sel):
            gpus.setdefault(i % 4, []).append(p["segundos"] * factor)
        pared = max(sum(v) for v in gpus.values())
        print(f"\n  {nom:<20} {gpu:4.0f} min de GPU   pared {pared:3.0f} min   "
              f"${pared / 60 * 1.79:.2f}   ({pasos})")
    print(f"\n{z.name}  {z.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
