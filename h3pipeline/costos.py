"""Cuánto va a costar, calculado desde las mediciones reales de `COSTOS-H3.md`.

Todo lo de acá sale de corridas medidas en 4× RTX 5090 (32 GB) a 1344×768, con
first_frame y sin imágenes de referencia — que es exactamente el pipeline de
planos. Lo que es extrapolación está marcado como tal.

Las dos mediciones que sostienen la curva, a 8 pasos con turbo:

    10,1 s de video  →   6,6 min de GPU
    15,1 s de video  →  11,8 min de GPU

De ahí sale un costo fijo por clip de ~1,2 min (cargar el modelo, decodificar
los dos VAE, escribir el MP4) más una parte que crece con el largo elevado a
1,68 — superlineal, porque la atención crece con el cuadrado de la secuencia.
Un ajuste lineal de dos puntos daría minutos negativos para planos de 5 s, que
es justo el rango donde vive la mitad de un short. Por eso el modelo es este y
no una recta.

Honestidad sobre el rango: los dos puntos medidos son de 10 y 15 s. Para
planos de 5 a 7 s **esto extrapola por debajo del rango medido**. La primera
corrida imprime el tiempo real de cada plano y con eso se reajusta.
"""
from __future__ import annotations

from dataclasses import dataclass

# --- constantes medidas ------------------------------------------------------
FIJO_MIN = 1.2                  # minutos de costo fijo por clip
REF_SEG, REF_VAR_MIN = 10.1, 5.4    # el punto de anclaje, ya sin el fijo
EXPONENTE = 1.677               # ln(10.6/5.4) / ln(15.1/10.1)

FACTOR_PASOS = {4: 0.62, 8: 1.0, 20: 2.30}   # 20 pasos cuestan 2,3× lo que 8
FACTOR_REFS = 1.48              # las imágenes de referencia cuestan +48 %
FACTOR_REF_MAX = 1.08           # ref_image_size='max' cuesta +8 % y es la palanca
                                # de identidad: conviene dejarla puesta

DESCARGA_GB = {"solo_fl": 59, "completo": 106}   # SOLO_FL=1 saca los dos Ref2VA


@dataclass
class Maquina:
    """Lo que se alquila. `dph` es el precio por hora de la instancia entera."""
    dph: float = 1.909
    gpus: int = 4
    inet_down_mbps: float = 800.0
    nombre: str = "4× RTX 5090"

    @property
    def por_minuto(self) -> float:
        return self.dph / 60


def minutos_clip(segundos: float, pasos: int = 8, refs: bool = False,
                 ref_max: bool = False) -> float:
    """Minutos de GPU de un solo clip."""
    var = REF_VAR_MIN * (segundos / REF_SEG) ** EXPONENTE
    m = (FIJO_MIN + var) * FACTOR_PASOS.get(pasos, pasos / 8)
    if refs:
        m *= FACTOR_REFS
        if ref_max:
            m *= FACTOR_REF_MAX
    return m


def reparto(planos: list[dict], gpus: int = 4, pasos: int = 8) -> list[list[float]]:
    """Cómo cae el trabajo en cada placa. El runner reparte por índice
    (`i % total == gpu`): como ningún plano depende de otro, sale parejo solo."""
    carga: list[list[float]] = [[] for _ in range(gpus)]
    for i, p in enumerate(planos):
        carga[i % gpus].append(minutos_clip(p["segundos"], pasos))
    return carga


def minutos_descarga(gb: float, mbps: float) -> float:
    """El ancho de banda del host mueve más plata que el precio por hora: los
    mismos 59 GB son 4 minutos a 2000 Mbps y 262 a 30."""
    return gb * 8 * 1000 / mbps / 60 if mbps > 0 else float("inf")


@dataclass
class Estimacion:
    planos: int
    segundos_video: float
    minutos_gpu: float
    minutos_pared: float
    minutos_descarga: float
    maquina: Maquina
    pasos: int

    @property
    def costo_generacion(self) -> float:
        return self.minutos_pared * self.maquina.por_minuto

    @property
    def costo_descarga(self) -> float:
        return self.minutos_descarga * self.maquina.por_minuto

    @property
    def costo_total(self) -> float:
        return self.costo_generacion + self.costo_descarga

    @property
    def minutos_total(self) -> float:
        return self.minutos_pared + self.minutos_descarga

    def __str__(self) -> str:
        return "\n".join([
            f"{self.planos} planos · {self.segundos_video:.0f} s de video · "
            f"{self.pasos} pasos · {self.maquina.nombre} a ${self.maquina.dph:.3f}/h",
            f"  descarga de modelos ... {self.minutos_descarga:5.0f} min   "
            f"${self.costo_descarga:5.2f}   (a {self.maquina.inet_down_mbps:.0f} Mbps)",
            f"  GPU en total .......... {self.minutos_gpu:5.0f} min",
            f"  pared con {self.maquina.gpus} placas ... {self.minutos_pared:5.0f} min   "
            f"${self.costo_generacion:5.2f}",
            f"  TOTAL ................. {self.minutos_total:5.0f} min   "
            f"${self.costo_total:5.2f}",
        ])


def estimar(planos: list[dict], maquina: Maquina | None = None, pasos: int = 8,
            solo_fl: bool = True, refs: bool = False) -> Estimacion:
    """La cuenta completa: descargar los modelos + generar todos los planos."""
    m = maquina or Maquina()
    tiempos = [minutos_clip(p["segundos"], pasos, refs) for p in planos]
    carga = [[] for _ in range(m.gpus)]
    for i, t in enumerate(tiempos):
        carga[i % m.gpus].append(t)
    return Estimacion(
        planos=len(planos),
        segundos_video=sum(p["segundos"] for p in planos),
        minutos_gpu=sum(tiempos),
        # La pared la marca la placa que más tarda, no el promedio.
        minutos_pared=max((sum(c) for c in carga), default=0.0),
        minutos_descarga=minutos_descarga(
            DESCARGA_GB["solo_fl" if solo_fl else "completo"], m.inet_down_mbps),
        maquina=m, pasos=pasos)


def comparar(planos: list[dict], maquina: Maquina | None = None) -> str:
    """La misma lista de planos con cada configuración. Los pasos son la palanca
    de costo dominante: 20 pasos cuestan 2,3× lo que 8."""
    m = maquina or Maquina()
    L = [f"{len(planos)} planos · {sum(p['segundos'] for p in planos):.0f} s de video · "
         f"{m.nombre} a ${m.dph:.3f}/h", "",
         f"  {'config':<26} {'GPU':>7} {'pared':>7} {'costo':>8}"]
    for nombre, pasos in (("8 pasos + turbo", 8), ("4 pasos + turbo", 4),
                          ("20 pasos, sin turbo", 20)):
        e = estimar(planos, m, pasos)
        L.append(f"  {nombre:<26} {e.minutos_gpu:6.0f}m {e.minutos_pared:6.0f}m "
                 f"  ${e.costo_generacion:6.2f}")
    L += ["", "  (sin contar la descarga de modelos, que depende del host: "
          f"{minutos_descarga(DESCARGA_GB['solo_fl'], m.inet_down_mbps):.0f} min "
          f"a {m.inet_down_mbps:.0f} Mbps)"]
    return "\n".join(L)
