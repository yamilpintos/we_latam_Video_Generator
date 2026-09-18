"""Ubica en el MXF el cuadro que corresponde a un instante del archivo chico.
python buscar_offset.py <chico.mp4> <t_chico_seg> <mxf> <desde_seg> <hasta_seg>
Compara miniaturas en gris (96x72) por error cuadrático medio, a 5 muestras por segundo."""
import subprocess, sys, numpy as np
FF = r"..\..\.venv-depthflow\Scripts\ffmpeg.exe"
W, H = 96, 72
def miniaturas(archivo, ss, dur, vf_extra=""):
    cmd = [FF, "-v", "error", "-ss", str(ss), "-t", str(dur), "-i", archivo,
           "-vf", f"{vf_extra}fps=5,scale={W}:{H}:flags=area,format=gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (W * H)
    return np.frombuffer(raw[: n * W * H], np.uint8).reshape(n, H, W).astype(np.float32)
chico, t, mxf, desde, hasta = sys.argv[1], float(sys.argv[2]), sys.argv[3], float(sys.argv[4]), float(sys.argv[5])
ref = miniaturas(chico, t, 0.2)[0]
ref = (ref - ref.mean()) / (ref.std() + 1e-6)
cand = miniaturas(mxf, desde, hasta - desde, "crop=720:576:0:32,")
cand = (cand - cand.mean(axis=(1, 2), keepdims=True)) / (cand.std(axis=(1, 2), keepdims=True) + 1e-6)
err = ((cand - ref) ** 2).mean(axis=(1, 2))
orden = np.argsort(err)[:5]
for i in orden:
    print(f"  mxf t={desde + i / 5:8.2f} s  err={err[i]:.3f}")
mejor = desde + orden[0] / 5
print(f"MEJOR mxf={mejor:.2f} s  chico={t:.2f} s  desfase={mejor - t:+.2f} s  (2do mejor err {err[orden[1]]:.3f} vs {err[orden[0]]:.3f})")
