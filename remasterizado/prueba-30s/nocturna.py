"""Corrida desatendida de FlashVSR v1.1 Full en Vast: alquila, instala, procesa, baja y destruye.

    python nocturna.py <clip_entrada.mp4> <salida_local.mp4> [oferta_id]

Todo queda en nocturna.log. Si algo pasa del tiempo límite o falla, la instancia se destruye igual.
"""
import json, subprocess, sys, time, urllib.request
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(RAIZ))
from h3pipeline import vast
AQUI = Path(__file__).resolve().parent
LOG = AQUI / "nocturna.log"
IMAGEN = "vastai/base-image:cuda-12.4.1-cudnn-devel-ubuntu22.04-py311"
PORTAL = "localhost:1111:11111:/:Instance Portal|localhost:8080:18080:/:Jupyter|localhost:8080:8080:/terminals/1:Jupyter Terminal"
ENV = {"-p 1111:1111": "1", "-p 8080:8080": "1", "OPEN_BUTTON_PORT": "1111", "OPEN_BUTTON_TOKEN": "1",
       "JUPYTER_DIR": "/", "DATA_DIRECTORY": "/workspace/", "PORTAL_CONFIG": PORTAL}
REMOTO = "/workspace/prueba"
PY = "/venv/main/bin/python"
OFERTA_PREFERIDA = 36602059          # A100 SXM 80 GB, Chequia, $1,056/h
PRECIO_MAX = 1.30
T_SETUP_MIN, T_INFER_MIN = 30, 80

def log(*a):
    linea = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a)
    print(linea, flush=True)
    with LOG.open("a", encoding="utf-8") as f: f.write(linea + "\n")

def ssh(inst, cmd, timeout=120):
    _h, p, u = vast._ssh_args(inst)
    r = subprocess.run(["ssh", "-p", p, "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=25", u, cmd],
                       capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")

def scp_desde(inst, remoto, local):
    _h, p, u = vast._ssh_args(inst)
    r = subprocess.run(["scp", "-P", p, "-o", "StrictHostKeyChecking=accept-new", f"{u}:{remoto}", str(local)], capture_output=True)
    return r.returncode, r.stderr.decode("utf-8", "replace")[-300:]

def ofertas_a100():
    q = {"verified": {"eq": True}, "rentable": {"eq": True}, "num_gpus": {"eq": 1}, "gpu_name": {"in": ["A100 SXM4", "A100 PCIE"]},
         "gpu_ram": {"gte": 70000}, "disk_space": {"gte": 60}, "inet_down": {"gte": 500}, "reliability2": {"gte": 0.98},
         "dph_total": {"lte": PRECIO_MAX}, "order": [["dph_total", "asc"]], "type": "on-demand", "limit": 20}
    req = urllib.request.Request("https://console.vast.ai/api/v0/bundles/", data=json.dumps(q).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    ofs = json.load(urllib.request.urlopen(req, timeout=60))["offers"]
    return [o for o in ofs if not (o.get("geolocation") or "").endswith(", CN")]

def elegir(pref):
    ofs = ofertas_a100()
    for o in ofs:
        if o["id"] == pref: return o
    log(f"la oferta preferida {pref} no está; hay {len(ofs)} A100 de 80 GB")
    return ofs[0] if ofs else None

def crear(o):
    cuerpo = {"client_id": "me", "image": IMAGEN, "env": ENV, "disk": 60, "label": "flashvsr-nocturna",
              "onstart": "entrypoint.sh", "runtype": "jupyter_direc ssh_direc ssh_proxy",
              "image_login": None, "python_utf8": False, "lang_utf8": False, "use_jupyter_lab": False,
              "jupyter_dir": None, "cancel_unavail": False, "template_hash_id": None, "user": None}
    r = vast._pedir(f"/asks/{o['id']}/", metodo="PUT", cuerpo=cuerpo)
    if not r.get("success", True): raise RuntimeError(f"no alquiló: {r}")
    return r["new_contract"]

def esperar_marca(inst, archivo, ok, fallo, minutos, avance=None):
    t0 = time.time(); ultimo = ""
    while time.time() - t0 < minutos * 60:
        # -F: los marcadores son texto literal ("[listo]" como regex es una clase de caracteres
        # y coincide con casi cualquier línea: así se perdió la detección del Traceback el 18/9).
        rc, out, err = ssh(inst, f"grep -a -F -e '{ok}' -e '{fallo}' {archivo} 2>/dev/null | tail -2; "
                                 + (f"grep -a -E '{avance}' {archivo} 2>/dev/null | tail -1" if avance else "true"))
        out = out.strip()
        if out and out != ultimo:
            log("   ", out.replace("\n", " | ")[:300]); ultimo = out
        if ok in out and fallo not in out: return True
        if fallo in out: return False
        time.sleep(30)
    log(f"   tiempo límite de {minutos} min en {archivo}")
    return False

def main():
    entrada, salida = Path(sys.argv[1]), Path(sys.argv[2])
    pref = int(sys.argv[3]) if len(sys.argv) > 3 else OFERTA_PREFERIDA
    log("=== corrida nocturna ===", entrada.name, "→", salida.name, "· saldo", vast.saldo())
    o = elegir(pref)
    if not o: log("no hay A100 de 80 GB disponibles; abandono"); return 2
    log(f"oferta {o['id']}: {o['gpu_name']} {o['gpu_ram']/1000:.0f} GB ${o['dph_total']:.3f}/h {o.get('geolocation')} bajada {o.get('inet_down',0):.0f} Mbps")
    iid = crear(o); t_alq = time.time()
    log(f"instancia {iid} creada; cobrando desde ahora")
    (AQUI / "estado.json").write_text(json.dumps({"iid": iid, "t0": t_alq}))
    exito = False
    try:
        try: vast.autorizar_clave(iid)
        except Exception as e: log("autorizar clave:", e)
        inst = vast.esperar_lista(iid, minutos=20, log=log)
        for f in ("setup-v2.sh", "infer_trozos.py", entrada):
            vast.subir(inst, AQUI / f if isinstance(f, str) else f, REMOTO + "/", log=log)
        vast.lanzar(inst, f"bash {REMOTO}/setup-v2.sh", log="/root/setup.log")
        log("setup lanzado")
        if not esperar_marca(inst, "/root/setup.log", "SETUP_OK", "SETUP_FALLO", T_SETUP_MIN, avance="BSA build rc|bsa OK|diffsynth OK"):
            rc, out, _ = ssh(inst, "tail -n 25 /root/setup.log | cut -c1-200"); log("setup falló:\n" + out); return 3
        log(f"setup OK a los {(time.time()-t_alq)/60:.0f} min")
        cmd = (f"cd /workspace/FlashVSR/examples/WanVSR && cp {REMOTO}/infer_trozos.py . && "
               f"PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True {PY} infer_trozos.py {REMOTO}/{entrada.name} {REMOTO}/salida.mp4")
        vast.lanzar(inst, cmd, log="/root/infer.log")
        log("inferencia lanzada")
        if not esperar_marca(inst, "/root/infer.log", "[listo]", "Traceback", T_INFER_MIN, avance=r"\[trozo|\[entrada\]|\[tiempo\]"):
            rc, out, _ = ssh(inst, "grep -a -v -E 'it/s' /root/infer.log | tail -n 30 | cut -c1-220"); log("inferencia falló:\n" + out); return 4
        rc, out, _ = ssh(inst, r"grep -a -E '\[trozo|\[listo\]' /root/infer.log | cut -c1-220"); log("resumen:\n" + out)
        log(f"inferencia OK a los {(time.time()-t_alq)/60:.0f} min; bajando")
        rc, err = scp_desde(inst, f"{REMOTO}/salida.mp4", salida)
        if rc or not salida.exists() or salida.stat().st_size < 1e6:
            log("scp falló:", err); rc, err = scp_desde(inst, f"{REMOTO}/salida.mp4", salida)
        if salida.exists() and salida.stat().st_size > 1e6:
            exito = True; log(f"bajado {salida.name}: {salida.stat().st_size/1e6:.0f} MB")
        else:
            log("NO se pudo bajar la salida; dejo la instancia viva para rescatarla a mano"); return 5
    except Exception as e:
        log("ERROR:", repr(e))
    finally:
        if exito or "inst" not in dir() or True:
            try:
                if exito or not salida.exists():
                    vast.destruir(iid, confirmar=True); log(f"instancia {iid} destruida · {(time.time()-t_alq)/60:.0f} min · saldo {vast.saldo()}")
            except Exception as e:
                log("destruir falló:", e)
    return 0 if exito else 1

if __name__ == "__main__":
    sys.exit(main())
