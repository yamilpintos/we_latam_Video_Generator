"""
Render en lote de los planos STILL con DepthFlow.

Lee una shotlist CSV (id,tecnica), busca IMG_<id>.png y escribe MOV_<id>.mp4
de 5,0 s exactos a 1920x1080 / 24 fps.

    uv run tools/depthflow_batch.py --shotlist tools/shotlist-mco.csv \
        --images output/mars-climate-orbiter/img \
        --out    output/mars-climate-orbiter/mov

Flags útiles:
    --dry-run   valida la shotlist y las imágenes sin renderizar nada
    --ssaa 2.0  supersampling para el export final (1.5 alcanza para revisar)
    --only S01  renderiza solo los planos de una secuencia
    --force     re-renderiza aunque el MP4 ya exista

Requiere ffmpeg en el PATH. La primera corrida descarga el modelo de estimación
de profundidad (varios cientos de MB).
"""

# /// script
# requires-python = ">=3.10"
# dependencies = ["depthflow"]
# ///

import argparse
import csv
import shutil
import sys
import time
from pathlib import Path

# Los nombres se declaran acá, sin importar depthflow, para que --dry-run pueda
# validar una shotlist en una máquina que todavía no tiene el paquete instalado.
# Tienen que coincidir con el dict SCENES de depthflow_scenes.py.
TECHNIQUES = ("acercar", "alejar", "quieto")

FPS = 24  # tiene que coincidir con Veo 3, no lo cambies
DURATION = 5.0  # la grilla del pipeline: STILL y GFX duran 5 s
WIDTH, HEIGHT = 1920, 1080


def load_shotlist(path: Path) -> list[tuple[str, str]]:
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sid = (row.get("id") or "").strip()
            tech = (row.get("tecnica") or "").strip().lower()
            if not sid or sid.startswith("#"):
                continue
            rows.append((sid, tech))
    return rows


def validate(rows, images: Path) -> list[str]:
    """Devuelve la lista de problemas. Vacía = todo bien."""
    problems = []
    seen = set()
    prev_tech = None
    for sid, tech in rows:
        if tech not in TECHNIQUES:
            problems.append(f"{sid}: técnica desconocida '{tech}' — válidas: {', '.join(TECHNIQUES)}")
        if sid in seen:
            problems.append(f"{sid}: ID duplicado")
        seen.add(sid)
        if not (images / f"IMG_{sid}.png").exists():
            problems.append(f"{sid}: falta {images / f'IMG_{sid}.png'}")
        # El sentido no se repite en planos consecutivos: dos acercamientos
        # seguidos y el video respira en una sola dirección.
        if tech == prev_tech:
            problems.append(f"{sid}: repite '{tech}' del plano anterior — alterná el sentido")
        prev_tech = tech
    return problems


def worker(tecnica: str, img: str, out: str, ssaa: str) -> int:
    """Renderiza un solo clip y termina.

    Por qué un proceso por clip: crear varias escenas de DepthFlow en el mismo
    proceso agota la memoria de texturas de OpenGL. Con SSAA 2.0 a 1080p cada
    escena reserva buffers de 3840x2160 y no los libera; en esta máquina, sin GPU
    dedicada, el tercer render falla con "cannot create texture". Salir del proceso
    destruye el contexto y lo devuelve todo.
    """
    try:
        import truststore
        truststore.inject_into_ssl()
    except ImportError:
        pass
    sys.path.insert(0, str(Path(__file__).parent))
    from depthflow_scenes import SCENES

    scene = SCENES[tecnica](backend="headless")
    scene.ffmpeg.h264(preset="slow", crf=16)
    scene.input(image=Path(img))
    scene.main(output=Path(out), time=DURATION, fps=FPS,
               width=WIDTH, height=HEIGHT, ssaa=float(ssaa))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shotlist", type=Path, required=True)
    ap.add_argument("--images", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ssaa", type=float, default=1.5)
    ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--worker", nargs=4, metavar=("TECNICA", "IMG", "OUT", "SSAA"),
                    help="uso interno: renderiza UN clip y termina")
    args = ap.parse_args()

    if args.worker:
        return worker(*args.worker)

    rows = load_shotlist(args.shotlist)
    if args.only:
        rows = [r for r in rows if r[0].startswith(args.only)]
    if not rows:
        print("No hay planos que renderizar.")
        return 1

    problems = validate(rows, args.images)
    for p in problems:
        print(f"  ! {p}")
    if problems:
        print(f"\n{len(problems)} problema(s). Corregilos antes de renderizar.")
        return 1
    print(f"Shotlist OK: {len(rows)} planos, sin técnicas repetidas consecutivas.")

    if args.dry_run:
        for sid, tech in rows:
            print(f"  {sid:12s} {tech}")
        return 0

    if not shutil.which("ffmpeg"):
        print("ERROR: ffmpeg no está en el PATH. DepthFlow lo necesita para encodear.")
        return 1

    import subprocess
    args.out.mkdir(parents=True, exist_ok=True)
    rendered = skipped = 0
    t0 = time.time()

    for i, (sid, tech) in enumerate(rows, 1):
        dst = args.out / f"MOV_{sid}.mp4"
        if dst.exists() and not args.force:
            print(f"[{i:>2}/{len(rows)}] {sid:12s} ya existe, salteado")
            skipped += 1
            continue

        ts = time.time()
        r = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()),
             "--shotlist", str(args.shotlist), "--images", str(args.images),
             "--out", str(args.out), "--worker", tech,
             str(args.images / f"IMG_{sid}.png"), str(dst), str(args.ssaa)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0 or not dst.exists():
            cola = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or ["sin detalle"]
            print(f"[{i:>2}/{len(rows)}] {sid:12s} FALLÓ — {cola[0][:70]}")
            continue
        print(f"[{i:>2}/{len(rows)}] {sid:12s} {tech:9s} -> {dst.name} ({time.time()-ts:.1f}s)")
        rendered += 1

    print(f"\nListo: {rendered} renderizados, {skipped} salteados, "
          f"{time.time()-t0:.0f}s totales.")
    print(f"Duración total generada: {rendered * DURATION:.0f} s de metraje.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
