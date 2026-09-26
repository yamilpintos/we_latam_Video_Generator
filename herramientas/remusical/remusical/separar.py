# -*- coding: utf-8 -*-
"""
Separación voz / instrumental con BS-Roformer (sep_run.py, Python 3.11), SÓLO sobre
las regiones con música más un margen. Caché por hash del trozo: un trabajo pago
no se repite.

Medido: 12,5x tiempo real en CPU. Separar 2 min de regiones son 25 min; separar
el video entero de 10 min serían 2 h. Por eso se separa lo mínimo.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np

from . import config as C
from .audio import escribir, leer48, hash_archivo, mono
from .mapa import Region

SUF = "_model_bs_roformer_ep_317_sdr_12.wav"

# ---- separación REMOTA (opcional): la misma _sep_run.py, pero en una GPU alquilada ----
# Se activa con REMUSICAL_SEP_REMOTO=vast. Usa la instancia que dejó `dubai_v2/docker/vast.py
# alquilar` (registrada en dubai_v2/docker/_instancia.json) y un venv de allá con audio-separator
# (REMUSICAL_SEP_REMOTO_PY, default /opt/venv/bin/python). Sube el trozo por scp, corre _sep_run.py
# allá y baja los dos stems al mismo caché por hash. No alquila ni destruye nada: el ciclo de vida
# de la máquina lo maneja quien la prendió.
REMOTO_INSTANCIA = C.FOTON / "dubai_v2" / "docker" / "_instancia.json"
REMOTO_SSH_KEY = Path.home() / ".ssh" / "id_ed25519"
REMOTO_PY = os.getenv("REMUSICAL_SEP_REMOTO_PY", "/opt/venv/bin/python")
REMOTO_BASE = "/motor/remusical_sep"


def _remoto_instancia() -> tuple[str, int]:
    import json
    i = json.loads(REMOTO_INSTANCIA.read_text(encoding="utf-8"))
    return i["host"], int(i["port"])


def _ssh(host, port, cmd, timeout):
    return subprocess.run(["ssh", "-i", str(REMOTO_SSH_KEY), "-p", str(port), "-o", "StrictHostKeyChecking=accept-new",
                           "-o", "BatchMode=yes", "-o", "ConnectTimeout=30", f"root@{host}", cmd],
                          capture_output=True, text=True, errors="replace", timeout=timeout)


def _scp(src, dst, port, timeout):
    r = subprocess.run(["scp", "-q", "-i", str(REMOTO_SSH_KEY), "-P", str(port), "-o", "StrictHostKeyChecking=accept-new",
                        "-o", "BatchMode=yes", src, dst], capture_output=True, text=True, errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"scp falló ({src} -> {dst}): {r.stderr[-300:]}")


def _separar_trozo_remoto(wav44: Path, cdir: Path, tope: int, log=print) -> None:
    """Corre _sep_run.py en la GPU de Vast y deja los stems crudos en cdir (mismos nombres que local)."""
    import uuid
    host, port = _remoto_instancia()
    base = f"{REMOTO_BASE}/{uuid.uuid4().hex[:12]}"
    try:
        r = _ssh(host, port, f"mkdir -p {base}/out", 60)
        if r.returncode != 0:
            raise RuntimeError(f"vast no responde por ssh: {r.stderr[-300:]}")
        _scp(C.SEP_RUN, f"root@{host}:{REMOTO_BASE}/_sep_run.py", port, 120)
        _scp(str(wav44), f"root@{host}:{base}/in.wav", port, 1800)
        r = _ssh(host, port, f"cd {base} && PYTHONIOENCODING=utf-8 timeout {tope} {REMOTO_PY} -u "
                             f"{REMOTO_BASE}/_sep_run.py {base}/in.wav {base}/out", tope + 120)
        if r.returncode != 0:
            raise RuntimeError("sep_run remoto falló:\n" + (r.stdout + r.stderr)[-1500:])
        r = _ssh(host, port, f"ls -1 {base}/out", 60)
        nombres = [n for n in r.stdout.splitlines() if n.strip().endswith(".wav")]
        if not nombres:
            raise RuntimeError(f"sep_run remoto no dejó wavs: {(r.stdout + r.stderr)[-300:]}")
        for n in nombres:
            # el scp de Windows no entiende paréntesis ni en el origen remoto ni en el destino local:
            # se renombra allá a un nombre simple, se baja con ese nombre y acá se repone el original
            simple = "voz_cruda.wav" if "(Vocals)" in n else "inst_cruda.wav" if "(Instrumental)" in n else None
            if not simple:
                continue
            _ssh(host, port, f"mv '{base}/out/{n}' {base}/out/{simple}", 60)
            _scp(f"root@{host}:{base}/out/{simple}", str(cdir / simple), port, 1800)
            os.replace(cdir / simple, cdir / n)
    finally:
        try:
            _ssh(host, port, f"rm -rf {base}", 60)      # no dejar audio del cliente en una máquina alquilada
        except Exception:
            pass


def _separar_trozo(wav44: Path, log=print) -> tuple[Path, Path]:
    """Devuelve (voz, instrumental) de un trozo, usando caché por hash."""
    h = hash_archivo(wav44)
    cdir = C.CACHE_SEP / h
    voz, inst = cdir / "voz.wav", cdir / "inst.wav"
    if voz.exists() and inst.exists():
        log(f"    caché: {h}")
        return voz, inst
    cdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["PATH"] = str(Path(C.FFMPEG).parent) + os.pathsep + env.get("PATH", "")
    # Tope por trozo, PROPORCIONAL al largo: en CPU BS-Roformer va a ~12,5x tiempo real
    # (1 min de audio = 12,5 min de CPU), así que se da 30x de margen. En GPU sobra.
    # ★ La primera versión tenía un tope fijo de 900 s "porque 15 min de CPU son 1 h de
    #   audio" — al revés. Mató un trozo de 271 s que necesitaba 56 min.
    import soundfile as sf
    largo_s = sf.info(str(wav44)).duration
    tope = int(os.getenv("REMUSICAL_SEP_TIMEOUT_S", "0")) or max(900, int(largo_s * 30))
    if os.getenv("REMUSICAL_SEP_REMOTO", "").lower() == "vast":
        log(f"    separando en Vast (GPU): {wav44.name}")
        try:
            _separar_trozo_remoto(wav44, cdir, tope, log)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"sep_run remoto superó {tope} s en {wav44.name}: se corta")
    else:
        try:
            r = subprocess.run([C.PY311, C.SEP_RUN, str(wav44), str(cdir)],
                               capture_output=True, text=True, env=env, timeout=tope)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"sep_run superó {tope} s en {wav44.name} ({largo_s:.0f} s de audio): se corta")
        if r.returncode != 0:
            raise RuntimeError("sep_run falló:\n" + r.stderr[-1500:])
    salidas = list(cdir.glob("*.wav"))
    v = [s for s in salidas if "(Vocals)" in s.name]
    i = [s for s in salidas if "(Instrumental)" in s.name]
    if not v or not i:
        raise RuntimeError(f"sep_run no dejó los dos stems en {cdir}: {[s.name for s in salidas]}")
    v[0].rename(voz)
    i[0].rename(inst)
    return voz, inst


def separar_regiones(audio48: np.ndarray, regs: list[Region], trabajo: Path,
                     margen: float = C.MARGEN_SEP, log=print) -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (voz, inst) del largo del audio completo, con ceros fuera de las
    regiones separadas. Trozos = región ± margen, fundidos si se solapan."""
    from scipy.signal import resample_poly
    n = len(audio48)
    dur = n / C.SR
    trozos = []
    for r in regs:
        a, b = max(0.0, r.inicio - margen), min(dur, r.fin + margen)
        if trozos and a <= trozos[-1][1]:
            trozos[-1][1] = max(trozos[-1][1], b)
        else:
            trozos.append([a, b])
    voz = np.zeros((n, 2))
    inst = np.zeros((n, 2))
    tdir = trabajo / "trozos"
    tdir.mkdir(parents=True, exist_ok=True)

    # Los trozos se separan EN PARALELO, de a WORKERS: el techo en la notebook es la RAM
    # (12,4 GB: caben 2 procesos de BS-Roformer), no la CPU. Medido: 2 workers = 1,7x.
    # Los trozos más largos primero, para que el final no quede esperando a uno solo.
    workers = int(os.getenv("REMUSICAL_SEP_WORKERS", "2"))
    orden = sorted(range(len(trozos)), key=lambda k: -(trozos[k][1] - trozos[k][0]))
    rutas = {}
    for k in orden:
        a, b = trozos[k]
        i0, i1 = int(a * C.SR), int(b * C.SR)
        w = tdir / f"trozo_{k:02d}.wav"
        if not w.exists():
            escribir(w, resample_poly(audio48[i0:i1], 44100, C.SR, axis=0), 44100)
        rutas[k] = w
    log(f"  separando {len(trozos)} trozos ({sum(b-a for a,b in trozos):.0f} s de audio) con {workers} en paralelo")

    def _uno(k):
        a, b = trozos[k]
        log(f"  separando trozo {k+1}/{len(trozos)}  {a:.1f}-{b:.1f}s  ({b-a:.0f}s)")
        return k, _separar_trozo(rutas[k], log)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for k, (pv, pi) in ex.map(_uno, orden):
            a, b = trozos[k]
            i0, i1 = int(a * C.SR), int(b * C.SR)
            v, ins = leer48(pv), leer48(pi)
            m = min(len(v), i1 - i0)
            voz[i0:i0 + m] = v[:m]
            inst[i0:i0 + m] = ins[:m]
            log(f"  trozo {k+1} listo")
    return voz, inst


def separar_todo(audio48: np.ndarray, trabajo: Path, trozo_s: float = 600.0, log=print):
    """Separación del archivo ENTERO por trozos de 10 min (para entregar stems completos).
    Es la opción lenta: 12,5x tiempo real en CPU."""
    dur = len(audio48) / C.SR
    regs = [Region(a, min(dur, a + trozo_s), "TODO", 1.0) for a in np.arange(0, dur, trozo_s)]
    return separar_regiones(audio48, regs, trabajo, margen=0.0, log=log)
