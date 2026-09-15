# -*- coding: utf-8 -*-
"""Isocronia por CLIP, no por palabra. Modelo tomado de Foton/dubai_v2.

QUE SE PROBO ANTES Y POR QUE SE ABANDONO
  La version previa alineaba palabra por palabra: una ancla por cada palabra que
  coincidia entre Scribe y ElevenLabs, y un factor de tiempo distinto para cada
  tramo, con silencio de relleno donde no alcanzaba. Suena entrecortado, y era
  inevitable: una frase de 12 palabras tenia 12 cambios de escala independientes
  mas silencios intercalados. Ningun ajuste de parametros lo arregla.

EL MODELO DE DUBAI, MEDIDO POR ELLOS EN PRODUCCION
  · UN solo atempo por linea. Nada de tramos.
  · Ralentizar casi no se tolera: SYNC_MAX_SLOW = 1.08. Su nota dice que una voz
    aguda estirada mas de 10 % "suena masculina/pastosa aunque el pitch no cambie";
    les paso con tres voces femeninas distintas. Yo tenia el tope en 1.60 con
    techo duro 2.20, o sea 20 veces su tolerancia.
  · Comprimir si tolera: hasta 1.15 suave, 1.30 duro.
  · Si el clip es mas corto que la ventana NO se estira para llenarla: se deja
    natural y lo que sobra queda en silencio. Lo que se corrige es el TEXTO.
  · Se recorta el silencio de bordes: ElevenLabs mete hasta 200 ms al inicio de
    cada clip y eso atrasa la voz respecto de los labios en todas las lineas.

LO QUE QUEDA PENDIENTE DEL MODELO
  Su isochrony.py reescribe con un LLM las lineas cuya densidad se aleja de los
  ~17 caracteres/segundo del espanol. Once de nuestras diecinueve estan por
  debajo, algunas a menos de la mitad. Eso se arregla en el guion, no aca.
"""
import base64, difflib, json, re, subprocess, tempfile, unicodedata, urllib.request
from pathlib import Path
import numpy as np, soundfile as sf

KEY = next(l.split("=",1)[1].strip() for l in
           Path(r"C:/Users/Yamil/Desktop/Foton/dubai_v2/.env").read_text(encoding="utf-8").splitlines()
           if l.strip().startswith("ELEVENLABS_API_KEY="))
SR = 48000
MAX_LENTO = 1.08     # tope de ralentizacion (DubAI SYNC_MAX_SLOW, medido)
MAX_RAPIDO = 1.15    # tope suave de compresion (DubAI MAX_TIME_STRETCH)
MAX_RAPIDO_DURO = 1.30
BORDE = 0.040        # aire que se deja al recortar el silencio inicial
FADE = 0.008         # rampa contra el clic al entrar en el silencio
FF = Path(r"c:/Users/Yamil/Desktop/youtube proyect/.venv-depthflow/Scripts/ffmpeg.exe").resolve()
MIN_SEG = 0.06   # por debajo de esto el vocoder no tiene ventana; ver _estirar


def _cadena(f):
    """Filtro de ffmpeg para llevar un tramo al factor f (>1 alarga).

    Medido en ida y vuelta contra el natural, distancia log-espectral, sobre
    una voz grave y una aguda: atempo (dominio del tiempo, sin fase) gana en
    todo el rango que usamos, y por bastante — a 1,25x da 5,70 dB contra 7,01
    de rubberband. El vocoder de fase solo conviene en compresion extrema,
    debajo de 0,62x, donde el solapamiento temporal empieza a repetir silabas.
    """
    if f < 0.62:
        return f"rubberband=tempo={1 / f:.6f}:transients=smooth"
    r, etapas = 1.0 / f, []
    while r > 2.0:
        etapas.append(2.0); r /= 2.0
    while r < 0.5:
        etapas.append(0.5); r /= 0.5
    etapas.append(r)
    return ",".join(f"atempo={e:.6f}" for e in etapas)


def _estirar(seg, dur_obj, td, i):
    """Lleva seg (n,2) a dur_obj segundos SIN mover el tono.

    Se procesa en MONO cuando los dos canales son iguales —que es el caso: las
    tomas de ElevenLabs son monofonicas— y recien despues se duplica. Tratar
    dos canales identicos por separado los descorrelaciona y abre la imagen
    estereo de forma artificial, que es parte de lo que se oye como lata.
    """
    dur_in = len(seg) / SR
    if dur_in <= 0 or dur_obj <= 0:
        return seg.astype(np.float32)
    n_obj = max(1, int(round(dur_obj * SR)))
    f = dur_obj / dur_in
    if abs(f - 1.0) < 1e-3:
        return seg[:n_obj].astype(np.float32) if len(seg) >= n_obj else seg.astype(np.float32)
    if dur_in < MIN_SEG or dur_obj < MIN_SEG:
        # Tramo mas corto que la ventana del algoritmo. A esta escala (<60 ms)
        # el remuestreo no alcanza a leerse como cambio de tono.
        idx = np.linspace(0, max(len(seg) - 1, 0), n_obj)
        i0 = np.clip(idx.astype(int), 0, max(len(seg) - 2, 0))
        fr = (idx - i0)[:, None]
        i1 = np.minimum(i0 + 1, len(seg) - 1)
        return (seg[i0] * (1 - fr) + seg[i1] * fr).astype(np.float32)
    mono = seg.ndim > 1 and np.abs(seg[:, 0] - seg[:, 1]).max() < 1e-6
    src, dst = td / f"_i{i}.wav", td / f"_o{i}.wav"
    sf.write(src, seg[:, 0] if mono else seg, SR)
    subprocess.run([str(FF), "-y", "-v", "error", "-i", str(src), "-af", _cadena(f),
                    "-c:a", "pcm_f32le", str(dst)], check=True, stdin=subprocess.DEVNULL)
    a, _ = sf.read(dst, dtype="float32")
    if a.ndim == 1:
        a = np.stack([a, a], 1)
    if len(a) > n_obj:
        a = a[:n_obj]
    elif len(a) < n_obj:
        a = np.pad(a, ((0, n_obj - len(a)), (0, 0)))
    return a.astype(np.float32)


def sintetizar_con_tiempos(txt, vid):
    """Devuelve (mp3_bytes, [(palabra, ini, fin), ...]) de la voz generada."""
    body = json.dumps({"text": txt, "model_id": "eleven_v3",
        "voice_settings": {"stability":0.5,"similarity_boost":0.8,"use_speaker_boost":True}}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps?output_format=mp3_44100_192",
        data=body, headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=240))
    audio = base64.b64decode(d["audio_base64"])
    al = d["alignment"]
    chars, ini, fin = al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]
    pals, cur = [], None
    for c, a, b in zip(chars, ini, fin):
        if c.isspace():
            if cur: pals.append(cur); cur = None
        else:
            if cur is None: cur = [c, a, b]
            else: cur[0] += c; cur[2] = b
    if cur: pals.append(cur)
    return audio, [(p[0], p[1], p[2]) for p in pals]


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


def _recortar_bordes(a, td):
    """Saca el silencio de los extremos dejando BORDE de aire.

    ElevenLabs mete entre 0 y 102 ms de silencio al inicio de cada una de
    nuestras 19 tomas (medido). Sin recortarlo la voz entra tarde respecto de
    los labios en todas las lineas. Solo bordes: las pausas internas actuadas
    de v3 no se tocan.
    """
    src, dst = td / "_b.wav", td / "_bo.wav"
    sf.write(src, a, SR)
    flt = (f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence={BORDE},"
           "areverse,"
           f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence={BORDE + 0.02},"
           "areverse")
    try:
        subprocess.run([str(FF), "-y", "-v", "error", "-i", str(src), "-af", flt,
                        "-c:a", "pcm_f32le", str(dst)], check=True, stdin=subprocess.DEVNULL)
        b, _ = sf.read(dst, dtype="float32")
        if b.ndim == 1:
            b = np.stack([b, b], 1)
        return b.astype(np.float32) if len(b) / SR > 0.15 else a
    except Exception:
        return a


def alinear(audio_gen, ventana, presupuesto=None):
    """Coloca la linea con UN factor de tiempo. Devuelve (audio, factor_x1000).

    `ventana` la mide ventana.py sobre el stem de voz del original: es el span
    real de habla, no el rango del ASR. `presupuesto` es hasta donde puede
    estirarse sin pisar la linea siguiente.
    """
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        a = _recortar_bordes(np.asarray(audio_gen, np.float32), td)
        dur = len(a) / SR
        if dur <= 0 or ventana <= 0:
            return np.asarray(audio_gen, np.float32), 0
        presupuesto = ventana if presupuesto is None else max(presupuesto, 0.2)
        abajo = 1.0 / MAX_LENTO
        if dur <= presupuesto:
            if dur < ventana:
                # Mas corta que la ventana: se estira apenas, nunca mas de
                # MAX_LENTO. Lo que falte queda en silencio; llenarlo es
                # trabajo del texto, no del audio.
                factor = max(abajo, min(dur / ventana, 1.0))
            else:
                factor = min(dur / ventana, MAX_RAPIDO)
        else:
            factor = min(dur / presupuesto, MAX_RAPIDO_DURO)
        if abs(factor - 1.0) < 1e-3:
            return a, 1000
        out = _estirar(a, dur / factor, td, 0)
    return out.astype(np.float32), int(round(factor * 1000))
