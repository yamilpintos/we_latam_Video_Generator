"""La API de la Fábrica. Cada endpoint es una llamada al módulo o una tarea.

Convenciones
  - Los proyectos se identifican por su `slug` = nombre de carpeta en mis-videos/.
  - Nada que cobre (alquilar, destruir) corre sin `confirmar: true` en el cuerpo.
  - Lo que tarda devuelve `{"tarea": {...}}` y se sigue por /api/tareas/{id}.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import config, costos, montaje, vast, web
from ..estructura import Estructura, disponibles
from ..proyecto import Proyecto, ProyectoInvalido
from . import tareas

RAIZ = Path(__file__).resolve().parents[2]
MIS = RAIZ / "mis-videos"
AQUI = Path(__file__).resolve().parent
STATIC = AQUI / "static"

app = FastAPI(title="La Fábrica", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


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
    motor: str = "nanobanana"
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
    return {"existe": True, "estado": inst.get("actual_status"), "dph": float(inst.get("dph_total") or 0),
            "ssh": vast.ssh_de(inst), "hechos": prog["hechos"], "total": prog["total"],
            "faltan": [x["id"] for x in planos if x["id"] not in prog["hechos"] and not x.get("clip_de")],
            "logs": (prog.get("logs") or "")[-3000:], "corrida": _corrida(c)}


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
        args = [str(bucle)]
        if m.musica:
            args += ["--musica", m.musica]
        if m.repite:
            args += ["--repite", str(m.repite)]
        return {"tarea": tareas.lanzar("máster (loop)", args, slug).a_dict()}
    args = ["-m", "h3pipeline", "mezclar", str(c / "proyecto.json"), str(c / "clips")]
    return {"tarea": tareas.lanzar("máster", args, slug).a_dict()}


@app.get("/api/proyectos/{slug}/archivo/{nombre}")
def archivo(slug: str, nombre: str):
    f = _carpeta(slug) / Path(nombre).name
    if not f.exists() or f.suffix.lower() not in (".mp4", ".srt", ".txt", ".md", ".json"):
        raise HTTPException(404)
    return FileResponse(str(f), filename=f.name)


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
