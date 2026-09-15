# -*- coding: utf-8 -*-
"""La imagen sigue a la voz.

El original clava sus cortes a su voz (22,7 cps). La nuestra (Kate, 16,7 cps
medidos) no entra en esas ventanas ni comprimida al tope de 1,30×, así que en
la primera corrida la voz se fue atrasando y a partir de la mitad contaba una
toma mientras se veía la siguiente.

Esto hace lo que hace un editor: **mueve cada corte a donde cae la frase**.
Se calcula una sola línea de tiempo nueva a partir de las duraciones medidas
de las 92 líneas (`desvio_voz.json`), y la usan las dos puntas —`armar.py`
para las duraciones de los planos y `mezclar_replica.py` para colocar la voz—
de modo que coincidan por construcción.

Reglas de colocación (las mismas de la primera corrida):
  · cada línea se comprime hasta TOPE (1,30×) como máximo;
  · nunca arranca antes de su marca del original;
  · nunca pisa a la anterior.
"""
import json
from pathlib import Path

AQUI = Path(__file__).parent
TOPE = 1.30


def lineas(tope: float = TOPE) -> list[dict]:
    """Cada línea con su arranque nuevo (`ini`), su duración ya comprimida
    (`largo`) y el factor usado."""
    filas = json.loads((AQUI / "desvio_voz.json").read_text(encoding="utf-8"))
    filas.sort(key=lambda f: f["t"])
    out, reloj = [], 0.0
    for f in filas:
        usado = min(f["factor"], tope) if f["factor"] > 1.0 else 1.0
        largo = f["dur"] / usado
        ini = max(f["t"], reloj)
        reloj = ini + largo
        out.append(dict(f, usado=round(usado, 4), largo=round(largo, 3),
                        ini=round(ini, 3), fin=round(reloj, 3)))
    return out


def mapa(tope: float = TOPE):
    """Función original→nuevo, lineal a trozos entre las marcas de las líneas.
    Antes de la primera línea y después de la última se prolonga con el último
    desfase, no con la pendiente: así la placa final conserva su duración."""
    ls = lineas(tope)
    xs = [l["t"] for l in ls]
    ys = [l["ini"] for l in ls]

    def f(t: float) -> float:
        if t <= xs[0]:
            return t + (ys[0] - xs[0])
        if t >= xs[-1]:
            return t + (ys[-1] - xs[-1])
        for k in range(1, len(xs)):
            if t <= xs[k]:
                x0, x1, y0, y1 = xs[k - 1], xs[k], ys[k - 1], ys[k]
                if x1 == x0:
                    return y1
                return y0 + (t - x0) * (y1 - y0) / (x1 - x0)
        return t
    return f


if __name__ == "__main__":
    ls = lineas()
    f = mapa()
    print(f"{len(ls)} líneas · la voz termina en {ls[-1]['fin']:.1f} s "
          f"(original 181,4) · el segundo 181,4 pasa a {f(181.4):.1f}")
