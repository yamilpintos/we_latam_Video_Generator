"""
Genera la voz por BLOQUE en una sola llamada y la corta en tomas usando los
timestamps por carácter que devuelve ElevenLabs.

Por qué por bloque y no por toma:
    eleven_v3 NO acepta previous_text / next_text — el API responde
    "not yet supported with the 'eleven_v3' model". Sin ese contexto, cada toma
    generada por separado arranca con un estado prosódico nuevo: empieza con otro
    tono y se acomoda a mitad de frase. Se oye como cambio de voz en cada corte.

    Generando el bloque entero de una sola vez la prosodia es continua de verdad
    —es una única interpretación— y los segmentos igual se colocan en su timecode.

Por qué por timestamps y no por silencios:
    Cortar por "los N-1 silencios más largos" falla: dentro de una toma con varias
    oraciones puede haber una pausa más larga que la del borde. Medido sobre los
    nueve bloques, 24 de 60 cortes caían mal.

    El endpoint /with-timestamps devuelve el tiempo de cada carácter, incluidos los
    saltos de línea que separan las tomas. El corte pasa a ser exacto.

    python tools/tts_block.py S01
    python tools/tts_block.py --all
"""

import argparse
import base64
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import timing  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "mars-climate-orbiter" / "voz"
VOICE_ID = "NNyuU2PGU4uwmrHysPYW"  # Sandmor
MODEL = "eleven_v3"
STABILITY = {"natural": 0.5, "numeros": 0.5, "creative": 0.0}
PAD = 0.06        # silencio que se deja a cada lado del segmento
SIL_RMS = 0.012


def api_key() -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("elevenlabs="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("No encontré la key en .env")


def synth(key: str, text: str, stability: float):
    """Devuelve (audio_bytes, caracteres, t_inicio, t_fin)."""
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
        f"/with-timestamps?output_format=mp3_44100_128",
        data=json.dumps({
            "text": text,
            "model_id": MODEL,
            "voice_settings": {"stability": stability, "similarity_boost": 0.8,
                               "use_speaker_boost": True},
        }).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json"},
    )
    d = json.load(urllib.request.urlopen(req, timeout=300))
    al = d.get("alignment") or d.get("normalized_alignment") or {}
    return (base64.b64decode(d["audio_base64"]),
            al.get("characters", []),
            al.get("character_start_times_seconds", []),
            al.get("character_end_times_seconds", []))


def cut_points(chars, t_ini, t_fin, n):
    """Tiempos de corte a partir de los n-1 separadores de párrafo."""
    seps, i = [], 0
    while i < len(chars) - 1:
        if chars[i] == "\n" and chars[i + 1] == "\n":
            j = i
            while j < len(chars) and chars[j] == "\n":
                j += 1
            seps.append((i, j))   # rango de caracteres del separador
            i = j
        else:
            i += 1
    if len(seps) != n - 1:
        return None, len(seps)
    # cortar a mitad de camino entre el fin del texto previo y el inicio del siguiente
    cuts = []
    for a, b in seps:
        antes = t_fin[a - 1] if a > 0 else 0.0
        despues = t_ini[b] if b < len(t_ini) else antes
        cuts.append((antes + despues) / 2)
    return cuts, len(seps)


def trim(seg: np.ndarray, sr: int) -> np.ndarray:
    win = int(sr * 0.01)
    if len(seg) < win * 2:
        return seg
    rms = np.sqrt((seg[: len(seg) // win * win].reshape(-1, win) ** 2).mean(axis=1))
    loud = np.where(rms >= SIL_RMS)[0]
    if not len(loud):
        return seg
    a = max(0, (loud[0] * win) - int(PAD * sr))
    b = min(len(seg), ((loud[-1] + 1) * win) + int(PAD * sr))
    return seg[a:b]


def single(key: str) -> int:
    """Genera el guion entero en una llamada y lo corta en las 60 tomas.

    Es la única forma de que no haya NINGÚN reinicio prosódico: hasta con una
    llamada por bloque quedan 8 empalmes, y se oyen. El guion son ~4.000
    caracteres y v3 admite 5.000, así que entra completo.

    Contrapartida: una llamada = un solo stability. S02 y S08 pierden Creative.
    """
    todas = [(bid, i + 1, t) for bid, _d, _m, tk in timing.BLOCKS
             for i, (_w, t) in enumerate(tk)]
    joined = "\n\n".join(t for _b, _i, t in todas)
    print(f"una sola generación · {len(todas)} tomas · {len(joined)} caracteres "
          f"(límite de v3: 5000)")
    if len(joined) > 5000:
        print("  no entra en una llamada; usá --all")
        return 1

    audio, chars, t_ini, t_fin = synth(key, joined, 0.5)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "GUION_COMPLETO.mp3").write_bytes(audio)

    x, sr = sf.read(io.BytesIO(audio), dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    print(f"  audio: {len(x)/sr:.1f} s continuos")

    cuts, found = cut_points(chars, t_ini, t_fin, len(todas))
    if cuts is None:
        print(f"  encontré {found} separadores y necesito {len(todas)-1}")
        return 1

    bounds = [0] + [int(c * sr) for c in cuts] + [len(x)]
    total_w = sum(timing.nwords(t) for _b, _i, t in todas)
    total_d = 0.0
    raros = []
    for k, (bid, ti, txt) in enumerate(todas):
        seg = trim(x[bounds[k]:bounds[k + 1]], sr)
        sf.write(OUT / f"VO_{bid}_T{ti}.wav", seg, sr)
        d = len(seg) / sr
        total_d += d
        esp = timing.nwords(txt) / total_w * (len(x) / sr)
        if esp and abs(d - esp) / esp > 0.45:
            raros.append(f"{bid}-T{ti}: {d:.1f}s vs {esp:.1f}s")
    print(f"  {len(todas)} tomas escritas · voz total {total_d:.1f} s")
    print(f"  cortes dudosos: {len(raros)}")
    for r in raros:
        print(f"    · {r}")
    print("  reinicios prosódicos: 0")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("blocks", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--single", action="store_true",
                    help="los 9 bloques en UNA sola generación: cero reinicios prosódicos")
    args = ap.parse_args()

    if args.single:
        return single(api_key())

    wanted = {b[0] for b in timing.BLOCKS} if args.all else set(args.blocks)
    if not wanted:
        ap.error("indicá bloques o --all")

    key = api_key()
    OUT.mkdir(parents=True, exist_ok=True)
    problems, chars_billed = [], 0

    for bid, dur, mode, takes in timing.BLOCKS:
        if bid not in wanted:
            continue
        texts = [t for _, t in takes]
        joined = "\n\n".join(texts)
        stab = STABILITY[mode]

        try:
            audio, chars, t_ini, t_fin = synth(key, joined, stab)
        except Exception as e:
            detail = getattr(e, "read", lambda: b"")()[:200].decode("utf-8", "replace")
            print(f"{bid}: FALLO {e} {detail}")
            problems.append(f"{bid}: {e}")
            continue
        chars_billed += len(joined)
        (OUT / f"BLOQUE_{bid}.mp3").write_bytes(audio)

        x, sr = sf.read(io.BytesIO(audio), dtype="float32", always_2d=True)
        x = x.mean(axis=1)

        cuts, found = cut_points(chars, t_ini, t_fin, len(texts))
        if cuts is None:
            print(f"{bid}: encontré {found} separadores y necesito {len(texts)-1}")
            problems.append(f"{bid}: separadores {found}/{len(texts)-1}")
            continue

        bounds = [0] + [int(c * sr) for c in cuts] + [len(x)]
        segs = [trim(x[bounds[k]:bounds[k + 1]], sr) for k in range(len(texts))]

        total_w = sum(timing.nwords(t) for t in texts)
        total_d = sum(len(s) / sr for s in segs)
        print(f"── {bid} · {len(x)/sr:.1f} s continuos · stability {stab} "
              f"({'Creative' if stab == 0 else 'Natural'}) ──")
        for i, (seg, txt) in enumerate(zip(segs, texts), 1):
            d = len(seg) / sr
            sf.write(OUT / f"VO_{bid}_T{i}.wav", seg, sr)
            esp = timing.nwords(txt) / total_w * total_d
            rel = (d - esp) / esp if esp else 0
            flag = "  <-- revisar" if abs(rel) > 0.45 else ""
            if flag:
                problems.append(f"{bid}-T{i}: {d:.1f}s vs {esp:.1f}s esperados")
            print(f"   T{i}  {d:5.2f} s  (esperado {esp:4.1f}){flag}")
        print(f"   suma {total_d:.1f} s en un slot de {dur} s "
              f"({total_d/dur*100:.0f} % de densidad)\n")
        time.sleep(0.4)

    print("=" * 60)
    print(f"Caracteres facturados: {chars_billed}")
    if problems:
        print(f"\n{len(problems)} a revisar:")
        for p in problems:
            print(f"  · {p}")
    else:
        print("Los nueve bloques cortados exactamente por timestamps.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
