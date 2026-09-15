"""
Genera las tomas de voz en ElevenLabs a partir de tools/timing.py y mide cada una
contra la duración prevista.

    python tools/tts_generate.py S01              # un bloque
    python tools/tts_generate.py S02 S03 S04      # varios
    python tools/tts_generate.py --all            # los nueve
    python tools/tts_generate.py --all --force    # regenerar lo ya existente

Escribe output/mars-climate-orbiter/voz/VO_<bloque>_T<n>.mp3 y un informe de desvíos.
Las tomas ya generadas se saltean salvo --force, así que se puede correr de a partes.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import timing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "mars-climate-orbiter" / "voz"
VOICE_ID = "NNyuU2PGU4uwmrHysPYW"  # Sandmor
MODEL = "eleven_v3"
FMT = "mp3_44100_128"
STABILITY = {"natural": 0.5, "numeros": 0.5, "creative": 0.0}
TOLERANCE = 0.4  # s por toma


def api_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("elevenlabs="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("No encontré la key en .env")


def mp3_seconds(data: bytes) -> float:
    """CBR 128 kbps: bytes * 8 / bitrate. Precisión ~0,05 s."""
    return len(data) * 8 / 128000


def synth(key: str, text: str, stability: float) -> bytes:
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format={FMT}",
        data=json.dumps({
            "text": text,
            "model_id": MODEL,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": 0.8,
                "use_speaker_boost": True,
            },
        }).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=240).read()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("blocks", nargs="*", help="IDs de bloque, ej. S01 S02")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    wanted = set(args.blocks)
    if args.all:
        wanted = {b[0] for b in timing.BLOCKS}
    if not wanted:
        ap.error("indicá bloques o --all")

    key = api_key()
    OUT.mkdir(parents=True, exist_ok=True)
    blocks, _, _ = timing.compute()

    print(f"voz: {timing.VOICE} | modelo: {MODEL}\n")
    grand_dev = grand_chars = 0
    problems = []

    for b in blocks:
        if b["id"] not in wanted:
            continue
        stab = STABILITY[b["mode"]]
        print(f"── {b['id']} · {b['dur']} s · stability {stab} "
              f"({'Creative' if stab == 0.0 else 'Natural'}) ──")
        block_dev = 0.0
        for i, (tc, text, words, pred) in enumerate(b["rows"], 1):
            dst = OUT / f"VO_{b['id']}_T{i}.mp3"
            if dst.exists() and not args.force:
                real = mp3_seconds(dst.read_bytes())
                mark = "="
            else:
                try:
                    audio = synth(key, text, stab)
                except Exception as e:
                    detail = getattr(e, "read", lambda: b"")()[:200].decode("utf-8", "replace")
                    print(f"  T{i}  FALLO: {e} {detail}")
                    problems.append(f"{b['id']}-T{i}: {e}")
                    continue
                dst.write_bytes(audio)
                real = mp3_seconds(audio)
                grand_chars += len(text)
                mark = " "
                time.sleep(0.3)
            dev = real - pred
            block_dev += dev
            flag = "  <-- fuera de tolerancia" if abs(dev) > TOLERANCE else ""
            if flag:
                problems.append(f"{b['id']}-T{i}: desvío {dev:+.1f} s ({words} pal)")
            print(f" {mark}T{i}  IN {tc}  prev {pred:5.1f}  real {real:5.1f}  "
                  f"desvío {dev:+5.1f}{flag}")
        grand_dev += block_dev
        verdict = "OK" if abs(block_dev) <= 1.5 else "REVISAR"
        print(f"    desvío acumulado del bloque: {block_dev:+.1f} s  [{verdict}]\n")

    print("=" * 62)
    print(f"Desvío acumulado total: {grand_dev:+.1f} s")
    print(f"Caracteres facturados en esta corrida: {grand_chars}")
    if problems:
        print(f"\n{len(problems)} punto(s) a revisar:")
        for p in problems:
            print(f"  · {p}")
    else:
        print("Todas las tomas dentro de tolerancia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
