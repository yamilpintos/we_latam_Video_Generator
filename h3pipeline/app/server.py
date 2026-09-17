"""La API de la Fábrica. Cada endpoint es una llamada al módulo o una tarea.

Convenciones
  - Los proyectos se identifican por su `slug` = nombre de carpeta en mis-videos/.
  - Nada que cobre (alquilar, destruir) corre sin `confirmar: true` en el cuerpo.
  - Lo que tarda devuelve `{"tarea": {...}}` y se sigue por /api/tareas/{id}.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import config, costos, guionista, montaje, tts, vast, voz as vozmod, web
from ..estructura import Estructura, disponibles
from ..proyecto import Proyecto, ProyectoInvalido
from . import cola, libre, maquina, tareas

RAIZ = Path(__file__).resolve().parents[2]
MIS = RAIZ / "mis-videos"
AQUI = Path(__file__).resolve().parent
STATIC = AQUI / "static"

app = FastAPI(title="La Fábrica", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


# ─────────────────────────────────────────────────────────────── acceso

@app.middleware("http")
async def _contrasena(request, call_next):
    """HTTP Basic con FABRICA_PASSWORD. Sin la variable, la app es local y
    abierta; con ella (Render, el Teramont) cada botón que gasta plata queda
    detrás de la contraseña."""
    import base64
    import os
    import secrets
    clave = os.environ.get("FABRICA_PASSWORD")
    if not clave:
        return await call_next(request)
    auth = request.headers.get("authorization", "")
    ok = False
    if auth.startswith("Basic "):
        try:
            usuario, _, dado = base64.b64decode(auth[6:]).decode("utf-8", "replace").partition(":")
            ok = secrets.compare_digest(dado, clave)
        except Exception:
            ok = False
    if not ok:
        from fastapi.responses import Response
        return Response("La Fábrica: hace falta la contraseña", status_code=401,
                        headers={"WWW-Authenticate": 'Basic realm="La Fabrica"'})
    return await call_next(request)


def _clave_ssh_desde_entorno() -> None:
    """En un servidor la clave SSH para Vast llega por variables de entorno;
    se escribe en ~/.ssh al arrancar, que es donde la busca el módulo."""
    import os
    priv, pub = os.environ.get("VAST_SSH_PRIVATE_KEY"), os.environ.get("VAST_SSH_PUBLIC_KEY")
    if not priv or not pub:
        return
    d = Path.home() / ".ssh"
    d.mkdir(mode=0o700, exist_ok=True)
    k = d / "id_ed25519"
    if not k.exists():
        k.write_text(priv.replace("\\n", "\n").strip() + "\n", encoding="utf-8")
        k.chmod(0o600)
        (d / "id_ed25519.pub").write_text(pub.strip() + "\n", encoding="utf-8")


_clave_ssh_desde_entorno()


# ─────────────────────────────────────────────────────────────── utilidades

def _carpeta(slug: str) -> Path:
    if not slug or "/" in slug or "\\" in slug or slug.startswith("."):
        raise HTTPException(400, "slug inválido")
    c = MIS / slug
    if not (c / "proyecto.json").exists():
        raise HTTPException(404, f"no existe mis-videos/{slug}/proyecto.json")
    return c


def _proyecto(slug: str) -> Proyecto:
    try:
        return Proyecto.cargar(_carpeta(slug) / "proyecto.json")
    except ProyectoInvalido as e:
        raise HTTPException(422, str(e))


def _corrida(c: Path) -> dict | None:
    f = c / "corrida.json"
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None
    horas = ((d.get("fin") or time.time()) - d["inicio"]) / 3600
    d["minutos"] = round(horas * 60)
    d["acumulado"] = round(d.get("dph", 0) * horas, 2)
    return d


def _estado(c: Path, p: Proyecto | None = None) -> dict:
    """Dónde está el proyecto en el flujo: qué existe ya en la carpeta."""
    p = p or Proyecto.cargar(c / "proyecto.json")
    sb, doc = p.construir()
    esperados = [a["id"] + ".png" for a in sb["assets"]] + [m["id"] + ".png" for m in p.madre]
    assets = c / "assets"
    hechos = [x for x in esperados if (assets / x).exists()]
    clips_dir = c / "clips"
    planos = doc["planos"]
    fuentes = sorted({montaje.clip_fuente(x) for x in planos})
    clips = [f for f in fuentes if montaje.buscar_clip(clips_dir, f)] if clips_dir.exists() else []
    masters = sorted([f.name for f in c.glob("*.mp4") if "corte" not in f.name.lower()],
                     key=lambda n: (c / n).stat().st_mtime, reverse=True)
    zip_ = c / f"{p.slug}-para-vast.zip"
    return {
        "planos": len(planos), "segundos": round(sum(x["segundos"] for x in planos), 1),
        "assets": {"hechos": len(hechos), "esperados": len(esperados)},
        "zip": zip_.exists(), "zip_mb": round(zip_.stat().st_size / 1e6, 1) if zip_.exists() else None,
        "clips": {"hechos": len(clips), "esperados": len(fuentes), "faltan": [f for f in fuentes if f not in clips]},
        "corrida": _corrida(c), "masters": masters,
        "tareas": [t.a_dict(lineas=2) for t in tareas.corriendo(p.slug)],
    }


def _oferta_dict(o: vast.Oferta, planos: list[dict] | None, pasos: int = 8) -> dict:
    d = {"id": o.id, "gpu": o.gpu, "gpus": o.gpus, "vram_gb": o.vram_gb, "dph": round(o.dph, 3),
         "disco_gb": round(o.disco_gb), "inet": round(o.inet_down), "fiabilidad": round(o.fiabilidad, 4),
         "geo": o.geo, "verificacion": o.verificacion, "datacenter": o.datacenter}
    motivos = []
    if o.verificacion != "verified":
        motivos.append("desverificada" if o.verificacion == "deverified" else "sin verificar")
    if o.dph > 4.0:
        motivos.append("precio absurdo")
    if o.fiabilidad < 0.995:
        motivos.append("fiabilidad < 0,995")
    if "shanghai" in o.geo.lower():
        motivos.append("Shanghái (colgó el 2/9)")
    if o.inet_down < 800:
        motivos.append("enlace < 800 Mbps")
    if "5090" not in o.gpu:
        motivos.append("no es 5090")
    d["apta"] = not motivos
    d["motivos"] = motivos
    if planos:
        e = costos.estimar(planos, o.a_maquina(), pasos)
        d["estimado"] = {"minutos": round(e.minutos_total), "costo": round(e.costo_total, 2),
                         "generacion": round(e.costo_generacion, 2), "descarga": round(e.costo_descarga, 2),
                         "con_overhead": round(e.costo_total + o.dph * 10 / 60, 2)}
    return d


# ─────────────────────────────────────────────────────────────── páginas

@app.get("/", response_class=HTMLResponse)
def portada():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/mesa", response_class=HTMLResponse)
def mesa():
    """La Mesa de Armado de siempre, regenerada desde el módulo cada vez."""
    return web.generar().read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────── proyectos

@app.get("/api/estructuras")
def estructuras():
    out = []
    for n in disponibles():
        e = Estructura.cargar(n)
        out.append({"nombre": n, "formato": e.formato, "duracion": e.duracion_objetivo,
                    "retencion": e.retencion_objetivo, "tramos": [t.id for t in e.tramos],
                    "plataformas": e.plataformas})
    return out


@app.get("/api/proyectos")
def proyectos():
    out = []
    for f in sorted(MIS.glob("*/proyecto.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            p = Proyecto.cargar(f)
            est = _estado(f.parent, p)
        except Exception as e:  # un proyecto roto no tira la lista
            out.append({"slug": f.parent.name, "titulo": f.parent.name, "error": str(e)[:200]})
            continue
        out.append({"slug": f.parent.name, "titulo": d.get("titulo"), "formato": p.formato,
                    "estructura": p.estructura_resuelta().nombre, "modificado": f.stat().st_mtime,
                    "estado": est})
    return out


class NuevoProyecto(BaseModel):
    proyecto: dict
    slug: str | None = None


@app.post("/api/proyectos")
def crear_proyecto(n: NuevoProyecto):
    try:
        p = Proyecto.desde_dict(n.proyecto)
    except (ProyectoInvalido, KeyError, ValueError) as e:
        raise HTTPException(422, f"proyecto inválido: {e}")
    slug = n.slug or n.proyecto.get("slug") or p.slug
    c = MIS / slug
    if (c / "proyecto.json").exists():
        raise HTTPException(409, f"ya existe mis-videos/{slug}/")
    c.mkdir(parents=True, exist_ok=True)
    (c / "proyecto.json").write_text(json.dumps(n.proyecto, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    return detalle(slug)


class EdicionProyecto(BaseModel):
    proyecto: dict


@app.put("/api/proyectos/{slug}")
def editar_proyecto(slug: str, e: EdicionProyecto):
    c = _carpeta(slug)
    try:
        Proyecto.desde_dict(e.proyecto)
    except (ProyectoInvalido, KeyError, ValueError) as ex:
        raise HTTPException(422, f"proyecto inválido: {ex}")
    (c / "proyecto.json").write_text(json.dumps(e.proyecto, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    return detalle(slug)


@app.get("/api/proyectos/{slug}")
def detalle(slug: str):
    c = _carpeta(slug)
    p = _proyecto(slug)
    sb, doc = p.construir()
    avisos = p.validar(doc["planos"])
    est = p.estructura_resuelta()
    lt = est.linea_de_tiempo(doc["planos"])
    planos = []
    for x, (a, b) in zip(doc["planos"], lt):
        planos.append({"id": x["id"], "tipo": x["tipo"], "tramo": x["tramo"], "segundos": x["segundos"],
                       "usa": x.get("usa"), "desde": a, "hasta": b, "funcion": x.get("funcion", ""),
                       "first_frame": x.get("first_frame"), "clip_de": x.get("clip_de"),
                       "sigue_de": x.get("sigue_de"), "prompt": x["prompt"]})
    return {"slug": slug, "titulo": p.titulo, "formato": p.formato, "estructura": est.nombre,
            "resolucion": list(p.wh), "negativos": p.negativos,
            "proyecto": json.loads((c / "proyecto.json").read_text(encoding="utf-8")),
            "planos": planos, "avisos": avisos, "estado": _estado(c, p),
            "tramos": [{"id": t.id, "desde": t.desde, "hasta": t.hasta, "nombre": t.nombre} for t in est.tramos]}


@app.post("/api/proyectos/{slug}/construir")
def construir(slug: str):
    p = _proyecto(slug)
    salidas = p.escribir(log=lambda *_: None)
    return {"escritos": [k for k in salidas], **{"avisos": p.validar()}}


class OpcionesFrames(BaseModel):
    madre: bool = True
    motor: str = "openai"             # el usuario eligió GPT para las imágenes (16/9/2026)
    rehacer: list[str] = []      # ids de assets a borrar antes (sb_P03, l_cuarto…)


@app.post("/api/proyectos/{slug}/frames")
def frames(slug: str, o: OpcionesFrames):
    c = _carpeta(slug)
    if tareas.corriendo(slug):
        raise HTTPException(409, "ya hay una tarea corriendo en este proyecto")
    for aid in o.rehacer:
        f = c / "assets" / f"{aid}.png"
        if f.exists():
            resp = c / "assets" / "_rehechos"
            resp.mkdir(exist_ok=True)
            shutil.move(str(f), str(resp / f"{aid}-{int(time.time())}.png"))
    args = ["-m", "h3pipeline", "frames", str(c / "proyecto.json"), "--motor", o.motor]
    if o.madre:
        args.append("--madre")
    return {"tarea": tareas.lanzar("dibujos", args, slug).a_dict()}


@app.get("/api/proyectos/{slug}/assets")
def assets(slug: str):
    c = _carpeta(slug)
    p = _proyecto(slug)
    sb, doc = p.construir()
    barras = _detector_barras(c)
    out = []
    for m in p.madre:
        out.append(_asset(c, m["id"], "madre", barras))
    por_plano = {x["first_frame"].split("/")[-1][:-4]: x for x in doc["planos"] if x.get("first_frame")}
    for a in sb["assets"]:
        d = _asset(c, a["id"], "plano", barras)
        pl = por_plano.get(a["id"])
        if pl:
            d["plano"] = pl["id"]
            d["funcion"] = pl.get("funcion", "")
        out.append(d)
    return out


def _asset(c: Path, aid: str, tipo: str, barras) -> dict:
    f = c / "assets" / f"{aid}.png"
    d = {"id": aid, "tipo": tipo, "existe": f.exists(),
         "url": f"/api/proyectos/{c.name}/assets/{aid}.png?t={int(f.stat().st_mtime) if f.exists() else 0}"}
    if f.exists() and barras:
        try:
            a, b = barras(f)
            d["barras"] = [a, b]
            d["con_barras"] = (a + b) > 0.03 * 768
        except Exception:
            pass
    return d


def _detector_barras(c: Path):
    """El detector de letterbox vive en los proyectos lo-fi; si está, se usa."""
    for cand in (c / "barras.py", MIS / "lofi-koi" / "barras.py"):
        if cand.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("barras_" + cand.parent.name, cand)
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                return mod.barras
            except Exception:
                return None
    return None


@app.get("/api/proyectos/{slug}/assets/{nombre}")
def asset_png(slug: str, nombre: str):
    f = _carpeta(slug) / "assets" / Path(nombre).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(str(f))


@app.post("/api/proyectos/{slug}/empaquetar")
def empaquetar(slug: str):
    c = _carpeta(slug)
    args = ["-m", "h3pipeline", "empaquetar", str(c / "proyecto.json")]
    return {"tarea": tareas.lanzar("empaquetar", args, slug).a_dict()}


# ─────────────────────────────────────────────────────────────── vast

@app.get("/api/vast/ofertas")
def ofertas(proyecto: str | None = None, todas: bool = False, pasos: int = 8):
    planos = None
    if proyecto:
        planos = _proyecto(proyecto).construir()[1]["planos"]
    try:
        if todas:
            lista = vast.buscar(planos=planos, gpu="RTX 5090", solo_verificadas=False,
                                inet_mbps=0, fiabilidad=0, respetar_licencia=True)
        else:
            lista = vast.buscar(planos=planos, gpu="RTX 5090")
    except Exception as e:
        raise HTTPException(502, f"Vast no contestó: {e}")
    out = [_oferta_dict(o, planos, pasos) for o in lista]
    out.sort(key=lambda d: (not d["apta"], d.get("estimado", {}).get("costo", d["dph"])))
    return {"consultado": time.time(), "ofertas": out}


@app.get("/api/vast/instancias")
def instancias():
    try:
        ins = vast.instancias()
    except Exception as e:
        raise HTTPException(502, f"Vast no contestó: {e}")
    corridas = {}
    for f in MIS.glob("*/corrida.json"):
        d = _corrida(f.parent)
        if d and d.get("instancia"):
            corridas[int(d["instancia"])] = {**d, "slug": f.parent.name}
    out = []
    for i in ins:
        iid = int(i.get("id"))
        out.append({"id": iid, "estado": i.get("actual_status"), "gpu": i.get("gpu_name"),
                    "gpus": i.get("num_gpus"), "dph": round(float(i.get("dph_total") or 0), 3),
                    "geo": i.get("geolocation"), "ssh": vast.ssh_de(i), "corrida": corridas.get(iid)})
    return {"consultado": time.time(), "instancias": out}


class Alquiler(BaseModel):
    slug: str
    id: int
    confirmar: bool = False
    forzar: bool = False
    pasos: int = 8


@app.post("/api/vast/alquilar")
def alquilar(a: Alquiler):
    c = _carpeta(a.slug)
    p = _proyecto(a.slug)
    zip_ = c / f"{p.slug}-para-vast.zip"
    if not zip_.exists():
        raise HTTPException(409, "falta el ZIP: empaquetá primero")
    if not a.confirmar:
        raise HTTPException(400, "hace falta confirmar: true (esto cobra)")
    if tareas.corriendo(a.slug):
        raise HTTPException(409, "ya hay una tarea corriendo en este proyecto")
    if not a.forzar:
        try:
            lista = vast.buscar(gpu="RTX 5090", solo_verificadas=False, inet_mbps=0, fiabilidad=0)
        except Exception as e:
            raise HTTPException(502, f"Vast no contestó: {e}")
        o = next((x for x in lista if x.id == a.id), None)
        if o is None:
            raise HTTPException(410, "esa oferta ya no está")
        d = _oferta_dict(o, None)
        if not d["apta"]:
            raise HTTPException(409, "oferta no apta: " + ", ".join(d["motivos"]) + " (forzar: true para insistir)")
    args = ["-m", "h3pipeline", "alquilar", str(c / "proyecto.json"), str(a.id), "--si", "--generar",
            "--pasos", str(a.pasos)]
    return {"tarea": tareas.lanzar("alquilar", args, a.slug).a_dict()}


@app.get("/api/vast/seguir/{slug}/{iid}")
def seguir(slug: str, iid: int):
    c = _carpeta(slug)
    p = _proyecto(slug)
    planos = p.construir()[1]["planos"]
    try:
        inst = vast.instancia(iid)
    except Exception as e:
        return {"existe": False, "error": str(e), "corrida": _corrida(c)}
    try:
        prog = vast.progreso(inst, planos, p.slug)
    except Exception as e:
        prog = {"hechos": [], "total": len(planos), "logs": f"(sin logs: {e})"}
    out = {"existe": True, "estado": inst.get("actual_status"), "dph": float(inst.get("dph_total") or 0),
           "ssh": vast.ssh_de(inst), "hechos": prog["hechos"], "total": prog["total"],
           "faltan": [x["id"] for x in planos if x["id"] not in prog["hechos"] and not x.get("clip_de")],
           "logs": (prog.get("logs") or "")[-3000:], "corrida": _corrida(c)}
    # Mientras no hay ningún clip, lo que pasa es la instalación: se mide igual
    # que en la máquina compartida (bytes de modelos contra 59 GB).
    if not prog["hechos"]:
        try:
            out["instalacion"] = maquina.progreso_instalacion(inst, cada=10)
        except Exception:
            pass
    return out


class Bajada(BaseModel):
    slug: str
    id: int


@app.post("/api/vast/bajar")
def bajar(b: Bajada):
    c = _carpeta(b.slug)
    if tareas.corriendo(b.slug):
        raise HTTPException(409, "ya hay una tarea corriendo en este proyecto")
    args = ["-m", "h3pipeline", "bajar", str(c / "proyecto.json"), str(b.id)]
    return {"tarea": tareas.lanzar("bajar", args, b.slug).a_dict()}


class Destruccion(BaseModel):
    id: int
    confirmar: bool = False


@app.post("/api/vast/destruir")
def destruir(d: Destruccion):
    if not d.confirmar:
        raise HTTPException(400, "hace falta confirmar: true")
    try:
        vast.destruir(d.id, confirmar=True)
    except Exception as e:
        raise HTTPException(502, f"no pude destruir: {e}")
    # El gasto final queda escrito en la corrida del proyecto que la alquiló.
    for f in MIS.glob("*/corrida.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if int(c.get("instancia", 0)) == d.id and not c.get("fin"):
            c["fin"] = time.time()
            c["gasto_final"] = round(c.get("dph", 0) * (c["fin"] - c["inicio"]) / 3600, 2)
            f.write_text(json.dumps(c), encoding="utf-8")
            return {"destruida": d.id, "gasto_final": c["gasto_final"], "slug": f.parent.name}
    return {"destruida": d.id}


# ─────────────────────────────────────────────────────────────── clips y máster

@app.get("/api/proyectos/{slug}/clips")
def clips(slug: str):
    c = _carpeta(slug)
    p = _proyecto(slug)
    planos = p.construir()[1]["planos"]
    out = []
    for x in planos:
        if x.get("clip_de"):
            continue
        f = montaje.buscar_clip(c / "clips", x["id"]) if (c / "clips").exists() else None
        tira = c / "qc" / f"tira_{x['id']}.png"
        out.append({"id": x["id"], "funcion": x.get("funcion", ""), "existe": bool(f),
                    "archivo": f.name if f else None, "mb": round(f.stat().st_size / 1e6, 2) if f else None,
                    "tira": f"/api/proyectos/{slug}/qc/{tira.name}?t={int(tira.stat().st_mtime)}" if tira.exists() else None})
    return out


@app.post("/api/proyectos/{slug}/tiras")
def tiras(slug: str):
    """Diez cuadros por clip (2 por segundo): es el control que encontró todo
    lo que entrada/medio/salida dejaba pasar."""
    c = _carpeta(slug)
    (c / "qc").mkdir(exist_ok=True)
    hechas = []
    for f in sorted((c / "clips").glob("*_*.mp4")) if (c / "clips").exists() else []:
        pid = f.name.split("_")[0]
        salida = c / "qc" / f"tira_{pid}.png"
        if salida.exists() and salida.stat().st_mtime > f.stat().st_mtime:
            continue
        r = subprocess.run([config.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(f),
                            "-vf", "fps=2,scale=336:-1,tile=5x2", "-frames:v", "1", str(salida)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            hechas.append(pid)
    return {"tiras": hechas}


@app.get("/api/proyectos/{slug}/qc/{nombre}")
def qc_png(slug: str, nombre: str):
    f = _carpeta(slug) / "qc" / Path(nombre).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(str(f))


class Master(BaseModel):
    musica: str | None = None
    repite: int = 0
    largo_de_pista: bool = False
    otros_loops: list[str] = []     # slugs de otros loops ya masterizados, para alternar
    cierre: str = "fundido"         # loops de UNA escena: fundido | pingpong | corte


@app.post("/api/proyectos/{slug}/master")
def master(slug: str, m: Master):
    c = _carpeta(slug)
    p = _proyecto(slug)
    if tareas.corriendo(slug):
        raise HTTPException(409, "ya hay una tarea corriendo en este proyecto")
    if p.estructura_resuelta().nombre.startswith("loop"):
        bucle = c / "bucle.py"
        if not bucle.exists():
            shutil.copy(MIS / "lofi-koi" / "bucle.py", bucle)
        args = [str(bucle), "--cierre", m.cierre if m.cierre in ("fundido", "pingpong", "corte") else "fundido"]
        if m.musica:
            args += ["--musica", m.musica]
        if m.repite:
            args += ["--repite", str(m.repite)]
        if m.largo_de_pista and m.musica:
            args.append("--largo-de-pista")
            otros = [f for s in m.otros_loops for f in (MIS / s).glob("* - loop.mp4") if (MIS / s).is_dir()]
            if otros:
                args += ["--otros-loops", *[str(f) for f in otros]]
        return {"tarea": tareas.lanzar("máster (loop)", args, slug).a_dict()}
    args = ["-m", "h3pipeline", "mezclar", str(c / "proyecto.json"), str(c / "clips")]
    return {"tarea": tareas.lanzar("máster", args, slug).a_dict()}


@app.get("/api/proyectos/{slug}/archivo/{nombre}")
def archivo(slug: str, nombre: str):
    f = _carpeta(slug) / Path(nombre).name
    if not f.exists() or f.suffix.lower() not in (".mp4", ".srt", ".txt", ".md", ".json", ".mp3", ".wav"):
        raise HTTPException(404)
    return FileResponse(str(f), filename=f.name)


# ─────────────────────────────────────────────────────────────── LA MÁQUINA

_saldo_cache: dict = {"t": 0, "v": None}


def _saldo() -> float | None:
    if time.time() - _saldo_cache["t"] > 60:
        try:
            _saldo_cache.update(t=time.time(), v=vast.saldo())
        except Exception:
            _saldo_cache["t"] = time.time()
    return _saldo_cache["v"]


@app.get("/api/maquina")
def estado_maquina():
    m = maquina.leer()
    out = {**m, "saldo": _saldo(), **maquina.gasto(m), "tareas": [t.a_dict(lineas=4) for t in tareas.corriendo("_maquina")],
           "progreso": maquina.progreso_general(m)}
    iid = m.get("instancia")
    if iid and m.get("fase") not in ("apagada", "fallo"):
        try:
            inst = vast.instancia(int(iid))
        except Exception as e:
            out["existe"] = False
            out["error"] = str(e)
            return out
        out["existe"] = True
        out["estado_vast"] = inst.get("actual_status")
        out["ssh"] = vast.ssh_de(inst)
        prog = None
        if m.get("fase") == "instalando":
            prog = maquina.progreso_instalacion(inst)
            out["instalacion"] = prog
            if prog["listo"]:
                maquina.escribir(fase="lista", lista_desde=time.time())
                out["fase"] = "lista"
                m["fase"] = "lista"
        out["progreso"] = maquina.progreso_general(m, prog)
        if m.get("proyecto") == "_libre" and m.get("fase") == "lista":
            ts = libre.refrescar()
            gen = [t for t in ts if t["estado"] == "generando"]
            out["generando"] = {"slug": "_libre", "titulo": "Libre (chat)", "hechos": 0 if gen else 1, "total": 1,
                                "libre": True}
        elif m.get("proyecto") and m.get("fase") == "lista":
            try:
                p = Proyecto.cargar(MIS / m["proyecto"] / "proyecto.json")
                planos = p.construir()[1]["planos"]
                prog = vast.progreso(inst, planos, p.slug)
                out["generando"] = {"slug": p.slug, "titulo": p.titulo, "hechos": len(prog["hechos"]),
                                    "total": len([x for x in planos if not x.get("clip_de")]),
                                    "logs": (prog.get("logs") or "")[-1500:]}
            except Exception as e:
                out["generando"] = {"slug": m["proyecto"], "error": str(e)}
    return out


class Encendido(BaseModel):
    id: int | None = None
    confirmar: bool = False


@app.post("/api/maquina/encender")
def encender(e: Encendido):
    if not e.confirmar:
        raise HTTPException(400, "hace falta confirmar: true (esto alquila y cobra)")
    m = maquina.leer()
    if m.get("fase") in ("arrancando", "instalando", "lista", "buscando") and m.get("instancia"):
        raise HTTPException(409, f"ya hay una máquina en fase {m['fase']} (instancia {m['instancia']})")
    if tareas.corriendo("_maquina"):
        raise HTTPException(409, "ya hay una tarea de máquina corriendo")
    args = ["-m", "h3pipeline.app.encender"] + ([str(e.id)] if e.id else [])
    maquina.escribir(fase="buscando", instancia=None, proyecto=None, fin=None, gasto_final=None)
    return {"tarea": tareas.lanzar("encender máquina", args, "_maquina").a_dict()}


@app.get("/api/maquina/mejor")
def mejor():
    try:
        o = maquina.mejor_oferta()
    except Exception as ex:
        raise HTTPException(502, f"Vast no contestó: {ex}")
    if not o:
        return {"oferta": None}
    return {"oferta": {"id": o.id, "geo": o.geo, "gpu": o.gpu, "gpus": o.gpus, "dph": round(o.dph, 3),
                       "inet": round(o.inet_down), "fiabilidad": round(o.fiabilidad, 4),
                       "instalacion_estimada": round(o.dph * (7 + 59e9 * 8 / max(o.inet_down, 1) / 1e6 / 60) / 60, 2)}}


class Apagado(BaseModel):
    confirmar: bool = False


@app.post("/api/maquina/apagar")
def apagar(a: Apagado):
    if not a.confirmar:
        raise HTTPException(400, "hace falta confirmar: true")
    for t in tareas.corriendo("_maquina") + tareas.corriendo("_cola"):
        tareas.matar(t.id)
    try:
        return maquina.apagar(log=lambda *_: None)
    except Exception as ex:
        raise HTTPException(502, f"no pude destruir: {ex}")


# ─────────────────────────────────────────────────────────────── LA COLA

@app.get("/api/cola")
def ver_cola():
    d = cola.leer()
    d["corriendo"] = bool(tareas.corriendo("_cola"))
    d["tarea"] = next((t.a_dict(lineas=6) for t in tareas.corriendo("_cola")), None)
    titulos = {}
    for i in d["items"]:
        try:
            titulos[i["slug"]] = json.loads((MIS / i["slug"] / "proyecto.json").read_text(encoding="utf-8")).get("titulo")
        except Exception:
            titulos[i["slug"]] = i["slug"]
        i["titulo"] = titulos[i["slug"]]
        i["zip"] = any((MIS / i["slug"]).glob("*-para-vast.zip"))
    return d


class ItemCola(BaseModel):
    slug: str


@app.post("/api/cola/agregar")
def cola_agregar(i: ItemCola):
    _carpeta(i.slug)
    if not any((MIS / i.slug).glob("*-para-vast.zip")):
        raise HTTPException(409, "el proyecto no está empaquetado: dibujos → empaquetar primero")
    return cola.agregar(i.slug)


@app.post("/api/cola/quitar")
def cola_quitar(i: ItemCola):
    return cola.quitar(i.slug)


class Correr(BaseModel):
    confirmar: bool = False
    apagar_al_final: bool = True


@app.post("/api/cola/correr")
def cola_correr(c: Correr):
    if not c.confirmar:
        raise HTTPException(400, "hace falta confirmar: true (puede alquilar y cobra)")
    if tareas.corriendo("_cola") or tareas.corriendo("_maquina"):
        raise HTTPException(409, "la cola o la máquina ya tienen una tarea corriendo")
    if not cola.pendientes():
        raise HTTPException(409, "la cola está vacía")
    d = cola.leer()
    d["apagar_al_final"] = c.apagar_al_final
    cola.escribir(d)
    return {"tarea": tareas.lanzar("correr la cola", ["-m", "h3pipeline.app.correr_cola"], "_cola").a_dict()}


# ─────────────────────────────────────────────────────────────── EL MODO LIBRE (chat)

class ImagenLibre(BaseModel):
    prompt: str = ""
    aspecto: str = "16:9"
    estilo: str = ""
    imagen_b64: str | None = None
    motor: str = "openai"            # openai | nanobanana


@app.get("/api/libre")
def libre_turnos():
    return {"turnos": libre.refrescar(), "maquina": maquina.leer().get("fase"), "ocupada": libre.ocupada()}


@app.post("/api/libre/imagen")
def libre_imagen(i: ImagenLibre):
    if not i.imagen_b64 and len(i.prompt.strip()) < 8:
        raise HTTPException(422, "escribí qué querés ver, o subí una imagen")
    try:
        return libre.imagen(i.prompt, i.aspecto, i.imagen_b64, i.estilo, i.motor)
    except Exception as e:
        raise HTTPException(502, f"no pude crear la imagen: {e}")


class VideoLibre(BaseModel):
    id: str
    prompt_video: str
    segundos: float = 5.167
    seed: int | None = None


@app.post("/api/libre/video")
def libre_video(v: VideoLibre):
    if len(v.prompt_video.strip()) < 8:
        raise HTTPException(422, "describí qué se mueve")
    m = maquina.leer()
    if m.get("fase") != "lista":
        raise HTTPException(409, f"la máquina no está lista (fase {m.get('fase')}). Encendela desde el inicio.")
    if libre.ocupada():
        raise HTTPException(409, "hay un turno generando; esperá a que termine")
    if m.get("proyecto") and m.get("proyecto") != "_libre":
        try:
            p0 = Proyecto.cargar(MIS / m["proyecto"] / "proyecto.json")
            inst = vast.instancia(int(m["instancia"]))
            planos0 = p0.construir()[1]["planos"]
            prog = vast.progreso(inst, planos0, p0.slug)
            if len(prog["hechos"]) < len([x for x in planos0 if not x.get("clip_de")]):
                raise HTTPException(409, f"la máquina está generando {m['proyecto']}")
        except HTTPException:
            raise
        except Exception:
            pass
    try:
        return libre.video(v.id, v.prompt_video, v.segundos, v.seed, log=lambda *_: None)
    except KeyError:
        raise HTTPException(404, "no existe ese turno")
    except Exception as e:
        raise HTTPException(502, f"no pude lanzar el video: {e}")


@app.get("/api/libre/archivo/{carpeta}/{nombre}")
def libre_archivo(carpeta: str, nombre: str):
    if carpeta not in ("assets", "clips"):
        raise HTTPException(404)
    f = libre.DIR / carpeta / Path(nombre).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(str(f))


class GenerarEn(BaseModel):
    slug: str


@app.post("/api/maquina/generar")
def generar_en(g: GenerarEn):
    c = _carpeta(g.slug)
    m = maquina.leer()
    if m.get("fase") != "lista":
        raise HTTPException(409, f"la máquina no está lista (fase {m.get('fase')})")
    if m.get("proyecto") and m.get("proyecto") != g.slug:
        # ¿el anterior terminó? si no, no se pisa
        try:
            p0 = Proyecto.cargar(MIS / m["proyecto"] / "proyecto.json")
            inst = vast.instancia(int(m["instancia"]))
            prog = vast.progreso(inst, p0.construir()[1]["planos"], p0.slug)
            total = len([x for x in p0.construir()[1]["planos"] if not x.get("clip_de")])
            if len(prog["hechos"]) < total:
                raise HTTPException(409, f"la máquina sigue generando {m['proyecto']} ({len(prog['hechos'])}/{total})")
        except HTTPException:
            raise
        except Exception:
            pass
    if tareas.corriendo(g.slug) or tareas.corriendo("_maquina"):
        raise HTTPException(409, "ya hay una tarea corriendo")
    p = _proyecto(g.slug)
    if not (c / f"{p.slug}-para-vast.zip").exists():
        raise HTTPException(409, "falta el ZIP: empaquetá primero")
    args = ["-m", "h3pipeline.app.generar_en", str(c / "proyecto.json")]
    return {"tarea": tareas.lanzar("generar en la máquina", args, g.slug).a_dict()}


# ─────────────────────────────────────────────────────────────── el guion → proyecto

class Guion(BaseModel):
    guion: str
    formato: str = "short"            # short (9:16) | largo (16:9)
    estructura: str = "short-15"
    titulo: str = ""
    estilo: int | None = 0            # índice en web.ESTILOS, o None si es libre
    estilo_libre: str = ""
    voz: str | None = "pablo"         # kate | pablo | None (sin voz)
    negativos: bool = True
    notas: str = ""
    slug: str | None = None
    duracion: float | None = None     # estira la estructura (loops: 15,5 / 31 / 62 / 93 s)


@app.get("/api/guion/opciones")
def opciones_guion():
    return {"estilos": [{"i": i, **e} for i, e in enumerate(web.ESTILOS)],
            "voces": [{"clave": k, **v} for k, v in guionista.VOCES.items()],
            "estructuras": estructuras()}


@app.post("/api/guion")
def traducir_guion(g: Guion):
    """El guion del director → proyecto.json validado, guardado en su carpeta.
    Tarda 1-3 min (una a tres llamadas al modelo). Corre como tarea."""
    est = web.ESTILOS[g.estilo] if g.estilo is not None and 0 <= g.estilo < len(web.ESTILOS) else None
    estilo_imagen = (g.estilo_libre.strip() or (est["prompt"] if est else "")).strip()
    if not estilo_imagen:
        raise HTTPException(422, "falta el estilo visual")
    slug = g.slug or (re.sub(r"[^a-z0-9]+", "-", g.titulo.lower()).strip("-")[:40] if g.titulo else None)
    if not slug:
        raise HTTPException(422, "falta el título")
    if (MIS / slug / "proyecto.json").exists():
        raise HTTPException(409, f"ya existe mis-videos/{slug}/")
    pedido = {"guion": g.guion, "formato": g.formato, "estructura": g.estructura, "titulo": g.titulo,
              "estilo_imagen": estilo_imagen, "estilo_video": est["cabecera"] if est else "",
              "cierre_video": est["cierre"] if est else "", "medio": est["medio"] if est else "",
              "voz": g.voz, "negativos": g.negativos, "notas": g.notas, "slug": slug,
              "duracion": g.duracion}
    c = MIS / slug
    c.mkdir(parents=True, exist_ok=True)
    (c / "guion.json").write_text(json.dumps(pedido, ensure_ascii=False, indent=2), encoding="utf-8")
    (c / "guion.txt").write_text(g.guion, encoding="utf-8")
    args = ["-m", "h3pipeline.app.traducir", str(c / "guion.json")]
    return {"slug": slug, "tarea": tareas.lanzar("guion → proyecto", args, slug).a_dict()}


# ─────────────────────────────────────────────────────────────── la voz

@app.get("/api/proyectos/{slug}/voz")
def voz(slug: str):
    c = _carpeta(slug)
    p = _proyecto(slug)
    try:
        lineas = p.lineas_de_voz()
    except Exception:
        lineas = []
    cache = c / "voz"
    por_id = {v["id"]: v for v in guionista.VOCES.values()}
    out = []
    for x in lineas:
        tomas = sorted(cache.glob(f"{x.id}_*.mp3"), key=lambda f: f.stat().st_mtime) if cache.exists() else []
        vz = por_id.get(x.voz_id)
        cps_real = (x.caracteres / x.ventana) if x.ventana else 0
        d = {"id": x.id, "personaje": x.personaje, "tipo": x.tipo, "ventana": round(x.ventana, 2),
             "texto": x.texto, "caracteres": x.caracteres, "cps": round(cps_real, 1), "veredicto": x.veredicto,
             "tags": list(x.tags or []), "voz_id": x.voz_id, "tomas": [],
             "voz_nombre": vz["nombre"] if vz else None, "cps_voz": vz["cps"] if vz else None,
             "entra_en_voz": (cps_real <= vz["cps"] * 1.05) if vz else None,
             "max_caracteres": int(x.ventana * vz["cps"]) if vz else None}
        for f in tomas:
            try:
                dur = tts.duracion_util(f)
            except Exception:
                dur = None
            d["tomas"].append({"archivo": f.name, "url": f"/api/proyectos/{slug}/voz/{f.name}",
                               "dur": round(dur, 2) if dur else None,
                               "factor": round(dur / x.ventana, 2) if dur and x.ventana else None})
        out.append(d)
    return {"lineas": out, "voces": p.voces, "cps_referencia": vozmod.CPS,
            "sin_voz": [x.id for x in lineas if not x.voz_id]}


@app.post("/api/proyectos/{slug}/voz/generar")
def voz_generar(slug: str):
    c = _carpeta(slug)
    if tareas.corriendo(slug):
        raise HTTPException(409, "ya hay una tarea corriendo en este proyecto")
    args = ["-m", "h3pipeline", "voz", str(c / "proyecto.json"), "--generar"]
    return {"tarea": tareas.lanzar("voz", args, slug).a_dict()}


@app.get("/api/proyectos/{slug}/voz/{nombre}")
def voz_mp3(slug: str, nombre: str):
    f = _carpeta(slug) / "voz" / Path(nombre).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(str(f), media_type="audio/mpeg")


# ─────────────────────────────────────────────────────────────── la música

class Musica(BaseModel):
    slug: str
    tipo: str                       # «lo-fi lento para estudiar, sin batería marcada…»
    duracion: float = 90.0
    nombre: str = "musica"


@app.post("/api/musica/componer")
def componer(m: Musica):
    c = _carpeta(m.slug)
    if not m.tipo.strip():
        raise HTTPException(422, "falta describir la música")
    if tareas.corriendo(m.slug):
        raise HTTPException(409, "ya hay una tarea corriendo en este proyecto")
    pedido = {"slug": m.slug, "tipo": m.tipo, "duracion": m.duracion,
              "nombre": re.sub(r"[^a-z0-9-]+", "-", m.nombre.lower()).strip("-") or "musica"}
    (c / "musica-pedido.json").write_text(json.dumps(pedido, ensure_ascii=False), encoding="utf-8")
    args = ["-m", "h3pipeline.app.componer", str(c / "musica-pedido.json")]
    return {"tarea": tareas.lanzar("música", args, m.slug).a_dict()}


@app.get("/api/proyectos/{slug}/musica")
def pistas(slug: str):
    c = _carpeta(slug)
    out = []
    for f in sorted(list(c.glob("*.mp3")) + list(c.glob("*.wav")), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            dur = montaje.duracion(f)
        except Exception:
            dur = None
        out.append({"archivo": f.name, "ruta": str(f), "dur": round(dur, 1) if dur else None,
                    "url": f"/api/proyectos/{slug}/archivo/{f.name}"})
    return out


# ─────────────────────────────────────────────────────────────── tareas

@app.get("/api/tareas")
def lista_tareas(slug: str | None = None):
    return tareas.listar(slug)


@app.get("/api/tareas/{tid}")
def una_tarea(tid: str, lineas: int = 80):
    t = tareas.obtener(tid)
    if not t:
        raise HTTPException(404)
    return t.a_dict(lineas=lineas)


@app.post("/api/tareas/{tid}/matar")
def matar_tarea(tid: str):
    return {"matada": tareas.matar(tid)}


@app.exception_handler(Exception)
async def _errores(request, exc):
    return JSONResponse(status_code=500, content={"detail": f"{type(exc).__name__}: {exc}"})
