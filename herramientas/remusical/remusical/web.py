# -*- coding: utf-8 -*-
"""
ReMusical web: conectás tu Google Drive, navegás carpeta por carpeta, elegís uno o
varios videos y se musicalizan solos. El resultado va a una carpeta `re-musical/`
creada DENTRO de la carpeta donde estaban los videos, con el mismo nombre y el
prefijo `re-musical`.

Sola:              python -m remusical.web        →  http://localhost:8765
Dentro del portal: el portal hace  app.mount("/remusical", remusical.web.app)

DOS MODOS (REMUSICAL_MODO):
  local      el procesamiento corre en esta misma máquina (importa el motor: torch, etc.)
  replicate  esta web sólo ORQUESTA: manda el trabajo a un contenedor en Replicate, que
             baja el video de Drive, procesa en GPU y sube el resultado a Drive.
             El video NUNCA pasa por este servidor → alcanza con 512 MB (Render Starter).

★★★ CONTRA EL GASTO SIN FIN EN REPLICATE (un modelo privado cobra cada segundo que la
instancia está viva: setup, espera, ejecución, y también si falla o se cuelga).
Ocho cortes, cada uno independiente de los otros:
  1. `Cancel-After` al crear la predicción: Replicate la cancela solo a los N minutos,
     AUNQUE ESTA WEB ESTÉ CAÍDA. Es el corte que no depende de nada nuestro.
  2. watchdog dentro del contenedor (predict.py): mata el proceso a los MAX_MIN.
  3. tope de trabajos simultáneos (MAX_SIMULTANEOS).
  4. tope de trabajos por día (MAX_POR_DIA).
  5. no se envía dos veces el mismo video mientras uno está en curso.
  6. el sondeo tiene fin: si pasa el límite o Replicate no responde, se CANCELA la
     predicción antes de darla por perdida. Nunca "error y que siga corriendo".
  7. al arrancar, la web se vuelve a enganchar a las predicciones que dejó en curso
     (no las abandona corriendo sin nadie que las mire).
  8. botón de pánico: cancela TODO lo que esté corriendo en la cuenta, y un indicador
     en vivo de cuántas instancias hay activas y cuánto cuestan por minuto.
Y lo que no es código: min_instances = 0 SIEMPRE, saldo prepago chico, sin auto-recarga.
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path
from queue import Queue

for _s in (sys.stdout, sys.stderr):          # consola cp1252 de Windows
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests

from . import config as C
from . import drive_io

AQUI = Path(__file__).resolve().parent
ESTATICO = AQUI / "static"


# ---------------------------------------------------------------- config
def _cargar_env():
    for p in (C.RAIZ / ".env", C.FOTON / "dubai_v2" / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
_cargar_env()

MODO = os.getenv("REMUSICAL_MODO", "local").lower()
PUERTO = int(os.getenv("REMUSICAL_PUERTO", os.getenv("PORT", "8765")))
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REPLICATE_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
REPLICATE_MODEL = os.getenv("REPLICATE_MODEL", "yamilpintos/remusical")
REPLICATE_API = os.getenv("REPLICATE_API", "https://api.replicate.com/v1")   # sobreescribible: los tests apuntan a un Replicate falso

# --- los topes ---
MAX_MIN = int(os.getenv("REMUSICAL_MAX_MIN", "40"))            # el mismo que el watchdog del contenedor
CANCEL_AFTER = f"{MAX_MIN + 5}m"                               # Replicate corta solo un poco después
SONDEO_MAX_S = (MAX_MIN + 10) * 60                             # y la web deja de mirar un poco después
MAX_SIMULTANEOS = int(os.getenv("REMUSICAL_MAX_SIMULTANEOS", "3"))
MAX_POR_DIA = int(os.getenv("REMUSICAL_MAX_POR_DIA", "20"))
USD_POR_S_GPU = float(os.getenv("REMUSICAL_USD_POR_S_GPU", "0.000975"))   # L40S

SCOPES = ["https://www.googleapis.com/auth/drive",
          "https://www.googleapis.com/auth/userinfo.email", "openid"]
if not os.getenv("RENDER"):                                    # en Render hay https de verdad
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

TRABAJOS_JSON = C.TRABAJO / "trabajos_web.json"

app = FastAPI(title="ReMusical")

# La DEMO: clips cortos + demo.json con los datos reales de una corrida. No necesita
# credenciales: es lo primero que ve alguien que entra sin haber configurado nada.
from fastapi.staticfiles import StaticFiles
if (ESTATICO / "demo").exists():
    app.mount("/demo", StaticFiles(directory=str(ESTATICO / "demo")), name="demo")

# El selector de TANDAS (elegir una serie de Drive y mandarla a Vast) vive en su propio
# módulo: usa cuenta de servicio + bucket, que es otro contrato de seguridad que el de
# esta web (que usa el token OAuth del usuario). Si falta una dependencia, la web
# arranca igual sin esa sección.
try:
    from .tandas_web import router as router_tandas
    app.include_router(router_tandas)
    TANDAS = True
except Exception as _e:
    print(f"  (sin sección de tandas: {type(_e).__name__}: {_e})")
    TANDAS = False

# ---------------------------------------------------------------- sesiones (en memoria)
_sesiones: dict[str, dict] = {}


def _callback_url(req: Request) -> str:
    forzada = os.getenv("REMUSICAL_URL")
    base = forzada.rstrip("/") if forzada else str(req.base_url).rstrip("/") + req.scope.get("root_path", "")
    return base + "/auth/callback"


def _sesion(req: Request) -> dict:
    tok = req.cookies.get("rm_sesion")
    if not tok or tok not in _sesiones or "creds" not in _sesiones[tok]:
        raise HTTPException(401, "no conectado")
    return _sesiones[tok]


def _creds_a_dict(c: Credentials) -> dict:
    return dict(token=c.token, refresh_token=c.refresh_token, token_uri=c.token_uri,
                client_id=c.client_id, client_secret=c.client_secret, scopes=list(c.scopes or []))


def _creds(s: dict, forzar_refresh: bool = False) -> Credentials:
    c = Credentials(**s["creds"])
    if (c.expired or forzar_refresh) and c.refresh_token:
        c.refresh(google.auth.transport.requests.Request())
        s["creds"] = _creds_a_dict(c)
    return c


def _drive(s: dict):
    return drive_io.drive_con_creds(_creds(s))


def _flow(req: Request, state=None) -> Flow:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(500, "faltan GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET en .env")
    cb = _callback_url(req)
    cfg = {"web": {"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
                   "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                   "token_uri": "https://oauth2.googleapis.com/token",
                   "redirect_uris": [cb]}}
    f = Flow.from_client_config(cfg, scopes=SCOPES, state=state)
    f.redirect_uri = cb
    return f


# ---------------------------------------------------------------- rutas
@app.get("/")
def index():
    return FileResponse(str(ESTATICO / "index.html"))


@app.get("/api/config")
def api_config(req: Request):
    return dict(google_configurado=bool(CLIENT_ID and CLIENT_SECRET), callback=_callback_url(req),
                modo=MODO, replicate_configurado=bool(REPLICATE_TOKEN) if MODO == "replicate" else None,
                tandas=TANDAS,
                limites=dict(max_min=MAX_MIN, max_simultaneos=MAX_SIMULTANEOS, max_por_dia=MAX_POR_DIA))


@app.get("/auth/login")
def login(req: Request):
    f = _flow(req)
    url, state = f.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    tok = secrets.token_urlsafe(24)
    _sesiones[tok] = dict(state=state)
    r = RedirectResponse(url)
    r.set_cookie("rm_sesion", tok, httponly=True, samesite="lax", secure=bool(os.getenv("RENDER")))
    return r


@app.get("/auth/callback")
def callback(req: Request):
    raiz = req.scope.get("root_path", "") or "/"
    tok = req.cookies.get("rm_sesion")
    s = _sesiones.get(tok or "")
    if not s:
        return RedirectResponse(raiz)
    f = _flow(req, state=s.get("state"))
    f.fetch_token(authorization_response=str(req.url).replace("http://", "https://", 1)
                  if os.getenv("RENDER") else str(req.url))
    s["creds"] = _creds_a_dict(f.credentials)
    try:
        info = build("oauth2", "v2", credentials=f.credentials, cache_discovery=False).userinfo().get().execute()
        s["email"] = info.get("email", "")
        s["nombre"] = info.get("name", "")
    except Exception:
        s["email"] = s["nombre"] = ""
    return RedirectResponse(raiz if raiz.endswith("/") else raiz + "/")


@app.post("/auth/logout")
def logout(req: Request):
    _sesiones.pop(req.cookies.get("rm_sesion") or "", None)
    r = JSONResponse(dict(ok=True))
    r.delete_cookie("rm_sesion")
    return r


@app.get("/api/me")
def me(req: Request):
    s = _sesiones.get(req.cookies.get("rm_sesion") or "")
    if not s or "creds" not in s:
        return dict(conectado=False)
    return dict(conectado=True, email=s.get("email", ""), nombre=s.get("nombre", ""))


@app.get("/api/carpeta")
def carpeta(req: Request, id: str = "root"):
    s = _sesion(req)
    d = _drive(s)
    campos = ("nextPageToken, files(id, name, mimeType, size, thumbnailLink, parents, "
              "videoMediaMetadata(durationMillis), modifiedTime)")
    q = "sharedWithMe = true and trashed = false" if id == "compartidos" else f"'{id}' in parents and trashed = false"
    items, page = [], None
    while True:
        r = d.files().list(q=q, fields=campos, pageSize=200, pageToken=page, orderBy="folder,name",
                           supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        items += r.get("files", [])
        page = r.get("nextPageToken")
        if not page:
            break
    carpetas = [dict(id=f["id"], nombre=f["name"]) for f in items
                if f["mimeType"] == "application/vnd.google-apps.folder"]
    videos = []
    for f in items:
        if f["mimeType"].startswith("video/"):
            vm = f.get("videoMediaMetadata") or {}
            videos.append(dict(id=f["id"], nombre=f["name"], tamano=int(f.get("size", 0) or 0),
                               duracion_s=int(vm.get("durationMillis", 0) or 0) / 1000,
                               miniatura=f.get("thumbnailLink"), padre=(f.get("parents") or [None])[0]))
    migas = []
    if id == "compartidos":
        migas = [dict(id="compartidos", nombre="Compartido conmigo")]
    else:
        cur = id
        while cur and cur != "root" and len(migas) < 12:
            m = d.files().get(fileId=cur, fields="id,name,parents", supportsAllDrives=True).execute()
            migas.insert(0, dict(id=m["id"], nombre=m["name"]))
            cur = (m.get("parents") or [None])[0]
        migas.insert(0, dict(id="root", nombre="Mi unidad"))
    return dict(id=id, migas=migas, carpetas=carpetas, videos=videos)


# ---------------------------------------------------------------- trabajos
_cola: Queue = Queue()
_trabajos: dict[str, dict] = {}
_lock = threading.Lock()
ACTIVOS = ("en cola", "procesando")


def _guardar_trabajos():
    C.TRABAJO.mkdir(parents=True, exist_ok=True)
    with _lock:
        TRABAJOS_JSON.write_text(json.dumps(list(_trabajos.values()), indent=1, ensure_ascii=False), encoding="utf-8")


def _activos() -> list[dict]:
    return [t for t in _trabajos.values() if t["estado"] in ACTIVOS]


def _de_hoy() -> int:
    hoy = date.today().isoformat()
    return sum(1 for t in _trabajos.values() if t["creado"].startswith(hoy))


@app.post("/api/musicalizar")
async def musicalizar(req: Request):
    s = _sesion(req)
    if MODO == "replicate" and not REPLICATE_TOKEN:
        raise HTTPException(500, "falta REPLICATE_API_TOKEN en el servidor")
    body = await req.json()
    ids = list(dict.fromkeys(body.get("videos", [])))            # sin repetidos
    completo = bool(body.get("separar_completo", False))
    if not ids:
        raise HTTPException(400, "no elegiste ningún video")

    # ---- topes (3, 4, 5) ----
    en_curso = {t["video_id"] for t in _activos()}
    repetidos = [v for v in ids if v in en_curso]
    if repetidos:
        raise HTTPException(409, f"{len(repetidos)} de esos videos ya está en curso; esperá a que termine")
    if len(_activos()) + len(ids) > MAX_SIMULTANEOS:
        raise HTTPException(429, f"tope de {MAX_SIMULTANEOS} trabajos a la vez (hay {len(_activos())} en curso). "
                                 f"Es una guarda de gasto: mandá menos o esperá.")
    if _de_hoy() + len(ids) > MAX_POR_DIA:
        raise HTTPException(429, f"tope de {MAX_POR_DIA} trabajos por día (van {_de_hoy()}). "
                                 f"Es una guarda de gasto; se puede subir con REMUSICAL_MAX_POR_DIA.")

    d = _drive(s)
    nuevos = []
    for vid in ids:
        f = drive_io.meta(d, vid)
        t = dict(id=uuid.uuid4().hex[:10], video_id=f["id"], nombre=f["name"],
                 padre=(f.get("parents") or ["root"])[0], tamano=int(f.get("size", 0) or 0),
                 separar_completo=completo, estado="en cola", etapa="", progreso=0.0,
                 log=[], creado=time.strftime("%Y-%m-%d %H:%M:%S"), usuario=s.get("email", ""),
                 carpeta_salida_id=None, salidas=[], informe=None, error=None,
                 replicate_id=None, replicate_url=None, inicio_ts=None)
        _trabajos[t["id"]] = t
        if MODO == "replicate":
            threading.Thread(target=_correr_replicate, args=(t, s), daemon=True).start()
        else:
            _cola.put((t["id"], dict(s)))
        nuevos.append(t["id"])
    _guardar_trabajos()
    return dict(trabajos=nuevos)


@app.get("/api/trabajos")
def trabajos(req: Request):
    s = _sesiones.get(req.cookies.get("rm_sesion") or "") or {}
    mail = s.get("email")
    lista = [dict(t, log=t["log"][-6:]) for t in _trabajos.values() if not mail or t.get("usuario") == mail]
    return dict(trabajos=sorted(lista, key=lambda t: t["creado"], reverse=True))


@app.post("/api/trabajos/{tid}/cancelar")
def cancelar(req: Request, tid: str):
    _sesion(req)
    t = _trabajos.get(tid)
    if not t:
        raise HTTPException(404, "no existe")
    if t["estado"] not in ACTIVOS:
        return dict(ok=True, estado=t["estado"])
    t["cancelar"] = True
    if t.get("replicate_url"):
        _cancelar_prediccion(t)
    t["estado"] = "cancelado"
    t["etapa"] = "cancelado por el usuario"
    _guardar_trabajos()
    return dict(ok=True, estado="cancelado")


# ---------------------------------------------------------------- común
ETAPAS = {"audio": "extrayendo audio", "mapa": "buscando la música", "separar": "separando voz y música",
          "generar": "componiendo música nueva", "montar": "montando", "guardas": "controlando",
          "exportar": "exportando", "listo": "subiendo a Drive", "bajando": "bajando de Drive",
          "subiendo": "subiendo a Drive"}


def _log_en(t: dict):
    def _l(msg: str):
        t["log"].append(str(msg))
        if len(t["log"]) > 400:
            del t["log"][:100]
        print(f"[{t['nombre']}] {msg}", flush=True)
    return _l


def _terminar(t: dict, estado_informe: str):
    t["estado"] = "listo" if estado_informe == "ENTREGABLE" else estado_informe.lower()
    t["etapa"] = "terminado"
    t["progreso"] = 1.0


# ---------------------------------------------------------------- modo REPLICATE
def _replicate(metodo: str, url: str, body: dict | None = None, headers: dict | None = None) -> dict:
    h = {"Authorization": f"Bearer {REPLICATE_TOKEN}", "Content-Type": "application/json"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Replicate HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")


def _cancelar_prediccion(t: dict) -> bool:
    """Best effort, y se reintenta: cancelar es lo que corta el gasto."""
    for _ in range(3):
        try:
            _replicate("POST", t["replicate_url"].rstrip("/") + "/cancel")
            _log_en(t)(f"predicción {t['replicate_id']} cancelada en Replicate")
            return True
        except Exception as e:
            _log_en(t)(f"no se pudo cancelar (reintento): {e}")
            time.sleep(3)
    return False


def _sondear(t: dict, url: str):
    """Mira la predicción hasta que termine. Con FIN: por tiempo, por errores seguidos,
    o por cancelación pedida. En cualquier salida anormal, cancela antes de rendirse."""
    log = _log_en(t)
    vistas = 0
    errores = 0
    inicio = t.get("inicio_ts") or time.time()
    p = None
    while True:
        time.sleep(5)
        if t.get("cancelar"):
            _cancelar_prediccion(t)
            raise RuntimeError("cancelado por el usuario")
        if time.time() - inicio > SONDEO_MAX_S:
            _cancelar_prediccion(t)
            raise RuntimeError(f"superó {SONDEO_MAX_S//60} min: cancelado para no seguir cobrando")
        try:
            p = _replicate("GET", url)
            errores = 0
        except Exception as e:
            errores += 1
            log(f"Replicate no responde ({errores}/6): {e}")
            if errores >= 6:
                _cancelar_prediccion(t)
                raise RuntimeError("Replicate no respondió 6 veces seguidas: cancelado por seguridad")
            continue
        for line in (p.get("logs") or "").splitlines()[vistas:]:
            vistas += 1
            if line.startswith("PROGRESO "):
                _, etapa, frac = line.split(" ", 2)
                t["etapa"] = ETAPAS.get(etapa, etapa)
                t["progreso"] = float(frac)
            elif line.startswith("LOG "):
                log(line[4:])
        if p["status"] in ("succeeded", "failed", "canceled"):
            return p


def _cerrar_prediccion(t: dict, p: dict):
    if p["status"] != "succeeded":
        raise RuntimeError(p.get("error") or f"predicción {p['status']}")
    out = p["output"] or {}
    inf = json.loads(out.get("informe") or "{}")
    t["informe"] = {k: inf.get(k) for k in ("estado", "duracion_s", "regiones_finales",
                                             "guardas", "creditos_eleven", "segundos")}
    t["carpeta_salida_id"] = out.get("carpeta_drive_id")
    t["salidas"] = out.get("salidas") or []
    m = p.get("metrics") or {}
    if m.get("predict_time"):
        t["gpu_s"] = round(float(m["predict_time"]), 1)
        t["usd_gpu"] = round(float(m["predict_time"]) * USD_POR_S_GPU, 3)
    _terminar(t, out.get("estado") or inf.get("estado", "REVISAR"))


def _correr_replicate(t: dict, s: dict):
    """Un hilo por trabajo. Crea la predicción CON Cancel-After y la sondea con fin."""
    log = _log_en(t)
    try:
        t["estado"] = "procesando"
        t["etapa"] = "enviando a Replicate"
        creds = _creds(s, forzar_refresh=True)          # token fresco: dura 1 h, el trabajo ~15-20 min
        body = {"input": {
            "drive_file_id": t["video_id"], "drive_parent_id": t["padre"],
            "access_token": creds.token,
            "eleven_api_key": os.getenv("ELEVENLABS_API_KEY", ""),
            "separar_completo": t["separar_completo"],
            "takes": int(os.getenv("REMUSICAL_TAKES", "3")),
        }}
        p = _replicate("POST", f"{REPLICATE_API}/models/{REPLICATE_MODEL}/predictions", body,
                       headers={"Cancel-After": CANCEL_AFTER})        # ★ corte 1: del lado de Replicate
        t["replicate_id"] = p["id"]
        t["replicate_url"] = p["urls"]["get"]
        t["inicio_ts"] = time.time()
        _guardar_trabajos()
        log(f"predicción {p['id']} creada (Replicate la cancela sola a los {CANCEL_AFTER})")
        p = _sondear(t, t["replicate_url"])
        _cerrar_prediccion(t, p)
    except Exception as e:
        if t["estado"] != "cancelado":
            t["estado"] = "error"
            t["error"] = f"{type(e).__name__}: {e}"
        log("ERROR " + traceback.format_exc()[-800:])
    finally:
        _guardar_trabajos()


def _reenganchar(t: dict):
    """★ corte 7: una predicción que quedó corriendo cuando la web se reinició no se
    abandona: se la vuelve a mirar (y si hace falta, se la cancela)."""
    log = _log_en(t)
    try:
        log("web reiniciada: me vuelvo a enganchar a la predicción")
        p = _sondear(t, t["replicate_url"])
        _cerrar_prediccion(t, p)
    except Exception as e:
        if t["estado"] != "cancelado":
            t["estado"] = "error"
            t["error"] = f"{type(e).__name__}: {e}"
    finally:
        _guardar_trabajos()


def _cargar_trabajos():
    if not TRABAJOS_JSON.exists():
        return
    for t in json.loads(TRABAJOS_JSON.read_text(encoding="utf-8")):
        _trabajos[t["id"]] = t
        if t["estado"] in ACTIVOS:
            if MODO == "replicate" and t.get("replicate_url") and REPLICATE_TOKEN:
                threading.Thread(target=_reenganchar, args=(t,), daemon=True).start()
            else:
                t["estado"] = "interrumpido"
_cargar_trabajos()


@app.get("/api/replicate/estado")
def replicate_estado(req: Request):
    """Cuántas predicciones tiene la CUENTA corriendo ahora y cuánto cuestan por minuto.
    Cuenta entera, no sólo esta web: si algo quedó corriendo de otro lado, acá se ve."""
    _sesion(req)
    if MODO != "replicate" or not REPLICATE_TOKEN:
        return dict(activo=False)
    try:
        r = _replicate("GET", f"{REPLICATE_API}/predictions")
    except Exception as e:
        return dict(activo=True, error=str(e))
    vivas = [p for p in r.get("results", []) if p.get("status") in ("starting", "processing")]
    return dict(activo=True, corriendo=len(vivas),
                usd_por_min=round(len(vivas) * USD_POR_S_GPU * 60, 3),
                ids=[p["id"] for p in vivas], modelo=REPLICATE_MODEL)


@app.post("/api/replicate/cancelar_todo")
def replicate_cancelar_todo(req: Request):
    """★ corte 8, el botón de pánico: cancela TODO lo que esté corriendo en la cuenta."""
    _sesion(req)
    if MODO != "replicate" or not REPLICATE_TOKEN:
        raise HTTPException(400, "no hay Replicate configurado")
    r = _replicate("GET", f"{REPLICATE_API}/predictions")
    canceladas, fallas = [], []
    for p in r.get("results", []):
        if p.get("status") in ("starting", "processing"):
            try:
                _replicate("POST", f"{REPLICATE_API}/predictions/{p['id']}/cancel")
                canceladas.append(p["id"])
            except Exception as e:
                fallas.append(f"{p['id']}: {e}")
    for t in _activos():
        t["cancelar"] = True
        t["estado"] = "cancelado"
        t["etapa"] = "cancelado (pánico)"
    _guardar_trabajos()
    return dict(canceladas=canceladas, fallas=fallas)


# ---------------------------------------------------------------- modo LOCAL
def _worker_local():
    from .orquestador import procesar            # importa el motor (torch…) sólo en este modo
    while True:
        tid, s = _cola.get()
        t = _trabajos.get(tid)
        if not t or t.get("cancelar"):
            continue
        log = _log_en(t)
        try:
            t["estado"] = "procesando"
            t["etapa"] = ETAPAS["bajando"]
            d = _drive(s)
            wdir = C.TRABAJO / "web" / tid
            local = wdir / t["nombre"]
            log(f"bajando {t['nombre']} ({t['tamano']/1e9:.2f} GB)")
            drive_io.bajar(d, t["video_id"], local, lambda f: t.__setitem__("progreso", 0.05 * f))

            def prog(etapa, f):
                t["etapa"] = ETAPAS.get(etapa, etapa)
                t["progreso"] = 0.05 + 0.85 * f
            inf = procesar(local, salida_dir=wdir / C.PREFIJO, separar_completo=t["separar_completo"],
                           log=log, progreso=prog)
            t["informe"] = {k: inf.get(k) for k in ("estado", "duracion_s", "regiones_finales",
                                                     "guardas", "creditos_eleven", "segundos")}
            t["etapa"] = ETAPAS["subiendo"]
            d = _drive(s)
            cid = drive_io.carpeta_salida(d, t["padre"])
            t["carpeta_salida_id"] = cid
            salidas = sorted((wdir / C.PREFIJO).glob("*"))
            for k, p in enumerate(salidas):
                log(f"subiendo {p.name}")
                fid = drive_io.subir(d, p, cid)
                t["salidas"].append(dict(nombre=p.name, id=fid))
                t["progreso"] = 0.90 + 0.10 * (k + 1) / len(salidas)
            _terminar(t, inf["estado"])
            try:
                local.unlink()
            except Exception:
                pass
        except Exception as e:
            t["estado"] = "error"
            t["error"] = f"{type(e).__name__}: {e}"
            log("ERROR " + traceback.format_exc()[-1200:])
        finally:
            _guardar_trabajos()
            _cola.task_done()


if MODO == "local":
    threading.Thread(target=_worker_local, daemon=True, name="remusical-worker").start()


def main():
    import uvicorn
    print(f"ReMusical [{MODO}] -> http://localhost:{PUERTO}")
    if not (CLIENT_ID and CLIENT_SECRET):
        print("  AVISO: faltan GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET; la página explica cómo crearlos")
    if MODO == "replicate":
        print(f"  Replicate: Cancel-After {CANCEL_AFTER} · máx {MAX_SIMULTANEOS} a la vez · máx {MAX_POR_DIA}/día"
              + ("" if REPLICATE_TOKEN else " · SIN TOKEN"))
    uvicorn.run(app, host="0.0.0.0", port=PUERTO, log_level="warning", proxy_headers=True,
                forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
