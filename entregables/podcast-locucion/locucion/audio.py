"""Armar el episodio: pegar las líneas con sus silencios, mezclar música con
ducking y masterizar a -14 LUFS.

El orden importa. Se pega primero con silencios EXACTOS (nada de concatenar y
después estirar), y recién al final se masteriza una sola vez sobre la mezcla
completa: masterizar línea por línea deja cada una con un volumen distinto y el
episodio suena a parches.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import DUCKING, LOUDNORM, MUSICA_DB, SR


class ErrorAudio(RuntimeError):
    pass


def _ffmpeg(*args: str) -> None:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                       capture_output=True, text=True)
    if r.returncode:
        raise ErrorAudio("ffmpeg: " + (r.stderr or "")[-600:])


def silencio(segundos: float, destino: Path) -> Path:
    _ffmpeg("-f", "lavfi", "-t", f"{max(0.001, segundos):.3f}",
            "-i", f"anullsrc=r={SR}:cl=mono", "-c:a", "pcm_s16le", str(destino))
    return destino


def pegar(wavs_y_pausas: list[tuple[Path, float]], arranque: float,
          destino: Path, tmp: Path) -> Path:
    """`wavs_y_pausas` = [(wav de la línea, silencio que va DESPUÉS), …].
    Arranca con `arranque` segundos de silencio."""
    tmp.mkdir(parents=True, exist_ok=True)
    partes: list[Path] = []
    if arranque > 0:
        partes.append(silencio(arranque, tmp / "s_ini.wav"))
    for i, (wav, pausa) in enumerate(wavs_y_pausas):
        partes.append(wav)
        if pausa > 0:
            partes.append(silencio(pausa, tmp / f"s_{i:04d}.wav"))
    lista = tmp / "lista.txt"
    lista.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in partes), encoding="utf-8")
    _ffmpeg("-f", "concat", "-safe", "0", "-i", str(lista),
            "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "1", str(destino))
    return destino


def masterizar(voz: Path, destino: Path, musica: Path | None = None,
               musica_db: float = MUSICA_DB, bitrate: str = "192k") -> Path:
    """Mezcla (voz + música con ducking) y masteriza a -14 LUFS.

    Sin música, sólo masteriza. La música NO baja «a mano»: baja sola cuando
    entra la voz (`sidechaincompress`), que es lo que suena profesional — un
    volumen fijo tapa la voz en los pasajes suaves o deja huecos en los fuertes.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    if musica:
        filtro = (f"[0:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo[voz];"
                  f"[1:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,"
                  f"afade=t=in:st=0:d=2[mus0];"
                  f"[mus0][voz]{DUCKING}[musd];"
                  f"[musd]volume={musica_db}dB[mus];"
                  f"[voz][mus]amix=inputs=2:normalize=0:duration=first[mez];"
                  f"[mez]apad,{LOUDNORM},aresample={SR}[out]")
        _ffmpeg("-i", str(voz), "-i", str(musica), "-filter_complex", filtro,
                "-map", "[out]", "-c:a", "libmp3lame", "-b:a", bitrate, str(destino))
    else:
        _ffmpeg("-i", str(voz), "-af", f"{LOUDNORM},aresample={SR}",
                "-c:a", "libmp3lame", "-b:a", bitrate, str(destino))
    return destino


def medir_lufs(archivo: Path) -> float | None:
    """El volumen integrado real del archivo. Para verificar el máster: tiene
    que dar -14 ± 0,5."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(archivo),
                        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    import json
    import re
    m = re.search(r"\{[^{]*input_i[^}]*\}", r.stderr or "", re.S)
    if not m:
        return None
    try:
        return float(json.loads(m.group(0))["input_i"])
    except Exception:
        return None
