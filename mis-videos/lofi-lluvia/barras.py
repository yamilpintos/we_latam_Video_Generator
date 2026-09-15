"""Detecta barras negras (letterbox) pintadas dentro de un PNG.

nano banana en 16:9 con estilo «film frame» pinta a veces la imagen en 21:9
dentro del lienzo, con franjas negras arriba y abajo. Si la locación madre sale
así, todos los fotogramas que la usan de referencia la copian. Se mide la
luminancia media de las filas: una franja de más de 3 % de la altura por debajo
de 40/255 es barra (O05 de lofi-orbita tenía barras a 35).
"""
import sys
from pathlib import Path
from PIL import Image

def barras(png: Path, umbral: int = 40, plano: float = 2.0) -> tuple[int, int]:
    """Filas de barra: oscuras (media < umbral) Y planas (desvío < `plano`).
    Sólo «oscuras» marcaba como barra un estanque de noche entero (lofi-koi);
    una barra pintada es uniforme (desvío medido ≤ 1,2), la escena oscura no (deck del koi: 3-5)."""
    im = Image.open(png).convert("L")
    w, h = im.size
    px = im.load()
    xs = range(0, w, 8)
    def fila_barra(y):
        v = [px[x, y] for x in xs]
        m = sum(v) / len(v)
        sd = (sum((a - m) ** 2 for a in v) / len(v)) ** 0.5
        return m < umbral and sd < plano
    arriba = 0
    while arriba < h // 3 and fila_barra(arriba):
        arriba += 1
    abajo = 0
    while abajo < h // 3 and fila_barra(h - 1 - abajo):
        abajo += 1
    return arriba, abajo

def recortar(png: Path, destino: Path, ancho: int = 1344, alto: int = 768) -> None:
    """Quita las barras y recorta al centro a la relación pedida, escalando."""
    a, b = barras(png)
    im = Image.open(png).convert("RGB")
    w, h = im.size
    im = im.crop((0, a, w, h - b))
    w, h = im.size
    obj = ancho / alto
    if w / h > obj:
        nw = int(h * obj); x = (w - nw) // 2; im = im.crop((x, 0, x + nw, h))
    else:
        nh = int(w / obj); y = (h - nh) // 2; im = im.crop((0, y, w, y + nh))
    im.resize((ancho, alto), Image.LANCZOS).save(destino, "PNG")

if __name__ == "__main__":
    carpeta = Path(sys.argv[1] if len(sys.argv) > 1 else "assets")
    malos = 0
    for png in sorted(carpeta.glob("*.png")):
        a, b = barras(png)
        h = Image.open(png).size[1]
        con = (a + b) > 0.03 * h
        malos += con
        print(f"  {'BARRAS' if con else 'ok    '}  {png.name:<14} arriba {a:3d}  abajo {b:3d}  de {h}")
    print(f"{malos} con barras")
