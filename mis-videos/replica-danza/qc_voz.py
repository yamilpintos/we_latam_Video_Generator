"""QC de voz de clips Ref2VA: ¿dijo la línea? ¿suena como su referencia?

    /c/Python314/python -X utf8 mis-videos/replica-danza/qc_voz.py <proyecto.json> <carpeta_clips>

Sin oído, se mide (REGLAS 55): Whisper contra la línea pedida, F0 mediana con
pYIN, F1-F3 por LPC, y la distancia de cada clip a su voz de referencia en esos
tres números. Lo que se aleja más de ~25 % en F0 o ~12 % en F3 de su referencia
se marca para escuchar. Escribe qc-voz.json al lado de los clips.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import librosa
import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
FF = "C:/ffmpeg-2026-04-09-git-d3d0b7a5ee-essentials_build/bin/ffmpeg.exe"
WHISPER = RAIZ / ".venv-depthflow" / "Scripts" / "python.exe"


def medir(ruta):
    tmp = Path(ruta).with_suffix(".qc.wav")
    subprocess.run([FF, "-y", "-v", "error", "-i", str(ruta), "-ac", "1", "-ar", "11025", str(tmp)],
                   check=True)
    y, sr = librosa.load(tmp, sr=11025)
    tmp.unlink()
    f0, vf, vp = librosa.pyin(y, fmin=60, fmax=500, sr=sr, frame_length=512, hop_length=256)
    voz = vf & (vp > 0.5)
    fr = librosa.util.frame(y, frame_length=512, hop_length=256).T
    F = []
    for i in np.flatnonzero(voz[:len(fr)]):
        x = fr[i] * np.hamming(512)
        x = np.append(x[0], x[1:] - 0.97 * x[:-1])
        r = [z for z in np.roots(librosa.lpc(x, order=12)) if np.imag(z) > 0]
        fs = [f for f in sorted(np.angle(r) * sr / (2 * np.pi)) if f > 200]
        if len(fs) >= 3:
            F.append(fs[:3])
    f0v = f0[voz]
    return {"f0": float(np.median(f0v)) if len(f0v) else None,
            "F": [float(v) for v in np.median(np.array(F), axis=0)] if F else None,
            "n": int(voz.sum())}


def normal(t):
    return re.sub(r"[^a-z' ]", "", t.lower().replace("-", " ")).split()


def main():
    proyecto, carpeta = Path(sys.argv[1]), Path(sys.argv[2])
    g = json.loads(proyecto.read_text(encoding="utf-8"))
    assets = proyecto.parent / "assets"
    planos = [p for p in g["planos"] if p.get("voz_ref")]
    clips = {p["id"]: next(iter(sorted(carpeta.glob(p["id"] + "_*.mp4"))), None) for p in planos}
    hay = [p for p in planos if clips[p["id"]]]

    textos = {}
    if hay:
        lista = json.dumps([str(clips[p["id"]]) for p in hay])
        salida = subprocess.run(
            [str(WHISPER), "-X", "utf8", "-c",
             "import whisper, json, sys; m = whisper.load_model('medium'); "
             "print(json.dumps([m.transcribe(f, language='en')['text'] for f in json.loads(sys.argv[1])]))",
             lista], capture_output=True, text=True, encoding="utf-8",
            env={**__import__("os").environ,
                 "PATH": str(Path(FF).parent) + ";" + __import__("os").environ["PATH"]})
        ultima = [l for l in salida.stdout.splitlines() if l.startswith("[")]
        if not ultima:
            print(salida.stderr[-2000:])
            sys.exit(1)
        textos = dict(zip([p["id"] for p in hay], json.loads(ultima[-1])))

    refs, filas = {}, []
    for p in hay:
        v = p["voz_ref"]
        if v not in refs:
            refs[v] = medir(assets / v)
        m, r = medir(clips[p["id"]]), refs[v]
        pedida = p.get("dialogo") or re.search(r"<d>\[English\] (.*?)</d>", p.get("prompt_h3") or p["prompt"]).group(1)
        a, b = normal(pedida), normal(textos[p["id"]])
        faltan = [w for w in a if w not in b]
        sobran = [w for w in b if w not in a]
        df0 = (m["f0"] / r["f0"] - 1) if m["f0"] and r["f0"] else None
        dF3 = (m["F"][2] / r["F"][2] - 1) if m["F"] and r["F"] else None
        alertas = []
        if len(faltan) > 1 or len(sobran) > 2:
            alertas.append("texto")
        if df0 is None or abs(df0) > 0.25:
            alertas.append("f0")
        if dF3 is None or abs(dF3) > 0.12:
            alertas.append("timbre")
        fila = {"id": p["id"], "voz": v, "pedida": pedida, "dicho": textos[p["id"]].strip(),
                "faltan": faltan, "sobran": sobran,
                "f0": m["f0"] and round(m["f0"]), "f0_ref": r["f0"] and round(r["f0"]),
                "F": m["F"] and [round(x) for x in m["F"]], "F_ref": r["F"] and [round(x) for x in r["F"]],
                "alertas": alertas}
        filas.append(fila)
        print(f"{p['id']:6} {v:15} f0 {fila['f0']}/{fila['f0_ref']}  F3 "
              f"{fila['F'] and fila['F'][2]}/{fila['F_ref'] and fila['F_ref'][2]}  "
              f"{'OK' if not alertas else 'REVISAR ' + ','.join(alertas)}  «{fila['dicho']}»")
    faltantes = [p["id"] for p in planos if not clips[p["id"]]]
    if faltantes:
        print("sin clip:", " ".join(faltantes))
    (carpeta / "qc-voz.json").write_text(json.dumps(filas, ensure_ascii=False, indent=1),
                                         encoding="utf-8")


if __name__ == "__main__":
    main()
