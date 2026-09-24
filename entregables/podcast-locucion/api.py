"""API HTTP del módulo de locución.

    uvicorn api:app --reload --port 8080

Los episodios largos no se sintetizan dentro del request: se encolan y se
consultan por id. Un episodio de 10 minutos son ~90 llamadas a ElevenLabs y
tarda varios minutos; hacerlo en el request da timeout en cualquier proxy.
"""
from __future__ import annotations

import threading
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from locucion import Ajustes, guion, narrar, voces
from locucion.config import TAGS

app = FastAPI(title="Locución para podcast", version="1.0")

SALIDAS = Path("salidas")
CACHE = Path("cache")
SALIDAS.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)

_trabajos: dict[str, dict] = {}
_lock = threading.Lock()


# ───────────────────────────────────────────────────────────────── voces

@app.get("/voces")
def listar_voces():
    """Todas las voces de la cuenta. Las que tienen `cps` están medidas y su
    duración estimada es confiable; las que tienen `cps: null` se estiman con
    un valor genérico hasta que corras /voces/{id}/medir."""
    return {"voces": voces.catalogo()}


@app.get("/voces/{voz_id}")
def ver_voz(voz_id: str):
    v = voces.ver(voz_id)
    if not v:
        raise HTTPException(404, "no existe esa voz")
    return v


@app.post("/voces/{voz_id}/medir")
def medir_voz(voz_id: str):
    """Mide los caracteres por segundo REALES de una voz. Corré esto una vez
    por voz nueva y guardá el número en tu base: con él las estimaciones de
    duración aciertan dentro del 10 %. Cuesta una síntesis corta."""
    return {"voz_id": voz_id, "cps": voces.medir_cps(voz_id)}


@app.get("/etiquetas")
def etiquetas():
    """Las etiquetas de emoción que el modelo interpreta, con cuándo usar cada
    una. Van dentro del texto: «No sé. [sighs] Tal vez tengas razón.»"""
    return {"etiquetas": TAGS,
            "aviso": "un texto que sea SÓLO una etiqueta lo rechaza la API con 400"}


# ───────────────────────────────────────────────────────────── estimar

class Estimacion(BaseModel):
    texto: str
    voz_id: str
    pausa_oracion: float = Ajustes.pausa_oracion
    pausa_parrafo: float = Ajustes.pausa_parrafo
    arranque: float = Ajustes.arranque


@app.post("/estimar")
def estimar(e: Estimacion):
    """Cuánto va a durar y cuántos caracteres se van a gastar, SIN sintetizar.
    Llamalo antes de encolar para avisarle al usuario."""
    cps = voces.cps_de(e.voz_id)
    seg = guion.estimar(e.texto, cps, e.pausa_oracion, e.pausa_parrafo, e.arranque)
    return {"segundos": seg, "mmss": f"{int(seg) // 60}:{int(seg) % 60:02d}",
            "caracteres": len(e.texto), "lineas": len(guion.partir(e.texto)),
            "cps_usado": cps, "voz_medida": voces.cps_de(e.voz_id) != voces.CPS_POR_DEFECTO}


# ───────────────────────────────────────────────────────────── locutar

class Pedido(BaseModel):
    texto: str = Field(..., description="el episodio; los párrafos se separan con una línea en blanco")
    voz_id: str
    estabilidad: float = Ajustes.estabilidad
    similitud: float = Ajustes.similitud
    speaker_boost: bool = Ajustes.speaker_boost
    pausa_oracion: float = Ajustes.pausa_oracion
    pausa_parrafo: float = Ajustes.pausa_parrafo
    arranque: float = Ajustes.arranque
    masterizar: bool = True
    musica: str | None = Field(None, description="ruta a un archivo de música de fondo (opcional)")

    def a_ajustes(self) -> Ajustes:
        return Ajustes(voz_id=self.voz_id, estabilidad=self.estabilidad,
                       similitud=self.similitud, speaker_boost=self.speaker_boost,
                       pausa_oracion=self.pausa_oracion, pausa_parrafo=self.pausa_parrafo,
                       arranque=self.arranque, masterizar=self.masterizar)


def _correr(tid: str, p: Pedido) -> None:
    mp3 = SALIDAS / f"{tid}.mp3"
    try:
        def progreso(i, n, _t):
            with _lock:
                _trabajos[tid].update(hechas=i, total=n)
        ep = narrar(p.texto, p.a_ajustes(), mp3,
                    musica=Path(p.musica) if p.musica else None,
                    cache=CACHE, progreso=progreso)
        (SALIDAS / f"{tid}.srt").write_text(ep.srt(), encoding="utf-8")
        with _lock:
            _trabajos[tid].update(estado="listo", segundos=ep.total,
                                  lineas=[{"t": l.t, "dur": round(l.dur, 3), "texto": l.texto}
                                          for l in ep.lineas])
    except Exception as e:
        with _lock:
            _trabajos[tid].update(estado="error", error=f"{type(e).__name__}: {e}")


@app.post("/locutar")
def locutar(p: Pedido, tareas: BackgroundTasks):
    """Encola un episodio. Devuelve un id: consultá /locutar/{id} hasta que el
    estado sea «listo», y bajá el audio en /locutar/{id}/audio."""
    if not p.texto.strip():
        raise HTTPException(400, "texto vacío")
    tid = uuid.uuid4().hex[:12]
    with _lock:
        _trabajos[tid] = {"id": tid, "estado": "corriendo", "hechas": 0,
                          "total": len(guion.partir(p.texto))}
    tareas.add_task(_correr, tid, p)
    return _trabajos[tid]


@app.get("/locutar/{tid}")
def estado(tid: str):
    t = _trabajos.get(tid)
    if not t:
        raise HTTPException(404, "no existe ese trabajo")
    return t


@app.get("/locutar/{tid}/audio")
def audio_de(tid: str):
    f = SALIDAS / f"{tid}.mp3"
    if not f.exists():
        raise HTTPException(404, "todavía no está listo")
    return FileResponse(f, media_type="audio/mpeg", filename=f"{tid}.mp3")


@app.get("/locutar/{tid}/srt", response_class=PlainTextResponse)
def srt_de(tid: str):
    f = SALIDAS / f"{tid}.srt"
    if not f.exists():
        raise HTTPException(404, "todavía no está listo")
    return f.read_text(encoding="utf-8")
