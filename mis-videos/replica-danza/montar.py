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
    if not w.exists():
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
        raise SystemExit(f"{cid}: no encuentro voz")
    if w:
        fin_palabra = w[min(n, len(w)) - 1][2]
        primera_fin = w[0][2]
        cand = [a for a, b in tr if a <= primera_fin + 0.05] or [tr[0][0]]
        ini = cand[-1] if len(cand) > 1 and w[0][1] > 0.3 else cand[0]
        # que el arranque no quede antes de un tramo que termina lejos de la palabra
        ini = max([a for a, b in tr if a <= w[0][1] + 0.05] or [ini]) if w[0][1] > 0.3 else ini
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
        if not k:                            # «¡Víbora!» de los matones: sin clip propio
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
        dur = pieza(cid, a, b, wav)
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

    # 1. imagen: cada toma recortada a su tramo, sin audio
    # Por CUADROS, no por segundos: con `-t` cada tramo redondea hacia arriba y
    # en 82 tomas la imagen se estiró 0,9 s contra el audio (15/9). Cada toma
    # dura round(hasta·24) − round(desde·24) cuadros de la línea del original.
    partes = []
    toma = {"T" + t[0]: t for t in T.TOMAS}
    for p in g["planos"]:
        cid = p.get("clip_de") or p["id"]
        t = toma[p["id"]]
        n = round(t[2] * 24) - round(t[1] * 24)
        hay = cuadros(clip(cid))
        a = max(0, min(round(p["usa"][0] * 24), hay - n)) / 24
        parte = TMP / f"v_{p['id']}.mp4"
        lento = []
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
    filtros = [f"subtitles=filename=subs.srt:force_style='{montaje.ESTILO_SUB}'"]
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
