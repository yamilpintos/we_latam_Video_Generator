"""
Montaje final: los 50 planos en orden de timeline + el mix de audio.

Cada plano se normaliza a 1920x1080 / 24 fps / yuv420p sin audio y se recorta a
su duración exacta de grilla (10 s los VEO, 5 s el resto). Recién con todos
idénticos se concatena por copia, que es lo único que garantiza que los cortes
caigan en el múltiplo de 5 s del timeline: reencodear en el concat reajusta los
PTS y el video se corre unos frames respecto de la voz.

    python tools/build_video.py
    python tools/build_video.py --rapido    # CRF 23, para revisar
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "output" / "mars-climate-orbiter"
FF = ROOT / ".venv-depthflow" / "Scripts" / "ffmpeg.exe"
TMP = BASE / "norm"
AUDIO = BASE / "audio" / "MIX_COMPLETO.wav"
FINAL = BASE / "MCO_5min.mp4"
W, H, FPS = 1920, 1080, 24

# Los 10 planos de Veo duran 10 s; los otros 40 duran 5 s.
VEO = {"S01-P01", "S01-P04", "S02-P05", "S03-P03", "S04-P05",
       "S05-P02", "S05-P04", "S06-P02", "S07-P03", "S09-P02"}

TIMELINE = [f"S{s:02d}-P{p:02d}" for s, n in
            ((1, 5), (2, 5), (3, 5), (4, 6), (5, 6), (6, 7), (7, 7), (8, 5), (9, 4))
            for p in range(1, n + 1)]


def origen(sid: str) -> Path | None:
    for carpeta, pref in (("veo", "VID"), ("mov", "MOV"), ("gfx", "GFX")):
        p = BASE / carpeta / f"{pref}_{sid}.mp4"
        if p.exists():
            return p
    return None


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print((r.stderr or "").strip()[-600:])
        raise SystemExit(f"ffmpeg falló: {' '.join(str(c) for c in cmd[:6])}…")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    args = ap.parse_args()
    crf = "23" if args.rapido else "17"
    preset = "veryfast" if args.rapido else "slow"

    faltan = [s for s in TIMELINE if origen(s) is None]
    if faltan:
        print(f"Faltan {len(faltan)} planos: {', '.join(faltan)}")
        return 1
    if not AUDIO.exists():
        print(f"Falta {AUDIO}")
        return 1

    TMP.mkdir(parents=True, exist_ok=True)
    total = 0.0
    for i, sid in enumerate(TIMELINE, 1):
        src, dur = origen(sid), 10.0 if sid in VEO else 5.0
        dst = TMP / f"{i:02d}_{sid}.mp4"
        # tpad rellena si el clip viene corto; -t recorta si viene largo. Los de
        # Veo llegan con 10,01 s y con audio: los dos se resuelven acá.
        run([FF, "-y", "-loglevel", "error", "-i", src,
             "-vf", f"scale={W}:{H}:flags=lanczos,fps={FPS},"
                    f"tpad=stop_mode=clone:stop_duration=1,format=yuv420p",
             "-t", f"{dur}", "-an", "-c:v", "libx264", "-preset", preset,
             "-crf", crf, "-x264-params", "keyint=48:min-keyint=48:scenecut=0",
             "-video_track_timescale", "12288", dst])
        total += dur
        print(f"[{i:>2}/50] {sid}  {src.parent.name}/{src.name:20s} -> {dur:.0f}s")

    lista = TMP / "concat.txt"
    lista.write_text("".join(f"file '{(TMP / f'{i:02d}_{s}.mp4').as_posix()}'\n"
                             for i, s in enumerate(TIMELINE, 1)), encoding="utf-8")

    print(f"\nConcatenando {len(TIMELINE)} planos ({total:.0f} s) y mezclando el audio…")
    run([FF, "-y", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", lista, "-i", AUDIO,
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
         "-movflags", "+faststart", "-shortest", FINAL])

    r = run([FF, "-i", FINAL, "-f", "null", "-"])
    linea = [l for l in (r.stderr or "").splitlines() if "time=" in l][-1:]
    print(f"\n{FINAL}")
    print(f"{FINAL.stat().st_size / 1e6:.1f} MB · {linea[0].strip() if linea else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
