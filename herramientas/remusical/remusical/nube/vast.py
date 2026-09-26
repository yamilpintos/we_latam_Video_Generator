# -*- coding: utf-8 -*-
"""
Cliente de Vast.ai: buscar ofertas SEGURAS, elegir la más barata, alquilar, mirar, destruir.

API (docs.vast.ai, ago-2026):
  POST   /api/v0/bundles/            buscar ofertas (filtros JSON: verified, rentable, gpu_name…)
  PUT    /api/v0/asks/{id}/          alquilar una oferta → {"new_contract": <instance_id>}
  GET    /api/v0/instances/{id}/     estado: actual_status null → "loading" → "running"
  DELETE /api/v0/instances/{id}/     destruir → {"success": true}
  Authorization: Bearer $VAST_API_KEY

"Segura" acá quiere decir: `verified: true` (hosts con identidad verificada por Vast),
fiabilidad ≥ 0,98 y, si se pide, `datacenter`. Vast es un mercado de máquinas ajenas:
el host puede ver lo que corre. Por eso a la instancia sólo le llega la key de
ElevenLabs de la tanda y las credenciales del bucket — nunca tokens de Drive ni
secretos de Google (ver docs/VAST.md).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, asdict

import requests

API = os.getenv("VAST_API", "https://console.vast.ai/api/v0")


class VastError(RuntimeError):
    pass


def _verificada(o: dict) -> bool:
    """★ Vast manda `verification`, un STRING con tres valores: verified / unverified /
    DEVERIFIED (un host al que le SACARON la verificación). Ojo con la trampa: cualquier
    string no vacío es verdadero en Python, así que hay que comparar contra "verified"
    exacto — `bool(o["verification"])` daría True para "unverified".
    El `verified: true` booleano se acepta igual por si la API vuelve a cambiar."""
    v = o.get("verification")
    if isinstance(v, str):
        return v.strip().lower() == "verified"
    return bool(o.get("verified", False))


def _datacenter(o: dict) -> bool:
    """`hosting_type`: 0 = comunidad (la PC de alguien), 1 = datacenter."""
    return bool(o.get("datacenter", False)) or (o.get("hosting_type") or 0) == 1


@dataclass
class Oferta:
    id: int
    gpu: str
    num_gpus: int
    usd_h: float            # dph_total: la máquina entera, por hora
    fiabilidad: float
    verificada: bool
    datacenter: bool
    disco_gb: float
    ram_gb: float
    bajada_mbps: float
    cuda: float
    pais: str

    @staticmethod
    def de(o: dict) -> "Oferta":
        return Oferta(id=int(o["id"]), gpu=str(o.get("gpu_name", "?")), num_gpus=int(o.get("num_gpus", 1) or 1),
                      usd_h=float(o.get("dph_total", 0) or 0), fiabilidad=float(o.get("reliability2", o.get("reliability", 0)) or 0),
                      verificada=_verificada(o), datacenter=_datacenter(o),
                      disco_gb=float(o.get("disk_space", 0) or 0), ram_gb=float(o.get("cpu_ram", 0) or 0) / 1024.0,
                      bajada_mbps=float(o.get("inet_down", 0) or 0), cuda=float(o.get("cuda_max_good", 0) or 0),
                      pais=str(o.get("geolocation", "") or ""))


class Vast:
    def __init__(self, api_key: str | None = None, api: str = API, timeout: int = 60):
        self.key = api_key or os.getenv("VAST_API_KEY", "")
        if not self.key:
            raise VastError("falta VAST_API_KEY")
        self.api = api.rstrip("/")
        self.timeout = timeout

    def _h(self):
        return {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}

    def _req(self, metodo: str, ruta: str, body: dict | None = None) -> dict:
        r = requests.request(metodo, f"{self.api}{ruta}", headers=self._h(), json=body, timeout=self.timeout)
        if r.status_code >= 400:
            raise VastError(f"Vast {metodo} {ruta} → HTTP {r.status_code}: {r.text[:300]}")
        try:
            return r.json() if r.text else {}
        except ValueError:
            raise VastError(f"Vast {metodo} {ruta}: respuesta no JSON: {r.text[:200]}")

    # ------------------------------------------------------------ buscar
    def buscar(self, gpu: str = "RTX 4090", num_gpus: int = 4, tope_usd_h: float | None = None,
               disco_gb: int = 80, fiabilidad_min: float = 0.98, solo_datacenter: bool = False,
               cuda_min: float = 12.1, bajada_min_mbps: float = 200, limite: int = 30) -> list[Oferta]:
        """Ofertas SEGURAS (verificadas) que cumplen los mínimos, de más barata a más cara."""
        q = {
            "verified": {"eq": True},
            "rentable": {"eq": True},
            "gpu_name": {"eq": gpu},
            "num_gpus": {"gte": num_gpus},
            "reliability2": {"gte": fiabilidad_min},
            "disk_space": {"gte": disco_gb},
            "cuda_max_good": {"gte": cuda_min},
            "inet_down": {"gte": bajada_min_mbps},
            "direct_port_count": {"gte": 1},
            "order": [["dph_total", "asc"]],
            "type": "on-demand",
            "limit": limite,
        }
        if solo_datacenter:
            q["datacenter"] = {"eq": True}
        if tope_usd_h is not None:
            q["dph_total"] = {"lte": tope_usd_h}
        r = self._req("POST", "/bundles/", q)
        ofertas = [Oferta.de(o) for o in r.get("offers", [])]
        # el filtro del lado del servidor no siempre respeta todo: se vuelve a filtrar acá
        ofertas = [o for o in ofertas if o.verificada and o.fiabilidad >= fiabilidad_min
                   and o.num_gpus >= num_gpus and (tope_usd_h is None or o.usd_h <= tope_usd_h)
                   and (not solo_datacenter or o.datacenter)]
        return sorted(ofertas, key=lambda o: o.usd_h)

    @staticmethod
    def mas_barata(ofertas: list[Oferta]) -> Oferta | None:
        return min(ofertas, key=lambda o: o.usd_h) if ofertas else None

    # ------------------------------------------------------------ alquilar / mirar / destruir
    def alquilar(self, oferta: Oferta | int, imagen: str, disco_gb: int, env: dict[str, str],
                 onstart: str, etiqueta: str = "remusical", puertos: tuple[int, ...] = (8790,)) -> int:
        oid = oferta.id if isinstance(oferta, Oferta) else int(oferta)
        e = dict(env)
        for p in puertos:
            e[f"-p {p}:{p}"] = "1"                 # así se declaran los puertos en Vast
        body = {"image": imagen, "disk": disco_gb, "runtype": "args", "label": etiqueta,
                "env": e, "onstart": onstart}
        r = self._req("PUT", f"/asks/{oid}/", body)
        iid = r.get("new_contract")
        if not iid:
            raise VastError(f"alquilar: sin new_contract en la respuesta: {r}")
        return int(iid)

    def estado(self, instancia: int) -> dict:
        r = self._req("GET", f"/instances/{instancia}/")
        ins = r.get("instances")
        if isinstance(ins, list):
            ins = ins[0] if ins else {}
        return ins or {}

    def mis_instancias(self) -> list[dict]:
        r = self._req("GET", "/instances/")
        ins = r.get("instances", [])
        return ins if isinstance(ins, list) else [ins]

    def destruir(self, instancia: int) -> bool:
        r = self._req("DELETE", f"/instances/{instancia}/")
        return bool(r.get("success", True))

    def destruir_todas(self, etiqueta: str | None = "remusical") -> list[int]:
        """Botón de pánico: destruye todas las instancias (de esta etiqueta, o todas)."""
        ids = []
        for i in self.mis_instancias():
            if etiqueta is None or i.get("label") == etiqueta:
                try:
                    self.destruir(int(i["id"]))
                    ids.append(int(i["id"]))
                except Exception:
                    pass
        return ids

    def esperar_running(self, instancia: int, timeout_s: int = 900, log=print) -> dict:
        """Espera a que arranque. Si no arranca en timeout_s, la DESTRUYE y avisa:
        una instancia en 'loading' eterno también cobra."""
        t0 = time.time()
        while True:
            st = self.estado(instancia)
            a = st.get("actual_status")
            if a == "running":
                return st
            if a in ("exited", "error") or st.get("status_msg", "").lower().startswith("error"):
                self.destruir(instancia)
                raise VastError(f"la instancia {instancia} falló al arrancar: {st.get('status_msg')}")
            if time.time() - t0 > timeout_s:
                self.destruir(instancia)
                raise VastError(f"la instancia {instancia} no arrancó en {timeout_s} s: destruida")
            log(f"    instancia {instancia}: {a or 'creando'}… ({int(time.time()-t0)} s)")
            time.sleep(15)

    @staticmethod
    def url_publica(st: dict, puerto: int = 8790) -> str | None:
        ip = st.get("public_ipaddr")
        ports = st.get("ports") or {}
        m = ports.get(f"{puerto}/tcp") or []
        if ip and m:
            return f"http://{ip}:{m[0].get('HostPort')}"
        return None
