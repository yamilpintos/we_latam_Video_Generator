"""LA MÁQUINA: una 4×RTX 5090 encendida, con H3 instalado, esperando trabajo.

Hasta ahora cada proyecto alquilaba su propia instancia y la instalación (59 GB
de modelos) se pagaba cada vez. Acá la máquina es una cosa aparte: se enciende
una vez, se instala una vez, y los proyectos se generan en ella uno tras otro
(como se hizo a mano el 13/9 con el koi y el invernadero). El estado vive en
`app/maquina.json`:

    fase        apagada | buscando | arrancando | instalando | lista | fallo
    instancia   id en Vast
    dph         $/h
    inicio/fin  timestamps; `gasto_final` al apagar
    proyecto    slug del proyecto que está generando ahora (o null)

Las funciones de acá las usan tres tareas: `encender.py`, `generar_en.py` y
`correr_cola.py` (que encadena encender → generar → bajar para varios).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from .. import costos, vast
from ..proyecto import Proyecto

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
MIS = RAIZ / "mis-videos"
ESTADO = AQUI / "maquina.json"
ZIP_SETUP = AQUI / "h3-setup.zip"
REMOTO = AQUI.parent / "remoto"
BYTES_MODELOS = 59e9          # perfil max, SOLO_FL=1 (COSTOS §12, VAST.md)
TECHO_DPH = 4.0


# ───────────────────────────────────────────────────────────── estado

def leer() -> dict:
    if not ESTADO.exists():
        return {"fase": "apagada"}
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except Exception:
        return {"fase": "apagada"}


def escribir(**cambios) -> dict:
    d = leer()
    d.update(cambios)
    ESTADO.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def gasto(d: dict) -> dict:
    if not d.get("inicio"):
        return {"minutos": 0, "acumulado": 0.0}
    fin = d.get("fin") or time.time()
    horas = (fin - d["inicio"]) / 3600
    return {"minutos": round(horas * 60), "acumulado": round(d.get("dph", 0) * horas, 2)}


# ───────────────────────────────────────────────────────────── ofertas

def apta(o: vast.Oferta) -> tuple[bool, list[str]]:
    motivos = []
    if o.verificacion != "verified":
        motivos.append("desverificada" if o.verificacion == "deverified" else "sin verificar")
    if o.dph > TECHO_DPH:
        motivos.append("precio absurdo")
    if o.fiabilidad < 0.995:
        motivos.append("fiabilidad < 0,995")
    if "shanghai" in o.geo.lower():
        motivos.append("Shanghái")
    if o.inet_down < 800:
        motivos.append("enlace < 800 Mbps")
    if "5090" not in o.gpu:
        motivos.append("no es 5090")
    return not motivos, motivos


def mejor_oferta() -> vast.Oferta | None:
    """La 4×5090 apta de mayor fiabilidad; a igual fiabilidad, más enlace."""
    lista = [o for o in vast.buscar(gpu="RTX 5090") if apta(o)[0]]
    if not lista:
        return None
    return max(lista, key=lambda o: (round(o.fiabilidad, 3), o.inet_down))


# ───────────────────────────────────────────────────────────── encender

def zip_setup() -> Path:
    """Sólo los scripts de la máquina: setup.sh baja los modelos sin necesitar
    planos (SOLO_FL=1 por defecto cuando no hay planos.json)."""
    with zipfile.ZipFile(ZIP_SETUP, "w", zipfile.ZIP_DEFLATED) as z:
        for n in ("setup.sh", "lanzar.sh", "rescate.sh", "runner.py"):
            z.write(REMOTO / n, n)
    return ZIP_SETUP


def _alquilar(oferta: vast.Oferta, log) -> dict | None:
    log(f"ALQUILANDO {oferta.id} · {oferta.geo} · ${oferta.dph:.3f}/h · {oferta.inet_down:.0f} Mbps · "
        f"fiab {oferta.fiabilidad:.3f}")
    r = vast.crear(oferta.id, confirmar=True, disco_gb=vast.DISCO_GB)
    iid = int(r.get("new_contract") or r.get("id"))
    escribir(fase="arrancando", instancia=iid, dph=float(oferta.dph), inicio=time.time(),
             oferta={"id": oferta.id, "geo": oferta.geo, "gpu": oferta.gpu, "gpus": oferta.gpus,
                     "inet": round(oferta.inet_down), "fiabilidad": round(oferta.fiabilidad, 4)},
             fin=None, gasto_final=None, proyecto=None)
    log(f"instancia {iid} creada")
    vast.autorizar_clave(iid)
    try:
        inst = vast.esperar_lista(iid)
    except Exception as e:
        log(f"!! no arrancó: {e}. La destruyo.")
        try:
            vast.destruir(iid, confirmar=True)
        except Exception:
            pass
        escribir(fase="fallo", fin=time.time())
        return None
    escribir(dph=float(inst.get("dph_total") or oferta.dph))
    return inst


def encender(pedido: int | None = None, log=print, intentos_max: int = 3) -> dict | None:
    """Busca (o toma) una 4×5090 apta, la alquila, espera el SSH y deja
    setup.sh corriendo. Devuelve la instancia (fase `instalando`) o None."""
    intentos, inst = 0, None
    while inst is None and intentos < intentos_max:
        oferta = None
        if pedido and intentos == 0:
            lista = vast.buscar(gpu="RTX 5090", solo_verificadas=False, inet_mbps=0, fiabilidad=0)
            oferta = next((o for o in lista if o.id == pedido), None)
            if oferta is None:
                log(f"la oferta {pedido} ya no está; busco otra apta")
        n = 0
        while oferta is None:
            n += 1
            try:
                oferta = mejor_oferta()
            except Exception as e:
                log(f"consulta {n}: error {e}")
            if oferta is None:
                if n == 1 or n % 10 == 0:
                    log(f"consulta {n} ({time.strftime('%H:%M')}): ninguna 4×5090 apta; sigo cada minuto")
                escribir(fase="buscando", instancia=None, proyecto=None)
                time.sleep(60)
        intentos += 1
        inst = _alquilar(oferta, log)
    if inst is None:
        log("!! tres intentos sin arrancar. Me rindo.")
        return None
    z = zip_setup()
    vast.subir(inst, z)
    cmd = ("export PATH=/venv/main/bin:$PATH && cd /workspace/refs && "
           f"unzip -oq {z.name} && sed -i 's/\\r$//' *.sh *.py && bash setup.sh")
    vast.lanzar(inst, cmd, log=vast.LOG_CORRIDA)
    escribir(fase="instalando")
    log(f"instalando H3 (59 GB) · log en {vast.LOG_CORRIDA} · {vast.ssh_de(inst)}")
    return inst


_cache: dict = {"t": 0, "v": None}


def progreso_instalacion(inst: dict, cada: float = 15.0) -> dict:
    """{gb, pct, listo, ultimo} por SSH, cacheado `cada` segundos."""
    ahora = time.time()
    if _cache["v"] and ahora - _cache["t"] < cada:
        return _cache["v"]
    try:
        salida = vast.ejecutar(
            inst, "du -sb /workspace/ComfyUI/models 2>/dev/null | cut -f1; "
                  "grep -c 'Listo. Ahora' /root/corrida.log 2>/dev/null; "
                  "tail -n 2 /root/corrida.log 2>/dev/null", timeout=40)
        lineas = salida.splitlines()
        b = float(lineas[0]) if lineas and lineas[0].strip().isdigit() else 0.0
        listo = len(lineas) > 1 and lineas[1].strip().isdigit() and int(lineas[1]) > 0
        v = {"gb": round(b / 1e9, 1), "pct": min(99, int(b / BYTES_MODELOS * 100)) if not listo else 100,
             "listo": listo, "ultimo": "\n".join(lineas[2:])[-400:]}
        # Velocidad y tiempo que falta, con dos muestras separadas por ≥ 20 s.
        m = leer()
        prev = m.get("muestra_descarga")
        if prev and ahora - prev["t"] >= 20 and b > prev["b"]:
            gbps = (b - prev["b"]) / (ahora - prev["t"])
            v["mbps"] = round(gbps * 8 / 1e6)
            if gbps > 0 and not listo:
                v["eta_min"] = round(max(0.0, BYTES_MODELOS - b) / gbps / 60 + 1)   # +1: reinicio de ComfyUI
        if not prev or ahora - prev["t"] >= 20:
            escribir(muestra_descarga={"t": ahora, "b": b})
    except Exception as e:
        v = {"gb": None, "pct": None, "listo": False, "ultimo": f"(sin respuesta: {e})"}
    _cache.update(t=ahora, v=v)
    return v


def progreso_general(m: dict, instalacion: dict | None = None) -> dict:
    """Una sola barra para todo el encendido: buscando → arrancando →
    instalando → lista. `pct` de 0 a 100, `etapa` para el texto."""
    fase = m.get("fase", "apagada")
    ahora = time.time()
    if fase == "buscando":
        return {"pct": 2, "etapa": "buscando una 4×5090 apta", "detalle": "consulta a Vast cada minuto"}
    if fase == "arrancando":
        mins = (ahora - m.get("inicio", ahora)) / 60
        return {"pct": 5 + min(10, int(mins / 6 * 10)), "etapa": "arrancando la instancia",
                "detalle": f"{mins:.0f} min · suele tardar 2 a 8; a los 20 se descarta y se busca otra"}
    if fase == "instalando":
        p = instalacion or {}
        gb = p.get("gb") or 0.0
        pct = 15 + int(min(gb / 59.0, 0.99) * 85)
        det = f"bajando los modelos de H3: {gb:.1f} de 59 GB"
        if p.get("mbps"):
            det += f" · {p['mbps']} Mbps"
        if p.get("eta_min") is not None:
            det += f" · faltan ~{p['eta_min']} min"
        return {"pct": pct, "etapa": "instalando H3", "detalle": det}
    if fase == "lista":
        return {"pct": 100, "etapa": "lista", "detalle": "H3 instalado; la máquina espera trabajo"}
    return {"pct": 0, "etapa": fase, "detalle": ""}


def esperar_instalacion(inst: dict, log=print, minutos: int = 45) -> bool:
    t0 = time.time()
    ultimo = -1
    while time.time() - t0 < minutos * 60:
        p = progreso_instalacion(inst, cada=0)
        if p["listo"]:
            escribir(fase="lista", lista_desde=time.time())
            log("H3 instalado: la máquina está lista")
            return True
        if p["pct"] is not None and p["pct"] // 10 != ultimo:
            ultimo = p["pct"] // 10
            log(f"  instalando… {p['gb']} de 59 GB ({p['pct']} %)")
        time.sleep(20)
    log("!! la instalación no terminó en el plazo")
    return False


# ───────────────────────────────────────────────────────────── generar

def generar_proyecto(slug: str, log=print) -> dict:
    """Sube el ZIP del proyecto a la máquina lista y lanza `lanzar.sh` (sin
    reinstalar). Escribe `corrida.json` para el taxímetro. Devuelve la instancia."""
    c = MIS / slug
    p = Proyecto.cargar(c / "proyecto.json")
    zip_ = c / f"{p.slug}-para-vast.zip"
    if not zip_.exists():
        raise RuntimeError("falta el ZIP: empaquetá primero")
    m = leer()
    if m.get("fase") != "lista" or not m.get("instancia"):
        raise RuntimeError(f"la máquina no está lista (fase {m.get('fase')})")
    inst = vast.instancia(int(m["instancia"]))
    anterior = m.get("proyecto")
    if anterior and anterior != p.slug:
        log(f"apartando las salidas de {anterior}…")
        vast.ejecutar(inst, f"cd {vast.SALIDA_REMOTA} 2>/dev/null && mkdir -p _{anterior} && "
                            f"mv *.mp4 *.json _{anterior}/ 2>/dev/null; true", timeout=60)
    vast.subir(inst, zip_)
    vast.ejecutar(inst, f"export PATH=/venv/main/bin:$PATH && cd /workspace/refs && unzip -oq {zip_.name} && "
                        f"sed -i 's/\\r$//' *.sh *.py && cp planos.json /root/planos.json", timeout=180)
    vast.lanzar(inst, "export PATH=/venv/main/bin:$PATH && cd /workspace/refs && PASOS=8 GPUS=4 bash lanzar.sh",
                log=vast.LOG_CORRIDA)
    planos = p.construir()[1]["planos"]
    est = costos.estimar(planos, costos.Maquina(dph=float(m.get("dph", 2.0))))
    (c / "corrida.json").write_text(json.dumps(
        {"instancia": int(m["instancia"]), "dph": float(m.get("dph", 0)), "inicio": time.time(),
         "estimado": round(est.costo_generacion, 2), "maquina_compartida": True}), encoding="utf-8")
    escribir(proyecto=p.slug, generando_desde=time.time())
    log(f"{p.titulo}: {len(planos)} planos lanzados en la instancia {m['instancia']} · "
        f"estimado de generación ${est.costo_generacion:.2f}")
    return inst


def fuentes(slug: str) -> list[str]:
    p = Proyecto.cargar(MIS / slug / "proyecto.json")
    return [x["id"] for x in p.construir()[1]["planos"] if not x.get("clip_de")]


def esperar_clips(slug: str, log=print, minutos: int = 90) -> bool:
    m = leer()
    inst = vast.instancia(int(m["instancia"]))
    p = Proyecto.cargar(MIS / slug / "proyecto.json")
    planos = p.construir()[1]["planos"]
    total = len(fuentes(slug))
    t0, previo = time.time(), -1
    while time.time() - t0 < minutos * 60:
        try:
            prog = vast.progreso(inst, planos, p.slug)
        except Exception as e:
            log(f"  (sin respuesta: {e})")
            time.sleep(60)
            continue
        n = len(prog["hechos"])
        if n != previo:
            log(f"  {slug}: {n}/{total} clips")
            previo = n
        if n >= total:
            return True
        time.sleep(45)
    log(f"!! {slug}: se agotó el plazo con {previo}/{total}")
    return False


def bajar(slug: str, log=print) -> bool:
    m = leer()
    r = subprocess.run([sys.executable, "-X", "utf8", "-u", "-m", "h3pipeline", "bajar",
                        str(MIS / slug / "proyecto.json"), str(m["instancia"])],
                       cwd=str(RAIZ), capture_output=True, text=True, encoding="utf-8", errors="replace")
    for linea in (r.stdout or "").splitlines()[-6:]:
        log("  " + linea)
    return r.returncode == 0


def apagar(log=print) -> dict:
    m = leer()
    iid = m.get("instancia")
    if iid:
        try:
            vast.destruir(int(iid), confirmar=True)
            log(f"instancia {iid} destruida")
        except Exception as ex:
            if "no existe" not in str(ex):
                raise
    g = gasto(m)
    d = escribir(fase="apagada", fin=time.time(), gasto_final=g["acumulado"], proyecto=None)
    for f in MIS.glob("*/corrida.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            if iid and int(c.get("instancia", 0)) == int(iid) and not c.get("fin"):
                c["fin"] = time.time()
                c["gasto_final"] = round(c.get("dph", 0) * (c["fin"] - c["inicio"]) / 3600, 2)
                f.write_text(json.dumps(c), encoding="utf-8")
        except Exception:
            pass
    return {"apagada": iid, "gasto_final": d.get("gasto_final"), "minutos": g["minutos"]}
