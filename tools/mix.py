"""
Mezcla la Capa E completa contra la voz y escribe la pista de audio final.

Cuatro pistas, según pipeline/07-CAPA-E-sfx.md:
    A1  voz          la referencia, no se toca
    A2  música       con ducking real disparado por A1
    A3  ambiente     loops tileados con cross-fade, nunca cortados en seco
    A4  spot FX      anclados al segundo exacto

Master a -14 LUFS integrado (estándar YouTube) y -1 dBTP, medido con
K-weighting según ITU-R BS.1770-4, no a ojo.

    python tools/mix.py                 # mezcla completa + stems
    python tools/mix.py --sin-musica    # para juzgar el diseño sonoro solo
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

sys.path.insert(0, str(Path(__file__).parent))
import sfx_plan  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "output" / "mars-climate-orbiter"
AUDIO, VOZ = BASE / "audio", BASE / "voz"
SR, DUR = 44100, 300.0
XFADE = 1.2   # cross-fade entre regiones de ambiente
LOOPX = 0.5   # cross-fade al repetir un loop


def db(x):
    return 10.0 ** (x / 20.0)


def leer(p):
    x, sr = sf.read(p, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != SR:
        x = np.interp(np.linspace(0, len(x) - 1, int(len(x) * SR / sr)),
                      np.arange(len(x)), x).astype(np.float32)
    return x


def tile(x, n):
    """Repite x hasta n muestras con cross-fade en cada empalme."""
    if len(x) >= n:
        return x[:n].copy()
    f = int(LOOPX * SR)
    out = np.zeros(n, dtype=np.float32)
    pos, cuerpo = 0, x[:-f] if len(x) > f else x
    while pos < n:
        seg = x if pos + len(x) <= n else x[: n - pos]
        if pos and f and len(seg) > f:
            w = np.linspace(0, 1, f, dtype=np.float32)
            out[pos:pos + f] = out[pos:pos + f] * (1 - w) + seg[:f] * w
            out[pos + f:pos + len(seg)] = seg[f:]
        else:
            out[pos:pos + len(seg)] = seg
        pos += len(cuerpo) if len(cuerpo) else len(x)
    return out


def fades(x, fi, fo):
    n = len(x)
    if fi > 0:
        k = min(int(fi * SR), n)
        x[:k] *= np.linspace(0, 1, k, dtype=np.float32)
    if fo > 0:
        k = min(int(fo * SR), n)
        x[n - k:] *= np.linspace(1, 0, k, dtype=np.float32)
    return x


def k_weight(x):
    """Filtros de ponderación K de la ITU-R BS.1770-4."""
    a = signal.lfilter([1.53512485958697, -2.69169618940638, 1.19839281085285],
                       [1.0, -1.69065929318241, 0.73248077421585], x)
    return signal.lfilter([1.0, -2.0, 1.0],
                          [1.0, -1.99004745483398, 0.99007225036621], a)


def lufs(x):
    """Loudness integrado con compuerta absoluta y relativa."""
    y = k_weight(x.astype(np.float64))
    win, hop = int(0.4 * SR), int(0.1 * SR)
    if len(y) < win:
        return -np.inf
    bloques = np.array([np.mean(y[i:i + win] ** 2)
                        for i in range(0, len(y) - win, hop)])
    l = -0.691 + 10 * np.log10(np.maximum(bloques, 1e-12))
    b = bloques[l > -70.0]
    if not len(b):
        return -np.inf
    umbral = -0.691 + 10 * np.log10(np.mean(b)) - 10.0
    l2 = -0.691 + 10 * np.log10(np.maximum(bloques, 1e-12))
    b2 = bloques[(l2 > -70.0) & (l2 > umbral)]
    return -0.691 + 10 * np.log10(np.mean(b2 if len(b2) else b))


def normalizar(x, objetivo_lufs):
    """Lleva una pista a un loudness conocido.

    Hace falta porque los archivos que devuelve ElevenLabs vienen cada uno con su
    propio nivel: un room tone y un impacto de cohete no salen parejos. Aplicar los
    dB del plan directamente sobre ellos deja la música 20 dB por debajo de donde
    debería. Primero se normaliza, después se aplica el nivel de mezcla.
    """
    actual = lufs(x)
    return x if not np.isfinite(actual) else (x * db(objetivo_lufs - actual)).astype(np.float32)


def limitar(x, techo_db, release_ms=50.0):
    """Limitador de pico con anticipación. Un escalado global no sirve: bajaría
    todo el programa por culpa de un solo transitorio (el cohete)."""
    techo = db(techo_db)
    look = int(0.005 * SR)
    pico = np.abs(x)
    if look:
        pico = np.maximum.accumulate(pico[::-1])[::-1] if False else \
            signal.order_filter(pico, np.ones(2 * look + 1), 2 * look) \
            if len(pico) < 10_000 else _envmax(pico, look)
    g = np.minimum(1.0, techo / np.maximum(pico, 1e-9))
    c = np.exp(-1.0 / (SR * release_ms / 1000.0))
    out = np.empty_like(g)
    prev = 1.0
    for i in range(len(g)):
        prev = g[i] if g[i] < prev else c * prev + (1 - c) * g[i]
        out[i] = prev
    return (x * out).astype(np.float32)


def _envmax(x, look):
    """Máximo deslizante rápido por bloques."""
    n = len(x)
    m = np.copy(x)
    paso = 1
    while paso < look:
        m[:-paso] = np.maximum(m[:-paso], m[paso:])
        paso *= 2
    return m


def envolvente(x, attack_ms, release_ms):
    """Seguidor de envolvente con ataque y relajación distintos."""
    win = int(0.01 * SR)
    r = np.sqrt(np.convolve(x ** 2, np.ones(win) / win, mode="same"))
    ca = np.exp(-1.0 / (SR * attack_ms / 1000.0))
    cr = np.exp(-1.0 / (SR * release_ms / 1000.0))
    out = np.zeros_like(r)
    prev = 0.0
    for i in range(0, len(r), 1):
        c = ca if r[i] > prev else cr
        prev = c * prev + (1 - c) * r[i]
        out[i] = prev
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sin-musica", action="store_true")
    ap.add_argument("--out", default="MIX_COMPLETO.wav")
    args = ap.parse_args()

    n = int(DUR * SR)
    vo = leer(VOZ / "VO_TRACK_FINAL.wav")
    A1 = np.zeros(n, dtype=np.float32); A1[:min(n, len(vo))] = vo[:n]

    # A3 · ambiente
    A3 = np.zeros(n, dtype=np.float32)
    aid, ai, ao, adb, _p = sfx_plan.DRONE
    A3 += tile(leer(AUDIO / f"{aid}.mp3"), n) * db(adb)
    for aid, ini, fin, nivel, _p in sfx_plan.AMBIENTES:
        largo = int((fin - ini) * SR)
        seg = fades(tile(leer(AUDIO / f"{aid}.mp3"), largo).copy(), XFADE, XFADE)
        A3[int(ini * SR):int(ini * SR) + largo] += seg * db(nivel)

    # A2 · música
    A2 = np.zeros(n, dtype=np.float32)
    if not args.sin_musica:
        for mid, ini, fin, fi, fo, nivel, _p in sfx_plan.MUSICA:
            largo = int((fin - ini) * SR)
            seg = fades(tile(leer(AUDIO / f"{mid}.mp3"), largo).copy(), fi, fo)
            A2[int(ini * SR):int(ini * SR) + largo] += seg * db(nivel)

    # A4 · efectos
    A4 = np.zeros(n, dtype=np.float32)
    for sid, t, _d, nivel, _pl, _p in sfx_plan.SPOTS:
        x = leer(AUDIO / f"{sid}.mp3") * db(nivel)
        a = int(t * SR); b = min(n, a + len(x))
        A4[a:b] += fades(x[: b - a].copy(), 0.02, 0.15)

    # cada pista a su loudness objetivo, y recién ahí se mezclan
    A1 = normalizar(A1, -16.0)
    A3 = normalizar(A3, -30.0)
    A4 = normalizar(A4, -24.0)
    if not args.sin_musica:
        A2 = normalizar(A2, -26.0)
        env = envolvente(A1, sfx_plan.DUCK["attack_ms"], sfx_plan.DUCK["release_ms"])
        e = env / max(env.max(), 1e-9)
        # el factor satura la envolvente: sin él, el habla normal solo alcanza a pedir
        # la mitad de la reducción y la música se cuela entre palabra y palabra
        gain = db(-sfx_plan.DUCK["reduccion_db"] * np.clip(e * 5.0, 0, 1))
        A2 *= gain.astype(np.float32)
        voz_act = envolvente(A1, 5, 5) > 0.01
        red = -20 * np.log10(np.maximum(gain[voz_act], 1e-9))
        print(f"  ducking sobre la voz: {red.mean():.1f} dB medio, "
              f"{np.percentile(red, 90):.1f} dB en los picos "
              f"(objetivo {sfx_plan.DUCK['reduccion_db']:.0f})")

    mezcla = A1 + A2 + A3 + A4

    # master: acercar a -14 LUFS y limitar, iterando porque el limitador
    # baja el loudness y hay que compensar
    ganancia_total = 0.0
    for _ in range(4):
        d = sfx_plan.MASTER["lufs"] - lufs(mezcla)
        if abs(d) < 0.15:
            break
        mezcla = (mezcla * db(d)).astype(np.float32)
        ganancia_total += d
        mezcla = limitar(mezcla, sfx_plan.MASTER["true_peak_dbtp"])
    limitado = True

    out = VOZ.parent / "audio" / args.out
    sf.write(out, mezcla, SR)
    for nombre, pista in [("STEM_A1_voz", A1), ("STEM_A2_musica", A2),
                          ("STEM_A3_ambiente", A3), ("STEM_A4_efectos", A4)]:
        sf.write(AUDIO / f"{nombre}.wav", pista, SR)

    print(f"{out}")
    print(f"  duración        {len(mezcla)/SR:.1f} s")
    print(f"  LUFS integrado  {lufs(mezcla):.1f}  (objetivo {sfx_plan.MASTER['lufs']})")
    print(f"  pico            {20*np.log10(float(np.abs(mezcla).max())):.1f} dBFS")
    print(f"  ganancia        {ganancia_total:+.1f} dB sobre la suma normalizada")
    print("\n  niveles por pista (LUFS):")
    for nombre, pista in [("A1 voz", A1), ("A2 música", A2),
                          ("A3 ambiente", A3), ("A4 efectos", A4)]:
        print(f"    {nombre:12s} {lufs(pista):6.1f}")
    print(f"\n  stems escritos en {AUDIO}")


if __name__ == "__main__":
    main()
