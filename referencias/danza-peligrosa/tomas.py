"""Tomas medidas de «El amor es una danza peligrosa», episodio 1 (doblado).

Cortes: ffmpeg `select=gt(scene,0.20)` → escenas.txt. Los tramos de menos de
0,5 s son destellos y se suman a la toma anterior (mismo criterio que la
réplica de @jcfdlw). Por toma se sacan tres cuadros —entrada, medio, salida—
a archivo (leer ffmpeg por tubería se cuelga en Windows) y se arma una hoja
de contacto por cada 8 tomas.

    /c/Python314/python -X utf8 tomas.py
"""
import json, re, subprocess
from pathlib import Path
from PIL import Image, ImageDraw

AQUI = Path(__file__).parent
VIDEO = AQUI.parent.parent / "Video realshort" / "Episodio 1 - [doblado] El amor es una danza peligrosa.mp4"
FF = "C:/ffmpeg-2026-04-09-git-d3d0b7a5ee-essentials_build/bin/ffmpeg.exe"
DURACION = 126.920272
MIN_TOMA = 0.5


def tomas():
    cortes = [float(x) for x in re.findall(r"pts_time:([\d.]+)", (AQUI / "escenas.txt").read_text())]
    bordes = [0.0]
    for c in cortes:
        if c - bordes[-1] >= MIN_TOMA:
            bordes.append(c)
    if DURACION - bordes[-1] < MIN_TOMA:
        bordes.pop()
    bordes.append(DURACION)
    return [{"n": i + 1, "desde": round(a, 3), "hasta": round(b, 3), "dura": round(b - a, 3)}
            for i, (a, b) in enumerate(zip(bordes, bordes[1:]))]


def cuadro(t, destino):
    if not destino.exists():
        subprocess.run([FF, "-v", "error", "-ss", f"{t:.3f}", "-i", str(VIDEO), "-frames:v", "1",
                        "-vf", "scale=240:-2", "-y", str(destino)], check=True)
    return destino


def main():
    ts = tomas()
    (AQUI / "tomas.json").write_text(json.dumps(ts, indent=1), encoding="utf-8")
    d = AQUI / "cuadros"
    d.mkdir(exist_ok=True)
    for t in ts:
        margen = min(0.15, t["dura"] / 4)
        t["cuadros"] = [cuadro(s, d / f"{t['n']:03d}-{k}.jpg") for k, s in
                        (("a", t["desde"] + margen), ("m", (t["desde"] + t["hasta"]) / 2),
                         ("z", t["hasta"] - margen))]
    # hojas: 8 tomas por hoja, cada toma una fila de 3 cuadros
    W, H = 240, 426
    for h in range(0, len(ts), 8):
        grupo = ts[h:h + 8]
        hoja = Image.new("RGB", (W * 3 * 2 + 20, (H + 24) * ((len(grupo) + 1) // 2)), "black")
        dib = ImageDraw.Draw(hoja)
        for i, t in enumerate(grupo):
            x0, y0 = (i % 2) * (W * 3 + 20), (i // 2) * (H + 24)
            dib.text((x0 + 4, y0 + 4), f"#{t['n']:02d}  {t['desde']:.2f}-{t['hasta']:.2f}  ({t['dura']:.2f}s)", fill="yellow")
            for k, p in enumerate(t["cuadros"]):
                hoja.paste(Image.open(p), (x0 + k * W, y0 + 24))
        hoja.save(AQUI / f"hoja-{h // 8 + 1:02d}.jpg", quality=85)
    durs = [t["dura"] for t in ts]
    print(f"{len(ts)} tomas · media {sum(durs) / len(durs):.2f} s · min {min(durs):.2f} · max {max(durs):.2f}")
    for t in ts:
        print(f"#{t['n']:02d} {t['desde']:7.2f} → {t['hasta']:7.2f}  {t['dura']:5.2f}")


if __name__ == "__main__":
    main()
