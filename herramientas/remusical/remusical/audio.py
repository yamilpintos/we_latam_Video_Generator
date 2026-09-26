# -*- coding: utf-8 -*-
"""Utilidades de audio: extraer, leer a 48 kHz, medir."""
import hashlib
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from . import config as C


def extraer_audio(video: Path, dst: Path, sr: int = C.SR, canales: int = 2) -> Path:
    """Saca la pista de audio del video a WAV PCM 16 bit."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([C.FFMPEG, "-y", "-v", "error", "-i", str(video), "-vn",
                    "-ac", str(canales), "-ar", str(sr), "-c:a", "pcm_s16le", str(dst)],
                   check=True)
    return dst


def duracion_video(video: Path) -> float:
    r = subprocess.run([C.FFMPEG, "-hide_banner", "-i", str(video)],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration:" in line:
            h, m, s = line.split("Duration:")[1].split(",")[0].strip().split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    raise RuntimeError(f"ffmpeg no reportó duración de {video}")


def leer48(ruta: Path) -> np.ndarray:
    """Lee cualquier WAV y lo devuelve estéreo float64 a 48 kHz.
    ★ Los stems de audio-separator salen a 44100. Indexarlos como 48000 aceleró la
    narración 1,088x en una entrega. Acá se resamplea SIEMPRE y explícitamente."""
    x, sr = sf.read(str(ruta), always_2d=True)
    if sr != C.SR:
        x = resample_poly(x, C.SR, sr, axis=0)
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2].astype(np.float64)


def escribir(ruta: Path, x: np.ndarray, sr: int = C.SR, formato: str = "PCM_16"):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(ruta), x, sr, subtype=formato)


def mono(x: np.ndarray) -> np.ndarray:
    return x.mean(axis=1) if x.ndim == 2 else x


def db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-12))


def nivel_banda(x: np.ndarray, sr: int = C.SR, lo: float = 250.0, hi: float = 8000.0) -> float:
    """Nivel (dB) de la energía entre lo y hi Hz. Es la vara para comparar MÚSICA: el
    viento y el motor viven abajo de 250 Hz y contaminan el RMS total."""
    import librosa
    y = mono(x).astype(np.float32)
    if len(y) < 2048:
        return -120.0
    S = np.abs(librosa.stft(y, n_fft=2048)) ** 2
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    m = (f >= lo) & (f < hi)
    return float(10 * np.log10(S[m].sum() / max(1, S.shape[1]) + 1e-12))


def a16k(x: np.ndarray, sr: int = C.SR) -> np.ndarray:
    return resample_poly(mono(x), 16000, sr)


def hash_archivo(ruta: Path) -> str:
    h = hashlib.sha1()
    with open(ruta, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def mmss(s: float) -> str:
    return f"{int(s)//60:d}:{s%60:05.2f}"
