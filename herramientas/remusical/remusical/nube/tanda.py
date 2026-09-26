# -*- coding: utf-8 -*-
"""
Corredor de TANDAS: muchos videos, N en paralelo, reanudable. Corre igual en tu
notebook (`workers=1`) o dentro de la instancia de Vast (`workers=4`).

Manifiesto (JSON):
  {
    "nombre": "tanda-septiembre",
    "destino": "s3://bucket/carpeta"   |  "C:/salidas",
    "videos": [
      {"id": "v001", "origen": "s3://bucket/entrada/a.mp4"},
      {"id": "v002", "origen": "https://.../b.mp4"},
      {"id": "v003", "origen": "C:/videos/c.mp4"}
    ],
    "opciones": {"separar_completo": false, "takes": 3}
  }

Orígenes: ruta local, http(s) o s3:// (S3-compatible: Backblaze B2, MinIO, AWS; boto3).
Estado: `estado.json` junto al destino, un registro por video (pendiente / en curso /
listo / revisar / error). Si la máquina se cae, otra instancia retoma sin repetir lo hecho.
Dentro de la instancia, `servir_estado()` expone el progreso por HTTP en :8790 para que el
provisionador lo mire desde afuera y sepa cuándo destruirla.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import traceback
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

from .. import config as C


# ---------------------------------------------------------------- almacén (local / http / s3)
def _s3():
    try:
        import boto3
    except ImportError:
        raise RuntimeError("origen/destino s3:// necesita boto3 (pip install boto3)")
    return boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT") or None,
                        aws_access_key_id=os.getenv("S3_KEY"), aws_secret_access_key=os.getenv("S3_SECRET"),
                        region_name=os.getenv("S3_REGION") or None)


def _split_s3(uri: str) -> tuple[str, str]:
    sin = uri[5:]
    b, _, k = sin.partition("/")
    return b, k


def bajar(origen: str, dst: Path, log=print) -> Path:
    """local | http(s) | s3:// | drive://<file_id>  (Drive vía cuenta de servicio: sólo
    lectura, sólo la carpeta que el usuario compartió — ver nube/drive_sa.py)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if origen.startswith("drive://"):
        from . import drive_sa
        return drive_sa.bajar(origen[len("drive://"):], dst,
                              progreso=lambda f: log(f"    bajando {f*100:.0f}%") if int(f * 10) % 5 == 0 else None)
    if origen.startswith("s3://"):
        b, k = _split_s3(origen)
        _s3().download_file(b, k, str(dst))
    elif origen.startswith(("http://", "https://")):
        with urllib.request.urlopen(origen, timeout=120) as r, open(dst, "wb") as f:
            shutil.copyfileobj(r, f, 32 * 1024 * 1024)
    else:
        shutil.copy(origen, dst)
    return dst


def subir(local: Path, destino: str, log=print) -> str:
    if destino.startswith("s3://"):
        b, k = _split_s3(destino.rstrip("/") + "/" + local.name)
        _s3().upload_file(str(local), b, k)
        return f"s3://{b}/{k}"
    d = Path(destino)
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(local, d / local.name)
    return str(d / local.name)


def leer_texto(uri: str) -> str:
    if uri.startswith("s3://"):
        b, k = _split_s3(uri)
        return _s3().get_object(Bucket=b, Key=k)["Body"].read().decode("utf-8")
    if uri.startswith(("http://", "https://")):
        with urllib.request.urlopen(uri, timeout=60) as r:
            return r.read().decode("utf-8")
    return Path(uri).read_text(encoding="utf-8")


def escribir_texto(uri: str, texto: str):
    if uri.startswith("s3://"):
        b, k = _split_s3(uri)
        _s3().put_object(Bucket=b, Key=k, Body=texto.encode("utf-8"), ContentType="application/json")
    else:
        p = Path(uri)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texto, encoding="utf-8")


# ---------------------------------------------------------------- la tanda
class Tanda:
    def __init__(self, manifiesto: dict, trabajo: Path | None = None, log=print):
        self.m = manifiesto
        self.destino = manifiesto["destino"].rstrip("/")
        self.trabajo = trabajo or (C.TRABAJO / "tanda" / manifiesto.get("nombre", "tanda"))
        self.trabajo.mkdir(parents=True, exist_ok=True)
        self.log = log
        self.uri_estado = self.destino + "/estado.json"
        self.lock = threading.Lock()
        self.estado = self._cargar_estado()

    def _cargar_estado(self) -> dict:
        try:
            e = json.loads(leer_texto(self.uri_estado))
        except Exception:
            e = {"nombre": self.m.get("nombre"), "videos": {}}
        for v in self.m["videos"]:
            e["videos"].setdefault(v["id"], {"estado": "pendiente"})
            if e["videos"][v["id"]]["estado"] == "en curso":     # quedó de una instancia caída
                e["videos"][v["id"]]["estado"] = "pendiente"
        return e

    def _guardar(self):
        with self.lock:
            self.estado["actualizado"] = time.strftime("%Y-%m-%d %H:%M:%S")
            escribir_texto(self.uri_estado, json.dumps(self.estado, indent=1, ensure_ascii=False))

    def resumen(self) -> dict:
        c = {}
        for v in self.estado["videos"].values():
            c[v["estado"]] = c.get(v["estado"], 0) + 1
        return dict(nombre=self.m.get("nombre"), total=len(self.m["videos"]), **c,
                    terminada=all(v["estado"] in ("listo", "revisar", "error", "sin_musica")
                                  for v in self.estado["videos"].values()))

    def _uno(self, v: dict):
        from ..orquestador import procesar
        vid = v["id"]
        est = self.estado["videos"][vid]
        est.update(estado="en curso", inicio=time.strftime("%Y-%m-%d %H:%M:%S"))
        self._guardar()
        wdir = self.trabajo / vid
        try:
            nombre = v.get("nombre") or (Path(v["origen"].split("?")[0]).name if not v["origen"].startswith("drive://") else f"{vid}.mp4")
            local = bajar(v["origen"], wdir / nombre, self.log)
            op = self.m.get("opciones", {})
            inf = procesar(local, salida_dir=wdir / C.PREFIJO, separar_completo=bool(op.get("separar_completo")),
                           takes_por_region=int(op.get("takes", C.TAKES_MAX)),
                           log=lambda m: self.log(f"[{vid}] {m}"), progreso=lambda e, f: est.update(etapa=e, progreso=round(f, 3)))
            # Si el manifiesto trae URLs firmadas, se usan: la máquina sube SIN credenciales.
            firmadas = v.get("subidas") or {}
            subidos, sin_url = [], []
            for p in sorted((wdir / C.PREFIJO).glob("*")):
                url = firmadas.get(p.name)
                if url:
                    from .bucket import subir_con_url
                    if subir_con_url(url, p, self.log):
                        subidos.append(p.name)
                    else:
                        sin_url.append(f"{p.name} (>5 GB)")
                elif firmadas:
                    sin_url.append(p.name)
                else:
                    subidos.append(subir(p, f"{self.destino}/{vid}", self.log))
            if sin_url:
                est["sin_subir"] = sin_url
                self.log(f"[{vid}] sin URL firmada: {sin_url}")
            est.update(estado="listo" if inf["estado"] == "ENTREGABLE" else inf["estado"].lower(),
                       salidas=subidos, creditos=inf.get("creditos_eleven"), segundos=inf.get("segundos"),
                       fin=time.strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            est.update(estado="error", error=f"{type(e).__name__}: {e}", fin=time.strftime("%Y-%m-%d %H:%M:%S"))
            self.log(f"[{vid}] ERROR {traceback.format_exc()[-600:]}")
        finally:
            shutil.rmtree(wdir, ignore_errors=True)         # nada queda en la máquina
            self._guardar()

    def correr(self, workers: int = 1) -> dict:
        pendientes = [v for v in self.m["videos"] if self.estado["videos"][v["id"]]["estado"] == "pendiente"]
        self.log(f"tanda {self.m.get('nombre')}: {len(pendientes)} pendientes de {len(self.m['videos'])}, {workers} en paralelo")
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            list(ex.map(self._uno, pendientes))
        r = self.resumen()
        self.log(f"tanda terminada: {r}")
        return r


# ---------------------------------------------------------------- servidor de estado (dentro de la instancia)
def servir_estado(tanda: Tanda, puerto: int = 8790):
    """GET /estado → resumen JSON. POST /parar → la tanda no toma más videos (y el
    provisionador destruye la instancia). Sin auth: sólo expone contadores."""
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = json.dumps(tanda.resumen()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path.startswith("/parar"):
                for v in tanda.m["videos"]:
                    if tanda.estado["videos"][v["id"]]["estado"] == "pendiente":
                        tanda.estado["videos"][v["id"]]["estado"] = "cancelado"
                tanda._guardar()
            self.send_response(200)
            self.end_headers()

    srv = HTTPServer(("0.0.0.0", puerto), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    """Lo que corre DENTRO de la instancia:  python -m remusical.nube.tanda
    Lee el manifiesto de REMUSICAL_MANIFIESTO (JSON) o REMUSICAL_MANIFIESTO_URI."""
    import base64
    raw = os.getenv("REMUSICAL_MANIFIESTO_B64")
    if raw:
        m = json.loads(base64.b64decode(raw).decode("utf-8"))
    elif os.getenv("REMUSICAL_MANIFIESTO_URI"):
        m = json.loads(leer_texto(os.environ["REMUSICAL_MANIFIESTO_URI"]))
    elif len(sys.argv) > 1:
        m = json.loads(leer_texto(sys.argv[1]))
    else:
        raise SystemExit("falta el manifiesto (REMUSICAL_MANIFIESTO_B64, REMUSICAL_MANIFIESTO_URI o argumento)")
    workers = int(os.getenv("REMUSICAL_WORKERS", "4"))
    t = Tanda(m)
    servir_estado(t)
    t.correr(workers=workers)
    # se queda sirviendo el estado unos minutos para que el provisionador lea "terminada"
    time.sleep(int(os.getenv("REMUSICAL_ESPERA_FINAL_S", "300")))


if __name__ == "__main__":
    main()
