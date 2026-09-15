"""Mide las tomas de casting de voz para elegir, con números, la voz de cada personaje.

    /c/Python314/python -X utf8 mis-videos/replica-danza/casting.py <carpeta_clips>

El usuario delegó la elección («que mantengan los personajes y los géneros»), y
elegir a oído no es posible desde acá, así que se mide lo que importa:

1. **¿Dijo la frase?** Whisper (medium, tiempos por palabra) contra la frase
   pedida: palabras de más = balbuceo (issue #16155), de menos = cortó.
2. **¿Es del género del personaje?** Frecuencia fundamental mediana de los
   tramos con voz (autocorrelación): hombre ~85-180 Hz, mujer ~165-255 Hz.
3. **¿Arranca donde se pidió?** Primer instante con habla (el prompt pide ~1 s de
   silencio): define la ventana limpia para recortar la referencia.
4. **¿Está limpia?** Relación entre el nivel del habla y el del resto.

Escribe `casting.json` con todo y la sugerencia por personaje, y los recortes
candidatos de voz (`voz_<quien>_<clip>.wav`) listos para `assets/`.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ))
from h3pipeline import config, voz_ref  # noqa: E402

GENERO = {"jack": "m", "luka": "m", "wady": "m", "hannah": "f"}
RANGO = {"m": (85, 180), "f": (165, 255)}
WHISPER = RAIZ / ".venv-depthflow" / "Scripts" / "python.exe"


def f0_mediana(wav, sr):
    """F0 por autocorrelación en ventanas de 40 ms con energía alta."""
    x = wav.mean(axis=1) if wav.ndim > 1 else wav
    n = int(0.04 * sr)
    energias = [np.sqrt(np.mean(x[i:i + n] ** 2)) for i in range(0, len(x) - n, n)]
    umbral = np.percentile(energias, 70)
    f0s = []
    for k, i in enumerate(range(0, len(x) - n, n)):
        if energias[k] < umbral:
            continue
        seg = x[i:i + n] - np.mean(x[i:i + n])
        ac = np.correlate(seg, seg, "full")[n - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        if hi >= len(ac):
            continue
        pico = lo + int(np.argmax(ac[lo:hi]))
        if ac[pico] > 0.3 * ac[0]:
            f0s.append(sr / pico)
    return float(np.median(f0s)) if f0s else None


def palabras(texto):
    return re.findall(r"[a-z']+", texto.lower())


def main():
    clips = Path(sys.argv[1])
    doc = json.loads((AQUI / "muestra-A.json").read_text(encoding="utf-8"))
    casting = [p for p in doc["planos"] if "CASTING" in p["funcion"]]
    tmp = AQUI / "casting"
    tmp.mkdir(exist_ok=True)
    resultados = []
    for p in casting:
        m = re.search(r"CASTING (\w+) semilla (\d+): «(.+)»", p["funcion"])
        quien, semilla, frase = m.group(1), int(m.group(2)), m.group(3)
        mp4 = next(iter(sorted(clips.glob(p["id"] + "_*.mp4"))), None)
        if not mp4:
            print(f"falta el clip de {p['id']}")
            continue
        wav = tmp / f"{p['id']}.wav"
        subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4),
                        "-vn", "-ac", "2", "-ar", "32000", str(wav)], check=True)
        datos, sr = sf.read(str(wav))
        # Whisper en el venv que lo tiene (DepthFlow), a archivo.
        out = tmp / f"{p['id']}.json"
        subprocess.run([str(WHISPER), "-X", "utf8", "-c", (
            "import whisper, json, sys; m = whisper.load_model('medium'); "
            f"r = m.transcribe(r'{wav}', language='en', word_timestamps=True, fp16=False); "
            f"json.dump(r, open(r'{out}', 'w', encoding='utf-8'))")], check=True)
        r = json.loads(out.read_text(encoding="utf-8"))
        ws = [w for s in r["segments"] for w in s.get("words", [])]
        dicho = " ".join(w["word"].strip() for w in ws)
        pedidas, oidas = palabras(frase), palabras(dicho)
        extra = max(0, len(oidas) - len(pedidas))
        faltan = len([w for w in pedidas if w not in oidas])
        ini = ws[0]["start"] if ws else None
        fin = ws[-1]["end"] if ws else None
        f0 = f0_mediana(datos, sr)
        lo, hi = RANGO[GENERO[quien]]
        genero_ok = f0 is not None and lo <= f0 <= hi
        x = datos.mean(axis=1)
        habla = x[int((ini or 0) * sr):int((fin or 0) * sr)] if ini is not None else x[:1]
        resto = np.concatenate([x[:int((ini or 0) * sr)], x[int((fin or 0) * sr):]])
        snr = (20 * np.log10((np.sqrt(np.mean(habla ** 2)) + 1e-9) / (np.sqrt(np.mean(resto ** 2)) + 1e-9))
               if len(resto) else None)
        puntaje = (100 - 25 * extra - 20 * faltan - (0 if genero_ok else 60)
                   - (10 * abs((ini or 3) - 1.0)) + (min(snr, 30) if snr else 0) / 3)
        res = {"id": p["id"], "quien": quien, "semilla": semilla, "frase": frase, "dicho": dicho,
               "palabras_de_mas": extra, "palabras_que_faltan": faltan, "habla_ini": ini,
               "habla_fin": fin, "f0_hz": round(f0, 1) if f0 else None, "genero_ok": genero_ok,
               "snr_db": round(float(snr), 1) if snr is not None else None,
               "puntaje": round(float(puntaje), 1), "clip": mp4.name}
        # Recorte candidato: la frase entera con 0,15 s de aire, dentro de 2-15 s.
        if ini is not None and fin is not None:
            a, b = max(0.0, ini - 0.15), min(len(x) / sr, fin + 0.15)
            if b - a < 2.0:
                b = min(len(x) / sr, a + 2.0)
                a = max(0.0, b - 2.0)
            cand = tmp / f"voz_{quien}_{p['id']}.wav"
            res["recorte"] = [round(a, 2), round(b, 2)]
            res["segundos_ref"] = round(voz_ref.recortar(mp4, a, b, cand), 3)
            res["archivo_ref"] = cand.name
        resultados.append(res)
        print(json.dumps(res, ensure_ascii=False))

    sugerida = {}
    for quien in GENERO:
        cands = [x for x in resultados if x["quien"] == quien and x.get("archivo_ref")]
        if cands:
            mejor = max(cands, key=lambda x: x["puntaje"])
            sugerida[quien] = {"id": mejor["id"], "archivo": mejor["archivo_ref"],
                               "puntaje": mejor["puntaje"], "f0_hz": mejor["f0_hz"],
                               "dicho": mejor["dicho"]}
    (AQUI / "casting.json").write_text(json.dumps({"tomas": resultados, "sugerida": sugerida},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nSUGERIDA:", json.dumps(sugerida, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
