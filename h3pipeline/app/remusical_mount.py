"""ReMusical dentro de La Fábrica.

La herramienta vive ENTERA en `herramientas/remusical/`: es el mismo código que corre
sola con `python -m remusical.web` (motor + web + tandas + tests). Acá no se reescribe
nada: se la importa y se la monta en `/remusical/`. Ella calcula sus URLs del request
(`root_path`), así que no sabe que está montada y funciona igual en los dos lugares.

Lo único que hace este módulo, ANTES de importarla, es darle el mismo entorno que tenía
en su casa, sin que el usuario cargue dos veces las mismas claves:
  - ELEVENLABS_API_KEY: si no está en el entorno, la del .env de La Fábrica (`elevenlabs=`).
  - FFMPEG: el que resuelve La Fábrica (PATH o el de depthflow).
  - FOTON: la raíz del motor de doblaje si existe en esta PC (ahí ReMusical busca el
    ffmpeg de respaldo, el .env de dubai_v2 y la instancia de Vast para separar remoto).
Todo se puede fijar por entorno o en `herramientas/remusical/.env`; acá sólo hay defaults.

Si falta una dependencia (google-api-python-client…), La Fábrica arranca igual: `cargar()`
devuelve el error y el servidor lo muestra en /remusical/ en vez de caerse.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CARPETA = RAIZ / "herramientas" / "remusical"


def _cargar_env_propio() -> None:
    """El .env de la herramienta (herramientas/remusical/.env), ANTES de importarla: su
    config.py fija rutas (REMUSICAL_TRABAJO, PY311, FFMPEG…) al importarse, o sea antes de
    que ella misma lea el .env. Sola le pasa lo mismo; acá se lo damos a tiempo."""
    env = CARPETA / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if v:
                os.environ.setdefault(k.strip(), v)


def _preparar_entorno() -> None:
    from .. import config
    _cargar_env_propio()
    if not os.environ.get("ELEVENLABS_API_KEY"):
        try:
            k = config.leer_env("ELEVENLABS_API_KEY", obligatorio=False) or config.leer_env("elevenlabs", obligatorio=False)
        except Exception:
            k = None
        if k:
            os.environ["ELEVENLABS_API_KEY"] = k
    if not os.environ.get("FOTON"):
        foton = Path.home() / "Desktop" / "Foton"
        if (foton / "dubai_v2").exists():
            os.environ["FOTON"] = str(foton)
    # ffmpeg: ReMusical tiene el suyo de respaldo (FOTON/dubai_v2/_bin); si no está, el de La Fábrica
    propio = Path(os.environ.get("FOTON", "")) / "dubai_v2" / "_bin" / "ffmpeg.exe"
    if not os.environ.get("FFMPEG") and not propio.exists():
        try:
            os.environ["FFMPEG"] = config.ffmpeg()
        except Exception:
            pass


def cargar():
    """(app de ReMusical, "") si se pudo importar; (None, motivo) si no."""
    if not CARPETA.exists():
        return None, f"no está la carpeta {CARPETA}"
    _preparar_entorno()
    if str(CARPETA) not in sys.path:
        sys.path.insert(0, str(CARPETA))
    try:
        from remusical import web as rweb          # noqa: WPS433  (la herramienta, entera)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}\n\n{traceback.format_exc()[-1500:]}"
    return rweb.app, ""


def estado(error: str) -> dict:
    """Lo que la portada muestra en la puerta de ReMusical."""
    if error:
        return {"montada": False, "error": error.splitlines()[0],
                "instalar": "pip install -r herramientas/remusical/requirements.txt"}
    from remusical import web as rweb
    return {"montada": True,
            "google_configurado": bool(rweb.CLIENT_ID and rweb.CLIENT_SECRET),
            "eleven": bool(os.environ.get("ELEVENLABS_API_KEY")),
            "modo": rweb.MODO, "tandas": rweb.TANDAS,
            "demo": (rweb.ESTATICO / "demo" / "demo.json").exists()}
