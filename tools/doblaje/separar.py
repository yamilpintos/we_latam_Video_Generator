"""Separa voz de ambiente con demucs, sin pasar por su cargador de audio.

Dos rodeos necesarios en esta maquina:
  · torchcodec tiene una DLL rota, y es lo que usa la CLI de demucs para leer
    el archivo. Cargamos el WAV con soundfile.
  · demucs.api no existe en esta instalacion (4.0.1 sin ese modulo), asi que
    vamos por pretrained + apply_model, que es la capa de abajo.
"""
import numpy as np, soundfile as sf, torch, torchaudio
from demucs.pretrained import get_model
from demucs.apply import apply_model

x, sr = sf.read("original.wav", dtype="float32")
if x.ndim == 1: x = np.stack([x, x], 1)
wav = torch.from_numpy(x.T).contiguous()
print(f"entrada: {wav.shape[1]/sr:.1f} s, {sr} Hz", flush=True)

model = get_model("htdemucs"); model.eval()
msr = model.samplerate
if sr != msr:
    wav = torchaudio.functional.resample(wav, sr, msr)
    print(f"remuestreado a {msr} Hz", flush=True)

# Normalizacion estandar de demucs: se deshace despues sobre las salidas.
ref = wav.mean(0)
med, desv = ref.mean(), ref.std()
wav_n = (wav - med) / desv

with torch.no_grad():
    fuentes = apply_model(model, wav_n[None], device="cpu", progress=True,
                          split=True, segment=7, overlap=0.15)[0]
fuentes = fuentes * desv + med

idx = {n: i for i, n in enumerate(model.sources)}
voz = fuentes[idx["vocals"]]
resto = sum(fuentes[i] for n, i in idx.items() if n != "vocals")

if msr != sr:
    voz = torchaudio.functional.resample(voz, msr, sr)
    resto = torchaudio.functional.resample(resto, msr, sr)

sf.write("vocals.wav", voz.numpy().T, sr)
sf.write("ambiente.wav", resto.numpy().T, sr)
print(f"OK  vocals.wav + ambiente.wav a {sr} Hz")
