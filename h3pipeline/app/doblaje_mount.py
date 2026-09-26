"""Doblaje dentro de La Fábrica.

La herramienta vive ENTERA en `herramientas/doblaje/`: es el mismo código que corre sola con
`python -m doblaje.web` (Drive → ElevenLabs Dubbing v2 → nivelación por pistas con la GPU de Vast que
se alquila e instala sola → verificación → Drive, con control de créditos). Acá no se reescribe nada:
se la importa y se la monta en `/doblaje/`. Ella calcula sus URLs del request (`root_path`), así que
no sabe que está montada y funciona igual en los dos lugares.

Lo único que hace este módulo, ANTES de importarla, es darle el mismo entorno que tenía en su casa,
sin que el usuario cargue dos veces las mismas claves:
  - ELEVENLABS_API_KEY: si no está en el entorno, la del .env de La Fábrica (`elevenlabs=`).
  - VAST_API_KEY: ídem (`vasia=`). Y la clave ssh: La Fábrica la recibe como VAST_SSH_PRIVATE_KEY;
    Doblaje la lee como VAST_SSH_KEY (o de ~/.ssh/id_ed25519, que server.py escribe al arrancar).
  - DOBLAJE_TRABAJO: `mis-videos/_doblaje/` (el disco persistente de Render), si no está fijado.
  - FOTON: la raíz del motor de doblaje si existe en esta PC (ahí busca el ffmpeg de respaldo y el .env
    de dubai_v2). En Render no existe y no hace falta: ffmpeg viene del contenedor.
Todo se puede fijar por entorno o en `herramientas/doblaje/.env`; acá sólo hay defaults.

Si falta una dependencia (paramiko, google-api-python-client…), La Fábrica arranca igual: `cargar()`
devuelve el error y el servidor lo muestra en /doblaje/ en vez de caerse.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CARPETA = RAIZ / "herramientas" / "doblaje"


def _cargar_env_propio() -> None:
    """El .env de la herramienta, ANTES de importarla: su config.py lee el entorno al importarse."""
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
    for var, alias in (("ELEVENLABS_API_KEY", "elevenlabs"), ("VAST_API_KEY", "vasia")):
        if not os.environ.get(var):
            try:
                k = config.leer_env(var, obligatorio=False) or config.leer_env(alias, obligatorio=False)
            except Exception:
                k = None
            if k:
                os.environ[var] = k
    if not os.environ.get("VAST_SSH_KEY") and os.environ.get("VAST_SSH_PRIVATE_KEY"):
        os.environ["VAST_SSH_KEY"] = os.environ["VAST_SSH_PRIVATE_KEY"]
    os.environ.setdefault("DOBLAJE_TRABAJO", str(RAIZ / "mis-videos" / "_doblaje"))
    if not os.environ.get("FOTON"):
        foton = Path.home() / "Desktop" / "Foton"
        if (foton / "dubai_v2").exists():
            os.environ["FOTON"] = str(foton)
    propio = Path(os.environ.get("FOTON", "")) / "dubai_v2" / "_bin" / "ffmpeg.exe"
    if not os.environ.get("FFMPEG") and not propio.exists():
        try:
            os.environ["FFMPEG"] = config.ffmpeg()
        except Exception:
            pass


def cargar():
    """(app de Doblaje, "") si se pudo importar; (None, motivo) si no."""
    if not CARPETA.exists():
        return None, f"no está la carpeta {CARPETA}"
    _preparar_entorno()
    if str(CARPETA) not in sys.path:
        sys.path.insert(0, str(CARPETA))
    try:
        from doblaje import web as dweb            # noqa: WPS433  (la herramienta, entera)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}\n\n{traceback.format_exc()[-1500:]}"
    return dweb.app, ""


def estado(error: str) -> dict:
    """Lo que la portada muestra en la puerta de Doblaje."""
    if error:
        return {"montada": False, "error": error.splitlines()[0],
                "instalar": "pip install -r herramientas/doblaje/requirements.txt"}
    from doblaje import web as dweb
    from doblaje import creditos, gpu_vast, media
    g = gpu_vast.estado(consultar=False)
    pausa = creditos.pausado()
    return {"montada": True,
            "google_configurado": bool(dweb.CLIENT_ID and dweb.CLIENT_SECRET),
            "eleven": bool(dweb._cuentas()),
            "gpu": g["configurada"], "gpu_modo": g["modo"], "gpu_fase": g["fase"],
            "pistas": media.separador_disponible(),
            "pausa": pausa["motivo"] if pausa else None,
            "activos": len(dweb._activos())}
