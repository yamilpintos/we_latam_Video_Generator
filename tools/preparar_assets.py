"""
Mapea los assets crudos a los IDs de plano del timeline y los deja listos.

Las imágenes se ordenan por fecha de modificación —el orden en que las generaste—
y se asignan a los planos DepthFlow en orden de timeline. Los videos de Veo, igual.

    python tools/preparar_assets.py --dry-run
    python tools/preparar_assets.py
"""

import argparse
import csv
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
IMGS_CRUDAS = ROOT / "Imagenes" / "imagenes en movimiento"
VIDS_CRUDOS = ROOT / "Pruebas video"
DEST_IMG = ROOT / "output" / "mars-climate-orbiter" / "img"
DEST_VEO = ROOT / "output" / "mars-climate-orbiter" / "veo"
W, H = 1920, 1080

# Los 10 planos VEO en orden de timeline
VEO = ["S01-P01", "S01-P04", "S02-P05", "S03-P03", "S04-P05",
       "S05-P02", "S05-P04", "S06-P02", "S07-P03", "S09-P02"]


def ids_depthflow():
    with open(ROOT / "tools" / "shotlist-mco.csv", encoding="utf-8-sig") as fh:
        return [r["id"].strip() for r in csv.DictReader(fh)]


def a_16_9(im: Image.Image) -> Image.Image:
    """Recorte centrado a 16:9 y escala a 1920x1080."""
    w, h = im.size
    if w / h > W / H:                      # demasiado ancha: recortar a los lados
        nw = int(h * W / H)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:                                  # demasiado alta: recortar arriba y abajo
        nh = int(w * H / W)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((W, H), Image.LANCZOS)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    imgs = sorted(IMGS_CRUDAS.glob("*.png"), key=lambda p: p.stat().st_mtime)
    vids = sorted(VIDS_CRUDOS.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    ids = ids_depthflow()

    print(f"imágenes crudas: {len(imgs)} · planos DepthFlow: {len(ids)}")
    print(f"videos crudos:   {len(vids)} · planos VEO: {len(VEO)}")
    if len(imgs) != len(ids) or len(vids) != len(VEO):
        print("\nNO COINCIDEN LAS CANTIDADES. Revisá antes de seguir.")
        return 1

    print("\nmapeo imágenes → plano:")
    for p, sid in zip(imgs, ids):
        print(f"  {p.name[:44]:46s} → IMG_{sid}.png")
    print("\nmapeo videos → plano:")
    for p, sid in zip(vids, VEO):
        print(f"  {p.name:10s} → VID_{sid}.mp4")

    if args.dry_run:
        return 0

    DEST_IMG.mkdir(parents=True, exist_ok=True)
    DEST_VEO.mkdir(parents=True, exist_ok=True)
    for p, sid in zip(imgs, ids):
        im = Image.open(p).convert("RGB")
        a_16_9(im).save(DEST_IMG / f"IMG_{sid}.png")
    for p, sid in zip(vids, VEO):
        shutil.copy2(p, DEST_VEO / f"VID_{sid}.mp4")
    print(f"\n{len(imgs)} imágenes recortadas a {W}x{H} en {DEST_IMG}")
    print(f"{len(vids)} videos copiados a {DEST_VEO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
