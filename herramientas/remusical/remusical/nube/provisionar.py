# -*- coding: utf-8 -*-
"""
Buscar → alquilar → correr → DESTRUIR. Todo lo que hace falta para procesar una tanda
en Vast.ai en la máquina segura más barata que haya en este momento.

  from remusical.nube.provisionar import correr_tanda_en_vast
  correr_tanda_en_vast(manifiesto, gpus=4, tope_usd_h=0.60)

★★★ GUARDAS DE GASTO (una máquina alquilada por hora cobra aunque no haga nada):
  1. no se alquila por encima de `tope_usd_h`
  2. presupuesto total `max_usd`: si horas × precio lo supera, se destruye
  3. `max_horas` por instancia: se destruye pase lo que pase
  4. si no arranca en `arranque_s`, se destruye
  5. si la tanda no responde por HTTP `silencio_s` seguidos, se destruye
  6. `try/finally`: cualquier excepción termina en destruir()
  7. `destruir_todas()` es el botón de pánico
  8. la instancia misma se apaga al terminar (onstart termina → contenedor termina);
     Vast la deja "exited" y no cobra GPU, pero el disco sí: por eso igual se destruye
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request

from .vast import Vast, VastError, Oferta

IMAGEN = os.getenv("REMUSICAL_IMAGEN", "ghcr.io/yamilpintos/remusical:latest")
PUERTO_ESTADO = 8790


def ofertas_seguras(gpu: str = "RTX 4090", gpus: int = 4, tope_usd_h: float | None = None,
                    solo_datacenter: bool = False, api_key: str | None = None) -> list[Oferta]:
    """Para mirar precios antes de decidir. Ordenadas de más barata a más cara."""
    return Vast(api_key).buscar(gpu=gpu, num_gpus=gpus, tope_usd_h=tope_usd_h, solo_datacenter=solo_datacenter)


def _onstart(workers: int) -> str:
    return (f"cd /src && REMUSICAL_WORKERS={workers} python -m remusical.nube.tanda "
            f"> /var/log/remusical.log 2>&1")


def _estado_http(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url + "/estado", timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def correr_tanda_en_vast(manifiesto: dict, gpu: str = "RTX 4090", gpus: int = 4,
                         tope_usd_h: float = 0.60, max_usd: float = 50.0, max_horas: float = 12.0,
                         solo_datacenter: bool = False, workers: int | None = None, disco_gb: int = 80,
                         imagen: str = IMAGEN, env_extra: dict[str, str] | None = None,
                         arranque_s: int = 900, silencio_s: int = 900, esperar_oferta_s: int = 0,
                         api_key: str | None = None, log=print, _vast: Vast | None = None) -> dict:
    """Devuelve un resumen: oferta elegida, instancia, horas, USD estimados, estado de la tanda.
    `esperar_oferta_s` > 0: si no hay oferta que cumpla, reintenta cada 10 min hasta ese tiempo."""
    v = _vast or Vast(api_key)
    workers = workers or gpus

    # ---- 1. buscar la más barata que cumpla ----
    t0 = time.time()
    while True:
        ofertas = v.buscar(gpu=gpu, num_gpus=gpus, tope_usd_h=tope_usd_h, solo_datacenter=solo_datacenter, disco_gb=disco_gb)
        if ofertas:
            break
        if time.time() - t0 >= esperar_oferta_s:
            raise VastError(f"no hay ofertas verificadas de {gpus}x {gpu} a ≤ USD {tope_usd_h}/h"
                            + (" en datacenter" if solo_datacenter else ""))
        log(f"  sin ofertas que cumplan; reintento en 10 min ({int((time.time()-t0)/60)} min esperando)")
        time.sleep(600)
    of = ofertas[0]
    log(f"  oferta más barata: #{of.id} {of.num_gpus}x {of.gpu} USD {of.usd_h:.3f}/h · fiabilidad {of.fiabilidad:.3f}"
        f" · {'datacenter' if of.datacenter else 'verificada'} · {of.pais} · RAM {of.ram_gb:.0f} GB")
    horas_max_por_presupuesto = max_usd / max(of.usd_h, 1e-6)
    horas_tope = min(max_horas, horas_max_por_presupuesto)
    log(f"  tope de esta corrida: {horas_tope:.1f} h (max_horas {max_horas}, presupuesto USD {max_usd})")

    # ---- 2. alquilar ----
    env = {
        "REMUSICAL_MANIFIESTO_B64": base64.b64encode(json.dumps(manifiesto).encode()).decode(),
        "REMUSICAL_WORKERS": str(workers),
        "REMUSICAL_MODO": "local",
        "ELEVENLABS_API_KEY": os.getenv("ELEVENLABS_API_KEY", ""),
    }
    for k in ("S3_ENDPOINT", "S3_KEY", "S3_SECRET", "S3_REGION"):
        if os.getenv(k):
            env[k] = os.environ[k]
    env.update(env_extra or {})
    iid = v.alquilar(of, imagen=imagen, disco_gb=disco_gb, env=env, onstart=_onstart(workers),
                     etiqueta=f"remusical-{manifiesto.get('nombre', 'tanda')}", puertos=(PUERTO_ESTADO,))
    log(f"  instancia {iid} alquilada")
    t_alq = time.time()
    resumen = dict(oferta=of.__dict__, instancia=iid, tanda=None, horas=0.0, usd=0.0, motivo="")

    try:
        # ---- 3. esperar que arranque ----
        st = v.esperar_running(iid, timeout_s=arranque_s, log=log)
        url = Vast.url_publica(st, PUERTO_ESTADO)
        log(f"  corriendo · estado en {url or '(puerto no mapeado todavía)'}")

        # ---- 4. mirar hasta que termine, con los topes ----
        ultimo_ok = time.time()
        while True:
            time.sleep(60)
            horas = (time.time() - t_alq) / 3600
            resumen.update(horas=round(horas, 2), usd=round(horas * of.usd_h, 3))
            if horas >= horas_tope:
                resumen["motivo"] = f"tope de {horas_tope:.1f} h alcanzado"
                log(f"  {resumen['motivo']}: se destruye")
                break
            if not url:
                url = Vast.url_publica(v.estado(iid), PUERTO_ESTADO)
            e = _estado_http(url) if url else None
            if e:
                ultimo_ok = time.time()
                resumen["tanda"] = e
                log(f"  {e.get('listo', 0)} listos · {e.get('en curso', 0)} en curso · {e.get('pendiente', 0)} pendientes"
                    f" · {horas:.2f} h · USD {horas*of.usd_h:.2f}")
                if e.get("terminada"):
                    resumen["motivo"] = "tanda terminada"
                    break
            elif time.time() - ultimo_ok > silencio_s:
                resumen["motivo"] = f"sin respuesta {silencio_s} s"
                log(f"  {resumen['motivo']}: se destruye")
                break
            a = v.estado(iid).get("actual_status")
            if a in ("exited", "error"):
                resumen["motivo"] = f"instancia {a}"
                break
    finally:
        # ---- 5. DESTRUIR, pase lo que pase ----
        try:
            v.destruir(iid)
            log(f"  instancia {iid} destruida")
        except Exception as e:
            log(f"  ⚠ no se pudo destruir {iid}: {e} — DESTRUIR A MANO en console.vast.ai")
            resumen["motivo"] += " | NO DESTRUIDA"
    return resumen
