"""
Recalcula los IN de cada toma usando la duración REAL de los MP3 generados,
en vez de la estimación por conteo de palabras.

Este es el paso que cierra la sincronía. El modelo de palabras sirve para
escribir el guion; una vez que el audio existe, manda el audio.

    python tools/retime.py            # informe + tabla markdown
    python tools/retime.py --check    # solo la verificación
    python tools/retime.py --out FILE

Detecta dos fallas que el modelo no puede prever:
  · SOLAPE  — una toma pisa la siguiente
  · DESBORDE — la voz de un bloque no entra en su duración
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import timing  # noqa: E402

VOZ = Path(__file__).resolve().parent.parent / "output" / "mars-climate-orbiter" / "voz"


def take_file(bid, i):
    """WAV primero (bloque continuo cortado), MP3 como respaldo."""
    for ext in ("wav", "mp3"):
        p = VOZ / f"VO_{bid}_T{i}.{ext}"
        if p.exists():
            return p
    return None


MIN_GAP = 0.35        # silencio mínimo entre tomas contiguas
MAX_GAP = 1.10        # tope de una pausa normal
MAX_GAP_BEAT = 1.60   # tope de una pausa dramática (peso >= 3)
# La cola de un bloque y la entrada del siguiente son el MISMO silencio continuo:
# el oyente escucha la suma, no dos huecos. Por eso comparten un presupuesto único.
MAX_BOUNDARY = 1.50   # silencio total audible en un cambio de secuencia
MAX_TAIL = 1.00       # de ese presupuesto, lo que va antes del corte
MAX_LEAD = MAX_BOUNDARY - MAX_TAIL   # y lo que va después
W_LEAD = 0.5          # peso de la entrada en el reparto
W_TAIL = 1.5          # peso de la cola


def waterfill(slack: float, weights: list[float], caps: list[float]) -> list[float]:
    """Reparte `slack` en proporción a `weights` sin que ninguno pase su tope.

    Repartir proporcionalmente a secas es lo que rompía el montaje: si la voz sale
    más corta de lo previsto, el sobrante crece y TODOS los silencios crecen con
    él. Acá lo que rebasa un tope se devuelve al resto, que todavía tiene lugar.

    Devuelve la lista de silencios. Si ni con todos los topes al máximo entra el
    sobrante, la suma queda corta: eso significa que al bloque le falta TEXTO,
    y quien llama lo reporta.
    """
    out = [0.0] * len(weights)
    libres = set(range(len(weights)))
    resto = slack
    for _ in range(len(weights) + 1):
        wsum = sum(weights[i] for i in libres)
        if resto <= 1e-6 or not libres or wsum <= 0:
            break
        unidad = resto / wsum
        topados = [i for i in libres if weights[i] * unidad > caps[i]]
        if not topados:
            for i in libres:
                out[i] = weights[i] * unidad
            resto = 0.0
            break
        for i in topados:
            out[i] = caps[i]
            resto -= caps[i]
            libres.discard(i)
    return out


def gap_cap(peso: float, dur_anterior: float) -> float:
    """Tope de un silencio. Hacen falta las dos reglas.

    1. Tope absoluto. Sin él el reparto proporcional se desmadra: cuando la voz
       sale más corta de lo previsto el sobrante crece y TODAS las pausas crecen
       con él. Así apareció un silencio de 2,50 s en S02.

    2. Proporcional a la frase anterior. Una pausa más larga que lo que se acaba
       de decir suena a error de montaje, no a énfasis: después de una frase de
       1,4 s, 2,5 s de silencio se leen como que algo se colgó.

    El sobrante que no entra queda como cola al final del bloque, que cae sobre un
    corte de secuencia y no se nota. Si la cola pasa MAX_TAIL, ese bloque necesita
    más texto — no más silencio.
    """
    absoluto = MAX_GAP_BEAT if peso >= 3 else MAX_GAP
    return min(absoluto, max(0.70, dur_anterior))


def real_seconds(path: Path) -> float:
    """Duración real. Decodifica el audio si hay soundfile; si no, estima por
    tamaño asumiendo CBR 128 kbps (sobreestima ~1,6 % por las cabeceras ID3)."""
    try:
        import soundfile as sf
        info = sf.info(path)
        return info.frames / info.samplerate
    except Exception:
        return path.stat().st_size * 8 / 128000


def retime():
    cursor = 0.0
    blocks = []
    for bid, dur, mode, takes in timing.BLOCKS:
        durs, missing = [], []
        for i, (_, text) in enumerate(takes, 1):
            f = take_file(bid, i)
            if f is not None:
                durs.append(real_seconds(f))
            else:
                durs.append(timing.nwords(text) / timing.RATES[mode])
                missing.append(i)

        voice = sum(durs)
        slack = dur - voice

        # Los silencios del bloque: entrada, un hueco antes de cada toma menos la
        # primera, y cola. Todos compiten por el mismo sobrante, todos con tope.
        pesos = [W_LEAD] + [w for w, _ in takes[1:]] + [W_TAIL]
        topes = ([MAX_LEAD]
                 + [gap_cap(w, durs[i]) for i, (w, _) in enumerate(takes[1:])]
                 + [MAX_TAIL])
        huecos = waterfill(max(slack, 0.0), pesos, topes)
        sin_ubicar = max(slack, 0.0) - sum(huecos)

        rows, t = [], cursor + huecos[0]
        for k, ((w, text), d) in enumerate(zip(takes, durs)):
            if rows:
                t = max(t + huecos[k], rows[-1][1] + MIN_GAP)
            rows.append((t, t + d, text, d))
            t += d

        overflow = rows[-1][1] - (cursor + dur) if rows else 0.0
        tail = -overflow
        blocks.append({"id": bid, "dur": dur, "mode": mode, "start": cursor,
                       "rows": rows, "voice": voice, "slack": slack,
                       "overflow": overflow, "tail": tail, "lead": huecos[0],
                       "sin_ubicar": sin_ubicar, "missing": missing})
        cursor += dur
    return blocks, cursor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.out:
        sys.stdout = open(args.out, "w", encoding="utf-8")

    blocks, total = retime()
    problems, voice_total = [], 0.0

    for b in blocks:
        if b["missing"]:
            problems.append(f"{b['id']}: faltan MP3 de las tomas {b['missing']} (usé estimación)")
        if b["overflow"] > 0.05:
            problems.append(f"{b['id']}: DESBORDE de {b['overflow']:.1f} s — hay que acortar texto")
        if b["sin_ubicar"] > 0.35:
            problems.append(f"{b['id']}: sobran {b['sin_ubicar']:.1f} s que no entran en "
                            f"ningún silencio — le faltan ~{int(b['sin_ubicar'] * 2.57)} "
                            f"palabras al bloque (no más pausa)")
        voice_total += b["voice"]

        if not args.check:
            stab = "0.0 Creative" if b["mode"] == "creative" else "0.5 Natural"
            print(f"\n### BLOQUE {b['id']} · {b['dur']} s · stability {stab}\n")
            print("| Toma | IN | Archivo | Dur. real | Texto |")
            print("|---|---|---|---|---|")
            for i, (ini, fin, text, d) in enumerate(b["rows"], 1):
                print(f"| T{i} | {timing.tc(ini)} | `{take_file(b['id'], i).name}` "
                      f"| {d:.1f} s | {text} |")
            print(f"\n**Voz {b['voice']:.1f} s / {b['dur']} s = "
                  f"{b['voice']/b['dur']*100:.0f} %** · "
                  f"cola de silencio {-b['overflow']:.1f} s")

    print("\n" + "=" * 62)
    print(f"Tomas: {sum(len(b['rows']) for b in blocks)} · duración total {total:.0f} s")
    print(f"Voz real: {voice_total:.1f} s = {voice_total/total*100:.1f} %")
    print(f"Silencio: {total - voice_total:.1f} s")
    gaps = [b["rows"][i][0] - b["rows"][i-1][1]
            for b in blocks for i in range(1, len(b["rows"]))]
    print(f"Huecos entre tomas: mín {min(gaps):.2f} s · máx {max(gaps):.2f} s")
    print(f"Solapes: {sum(1 for g in gaps if g < -0.001)}")
    print(f"Desbordes: {sum(1 for b in blocks if b['overflow'] > 0.05)}")
    if problems:
        print("\nA revisar:")
        for p in problems:
            print(f"  · {p}")
    else:
        print("\nSin solapes ni desbordes. Sincronía cerrada.")


if __name__ == "__main__":
    main()
