# -*- coding: utf-8 -*-
"""
Prueba las guardas de gasto contra un REPLICATE FALSO.

Un servidor local se hace pasar por api.replicate.com: registra los headers con que se
crea cada predicción, se queda en "processing" para siempre (o devuelve 500 si se le
pide), y anota cada POST .../cancel. Así se verifica lo que importa sin gastar un
centavo:

  A. la predicción se crea con `Cancel-After`
  B. si el sondeo pasa el límite, la web CANCELA (no sólo marca error)
  C. si Replicate no responde 6 veces, la web CANCELA
  D. el tope de simultáneos rechaza el 4º trabajo (429)
  E. el mismo video en curso se rechaza (409)
  F. "Cancelar" de un trabajo llega a Replicate
  G. "Cancelar TODO" cancela lo que la cuenta tiene corriendo

Correr:  cd apps/remusical && python -m tests.test_guardas_replicate
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

PUERTO_FALSO = 8799
os.environ["REMUSICAL_MODO"] = "replicate"
os.environ["REPLICATE_API"] = f"http://127.0.0.1:{PUERTO_FALSO}/v1"
os.environ["REPLICATE_API_TOKEN"] = "r8_test_falso"
os.environ["REMUSICAL_MAX_SIMULTANEOS"] = "3"
os.environ["REMUSICAL_MAX_POR_DIA"] = "50"
os.environ["REMUSICAL_TRABAJO"] = str(RAIZ / "_trabajo" / "_test")


# ---------------------------------------------------------------- el Replicate falso
class Falso(BaseHTTPRequestHandler):
    creadas: list[dict] = []
    cancelaciones: list[str] = []
    fallar_get = False
    n = 0

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = json.loads(self.rfile.read(largo) or b"{}") if largo else {}
        if self.path.endswith("/predictions"):
            Falso.n += 1
            pid = f"pred{Falso.n}"
            Falso.creadas.append(dict(id=pid, cancel_after=self.headers.get("Cancel-After"), input=cuerpo.get("input")))
            self._json(201, dict(id=pid, status="starting", urls=dict(get=f"http://127.0.0.1:{PUERTO_FALSO}/v1/predictions/{pid}")))
        elif self.path.endswith("/cancel"):
            Falso.cancelaciones.append(self.path.split("/")[-2])
            self._json(200, dict(status="canceled"))
        else:
            self._json(404, dict(detail="?"))

    def do_GET(self):
        if Falso.fallar_get:
            self._json(500, dict(detail="caído"))
            return
        if self.path.endswith("/predictions"):
            vivas = [dict(id=c["id"], status="processing") for c in Falso.creadas if c["id"] not in Falso.cancelaciones]
            self._json(200, dict(results=vivas))
        else:
            pid = self.path.split("/")[-1]
            st = "canceled" if pid in Falso.cancelaciones else "processing"
            self._json(200, dict(id=pid, status=st, logs="PROGRESO mapa 0.100\nLOG hola\n", output=None))


srv = ThreadingHTTPServer(("127.0.0.1", PUERTO_FALSO), Falso)
threading.Thread(target=srv.serve_forever, daemon=True).start()

# ---------------------------------------------------------------- la web, con sesión falsa
from fastapi.testclient import TestClient      # noqa: E402
import remusical.web as W                       # noqa: E402

W._trabajos.clear()
W.SONDEO_MAX_S = 8                              # el límite de sondeo, acortado para el test


class _Creds:
    token = "ya29.falso"


W._creds = lambda s, forzar_refresh=False: _Creds()


class _DriveFalso:
    def files(self):
        return self

    def get(self, fileId, **k):
        self._id = fileId
        return self

    def execute(self):
        return dict(id=self._id, name=f"video_{self._id}.mp4", parents=["carpetaX"], size="1000")


W._drive = lambda s: _DriveFalso()
W.drive_io.meta = lambda d, fid: d.files().get(fileId=fid).execute()
W._sesiones["tok"] = dict(creds=dict(token="x"), email="test@x")
cli = TestClient(W.app, cookies={"rm_sesion": "tok"})

fallos = []


def check(cond, msg):
    print(("  OK   " if cond else "  FALLA") + " " + msg)
    if not cond:
        fallos.append(msg)


def espera(cond, seg):
    t0 = time.time()
    while time.time() - t0 < seg:
        if cond():
            return True
        time.sleep(0.3)
    return cond()


print("\nA. Cancel-After al crear")
r = cli.post("/api/musicalizar", json=dict(videos=["v1"]))
check(r.status_code == 200, f"crear trabajo -> {r.status_code} {r.text[:80]}")
espera(lambda: len(Falso.creadas) >= 1, 5)
check(Falso.creadas and Falso.creadas[0]["cancel_after"] == W.CANCEL_AFTER,
      f"header Cancel-After = {Falso.creadas[0]['cancel_after'] if Falso.creadas else None} (esperado {W.CANCEL_AFTER})")
check(Falso.creadas and Falso.creadas[0]["input"]["access_token"] == "ya29.falso", "el token de Drive viaja en el input")

print("\nE. el mismo video en curso se rechaza")
r = cli.post("/api/musicalizar", json=dict(videos=["v1"]))
check(r.status_code == 409, f"repetido -> {r.status_code}")

print("\nD. tope de simultáneos")
r = cli.post("/api/musicalizar", json=dict(videos=["v2", "v3"]))
check(r.status_code == 200, f"2 más (total 3) -> {r.status_code}")
r = cli.post("/api/musicalizar", json=dict(videos=["v4"]))
check(r.status_code == 429, f"el 4º -> {r.status_code} {r.json().get('detail', '')[:60]}")

print("\nB. el sondeo pasa el límite -> se CANCELA en Replicate")
ok = espera(lambda: "pred1" in Falso.cancelaciones, W.SONDEO_MAX_S + 12)
check(ok, f"pred1 cancelada tras el límite ({W.SONDEO_MAX_S}s): {Falso.cancelaciones}")
t1 = next(t for t in W._trabajos.values() if t["video_id"] == "v1")
check(t1["estado"] == "error" and "cancelado" in (t1["error"] or ""), f"estado del trabajo: {t1['estado']} / {t1['error']}")

print("\nF. cancelar un trabajo desde la web")
t2 = next(t for t in W._trabajos.values() if t["video_id"] == "v2")
r = cli.post(f"/api/trabajos/{t2['id']}/cancelar")
check(r.status_code == 200 and espera(lambda: "pred2" in Falso.cancelaciones, 5), f"pred2 cancelada: {Falso.cancelaciones}")

print("\nG. cancelar TODO lo que corre en la cuenta")
# pred3 nació casi junto con pred1; si la máquina va lenta, el sondeo (SONDEO_MAX_S=8 s)
# ya la canceló solo antes de llegar acá y el pánico no encuentra nada que cancelar.
# Las dos cosas son correctas: lo que se exige es que pred3 termine cancelada y que no
# quede NADA corriendo. (Fallaba al azar con la CPU ocupada: 54 s de corrida vs 44.)
r = cli.post("/api/replicate/cancelar_todo")
check(r.status_code == 200 and ("pred3" in r.json()["canceladas"] or "pred3" in Falso.cancelaciones),
      f"pred3 cancelada (por pánico o por el límite de sondeo) -> {r.json()} / ya canceladas: {Falso.cancelaciones}")
r = cli.get("/api/replicate/estado")
check(r.json()["corriendo"] == 0, f"estado después: {r.json()}")

print("\nC. Replicate no responde -> se CANCELA")
Falso.creadas.clear(); Falso.cancelaciones.clear(); W._trabajos.clear()
W.SONDEO_MAX_S = 600
r = cli.post("/api/musicalizar", json=dict(videos=["v9"]))
espera(lambda: len(Falso.creadas) >= 1, 5)
Falso.fallar_get = True
ok = espera(lambda: Falso.creadas and Falso.creadas[0]["id"] in Falso.cancelaciones, 60)
Falso.fallar_get = False
check(ok, f"cancelada tras 6 errores seguidos: {Falso.cancelaciones}")

print()
if fallos:
    print(f"FALLARON {len(fallos)}:", *fallos, sep="\n  ")
    sys.exit(1)
print("TODAS LAS GUARDAS PASAN")
