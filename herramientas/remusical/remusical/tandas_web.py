# -*- coding: utf-8 -*-
"""
El selector de TANDAS de la web: elegir una carpeta de Drive (una serie), marcar los
episodios, ver cuánto va a costar ANTES de gastar, lanzar en Vast y seguirla.

Se monta sobre la app de `web.py` como router. Separado a propósito: `web.py` maneja
un video a la vez con el Drive del usuario; esto maneja tandas con la cuenta de
servicio y el bucket, que es otro contrato de seguridad.

FLUJO
  1. el usuario navega SU Drive con su token OAuth (eso ya está en web.py)
  2. elige una carpeta -> `preparar` verifica que la cuenta de servicio la vea y que el
     bucket responda, lista los episodios y estima el costo
  3. marca los episodios, le pone nombre a la tanda y confirma
  4. `crear` arranca en segundo plano: buscar máquina -> alquilar -> procesar -> destruir
  5. el progreso sale del `estado.json` que la máquina escribe en el bucket
  6. al terminar, links firmados para bajar

★ NADA de esto manda credenciales del usuario a la máquina: ver nube/drive_sa.py.
"""
from __future__ import annotations

import json
import os
import threading
import time
import traceback
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from . import config as C

router = APIRouter(prefix="/api/tandas", tags=["tandas"])

REGISTRO = C.TRABAJO / "tandas.json"
_tandas: dict[str, dict] = {}
_lock = threading.Lock()

# Créditos de ElevenLabs por minuto de MÚSICA. Medido de punta a punta en La ruta de la
# seda: 16.600 cr para 25,2 min de música (27 min de video al 93 %). Vale para episodios
# largos con estilos que se repiten, que es donde "un tema por familia" amortiza. En un
# video corto con dos regiones sueltas sale MÁS caro por minuto: cada tema generado tiene
# un piso, y ahí no hay entre quiénes repartirlo.
CR_POR_MIN_MUSICA = 659
# USD por crédito. Scale: USD 299 por 1.800.000 créditos (precio consultado el 30-ago-2026).
# ★ Pro, Scale y Business cuestan casi lo MISMO por crédito (0,000165 - 0,000166): no hay
# descuento por volumen entre planes. El único descuento real es pagar anual (-17 %):
# poner REMUSICAL_USD_POR_CREDITO=0.00013843 si el plan es anual.
USD_POR_CREDITO = float(os.getenv("REMUSICAL_USD_POR_CREDITO", str(299 / 1_800_000)))
# Minutos de reloj en UNA GPU por minuto de video. ★ ESTO NO ESTÁ MEDIDO EN GPU. Lo único
# medido es en CPU: 4 h 24 para 27 min de video = 9,8 min por minuto. El 1,0 de acá supone
# una GPU 10x más rápida que ese CPU y es a propósito CONSERVADOR: preferimos estimar de
# más y que la factura sorprenda para abajo. Medirlo con el primer episodio real y ajustar
# con REMUSICAL_GPU_MIN_POR_MIN.
GPU_MIN_POR_MIN_VIDEO = float(os.getenv("REMUSICAL_GPU_MIN_POR_MIN", "1.0"))


def _guardar():
    C.TRABAJO.mkdir(parents=True, exist_ok=True)
    with _lock:
        REGISTRO.write_text(json.dumps(list(_tandas.values()), indent=1, ensure_ascii=False), encoding="utf-8")


def _cargar():
    if REGISTRO.exists():
        try:
            for t in json.loads(REGISTRO.read_text(encoding="utf-8")):
                if t.get("estado") in ("preparando", "procesando"):
                    t["estado"] = "interrumpida"      # la web se reinició; la máquina ya se destruyó sola
                _tandas[t["id"]] = t
        except Exception:
            pass
_cargar()


def estimar(duracion_total_s: float, frac_musica: float = 0.5, usd_h_gpu: float = 2.70,
            gpus: int = 4) -> dict:
    """Qué va a costar, antes de apretar el botón. Es una estimación: el costo real
    depende de cuánta música tenga de verdad cada video."""
    min_video = duracion_total_s / 60
    min_musica = min_video * frac_musica
    usd_eleven = min_musica * CR_POR_MIN_MUSICA * USD_POR_CREDITO
    horas_gpu = (min_video * GPU_MIN_POR_MIN_VIDEO) / 60 / max(1, gpus)
    usd_gpu = horas_gpu * usd_h_gpu
    return dict(minutos_video=round(min_video, 1), minutos_musica=round(min_musica, 1),
                usd_eleven=round(usd_eleven, 2), usd_gpu=round(usd_gpu, 2),
                usd_total=round(usd_eleven + usd_gpu, 2), horas_reloj=round(horas_gpu, 2),
                supuesto=f"{int(frac_musica*100)}% del video con música")


@router.get("/config")
def config(req: Request):
    """Qué falta configurar. La web lo muestra antes de dejar crear una tanda."""
    from .nube import drive_sa, bucket
    r = dict(vast=bool(os.getenv("VAST_API_KEY")),
             eleven=bool(os.getenv("ELEVENLABS_API_KEY")),
             bucket=bool(os.getenv("S3_KEY") and os.getenv("S3_BUCKET")),
             sa=bool(os.getenv("GOOGLE_SA_JSON_B64") or os.getenv("GOOGLE_SA_JSON")),
             email_sa=None)
    if r["sa"]:
        try:
            r["email_sa"] = drive_sa.email_cuenta()
        except Exception as e:
            r["sa"] = False
            r["error_sa"] = str(e)[:200]
    r["listo"] = all([r["vast"], r["eleven"], r["bucket"], r["sa"]])
    return r


@router.get("/preparar")
def preparar(req: Request, carpeta: str, frac_musica: float = 0.5, gpus: int = 4):
    """Lo que la web muestra antes de confirmar: episodios, accesos y costo estimado."""
    from .nube import drive_sa, bucket, provisionar
    acceso = drive_sa.verificar_acceso(carpeta)
    if not acceso.get("ok"):
        return dict(ok=False, drive=acceso, bucket=bucket.verificar())
    vids = drive_sa.listar_videos(carpeta)
    dur = sum(v.duracion_s for v in vids)
    # precio real del momento, para que la estimación no sea inventada
    # si no se puede preguntar a Vast, se usa el precio de 4x RTX 4090 de DATACENTER
    # (USD 2,673/h el 30-ago-2026), que es el caro: la estimación nunca queda corta.
    usd_h, ofertas = 2.70, []
    try:
        ofs = provisionar.ofertas_seguras(gpus=gpus, solo_datacenter=True)
        if ofs:
            usd_h = ofs[0].usd_h
            ofertas = [dict(usd_h=o.usd_h, gpu=o.gpu, num_gpus=o.num_gpus, pais=o.pais,
                            fiabilidad=round(o.fiabilidad, 3)) for o in ofs[:3]]
    except Exception as e:
        ofertas = [dict(error=str(e)[:150])]
    return dict(ok=True, carpeta=acceso.get("carpeta"), bucket=bucket.verificar(),
                videos=[dict(id=v.id, nombre=v.nombre, bytes=v.tamano, duracion_s=v.duracion_s) for v in vids],
                duracion_total_s=dur, ofertas=ofertas, usd_h=usd_h,
                # las constantes van al navegador para que pueda recalcular el costo del
                # SUBCONJUNTO que el usuario marca, sin volver a preguntarle a Vast
                constantes=dict(cr_por_min_musica=CR_POR_MIN_MUSICA, usd_por_credito=USD_POR_CREDITO,
                                gpu_min_por_min=GPU_MIN_POR_MIN_VIDEO),
                estimacion=estimar(dur, frac_musica, usd_h, gpus))


@router.post("/crear")
async def crear(req: Request):
    from . import api as fachada
    body = await req.json()
    carpeta = body.get("carpeta")
    archivos = body.get("archivos") or None
    nombre = (body.get("nombre") or f"tanda-{time.strftime('%Y%m%d-%H%M')}").strip()
    if not carpeta:
        raise HTTPException(400, "falta la carpeta")
    nube = body.get("nube") or {}
    opciones = body.get("opciones") or {}
    tid = uuid.uuid4().hex[:10]
    prefijo = f"{nombre}-{tid}".replace(" ", "_")
    t = dict(id=tid, nombre=nombre, prefijo=prefijo, carpeta=carpeta, estado="preparando",
             creado=time.strftime("%Y-%m-%d %H:%M:%S"), usuario=body.get("usuario", ""),
             videos=len(archivos or []), log=[], resumen=None, error=None, instancia=None)
    _tandas[tid] = t
    _guardar()

    def correr():
        def log(m):
            t["log"].append(str(m))
            del t["log"][:-200]
            print(f"[tanda {tid}] {m}", flush=True)
        try:
            m = fachada.manifiesto_drive(prefijo, carpeta, prefijo_bucket=prefijo, archivos=archivos,
                                         completo=bool(opciones.get("separar_completo")),
                                         takes=int(opciones.get("takes", C.TAKES_MAX)))
            t["videos"] = len(m["videos"])
            t["estado"] = "procesando"
            _guardar()
            r = fachada.tanda_vast(m, gpus=int(nube.get("gpus", 4)),
                                   tope_usd_h=float(nube.get("tope_usd_h", 0.6)),
                                   max_usd=float(nube.get("max_usd", 50)),
                                   max_horas=float(nube.get("max_horas", 12)),
                                   solo_datacenter=bool(nube.get("solo_datacenter", True)),
                                   esperar_oferta_s=int(nube.get("esperar_oferta_s", 0)), log=log)
            t["resumen"] = r
            t["instancia"] = r.get("instancia")
            tan = r.get("tanda") or {}
            t["estado"] = "lista" if tan.get("terminada") else "incompleta"
        except Exception as e:
            t["estado"] = "error"
            t["error"] = f"{type(e).__name__}: {e}"
            t["log"].append(traceback.format_exc()[-600:])
        finally:
            _guardar()

    threading.Thread(target=correr, daemon=True, name=f"tanda-{tid}").start()
    return dict(id=tid, prefijo=prefijo)


@router.get("")
def listar(req: Request):
    return dict(tandas=sorted([dict(t, log=t["log"][-4:]) for t in _tandas.values()],
                              key=lambda t: t["creado"], reverse=True))


@router.get("/{tid}")
def detalle(req: Request, tid: str):
    t = _tandas.get(tid)
    if not t:
        raise HTTPException(404, "no existe")
    # el estado por video lo escribe la máquina en el bucket: es la fuente de verdad
    estado_videos = None
    try:
        from .nube.tanda import leer_texto
        from .nube import bucket
        estado_videos = json.loads(leer_texto(f"s3://{bucket.bucket_por_defecto()}/{t['prefijo']}/estado.json"))
    except Exception:
        pass
    return dict(**t, detalle_videos=estado_videos)


@router.get("/{tid}/descargas")
def descargas(req: Request, tid: str, horas: float = 24):
    from . import api as fachada
    t = _tandas.get(tid)
    if not t:
        raise HTTPException(404, "no existe")
    try:
        return dict(archivos=fachada.descargas(t["prefijo"], horas))
    except Exception as e:
        raise HTTPException(500, f"no pude listar el bucket: {e}")


@router.post("/{tid}/cancelar")
def cancelar(req: Request, tid: str):
    from .nube.vast import Vast
    t = _tandas.get(tid)
    if not t:
        raise HTTPException(404, "no existe")
    destruidas = []
    if t.get("instancia"):
        try:
            Vast().destruir(int(t["instancia"]))
            destruidas.append(t["instancia"])
        except Exception:
            pass
    destruidas += Vast().destruir_todas(f"remusical-{t['prefijo']}")
    t["estado"] = "cancelada"
    _guardar()
    return dict(ok=True, destruidas=destruidas)


@router.delete("/{tid}/archivos")
def limpiar(req: Request, tid: str):
    """Borra los resultados del bucket (después de bajarlos). Es lo que mantiene el costo en centavos."""
    from .nube import bucket
    t = _tandas.get(tid)
    if not t:
        raise HTTPException(404, "no existe")
    n = bucket.borrar(t["prefijo"])
    t["archivos_borrados"] = n
    _guardar()
    return dict(borrados=n)
