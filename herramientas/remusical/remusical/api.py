# -*- coding: utf-8 -*-
"""
LA FACHADA DE REMUSICAL. Lo único que un `main` externo necesita importar.

    from remusical import api

    # un video, acá (CPU/GPU local)
    inf = api.procesar_video("C:/videos/a.mp4")                  # → dict con estado, regiones, guardas, créditos
    inf = api.procesar_video("a.mp4", salida="C:/out", completo=True, takes_max=3,
                             log=print, progreso=lambda etapa, f: ...)

    # corregir el nivel de una entrega ya hecha (sin separar ni generar)
    api.renivelar("C:/out/re-musical", "C:/videos/a.mp4")

    # una tanda, acá, N en paralelo
    api.tanda_local(manifiesto, workers=2)

    # una tanda en Vast.ai: busca la máquina VERIFICADA más barata del momento,
    # la alquila, corre y la destruye. Devuelve el resumen (oferta, horas, USD, estado).
    api.vast_ofertas(gpus=4, tope_usd_h=0.6)                   # mirar precios primero
    api.tanda_vast(manifiesto, gpus=4, tope_usd_h=0.6, max_usd=50, max_horas=12)
    api.vast_panico()                                          # destruir todo lo nuestro

Nada acá imprime salvo lo que pases en `log`. Nada acá lee argv. Los errores son
excepciones normales. Las claves salen del entorno o de `.env` (ELEVENLABS_API_KEY,
VAST_API_KEY, S3_*).
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import config as C

Log = Callable[[str], None]
Progreso = Callable[[str, float], None]


def _nada(*a, **k):
    pass


def procesar_video(video: str | Path, salida: str | Path | None = None, completo: bool = False,
                   takes_max: int = C.TAKES_MAX, log: Log = _nada, progreso: Progreso = _nada) -> dict:
    """Reemplaza la música del video. Deja `re-musical/` (o `salida`) con el MP4, los stems
    (voz, música original, música nueva) y `informe.json`. Devuelve el informe."""
    from .orquestador import procesar
    return procesar(Path(video), salida_dir=Path(salida) if salida else None, separar_completo=completo,
                    takes_por_region=takes_max, log=log, progreso=progreso)


def renivelar(carpeta: str | Path, video: str | Path, log: Log = _nada) -> dict:
    """Iguala la música nueva a la original pista por pista en una entrega ya hecha."""
    import sys
    from . import renivelar as _r
    viejo = sys.argv
    try:
        sys.argv = ["renivelar", str(carpeta), str(video)]
        _r.main()
    finally:
        sys.argv = viejo
    import json
    inf = Path(carpeta) / f"{Path(video).stem} - informe.json"
    return json.loads(inf.read_text(encoding="utf-8"))


def tanda_local(manifiesto: dict, workers: int = 1, log: Log = _nada) -> dict:
    """Corre el manifiesto en esta máquina, `workers` videos a la vez. Reanudable."""
    from .nube.tanda import Tanda
    return Tanda(manifiesto, log=log).correr(workers=workers)


def vast_ofertas(gpu: str = "RTX 4090", gpus: int = 4, tope_usd_h: float | None = None,
                 solo_datacenter: bool = False) -> list[dict]:
    """Ofertas VERIFICADAS disponibles ahora, de más barata a más cara (USD/h por la máquina)."""
    from .nube.provisionar import ofertas_seguras
    return [o.__dict__ for o in ofertas_seguras(gpu=gpu, gpus=gpus, tope_usd_h=tope_usd_h, solo_datacenter=solo_datacenter)]


def tanda_vast(manifiesto: dict, gpu: str = "RTX 4090", gpus: int = 4, tope_usd_h: float = 0.60,
               max_usd: float = 50.0, max_horas: float = 12.0, solo_datacenter: bool = False,
               workers: int | None = None, esperar_oferta_s: int = 0, log: Log = _nada) -> dict:
    """Busca la máquina verificada más barata que cumpla, la alquila, corre la tanda y la
    destruye. Guardas: tope por hora, presupuesto total, horas máximas, sin respuesta."""
    from .nube.provisionar import correr_tanda_en_vast
    return correr_tanda_en_vast(manifiesto, gpu=gpu, gpus=gpus, tope_usd_h=tope_usd_h, max_usd=max_usd,
                                max_horas=max_horas, solo_datacenter=solo_datacenter, workers=workers,
                                esperar_oferta_s=esperar_oferta_s, log=log)


def manifiesto_drive(nombre: str, carpeta_drive_id: str, prefijo_bucket: str | None = None,
                     archivos: list[str] | None = None, completo: bool = False,
                     takes: int = C.TAKES_MAX, horas_firma: float = 8) -> dict:
    """Arma una tanda desde UNA carpeta de Drive compartida con la cuenta de servicio.

    Lee de Drive (sólo lectura, sólo esa carpeta) y escribe al bucket con URLs firmadas:
    la máquina no lleva ninguna credencial encima. `archivos` limita a esos ids (los
    episodios elegidos); si es None, van todos los videos de la carpeta.
    """
    from .nube import drive_sa, bucket
    vids = drive_sa.listar_videos(carpeta_drive_id)
    if archivos:
        elegidos = set(archivos)
        vids = [v for v in vids if v.id in elegidos]
    if not vids:
        raise ValueError("no hay videos que procesar en esa carpeta")
    pref = (prefijo_bucket or nombre).strip("/")
    salida = []
    for i, v in enumerate(vids, 1):
        f = bucket.firmar_salidas(f"{pref}/v{i:03d}", v.nombre, completo, horas_firma)
        salida.append(dict(id=f"v{i:03d}", origen=f"drive://{v.id}", nombre=v.nombre,
                           bytes=v.tamano, duracion_s=v.duracion_s, subidas=f.subidas))
    return dict(nombre=nombre, destino=f"s3://{bucket.bucket_por_defecto()}/{pref}",
                videos=salida, opciones=dict(separar_completo=completo, takes=takes))


def verificar_accesos(carpeta_drive_id: str | None = None) -> dict:
    """Antes de alquilar nada: ¿la cuenta de servicio ve la carpeta? ¿el bucket responde?"""
    from .nube import drive_sa, bucket
    r = dict(bucket=bucket.verificar())
    if carpeta_drive_id:
        r["drive"] = drive_sa.verificar_acceso(carpeta_drive_id)
    else:
        try:
            r["drive"] = dict(ok=None, email=drive_sa.email_cuenta())
        except Exception as e:
            r["drive"] = dict(ok=False, error=str(e)[:200])
    return r


def descargas(prefijo: str, horas: float = 24) -> list[dict]:
    """Links firmados para bajar los resultados de una tanda."""
    from .nube import bucket
    return [dict(archivo=o["clave"].split("/")[-1], bytes=o["bytes"],
                 url=bucket.firmar_bajada(o["clave"], horas))
            for o in bucket.listar(prefijo)]


def vast_panico() -> list[int]:
    """Destruye todas nuestras instancias en Vast (etiqueta remusical-*)."""
    from .nube.vast import Vast
    v = Vast()
    return [int(i["id"]) for i in v.mis_instancias() if str(i.get("label", "")).startswith("remusical")
            and v.destruir(int(i["id"]))]


def manifiesto(nombre: str, videos: list[str], destino: str, separar_completo: bool = False,
               takes: int = C.TAKES_MAX) -> dict:
    """Arma un manifiesto de tanda a partir de una lista de orígenes (rutas, http(s) o s3://)."""
    return dict(nombre=nombre, destino=destino,
                videos=[dict(id=f"v{i+1:03d}", origen=str(v)) for i, v in enumerate(videos)],
                opciones=dict(separar_completo=separar_completo, takes=takes))
