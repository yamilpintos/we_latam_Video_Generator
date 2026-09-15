"""
Genera la Capa E completa en ElevenLabs: ambientes, música y efectos puntuales.

    python tools/sfx_generate.py --amb      # 6 ambientes + drone base
    python tools/sfx_generate.py --mus      # 4 cues de música
    python tools/sfx_generate.py --spots    # 45 efectos puntuales
    python tools/sfx_generate.py --all
    python tools/sfx_generate.py --spots --force   # regenerar lo existente

Los ambientes se piden con loop=true y una duración corta; se repiten en bucle
al montar, así no hay que generar 70 segundos de room tone.
"""

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import sfx_plan  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "mars-climate-orbiter" / "audio"
LOOP_LEN = 22.0        # segundos de material de ambiente; se tilea al montar
MUS_CHUNK = 120.0      # trozo máximo de música por llamada


def api_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("elevenlabs="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("No encontré la key en .env")


def post(key: str, url: str, body: dict) -> bytes:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=420).read()


def sfx(key, text, secs, loop=False, influence=0.4) -> bytes:
    body = {"text": text, "duration_seconds": round(secs, 1),
            "prompt_influence": influence}
    if loop:
        body["loop"] = True
    return post(key, "https://api.elevenlabs.io/v1/sound-generation", body)


def music(key, prompt, ms) -> bytes:
    return post(key, "https://api.elevenlabs.io/v1/music",
                {"prompt": prompt, "music_length_ms": int(ms)})


def run(key, args):
    OUT.mkdir(parents=True, exist_ok=True)
    hechos = fallos = 0

    def escribir(nombre, data):
        nonlocal hechos
        (OUT / nombre).write_bytes(data)
        print(f"  OK  {nombre:26s} {len(data)/1024:7.0f} KB")
        hechos += 1

    if args.amb or args.all:
        print("── ambientes (loops de 22 s) ──")
        for aid, _i, _o, _db, prompt in [sfx_plan.DRONE] + sfx_plan.AMBIENTES:
            f = OUT / f"{aid}.mp3"
            if f.exists() and not args.force:
                print(f"  =   {aid}.mp3 ya existe"); continue
            try:
                escribir(f"{aid}.mp3", sfx(key, prompt, LOOP_LEN, loop=True, influence=0.5))
            except Exception as e:
                print(f"  X   {aid}: {e}"); fallos += 1
            time.sleep(0.4)

    if args.mus or args.all:
        print("\n── música ──")
        for mid, ini, out, _fi, _fo, _db, prompt in sfx_plan.MUSICA:
            f = OUT / f"{mid}.mp3"
            if f.exists() and not args.force:
                print(f"  =   {mid}.mp3 ya existe"); continue
            largo = min(out - ini, MUS_CHUNK)
            try:
                escribir(f"{mid}.mp3", music(key, prompt, largo * 1000))
            except Exception as e:
                det = getattr(e, "read", lambda: b"")()[:160].decode("utf-8", "replace")
                print(f"  X   {mid}: {e} {det}"); fallos += 1
            time.sleep(0.6)

    if args.spots or args.all:
        print("\n── efectos puntuales ──")
        for sid, _t, dur, _db, plano, prompt in sfx_plan.SPOTS:
            f = OUT / f"{sid}.mp3"
            if f.exists() and not args.force:
                print(f"  =   {sid}.mp3 ya existe"); continue
            try:
                escribir(f"{sid}.mp3", sfx(key, prompt, dur))
            except Exception as e:
                print(f"  X   {sid}: {e}"); fallos += 1
            time.sleep(0.3)

    print(f"\n{hechos} generados, {fallos} fallos")
    return 1 if fallos else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    for f in ("amb", "mus", "spots", "all", "force"):
        ap.add_argument(f"--{f}", action="store_true")
    args = ap.parse_args()
    if not (args.amb or args.mus or args.spots or args.all):
        ap.error("indicá --amb, --mus, --spots o --all")
    return run(api_key(), args)


if __name__ == "__main__":
    raise SystemExit(main())
