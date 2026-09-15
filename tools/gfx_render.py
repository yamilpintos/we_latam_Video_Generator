"""
Renderiza los 12 planos gráficos del video: 5 s cada uno, 1920x1080, 24 fps.

Sistema de diseño (pipeline/05-CAPA-B3-gfx.md): fondo negro, trazo verde fósforo,
énfasis ámbar, tipografía monoespaciada, grano de película al 8 %. Entrada por
barrido de 0,4 s, salida por fundido de 0,3 s.

    python tools/gfx_render.py
    python tools/gfx_render.py --solo S06-P04
"""

import argparse
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "mars-climate-orbiter" / "gfx"
FF = ROOT / ".venv-depthflow" / "Scripts" / "ffmpeg.exe"
W, H, FPS, DUR = 1920, 1080, 24, 5.0

FONDO = (8, 8, 10)
VERDE = (74, 224, 122)
AMBAR = (224, 162, 74)
ROJO = (199, 80, 60)
TENUE = (34, 60, 44)


def fuente(px):
    for f in ("consola.ttf", "cour.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            continue
    return ImageFont.load_default()


def suave(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def centrado(d, txt, y, fnt, color):
    x0, y0, x1, y1 = d.textbbox((0, 0), txt, font=fnt)
    d.text(((W - (x1 - x0)) / 2 - x0, y), txt, font=fnt, fill=color)
    return x1 - x0


# ── los doce gráficos ─────────────────────────────────────────────────────────

def osciloscopio(d, t):
    """S01-P02 · la señal cae a línea plana en el segundo 2."""
    for x in range(0, W, 160):
        d.line([(x, 240), (x, 840)], fill=TENUE, width=1)
    for y in range(240, 841, 100):
        d.line([(0, y), (W, y)], fill=TENUE, width=1)
    corte = 2.0
    pts, avance = [], int(W * min(t / 4.2, 1.0))
    for x in range(0, avance):
        tt = x / W * 4.2
        y = 540 + (0 if tt > corte else 130 * math.sin(tt * 22) * math.exp(-((tt - 1) ** 2) / 6))
        pts.append((x, y))
    if len(pts) > 1:
        d.line(pts, fill=VERDE, width=3)
    if t > corte:
        d.ellipse([int(W * corte / 4.2) - 6, 534, int(W * corte / 4.2) + 6, 546], fill=AMBAR)


def reglas(d, t):
    """S02-P02 · pulgadas contra centímetros: no encajan."""
    a = suave(min(t / 1.6, 1.0))
    y1, y2 = 420, 620
    d.line([(200, y1), (1720, y1)], fill=VERDE, width=3)
    for i in range(13):
        x = 200 + i * 126.7
        d.line([(x, y1), (x, y1 - 34)], fill=VERDE, width=2)
    off = 1720 - a * 1520
    d.line([(off - 1520 + 1520, y2), (200, y2)] if False else [(200, y2), (1720, y2)],
           fill=AMBAR, width=3)
    for i in range(31):
        x = 200 + i * 50.7 + (1 - a) * 300
        if 200 <= x <= 1720:
            d.line([(x, y2), (x, y2 + 34)], fill=AMBAR, width=2)
    f = fuente(30)
    d.text((200, y1 - 90), "PULGADAS", font=f, fill=VERDE)
    d.text((200, y2 + 60), "CENTIMETROS", font=f, fill=AMBAR)


def nueve(d, t):
    """S03-P02 · nueve causas; la primera en ámbar."""
    f = fuente(34)
    for i in range(9):
        if t < 0.35 + i * 0.42:
            continue
        a = suave(min((t - 0.35 - i * 0.42) / 0.35, 1.0))
        y = 250 + i * 66
        col = AMBAR if i == 0 else VERDE
        d.line([(660, y + 18), (660 + int(440 * a), y + 18)], fill=col, width=3)
        if a > 0.6:
            d.text((610, y), f"{i+1}", font=f, fill=col)
    if t > 4.0:
        d.line([(575, 316), (575, 830)], fill=VERDE, width=2)
        d.line([(575, 316), (600, 316)], fill=VERDE, width=2)
        d.line([(575, 830), (600, 830)], fill=VERDE, width=2)


def trayectoria(d, t):
    """S04-P06 · Type 2: arco de más de 180° alrededor del Sol."""
    cx, cy = W // 2, H // 2
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=AMBAR)
    for r, col in ((230, TENUE), (390, TENUE)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=col, width=2)
    a = suave(min(t / 4.0, 1.0))
    ang0, span = math.radians(200), math.radians(215) * a
    pts = []
    for k in range(120):
        u = k / 119
        ang = ang0 + span * u
        r = 230 + 160 * u
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    if len(pts) > 1:
        d.line(pts, fill=VERDE, width=4)
        d.ellipse([pts[-1][0] - 7, pts[-1][1] - 7, pts[-1][0] + 7, pts[-1][1] + 7], fill=VERDE)


def contador(d, t):
    """S05-P05 · las desaturaciones se acumulan."""
    n = int(suave(min(t / 4.0, 1.0)) * 340)
    for i in range(n):
        ang = i * 0.61
        r = 40 + i * 1.05
        x, y = W / 2 + r * math.cos(ang) * 1.7, H / 2 + r * math.sin(ang) * 0.85
        d.line([(x, y), (x + 9, y - 3)], fill=VERDE, width=2)
    f = fuente(78)
    centrado(d, f"{n}", 880, f, AMBAR)


def unidad_lbf(d, t):
    """S06-P03 · lbf·s, la unidad que escribía el archivo."""
    a = suave(min(t / 0.5, 1.0))
    f1, f2 = fuente(190), fuente(40)
    centrado(d, "lbf·s", 400, f1, VERDE)
    if t > 0.8:
        centrado(d, "LIBRA-FUERZA-SEGUNDO", 640, f2, TENUE)
    if int(t * 2) % 2 == 0:
        d.rectangle([W // 2 + 250, 430, W // 2 + 272, 560], fill=VERDE)


def unidad_ns(d, t):
    """S06-P04 · N·s reemplaza a lbf·s, y aparece el factor."""
    f1, f2, f3 = fuente(190), fuente(40), fuente(64)
    if t < 0.5:
        a = 1 - suave(t / 0.5)
        centrado(d, "lbf·s", 400, f1, tuple(int(c * a) for c in VERDE))
    else:
        centrado(d, "N·s", 400, f1, VERDE)
        centrado(d, "NEWTON-SEGUNDO", 640, f2, TENUE)
    if t > 2.5:
        a = suave(min((t - 2.5) / 0.5, 1.0))
        y = 790
        d.line([(700, y), (700 + int(520 * a), y)], fill=AMBAR, width=4)
        if a > 0.9:
            d.polygon([(1220, y), (1190, y - 14), (1190, y + 14)], fill=AMBAR)
            centrado(d, "× 4,45", y + 30, f3, AMBAR)


def diez_a_445(d, t):
    """S06-P06 · el 10 se transforma en 44,5."""
    f1, f2 = fuente(240), fuente(44)
    if t < 1.5:
        centrado(d, "10", 380, f1, VERDE)
    else:
        a = suave(min((t - 1.5) / 0.7, 1.0))
        esc = int(240 * (1 + 0.35 * a))
        centrado(d, "44,5", 380 - int(30 * a), fuente(esc), AMBAR)
    centrado(d, "N·s", 720, f2, TENUE)


def flecha_sola(d, t):
    """S07-P01 · un solo empujón no desvía la trayectoria."""
    y = H // 2
    d.line([(180, y), (1740, y)], fill=TENUE, width=2)
    a = suave(min(t / 1.2, 1.0))
    d.line([(180, y), (180 + int(1560 * a), y)], fill=VERDE, width=4)
    if t > 1.4:
        x = 900
        d.line([(x, y), (x, y - 26)], fill=AMBAR, width=3)
        d.polygon([(x, y - 34), (x - 8, y - 22), (x + 8, y - 22)], fill=AMBAR)
        f = fuente(32)
        d.text((x + 24, y - 46), "1 impulso", font=f, fill=AMBAR)
    if t > 3.2:
        f = fuente(38)
        centrado(d, "sin desviación medible", y + 90, f, TENUE)


def barras(d, t):
    """S07-P06 · esperado contra real."""
    f, fp = fuente(36), fuente(30)
    base, alto = 880, 620
    a = suave(min(t / 3.2, 1.0))
    he = int(alto * 0.09 * min(a * 3, 1.0))
    hr = int(alto * a)
    d.rectangle([620, base - he, 800, base], fill=VERDE)
    d.rectangle([1120, base - hr, 1300, base], fill=AMBAR)
    d.text((618, base + 20), "ESPERADO", font=fp, fill=VERDE)
    d.text((1122, base + 20), "REAL", font=fp, fill=AMBAR)
    if t > 3.6:
        centrado(d, "× 10–14", 190, f, AMBAR)


def acumulacion(d, t):
    """S08-P01 · miles de flechas diminutas se agrupan en una."""
    a = suave(min(t / 3.0, 1.0))
    rng = np.random.default_rng(7)
    pts = rng.uniform([120, 180], [1800, 900], size=(320, 2))
    cx, cy = W / 2, 560
    for px, py in pts:
        x = px + (cx - px) * a
        y = py + (cy - py) * a
        d.line([(x, y), (x + 10, y + 3)], fill=VERDE, width=2)
    if t > 3.2:
        b = suave(min((t - 3.2) / 0.8, 1.0))
        d.line([(cx - 260, cy), (cx - 260 + int(520 * b), cy)], fill=AMBAR, width=8)
        if b > 0.9:
            d.polygon([(cx + 290, cy), (cx + 250, cy - 20), (cx + 250, cy + 20)], fill=AMBAR)


def doppler(d, t):
    """S09-P03 · la componente que el Doppler ve y la que no."""
    f = fuente(30)
    y = 560
    for x in range(200, 1721, 26):
        d.line([(x, y), (x + 13, y)], fill=TENUE, width=2)
    d.text((200, y - 52), "TIERRA", font=f, fill=TENUE)
    d.text((1600, y - 52), "NAVE", font=f, fill=TENUE)
    if t > 0.4:
        d.line([(960, y), (1180, y - 190)], fill=AMBAR, width=5)
        d.polygon([(1190, y - 200), (1160, y - 190), (1178, y - 162)], fill=AMBAR)
    if t > 1.8:
        a = suave(min((t - 1.8) / 1.0, 1.0))
        d.line([(960, y), (960 + int(220 * a), y)], fill=VERDE, width=5)
        d.text((1000, y + 24), "lo que ve el Doppler", font=f, fill=VERDE)
    if t > 3.0:
        b = suave(min((t - 3.0) / 1.2, 1.0))
        col = tuple(int(c * (1 - 0.85 * b)) for c in AMBAR)
        d.line([(1180, y), (1180, y - 190)], fill=col, width=5)
        if b < 0.7:
            d.text((1210, y - 130), "lo que no ve", font=f,
                   fill=tuple(int(c * (1 - b)) for c in AMBAR))


GFX = [
    ("S01-P02", osciloscopio), ("S02-P02", reglas),      ("S03-P02", nueve),
    ("S04-P06", trayectoria),  ("S05-P05", contador),    ("S06-P03", unidad_lbf),
    ("S06-P04", unidad_ns),    ("S06-P06", diez_a_445),  ("S07-P01", flecha_sola),
    ("S07-P06", barras),       ("S08-P01", acumulacion), ("S09-P03", doppler),
]


def render(sid, fn):
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"GFX_{sid}.mp4"
    p = subprocess.Popen(
        [str(FF), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
         "-preset", "slow", "-crf", "16", "-pix_fmt", "yuv420p", str(dst)],
        stdin=subprocess.PIPE)
    rng = np.random.default_rng(3)
    n = int(DUR * FPS)
    for k in range(n):
        t = k / FPS
        im = Image.new("RGB", (W, H), FONDO)
        fn(ImageDraw.Draw(im), t)
        a = np.asarray(im, dtype=np.int16)
        # barrido de entrada
        if t < 0.4:
            corte = int(W * suave(t / 0.4))
            a[:, corte:] = FONDO
        # fundido de salida
        if t > DUR - 0.3:
            a = (a * (1 - suave((t - (DUR - 0.3)) / 0.3))).astype(np.int16)
        # grano de película al 8 %
        a = np.clip(a + rng.normal(0, 5.5, a.shape), 0, 255)
        p.stdin.write(a.astype(np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", default="")
    args = ap.parse_args()
    hechos = 0
    for sid, fn in GFX:
        if args.solo and sid != args.solo:
            continue
        dst = render(sid, fn)
        print(f"  {sid}  ->  {dst.name}  ({dst.stat().st_size/1024:.0f} KB)")
        hechos += 1
    print(f"\n{hechos} gráficos de {DUR:.0f} s a {W}x{H} / {FPS} fps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
