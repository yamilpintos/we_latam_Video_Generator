# -*- coding: utf-8 -*-
"""Separación voz/fondo en la GPU de vast.ai: la MISMA que `media.separar`, en la 4090 en vez de la CPU.

POR QUÉ (medido): el modo "pistas" (aprobado de oído 11-sep) separa el original y el doblado. En esta PC eso son
~15 min de CPU por minuto de película (Goazen, 3 min: 46 min) → una película de 80 min tarda ~20 h. En la 4090
el mismo BS-RoFormer separó 45 min de Chiquititas en ~10 min.

CÓMO. Usa la instancia que dejó `dubai_v2/docker/vast.py` (registrada en `docker/_instancia.json`; se prepara con
`python docker/vast.py alquilar` + `subir` + `instalar`). Sube el wav por scp, corre allá el separador del motor
(`_work/ab_scribe/sep_replicate.py --backend local`, las mismas salidas `vocals_clean.wav` / `music_effects.wav`
que espera la app) y baja las dos pistas. Sin instancia, o si algo falla, devuelve None: `web._procesar` ya sabe
caer al modo "mezcla" y lo dice en el log.

Se activa con `DOBLAJE_SEP_REMOTO=vast` (config.SEP_REMOTO). No alquila ni destruye nada: la instancia cobra por
hora mientras exista, así que su ciclo de vida lo decide quien la prendió (`vast.py destruir --si`).
"""
from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path

from . import config as C

INSTANCIA = C.FOTON / "dubai_v2" / "docker" / "_instancia.json"
CLAVE_SSH = Path.home() / ".ssh" / "id_ed25519"
SEPARADOR_REMOTO = "/motor/dubai_v2/_work/ab_scribe/sep_replicate.py"
PY_REMOTO = "/opt/venv/bin/python"
TOPE_S = 7200            # tope por separación (2 h): una película de 78 min tardó 26 min con la subida


def instancia() -> tuple[str, int] | None:
    try:
        i = json.loads(INSTANCIA.read_text(encoding="utf-8"))
        return i["host"], int(i["port"])
    except Exception:
        return None


def disponible() -> bool:
    return instancia() is not None


def _ssh(host: str, port: int, cmd: str, timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(["ssh", "-i", str(CLAVE_SSH), "-p", str(port), "-o", "StrictHostKeyChecking=accept-new",
                           "-o", "BatchMode=yes", "-o", "ConnectTimeout=30", f"root@{host}", cmd],
                          capture_output=True, text=True, errors="replace", timeout=timeout)


def _scp(src: str, dst: str, port: int, timeout: float) -> bool:
    r = subprocess.run(["scp", "-q", "-i", str(CLAVE_SSH), "-P", str(port), "-o", "StrictHostKeyChecking=accept-new",
                        "-o", "BatchMode=yes", src, dst], capture_output=True, text=True, errors="replace", timeout=timeout)
    return r.returncode == 0


def separar(audio: Path, out_dir: Path, log=None) -> tuple[Path, Path] | None:
    """(vocals_clean.wav, music_effects.wav) en `out_dir`, separados en la GPU de vast, o None."""
    di = log or (lambda m: None)
    # ★ 22-sep: si ya está separado, no se vuelve a separar. Separar el original de una película son ~26 min de GPU
    #   y no cambia nunca: se calcula una vez y se reusa (para el doblaje y para cada parche).
    v0, f0 = out_dir / "vocals_clean.wav", out_dir / "music_effects.wav"
    if v0.exists() and f0.exists() and v0.stat().st_size > 1000 and f0.stat().st_size > 1000:
        di(f"ya estaba separado, se reusa: {out_dir.name}")
        return v0, f0
    hp = instancia()
    if not hp:
        di(f"separación en vast pedida pero no hay instancia registrada ({INSTANCIA.name}): caigo a lo que haya")
        return None
    host, port = hp
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"/motor/sep_app/{uuid.uuid4().hex[:12]}"
    t0 = time.time()
    try:
        r = _ssh(host, port, f"mkdir -p {base}/out", 60)
        if r.returncode != 0:
            di(f"vast no responde por ssh: {(r.stderr or '').strip()[-200:]}")
            return None
        if not _scp(str(audio), f"root@{host}:{base}/in.wav", port, 1800):
            di("no pude subir el audio a vast")
            return None
        r = _ssh(host, port, f"cd /motor/dubai_v2/_work/ab_scribe && PYTHONIOENCODING=utf-8 timeout {TOPE_S} "
                             f"{PY_REMOTO} -u {SEPARADOR_REMOTO} {base}/in.wav {base}/out --backend local", TOPE_S + 120)
        if r.returncode != 0:
            di("separador en vast falló: " + ((r.stdout or "") + (r.stderr or ""))[-300:].strip())
            return None
        v, f = out_dir / "vocals_clean.wav", out_dir / "music_effects.wav"
        for nombre, dst in (("vocals_clean.wav", v), ("music_effects.wav", f)):
            if not _scp(f"root@{host}:{base}/out/{nombre}", str(dst), port, 1800):
                di(f"no pude bajar {nombre} de vast")
                return None
        di(f"separado en vast en {time.time() - t0:.0f} s ({audio.name})")
        return v, f
    except subprocess.TimeoutExpired:
        di(f"la separación en vast pasó el tope ({TOPE_S} s)")
        return None
    finally:
        try:
            _ssh(host, port, f"rm -rf {base}", 60)          # no dejar audio del cliente en una máquina alquilada
        except Exception:
            pass
