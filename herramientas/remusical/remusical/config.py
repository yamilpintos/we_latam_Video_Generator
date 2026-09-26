# -*- coding: utf-8 -*-
"""Configuración única de ReMusical. Todo lo que es una ruta o un umbral vive acá."""
import os
from pathlib import Path

PAQUETE = Path(__file__).resolve().parent              # .../remusical
RAIZ = PAQUETE.parent                                  # la carpeta de la app
FOTON = Path(os.getenv("FOTON", str(RAIZ.parent.parent.parent if RAIZ.parent.name == "apps" else RAIZ.parent)))


def _ffmpeg() -> str:
    """FFMPEG del entorno; si no, el de dubai_v2 si existe; si no, el del PATH."""
    if os.getenv("FFMPEG"):
        return os.environ["FFMPEG"]
    local = FOTON / "dubai_v2" / "_bin" / "ffmpeg.exe"
    return str(local) if local.exists() else "ffmpeg"


def _py_separador() -> str:
    """El Python con audio-separator. En la notebook es un 3.11 aparte; en el contenedor
    de Replicate es el mismo intérprete (todo vive en un solo Python)."""
    import sys
    cand = os.getenv("PY311", r"C:/Users/Yamil/AppData/Local/Programs/Python/Python311/python.exe")
    return cand if Path(cand).exists() else sys.executable


# ---- binarios ----
FFMPEG = _ffmpeg()
PY311 = _py_separador()
SEP_RUN = str(PAQUETE / "_sep_run.py")                 # vendoreado: la app no depende de dubai_v2

# ---- trabajo ----
TRABAJO = Path(os.getenv("REMUSICAL_TRABAJO", str(RAIZ / "_trabajo")))
CACHE_SEP = TRABAJO / "_cache_separacion"

SR = 48000
PREFIJO = "re-musical"

# ---- detección de música (AudioSet) ----
AST_MODELO = "MIT/ast-finetuned-audioset-10-10-0.4593"
AST_VENTANA = 4.0
AST_PASO = 1.0            # s. 2.5 para un mapa rápido; 1.0 para bordes finos
U_MUSICA = 0.30           # validado contra 2 videos: ver dubai-alcance-detector-musica
REGION_MIN = 3.0          # s: islas más cortas se descartan
HUECO_MAX = 3.0           # s: huecos más cortos se rellenan
FUSION_MAX = 5.0          # s: regiones más cercanas se funden
MARGEN_SEP = 12.0         # s a cada lado de la región que se separan además

# ---- generación: 1 take BAJO DEMANDA ----
# Se genera UN take por pista y se mide contra la original. Sólo si lo descalifican
# (drone, p(música) baja) o se parece poco (distancia > DIST_MAX) se pide otro, hasta
# TAKES_MAX. Antes eran 3 fijos y se tiraban 2 de cada 3: en 66 takes reales sólo 1 fue
# descalificado, así que la elección "el mejor de 3 buenos" costaba 3x para ganar poco.
TAKES_MAX = int(os.getenv("REMUSICAL_TAKES", "3"))
DIST_MAX = float(os.getenv("REMUSICAL_DIST_MAX", "0.45"))   # medido: buenos 0,15-0,39; huecos/retumbe 0,58-0,76
MODELO_MUSICA = "music_v2"
HOLGURA_TEMA = 10.0       # s de más que se generan para poder anclar el fade

# ---- montaje ----
DUCK_DB = 9.0
U_VOZ_DB = -42.0
ATAQUE_S, SALIDA_S = 0.15, 0.70

# ---- guardas ----
TOL_NIVEL_DB = 3.0
REINTENTOS = 2
