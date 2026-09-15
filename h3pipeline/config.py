"""Dónde vive cada cosa: el .env, ffmpeg, los certificados y las rutas.

Nada de esto se importa desde el main de la app: lo usan los demás módulos del
paquete. Lo único que hay que saber desde afuera es que las claves se leen de
variables de entorno o de un `.env`, en este orden:

    1. la variable de entorno tal cual (NANOBANANA, VAST_API_KEY, ...)
    2. el archivo que diga H3PIPELINE_ENV
    3. ./.env en el directorio de trabajo
    4. ../.env respecto de este paquete (la raíz del proyecto de video)
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

PAQUETE = Path(__file__).resolve().parent
RAIZ = PAQUETE.parent


class ConfigFaltante(RuntimeError):
    """Falta una clave, un binario o un archivo sin el que no se puede seguir."""


def _archivos_env():
    for c in ((os.environ.get("H3PIPELINE_ENV"), Path.cwd() / ".env", RAIZ / ".env")
              + ENV_EXTRA):
        if c and Path(c).is_file():
            yield Path(c)


# El .env del proyecto se fue escribiendo a mano, así que la misma clave aparece
# con nombres distintos. Se aceptan todos en vez de pedir que se renombre.
ALIAS = {
    "VAST_API_KEY": ("VAST_API_KEY", "VASTAI_API_KEY", "VAST", "vast", "vastai", "vasia"),
    "ELEVENLABS_API_KEY": ("ELEVENLABS_API_KEY", "elevenlabs", "ELEVENLABS", "eleven"),
    "nanobanana": ("nanobanana", "NANOBANANA", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "OPENAI_API_KEY": ("OPENAI_API_KEY", "openai", "OPENAI"),
}

# Otros `.env` del usuario donde también viven claves de este stack. El de
# dubai_v2 es el del motor de doblaje, y tiene la de OpenAI y la de ElevenLabs
# con los clones `professional`.
ENV_EXTRA = (Path.home() / "Desktop" / "Foton" / "dubai_v2" / ".env",)


def _candidatos(nombre: str) -> tuple[str, ...]:
    for canon, alias in ALIAS.items():
        if nombre in alias or nombre.upper() == canon:
            return alias
    return (nombre, nombre.upper(), nombre.lower())


def leer_env(nombre: str, obligatorio: bool = True) -> str | None:
    """Una clave del entorno o del `.env`, tolerando los nombres con que quedó
    escrita: el `.env` del proyecto usa `nanobanana=`, `elevenlabs=` y `vasia=`."""
    nombres = _candidatos(nombre)
    for k in nombres:
        if os.environ.get(k):
            return os.environ[k]
    for archivo in _archivos_env():
        for linea in archivo.read_text(encoding="utf-8", errors="replace").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            if k.strip() in nombres:
                return v.strip().strip('"').strip("'")
    if obligatorio:
        raise ConfigFaltante(
            f"falta {nombre}: ponelo en .env o como variable de entorno. "
            f"También lo busco como: {', '.join(x for x in nombres if x != nombre)}")
    return None


def ffmpeg() -> str:
    for c in (os.environ.get("FFMPEG"), shutil.which("ffmpeg"),
              RAIZ / ".venv-depthflow" / "Scripts" / "ffmpeg.exe"):
        if c and Path(c).exists():
            return str(c)
    raise ConfigFaltante("no encuentro ffmpeg: FFMPEG=<ruta> o instalalo en el PATH")


def certificados() -> None:
    """Avast reemplaza los certificados SSL de la máquina y toda descarga HTTPS desde
    Python falla. El proyecto guarda un bundle que lo arregla; si está, se usa."""
    if os.environ.get("SSL_CERT_FILE"):
        return
    pem = RAIZ / "certs" / "ca-bundle-avast.pem"
    if pem.exists():
        os.environ["SSL_CERT_FILE"] = str(pem)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", str(pem))
