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

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import config, costos, guionista, montaje, tts, vast, voces, voz as vozmod, web
from ..estructura import Estructura, disponibles
from ..proyecto import Proyecto, ProyectoInvalido
from . import cola, doblaje_mount, editar, libre, maquina, remaster, remusical_mount, series, tareas

RAIZ = Path(__file__).resolve().parents[2]
MIS = RAIZ / "mis-videos"
AQUI = Path(__file__).resolve().parent
STATIC = AQUI / "static"

app = FastAPI(title="La Fábrica", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

# ReMusical: la herramienta entera (herramientas/remusical) montada en /remusical/.
# Pasa por la misma puerta de entrada (login) que el resto; sus URLs las calcula ella.
REMUSICAL, REMUSICAL_ERROR = remusical_mount.cargar()
if REMUSICAL is not None:
    app.mount("/remusical", REMUSICAL, name="remusical")
else:
    print(f"!! ReMusical no se pudo montar: {REMUSICAL_ERROR.splitlines()[0]}")

# Doblaje: la herramienta entera (herramientas/doblaje) montada en /doblaje/.
DOBLAJE, DOBLAJE_ERROR = doblaje_mount.cargar()
if DOBLAJE is not None:
    app.mount("/doblaje", DOBLAJE, name="doblaje")
else:
    print(f"!! Doblaje no se pudo montar: {DOBLAJE_ERROR.splitlines()[0]}")


# ─────────────────────────────────────────────────────────────── acceso

COOKIE = "fabrica_sesion"


def _credenciales() -> tuple[str, str] | None:
    """(usuario, contraseña) del entorno, o None si la app es local y abierta."""
    import os
    clave = os.environ.get("FABRICA_PASSWORD")
    if not clave:
        return None
    return os.environ.get("FABRICA_USUARIO") or "fabrica", clave


def _ficha(usuario: str, clave: str) -> str:
    """El valor de la cookie: un HMAC de la sesión con la contraseña como
    secreto. Cambiar la contraseña cierra todas las sesiones."""
    import hashlib
    import hmac
    return hmac.new(clave.encode(), f"sesion:{usuario}".encode(), hashlib.sha256).hexdigest()


def _autorizado(request) -> bool:
    import base64
    import secrets
    cred = _credenciales()
    if cred is None:
        return True
    usuario, clave = cred
    ficha = request.cookies.get(COOKIE, "")
    if ficha and secrets.compare_digest(ficha, _ficha(usuario, clave)):
        return True
    auth = request.headers.get("authorization", "")        # curl / scripts
    if auth.startswith("Basic "):
        try:
            _u, _, dado = base64.b64decode(auth[6:]).decode("utf-8", "replace").partition(":")
            return secrets.compare_digest(dado, clave)
        except Exception:
            return False
    return False


@app.middleware("http")
async def _contrasena(request, call_next):
    """Puerta de entrada. Sin FABRICA_PASSWORD la app es local y abierta; con
    ella (Render, el Teramont) hay una pantalla de login y una cookie de sesión
    de 30 días. Las llamadas a /api sin sesión reciben 401 (el front manda al
    login); el resto se redirige a /login. Basic auth sigue valiendo para curl."""
    from fastapi.responses import RedirectResponse
    ruta = request.url.path
    if ruta in ("/login", "/logout") or ruta.startswith("/static/") or _autorizado(request):
        return await call_next(request)
    if ruta.startswith("/api/") or "/api/" in ruta:          # también /remusical/api/…
        return JSONResponse({"detail": "sesión vencida: volvé a entrar"}, status_code=401)
    destino = ruta + (("?" + request.url.query) if request.url.query else "")
    return RedirectResponse(f"/login?next={destino}", status_code=302)


def _https(request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"


@app.get("/login", response_class=HTMLResponse)
def login_pantalla(request: Request):
    if _credenciales() is None or _autorizado(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/", status_code=302)
    return (STATIC / "login.html").read_text(encoding="utf-8")


@app.post("/login")
async def login_entrar(request: Request):
    import secrets
    from fastapi.responses import RedirectResponse
    cred = _credenciales()
    if cred is None:
        return RedirectResponse("/", status_code=303)
    form = await request.form()
    usuario, clave = cred
    u, c = str(form.get("usuario", "")).strip(), str(form.get("contrasena", ""))
    siguiente = str(form.get("next", "/"))
    if not siguiente.startswith("/") or siguiente.startswith("//"):
        siguiente = "/"
    if not (secrets.compare_digest(u, usuario) and secrets.compare_digest(c, clave)):
        return RedirectResponse(f"/login?e=1&next={siguiente}", status_code=303)
    r = RedirectResponse(siguiente, status_code=303)
    r.set_cookie(COOKIE, _ficha(usuario, clave), max_age=30 * 24 * 3600, httponly=True,
                 samesite="lax", secure=_https(request), path="/")
    return r


@app.get("/logout")
def login_salir(request: Request):
    from fastapi.responses import RedirectResponse
    r = RedirectResponse("/login" if _credenciales() else "/", status_code=302)
    r.delete_cookie(COOKIE, path="/")
    return r


def _clave_ssh_desde_entorno() -> None:
    """En un servidor la clave SSH para Vast llega por variables de entorno;
    se escribe en ~/.ssh al arrancar, que es donde la busca el módulo."""
    import os
    import subprocess
    priv, pub = (os.environ.get("VAST_SSH_PRIVATE_KEY") or "").strip(), (os.environ.get("VAST_SSH_PUBLIC_KEY") or "").strip()
    if not priv:
        return
    d = Path.home() / ".ssh"
    d.mkdir(mode=0o700, exist_ok=True)
    k = d / "id_ed25519"
    # Se reescribe en cada arranque, así un cambio en el entorno se aplica.
    # newline="\n": en Windows write_text escribiría CRLF y ssh rechaza la clave.
    k.write_text(_normalizar_clave_privada(priv), encoding="utf-8", newline="\n")
    k.chmod(0o600)
    if not pub:
        # Sin pública en el entorno, se deriva de la privada: una variable menos que pegar.
        try:
            r = subprocess.run(["ssh-keygen", "-y", "-f", str(k)], capture_output=True, text=True, timeout=20)
            pub = r.stdout.strip() if r.returncode == 0 else ""
        except Exception:
            pub = ""
    if pub:
        (d / "id_ed25519.pub").write_text(pub.strip('"').strip() + "\n", encoding="utf-8", newline="\n")


def _normalizar_clave_privada(priv: str) -> str:
    """Una clave OpenSSH pegada en un formulario web llega de mil formas:
    con `\\n` literales, entre comillas, o en UNA línea con espacios donde
    iban los saltos. ssh la rechaza si no está en bloque; acá se rearma."""
    import re
    s = priv.replace("\\n", "\n").strip().strip('"').strip("'").strip()
    # Cabeceras maltratadas («----BEGIN -OPENSSH PRIVATE KEY-----», visto el
    # 17/9 en Render): se rescata el tipo y el cuerpo y se rearma la cabecera.
    # El cuerpo es base64 (sin guiones), así que los guiones se pueden tratar
    # como espacios: quedan BEGIN, las palabras del tipo en mayúsculas, el
    # cuerpo, END y otra vez el tipo.
    tokens = s.replace("-", " ").split()
    if "BEGIN" not in tokens or "END" not in tokens:
        return s + "\n"
    i, j = tokens.index("BEGIN") + 1, tokens.index("END")
    tipo_l = []
    while i < j and re.fullmatch(r"[A-Z]+", tokens[i]):
        tipo_l.append(tokens[i])
        i += 1
    tipo = " ".join(tipo_l) or "OPENSSH PRIVATE KEY"
    cuerpo = "".join(tokens[i:j])
    lineas = [cuerpo[i:i + 70] for i in range(0, len(cuerpo), 70)]
    return f"-----BEGIN {tipo}-----\n" + "\n".join(lineas) + f"\n-----END {tipo}-----\n"


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
    # Una corrida sin `fin` de hace más de 12 h no es una máquina viva: es un
    # registro viejo (los proyectos del repo mostraban «máquina viva · $805»).
    d["vieja"] = not d.get("fin") and (time.time() - d["inicio"]) > 12 * 3600
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
    # Una sola definición de «apta» para toda la app (maquina.apta): hasta el
    # 18/9 había dos copias y una dejaba pasar China continental.
    ok, motivos = maquina.apta(o)
    d["apta"] = ok
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


@app.get("/api/remusical")
def remusical_estado():
    """Qué ve la puerta de ReMusical en la portada: montada o no, y qué le falta."""
    return remusical_mount.estado(REMUSICAL_ERROR)


@app.get("/api/doblaje")
def doblaje_estado():
    """Qué ve la puerta de Doblaje en la portada: montada o no, y qué le falta."""
    return doblaje_mount.estado(DOBLAJE_ERROR)


if DOBLAJE is None:
    @app.get("/doblaje/", response_class=HTMLResponse)
    @app.get("/doblaje", response_class=HTMLResponse)
    def doblaje_caido():
        return f"""<!doctype html><meta charset="utf-8"><title>Doblaje</title>
<body style="font-family:system-ui;max-width:720px;margin:60px auto;padding:0 20px;color:#eee;background:#111">
<h1>Doblaje no arrancó</h1><p>La herramienta está en <code>herramientas/doblaje/</code> pero no se pudo importar.
Instalá sus dependencias y reiniciá La Fábrica:</p><pre style="background:#000;padding:12px;border-radius:8px">pip install -r herramientas/doblaje/requirements.txt</pre>
<pre style="white-space:pre-wrap;color:#f88">{DOBLAJE_ERROR}</pre><p><a href="/" style="color:#9cf">← La Fábrica</a></p>"""


if REMUSICAL is None:
    @app.get("/remusical/", response_class=HTMLResponse)
    @app.get("/remusical", response_class=HTMLResponse)
    def remusical_caida():
        return f"""<!doctype html><meta charset="utf-8"><title>ReMusical</title>
<body style="font-family:system-ui;max-width:720px;margin:60px auto;padding:0 20px;color:#eee;background:#111">
<h1>ReMusical no arrancó</h1><p>La herramienta está en <code>herramientas/remusical/</code> pero no se pudo importar.
Instalá sus dependencias y reiniciá La Fábrica:</p><pre style="background:#000;padding:12px;border-radius:8px">pip install -r herramientas/remusical/requirements.txt</pre>
<pre style="white-space:pre-wrap;color:#f88">{REMUSICAL_ERROR}</pre><p><a href="/" style="color:#9cf">← La Fábrica</a></p>"""


# ─────────────────────────────────────────────────────────────── proyectos

@app.get("/api/salud")
def salud():
    """¿Este servidor GUARDA lo que produce? En Render, sin un disco persistente
    montado en mis-videos/, cada reinicio (memoria, deploy, mantenimiento)
    borra series, clips y másters: el 18 y el 19/9 se perdieron dos series
    enteras así. Se detecta comparando el dispositivo de mis-videos/ con el de
    la raíz del código: si es el mismo, mis-videos vive en el contenedor."""
    import os
    local = os.environ.get("FABRICA_HOST", "127.0.0.1") in ("127.0.0.1", "localhost")
    persistente = True
    detalle = "PC local: todo queda en el disco de esta máquina"
    if not local:
        try:
            MIS.mkdir(parents=True, exist_ok=True)
            persistente = os.stat(MIS).st_dev != os.stat(RAIZ).st_dev
            detalle = ("mis-videos/ está en un disco aparte (persistente)" if persistente
                       else "mis-videos/ vive DENTRO del contenedor: se borra en cada reinicio")
        except Exception as e:
            persistente, detalle = False, f"no pude comprobar el disco: {e}"
    mem = None
    try:
        with open("/sys/fs/cgroup/memory.max") as f:
            t = f.read().strip()
            mem = None if t == "max" else round(int(t) / 1e6)
    except Exception:
        pass
    return {"local": local, "persistente": persistente, "detalle": detalle, "memoria_mb": mem}


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
                    "estado": est, "serie": d.get("serie")})
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


@app.delete("/api/proyectos/{slug}")
def borrar_proyecto(slug: str):
    """A la papelera (`mis-videos/_papelera/<slug>-<fecha>/`), no se destruye:
    el usuario pidió limpiar los proyectos viejos del repo que aparecen en
    Render sin dibujos ni clips (18/9)."""
    c = _carpeta(slug)
    if tareas.corriendo(slug):
        raise HTTPException(409, "hay una tarea corriendo en este proyecto")
    if any(i["slug"] == slug and i["estado"] == "generando" for i in cola.leer()["items"]):
        raise HTTPException(409, "el proyecto se está generando en la cola")
    cola.quitar(slug)
    pap = MIS / "_papelera"
    pap.mkdir(parents=True, exist_ok=True)
    destino = pap / f"{slug}-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.move(str(c), str(destino))
    return {"ok": True, "papelera": destino.name}


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
    for cand in (c / "barras.py", AQUI / "herramientas" / "barras.py", MIS / "lofi-koi" / "barras.py"):
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


class Reescribir(BaseModel):
    forzar: bool = False
    solo: list[str] = []


@app.post("/api/proyectos/{slug}/reescribir")
def reescribir_prompts(slug: str, r: Reescribir):
    """Escribe el prompt oficial de H3 de cada plano (tarea; GPT + validación)."""
    c = _carpeta(slug)
    if tareas.corriendo(slug):
        raise HTTPException(409, "ya hay una tarea corriendo en este proyecto")
    args = ["-m", "h3pipeline", "reescribir", str(c / "proyecto.json")]
    if r.forzar:
        args.append("--forzar")
    if r.solo:
        args += ["--solo", *r.solo]
    return {"tarea": tareas.lanzar("prompts H3", args, slug).a_dict()}


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


@app.get("/api/proyectos/{slug}/clip/{nombre}")
def clip_crudo(slug: str, nombre: str):
    """Un clip tal como lo bajó la máquina (clips/<id>_*.mp4), para verlo o revisarlo."""
    c = _carpeta(slug) / "clips"
    f = montaje.buscar_clip(c, Path(nombre).stem.split("_")[0]) if c.exists() else None
    if not f:
        raise HTTPException(404)
    return FileResponse(str(f), media_type="video/mp4", filename=f.name)


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
            origen = AQUI / "herramientas" / "bucle.py"
            if not origen.exists():
                origen = MIS / "lofi-koi" / "bucle.py"
            shutil.copy(origen, bucle)
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
    if not p.voz:
        # Sin voz en off (series actuadas: los personajes hablan dentro del clip,
        # el audio de H3 es la pista): `montar` concatena y escribe el SRT de los
        # diálogos; `mezclar` exigiría pistas de ElevenLabs que no existen.
        args = ["-m", "h3pipeline", "montar", str(c / "proyecto.json"), str(c / "clips")]
        return {"tarea": tareas.lanzar("máster (actuado)", args, slug).a_dict()}
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
    maquina.adoptar()          # estado perdido pero instancia viva → se retoma
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
            if isinstance(e, vast.ErrorVast) and "no existe" in str(e):
                # Destruida desde otro lado: el estado pasa a apagada solo, y
                # «Encender» vuelve a estar disponible (18/9).
                out.update(maquina.desaparecida(m), existe=False)
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
        if m.get("proyecto") in ("_libre", "_editar") and m.get("fase") == "lista":
            mod = libre if m["proyecto"] == "_libre" else editar
            ts = mod.refrescar()
            gen = [t for t in ts if t["estado"] in ("generando", "instalando_ref2va")]
            out["generando"] = {"slug": m["proyecto"], "titulo": "Libre (chat)" if m["proyecto"] == "_libre" else "Editar video",
                                "hechos": 0 if gen else 1, "total": 1, "libre": True}
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
    maquina.escribir(fase="buscando", instancia=None, proyecto=None, fin=None, gasto_final=None, error=None)
    return {"tarea": tareas.lanzar("encender máquina", args, "_maquina").a_dict()}


@app.get("/api/maquina/diagnostico")
def diagnostico_maquina():
    """¿Este servidor puede entrar por SSH a una máquina de Vast? Sin alquilar."""
    return vast.diagnostico_ssh()


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
    ajuste: str = "encajar"          # imagen subida: encajar (entera, fondo desenfocado) | recortar


@app.get("/api/libre")
def libre_turnos():
    return {"turnos": libre.refrescar(), "maquina": maquina.sincronizar().get("fase"), "ocupada": libre.ocupada()}


@app.post("/api/libre/imagen")
def libre_imagen(i: ImagenLibre):
    if not i.imagen_b64 and len(i.prompt.strip()) < 8:
        raise HTTPException(422, "escribí qué querés ver, o subí una imagen")
    try:
        return libre.imagen(i.prompt, i.aspecto, i.imagen_b64, i.estilo, i.motor, i.ajuste)
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
    m = maquina.sincronizar()
    if m.get("fase") != "lista":
        raise HTTPException(409, f"la máquina no está lista (fase {m.get('fase')}). Encendela desde el inicio.")
    if libre.ocupada() or editar.ocupada():
        raise HTTPException(409, "hay un turno generando; esperá a que termine")
    if m.get("proyecto") and m.get("proyecto") not in ("_libre", "_editar"):
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


class PromptLibre(BaseModel):
    id: str
    texto: str
    segundos: float = 5.167


@app.post("/api/libre/reescribir")
def libre_reescribir(q: PromptLibre):
    """Lo que escribió el usuario → el prompt oficial de H3, para verlo y
    retocarlo antes de generar. Tarda 10-20 s; cuesta centavos."""
    try:
        return libre.armar_prompt(q.id, q.texto, q.segundos, log=lambda *_: None)
    except KeyError:
        raise HTTPException(404, "no existe ese turno")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"el reescritor falló: {e}")


# ─────────────────────────────────────────────────────────────── EDITAR (Ref2VA)

@app.get("/api/editar")
def editar_turnos():
    return {"turnos": editar.refrescar(), "maquina": maquina.sincronizar().get("fase"),
            "ocupada": editar.ocupada() or libre.ocupada()}


class VideoSubido(BaseModel):
    nombre: str
    b64: str
    ajuste: str = "encajar"          # encajar (entero, fondo desenfocado) | recortar
    desde: float = 0.0               # segundo desde el que se toma el video


@app.post("/api/editar/video")
def editar_subir(v: VideoSubido):
    try:
        return editar.subir_video(v.nombre, v.b64, v.ajuste, v.desde)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"no pude preparar el video: {e}")


class ImagenRef(BaseModel):
    b64: str | None = None           # None = quitar la referencia


@app.post("/api/editar/{tid}/referencia")
def editar_referencia(tid: str, i: ImagenRef):
    try:
        return editar.referencia(tid, i.b64) if i.b64 else editar.quitar_referencia(tid)
    except KeyError:
        raise HTTPException(404, "no existe ese turno")


class PromptEdicion(BaseModel):
    id: str
    texto: str
    segundos: float = 5.167
    audio_original: bool = True
    dialogo: str = ""


@app.post("/api/editar/reescribir")
def editar_reescribir(q: PromptEdicion):
    try:
        return editar.armar_prompt(q.id, q.texto, q.segundos, q.audio_original, q.dialogo, log=lambda *_: None)
    except KeyError:
        raise HTTPException(404, "no existe ese turno")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"el reescritor falló: {e}")


class Edicion(PromptEdicion):
    seed: int | None = None


@app.post("/api/editar/generar")
def editar_generar(e: Edicion):
    if len(e.texto.strip()) < 6:
        raise HTTPException(422, "decí qué querés cambiar")
    try:
        return editar.video(e.id, e.texto, e.segundos, e.seed, e.audio_original, e.dialogo, log=lambda *_: None)
    except KeyError:
        raise HTTPException(404, "no existe ese turno")
    except RuntimeError as ex:
        raise HTTPException(409, str(ex))
    except Exception as ex:
        raise HTTPException(502, f"no pude lanzar la edición: {ex}")


@app.get("/api/editar/archivo/{carpeta}/{nombre}")
def editar_archivo(carpeta: str, nombre: str):
    if carpeta not in ("fuentes", "assets", "clips"):
        raise HTTPException(404)
    f = editar.DIR / carpeta / Path(nombre).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(str(f), filename=f.name)


# ─────────────────────────────────────────────────────── SERIES (producción en masa)
# La capa de arriba: personajes fijos + estilo + idea → lista de capítulos →
# guiones → proyectos → cola. Lo que llama a una API corre como tarea con slug
# `_serie:<slug>`; lo que gasta GPU es la cola de siempre.

def _slug_serie(slug: str) -> str:
    return f"_serie:{slug}"


@app.get("/api/series")
def series_listar():
    return {"series": series.listar(), "estilos": [{"i": i, **e} for i, e in enumerate(web.ESTILOS)],
            "voces": [{"clave": k, **v} for k, v in guionista.VOCES.items()], "estructuras": estructuras()}


class NuevaSerie(BaseModel):
    titulo: str
    formato: str = "short"            # short | largo | musica
    idea: str = ""                    # se puede escribir después, ya con los personajes cargados
    estructura: str | None = None
    duracion: float | None = None
    voz: str | None = "pablo"
    estilo: int | None = 0
    estilo_libre: str = ""
    continuidad: str = "antologia"    # antologia | serial
    musica: dict | None = None        # {genero, tipo, duracion} para music video
    modo: str = "narrado"             # narrado (voz en off) | actuado (los personajes hablan en cámara)
    toma: str | None = None           # shorts: una (tomas de 15 s; duracion = 15/30/45/60) | cortes (planos de 5 s)
                                      # largos actuados: escenas (un dibujo por escena, 22/9) | cortes (uno por plano)


@app.post("/api/series")
def series_crear(n: NuevaSerie):
    try:
        return series.crear(n.titulo, n.formato, n.idea, estructura=n.estructura, duracion=n.duracion, voz=n.voz,
                            estilo=n.estilo, estilo_libre=n.estilo_libre, continuidad=n.continuidad, musica=n.musica,
                            modo=n.modo, toma=n.toma)
    except ValueError as e:
        raise HTTPException(422, str(e))


def _serie_o_404(slug: str) -> dict:
    try:
        return series.leer(slug)
    except KeyError:
        raise HTTPException(404, "no existe esa serie")


@app.get("/api/series/{slug}")
def serie_detalle(slug: str):
    s = _serie_o_404(slug)
    m = maquina.leer()
    pasadas = tareas.listar(_slug_serie(slug), cuantas=1)
    ultima = None
    if pasadas:
        t = tareas.obtener(pasadas[0]["id"])
        ultima = t.a_dict(lineas=60) if t else None
    return {**s, "proyectos": series.estado_proyectos(s), "banco_voces": _banco_voces(),
            "tarea": next((t.a_dict(lineas=8) for t in tareas.corriendo(_slug_serie(slug))), None),
            "ultima_tarea": ultima, "cola": {**cola.leer(), "corriendo": bool(tareas.corriendo("_cola")) or cola.leer().get("corriendo", False)},
            "maquina": {**{k: m.get(k) for k in ("fase", "instancia", "dph", "proyecto", "error")}, **maquina.gasto(m)}}


class EdicionSerie(BaseModel):
    titulo: str | None = None
    idea: str | None = None
    notas: str | None = None
    continuidad: str | None = None
    voz: str | None = None
    estructura: str | None = None
    estilo: dict | None = None        # {preset, libre}
    musica: dict | None = None
    modo: str | None = None
    toma: str | None = None
    duracion: float | None = None     # largos: segundos totales (la estructura se estira)
    dialogos: bool | None = None      # largos narrados: los personajes dicen sus citas en cámara


@app.put("/api/series/{slug}")
def serie_editar(slug: str, e: EdicionSerie):
    _serie_o_404(slug)
    campos = {k: v for k, v in e.model_dump().items() if v is not None}
    return series.actualizar(slug, **campos)


@app.delete("/api/series/{slug}")
def serie_borrar(slug: str):
    _serie_o_404(slug)
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "hay una tarea de esta serie corriendo")
    try:
        series.borrar(slug)
    except RuntimeError as ex:
        raise HTTPException(409, str(ex))
    return {"ok": True}


class NuevoPersonaje(BaseModel):
    nombre: str
    descripcion: str
    b64: str | None = None            # imagen de referencia (opcional)


@app.post("/api/series/{slug}/personajes")
def serie_personaje(slug: str, p: NuevoPersonaje):
    _serie_o_404(slug)
    try:
        return series.agregar_personaje(slug, p.nombre, p.descripcion, p.b64, log=lambda *_: None)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"no pude describir al personaje: {e}")


class EdicionPersonaje(BaseModel):
    b64: str | None = None            # foto de referencia nueva (después: «otra hoja»)
    nombre: str | None = None
    descripcion: str | None = None
    descripcion_es: str | None = None
    voz: str | None = None
    voz_id: str | None = None         # preset del banco de voces ("" = sin voz de referencia)
    genero: str | None = None         # m | f | n
    aprobada: bool | None = None


@app.put("/api/series/{slug}/personajes/{pid}")
def serie_personaje_editar(slug: str, pid: str, e: EdicionPersonaje):
    _serie_o_404(slug)
    try:
        if e.aprobada is not None:
            series.aprobar_personaje(slug, pid, e.aprobada)
        if e.b64:
            series.foto_personaje(slug, pid, e.b64)
        return series.editar_personaje(slug, pid, nombre=e.nombre, descripcion=e.descripcion, descripcion_es=e.descripcion_es, voz=e.voz,
                                       voz_id=e.voz_id, genero=e.genero)
    except KeyError:
        raise HTTPException(404, "no existe ese personaje")
    except ValueError as e:
        raise HTTPException(422, str(e))


# ─────────────────────────────────────────────────────────────── EL BANCO DE VOCES
# Presets de timbre para Ref2VA (21/9): la misma voz en todos los clips de un
# personaje. Se asignan al azar por género al crear el personaje y quedan fijas.

def _banco_voces() -> list[dict]:
    return [{k: v.get(k) for k in ("id", "nombre", "genero", "descripcion", "segundos", "origen", "origen_carpeta")} for v in voces.listar()]


@app.get("/api/voces")
def voces_listar():
    return {"voces": _banco_voces(), **voces.resumen()}


@app.get("/api/voces/{vid}.wav")
def voces_audio(vid: str):
    v = voces.ver(Path(vid).name)
    if not v:
        raise HTTPException(404)
    return FileResponse(v["ruta"], media_type="audio/wav", filename=v["archivo"])


class ExtraerVoz(BaseModel):
    proyecto: str                     # slug del proyecto que tiene el clip (o el máster)
    archivo: str                      # nombre del mp4 dentro del proyecto o de clips/
    inicio: float
    fin: float
    id: str
    nombre: str = ""
    genero: str = "m"
    descripcion: str = ""


@app.post("/api/voces/extraer")
def voces_extraer(e: ExtraerVoz):
    """Saca la voz de un clip ya generado (2-15 s limpios) y la guarda como preset."""
    c = _carpeta(e.proyecto)
    f = c / Path(e.archivo).name
    if not f.exists():
        f = c / "clips" / Path(e.archivo).name
    if not f.exists():
        raise HTTPException(404, "no está ese clip")
    try:
        return voces.extraer(f, e.inicio, e.fin, e.id, e.genero, e.nombre, e.descripcion)
    except ValueError as ex:
        raise HTTPException(422, str(ex))


@app.delete("/api/voces/{vid}")
def voces_quitar(vid: str):
    if not voces.quitar(Path(vid).name):
        raise HTTPException(404)
    return {"ok": True}


@app.delete("/api/series/{slug}/personajes/{pid}")
def serie_personaje_quitar(slug: str, pid: str):
    _serie_o_404(slug)
    return series.quitar_personaje(slug, pid)


class NuevaLocacion(BaseModel):
    nombre: str
    descripcion: str


@app.post("/api/series/{slug}/locaciones")
def serie_locacion(slug: str, l: NuevaLocacion):
    _serie_o_404(slug)
    try:
        return series.agregar_locacion(slug, l.nombre, l.descripcion, log=lambda *_: None)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"no pude describir la locación: {e}")


@app.delete("/api/series/{slug}/locaciones/{lid}")
def serie_locacion_quitar(slug: str, lid: str):
    _serie_o_404(slug)
    return series.quitar_locacion(slug, lid)


class PedidoHojas(BaseModel):
    ids: list[str] = []
    motor: str = "openai"
    rehacer: bool = False


@app.post("/api/series/{slug}/hojas")
def serie_hojas(slug: str, p: PedidoHojas):
    """Dibuja las hojas de modelo y locaciones que faltan (una imagen por asset, ~$0,05-0,20 cada una)."""
    _serie_o_404(slug)
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "ya hay una tarea de esta serie corriendo")
    args = ["-m", "h3pipeline.app.serie_tarea", "hojas", slug, "--motor", p.motor] + (["--rehacer"] if p.rehacer else []) + p.ids
    return {"tarea": tareas.lanzar("hojas de modelo", args, _slug_serie(slug)).a_dict()}


class PedidoPlan(BaseModel):
    n: int = 10
    pista: str = ""


@app.post("/api/series/{slug}/planificar")
def serie_planificar(slug: str, p: PedidoPlan):
    _serie_o_404(slug)
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "ya hay una tarea de esta serie corriendo")
    n = max(1, min(50, p.n))
    s = series.leer(slug)
    if len((s.get("idea") or "").strip()) < 20:
        raise HTTPException(422, "escribí primero la idea general de la serie (paso 2), nombrando a los personajes")
    args = ["-m", "h3pipeline.app.serie_tarea", "planificar", slug, str(n)] + ([p.pista] if p.pista.strip() else [])
    return {"tarea": tareas.lanzar(f"planificar {n} capítulos", args, _slug_serie(slug)).a_dict()}


class EdicionCapitulo(BaseModel):
    titulo: str | None = None
    premisa: str | None = None
    guion: str | None = None
    locacion: str | None = None
    musica: str | None = None
    personajes: list[str] | None = None
    vestuario: dict | None = None     # {id del personaje: ropa de este capítulo}
    tomas: int | None = None          # 1-4 tomas de 15 s para ESTE capítulo (pisa el default de la serie)
    estado: str | None = None         # aprobado | descartado | guion (aprobar guion) | propuesto


@app.put("/api/series/{slug}/capitulos/{n}")
def serie_capitulo_editar(slug: str, n: int, e: EdicionCapitulo):
    _serie_o_404(slug)
    campos = {k: v for k, v in e.model_dump().items() if v is not None}
    try:
        # Un capítulo que quedó «escribiendo»/«produciendo» sin ninguna tarea viva
        # está huérfano (la tarea murió): se le puede fijar el estado a mano.
        if campos.get("estado") and not tareas.corriendo(_slug_serie(slug)):
            series._estado(slug, n, campos.pop("estado"))
        return series.editar_capitulo(slug, n, **campos)
    except KeyError:
        raise HTTPException(404, "no existe ese capítulo")
    except RuntimeError as ex:
        raise HTTPException(409, str(ex))


@app.post("/api/series/{slug}/capitulos/{n}/guion")
def serie_capitulo_guion(slug: str, n: int):
    s = _serie_o_404(slug)
    try:
        c = series.capitulo(s, n)
    except KeyError:
        raise HTTPException(404, "no existe ese capítulo")
    if c["estado"] not in ("aprobado", "guion", "error"):
        raise HTTPException(409, f"el capítulo está {c['estado']}; aprobalo primero")
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "ya hay una tarea de esta serie corriendo")
    args = ["-m", "h3pipeline.app.serie_tarea", "guion", slug, str(n)]
    return {"tarea": tareas.lanzar(f"guion del capítulo {n}", args, _slug_serie(slug)).a_dict()}


class PedidoProducir(BaseModel):
    confirmar: bool = False
    hasta: str = "cola"               # proyecto | dibujos | cola
    motor: str = "openai"
    rehacer: bool = False             # descartar el proyecto anterior y volver a traducir
    cola: bool = True                 # (masa) encender la máquina, generar y masterizar (todo)
    apagar: bool = True               # (masa) apagar la máquina al final de la cola


@app.post("/api/series/{slug}/capitulos/{n}/producir")
def serie_capitulo_producir(slug: str, n: int, p: PedidoProducir):
    """Guion aprobado → proyecto + voz + dibujos + ZIP + cola. Gasta API (GPT,
    ElevenLabs, imágenes), no GPU: por eso pide confirmar."""
    s = _serie_o_404(slug)
    if not p.confirmar:
        raise HTTPException(400, "hace falta confirmar: true (gasta GPT, voz e imágenes)")
    try:
        c = series.capitulo(s, n)
    except KeyError:
        raise HTTPException(404, "no existe ese capítulo")
    if c["estado"] not in ("guion", "error", "producido"):
        raise HTTPException(409, f"el capítulo está {c['estado']}; primero el guion aprobado")
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "ya hay una tarea de esta serie corriendo")
    args = ["-m", "h3pipeline.app.serie_tarea", "producir", slug, str(n), "--hasta", p.hasta, "--motor", p.motor] + (["--rehacer"] if p.rehacer else [])
    return {"tarea": tareas.lanzar(f"producir el capítulo {n}", args, _slug_serie(slug)).a_dict()}


@app.post("/api/series/{slug}/guiones")
def serie_guiones(slug: str):
    """Aprueba todos los propuestos y escribe los guiones que falten (sólo GPT)."""
    s = _serie_o_404(slug)
    if not any(c["estado"] in ("propuesto", "aprobado", "error") and len(c.get("guion") or "") < 40 for c in s["capitulos"]):
        raise HTTPException(409, "no hay capítulos sin guion")
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "ya hay una tarea de esta serie corriendo")
    args = ["-m", "h3pipeline.app.serie_tarea", "guiones", slug]
    return {"tarea": tareas.lanzar("aprobar todo y escribir los guiones", args, _slug_serie(slug)).a_dict()}


@app.post("/api/series/{slug}/masa")
def serie_masa(slug: str, p: PedidoProducir):
    """Producción en masa: aprueba, escribe guiones, produce y encola todo lo que
    no esté descartado; con `cola: true` además enciende la máquina y genera
    (alquila: por eso confirma explícito)."""
    s = _serie_o_404(slug)
    if not p.confirmar:
        raise HTTPException(400, "hace falta confirmar: true (gasta GPT, voz e imágenes; con cola, también GPU)")
    if not any(c["estado"] in ("propuesto", "aprobado", "guion", "error", "producido") for c in s["capitulos"]):
        raise HTTPException(409, "no hay capítulos")
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "ya hay una tarea de esta serie corriendo")
    if p.cola and (tareas.corriendo("_cola") or tareas.corriendo("_maquina")):
        raise HTTPException(409, "la cola o la máquina ya tienen una tarea corriendo")
    args = ["-m", "h3pipeline.app.serie_tarea", "masa", slug, "--motor", p.motor] + ([] if p.cola else ["--sin-cola"]) + ([] if p.apagar else ["--no-apagar"])
    return {"tarea": tareas.lanzar("producción en masa", args, _slug_serie(slug)).a_dict()}


@app.post("/api/series/{slug}/capitulos/{n}/dialogos")
def serie_capitulo_dialogos(slug: str, n: int, p: PedidoProducir):
    """Largo narrado ya producido: las citas cortas las dicen los personajes en
    cámara (planos nuevos con dibujos ya hechos; la cola genera sólo esos y se
    rehace el máster). Alquila: confirmar explícito."""
    _serie_o_404(slug)
    if not p.confirmar:
        raise HTTPException(400, "hace falta confirmar: true (alquila la máquina para los planos de diálogo)")
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "ya hay una tarea de esta serie corriendo")
    if p.cola and (tareas.corriendo("_cola") or tareas.corriendo("_maquina")):
        raise HTTPException(409, "la cola o la máquina ya tienen una tarea corriendo")
    args = ["-m", "h3pipeline.app.serie_tarea", "dialogos", slug, str(n)] + ([] if p.cola else ["--sin-cola"]) + ([] if p.apagar else ["--no-apagar"])
    return {"tarea": tareas.lanzar("diálogos de los personajes", args, _slug_serie(slug)).a_dict()}


@app.post("/api/series/{slug}/producir-aprobados")
def serie_producir_aprobados(slug: str, p: PedidoProducir):
    s = _serie_o_404(slug)
    if not p.confirmar:
        raise HTTPException(400, "hace falta confirmar: true (gasta GPT, voz e imágenes)")
    if not any(c["estado"] == "guion" for c in s["capitulos"]):
        raise HTTPException(409, "no hay capítulos con guion aprobado")
    if tareas.corriendo(_slug_serie(slug)):
        raise HTTPException(409, "ya hay una tarea de esta serie corriendo")
    args = ["-m", "h3pipeline.app.serie_tarea", "producir-aprobados", slug, "--motor", p.motor]
    return {"tarea": tareas.lanzar("producir los aprobados", args, _slug_serie(slug)).a_dict()}


@app.get("/api/series/{slug}/archivo/{carpeta}/{nombre}")
def serie_archivo(slug: str, carpeta: str, nombre: str):
    if carpeta not in ("assets", "refs"):
        raise HTTPException(404)
    f = series.carpeta(slug) / carpeta / Path(nombre).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(str(f), filename=f.name)


# ─────────────────────────────────────────────────────── REMASTERIZAR (SD → 4K)
# Otra máquina (1×A100 80 GB) y otro modelo (FlashVSR). Nada de acá toca la
# 4×5090 de H3. Los pasos largos son tareas con slug `_remaster`.

@app.get("/api/remaster")
def remaster_estado():
    return {"trabajos": remaster.refrescar(), "maquina": remaster.maquina_dict(), "saldo": _saldo(),
            "ocupada": remaster.ocupada(),
            "tarea": next((t.a_dict(lineas=6) for t in tareas.corriendo("_remaster")), None)}


class OrigenRemaster(BaseModel):
    nombre: str = ""
    b64: str | None = None            # el archivo subido desde el navegador
    ruta: str | None = None           # o una ruta en este servidor (másters de varios GB)
    drive: str | None = None          # o un link de Google Drive (se baja con gdown, como tarea)


@app.post("/api/remaster/origen")
def remaster_origen(o: OrigenRemaster):
    try:
        if o.drive:
            t = remaster.nuevo_origen_drive(o.drive)
            if tareas.corriendo("_remaster"):
                remaster.actualizar(t["id"], estado="error", nota="hay otra tarea de remaster corriendo; tocá «reintentar descarga» cuando termine")
                return t
            tareas.lanzar("bajar de Drive", ["-m", "h3pipeline.app.remasterizar", "descargar", t["id"]], "_remaster")
            return t
        return remaster.nuevo_origen(o.nombre, o.b64, o.ruta)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"no pude analizar el video: {e}")


@app.post("/api/remaster/{tid}/descargar")
def remaster_descargar(tid: str):
    """Reintenta (retoma) la bajada de Drive de un trabajo."""
    try:
        t = remaster.trabajo(tid)
    except KeyError:
        raise HTTPException(404, "no existe ese trabajo")
    if not t.get("drive"):
        raise HTTPException(409, "este trabajo no vino de Drive")
    if tareas.corriendo("_remaster"):
        raise HTTPException(409, "ya hay una tarea de remaster corriendo")
    remaster.actualizar(tid, estado="descargando", nota="")
    return {"tarea": tareas.lanzar("bajar de Drive", ["-m", "h3pipeline.app.remasterizar", "descargar", tid], "_remaster").a_dict()}


class OpcionesRemaster(BaseModel):
    inicio: float = 0.0
    fin: float | None = None
    recorte: str = ""
    desentrelazar: bool = True
    campo: str = "auto"
    variante: str = "full"


@app.post("/api/remaster/{tid}/preparar")
def remaster_preparar(tid: str, o: OpcionesRemaster):
    """Guarda las opciones y lanza la preparación local (ffmpeg): gratis."""
    try:
        remaster.fijar_opciones(tid, **o.model_dump())
    except KeyError:
        raise HTTPException(404, "no existe ese trabajo")
    except (ValueError, RuntimeError) as e:
        raise HTTPException(422, str(e))
    if tareas.corriendo("_remaster"):
        raise HTTPException(409, "ya hay una tarea de remaster corriendo")
    remaster.actualizar(tid, estado="preparando", nota="")
    return {"tarea": tareas.lanzar("preparar fuente", ["-m", "h3pipeline.app.remasterizar", "preparar", tid], "_remaster").a_dict()}


@app.get("/api/remaster/{tid}/estimacion")
def remaster_estimacion(tid: str):
    try:
        return remaster.estimacion(tid)
    except KeyError:
        raise HTTPException(404, "no existe ese trabajo")
    except Exception as e:
        raise HTTPException(502, f"Vast no contestó: {e}")


class CorrerRemaster(BaseModel):
    confirmar: bool = False
    oferta: int | None = None


@app.post("/api/remaster/{tid}/correr")
def remaster_correr(tid: str, c: CorrerRemaster):
    if not c.confirmar:
        raise HTTPException(400, "hace falta confirmar: true (esto alquila una A100 y cobra)")
    try:
        t = remaster.trabajo(tid)
    except KeyError:
        raise HTTPException(404, "no existe ese trabajo")
    if t["estado"] not in ("preparado", "error", "listo"):
        raise HTTPException(409, f"el trabajo está en estado {t['estado']}")
    if not t.get("fuente"):
        raise HTTPException(409, "primero prepará la fuente")
    if tareas.corriendo("_remaster") or remaster.ocupada():
        raise HTTPException(409, "ya hay un remaster en curso")
    m = remaster.sincronizar_maquina()
    if m.get("fase") not in ("apagada", "fallo"):
        raise HTTPException(409, f"ya hay una A100 en fase {m['fase']}; apagala primero")
    args = ["-m", "h3pipeline.app.remasterizar", "correr", tid] + ([str(c.oferta)] if c.oferta else [])
    remaster.actualizar(tid, estado="alquilando", nota="", qc=[], salidas={})
    return {"tarea": tareas.lanzar("remasterizar en A100", args, "_remaster").a_dict()}


@app.post("/api/remaster/{tid}/bajar")
def remaster_bajar(tid: str):
    if tareas.corriendo("_remaster"):
        raise HTTPException(409, "ya hay una tarea de remaster corriendo")
    return {"tarea": tareas.lanzar("bajar el 4K", ["-m", "h3pipeline.app.remasterizar", "bajar", tid], "_remaster").a_dict()}


@app.post("/api/remaster/{tid}/uhd")
def remaster_uhd(tid: str):
    try:
        t = remaster.trabajo(tid)
    except KeyError:
        raise HTTPException(404, "no existe ese trabajo")
    if not (t.get("salidas") or {}).get("4k"):
        raise HTTPException(409, "todavía no hay 4K bajado")
    return {"tarea": tareas.lanzar("versión UHD", ["-m", "h3pipeline.app.remasterizar", "uhd", tid], "_remaster").a_dict()}


@app.delete("/api/remaster/{tid}")
def remaster_borrar(tid: str):
    try:
        remaster.borrar(tid)
    except KeyError:
        raise HTTPException(404, "no existe ese trabajo")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.post("/api/remaster/maquina/apagar")
def remaster_apagar(a: Apagado):
    if not a.confirmar:
        raise HTTPException(400, "hace falta confirmar: true")
    for t in tareas.corriendo("_remaster"):
        tareas.matar(t.id)
    try:
        return remaster.apagar(log=lambda *_: None)
    except Exception as ex:
        raise HTTPException(502, f"no pude destruir: {ex}")


@app.get("/api/remaster/archivo/{carpeta}/{nombre}")
def remaster_archivo(carpeta: str, nombre: str):
    if carpeta not in ("hojas", "fuentes", "salidas", "qc", "logs"):
        raise HTTPException(404)
    f = remaster.DIR / carpeta / Path(nombre).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(str(f), filename=f.name)


@app.post("/api/libre/{tid}/otra-vez")
def libre_otra_vez(tid: str):
    """Turno nuevo con la misma imagen de uno terminado (para iterar el prompt)."""
    try:
        return libre.duplicar(tid)
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

BIBLIOTECA = MIS / "_musica"      # las pistas de los music videos, independientes de la escena


class Musica(BaseModel):
    slug: str = "_musica"           # "_musica" = la biblioteca; o el slug de un proyecto
    tipo: str = ""                  # descripción libre: «lento para estudiar, sin batería marcada…»
    duracion: float = 90.0          # 30 s a 30 min; más de 5 min se compone en piezas unidas con fundido a silencio
    nombre: str = "musica"
    genero: str = ""                # clave de componer.GENEROS ("" = sólo la descripción)
    loopeable: bool = True          # instrumental sin intro ni final (para el loop de video)
    con_letra: bool = False
    letra: str = ""
    idioma_letra: str = "es"
    voz_letra: str = "femenina"     # femenina | masculina | duo | coro


def _pista_dict(f: Path, url: str) -> dict:
    try:
        dur = montaje.duracion(f)
    except Exception:
        dur = None
    meta = {}
    j = f.with_suffix(".json")
    if j.exists():
        try:
            meta = json.loads(j.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {"archivo": f.name, "ruta": str(f), "dur": round(dur, 1) if dur else None, "url": url,
            "genero": meta.get("genero"), "con_letra": meta.get("con_letra"), "piezas": meta.get("piezas"),
            "tipo": meta.get("tipo"), "creado": f.stat().st_mtime}


@app.get("/api/musica/biblioteca")
def biblioteca():
    BIBLIOTECA.mkdir(parents=True, exist_ok=True)
    fs = sorted(list(BIBLIOTECA.glob("*.mp3")) + list(BIBLIOTECA.glob("*.wav")), key=lambda f: f.stat().st_mtime, reverse=True)
    return {"pistas": [_pista_dict(f, f"/api/musica/archivo/{f.name}") for f in fs],
            "tareas": [t.a_dict(lineas=3) for t in tareas.corriendo("_musica")]}


@app.get("/api/musica/archivo/{nombre}")
def musica_archivo(nombre: str):
    f = BIBLIOTECA / Path(nombre).name
    if not f.exists() or f.suffix.lower() not in (".mp3", ".wav"):
        raise HTTPException(404)
    return FileResponse(str(f), filename=f.name)


class PistaSubida(BaseModel):
    nombre: str
    b64: str                        # el archivo (mp3 o wav), base64 con o sin prefijo data:


@app.post("/api/musica/subir")
def subir_pista(p: PistaSubida):
    """Tu propia pista a la biblioteca (la que hiciste afuera o ya tenías)."""
    import base64
    BIBLIOTECA.mkdir(parents=True, exist_ok=True)
    ext = Path(p.nombre).suffix.lower()
    if ext not in (".mp3", ".wav"):
        raise HTTPException(422, "sólo mp3 o wav")
    b = p.b64.split(",", 1)[1] if "," in p.b64[:64] else p.b64
    base = re.sub(r"[^a-z0-9-]+", "-", Path(p.nombre).stem.lower()).strip("-") or "pista"
    f = BIBLIOTECA / f"{base}{ext}"
    n = 2
    while f.exists():
        f = BIBLIOTECA / f"{base}-{n}{ext}"
        n += 1
    f.write_bytes(base64.b64decode(b))
    return _pista_dict(f, f"/api/musica/archivo/{f.name}")


@app.post("/api/musica/componer")
def componer(m: Musica):
    if m.slug == "_musica":
        BIBLIOTECA.mkdir(parents=True, exist_ok=True)
        c = BIBLIOTECA
    else:
        c = _carpeta(m.slug)
    if not m.tipo.strip() and not m.genero:
        raise HTTPException(422, "elegí un género o describí la música")
    if m.con_letra and len(m.letra.strip()) < 10:
        raise HTTPException(422, "marcaste «con letra» pero no pegaste la letra")
    if not 30 <= m.duracion <= 1800:
        raise HTTPException(422, "la duración va de 30 segundos a 30 minutos")
    if tareas.corriendo(m.slug):
        raise HTTPException(409, "ya hay una composición en marcha; esperá a que termine")
    pedido = {"slug": m.slug, "tipo": m.tipo, "duracion": m.duracion, "genero": m.genero,
              "loopeable": m.loopeable, "con_letra": m.con_letra, "letra": m.letra,
              "idioma_letra": m.idioma_letra, "voz_letra": m.voz_letra,
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
