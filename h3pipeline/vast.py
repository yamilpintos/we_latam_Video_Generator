"""Buscar y alquilar cómputo en Vast.ai, con los filtros que este pipeline pide.

Qué significa acá "cómputo seguro". Tres cosas distintas, y todas se filtran:

  1. Seguro de que corre.   4 placas con **32 GB cada una**, fiabilidad ≥ 99,5 %
     (por debajo se caen solas) y verificadas por Vast. Dos trampas que el
     filtro por gigas no ve y que este módulo sí:
       · una Tesla V100 tiene los mismos 32 GB que una 5090 y es de 2017, sin
         bf16 nativo, que es lo que piden las LoRAs turbo de H3;
       · `deverified` es una máquina a la que Vast le SACÓ la verificación, y
         el filtro `verified` de la consulta la deja pasar igual.
  2. Seguro de que no te lo cortan.  Sólo `on-demand`. Las interruptible salen
     2-3× más baratas pero te desalojan a mitad de una tanda de 45 minutos.
  3. Seguro legalmente.  La MiniMax H3 Community License **excluye Estados
     Unidos, la Unión Europea, el Reino Unido y Corea del Sur** del despliegue
     local. El país del host se filtra antes de mostrarte nada — y eso saca
     casi la mitad de la oferta, así que conviene saberlo antes de buscar.

Y una cuarta que no es un filtro sino el orden: **se ordena por costo total del
trabajo, no por precio por hora.** Hay que bajar 59 GB de modelos antes de
generar el primer plano; a 30 Mbps eso son 262 minutos de máquina encendida
esperando, más caro que generar el video entero. Una máquina barata con enlace
lento sale más cara que una cara con enlace rápido.

Uso:

    from h3pipeline import vast
    ofertas = vast.buscar(planos=planos)      # ya ordenadas por costo total
    print(vast.tabla(ofertas))

La clave sale de `VAST_API_KEY` en el entorno o en el `.env`
(https://cloud.vast.ai/account/ → API Keys).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import config, costos

API = "https://console.vast.ai/api"

# --- lo que pide este pipeline ----------------------------------------------
GPUS = 4
VRAM_GB = 32          # por placa. El Q5 de 23,9 GB + encoder no entra en 24.
DISCO_GB = 250        # con 150 se llenó el disco y F_MAXIMO no llegó a correr
INET_MBPS = 800       # por debajo de esto la descarga se come el presupuesto
FIABILIDAD = 0.995

# Placas que pasan el filtro de VRAM pero NO sirven: son anteriores a Ampere,
# no tienen bf16 nativo y las LoRAs turbo de H3 vienen en bf16. Hay que
# nombrarlas porque el filtro por gigas no las distingue — una Tesla V100 tiene
# los mismos 32 GB que una 5090 y es de 2017.
GPU_VIEJAS = ("V100", "P100", "P40", "P4", "M40", "K80", "T4", "TITAN V",
              "RTX 8000", "RTX 6000")     # "RTX 6000" a secas es la Turing;
                                          # la 6000Ada y la PRO 6000 sí sirven
GPU_VIEJAS_EXCEPCIONES = ("6000ADA", "PRO 6000", "6000 ADA")


def _placa_sirve(nombre: str) -> bool:
    n = nombre.upper()
    if any(x in n for x in GPU_VIEJAS_EXCEPCIONES):
        return True
    return not any(v in n for v in GPU_VIEJAS)

# --- licencia MiniMax H3: dónde NO se puede desplegar ------------------------
# EE.UU. + los 27 de la UE + Reino Unido + Corea del Sur. Noruega, Suiza,
# Islandia, Canadá, Japón y Taiwán quedan fuera de la exclusión.
EXCLUIDOS = {
    "US", "USA", "UNITED STATES",
    "GB", "UK", "UNITED KINGDOM", "ENGLAND", "SCOTLAND", "WALES",
    "KR", "SOUTH KOREA", "KOREA",
    "AT", "AUSTRIA", "BE", "BELGIUM", "BG", "BULGARIA", "HR", "CROATIA",
    "CY", "CYPRUS", "CZ", "CZECHIA", "CZECH REPUBLIC", "DK", "DENMARK",
    "EE", "ESTONIA", "FI", "FINLAND", "FR", "FRANCE", "DE", "GERMANY",
    "GR", "GREECE", "HU", "HUNGARY", "IE", "IRELAND", "IT", "ITALY",
    "LV", "LATVIA", "LT", "LITHUANIA", "LU", "LUXEMBOURG", "MT", "MALTA",
    "NL", "NETHERLANDS", "PL", "POLAND", "PT", "PORTUGAL", "RO", "ROMANIA",
    "SK", "SLOVAKIA", "SI", "SLOVENIA", "ES", "SPAIN", "SE", "SWEDEN",
}


class ErrorVast(RuntimeError):
    pass


@dataclass
class Oferta:
    id: int
    maquina: int
    gpu: str
    gpus: int
    vram_gb: float
    dph: float
    disco_gb: float
    inet_down: float
    fiabilidad: float
    geo: str
    verificacion: str          # "verified" | "deverified" | "unverified"
    datacenter: bool
    cuda: float = 0.0
    crudo: dict = field(default_factory=dict, repr=False)

    @property
    def verificada(self) -> bool:
        # Ojo: "deverified" es una máquina a la que Vast le SACÓ la verificación.
        # El filtro `verified` de la consulta las deja pasar igual, así que hay
        # que mirar este campo acá y no confiar en la query.
        return self.verificacion == "verified"

    @property
    def pais(self) -> str:
        # Vast devuelve cosas como "SE", "Sweden, SE", "US, Texas". Nos quedamos
        # con las piezas y las comparamos todas contra la lista de excluidos.
        return self.geo.strip()

    def permitida_por_licencia(self) -> bool:
        piezas = [x.strip().upper() for x in self.geo.replace("/", ",").split(",")]
        return not any(x in EXCLUIDOS for x in piezas if x)

    def a_maquina(self) -> costos.Maquina:
        return costos.Maquina(dph=self.dph, gpus=self.gpus,
                              inet_down_mbps=self.inet_down,
                              nombre=f"{self.gpus}× {self.gpu}")


# ----------------------------------------------------------------- HTTP

def _clave(clave: str | None = None, obligatoria: bool = True) -> str | None:
    return clave or config.leer_env("VAST_API_KEY", obligatorio=obligatoria)


def _pedir(ruta: str, clave: str | None = None, metodo: str = "GET",
           cuerpo: dict | None = None, params: dict | None = None,
           requiere_clave: bool = True, version: str = "v0") -> dict:
    """Buscar ofertas es público; alquilar, listar y destruir piden clave.

    Vast está migrando de v0 a v1 endpoint por endpoint: `/instances/` ya
    responde 410 en v0, pero `/bundles/` **no existe** en v1. En vez de adivinar
    cuál está en cuál, se pide en la versión conocida y, si contesta 410
    `deprecated_endpoint`, se reintenta en la otra. Así el módulo sobrevive a la
    próxima migración sin tocarlo.
    """
    config.certificados()
    url = f"{API}/{version}{ruta}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    cabeceras = {"Accept": "application/json", "Content-Type": "application/json"}
    k = _clave(clave, obligatoria=requiere_clave)
    if k:
        cabeceras["Authorization"] = f"Bearer {k}"
    req = urllib.request.Request(url, data=datos, method=metodo, headers=cabeceras)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:500]
        if e.code == 410 and "deprecated" in detalle and version == "v0":
            return _pedir(ruta, clave, metodo, cuerpo, params, requiere_clave, "v1")
        if e.code in (401, 403):
            raise ErrorVast("Vast rechazó la clave. Revisá `vasia`/`VAST_API_KEY` en el "
                            ".env, o sacá una nueva en cloud.vast.ai/account/") from e
        raise ErrorVast(f"Vast HTTP {e.code} en {version}{ruta}: {detalle}") from e
    except urllib.error.URLError as e:
        raise ErrorVast(f"no pude hablar con Vast: {e.reason}") from e


# ---------------------------------------------------------------- buscar

def buscar(planos: list[dict] | None = None, *, gpus: int = GPUS, vram_gb: int = VRAM_GB,
           disco_gb: int = DISCO_GB, inet_mbps: int = INET_MBPS,
           fiabilidad: float = FIABILIDAD, gpu: str | None = None,
           respetar_licencia: bool = True, solo_verificadas: bool = True,
           solo_datacenter: bool = False, limite: int = 200, pasos: int = 8,
           clave: str | None = None) -> list[Oferta]:
    """Las ofertas que sirven, ordenadas por costo total del trabajo.

    Si se pasan `planos`, el orden es por lo que costaría hacer ESE video:
    descarga de modelos + generación repartida entre las placas. Sin planos,
    ordena por precio por hora.

    `solo_datacenter` va en False por defecto a propósito: exigirlo deja fuera
    a nueve de cada diez ofertas, y con la verificación y la fiabilidad ya
    filtradas la diferencia práctica es chica. Ponelo en True si tuviste un
    `OCI runtime create failed`, que es el síntoma típico de host particular.
    """
    q: dict = {
        "rentable": {"eq": True},
        "rented": {"eq": False},
        "external": {"eq": False},
        "num_gpus": {"eq": gpus},
        "gpu_ram": {"gte": vram_gb * 1000},        # Vast lo da en MB
        "disk_space": {"gte": disco_gb},
        "inet_down": {"gte": inet_mbps},
        "reliability2": {"gte": fiabilidad},
        "type": "on-demand",                        # nada de interruptible
        "order": [["dph_total", "asc"]],
        "limit": limite,
    }
    if gpu:
        q["gpu_name"] = {"eq": gpu}
    datos = _pedir("/bundles/", clave, params={"q": json.dumps(q)},
                   requiere_clave=False)

    ofertas = []
    for o in datos.get("offers", []):
        ofertas.append(Oferta(
            id=o.get("id", 0), maquina=o.get("machine_id", 0),
            gpu=o.get("gpu_name", "?"), gpus=int(o.get("num_gpus", 0)),
            vram_gb=round(float(o.get("gpu_ram", 0)) / 1024, 1),
            dph=float(o.get("dph_total", 0)), disco_gb=float(o.get("disk_space", 0)),
            inet_down=float(o.get("inet_down", 0)),
            fiabilidad=float(o.get("reliability2", 0)),
            geo=str(o.get("geolocation") or "?"),
            verificacion=str(o.get("verification") or "unverified"),
            # hosting_type 1 y 2 son datacenter; 0 o ausente, host particular
            datacenter=bool(o.get("hosting_type")),
            cuda=float(o.get("cuda_max_good", 0) or 0), crudo=o))

    # Los filtros que la consulta no sabe hacer, o que hace mal.
    ofertas = [o for o in ofertas if _placa_sirve(o.gpu)]
    if solo_verificadas:
        ofertas = [o for o in ofertas if o.verificada]
    if solo_datacenter:
        ofertas = [o for o in ofertas if o.datacenter]
    if respetar_licencia:
        ofertas = [o for o in ofertas if o.permitida_por_licencia()]

    if planos:
        ofertas.sort(key=lambda o: costos.estimar(planos, o.a_maquina(), pasos).costo_total)
    else:
        ofertas.sort(key=lambda o: o.dph)
    return ofertas


def tabla(ofertas: list[Oferta], planos: list[dict] | None = None, pasos: int = 8,
          cuantas: int = 12) -> str:
    """Las ofertas como tabla. Con `planos`, la última columna es lo que sale
    hacer ese video entero en cada una — que es el número que decide."""
    if not ofertas:
        return ("Ninguna oferta pasa los filtros.\n"
                "  Aflojá con inet_mbps=500 o disco_gb=150. Si igual no hay, mirá\n"
                "  cuántas quedan sin filtrar por licencia: puede que todo lo que\n"
                "  sirve esté en EE.UU. o la UE, y ésa es una decisión tuya.")
    L = [f"{'id':>9} {'GPU':<16} {'VRAM':>5} {'$/h':>7} {'disco':>6} {'Mbps':>6} "
         f"{'fiab':>5} {'DC':>3} {'país':<16}" + ("  total del video" if planos else "")]
    for o in ofertas[:cuantas]:
        fila = (f"{o.id:>9} {o.gpu:<16} {o.vram_gb:>4.0f}G {o.dph:>7.3f} "
                f"{o.disco_gb:>5.0f}G {o.inet_down:>6.0f} {o.fiabilidad:>5.3f} "
                f"{'sí' if o.datacenter else '·':>3} {o.geo[:16]:<16}")
        if planos:
            e = costos.estimar(planos, o.a_maquina(), pasos)
            fila += f"  ${e.costo_total:5.2f} en {e.minutos_total:3.0f} min"
        L.append(fila)
    if len(ofertas) > cuantas:
        L.append(f"  … y {len(ofertas) - cuantas} más")
    return "\n".join(L)


# ------------------------------------------------------------- instancias
# Alquilar cuesta plata desde el segundo cero y no hay deshacer, así que crear
# y destruir piden `confirmar=True` explícito. El camino probado sigue siendo
# alquilar desde la web eligiendo una plantilla de ComfyUI; esto es la versión
# desatendida de lo mismo.

# El template oficial de ComfyUI de Vast, el que usa todo el mundo (22.667
# instancias creadas). Se alquila **por hash de template** y no armando el
# contenedor a mano, y la razón salió cara de aprender:
#
#   Pasar `image` + un `onstart` propio te da un contenedor que arranca y no
#   sirve para nada. El template trae `onstart: entrypoint.sh`, que es lo que
#   levanta sshd, Jupyter y supervisor, más un `env` con los puertos
#   (`-p 8188:8188`), el `PROVISIONING_SCRIPT` que instala ComfyUI y
#   `COMFYUI_ARGS=--port 18188`. Sin eso la instancia queda en `running` con
#   todos los puertos cerrados: el proxy SSH acepta el TCP y cierra sin banner.
#
# El tag lo resuelve Vast (`@vastai-automatic-tag`): fijar uno a mano es cómo
# terminás con una imagen de enero, anterior a los nodos de H3.
TEMPLATE_COMFY = "2188dfd3e0a0b83691bb468ddae0a4e5"
IMAGEN_COMFY = "vastai/comfy"      # informativo: lo elige el template


def crear(oferta: Oferta | int, *, confirmar: bool = False, disco_gb: int = DISCO_GB,
          template: str = TEMPLATE_COMFY, etiqueta: str = "h3",
          clave: str | None = None) -> dict:
    """Alquila la oferta con el template oficial de ComfyUI.

    **Empieza a cobrar apenas la instancia arranca.**
    """
    oid = oferta.id if isinstance(oferta, Oferta) else int(oferta)
    if not confirmar:
        raise ErrorVast(f"crear() no hace nada sin confirmar=True. "
                        f"Alquilar la oferta {oid} empieza a cobrar de inmediato.")
    cuerpo = {"client_id": "me", "template_hash_id": template,
              "disk": disco_gb, "label": etiqueta}
    r = _pedir(f"/asks/{oid}/", clave, metodo="PUT", cuerpo=cuerpo)
    if not r.get("success", True):
        raise ErrorVast(f"Vast no alquiló la oferta: {r}")
    return r


def autorizar_clave(instancia_id: int, clave_pub: str | None = None,
                    clave: str | None = None) -> dict:
    """Adjunta una clave pública **a la instancia**.

    Hace falta porque una API key de *team* no puede registrar claves en la
    cuenta (`Team SSH keys are not supported`), pero sí adjuntarlas a cada
    instancia. Sin esto, `scp` y `ssh` fallan con `connection reset`.
    """
    from pathlib import Path
    if clave_pub is None:
        pub = Path.home() / ".ssh" / "id_ed25519.pub"
        if not pub.exists():
            raise ErrorVast(f"no encuentro {pub}. Generá una con: ssh-keygen -t ed25519")
        clave_pub = pub.read_text().strip()
    return _pedir(f"/instances/{instancia_id}/ssh/", clave, metodo="POST",
                  cuerpo={"ssh_key": clave_pub})


def instancia(instancia_id: int, clave: str | None = None) -> dict:
    for i in instancias(clave):
        if int(i.get("id", 0)) == int(instancia_id):
            return i
    raise ErrorVast(f"no existe la instancia {instancia_id} en tu cuenta")


def ssh_responde(inst: dict) -> bool:
    """Si por SSH se puede **ejecutar algo**, que es lo único que importa.

    Hay tres estados que parecen el mismo y no lo son, y cada uno costó una
    vuelta:

        puerto cerrado          el proxy todavía no enruta
        abre y no saluda        el contenedor no levantó sshd (imagen sin
                                `entrypoint.sh`: la instancia queda inservible)
        saluda y cierra         sshd arriba pero `entrypoint.sh` sigue
                                corriendo, o la clave no propagó todavía

    Sólo el handshake completo distingue el tercero del listo de verdad.
    """
    import subprocess
    global ULTIMO_ERROR_SSH
    try:
        _host, puerto, usuario = _ssh_args(inst)
    except ErrorVast as e:
        ULTIMO_ERROR_SSH = str(e)
        return False
    try:
        r = subprocess.run(
            ["ssh", "-p", puerto, "-o", "StrictHostKeyChecking=accept-new",
             "-o", "ConnectTimeout=12", "-o", "BatchMode=yes", usuario, "true"],
            capture_output=True, text=True, timeout=40)
    except Exception as e:                       # no hay ssh, o se colgó
        ULTIMO_ERROR_SSH = f"{type(e).__name__}: {e}"
        return False
    err = " ".join(l for l in (r.stderr or "").splitlines()
                   if l.strip() and not l.startswith("Warning: Permanently added"))
    ULTIMO_ERROR_SSH = "" if r.returncode == 0 else (err[-300:] or f"código {r.returncode} sin mensaje")
    return r.returncode == 0


ULTIMO_ERROR_SSH = ""   # por qué falló el último ssh_responde; lo muestra esperar_lista


def diagnostico_ssh() -> dict:
    """Estado de la clave SSH de ESTE servidor, sin tocar Vast ni alquilar nada.

    Nació el 17/9/2026: en Render dos 4×5090 quedaron 20 min en «arrancando»
    y se destruyeron solas (~$1,80) porque el ssh desde el servidor no entraba
    y el log sólo decía «running…». Con esto se ve antes de gastar si la
    clave privada es válida y si su pública es la que se adjunta a la instancia.
    """
    import shutil
    import subprocess
    from pathlib import Path
    home = Path.home()
    k, pub = home / ".ssh" / "id_ed25519", home / ".ssh" / "id_ed25519.pub"
    import os
    d = {"home": str(home), "ssh": shutil.which("ssh"), "privada": k.exists(), "publica": pub.exists(),
         "privada_valida": False, "publica_coincide": False, "error": None,
         # cuántos caracteres trae cada variable del entorno (0 = no está o está vacía)
         "entorno": {n: len((os.environ.get(n) or "").strip()) for n in ("VAST_SSH_PRIVATE_KEY", "VAST_SSH_PUBLIC_KEY")}}
    if not d["ssh"]:
        d["error"] = "no hay cliente ssh en el PATH"
        return d
    if not k.exists():
        d["error"] = f"no existe {k} (en un servidor: VAST_SSH_PRIVATE_KEY y VAST_SSH_PUBLIC_KEY)"
        return d
    d["lineas_privada"] = k.read_text(encoding="utf-8").count("\n")
    try:
        r = subprocess.run(["ssh-keygen", "-y", "-f", str(k)], capture_output=True, text=True, timeout=20)
    except Exception as e:
        d["error"] = f"ssh-keygen: {e}"
        return d
    if r.returncode != 0:
        d["error"] = (r.stderr or "").strip()[-300:] or "ssh-keygen no pudo leer la clave privada"
        return d
    d["privada_valida"] = True
    derivada = r.stdout.split()[:2]
    if pub.exists():
        d["publica_coincide"] = pub.read_text(encoding="utf-8").split()[:2] == derivada
        if not d["publica_coincide"]:
            d["error"] = "la pública guardada no es la de esta privada: la instancia autoriza una clave y ssh presenta otra"
    else:
        d["error"] = f"no existe {pub}"
    return d


def esperar_lista(instancia_id: int, minutos: int = 20, clave: str | None = None,
                  log=print) -> dict:
    """Espera a que la instancia esté **de verdad** lista.

    Dos campos que no significan lo mismo y que confundí una vez:

        cur_state       el contrato está activo. Dice *running* enseguida.
        actual_status   la máquina terminó de bajar la imagen Docker y arrancó.

    Sólo el segundo sirve, y ni siquiera alcanza: el puerto SSH abre después.
    Por eso además se prueba la conexión. Mientras tanto ya te está cobrando,
    así que el log dice cuánto va.
    """
    import time
    t0 = time.time()
    while time.time() - t0 < minutos * 60:
        i = instancia(instancia_id, clave)
        estado = i.get("actual_status") or "sin estado"
        if estado == "running" and ssh_responde(i):
            log(f"  lista en {(time.time() - t0) / 60:.1f} min · {ssh_de(i)}")
            return i
        if estado == "running":
            # La máquina ya corre: si no entramos es cosa nuestra (clave, red,
            # ssh) o de la imagen. El motivo va al log, no se lo traga más.
            log(f"  running, pero ssh no entra ({ULTIMO_ERROR_SSH or 'sin respuesta'}) · "
                f"{ssh_de(i)} · {(time.time() - t0) / 60:.1f} min")
        else:
            log(f"  {estado}… {(time.time() - t0) / 60:.1f} min")
        time.sleep(20)
    raise ErrorVast(f"la instancia {instancia_id} no arrancó en {minutos} min. "
                    f"Si quedó colgada, destruila para no pagarla: "
                    f"python -m h3pipeline destruir {instancia_id} --si")


def _ssh_args(inst: dict) -> tuple[str, str, str]:
    """Host y puerto para entrar, **prefiriendo el SSH directo**.

    Vast da dos caminos y no son equivalentes:

      proxy    `ssh_host` (sshN.vast.ai) + `ssh_port`. Autentica contra las
               claves de la CUENTA antes de enrutar, así que con una API key de
               team —que no puede registrar claves de cuenta— cierra la conexión
               en el `kex_exchange_identification`, sin llegar a autenticar.
      directo  la IP pública y el puerto al que está mapeado el 22. Usa las
               claves adjuntas a la INSTANCIA, que sí se pueden poner por API.

    Por eso el directo va primero: es el que funciona en este proyecto.
    """
    puerto_22 = (inst.get("ports") or {}).get("22/tcp")
    ip = inst.get("public_ipaddr")
    if puerto_22 and ip:
        return ip, str(puerto_22[0]["HostPort"]), f"root@{ip}"
    host = inst.get("ssh_host")
    if not host:
        raise ErrorVast("la instancia todavía no expone SSH")
    return host, str(inst.get("ssh_port") or 22), f"root@{host}"


def subir(inst: dict, archivo, destino: str = "/workspace/refs/", log=print) -> None:
    """Manda un archivo por scp. Evita el Upload de Jupyter, que **aplasta las
    carpetas** — por eso lo que se sube es siempre el ZIP."""
    import subprocess
    from pathlib import Path
    host, puerto, usuario = _ssh_args(inst)
    archivo = Path(archivo)
    log(f"  subiendo {archivo.name} ({archivo.stat().st_size / 1e6:.0f} MB) a {destino}")
    ejecutar(inst, f"mkdir -p {destino}", log=log)
    r = subprocess.run(["scp", "-P", puerto, "-o", "StrictHostKeyChecking=accept-new",
                        str(archivo), f"{usuario}:{destino}"],
                       capture_output=True, text=True)
    if r.returncode:
        raise ErrorVast(f"scp falló: {r.stderr[-400:]}\n"
                        f"  ¿Está tu clave pública cargada en Vast? "
                        f"(cloud.vast.ai/account/ → SSH Keys)")


def ejecutar(inst: dict, comando: str, log=print, timeout: int = 300) -> str:
    """Corre un comando por ssh y devuelve su salida."""
    import subprocess
    _host, puerto, usuario = _ssh_args(inst)
    r = subprocess.run(["ssh", "-p", puerto, "-o", "StrictHostKeyChecking=accept-new",
                        usuario, comando], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise ErrorVast(f"ssh falló ({r.returncode}): {r.stderr[-400:]}")
    return r.stdout


def lanzar(inst: dict, comando: str, log: str = "/root/tarea.log") -> str:
    """Arranca algo largo y **vuelve enseguida**, dejando el proceso vivo.

    `nohup … &` a secas no alcanza: ssh no cierra la sesión mientras el proceso
    conserve stdout o stderr, así que el cliente se queda colgado aunque el
    comando ya esté corriendo. Hay que redirigir los tres descriptores y
    despegarlo de la sesión con `setsid`.
    """
    return ejecutar(inst, f"setsid nohup bash -c {_comillas(comando)} "
                          f"> {log} 2>&1 < /dev/null & echo lanzado", timeout=60)


def _comillas(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


# ------------------------------------------------------------ la corrida
# Los tres pasos que antes se hacían a mano por SSH —y donde más se tropezó—
# como funciones: generar (unzip + sed + setup + lanzar, desatendido), progreso
# (cuántos clips van) y bajar (los archivos a esta máquina). Cada paso manual
# de menos es una trampa de menos.

LOG_CORRIDA = "/root/corrida.log"
SALIDA_REMOTA = "/workspace/ComfyUI/output/video"


def generar(inst: dict, zip_nombre: str, pasos: int = 8, gpus: int = GPUS,
            log=print, ref2va: bool = False) -> None:
    """Deja la corrida entera andando DENTRO de la máquina, desatendida.

    Encadena lo que antes se tipeaba a mano: descomprimir el ZIP, sacar los
    saltos de línea de Windows (sin eso los .sh mueren), `setup.sh` (los ~59 GB
    de modelos) y `lanzar.sh` (un ComfyUI por placa + los runners). Todo
    despegado de la sesión SSH, con la salida en un solo log.

    El PATH antepone `/venv/main/bin` porque un shell no interactivo por SSH no
    trae el venv: sin eso `python` no existe y el `pip install gguf` del setup
    va al intérprete equivocado (trampa 5).
    """
    # `ref2va`: baja Ref2VA aunque este paquete no lo use. setup.sh ya lo decide
    # solo mirando planos.json, pero la etapa A de una muestra no tiene planos
    # ref2va y la B sí, en la misma instancia (14/9/2026).
    solo_fl = "SOLO_FL=0 " if ref2va else ""
    cmd = (f"export PATH=/venv/main/bin:$PATH && cd /workspace/refs && "
           f"unzip -oq {zip_nombre} && sed -i 's/\\r$//' *.sh *.py && "
           f"{solo_fl}bash setup.sh && PASOS={pasos} GPUS={gpus} bash lanzar.sh")
    lanzar(inst, cmd, log=LOG_CORRIDA)
    log(f"  corrida lanzada · el log vive en {LOG_CORRIDA}")


def archivos_remotos(inst: dict) -> list[str]:
    """Qué hay en la carpeta de salida de la instancia."""
    try:
        salida = ejecutar(inst, f"ls -1 {SALIDA_REMOTA}/ 2>/dev/null || true",
                          timeout=60)
    except ErrorVast:
        return []
    return [x.strip() for x in salida.splitlines() if x.strip()]


def progreso(inst: dict, planos: list[dict], slug: str = "") -> dict:
    """Dónde va la corrida: qué planos ya tienen clip, si está el MP4 final,
    y las últimas líneas de los logs para ver en qué anda cada placa."""
    archivos = archivos_remotos(inst)
    hechos = [p["id"] for p in planos
              if any(x.startswith(p["id"] + "_") for x in archivos)]
    final = (slug + ".mp4") if slug and (slug + ".mp4") in archivos else None
    try:
        colas = ejecutar(
            inst, f"tail -n 2 {LOG_CORRIDA} /root/gpu*.log 2>/dev/null || true",
            timeout=60)
    except ErrorVast:
        colas = ""
    return {"hechos": hechos, "total": len(planos), "final": final,
            "archivos": archivos, "logs": colas}


def bajar(inst: dict, remotos: list[str], destino, log=print) -> None:
    """Baja archivos de la carpeta de salida por scp, en una sola conexión."""
    import subprocess
    from pathlib import Path
    if not remotos:
        return
    _host, puerto, usuario = _ssh_args(inst)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    log(f"  bajando {len(remotos)} archivo(s) a {destino}")
    r = subprocess.run(
        ["scp", "-P", puerto, "-o", "StrictHostKeyChecking=accept-new"]
        + [f"{usuario}:{SALIDA_REMOTA}/{x}" for x in remotos] + [str(destino)],
        capture_output=True, text=True)
    if r.returncode:
        raise ErrorVast(f"scp falló: {r.stderr[-400:]}")


def instancias(clave: str | None = None) -> list[dict]:
    return _pedir("/instances/", clave).get("instances", [])


def saldo(clave: str | None = None) -> float | None:
    """El crédito que queda en la cuenta, en dólares (`credit` de /users/current/)."""
    d = _pedir("/users/current/", clave)
    c = d.get("credit")
    return round(float(c), 2) if c is not None else None


def destruir(instancia_id: int, *, confirmar: bool = False, clave: str | None = None) -> dict:
    """Borra la instancia y deja de cobrar. **Bajate los archivos antes**: no
    hay vuelta atrás. Para volver en unos días conviene STOP desde la web, que
    apaga la GPU pero conserva el disco con los 59 GB ya bajados."""
    if not confirmar:
        raise ErrorVast(f"destruir() no hace nada sin confirmar=True. "
                        f"La instancia {instancia_id} y todo su disco se pierden.")
    return _pedir(f"/instances/{instancia_id}/", clave, metodo="DELETE", cuerpo={})


def ssh_de(inst: dict) -> str:
    """La línea de ssh para entrar, por la vía que de verdad funciona."""
    try:
        _h, puerto, usuario = _ssh_args(inst)
        return f"ssh -p {puerto} {usuario}"
    except ErrorVast:
        return "(todavía sin SSH)"


def resumen_instancias(clave: str | None = None) -> str:
    ins = instancias(clave)
    if not ins:
        return "No tenés instancias. (Bien: no estás pagando nada.)"
    L = [f"{len(ins)} instancia(s) — recordá DESTROY cuando termines:"]
    for i in ins:
        L.append(f"  {i.get('id')}  {i.get('actual_status', '?'):<10} "
                 f"{i.get('num_gpus', '?')}× {i.get('gpu_name', '?'):<14} "
                 f"${float(i.get('dph_total', 0)):.3f}/h   {ssh_de(i)}")
    return "\n".join(L)
