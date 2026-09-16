"""Dos semillas por toma con diálogo, y la elección de la que mejor encaja.

    /c/Python314/python -X utf8 mis-videos/replica-danza/semillas.py armar    # → proyecto-alt.json
    /c/Python314/python -X utf8 mis-videos/replica-danza/semillas.py elegir   # tras bajar los clips

Pedido del 15/9 («que las voces encajen»): la causa de los desfases fue que H3
arrancó a hablar tarde en el clip (3-4 s) y la ventana de la toma se corrió
contra el techo. Cada toma con voz se genera dos veces (la normal, semilla
1000+idx del runner, y `T47a`, semilla 7000+idx) y `elegir` se queda con la que:
 1. dice la línea completa (Whisper),
 2. arranca antes de los 2,5 s del clip,
 3. dura lo más parecido posible al original.
La ganadora queda como T47_00001_.mp4; la otra va a clips/_alt/.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import tomas as T  # noqa: E402

CLIPS = AQUI / "clips"
RAIZ = AQUI.parents[1]
WHISPER = RAIZ / ".venv-depthflow" / "Scripts" / "python.exe"
FFBIN = "C:/ffmpeg-2026-04-09-git-d3d0b7a5ee-essentials_build/bin"


def armar():
    g = json.loads((AQUI / "proyecto.json").read_text(encoding="utf-8"))
    alt = []
    for i, p in enumerate(g["planos"]):
        if not p.get("voz_ref") or p.get("clip_de"):    # sólo las que hablan
            continue
        q = dict(p)
        q["id"] = p["id"] + "a"
        q["seed"] = 7000 + i
        q["dibujo"] = f"sb_{p['id']}.png"     # el mismo primer fotograma que la toma original
        q["funcion"] = "semilla alternativa de " + p["id"] + " · " + p.get("funcion", "")
        q.pop("clip_de", None)
        q.pop("texto", None)
        alt.append(q)
    total = round(sum(p["corta"] for p in alt), 2)
    doc = {**g, "titulo": "REPLICA DANZA · SEMILLAS ALT", "slug": "replica-danza-alt",
           "estructura": {"nombre": "alt", "formato": "short", "duracion_objetivo": total,
                          "tolerancia": 1, "plataformas": ["prueba"], "interrupcion_cada": 0,
                          "tramos": [{"id": "ALT", "nombre": "alt", "desde": 0, "hasta": total,
                                      "objetivo": "segunda semilla de cada diálogo",
                                      "corte_min": 0.3, "corte_max": 5.2, "planos_min": len(alt)}]},
           "planos": alt}
    (AQUI / "proyecto-alt.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"proyecto-alt.json · {len(alt)} tomas con voz, segunda semilla")


def palabras(mp4s):
    lista = json.dumps([str(m) for m in mp4s])
    r = subprocess.run([str(WHISPER), "-X", "utf8", "-c",
                        "import whisper, json, sys; m = whisper.load_model('medium'); "
                        "out = []\n"
                        "for f in json.loads(sys.argv[1]):\n"
                        "    r = m.transcribe(f, language='en', word_timestamps=True)\n"
                        "    out.append([(w['word'].strip(), round(w['start'], 2), round(w['end'], 2)) "
                        "for s in r['segments'] for w in s['words']])\n"
                        "print(json.dumps(out))", lista],
                       capture_output=True, text=True, encoding="utf-8",
                       env={**__import__("os").environ, "PATH": FFBIN + ";" + __import__("os").environ["PATH"]})
    filas = [l for l in r.stdout.splitlines() if l.startswith("[")]
    if not filas:
        raise SystemExit(r.stderr[-1500:])
    return json.loads(filas[-1])


def normal(t):
    return re.sub(r"[^a-z0-9' ]", "", t.lower().replace("-", " ")).split()


def puntaje(w, linea, dur_orig):
    """Menor es mejor. Sin palabras: muy malo. Palabras que faltan: malo.
    Después, arranque (penaliza > 2,5 s) y diferencia de duración con el original."""
    pedidas = normal(linea)
    dichas = [x for p in w for x in normal(p[0])]
    faltan = sum(1 for x in pedidas if x not in dichas)
    if not w:
        return 100.0, "sin voz"
    n = len(re.findall(r"[A-Za-z0-9']+", linea))
    ini, fin = w[0][1], w[min(n, len(w)) - 1][2]
    tarde = max(0.0, ini - 2.5)
    return (faltan * 10 + tarde * 4 + abs((fin - ini) - dur_orig)), f"ini {ini:.2f} dur {fin - ini:.2f} faltan {faltan}"


def elegir():
    (CLIPS / "_alt").mkdir(exist_ok=True)
    lineas = {}
    for (q, t0, t1, k, es, en) in T.LINEAS:
        if k:
            cid = "T" + next(t[0] for t in T.TOMAS if t[6] == k)
            lineas[cid] = (en, t1 - t0)
    pares = [(cid, CLIPS / f"{cid}_00001_.mp4", CLIPS / f"{cid}a_00001_.mp4") for cid in lineas
             if (CLIPS / f"{cid}a_00001_.mp4").exists() and (CLIPS / f"{cid}_00001_.mp4").exists()]
    if not pares:
        print("no hay pares para comparar")
        return
    ws = palabras([m for _c, a, b in pares for m in (a, b)])
    P = json.loads((CLIPS / "palabras.json").read_text(encoding="utf-8")) if (CLIPS / "palabras.json").exists() else {}
    for i, (cid, a, b) in enumerate(pares):
        en, dur = lineas[cid]
        wa, wb = ws[2 * i], ws[2 * i + 1]
        sa, da = puntaje(wa, en, dur)
        sb, db = puntaje(wb, en, dur)
        gana_b = sb < sa
        if gana_b:
            shutil.move(a, CLIPS / "_alt" / f"{cid}_orig_00001_.mp4")
            shutil.move(b, a)
            P[cid] = wb
        else:
            shutil.move(b, CLIPS / "_alt" / b.name)
            P[cid] = wa
        print(f"{cid:5} «{en[:30]:30}» A[{da}] B[{db}] → {'B' if gana_b else 'A'}")
    (CLIPS / "palabras.json").write_text(json.dumps(P, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    {"armar": armar, "elegir": elegir}[sys.argv[1]]()
