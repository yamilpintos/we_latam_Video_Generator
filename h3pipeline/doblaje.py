"""Isocronía: hacer calzar una voz generada con una boca que ya está animada.

Vale para cualquier video de MiniMax H3. El método completo, con el porqué de
cada número, está en `ISOCRONIA.md`; acá está el motor.

    La ventana la define la boca. El texto se escribe para esa ventana.
    El audio casi no se toca.

Todo lo demás son consecuencias de esa frase. El error que costó más
iteraciones fue hacerlo al revés: escribir el texto libre y después deformar el
audio para que entrara.

Los seis pasos, y dónde vive cada uno:

    1. separar voz de ambiente        demucs, fuera de este módulo
    2. medir la ventana               `bloques()` y `medir()`
    3. corregir el desfase de boca    la tabla `pre` que se pasa a `colocar()`
    4. escribir el texto              `voz.py` (densidad)
    5. varias redacciones             `tts.elegir()`
    6. tocar el audio lo mínimo       `alinear()`

Las constantes son las del motor de doblaje de DubAI (`Foton/dubai_v2`), medidas
por ellos en producción sobre cientos de líneas. No están elegidas por nosotros
y no conviene tocarlas sin medir: ver `ISOCRONIA.md §"De dónde salen los
números"`.

> Este módulo es la versión **general y reusable** del motor. La corrida de
> Aladino sigue viva en `tools/doblaje/`, con su tabla de líneas y su mezcla;
> se migrará cuando esa película esté cerrada.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import config, voz

SR = 48000
HOP = 0.010          # resolución del detector de energía
UMBRAL = 0.18        # fracción del pico local que cuenta como voz
GUARDA = 0.15        # silencio exigido antes del inicio / después del fin
BACK, FWD = 0.60, 0.40        # ventana de búsqueda del ataque
END_FWD = 0.80                # ventana de búsqueda del final

FUSION = 0.25        # huecos menores se fusionan: son pausas entre palabras
PARTIR = 0.45        # huecos mayores parten la línea: ahí la boca para de verdad
MIN_BLOQUE = 0.15

LEAD = 0.10          # se adelanta todo: entre llegar antes o tarde, antes —
                     # tarde se ve como boca moviéndose muda
BORDE = 0.040        # aire que se deja al recortar el silencio de bordes
MIN_SEG = 0.06       # por debajo, el vocoder no tiene ventana


class ErrorDoblaje(RuntimeError):
    pass


# ------------------------------------------------------------- la ventana

def _rms(x):
    import numpy as np
    h = int(SR * HOP)
    n = len(x) // h
    if n < 20:
        return None
    return np.sqrt((x[:n * h].reshape(n, h) ** 2).mean(axis=1))


def _tramo(v, a, b):
    import numpy as np
    i, j = max(0, int(a * SR)), min(len(v), int(b * SR))
    return v[i:j] if j > i else np.zeros(0, "float32")


def cargar_voz(ruta) -> "object":
    """El stem de voz de demucs, en mono. Sin él no se puede medir nada: sobre
    el audio mezclado de H3 hay ambiente continuo y ninguna detección por
    energía lo separa."""
    import soundfile as sf
    v, _ = sf.read(str(ruta), dtype="float32")
    return v.mean(1) if v.ndim > 1 else v


def separar(video, destino: Path, log=print) -> tuple[Path, Path]:
    """Separa la voz del resto con demucs. Devuelve `(vocals, ambiente)`.

    Dos rodeos que hacen falta en esta máquina y que ya costaron su tiempo:

      · la CLI de demucs lee el audio con `torchcodec`, que acá tiene una DLL
        rota. Se carga el WAV con `soundfile` y se le pasa el tensor.
      · `demucs.api` no existe en la 4.0.1 instalada, así que se va por
        `pretrained` + `apply_model`, que es la capa de abajo.

    El ambiente **no se descarta**: viento, motor, metal y tren son lo que H3
    hace distinto, y vuelven a la mezcla final debajo de la voz nueva.
    """
    import numpy as np
    import soundfile as sf
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    crudo = destino / "_original.wav"
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-i", str(video),
                    "-ac", "2", "-ar", str(SR), "-c:a", "pcm_f32le", str(crudo)],
                   check=True, stdin=subprocess.DEVNULL)

    x, sr = sf.read(crudo, dtype="float32")
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    wav = torch.from_numpy(x.T).contiguous()
    log(f"  separando {wav.shape[1] / sr:.1f} s con demucs (en CPU tarda unos minutos)")

    modelo = get_model("htdemucs")
    modelo.eval()
    if sr != modelo.samplerate:
        import torchaudio
        wav = torchaudio.functional.resample(wav, sr, modelo.samplerate)

    # Normalización estándar de demucs; se deshace sobre las salidas.
    ref = wav.mean(0)
    med, des = ref.mean(), ref.std() + 1e-8
    with torch.no_grad():
        fuentes = apply_model(modelo, ((wav - med) / des)[None], device="cpu",
                              progress=False)[0]
    fuentes = fuentes * des + med
    nombres = modelo.sources
    voz_t = fuentes[nombres.index("vocals")]
    resto = sum(fuentes[i] for i, n in enumerate(nombres) if n != "vocals")

    v, a = destino / "vocals.wav", destino / "ambiente.wav"
    sf.write(v, voz_t.T.numpy(), modelo.samplerate)
    sf.write(a, resto.T.numpy(), modelo.samplerate)
    log(f"    {v.name} y {a.name} listos")
    return v, a


def bloques(v, a: float, b: float, fusion: float = FUSION,
            minimo: float = MIN_BLOQUE) -> list[tuple[float, float]]:
    """Los tramos de habla contigua dentro de [a, b].

    Los huecos menores a `fusion` se fusionan: son las pausas naturales entre
    palabras, no separaciones de línea."""
    import numpy as np
    from scipy.ndimage import uniform_filter1d
    seg = _tramo(v, a, b)
    if not len(seg):
        return []
    r = uniform_filter1d(np.abs(seg).astype("float32"), int(SR * 0.03))
    pico = float(r.max())
    if pico < 1e-4:
        return []
    act = r > pico * UMBRAL
    d = np.diff(act.astype("int8"))
    ini = list(np.where(d == 1)[0] + 1)
    fin = list(np.where(d == -1)[0] + 1)
    if act[0]:
        ini.insert(0, 0)
    if act[-1]:
        fin.append(len(act))
    bl = [(a + i0 / SR, a + i1 / SR) for i0, i1 in zip(ini, fin)]
    fus: list[tuple[float, float]] = []
    for x, y in bl:
        if fus and x - fus[-1][1] < fusion:
            fus[-1] = (fus[-1][0], y)
        else:
            fus.append((x, y))
    return [(x, y) for x, y in fus if y - x >= minimo]


@dataclass
class Ventana:
    inicio: float
    fin: float
    activo: float                 # segundos de habla REAL: es lo que manda la densidad
    tramos: list[tuple[float, float]]

    @property
    def span(self) -> float:
        return self.fin - self.inicio

    @property
    def partida(self) -> bool:
        return len(self.tramos) > 1


def medir(v, t0_asr: float, t1_asr: float, tope: float | None = None) -> Ventana:
    """La ventana REAL de una línea, sobre el stem de voz.

    **El ASR no alcanza.** Agrupa en frases y esas frases se comen silencios
    enteros. Un caso medido: una línea que el ASR daba como 8,63 s tenía sólo
    5,24 s de habla, con 2,8 s de silencio al final — el doblaje escrito para
    8,63 s seguía sonando casi tres segundos después de que la boca paraba.

    La línea abarca **todos** sus bloques, no el mayor: una frase puede llevar
    una pausa dramática adentro y sigue siendo una frase.

    `activo` es lo que se usa para la densidad. Escribir contra el span
    convierte el silencio interno en desborde.
    """
    bl = bloques(v, max(0.0, t0_asr - BACK), t1_asr + END_FWD)
    if tope is not None:
        bl = [(x, min(y, tope - 0.06)) for x, y in bl if x < tope - 0.06]
    prop = [b for b in bl if min(b[1], t1_asr) - max(b[0], t0_asr) > 0]
    if not prop:
        return Ventana(t0_asr, t1_asr, t1_asr - t0_asr, [])
    # Bloques separados por menos de PARTIR son pausas dentro de la misma frase.
    grupos = [[prop[0]]]
    for b in prop[1:]:
        if b[0] - grupos[-1][-1][1] < PARTIR:
            grupos[-1].append(b)
        else:
            grupos.append([b])
    tramos = [(g[0][0], g[-1][1]) for g in grupos]
    return Ventana(prop[0][0], prop[-1][1],
                   sum(y - x for x, y in prop), tramos)


def aplicar_pre(ventana: Ventana, pre: float) -> Ventana:
    """Extiende el primer tramo hacia atrás los segundos que la BOCA se mueve
    antes de que H3 emita sonido.

    H3 no sincroniza su propia boca con su propio audio: medido, mueve los
    labios hasta 0,85 s antes. Durante ese hueco **la onda está en cero**, así
    que ninguna medición sobre el audio lo encuentra — se mide por ojo, una vez
    por plano, con una hoja de contacto (ver ISOCRONIA.md §3).

    Se extiende el primer tramo y **no** se crea uno nuevo: probado a crear un
    tramo propio para el suspiro y midió peor — en 0,70 s ElevenLabs no dice
    nada (pedía 2,19×), mientras que pegado a la primera frase entra en 1,56×.
    """
    if not ventana.tramos or pre <= 0:
        return ventana
    t = list(ventana.tramos)
    t[0] = (t[0][0] - pre, t[0][1])
    return Ventana(t[0][0], ventana.fin, ventana.activo + pre, t)


# ------------------------------------------------------ tocar el audio

def _cadena(f: float) -> str:
    """El filtro de ffmpeg para llevar un tramo al factor f (>1 alarga).

    Medido en ida y vuelta contra el natural, por distancia log-espectral, sobre
    una voz grave y una aguda: `atempo` (dominio del tiempo, sin fase) gana en
    todo el rango que usamos, y por bastante — a 1,25× da 5,70 dB contra 7,01 de
    rubberband. El vocoder de fase sólo conviene debajo de 0,62×, donde el
    solapamiento temporal empieza a repetir sílabas.
    """
    if f < 0.62:
        return f"rubberband=tempo={1 / f:.6f}:transients=smooth"
    r, etapas = 1.0 / f, []
    while r > 2.0:
        etapas.append(2.0)
        r /= 2.0
    while r < 0.5:
        etapas.append(0.5)
        r /= 0.5
    etapas.append(r)
    return ",".join(f"atempo={e:.6f}" for e in etapas)


def estirar(seg, dur_obj: float, td: Path, i: int = 0):
    """Lleva `seg` a `dur_obj` segundos **sin mover el tono**.

    Estirar en el dominio del tiempo, nunca remuestreando: remuestrear cambia el
    tono junto con la velocidad y el personaje suena distinto en cada línea. Esa
    fue la falla que hubo que corregir — la F0 pasaba de 102,8 a 120,6 Hz.

    Se procesa en MONO cuando los dos canales son iguales, que es el caso: las
    tomas de ElevenLabs son monofónicas. Tratar dos canales idénticos por
    separado los descorrelaciona y abre la imagen estéreo artificialmente, que
    es parte de lo que se oye como lata.
    """
    import numpy as np
    import soundfile as sf
    dur_in = len(seg) / SR
    if dur_in <= 0 or dur_obj <= 0:
        return np.asarray(seg, "float32")
    n_obj = max(1, int(round(dur_obj * SR)))
    f = dur_obj / dur_in
    if abs(f - 1.0) < 1e-3:
        return np.asarray(seg[:n_obj] if len(seg) >= n_obj else seg, "float32")
    if dur_in < MIN_SEG or dur_obj < MIN_SEG:
        # Más corto que la ventana del algoritmo. A esta escala (<60 ms) el
        # remuestreo no alcanza a leerse como cambio de tono.
        idx = np.linspace(0, max(len(seg) - 1, 0), n_obj)
        i0 = np.clip(idx.astype(int), 0, max(len(seg) - 2, 0))
        fr = (idx - i0)[:, None]
        i1 = np.minimum(i0 + 1, len(seg) - 1)
        return (seg[i0] * (1 - fr) + seg[i1] * fr).astype("float32")
    mono = seg.ndim > 1 and float(np.abs(seg[:, 0] - seg[:, 1]).max()) < 1e-6
    src, dst = td / f"_i{i}.wav", td / f"_o{i}.wav"
    sf.write(src, seg[:, 0] if mono else seg, SR)
    subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-i", str(src),
                    "-af", _cadena(f), "-c:a", "pcm_f32le", str(dst)],
                   check=True, stdin=subprocess.DEVNULL)
    a, _ = sf.read(dst, dtype="float32")
    if a.ndim == 1:
        a = np.stack([a, a], 1)
    if len(a) > n_obj:
        a = a[:n_obj]
    elif len(a) < n_obj:
        a = np.pad(a, ((0, n_obj - len(a)), (0, 0)))
    return a.astype("float32")


def recortar_bordes(a, td: Path):
    """Saca el silencio de los extremos dejando `BORDE` de aire.

    ElevenLabs mete entre 0 y 102 ms al inicio de cada toma (medido sobre 19).
    Sin recortarlo la voz entra tarde respecto de los labios en **todas** las
    líneas. Sólo bordes: las pausas internas actuadas de v3 no se tocan.
    """
    import numpy as np
    import soundfile as sf
    src, dst = td / "_b.wav", td / "_bo.wav"
    sf.write(src, a, SR)
    flt = (f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence={BORDE},"
           "areverse,"
           f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence={BORDE + 0.02},"
           "areverse")
    try:
        subprocess.run([config.ffmpeg(), "-y", "-v", "error", "-i", str(src),
                        "-af", flt, "-c:a", "pcm_f32le", str(dst)],
                       check=True, stdin=subprocess.DEVNULL)
        b, _ = sf.read(dst, dtype="float32")
        if b.ndim == 1:
            b = np.stack([b, b], 1)
        return b.astype("float32") if len(b) / SR > 0.15 else a
    except Exception:
        # Si el filtro falla, es mejor el audio sin recortar que ninguno.
        return a


def alinear(audio, ventana_s: float, presupuesto: float | None = None):
    """Coloca una toma con **un solo factor de tiempo**. Devuelve (audio, factor).

    Un factor por clip, nunca por tramo: alinear palabra por palabra fue el
    primer diseño y suena entrecortado — una frase de doce palabras terminaba
    con doce cambios de escala independientes más silencios intercalados. No se
    arregla con parámetros.

    Y si la toma es **más corta** que la ventana no se estira para llenarla: se
    deja natural y lo que sobra queda en silencio. Llenar el hueco es trabajo
    del texto (ver `voz.py`), no del audio.
    """
    import numpy as np
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        a = recortar_bordes(np.asarray(audio, "float32"), td)
        dur = len(a) / SR
        if dur <= 0 or ventana_s <= 0:
            return np.asarray(audio, "float32"), 1.0
        presupuesto = ventana_s if presupuesto is None else max(presupuesto, 0.2)
        abajo = 1.0 / voz.MAX_LENTO
        if dur <= presupuesto:
            factor = (max(abajo, min(dur / ventana_s, 1.0)) if dur < ventana_s
                      else min(dur / ventana_s, voz.MAX_RAPIDO))
        else:
            factor = min(dur / presupuesto, voz.MAX_RAPIDO_DURO)
        if abs(factor - 1.0) < 1e-3:
            return a, 1.0
        return estirar(a, dur / factor, td, 0).astype("float32"), float(factor)


# --------------------------------------------------- lo que H3 sí hace bien

def capa_no_verbal(stem_voz, palabras: list[dict], n_muestras: int,
                   guarda: float = 0.15, min_dur: float = 0.18,
                   fusion: float = 0.20, log=print):
    """Devuelve la voz del original **sólo donde no hay palabra transcrita**.

    Risas, gruñidos y exclamaciones sin palabra son lo que H3 hace bien: nacen y
    mueren dentro del plano. Vivían en el stem de voz y se descartaban enteros
    junto con el habla. Acá se recuperan enmascarando todo lo que el ASR
    transcribió —el habla que se reemplaza y el balbuceo que queda mudo a
    propósito— y dejando pasar el resto.

    `palabras` son dicts con `start` y `end` en segundos.
    """
    import numpy as np
    from scipy.ndimage import uniform_filter1d
    v = stem_voz
    if v.ndim == 1:
        v = np.stack([v, v], 1)
    v = v[:n_muestras] if len(v) >= n_muestras else np.pad(
        v, ((0, n_muestras - len(v)), (0, 0)))
    r = uniform_filter1d(np.abs(v.mean(1)).astype("float32"), int(0.03 * SR))
    piso, pico = np.percentile(r, 20), np.percentile(r, 99.5)
    umb = piso + 0.10 * (pico - piso)
    hablado = np.zeros(n_muestras, bool)
    for w in palabras:
        a = max(0, int((w["start"] - guarda) * SR))
        b = min(n_muestras, int((w["end"] + guarda) * SR))
        hablado[a:b] = True
    cand = (r > umb) & (~hablado)
    d = np.diff(cand.astype("int8"))
    ini = list(np.where(d == 1)[0] + 1)
    fin = list(np.where(d == -1)[0] + 1)
    if cand[0]:
        ini.insert(0, 0)
    if cand[-1]:
        fin.append(n_muestras)
    seg = [(i, j) for i, j in zip(ini, fin) if (j - i) / SR >= min_dur]
    fus: list[tuple[int, int]] = []
    for a, b in seg:
        if fus and (a - fus[-1][1]) / SR < fusion:
            fus[-1] = (fus[-1][0], b)
        else:
            fus.append((a, b))
    out = np.zeros((n_muestras, 2), "float32")
    nf = int(0.02 * SR)
    for a, b in fus:
        x = v[a:b].copy()
        f = min(nf, len(x) // 2)
        if f:
            ramp = np.linspace(0, 1, f, dtype="float32")[:, None]
            x[:f] *= ramp
            x[-f:] *= ramp[::-1]
        out[a:b] = x
    log(f"capa no verbal: {len(fus)} tramos, "
        f"{sum(b - a for a, b in fus) / SR:.1f} s")
    return out, fus


# ------------------------------------------------------------ verificación

def error_de_colocacion(stem_voz, colocadas: list[tuple[str, float]],
                        log=print) -> list[tuple[str, float]]:
    """Dónde arranca cada línea doblada contra dónde arranca el habla del
    original. Es **la única prueba** de que la colocación funciona, y separa dos
    problemas que suenan igual:

      · error dentro de ±0,1 s → la colocación está bien; lo que falta es el
        corrimiento de boca (`aplicar_pre`);
      · error mayor o disperso → hay un bug en el motor.

    En la implementación de referencia el error mediano es −0,067 s sobre 22
    piezas, y ese valor es el `LEAD` deliberado.
    """
    import numpy as np
    out = []
    for pid, t in colocadas:
        bl = bloques(stem_voz, max(0.0, t - 1.0), t + 1.5)
        if not bl:
            continue
        out.append((pid, t - bl[0][0]))
    if out:
        med = float(np.median([e for _p, e in out]))
        dentro = sum(1 for _p, e in out if abs(e) <= 0.1)
        log(f"error de colocación: mediana {med:+.3f} s · "
            f"{dentro}/{len(out)} dentro de ±0,1 s")
    return out
