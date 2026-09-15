"""
Arma la pista de voz completa: coloca cada toma en su timecode exacto sobre una
base de silencio y escribe un único WAV de la duración del video.

Sirve para dos cosas:
  1. Escuchar cómo suena realmente el bloque, con sus pausas. Las tomas sueltas
     duran 1-8 s y por separado no se entiende nada.
  2. Es el stem de voz definitivo: lo tirás al editor en 00:00 y ya está sincronizado.

    python tools/build_vo_track.py
    python tools/build_vo_track.py --only S06 --out solo_s06.wav

No necesita ffmpeg: decodifica con libsndfile vía soundfile.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import retime  # noqa: E402
import timing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
VOZ = ROOT / "output" / "mars-climate-orbiter" / "voz"
SR = 44100


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="un solo bloque, ej. S06")
    ap.add_argument("--out", default="VO_TRACK_completo.wav")
    ap.add_argument("--trim", type=float, default=0.0,
                    help="recorta N segundos de silencio al inicio de cada toma")
    args = ap.parse_args()

    blocks, total = retime.retime()
    if args.only:
        blocks = [b for b in blocks if b["id"] == args.only]
        if not blocks:
            print(f"No existe el bloque {args.only}")
            return 1

    t0 = blocks[0]["start"]
    t1 = blocks[-1]["start"] + blocks[-1]["dur"]
    track = np.zeros(int((t1 - t0) * SR), dtype=np.float32)

    placed = clipped = 0
    for b in blocks:
        for i, (ini, _fin, _text, _d) in enumerate(b["rows"], 1):
            f = retime.take_file(b["id"], i)
            if f is None:
                print(f"  falta VO_{b['id']}_T{i}")
                continue
            x, sr = sf.read(f, dtype="float32", always_2d=True)
            x = x.mean(axis=1)
            if sr != SR:
                idx = np.linspace(0, len(x) - 1, int(len(x) * SR / sr))
                x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
            if args.trim > 0:
                x = x[int(args.trim * SR):]
            start = int((ini - t0) * SR)
            end = start + len(x)
            if end > len(track):
                x = x[: len(track) - start]
                clipped += 1
            track[start:start + len(x)] += x
            placed += 1

    peak = float(np.abs(track).max())
    if peak > 0.99:
        track *= 0.99 / peak
        print(f"  normalizado: el pico era {peak:.2f}")

    out = VOZ / args.out
    sf.write(out, track, SR)

    dur = len(track) / SR
    win = int(SR * 0.02)
    fr = track[: len(track) // win * win].reshape(-1, win)
    audible = float((np.sqrt((fr ** 2).mean(axis=1)) > 0.01).mean())

    print(f"\n{out}")
    print(f"  duración   {dur:.1f} s ({int(dur)//60}:{dur % 60:04.1f})")
    print(f"  tomas      {placed} colocadas" + (f", {clipped} recortadas al final" if clipped else ""))
    print(f"  pico       {float(np.abs(track).max()):.3f}")
    print(f"  voz        {audible*100:.0f} % del tiempo · silencio {(1-audible)*100:.0f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
