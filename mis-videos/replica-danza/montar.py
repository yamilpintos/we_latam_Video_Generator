"""Montaje final de la réplica: imagen de los 81 clips + voces de H3 + ambiente del
original + subtítulos en castellano + placas de nombre.

    /c/Python314/python -X utf8 mis-videos/replica-danza/montar.py medir   # arranques → armar.py
    /c/Python314/python -X utf8 mis-videos/replica-danza/montar.py         # el MP4

`medir` escribe en armar.py el arranque real de la voz de cada encuadre que habla
(ONSETS_MEDIDOS) y hay que volver a correr `armar.py` para que los `usa` se
recalculen. H3 no arranca donde se le pide: T47 habló a los 3,2 s, T54 a los 3,2.

La voz de cada línea se saca del MISMO clip cuya boca se ve y con la misma
correspondencia de tiempos que la imagen (clip = arranque + (t − t0)), así que
queda en sincronía por construcción. La narración en off sale de VO01-VO08,
tramos pegados uno detrás de otro desde el t0 de cada línea.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ))
import tomas as T  # noqa: E402
from h3pipeline import montaje  # noqa: E402

FF = "C:/ffmpeg-2026-04-09-git-d3d0b7a5ee-essentials_build/bin/ffmpeg.exe"
CLIPS = AQUI / "clips"
FINAL = AQUI / "final"
TMP = FINAL / "_tmp"
SR = 48000
LARGO_CLIP = 5.167

# La narración: qué tramos forman cada línea en off y qué pausa va ANTES de cada
# uno (coma: corta; punto: larga).
# Líneas que NO se mezclan aunque el clip las traiga. 16/9: el «Ah!» final salió
# como gemido; queda la cara de susto con la patada y los disparos del ambiente.
SIN_VOZ = {"E81"}
# Tomas mudas cuyo AUDIO de H3 sí se mezcla, como efecto (16/9: el grito de la
# pasajera en T34; el original lo tenía y demucs se lo llevó con las voces).
SFX_DE_CLIP = set()   # 16/9: el ambiente ya trae el residuo del grito original; sumar el de H3 daba dos gritos
# Efectos tomados de un archivo (ruta, desde, hasta) y puestos al inicio de la toma.
# 16/9: el grito que generó H3 para T34 sonaba «acapanaaa»; va el grito de la
# pasajera del ORIGINAL (vocals.wav de demucs, 56,7-58,3 s). Es un efecto, no
# una línea de personaje.
SFX_ARCHIVO = {"T34": (AQUI / "audio-original" / "vocals.wav", 56.7, 58.3)}   # refuerza el mismo grito que ya está en el ambiente
# Cirugía manual de una línea: tramos del clip (en segundos) que se pegan con
# 0,35 s de pausa entre ellos. 16/9: T73 dijo «I said, I said … moan» en las
# tres semillas; se queda el primer «I said» y el «moan».
SEGMENTOS = {}   # (v4: los tramos manuales de E73 eran del clip viejo; se quitan)


def sin_repeticiones(cid, a, b):
    """Si Whisper ve la misma secuencia de ≥ 2 palabras dos veces seguidas dentro
    de [a, b] (16/9 v4, T64: «of our best men of our best men»), devuelve los
    tramos a conservar, saltando la segunda repetición. Si no hay, None."""
    w = [x for x in PALABRAS.get(cid, []) if a - 0.05 <= x[1] and x[2] <= b + 0.05]
    tok = [re.sub(r"[^a-z0-9']", "", x[0].lower()) for x in w]
    for n in range(4, 1, -1):
        for i in range(len(tok) - 2 * n + 1):
            if tok[i:i + n] == tok[i + n:i + 2 * n] and all(tok[i:i + n]):
                d0, d1 = w[i + n][1], w[i + 2 * n - 1][2]
                print(f"        ({cid}: repetición «{' '.join(tok[i:i + n])}» {d0:.2f}-{d1:.2f} quitada)")
                return [(a, d0 - 0.02), (d1 + 0.02, b)]
    return None

VO = {2.14: [("VO01", 0.0), ("VO02", 0.22)],
      11.32: [("VO03", 0.0), ("VO04", 0.15), ("VO05", 0.45), ("VO06", 0.15)],
      24.3: [("VO07", 0.0), ("VO08", 0.40)]}


def ff(*a, cwd=None):
    r = subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *a],
                       capture_output=True, text=True, cwd=cwd)
    if r.returncode:
        raise SystemExit("ffmpeg: " + r.stderr[-1500:])


def cuadros(mp4):
    r = subprocess.run([FF.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-count_frames",
                        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                        "-of", "csv=p=0", str(mp4)], capture_output=True, text=True)
    return int(r.stdout.strip() or 0)


def clip(cid):
    return CLIPS / f"{cid}_00001_.mp4"


def audio(cid):
    """El audio del clip, estéreo 48 kHz, cacheado."""
    TMP.mkdir(parents=True, exist_ok=True)
    w = TMP / f"{cid}.wav"
    # 16/9: el WAV cacheado sobrevivía al clip regenerado y el grito de T34 (y
    # las voces rehechas) salían del clip VIEJO. Se rehace si el clip es más nuevo.
    if not w.exists() or w.stat().st_mtime < clip(cid).stat().st_mtime:
        ff("-i", str(clip(cid)), "-vn", "-ac", "2", "-ar", str(SR), str(w))
    return w


def energia(cid):
    """dB en la banda de voz (250-4000 Hz) cada 10 ms."""
    y, sr = librosa.load(audio(cid), sr=16000, mono=True)
    S = np.abs(librosa.stft(y, n_fft=512, hop_length=160))
    f = librosa.fft_frequencies(sr=sr, n_fft=512)
    e = 20 * np.log10(S[(f > 250) & (f < 4000)].mean(axis=0) + 1e-9)
    return e, 0.01


def tramos_de_voz(cid, desde=0.0, hasta=LARGO_CLIP):
    """[(ini, fin)] de habla por energía: 18 dB sobre el piso, ≥ 60 ms."""
    e, paso = energia(cid)
    piso = np.percentile(e, 20)
    on = e > piso + 18
    out, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            if j - i >= 6:
                a, b = i * paso, j * paso
                if b > desde and a < hasta:
                    out.append((round(a, 2), round(b, 2)))
            i = j
        else:
            i += 1
    # une huecos menores a 250 ms (entre palabras)
    unidos = []
    for a, b in out:
        if unidos and a - unidos[-1][1] < 0.25:
            unidos[-1] = (unidos[-1][0], b)
        else:
            unidos.append((a, b))
    return unidos


PALABRAS = json.loads((CLIPS / "palabras.json").read_text(encoding="utf-8"))


def limites(cid, linea):
    """(arranque, fin) de la línea pedida dentro del clip. El fin sale de la
    N-ésima palabra de Whisper (N = palabras de la línea), para no llevarse el
    balbuceo que a veces sigue (T53, T55); el arranque, de la energía, porque
    Whisper pone 0,0 a la primera palabra cuando hay silencio antes."""
    n = len(re.findall(r"[A-Za-z0-9']+", linea))
    w = PALABRAS.get(cid) or []
    tr = tramos_de_voz(cid)
    if not tr:
        # Con disparos o tren fuerte el piso sube y la energía no separa nada
        # (T30, 16/9): manda Whisper solo.
        if not w:
            raise SystemExit(f"{cid}: no encuentro voz")
        return round(w[0][1], 2), round(w[min(n, len(w)) - 1][2], 2)
    if w:
        fin_palabra = w[min(n, len(w)) - 1][2]
        primera_fin = w[0][2]
        cand = [a for a, b in tr if a <= primera_fin + 0.05] or [tr[0][0]]
        ini = cand[-1] if len(cand) > 1 and w[0][1] > 0.3 else cand[0]
        # que el arranque no quede antes de un tramo que termina lejos de la palabra
        ini = max([a for a, b in tr if a <= w[0][1] + 0.05] or [ini]) if w[0][1] > 0.3 else ini
        # Con el tren fuerte en la banda de voz, el tramo de energía puede arrancar
        # en 0 y llevarse el clip entero (15/9: «What?» dio 0,28-4,99 y tapaba las
        # dos líneas siguientes). El arranque nunca va más de 0,4 s antes de la
        # primera palabra de Whisper.
        if w[0][1] > 0.3:
            ini = max(ini, w[0][1] - 0.4)
        fin = max(fin_palabra, min(max([b for a, b in tr if a < fin_palabra] or [fin_palabra]),
                                   fin_palabra + 0.3))
    else:                                   # «Shh»: sin palabras, el tramo más fuerte
        e, paso = energia(cid)
        a, b = max(tr, key=lambda ab: e[int(ab[0] / paso):int(ab[1] / paso)].max())
        ini, fin = a, b
    return round(ini, 2), round(fin, 2)


def boca(k):
    return "T" + next(t[0] for t in T.TOMAS if t[6] == k)


def medir():
    medidos = {}
    for (quien, t0, t1, k, es, en) in T.LINEAS:
        if not k:
            continue
        cid = boca(k)
        ini, fin = limites(cid, en)
        medidos[k] = ini
        print(f"{k:5} {cid:5} «{en}» voz {ini:.2f}-{fin:.2f} (original {t1 - t0:.2f} s)")
    ar = AQUI / "armar.py"
    s = ar.read_text(encoding="utf-8")
    nuevo = "ONSETS_MEDIDOS = " + json.dumps(medidos) + "   # medido con montar.py medir"
    s = re.sub(r"^ONSETS_MEDIDOS = .*$", nuevo, s, count=1, flags=re.M)
    ar.write_text(s, encoding="utf-8")
    print(f"\n{len(medidos)} arranques escritos en armar.py — correr armar.py")


def pieza(cid, a, b, destino, fade=0.03):
    x, sr = sf.read(audio(cid), dtype="float32")
    a, b = max(0.0, a), min(len(x) / sr, b)
    y = x[int(a * sr):int(b * sr)].copy()
    nf = int(fade * sr)
    if len(y) > 2 * nf:
        rampa = np.linspace(0, 1, nf)[:, None]
        y[:nf] *= rampa
        y[-nf:] *= rampa[::-1]
    sf.write(destino, y, sr)
    return len(y) / sr


def pieza_compacta(cid, a, b, destino, pausa=0.35, hueco=0.9):
    """Como `pieza`, pero si entre dos palabras de Whisper hay más de `hueco` s de
    silencio, lo acorta a `pausa` s (con el propio silencio del clip). 16/9: T73
    dijo «I said … moan» con 1,6 s de pausa, y el tope de duración del montaje
    se llevaba el «moan». La boca queda cerrada en la pausa, así que acortarla
    no desincroniza nada visible. Devuelve la duración."""
    w = [x for x in PALABRAS.get(cid, []) if a - 0.05 <= x[1] and x[2] <= b + 0.05]
    huecos = [(w[i][2], w[i + 1][1]) for i in range(len(w) - 1) if w[i + 1][1] - w[i][2] > hueco]
    if not huecos:
        return pieza(cid, a, b, destino)
    x, sr = sf.read(audio(cid), dtype="float32")
    trozos, cur = [], a
    for h0, h1 in huecos:
        trozos.append(x[int(cur * sr):int((h0 + 0.08) * sr)])
        trozos.append(x[int((h0 + 0.08) * sr):int((h0 + 0.08 + pausa) * sr)])   # silencio del clip
        cur = h1 - 0.08
    trozos.append(x[int(cur * sr):int(b * sr)])
    y = np.concatenate(trozos)
    nf = int(0.03 * sr)
    rampa = np.linspace(0, 1, nf)[:, None]
    y[:nf] *= rampa
    y[-nf:] *= rampa[::-1]
    sf.write(destino, y, sr)
    print(f"        ({cid}: {len(huecos)} pausa(s) larga(s) acortada(s) a {pausa} s)")
    return len(y) / sr


def voces():
    """[(segundo, wav)] de todas las líneas, y los tiempos reales para el SRT."""
    TMP.mkdir(parents=True, exist_ok=True)
    g = json.loads((AQUI / "proyecto.json").read_text(encoding="utf-8"))
    planos = {p["id"]: p for p in g["planos"]}
    inicio, t = {}, 0.0
    for p in g["planos"]:
        inicio[p["id"]] = t
        t += p["usa"][1] - p["usa"][0]
    out, subs = [], []
    for cid in SFX_DE_CLIP:
        p = planos[cid]
        a, b = p["usa"]
        wav = TMP / f"sfx_{cid}.wav"
        pieza(cid, a, b + 0.6, wav)      # el grito de T34 dura hasta ~1,55 s: «Oh! No!»
        out.append((round(inicio[cid], 3), wav))
        print(f"  sfx   {cid:5} clip {a:.2f}-{b + 0.3:.2f} → {inicio[cid]:6.2f}")
    for cid, (ruta, s0, s1) in SFX_ARCHIVO.items():
        x, sr = sf.read(ruta, dtype="float32")
        y = x[int(s0 * sr):int(s1 * sr)].copy()
        if y.ndim == 1:
            y = np.stack([y, y], axis=1)
        nf = int(0.03 * sr)
        rampa = np.linspace(0, 1, nf)[:, None]
        y[:nf] *= rampa
        y[-nf:] *= rampa[::-1]
        wav = TMP / f"sfx_{cid}.wav"
        sf.write(wav, y, sr)
        out.append((round(s0, 3), wav))
        print(f"  sfx   {cid:5} {ruta.name} {s0:.2f}-{s1:.2f} → {s0:6.2f} (misma línea de tiempo que el original)")
    lineas = sorted(T.LINEAS, key=lambda l: l[1])
    for n, (quien, t0, t1, k, es, en) in enumerate(lineas):
        sig = lineas[n + 1][1] if n + 1 < len(lineas) else 999
        if t0 in VO:
            # La narración en inglés es más larga que la doblada: si no entra hasta
            # la línea siguiente, arranca hasta 0,8 s antes (sin pisar la anterior)
            # y, si igual no entra, se acelera hasta 12 % con atempo.
            trozos = []
            for cid, pausa in VO[t0]:
                w = PALABRAS[cid]
                tr = tramos_de_voz(cid)
                ini = min(a for a, b in tr) if tr else 0.0
                fin = min(w[-1][2] + 0.15, LARGO_CLIP)
                trozos.append((cid, pausa, ini - 0.06, fin))
            total = sum(p_ + (f_ - i_) for _c, p_, i_, f_ in trozos)
            fin_previa = subs[-1][1] if subs else 0.0
            arranque = max(fin_previa + 0.35, t0 - 0.8) if t0 + total > sig - 0.3 else t0
            tempo = max(1.0, min(1.12, total / max(0.1, sig - 0.3 - arranque)))
            t = arranque
            for cid, pausa, a_, b_ in trozos:
                t += pausa / tempo
                wav = TMP / f"voz_{cid}.wav"
                dur = pieza(cid, a_, b_, wav)
                if tempo > 1.0:
                    rapido = TMP / f"voz_{cid}_x.wav"
                    ff("-i", str(wav), "-af", f"atempo={tempo:.3f}", str(rapido))
                    wav, dur = rapido, dur / tempo
                out.append((round(t, 3), wav))
                t += dur
            subs.append((arranque, t, es))
            print(f"  (tempo {tempo:.2f}, arranca {arranque:.2f})")
            print(f"  en off {t0:6.2f}-{t:6.2f} (original hasta {t1:.2f}, sigue {sig:.2f})")
            continue
        if not k or k in SIN_VOZ:            # «¡Víbora!» de los matones: sin clip propio
            continue
        cid = boca(k)
        # Correspondencia clip → línea de tiempo de la toma que muestra la boca:
        # t = inicio_toma + (tiempo_clip − usa_ini). Así la voz cae donde la boca
        # se mueve aunque armar.py haya corrido la ventana contra el techo.
        # De las tomas de este encuadre, la que más se superpone con la línea
        # (E36 se dice durante la toma 36, que reusa el clip de la 32).
        propias = [t for t in T.TOMAS if t[6] == k]
        tt = max(propias, key=lambda t: min(t[2], t1) - max(t[1], t0))
        pb = planos["T" + tt[0]]
        desplazamiento = inicio["T" + tt[0]] - pb["usa"][0]
        ini, fin = limites(cid, en)
        a = ini - 0.12
        entra = desplazamiento + a
        b = min(fin + 0.2, sig - desplazamiento - 0.02)   # no pisa la línea siguiente
        if b < fin:          # «What…?» cae encima del «Shh» siguiente: se deja entera
            b = fin + 0.1
        wav = TMP / f"voz_{k}.wav"
        segs_auto = sin_repeticiones(cid, a, b)
        if k in SEGMENTOS or segs_auto:
            x, sr = sf.read(audio(cid), dtype="float32")
            segs = SEGMENTOS.get(k) or segs_auto
            a, b = segs[0][0], segs[-1][1]
            trozos = []
            for i, (s0, s1) in enumerate(segs):
                trozos.append(x[int(s0 * sr):int(s1 * sr)])
                if i + 1 < len(segs) and k in SEGMENTOS:
                    trozos.append(np.zeros((int(0.35 * sr), x.shape[1]), dtype=x.dtype))
            y = np.concatenate(trozos)
            nf = int(0.03 * sr)
            rampa = np.linspace(0, 1, nf)[:, None]
            y[:nf] *= rampa
            y[-nf:] *= rampa[::-1]
            sf.write(wav, y, sr)
            dur = len(y) / sr
            entra = desplazamiento + a
            print(f"        ({k}: {len(segs)} tramos manuales → {dur:.2f} s)")
        else:
            dur = pieza_compacta(cid, a, b, wav)
        # La línea no puede durar mucho más que en el original: H3 alarga («Shh,
        # shh» duró 3,2 s contra 1,0; T55 dijo la frase dos veces) y la voz se
        # derramaba sobre las dos tomas siguientes, donde ya no se ve esa boca
        # (15/9, «el audio no coincide»). Se acelera hasta 1,25× para entrar en
        # la duración original + 0,3 s y, si igual sobra, se corta con fundido
        # (sólo llega a pasar con siseos y balbuceo, nunca con la frase).
        objetivo = (t1 - t0) + 0.3
        if dur > objetivo + 0.05:
            tempo = min(1.25, dur / objetivo)
            rapido = TMP / f"voz_{k}_x.wav"
            ff("-i", str(wav), "-af", f"atempo={tempo:.3f}", str(rapido))
            wav, dur = rapido, dur / tempo
            if dur > objetivo + 0.4:
                corto = TMP / f"voz_{k}_c.wav"
                ff("-i", str(wav), "-af", f"atrim=0:{objetivo + 0.4:.3f},afade=t=out:st={objetivo + 0.1:.3f}:d=0.3",
                   str(corto))
                wav, dur = corto, objetivo + 0.4
            print(f"        ({k}: {tempo:.2f}× → {dur:.2f} s, original {t1 - t0:.2f})")
        out.append((round(entra, 3), wav))
        subs.append((t0, max(t1, entra + dur), es))
        print(f"  {k:5} {cid:5} clip {a:.2f}-{b:.2f} → {entra:6.2f}  «{en}»")
    return out, subs


def partir(texto, a, b, largo=42):
    """Una línea larga en trozos de ≤ ~42 caracteres (dos renglones: con cuatro,
    el subtítulo subía hasta tapar la placa de nombre), cortando primero en la
    puntuación y, si un tramo sigue largo, entre palabras. El tiempo se reparte
    según los caracteres de cada trozo."""
    partes = []
    for frase in re.split(r"(?<=[,.?!…])\s+", texto):
        while len(frase) > largo:
            corte = frase.rfind(" ", 0, largo)
            if corte <= 0:
                break
            partes.append(frase[:corte])
            frase = frase[corte + 1:]
        partes.append(frase)
    trozos, cur = [], ""
    for parte in partes:
        if cur and len(cur) + 1 + len(parte) > largo:
            trozos.append(cur)
            cur = parte
        else:
            cur = (cur + " " + parte).strip()
    if cur:
        trozos.append(cur)
    total = sum(len(x) for x in trozos)
    out, t = [], a
    for x in trozos:
        d = (b - a) * len(x) / total
        out.append((t, t + d, x))
        t += d
    return out


def srt(subs, ruta):
    filas = []
    for a, b, es in sorted(subs):
        filas += partir(es, a, b)
    # ninguno se queda en pantalla cuando entra el siguiente
    filas = [(a, min(b, filas[i + 1][0]) if i + 1 < len(filas) else b, x)
             for i, (a, b, x) in enumerate(filas)]
    montaje.srt_voz([(a, b - 0.05, x) for a, b, x in filas], ruta)
    return len(filas)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "medir":
        return medir()
    FINAL.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    g = json.loads((AQUI / "proyecto.json").read_text(encoding="utf-8"))

    global CORTES, planos_con_voz
    CORTES = json.loads((CLIPS / "cortes.json").read_text()) if (CLIPS / "cortes.json").exists() else {}
    planos_con_voz = {p["id"]: True for p in g["planos"] if p.get("voz_ref")}
    # 1. imagen: cada toma recortada a su tramo, sin audio
    # Por CUADROS, no por segundos: con `-t` cada tramo redondea hacia arriba y
    # en 82 tomas la imagen se estiró 0,9 s contra el audio (15/9). Cada toma
    # dura round(hasta·24) − round(desde·24) cuadros de la línea del original.
    partes = []
    toma = {"T" + t[0]: t for t in T.TOMAS}
    # Caché de partes (16/9): cada toma recortada se guarda con una clave (clip,
    # tamaño y fecha del clip, ventana, cuadros, corte) y sólo se recodifica si
    # algo cambió. Rehacer 3 clips ya no obliga a recortar las 82 tomas.
    cache_f = TMP / "cache.json"
    cache = json.loads(cache_f.read_text()) if cache_f.exists() else {}
    reusadas = 0
    for p in g["planos"]:
        cid = p.get("clip_de") or p["id"]
        t = toma[p["id"]]
        n = round(t[2] * 24) - round(t[1] * 24)
        parte = TMP / f"v_{p['id']}.mp4"
        st = clip(cid).stat()
        clave = f"{cid}|{st.st_size}|{int(st.st_mtime)}|{p['usa']}|{n}|{CORTES.get(cid, {}).get('cortes')}"
        if cache.get(p["id"]) == clave and parte.exists():
            partes.append(parte)
            reusadas += 1
            continue
        cache[p["id"]] = clave
        hay = cuadros(clip(cid))
        a = max(0, min(round(p["usa"][0] * 24), hay - n)) / 24
        lento = []
        # Corte inventado dentro del tramo (cortes.json) en una toma MUDA: se usa
        # sólo lo anterior al corte, estirado en cámara lenta; si es muy poco
        # (T60: 0,38 s de 1,22), un cuadro fijo con zoom suave. En las que hablan
        # no se toca: la voz sale del mismo clip y estirar desincroniza la boca.
        # Tomas cuyo «corte» es movimiento verificado a ojo (puerta que se abre,
        # matón que entra): no se tapan. v4: T31 quedaba en cámara lenta ×0,77.
        SIN_TAPAR = {"T31", "T15", "T79", "T35"}
        cut = [] if cid in SIN_TAPAR else [t for t in CORTES.get(cid, {}).get("cortes", []) if a + 0.1 < t < a + n / 24]
        if cut and not p.get("voz_ref") and not planos_con_voz.get(cid):
            disp = int((min(cut) - a) * 24) - 2
            if disp >= 0.4 * n:
                f = n / disp
                lento = ["-vf", f"setpts=PTS*{f:.4f},fps=24"]
                print(f"  !! {p['id']}: corte a {min(cut):.2f} s dentro del tramo: {disp} cuadros "
                      f"estirados a {n} (×{1 / f:.2f})")
            else:
                png = TMP / f"still_{p['id']}.png"
                ff("-ss", f"{a:.4f}", "-i", str(clip(cid)), "-frames:v", "1", str(png))
                ff("-loop", "1", "-i", str(png), "-vf",
                   f"zoompan=z='1+0.05*on/{n}':d={n}:s=768x1344:fps=24,format=yuv420p",
                   "-frames:v", str(n), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                   "-r", "24", str(parte))
                partes.append(parte)
                print(f"  !! {p['id']}: corte a {min(cut):.2f} s casi al arranque: cuadro fijo con zoom")
                continue
        if hay < n:
            # T11 llegó con 21 de 124 cuadros (la primera bajada por tar se cortó y
            # la instancia ya no existía): se estira lo que hay, en cámara lenta.
            f = n / hay
            lento = ["-vf", f"setpts=PTS*{f:.4f},fps=24"]
            print(f"  !! {cid}: {hay} cuadros para {n}: cámara lenta ×{1 / f:.2f}")
        ff("-ss", f"{a:.4f}", "-i", str(clip(cid)), *lento, "-frames:v", str(n), "-an",
           "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
           "-r", "24", str(parte))
        partes.append(parte)
    cache_f.write_text(json.dumps(cache))
    print(f"partes reutilizadas: {reusadas}/{len(partes)}")
    lista = TMP / "orden.txt"
    lista.write_text("".join(f"file '{x.name}'\n" for x in partes), encoding="utf-8")
    imagen = TMP / "imagen.mp4"
    ff("-f", "concat", "-safe", "0", "-i", "orden.txt", "-c", "copy", imagen.name, cwd=str(TMP))
    print(f"imagen: {len(partes)} tomas, {montaje.duracion(imagen):.2f} s")

    # 2. imagen + ambiente del original (música y efectos, sin voces)
    con_amb = TMP / "imagen_amb.mp4"
    ff("-i", str(imagen), "-i", str(AQUI / "audio-original" / "ambiente.wav"),
       "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
       "-shortest", str(con_amb))

    # 3. voces de H3 encima, con el ambiente agachándose cuando hablan, a -14 LUFS
    vs, subs = voces()
    mezcla = TMP / "mezcla.mp4"
    montaje.mezclar(con_amb, vs, mezcla, ambiente_db=-2.0, voz_db=3.0)

    # 4. subtítulos en castellano y placas de nombre
    n = srt(subs, TMP / "subs.srt")
    shutil.copy(r"C:\Windows\Fonts\georgiai.ttf", TMP / "georgiai.ttf")
    # Sin subtítulos quemados (pedido del 15/9): el SRT queda al lado del MP4 por
    # si hace falta, pero no va en la imagen.
    filtros = []
    shutil.copy(TMP / "subs.srt", FINAL / "replica-danza-ep1.es.srt")
    for i, (a, b, texto) in enumerate(T.PLACAS):
        txt = TMP / f"placa{i}.txt"
        palabras = texto.split()
        # como el original: apiladas de a una o dos palabras
        renglones, cur = [], ""
        for w in palabras:
            if cur and len(cur) + len(w) > 10:
                renglones.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        renglones.append(cur)
        # write_bytes y no write_text: en Windows write_text escribe \r\n y drawtext
        # deja un renglón vacío de más entre cada palabra.
        txt.write_bytes("\n".join(renglones).encode("utf-8"))
        filtros.append(f"drawtext=fontfile=georgiai.ttf:textfile={txt.name}:fontsize=66:"
                       f"fontcolor=white:line_spacing=6:shadowcolor=black@0.6:shadowx=2:shadowy=2:"
                       f"x=w*0.08:y=h*0.34:enable='between(t,{a:.2f},{b:.2f})'")
    salida = FINAL / "replica-danza-ep1.mp4"
    ff("-i", mezcla.name, "-vf", ",".join(filtros), "-c:v", "libx264", "-preset", "slow",
       "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
       str(salida.resolve()), cwd=str(TMP))
    print(f"\n{salida}  {montaje.duracion(salida):.2f} s · {len(vs)} pistas de voz · "
          f"{n} subtítulos · {len(T.PLACAS)} placas · {salida.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
