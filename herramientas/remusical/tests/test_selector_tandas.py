# -*- coding: utf-8 -*-
"""
Prueba el SELECTOR de tandas de la web de punta a punta, sin credenciales, sin tocar
Drive, sin tocar el bucket y sin alquilar una sola máquina.

  A. `/config` dice exactamente qué falta configurar (y no se lo guarda)
  B. `/preparar` con una carpeta que la cuenta de servicio NO ve: ok=False y la ayuda
  C. `/preparar` con acceso: lista los episodios, el precio REAL del momento y el costo
  D. la estimación es la fórmula medida, y crece con la duración (no es un número fijo)
  E. `/crear` arma el manifiesto SÓLO con los episodios marcados y corre la tanda
  F. `/cancelar` destruye la instancia (es el corte de gasto que se aprieta a mano)
  G. `/archivos` borra del bucket lo que ya se bajó

Correr:  cd apps/remusical && python -m tests.test_selector_tandas
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI                                    # noqa: E402
from fastapi.testclient import TestClient                      # noqa: E402

from remusical import tandas_web as T                          # noqa: E402
from remusical import api as fachada                           # noqa: E402
from remusical.nube import drive_sa, bucket, provisionar, vast  # noqa: E402

fallos = []


def check(c, m):
    print(("  OK   " if c else "  FALLA") + " " + m)
    if not c:
        fallos.append(m)


# ---------------------------------------------------------------- dobles
class Vid:
    def __init__(self, i, n, dur, tam):
        self.id, self.nombre, self.duracion_s, self.tamano = i, n, dur, tam


EPISODIOS = [Vid(f"v{i}", f"Ep {i}.mp4", 1620.0, 3_800_000_000) for i in range(1, 6)]   # 5 × 27 min


class OfertaFalsa:
    usd_h, gpu, num_gpus, pais, fiabilidad = 0.512, "RTX 4090", 4, "Suecia", 0.994


lanzadas, destruidas, borrados = [], [], []


def manifiesto_falso(nombre, carpeta_drive_id, prefijo_bucket=None, archivos=None,
                     completo=False, takes=1, horas_firma=8):
    ids = list(archivos or [v.id for v in EPISODIOS])
    return dict(nombre=nombre, destino=f"s3://b/{prefijo_bucket}",
                videos=[dict(id=i, origen=f"drive://{i}", nombre=f"{i}.mp4") for i in ids])


def tanda_vast_falso(m, **kw):
    lanzadas.append((m, kw))
    return dict(instancia=98765, usd_gpu=0.41, horas=0.8,
                tanda=dict(terminada=True, listos=len(m["videos"]), fallados=0))


def montar():
    T._tandas.clear()
    T._guardar = lambda: None                       # nada de escribir el registro real
    app = FastAPI()
    app.include_router(T.router)
    return TestClient(app)


cli = montar()

# ---------------------------------------------------------------- A
print("\nA. /config dice qué falta")
import os                                           # noqa: E402
for k in ("VAST_API_KEY", "ELEVENLABS_API_KEY", "S3_KEY", "S3_BUCKET",
          "GOOGLE_SA_JSON_B64", "GOOGLE_SA_JSON"):
    os.environ.pop(k, None)
c = cli.get("/api/tandas/config").json()
check(c["listo"] is False and not any([c["vast"], c["eleven"], c["bucket"], c["sa"]]),
      f"sin nada configurado: listo={c['listo']}, {c}")
os.environ["VAST_API_KEY"] = "x"; os.environ["S3_KEY"] = "x"; os.environ["S3_BUCKET"] = "b"
c = cli.get("/api/tandas/config").json()
check(c["vast"] and c["bucket"] and not c["sa"] and not c["listo"],
      "con Vast y bucket puestos sigue faltando la cuenta de servicio")

# ---------------------------------------------------------------- B
print("\nB. carpeta que la cuenta de servicio no ve")
drive_sa.verificar_acceso = lambda cid: dict(ok=False, error="File not found: XYZ",
                                             email="rm@proj.iam.gserviceaccount.com",
                                             ayuda="Compartí la carpeta con rm@proj.iam.gserviceaccount.com como Lector")
bucket.verificar = lambda: dict(ok=True, bucket="b")
r = cli.get("/api/tandas/preparar", params={"carpeta": "XYZ"}).json()
check(r["ok"] is False and "Lector" in r["drive"]["ayuda"], "ok=False y dice qué hacer")

# ---------------------------------------------------------------- C
print("\nC. carpeta accesible: episodios + precio real + costo")
drive_sa.verificar_acceso = lambda cid: dict(ok=True, carpeta="Viajero Errante T3",
                                             videos=len(EPISODIOS), email="rm@proj")
drive_sa.listar_videos = lambda cid, d=None: EPISODIOS
provisionar.ofertas_seguras = lambda gpus=4, solo_datacenter=True, **kw: [OfertaFalsa()]
r = cli.get("/api/tandas/preparar", params={"carpeta": "OK1"}).json()
check(r["ok"] and r["carpeta"] == "Viajero Errante T3", f"carpeta {r.get('carpeta')!r}")
check(len(r["videos"]) == 5 and r["videos"][0]["nombre"] == "Ep 1.mp4", f"{len(r['videos'])} episodios")
check(abs(r["duracion_total_s"] - 8100) < 1, f"duración total {r['duracion_total_s']} s")
check(r["usd_h"] == 0.512 and r["ofertas"][0]["gpu"] == "RTX 4090",
      f"usó el precio real del momento: USD {r['usd_h']}/h")
check(set(r["constantes"]) == {"cr_por_min_musica", "usd_por_credito", "gpu_min_por_min"},
      "manda las constantes para que el navegador recalcule el subconjunto")

# ---------------------------------------------------------------- D
print("\nD. la estimación es la fórmula medida")
e = r["estimacion"]
min_mus = 135 * 0.5                                  # 8100 s = 135 min, mitad con música
esperado = min_mus * T.CR_POR_MIN_MUSICA * T.USD_POR_CREDITO
check(abs(e["usd_eleven"] - esperado) < 0.02, f"ElevenLabs USD {e['usd_eleven']} ≈ {esperado:.2f}")
check(e["usd_gpu"] < e["usd_eleven"] / 5, f"la GPU (USD {e['usd_gpu']}) es calderilla al lado de la música")
check(abs(e["usd_total"] - (e["usd_eleven"] + e["usd_gpu"])) < 0.01, "el total es la suma")
doble = T.estimar(8100 * 2, 0.5, 0.512, 4)
check(abs(doble["usd_total"] - 2 * e["usd_total"]) < 0.05, "el doble de video cuesta el doble")
mitad = T.estimar(8100, 0.25, 0.512, 4)
check(mitad["usd_eleven"] < e["usd_eleven"], "menos música, menos plata")

# ---------------------------------------------------------------- E
print("\nE. /crear lanza sólo los episodios marcados")
fachada.manifiesto_drive = manifiesto_falso
fachada.tanda_vast = tanda_vast_falso
r = cli.post("/api/tandas/crear", json=dict(
    carpeta="OK1", nombre="Viajero Errante T3", archivos=["v2", "v4"],
    opciones=dict(separar_completo=False),
    nube=dict(gpus=4, tope_usd_h=0.6, max_usd=50, max_horas=12, solo_datacenter=True))).json()
tid = r["id"]
for _ in range(100):
    t = cli.get(f"/api/tandas/{tid}").json()
    if t["estado"] not in ("preparando", "procesando"):
        break
    time.sleep(0.05)
check(t["estado"] == "lista", f"estado final {t['estado']} {t.get('error') or ''}")
m, kw = lanzadas[-1]
check([v["id"] for v in m["videos"]] == ["v2", "v4"], f"fue con los 2 marcados: {[v['id'] for v in m['videos']]}")
check(kw["max_usd"] == 50 and kw["max_horas"] == 12 and kw["solo_datacenter"] is True,
      f"los topes de gasto llegaron intactos: {kw['max_usd']} USD / {kw['max_horas']} h / dc={kw['solo_datacenter']}")
check(t["videos"] == 2 and t["instancia"] == 98765, f"{t['videos']} videos, instancia {t['instancia']}")
check(cli.get("/api/tandas").json()["tandas"][0]["id"] == tid, "aparece en el listado")

# ---------------------------------------------------------------- F
print("\nF. cancelar destruye la máquina")
vast.Vast.destruir = lambda self, i: destruidas.append(i)
vast.Vast.destruir_todas = lambda self, etq=None: []
vast.Vast.__init__ = lambda self, *a, **k: None
r = cli.post(f"/api/tandas/{tid}/cancelar").json()
check(destruidas == [98765], f"destruyó la instancia {destruidas}")
check(cli.get(f"/api/tandas/{tid}").json()["estado"] == "cancelada", "queda marcada cancelada")

# ---------------------------------------------------------------- G
print("\nG. limpiar el bucket")
bucket.borrar = lambda pref, b=None: (borrados.append(pref), 7)[1]
r = cli.request("DELETE", f"/api/tandas/{tid}/archivos").json()
check(r["borrados"] == 7 and borrados and borrados[0].startswith("Viajero_Errante_T3-"),
      f"borró {r['borrados']} con el prefijo {borrados}")

print()
if fallos:
    print(f"FALLARON {len(fallos)}:", *fallos, sep="\n  ")
    sys.exit(1)
print("SELECTOR DE TANDAS: TODO PASA")
