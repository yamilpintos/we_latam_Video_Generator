# -*- coding: utf-8 -*-
"""gpu_vast sin prender nada: API de vast y ssh FALSOS. 0 USD, 0 créditos.

  G1  sin credenciales: configurada() False, separar() devuelve None y lo dice (la app cae a "mezcla")
  G2  alquilar: las ofertas más caras que GPU_MAX_USD_H no se piden; si la oferta ya no está (no_such_ask) prueba
      la siguiente; queda registrada con NUESTRA etiqueta
  G3  asegurar + separar: instala una sola vez (marca LISTA), sube el wav, corre sep_app.py, baja las DOS pistas y
      borra allá (rm -rf) aunque falle
  G4  vigilante: ociosa más de GPU_OCIO_MIN → destruye SÓLO la nuestra; la otra instancia de la cuenta queda intacta
  G5  vigilante: pasado GPU_MAX_HORAS → destruida (si está en uso, espera a que termine)
  G6  tope de USD por día alcanzado → no alquila, separar() devuelve None y lo dice
  G7  DOBLAJE_GPU=manual sin instancia → no alquila
  G8  adopta una instancia nuestra que quedó viva de una web anterior (sin registro) y la apaga cuando queda ociosa
  G9  media.separar va primero a la GPU propia y, si ésta devuelve None, sigue por el camino de antes

Correr: cd plataforma/apps/doblaje && python -m tests.test_gpu_vast
"""
import json, sys, tempfile, time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doblaje import config as C, media, gpu_vast as G     # noqa: E402

F = []


def ok(c, e, d=""):
    print(("  OK   " if c else "  MAL  ") + e + (f"  ({d})" if d else ""))
    if not c:
        F.append(e)


tmp = Path(tempfile.mkdtemp())
G.REGISTRO, G.LEDGER = tmp / "gpu_vast.json", tmp / "ledger_gpu.jsonl"
C.GPU_ETIQUETA = "doblaje-app"


class VastFalso:
    """La API de vast y el ssh, en memoria."""
    def __init__(self):
        self.instancias = []          # lo vivo en la cuenta (nuestras y ajenas)
        self.ofertas = []
        self.ocupadas = set()         # ofertas que "ya no están"
        self.llamadas = []            # (metodo, ruta)
        self.ssh = []                 # comandos
        self.archivos = {}            # ruta remota -> bytes
        self.lista = set()            # hosts con /motor/LISTA
        self.falla_sep = False
        self.sig = 900

    def api(self, metodo, ruta, base=None, **kw):
        self.llamadas.append((metodo, ruta))
        if ruta == "/bundles/":
            tope = kw["json"]["dph_total"]["lte"]
            return {"offers": [o for o in self.ofertas if o["dph_total"] <= tope]}
        if ruta == "/instances/":
            return {"instances": list(self.instancias)}
        if ruta.startswith("/asks/"):
            oid = int(ruta.split("/")[2])
            if oid in self.ocupadas:
                raise G.GpuError("vast PUT: HTTP 400: no_such_ask")
            o = next(x for x in self.ofertas if x["id"] == oid)
            self.sig += 1
            self.instancias.append(dict(id=self.sig, label=kw["json"]["label"], actual_status="running", ssh_host=f"h{self.sig}",
                                        ssh_port=22, dph_total=o["dph_total"], gpu_name=o["gpu_name"], start_date=time.time()))
            return {"new_contract": self.sig}
        if ruta.startswith("/instances/") and metodo == "DELETE":
            iid = int(ruta.split("/")[2])
            self.instancias = [i for i in self.instancias if i["id"] != iid]
            return {}
        return {}

    def _ssh(self, host, port, cmd, timeout):
        self.ssh.append(cmd)
        if "echo ssh_ok" in cmd:
            return 0, "ssh_ok\n", ""
        if "test -f /motor/LISTA" in cmd:
            return 0, ("LISTA\n" if host in self.lista else ""), ""
        if "instalar.sh" in cmd:
            self.lista.add(host)
            return 0, "MODELO_LOCAL: model_bs_roformer_ep_317_sdr_12.9755.ckpt\nINSTALADA\n", ""
        if "sep_app.py" in cmd and "in.wav" in cmd:
            if self.falla_sep:
                return 1, "", "CUDA out of memory"
            base = cmd.split(" ")[-1].rsplit("/out", 1)[0]
            self.archivos[f"{base}/out/vocals_clean.wav"] = b"RIFFv" * 400
            self.archivos[f"{base}/out/music_effects.wav"] = b"RIFFf" * 400
            return 0, "MODELO_LOCAL: x SEGUNDOS: 3\n", ""
        return 0, "", ""

    def _subir(self, host, port, local, remoto):
        self.archivos[remoto] = local if isinstance(local, bytes) else Path(local).read_bytes()

    def _bajar(self, host, port, remoto, local):
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        Path(local).write_bytes(self.archivos[remoto])


def armar(modo="auto", ofertas=None):
    v = VastFalso()
    v.ofertas = ofertas or [dict(id=1, dph_total=0.45, gpu_name="RTX 4090", geolocation="US"),
                            dict(id=2, dph_total=0.50, gpu_name="RTX 4090", geolocation="US"),
                            dict(id=3, dph_total=0.95, gpu_name="RTX 4090", geolocation="US")]
    G._api, G._ssh, G._subir, G._bajar = v.api, v._ssh, v._subir, v._bajar
    G._clave_publica = lambda: "ssh-ed25519 AAAAFAKE doblaje-app"
    G._clave_privada = lambda: tmp / "clave"
    G._esperar_ssh = lambda host, port, log=None, tope=0: None
    G.time.sleep = lambda s: None
    C.VAST_API_KEY, C.GPU_MODO, C.GPU_MAX_USD_H, C.GPU_USD_TOPE_DIA = "k", modo, 0.60, 6.0
    C.GPU_OCIO_MIN, C.GPU_MAX_HORAS = 10, 6
    G._estado.update(fase="apagada", detalle="", usando=0, ultimo_uso=0.0, error=None, vencida=False)
    G._guardar_registro(None)
    G.LEDGER.unlink(missing_ok=True)
    return v


(tmp / "clave").write_text("x")
audio = tmp / "in.wav"
audio.write_bytes(b"RIFF")
real_sleep = G.time.sleep

print("G1 · sin credenciales")
v = armar()
C.VAST_API_KEY = ""
logs = []
ok(not G.configurada(), "G1a configurada() False sin VAST_API_KEY")
ok(G.separar(audio, tmp / "o1", logs.append) is None and logs and "no disponible" in logs[-1], "G1b separar() None y lo dice", logs[-1:])

print("G2 · alquilar con topes y ofertas que se van")
v = armar()
v.ocupadas = {1}
d = G.alquilar(logs.append)
pedidas = [r for m, r in v.llamadas if r.startswith("/asks/")]
ok(pedidas == ["/asks/1/", "/asks/2/"], "G2a probó la oferta 1 (ya no estaba) y alquiló la 2", str(pedidas))
ok(all("/asks/3/" != r for r in pedidas), "G2b la oferta de USD 0,95 (> tope 0,60) ni se pidió")
ok(v.instancias[0]["label"] == "doblaje-app" and G._registro()["id"] == v.instancias[0]["id"], "G2c registrada con nuestra etiqueta")
ok(any(e.get("tipo") == "alquilada" for e in G._leer_ledger()), "G2d anotada en el libro de GPU")

print("G3 · asegurar + separar")
r = G.separar(audio, tmp / "o3", logs.append)
ok(r is not None and r[0].read_bytes().startswith(b"RIFFv") and r[1].read_bytes().startswith(b"RIFFf"), "G3a baja las dos pistas", str(r))
ok(sum(1 for c in v.ssh if "instalar.sh" in c) == 1, "G3b instaló una vez")
ok(any("sep_app.py" in c and "in.wav" in c for c in v.ssh), "G3c corrió sep_app.py sobre in.wav")
ok(v.ssh[-1].startswith("rm -rf /motor/sep_app/"), "G3d al final borró allá el audio del cliente")
n_inst = sum(1 for c in v.ssh if "instalar.sh" in c)
r2 = G.separar(audio, tmp / "o3b", logs.append)
ok(r2 is not None and sum(1 for c in v.ssh if "instalar.sh" in c) == n_inst, "G3e la segunda vez no reinstala")
ok(G._estado["usando"] == 0 and G._estado["fase"] == "lista", "G3f queda lista y sin uso", str(G._estado))
v.falla_sep = True
ok(G.separar(audio, tmp / "o3c", logs.append) is None and v.ssh[-1].startswith("rm -rf"), "G3g si el separador falla: None y borra allá")
v.falla_sep = False
ok(G.separar(audio, tmp / "o3", logs.append) is not None and "se reusa" in logs[-1], "G3h lo ya separado se reusa sin tocar la GPU")

print("G4 · vigilante: ociosa → sólo la nuestra")
v.instancias.append(dict(id=555, label="otra-cosa", actual_status="running", ssh_host="h555", ssh_port=22, dph_total=2.49,
                         gpu_name="RTX 5090", start_date=time.time()))
G._estado["ultimo_uso"] = time.time() - 5 * 60
ok(G.vigilar_una_vez() == "viva", "G4a a los 5 min sigue viva")
G._estado["ultimo_uso"] = time.time() - 11 * 60
res = G.vigilar_una_vez(log=logs.append)
ok(res == "destruida por ociosa" and G.mia() is None, "G4b a los 11 min ociosa: destruida", res)
ok([i["id"] for i in v.instancias] == [555], "G4c la RTX 5090 ajena sigue viva")
e = [e for e in G._leer_ledger() if e.get("tipo") == "destruida"]
ok(e and e[-1]["motivo"].startswith("ociosa") and "usd" in e[-1], "G4d destrucción anotada con USD", str(e[-1]))

print("G5 · vigilante: tope de horas")
v = armar()
G.asegurar(logs.append)
v.instancias[0]["start_date"] = time.time() - 7 * 3600
G._estado["usando"] = 1
G._estado["ultimo_uso"] = time.time()
ok(G.vigilar_una_vez(log=logs.append) == "vencida, en uso" and G.mia() is not None, "G5a en uso: espera")
G._estado["usando"] = 0
ok(G.vigilar_una_vez(log=logs.append) == "destruida por tope de horas" and G.mia() is None, "G5b sin uso: destruida")
try:
    G.asegurar(logs.append)
    ok(True, "G5c después del tope se puede volver a alquilar (instancia nueva)")
except G.GpuError as ex:
    ok(False, "G5c después del tope se puede volver a alquilar", str(ex))

print("G6 · tope de USD por día")
v = armar()
C.GPU_USD_TOPE_DIA = 1.0
G._ledger(tipo="destruida", id=1, usd=1.2, horas=2.5)
logs.clear()
ok(G.separar(audio, tmp / "o6", logs.append) is None and "tope de GPU del día" in logs[-1], "G6a no alquila y lo dice", logs[-1:])
ok(not any(r.startswith("/asks/") for m, r in v.llamadas), "G6b ninguna oferta pedida")

print("G7 · modo manual")
v = armar(modo="manual")
logs.clear()
ok(G.separar(audio, tmp / "o7", logs.append) is None and "manual" in logs[-1], "G7a no alquila y dice que está en manual")
ok(not any(r.startswith("/asks/") for m, r in v.llamadas), "G7b ninguna oferta pedida")

print("G8 · adopta una instancia nuestra que quedó viva")
v = armar()
v.instancias.append(dict(id=777, label="doblaje-app", actual_status="running", ssh_host="h777", ssh_port=22, dph_total=0.4,
                         gpu_name="RTX 4090", start_date=time.time() - 3600))
ok(G._registro() is None and G.vigilar_una_vez(log=logs.append) == "viva" and G._registro()["id"] == 777, "G8a la adopta y la registra")
G._estado["ultimo_uso"] = time.time() - 11 * 60
ok(G.vigilar_una_vez() == "destruida por ociosa" and not v.instancias, "G8b y la apaga cuando queda ociosa")

print("G9 · media.separar: GPU propia primero, después lo de antes")
v = armar()
C.SEP_REMOTO = ""
C.SEPARADOR = str(tmp / "no_hay_separador.py")
r = media.separar(audio, tmp / "o9", logs.append)
ok(r is not None and any("sep_app.py" in c for c in v.ssh), "G9a fue a la GPU propia")
C.GPU_USD_TOPE_DIA = 0.0
G.destruir("prueba")
ok(media.separar(audio, tmp / "o9b", logs.append) is None, "G9b si la GPU no puede y no hay separador local: None (mezcla)")

G.time.sleep = real_sleep
print()
print("TODO OK" if not F else f"FALLAN {len(F)}: {F}")
sys.exit(1 if F else 0)
