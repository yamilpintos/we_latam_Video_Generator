# -*- coding: utf-8 -*-
"""
El contenedor de Replicate. Una predicción = un video.

Dos formas de entrada:
  · Drive (la que usa la web):  drive_file_id + access_token → baja el video de Drive,
    procesa, y SUBE el resultado a `re-musical/` dentro de la carpeta del video.
    El servidor web nunca toca el video.
  · Archivo (para probar desde la interfaz de Replicate): `video` → devuelve los
    archivos como salida.

Progreso: se imprime `PROGRESO <etapa> <fracción>` y `LOG <mensaje>`; la web los lee
de los logs de la predicción. Los secretos (token de Drive, key de ElevenLabs) entran
como `Secret`: Replicate los tacha en su panel y en la API.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

from cog import BaseModel, BasePredictor, Input, Path as CogPath, Secret

sys.path.insert(0, str(Path(__file__).resolve().parent))
TRABAJO = Path("/tmp/remusical")
os.environ.setdefault("REMUSICAL_TRABAJO", str(TRABAJO))

# ★★★ CONTRA EL GASTO SIN FIN — Replicate cobra cada segundo que la instancia está viva,
# también si la predicción falla o se cuelga. Tres cortes independientes:
#   1. socket.setdefaulttimeout: ninguna llamada de red (Drive, ElevenLabs, HF) puede
#      quedarse esperando para siempre. Sin esto, un download colgado = GPU cobrando.
#   2. un watchdog que MATA el proceso a los MAX_MIN minutos, pase lo que pase. Es el
#      corte de última instancia: si algo se cuelga adentro de torch o de ffmpeg, esto
#      termina la predicción (falla, deja de cobrar).
#   3. la web además crea la predicción con `deadline`: Replicate la cancela solo.
MAX_MIN = int(os.getenv("REMUSICAL_MAX_MIN", "40"))
socket.setdefaulttimeout(120)


def _watchdog(inicio: float):
    while True:
        time.sleep(15)
        if time.time() - inicio > MAX_MIN * 60:
            print(f"LOG WATCHDOG: {MAX_MIN} min cumplidos, se corta para no seguir cobrando", flush=True)
            os._exit(3)


class Salida(BaseModel):
    estado: str
    informe: str
    carpeta_drive_id: Optional[str] = None
    salidas: Optional[List[dict]] = None
    archivos: Optional[List[CogPath]] = None


class Predictor(BasePredictor):
    def setup(self):
        from remusical import mapa
        mapa.modelo()                                   # AST a GPU una sola vez

    def predict(
        self,
        video: CogPath = Input(default=None, description="Video a musicalizar (si no se usa Drive)"),
        drive_file_id: str = Input(default="", description="ID del video en Google Drive"),
        drive_parent_id: str = Input(default="", description="Carpeta de Drive donde crear re-musical/ (default: la del video)"),
        access_token: Secret = Input(default=None, description="Token OAuth de Drive (1 h)"),
        eleven_api_key: Secret = Input(default=None, description="API key de ElevenLabs"),
        separar_completo: bool = Input(default=False, description="Stems del video entero (más lento)"),
        takes: int = Input(default=3, ge=1, le=5, description="Máximo de takes por pista (se genera 1; más sólo si no convence)"),
    ) -> Salida:
        from remusical import drive_io
        from remusical.orquestador import procesar

        inicio = time.time()
        threading.Thread(target=_watchdog, args=(inicio,), daemon=True).start()
        print(f"LOG límite duro de esta predicción: {MAX_MIN} min", flush=True)

        if eleven_api_key:
            os.environ["ELEVENLABS_API_KEY"] = eleven_api_key.get_secret_value()
        if not os.getenv("ELEVENLABS_API_KEY"):
            raise ValueError("falta eleven_api_key")

        shutil.rmtree(TRABAJO, ignore_errors=True)
        TRABAJO.mkdir(parents=True)

        def progreso(etapa, f):
            print(f"PROGRESO {etapa} {f:.3f}", flush=True)

        def log(m):
            print(f"LOG {m}", flush=True)

        d = None
        if drive_file_id:
            if not access_token:
                raise ValueError("con drive_file_id hace falta access_token")
            d = drive_io.drive_con_token(access_token.get_secret_value())
            m = drive_io.meta(d, drive_file_id)
            padre = drive_parent_id or (m.get("parents") or ["root"])[0]
            local = TRABAJO / "entrada" / m["name"]
            log(f"bajando de Drive: {m['name']} ({int(m.get('size', 0) or 0)/1e9:.2f} GB)")
            progreso("bajando", 0.0)
            drive_io.bajar(d, drive_file_id, local, lambda f: progreso("bajando", 0.04 * f))
        elif video:
            local = TRABAJO / "entrada" / Path(str(video)).name
            local.parent.mkdir(parents=True)
            shutil.copy(str(video), local)
        else:
            raise ValueError("hace falta `video` o `drive_file_id`")

        salida = TRABAJO / "re-musical"
        inf = procesar(local, salida_dir=salida, separar_completo=separar_completo,
                       takes_por_region=takes, log=log,
                       progreso=lambda e, f: progreso(e, 0.05 + 0.85 * f))
        archivos = sorted(salida.glob("*"))

        if d is not None:
            progreso("subiendo", 0.90)
            cid = drive_io.carpeta_salida(d, padre)
            subidos = []
            for k, p in enumerate(archivos):
                log(f"subiendo {p.name}")
                subidos.append(dict(nombre=p.name, id=drive_io.subir(d, p, cid)))
                progreso("subiendo", 0.90 + 0.10 * (k + 1) / len(archivos))
            return Salida(estado=inf["estado"], informe=json.dumps(inf, ensure_ascii=False),
                          carpeta_drive_id=cid, salidas=subidos)
        return Salida(estado=inf["estado"], informe=json.dumps(inf, ensure_ascii=False),
                      archivos=[CogPath(p) for p in archivos])
