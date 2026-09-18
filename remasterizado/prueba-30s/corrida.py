"""Driver de la prueba FlashVSR en Vast: alquilar | estado | log | correr | bajar | destruir."""
import json, sys, time
from pathlib import Path
RAIZ = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(RAIZ))
from h3pipeline import vast
AQUI = Path(__file__).resolve().parent
ESTADO = AQUI / "estado.json"
IMAGEN = "vastai/base-image:cuda-12.4.1-cudnn-devel-ubuntu22.04-py311"
PORTAL = "localhost:1111:11111:/:Instance Portal|localhost:8080:18080:/:Jupyter|localhost:8080:8080:/terminals/1:Jupyter Terminal"
ENV = {"-p 1111:1111": "1", "-p 8080:8080": "1", "OPEN_BUTTON_PORT": "1111", "OPEN_BUTTON_TOKEN": "1",
       "JUPYTER_DIR": "/", "DATA_DIRECTORY": "/workspace/", "PORTAL_CONFIG": PORTAL}
REMOTO = "/workspace/prueba"

def estado(): return json.loads(ESTADO.read_text()) if ESTADO.exists() else {}
def guardar(d): ESTADO.write_text(json.dumps(d, indent=1))
def inst(): return vast.instancia(estado()["iid"])

def alquilar(oferta):
    cuerpo = {"client_id": "me", "image": IMAGEN, "env": ENV, "disk": 60, "label": "flashvsr-prueba",
              "onstart": "entrypoint.sh", "runtype": "jupyter_direc ssh_direc ssh_proxy",
              "image_login": None, "python_utf8": False, "lang_utf8": False, "use_jupyter_lab": False,
              "jupyter_dir": None, "cancel_unavail": False, "template_hash_id": None, "user": None}
    r = vast._pedir(f"/asks/{oferta}/", metodo="PUT", cuerpo=cuerpo)
    print("crear:", r)
    if not r.get("success", True): sys.exit(1)
    iid = r["new_contract"]; guardar({"iid": iid, "t0": time.time(), "oferta": oferta})
    print("autorizar clave:", vast.autorizar_clave(iid))
    i = vast.esperar_lista(iid, minutos=25)
    for f in ("setup-flashvsr.sh", "infer_prueba.py", "entrada_19m16_360p.mp4"):
        vast.subir(i, AQUI / f, REMOTO + "/")
    print(vast.lanzar(i, f"bash {REMOTO}/setup-flashvsr.sh", log="/root/setup.log"))
    print("listo en", (time.time() - estado()["t0"]) / 60, "min ·", vast.ssh_de(i))

def correr():
    i = inst()
    cmd = (f"cd /workspace/FlashVSR/examples/WanVSR && cp {REMOTO}/infer_prueba.py . && "
           f"/venv/main/bin/python infer_prueba.py {REMOTO}/entrada_19m16_360p.mp4 {REMOTO}/salida_flashvsr_full.mp4")
    print(vast.lanzar(i, cmd, log="/root/infer.log"))

def log(nombre="setup", n=15):
    print(vast.ejecutar(inst(), f"tail -n {n} /root/{nombre}.log", timeout=60))

def bajar():
    import subprocess
    i = inst(); h, p, u = vast._ssh_args(i)
    r = subprocess.run(["scp", "-P", p, "-o", "StrictHostKeyChecking=accept-new",
                        f"{u}:{REMOTO}/salida_flashvsr_full.mp4", str(AQUI)], capture_output=True, text=True)
    print(r.returncode, r.stderr[-300:])

def destruir():
    print(vast.destruir(estado()["iid"], confirmar=True))

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "alquilar": alquilar(int(a[1]))
    elif a[0] == "estado":
        i = inst(); print(i.get("actual_status"), vast.ssh_de(i), f"${i.get('dph_total',0):.3f}/h", f"{(time.time()-estado()['t0'])/60:.0f} min")
    elif a[0] == "log": log(*(a[1:2] or ["setup"]), n=int(a[2]) if len(a) > 2 else 15)
    elif a[0] == "correr": correr()
    elif a[0] == "bajar": bajar()
    elif a[0] == "destruir": destruir()
    elif a[0] == "ssh": print(vast.ejecutar(inst(), " ".join(a[1:]), timeout=120))
