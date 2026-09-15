"""La grilla de duraciones de MiniMax H3.

H3 acepta `length = 17k + 5` fotogramas a 24 fps y está entrenado entre 124 y
362. Eso da planos de 5,17 a 15,08 s. Fuera de ahí no está roto: está
adivinando. Cualquier duración que pida el director se acomoda al valor más
cercano de la grilla, y el resto del pipeline trabaja siempre con el valor real.
"""
from __future__ import annotations

FPS = 24
K_MIN, K_MAX = 7, 21
GRILLA: list[tuple[int, float]] = [(17 * k + 5, (17 * k + 5) / FPS) for k in range(K_MIN, K_MAX + 1)]
MINIMO = GRILLA[0][1]      # 5.167 s · 124 fotogramas
MAXIMO = GRILLA[-1][1]     # 15.083 s · 362 fotogramas


def encajar(segundos: float) -> tuple[int, float]:
    """(length, segundos_reales) del punto de la grilla más cercano."""
    return min(GRILLA, key=lambda g: abs(g[1] - segundos))


def en_rango(length: int) -> bool:
    return GRILLA[0][0] <= length <= GRILLA[-1][0]


def mmss(segundos: float) -> str:
    m, s = divmod(segundos, 60)
    return f"{int(m)}:{s:04.1f}"
