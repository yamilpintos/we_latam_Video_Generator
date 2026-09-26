# -*- coding: utf-8 -*-
"""
Prueba el provisionador contra un Vast.ai FALSO (un servidor HTTP local que se hace pasar
por la API), sin alquilar nada:

  A. elige la oferta VERIFICADA más barata que cumple el tope (ignora las no verificadas
     y las más caras aunque tengan mejor GPU)
  B. sin ofertas que cumplan → error, sin alquilar
  C. alquila con la imagen, el manifiesto y los puertos; espera 'running'; lee el estado
     de la tanda por HTTP; al terminar la tanda DESTRUYE la instancia
  D. si la instancia no arranca → la destruye igual
  E. tope de horas / presupuesto → destruye aunque la tanda no haya terminado
  F. pánico: destruye todas las instancias remusical-*

Correr:  cd apps/remusical && python -m tests.test_vast_falso
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from remusical.nube import provisionar, vast  # noqa: E402

fallos = []


def check(c, m):
    print(("  OK   " if c else "  FALLA") + " " + m)
    if not c:
        fallos.append(m)


# ---------------------------------------------------------------- Vast falso
class Falso:
    def __init__(self):
        self.ofertas = []
        self.alquileres = []
        self.destruidas = []
        self.estado_inst = {}
        self.arranca = True
        self.tanda_terminada = False
        self.tanda_puerto = 0

    def handler(self):
        f = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, code, obj):
                b = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                q = json.loads(self.rfile.read(n) or b"{}")
                if self.path.startswith("/bundles"):
                    tope = q.get("dph_total", {}).get("lte")
                    ofs = [o for o in f.ofertas if o["verification"] == "verified" and o["rentable"]
                           and (tope is None or o["dph_total"] <= tope) and o["num_gpus"] >= q.get("num_gpus", {}).get("gte", 1)]
                    return self._json(200, {"offers": sorted(ofs, key=lambda o: o["dph_total"])})
                self._json(404, {})

            def do_PUT(self):
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                oid = int(self.path.strip("/").split("/")[1])
                iid = 9000 + len(f.alquileres)
                f.alquileres.append(dict(oferta=oid, instancia=iid, body=body))
                f.estado_inst[iid] = dict(id=iid, actual_status=None, label=body.get("label"),
                                          public_ipaddr="127.0.0.1", ports={"8790/tcp": [{"HostPort": str(f.tanda_puerto)}]})
                threading.Timer(0.5, lambda: f.estado_inst[iid].update(actual_status="running" if f.arranca else "error", status_msg="" if f.arranca else "Error: no cuda")).start()
                self._json(200, {"success": True, "new_contract": iid})

            def do_GET(self):
                p = self.path.strip("/").split("/")
                if p[0] == "instances" and len(p) > 1:
                    return self._json(200, {"instances": f.estado_inst.get(int(p[1]), {})})
                if p[0] == "instances":
                    return self._json(200, {"instances": list(f.estado_inst.values())})
                if p[0] == "estado":
                    return self._json(200, {"nombre": "t", "total": 2, "listo": 2 if f.tanda_terminada else 1,
                                            "en curso": 0 if f.tanda_terminada else 1, "terminada": f.tanda_terminada})
                self._json(404, {})

            def do_DELETE(self):
                iid = int(self.path.strip("/").split("/")[1])
                f.destruidas.append(iid)
                f.estado_inst.pop(iid, None)
                self._json(200, {"success": True})
        return H


def servidor(f):
    srv = HTTPServer(("127.0.0.1", 0), f.handler())
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def oferta(id, usd, verified=True, gpus=4, gpu="RTX 4090", rel=0.99, dc=False):
    """★ Con los nombres que usa Vast DE VERDAD (comprobado contra la API pública el
    30-ago-2026): `verification` es un string de tres valores y `hosting_type` es 0/1.
    NO existen las claves `verified` ni `datacenter` en la respuesta. Si este falso miente
    sobre la forma de los datos, el test no guarda nada."""
    return dict(id=id, gpu_name=gpu, num_gpus=gpus, dph_total=usd, reliability2=rel,
                verification="verified" if verified else "unverified",
                rentable=True, hosting_type=1 if dc else 0,
                disk_space=200, cpu_ram=32768, inet_down=800, cuda_max_good=12.4, geolocation="US")


f = Falso()
srv = servidor(f)
puerto = srv.server_address[1]
f.tanda_puerto = puerto
api = f"http://127.0.0.1:{puerto}"
V = vast.Vast(api_key="falsa", api=api)
mf = dict(nombre="t", destino="/tmp/x", videos=[dict(id="a", origen="a.mp4"), dict(id="b", origen="b.mp4")])
_sleep_real = time.sleep                                            # `time` es el mismo módulo en todos lados
time.sleep = lambda s: _sleep_real(min(s, 0.05))                    # sin esperas reales
provisionar._estado_http = lambda url: json.loads(__import__("urllib.request").request.urlopen(f"{api}/estado", timeout=5).read())

print("\nA. elige la verificada más barata que cumple el tope")
f.ofertas = [oferta(1, 0.20, verified=False), oferta(2, 0.55), oferta(3, 0.41), oferta(4, 0.30, gpus=2), oferta(5, 0.90, gpu="H100")]
# ★ un host al que le SACARON la verificación: más barato que todos, y no se puede tomar.
# Es el caso que el `verified: true/false` booleano no sabía ni nombrar.
f.ofertas.insert(0, dict(oferta(6, 0.10), verification="deverified"))
ofs = V.buscar(gpu="RTX 4090", num_gpus=4, tope_usd_h=0.60)
check(ofs and ofs[0].id == 3, f"elegida #{ofs[0].id if ofs else None} a USD {ofs[0].usd_h if ofs else '-'} (esperada #3 a 0,41: la #1 es más barata pero NO verificada; la #4 tiene 2 GPUs)")

print("\nB. sin ofertas que cumplan -> error, nada alquilado")
try:
    provisionar.correr_tanda_en_vast(mf, tope_usd_h=0.10, _vast=V, log=lambda m: None)
    check(False, "debió fallar")
except vast.VastError as e:
    check(not f.alquileres, f"VastError sin alquilar: {str(e)[:60]}")

print("\nC. alquila, espera running, lee la tanda por HTTP, DESTRUYE al terminar")
f.tanda_terminada = True
r = provisionar.correr_tanda_en_vast(mf, tope_usd_h=0.60, gpus=4, _vast=V, log=lambda m: None)
alq = f.alquileres[-1]
check(alq["oferta"] == 3, f"alquiló la oferta #{alq['oferta']}")
check(alq["body"]["image"] == provisionar.IMAGEN and "REMUSICAL_MANIFIESTO_B64" in alq["body"]["env"] and "-p 8790:8790" in alq["body"]["env"], "imagen, manifiesto y puerto en el alquiler")
check(r["motivo"] == "tanda terminada" and r["instancia"] in f.destruidas, f"motivo '{r['motivo']}', instancia {r['instancia']} destruida")

print("\nD. la instancia no arranca -> se destruye igual")
f.arranca = True
f.tanda_terminada = True
f.arranca = False
try:
    provisionar.correr_tanda_en_vast(mf, tope_usd_h=0.60, _vast=V, log=lambda m: None)
    check(False, "debió fallar")
except vast.VastError as e:
    check(f.alquileres[-1]["instancia"] in f.destruidas, f"error '{str(e)[:50]}' y la instancia destruida")
f.arranca = True

print("\nE. tope de horas/presupuesto -> destruye aunque la tanda siga")
f.tanda_terminada = False
r = provisionar.correr_tanda_en_vast(mf, tope_usd_h=0.60, max_horas=0.0002, _vast=V, log=lambda m: None)   # tope ≈ 0,7 s reales
check("tope" in r["motivo"] and r["instancia"] in f.destruidas, f"motivo '{r['motivo']}', destruida")

print("\nF. pánico: destruye todas las remusical-*")
V.alquilar(3, imagen="x", disco_gb=10, env={}, onstart="", etiqueta="remusical-loca")
V.alquilar(3, imagen="x", disco_gb=10, env={}, onstart="", etiqueta="otra-cosa")
ids = V.destruir_todas("remusical-loca")
check(len(ids) == 1 and any(i.get("label") == "otra-cosa" for i in f.estado_inst.values()), f"destruyó {ids}, dejó la ajena")

print()
if fallos:
    print(f"FALLARON {len(fallos)}:", *fallos, sep="\n  ")
    sys.exit(1)
print("VAST FALSO: TODO PASA")
