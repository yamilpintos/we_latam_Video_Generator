# -*- coding: utf-8 -*-
"""La GPU PROPIA de la app en vast.ai: se alquila sola cuando hace falta separar voz/fondo, se instala sola,
separa, y se apaga sola cuando queda ociosa. Sin depender de `dubai_v2` ni de la PC: corre igual en Render.

POR QUÉ. El modo "pistas" (voz doblada al nivel de la original + fondo original intacto, aprobado de oído) necesita
separar el original y el doblado. En CPU son ~15 min por minuto de película; en una RTX 4090, una película de 78 min
se separó en 26 min. Hasta el 22-sep la GPU se prendía a mano (`preparar_vast.py`) y se apagaba a mano: un olvido
cuesta USD 10 por día. Acá el ciclo de vida es del sistema, con topes.

CÓMO.
  asegurar(log)  →  si hay una instancia nuestra viva y lista, se usa; si está viva sin instalar, se instala;
                    si no hay, se ALQUILA (modo auto) y se instala (≈6-10 min: torch + audio-separator + pesos).
  separar(audio, out_dir, log)  →  sube el wav por SFTP, corre allá `sep_app.py` (el MISMO criterio de checkpoint
                    que el separador sellado del motor: `sep_replicate.separar_local`), baja las dos pistas, borra allá.
  vigilante      →  cada minuto: ociosa más de GPU_OCIO_MIN → se destruye; más de GPU_MAX_HORAS → se destruye
                    (si está separando, al terminar); registra las horas y los USD en el libro (ledger_gpu.jsonl).

★ GUARDAS DE GASTO (cada una independiente):
  1. sólo se alquila si la oferta cuesta ≤ GPU_MAX_USD_H
  2. tope de USD por día (GPU_USD_TOPE_DIA): pasado el tope NO se alquila y la app cae al modo "mezcla" y lo dice
  3. tope de horas por instancia (GPU_MAX_HORAS) aunque esté en uso
  4. ociosa GPU_OCIO_MIN minutos → destruida
  5. SÓLO se destruye la instancia con NUESTRA etiqueta (GPU_ETIQUETA) o nuestro id: nunca otra de la cuenta
     (el 22-sep `vast.py destruir --si` habría borrado una 5090 del usuario que trabajaba en otro proceso)
  6. al arrancar la web se ADOPTA una instancia nuestra que haya quedado viva (Render reinicia y pierde /tmp):
     entra al ciclo de ociosidad y se apaga sola
  7. DOBLAJE_GPU=manual: nunca alquila sola (sólo usa una que se prendió desde la web); DOBLAJE_GPU=off: no toca vast
  8. el PROCESO que alquiló la destruye al terminar (atexit), salvo DOBLAJE_GPU_MANTENER=1. ★ 26-sep: una prueba que
     llamó a media.separar con las credenciales de la PC alquiló una 4090 real y el proceso murió sin vigilante:
     habría quedado cobrando hasta que alguien mirara. Las pruebas corren con DOBLAJE_GPU=off (tests/__init__.py).

Credenciales: VAST_API_KEY y la clave ssh privada en VAST_SSH_KEY (texto con saltos o base64); sin esa variable,
~/.ssh/id_ed25519 (la PC). La pública se deriva de la privada, así que no hace falta el .pub.
"""
from __future__ import annotations

import atexit
import base64
import io
import json
import os
import threading
import time
import uuid
from datetime import date
from pathlib import Path

import requests

from . import config as C

API0 = "https://console.vast.ai/api/v0"
API1 = "https://console.vast.ai/api/v1"
# la imagen BASE de vast (trae sshd + python 3.11): con `nvidia/cuda` pelada el lanzador muere en bucle (6-sep)
IMAGEN = "vastai/base-image:cuda-12.4.1-cudnn-devel-ubuntu22.04-py311-2026-08-28"
REGISTRO = C.TRABAJO / "gpu_vast.json"              # nuestra instancia viva (id, host, port, dph, creada)
LEDGER = C.TRABAJO / "ledger_gpu.jsonl"             # alquileres y destrucciones con horas y USD
MARCA_LISTA = "/motor/LISTA"
SEP_REMOTO = "/motor/sep_app.py"
TOPE_SEP_S = 7200                                   # una separación (una película de 78 min tardó 26 min)
TOPE_INSTALAR_S = 2700
CKPT_PREF = "Vocals FT1"                            # el mismo preferido que sep_replicate (MODELO_DEFAULT)


class GpuError(RuntimeError):
    pass


# ── lo que corre ALLÁ ──────────────────────────────────────────────────────────────────────────
INSTALAR_SH = r"""#!/usr/bin/env bash
# La GPU de la app Doblaje: separador BS-RoFormer (audio-separator) listo para sep_app.py. Idempotente.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1 PYTHONIOENCODING=utf-8
if [ -f /motor/LISTA ]; then echo YA_LISTA; exit 0; fi
mkdir -p /motor /opt/sep_models
echo "== 1/4 apt (ffmpeg, libsndfile)"
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq --no-install-recommends ffmpeg libsndfile1 >/dev/null 2>&1 || true
echo "== 2/4 venv"
PYB=$(command -v python3.11 || command -v python3)
if [ ! -x /opt/venv/bin/python ]; then "$PYB" -m venv /opt/venv || true; fi
if [ -x /opt/venv/bin/python ]; then PY=/opt/venv/bin/python; else PY="$PYB"; fi
echo "$PY" > /motor/PY
"$PY" -m pip install -q --upgrade pip wheel setuptools
echo "== 3/4 torch CUDA + audio-separator (la misma versión que el motor: 0.44.3)"
"$PY" -m pip install -q torch torchaudio --index-url https://download.pytorch.org/whl/cu124
"$PY" -m pip install -q "audio-separator[gpu]==0.44.3" soundfile
if ! "$PY" -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
  echo "   torch quedó sin CUDA: reinstalo la pila cu124"
  "$PY" -m pip install -q --force-reinstall torch torchaudio --index-url https://download.pytorch.org/whl/cu124
fi
"$PY" - <<'EOF'
import torch
print("   torch", torch.__version__, "cuda", torch.version.cuda, "gpu", torch.cuda.is_available() and torch.cuda.get_device_name(0))
assert torch.cuda.is_available(), "NO HAY GPU"
EOF
echo "== 4/4 pesos del separador"
"$PY" /motor/sep_app.py --precargar
touch /motor/LISTA
echo INSTALADA
"""

SEP_PY = r'''# -*- coding: utf-8 -*-
"""Separador de la app en la GPU: audio-separator con el MISMO criterio de checkpoint que el separador sellado del
motor (sep_replicate.separar_local): preferido "Vocals FT1"; de no cargar, BS-RoFormer ep_317 / ep_368 / duality."""
import json, os, sys, time
from pathlib import Path
from audio_separator.separator import Separator

PREF = "Vocals FT1"
RED = ["model_bs_roformer_ep_317_sdr_12.9755.ckpt", "model_bs_roformer_ep_368_sdr_12.9628.ckpt",
       "melband_roformer_instvox_duality_v2.ckpt"]


def candidatos(sep):
    cand = []
    for arch, models in sep.list_supported_model_files().items():
        for nombre, info in models.items():
            f = info.get("filename") if isinstance(info, dict) else (info if isinstance(info, str) else "")
            if not f:
                continue
            b = (str(nombre) + " " + str(f)).lower()
            if PREF.lower().replace(" ", "") in b.replace(" ", "").replace("_", "").replace("-", ""):
                cand.append(f)
    return cand + RED


def cargar(sep):
    for m in candidatos(sep):
        try:
            sep.load_model(model_filename=m)
            return m
        except Exception as e:
            print("  fallo", m, str(e)[:100], flush=True)
    raise SystemExit("no se pudo cargar ningun modelo de separacion")


if sys.argv[1] == "--precargar":
    print("MODELO_LOCAL:", cargar(Separator(model_file_dir="/opt/sep_models")), flush=True)
    sys.exit(0)

entrada, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
t0 = time.time()
sep = Separator(model_file_dir="/opt/sep_models", output_dir=str(out))
m = cargar(sep)
salidas = sep.separate(str(entrada))
voz = next(iter(sorted(out.glob("*Vocals*.wav"))), None)
fondo = next(iter(sorted(out.glob("*Instrumental*.wav"))), None)
if not (voz and fondo):
    raise SystemExit("faltan stems: " + json.dumps(salidas))
os.replace(voz, out / "vocals_clean.wav")
os.replace(fondo, out / "music_effects.wav")
(out / "_sep_meta.json").write_text(json.dumps(dict(backend="gpu_vast", checkpoint=m, segundos=round(time.time() - t0, 1))))
print("MODELO_LOCAL:", m, "SEGUNDOS:", round(time.time() - t0, 1), flush=True)
'''


# ── estado en memoria (lo lee la web sin bloquear) ─────────────────────────────────────────────
_lock = threading.RLock()
_estado = dict(fase="apagada", detalle="", usando=0, ultimo_uso=0.0, error=None, vencida=False)
_vigilante_iniciado = False


def _log(log, m):
    if log:
        try:
            log(m)
        except Exception:                                   # una consola cp1252 no puede frenar una destrucción
            try:
                log(m.encode("ascii", "replace").decode())
            except Exception:
                pass


_atexit_puesto = False


def _destruir_al_salir():
    if C.GPU_MANTENER:
        return
    try:
        d = destruir("el proceso que la alquiló terminó")
        if d:
            print(f"[gpu] instancia {d['id']} destruida al salir: {d['horas']} h = USD {d['usd']}", flush=True)
    except Exception as e:
        print("[gpu] al salir no pude destruir la instancia: " + str(e)[:200] + " -> python saldo.py", flush=True)


def _asegurar_atexit():
    global _atexit_puesto
    if not _atexit_puesto:
        _atexit_puesto = True
        atexit.register(_destruir_al_salir)


def _hoy():
    return date.today().isoformat()


# ── credenciales ───────────────────────────────────────────────────────────────────────────────
def _clave_privada() -> Path | None:
    txt = (C.VAST_SSH_KEY or "").strip()
    if txt:
        if "PRIVATE KEY" not in txt:                   # base64 de la clave entera
            try:
                txt = base64.b64decode(txt).decode("utf-8")
            except Exception:
                return None
        txt = txt.replace("\\n", "\n")
        p = C.TRABAJO / ".ssh" / "id_app"
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() or p.read_text(encoding="utf-8") != txt + "\n":
            p.write_text(txt + "\n", encoding="utf-8")
            try:
                os.chmod(p, 0o600)
            except Exception:
                pass
        return p
    p = Path.home() / ".ssh" / "id_ed25519"
    return p if p.exists() else None


def configurada() -> bool:
    return bool(C.VAST_API_KEY) and _clave_privada() is not None and C.GPU_MODO != "off"


def _pkey():
    import paramiko
    p = _clave_privada()
    if not p:
        raise GpuError("no hay clave ssh (VAST_SSH_KEY o ~/.ssh/id_ed25519)")
    for cls in (paramiko.Ed25519Key, paramiko.RSAKey, paramiko.ECDSAKey):
        try:
            return cls.from_private_key_file(str(p))
        except Exception:
            continue
    raise GpuError("la clave ssh no se pudo leer (¿ed25519/rsa sin passphrase?)")


def _clave_publica() -> str:
    k = _pkey()
    return f"{k.get_name()} {k.get_base64()} doblaje-app"


# ── API de vast ────────────────────────────────────────────────────────────────────────────────
def _api(metodo: str, ruta: str, base: str = API0, **kw) -> dict:
    if not C.VAST_API_KEY:
        raise GpuError("falta VAST_API_KEY")
    r = requests.request(metodo, base + ruta, headers={"Authorization": "Bearer " + C.VAST_API_KEY, "Accept": "application/json"},
                         timeout=kw.pop("timeout", 60), **kw)
    if not r.ok:
        raise GpuError(f"vast {metodo} {ruta}: HTTP {r.status_code}: {r.text[:300]}")
    try:
        return r.json() if r.text else {}
    except ValueError:
        return {}


def instancias_vivas() -> list[dict]:
    try:
        d = _api("GET", "/instances/", base=API1)
    except GpuError:
        d = _api("GET", "/instances/")
    return d.get("instances", d if isinstance(d, list) else [])


def _registro() -> dict | None:
    try:
        return json.loads(REGISTRO.read_text(encoding="utf-8"))
    except Exception:
        return None


def _guardar_registro(d: dict | None):
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    if d is None:
        REGISTRO.unlink(missing_ok=True)
    else:
        REGISTRO.write_text(json.dumps(d, indent=1), encoding="utf-8")


def mia(vivas: list[dict] | None = None) -> dict | None:
    """NUESTRA instancia viva: la registrada, o una con nuestra etiqueta (quedó de una web anterior). Nunca otra."""
    vivas = instancias_vivas() if vivas is None else vivas
    reg = _registro() or {}
    for i in vivas:
        if reg.get("id") == i.get("id") or i.get("label") == C.GPU_ETIQUETA:
            return i
    return None


def _de_instancia(i: dict) -> dict:
    return dict(id=i["id"], host=i.get("ssh_host"), port=int(i.get("ssh_port") or 0), dph=i.get("dph_total"),
                gpu=i.get("gpu_name"), inicio=float(i.get("start_date") or time.time()), etiqueta=i.get("label"))


# ── ssh (paramiko: Render no trae el cliente ssh) ──────────────────────────────────────────────
def _cliente(host: str, port: int):
    import paramiko
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(host, port=port, username="root", pkey=_pkey(), timeout=30, banner_timeout=60, auth_timeout=60,
              allow_agent=False, look_for_keys=False)
    return c


def _ssh(host: str, port: int, cmd: str, timeout: float) -> tuple[int, str, str]:
    c = _cliente(host, port)
    try:
        t = c.get_transport()
        t.set_keepalive(30)
        ch = t.open_session()
        ch.settimeout(timeout)
        ch.exec_command("bash -lc " + _q(cmd))
        out, err = io.BytesIO(), io.BytesIO()
        t0 = time.time()
        while True:
            while ch.recv_ready():
                out.write(ch.recv(65536))
            while ch.recv_stderr_ready():
                err.write(ch.recv_stderr(65536))
            if ch.exit_status_ready():
                break
            if time.time() - t0 > timeout:
                ch.close()
                raise GpuError(f"tope de {timeout:.0f} s en: {cmd[:60]}")
            time.sleep(0.5)
        while ch.recv_ready():
            out.write(ch.recv(65536))
        while ch.recv_stderr_ready():
            err.write(ch.recv_stderr(65536))
        return ch.recv_exit_status(), out.getvalue().decode("utf-8", "replace"), err.getvalue().decode("utf-8", "replace")
    finally:
        c.close()


def _q(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _subir(host: str, port: int, local: Path | bytes, remoto: str):
    c = _cliente(host, port)
    try:
        s = c.open_sftp()
        try:
            if isinstance(local, bytes):
                with s.open(remoto, "wb") as f:
                    f.write(local)
            else:
                s.put(str(local), remoto)
        finally:
            s.close()
    finally:
        c.close()


def _bajar(host: str, port: int, remoto: str, local: Path):
    local.parent.mkdir(parents=True, exist_ok=True)
    c = _cliente(host, port)
    try:
        s = c.open_sftp()
        try:
            s.get(remoto, str(local))
        finally:
            s.close()
    finally:
        c.close()


# ── libro de USD ───────────────────────────────────────────────────────────────────────────────
def _ledger(**ev):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    ev.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def _leer_ledger() -> list[dict]:
    if not LEDGER.exists():
        return []
    out = []
    for l in LEDGER.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


def usd_hoy(viva: dict | None = None) -> float:
    """USD de hoy: lo cerrado en el libro (destrucciones de hoy) + lo que lleva la instancia viva."""
    hoy = _hoy()
    total = sum(float(e.get("usd") or 0) for e in _leer_ledger() if e.get("tipo") == "destruida" and str(e.get("ts", "")).startswith(hoy))
    if viva:
        horas = (time.time() - float(viva.get("start_date") or time.time())) / 3600
        total += horas * float(viva.get("dph_total") or 0)
    return round(total, 3)


# ── alquilar / instalar / destruir ─────────────────────────────────────────────────────────────
def _ofertas() -> list[dict]:
    q = {"gpu_name": {"eq": C.GPU_NOMBRE}, "num_gpus": {"eq": 1}, "cpu_ram": {"gte": 32000}, "disk_space": {"gte": C.GPU_DISCO_GB},
         "inet_down": {"gte": 300}, "reliability2": {"gte": 0.97}, "rentable": {"eq": True}, "verified": {"eq": True},
         "dph_total": {"lte": C.GPU_MAX_USD_H}, "order": [["dph_total", "asc"]], "type": "on-demand", "limit": 10}
    return [o for o in _api("POST", "/bundles/", json=q).get("offers", []) if float(o.get("dph_total") or 9) <= C.GPU_MAX_USD_H]


def alquilar(log=None) -> dict:
    """Crea la instancia (probando varias ofertas: la más barata se la llevan entre listar y pedir) y espera el ssh."""
    pub = _clave_publica()
    onstart = ("mkdir -p /motor ~/.ssh && chmod 700 ~/.ssh && touch ~/.no_auto_tmux && "
               f"grep -qF '{pub.split()[1]}' ~/.ssh/authorized_keys 2>/dev/null || echo '{pub}' >> ~/.ssh/authorized_keys; "
               "chmod 600 ~/.ssh/authorized_keys")
    ofs = _ofertas()
    if not ofs:
        raise GpuError(f"no hay ofertas de {C.GPU_NOMBRE} a ≤ USD {C.GPU_MAX_USD_H}/h (subí DOBLAJE_GPU_MAX_USD_H o esperá)")
    iid = None
    for k, o in enumerate(ofs[:8], 1):
        _log(log, f"GPU: alquilando {o['gpu_name']} a USD {o['dph_total']:.3f}/h ({o.get('geolocation', '?')}; intento {k})")
        cuerpo = {"client_id": "me", "image": IMAGEN, "disk": C.GPU_DISCO_GB, "runtype": "ssh", "label": C.GPU_ETIQUETA,
                  "onstart": onstart, "env": {}}
        try:
            r = _api("PUT", f"/asks/{o['id']}/", json=cuerpo)
        except GpuError as e:
            if "no_such_ask" in str(e) or "unavailable" in str(e).lower():
                continue
            raise
        iid = r.get("new_contract") or r.get("id")
        if iid:
            break
    if not iid:
        raise GpuError("ninguna de las ofertas seguía disponible: reintentar en un rato")
    _guardar_registro(dict(id=iid, creada=time.strftime("%Y-%m-%d %H:%M:%S"), etiqueta=C.GPU_ETIQUETA))
    _ledger(tipo="alquilada", id=iid, dph=o.get("dph_total"), gpu=o.get("gpu_name"))
    _asegurar_atexit()                                       # guarda 8: quien alquila, destruye al salir
    t0 = time.time()
    while time.time() - t0 < 900:
        time.sleep(15)
        i = next((x for x in instancias_vivas() if x.get("id") == iid), None)
        est = (i or {}).get("actual_status")
        _estado["detalle"] = f"instancia {iid}: {est} ({int(time.time() - t0)} s)"
        if i and est == "running" and i.get("ssh_host"):
            d = _de_instancia(i)
            d["creada"] = time.strftime("%Y-%m-%d %H:%M:%S")
            _guardar_registro(d)
            _log(log, f"GPU: instancia {iid} arriba en {int(time.time() - t0)} s (USD {d['dph']}/h)")
            return d
    destruir("no arrancó en 15 min", log)
    raise GpuError("la instancia no arrancó en 15 min (destruida)")


def _esperar_ssh(host: str, port: int, log=None, tope: float = 600):
    t0 = time.time()
    while time.time() - t0 < tope:
        try:
            rc, out, _ = _ssh(host, port, "echo ssh_ok", 40)
            if "ssh_ok" in out:
                return
        except Exception as e:
            _estado["detalle"] = f"esperando ssh ({int(time.time() - t0)} s): {str(e)[:60]}"
        time.sleep(20)
    raise GpuError("el ssh de la instancia nunca entró")


def lista(host: str, port: int) -> bool:
    try:
        rc, out, _ = _ssh(host, port, f"test -f {MARCA_LISTA} && echo LISTA", 40)
        return "LISTA" in out
    except Exception:
        return False


def instalar(host: str, port: int, log=None):
    _log(log, "GPU: instalando el separador (torch CUDA + audio-separator + pesos; ≈6-10 min)")
    _ssh(host, port, "mkdir -p /motor", 60)
    _subir(host, port, SEP_PY.encode("utf-8"), SEP_REMOTO)
    _subir(host, port, INSTALAR_SH.replace("\r\n", "\n").encode("utf-8"), "/motor/instalar.sh")
    rc, out, err = _ssh(host, port, "bash /motor/instalar.sh 2>&1 | tee /motor/_instalar.log", TOPE_INSTALAR_S)
    if rc != 0 or "INSTALADA" not in out and "YA_LISTA" not in out:
        raise GpuError("la instalación falló: " + (out + err)[-400:].strip())
    m = [l for l in out.splitlines() if "MODELO_LOCAL" in l]
    _log(log, "GPU: lista" + (f" · {m[-1].strip()}" if m else ""))


def destruir(motivo: str = "", log=None) -> dict | None:
    """Destruye SÓLO nuestra instancia (por id/etiqueta). Devuelve lo destruido o None."""
    with _lock:
        i = mia()
        if not i:
            _guardar_registro(None)
            _estado.update(fase="apagada", detalle="", vencida=False)
            return None
        horas = (time.time() - float(i.get("start_date") or time.time())) / 3600
        usd = horas * float(i.get("dph_total") or 0)
        _api("DELETE", f"/instances/{i['id']}/")
        _guardar_registro(None)
        _ledger(tipo="destruida", id=i["id"], gpu=i.get("gpu_name"), dph=i.get("dph_total"), horas=round(horas, 3),
                usd=round(usd, 3), motivo=motivo)
        _estado.update(fase="apagada", detalle=f"apagada ({motivo})", vencida=False, usando=0)
        _log(log, f"GPU: instancia {i['id']} destruida ({motivo}) · {horas:.2f} h ≈ USD {usd:.2f}")
        return dict(id=i["id"], horas=round(horas, 2), usd=round(usd, 2))


def asegurar(log=None) -> tuple[str, int]:
    """(host, port) de nuestra GPU lista. Alquila e instala si hace falta (modo auto) respetando los topes."""
    if not configurada():
        raise GpuError("GPU no configurada (VAST_API_KEY / clave ssh) o DOBLAJE_GPU=off")
    with _lock:
        i = mia()
        if i and i.get("actual_status") == "running" and i.get("ssh_host"):
            d = _de_instancia(i)
            if not _registro():
                d["creada"] = time.strftime("%Y-%m-%d %H:%M:%S")
                _guardar_registro(d)
                _estado["ultimo_uso"] = time.time()
            if _estado.get("vencida"):
                raise GpuError("la GPU pasó el tope de horas y se apaga al terminar lo que está haciendo")
            if lista(d["host"], d["port"]):
                _estado.update(fase="lista", detalle="", error=None)
                return d["host"], d["port"]
            _estado.update(fase="instalando")
            instalar(d["host"], d["port"], log)
            _estado.update(fase="lista", detalle="", error=None)
            return d["host"], d["port"]
        if C.GPU_MODO != "auto":
            raise GpuError("la GPU está apagada y DOBLAJE_GPU=manual: prendela desde la web")
        gastado = usd_hoy()
        if gastado >= C.GPU_USD_TOPE_DIA:
            raise GpuError(f"tope de GPU del día alcanzado (USD {gastado:.2f} de {C.GPU_USD_TOPE_DIA:.2f}); "
                           "se sube con DOBLAJE_GPU_USD_TOPE_DIA")
        try:
            _estado.update(fase="alquilando", detalle="buscando oferta", error=None)
            d = alquilar(log)
            _estado.update(fase="instalando", detalle="esperando ssh")
            _esperar_ssh(d["host"], d["port"], log)
            instalar(d["host"], d["port"], log)
            _estado.update(fase="lista", detalle="", ultimo_uso=time.time())
            return d["host"], d["port"]
        except Exception as e:
            _estado.update(fase="error", detalle=str(e)[:200], error=str(e)[:200])
            if mia():
                destruir("falló la preparación: " + str(e)[:80], log)
            raise GpuError(str(e))


# ── separar ────────────────────────────────────────────────────────────────────────────────────
def separar(audio: Path, out_dir: Path, log=None) -> tuple[Path, Path] | None:
    """(vocals_clean.wav, music_effects.wav) en `out_dir`, separados en nuestra GPU; None si no se pudo (y lo dice)."""
    v0, f0 = out_dir / "vocals_clean.wav", out_dir / "music_effects.wav"
    if v0.exists() and f0.exists() and v0.stat().st_size > 1000 and f0.stat().st_size > 1000:
        _log(log, f"ya estaba separado, se reusa: {out_dir.name}")
        return v0, f0
    try:
        host, port = asegurar(log)
    except GpuError as e:
        _log(log, f"GPU no disponible: {e}")
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    base = f"/motor/sep_app/{uuid.uuid4().hex[:12]}"
    t0 = time.time()
    with _lock:
        _estado["usando"] += 1
        _estado["fase"] = "separando"
    try:
        _ssh(host, port, f"mkdir -p {base}/out", 60)
        _subir(host, port, audio, f"{base}/in.wav")
        rc, out, err = _ssh(host, port, f"PY=$(cat /motor/PY 2>/dev/null || echo /opt/venv/bin/python); PYTHONIOENCODING=utf-8 "
                                        f"timeout {TOPE_SEP_S} $PY -u {SEP_REMOTO} {base}/in.wav {base}/out", TOPE_SEP_S + 120)
        if rc != 0:
            _log(log, "GPU: el separador falló: " + (out + err)[-300:].strip())
            return None
        for nombre, dst in (("vocals_clean.wav", v0), ("music_effects.wav", f0)):
            _bajar(host, port, f"{base}/out/{nombre}", dst)
        m = [l for l in out.splitlines() if "MODELO_LOCAL" in l]
        _log(log, f"separado en la GPU en {time.time() - t0:.0f} s ({audio.name})" + (f" · {m[-1].strip()}" if m else ""))
        return v0, f0
    except Exception as e:
        _log(log, f"GPU: falló la separación: {str(e)[:200]}")
        return None
    finally:
        try:
            _ssh(host, port, f"rm -rf {base}", 60)                 # no dejar audio del cliente en una máquina alquilada
        except Exception:
            pass
        with _lock:
            _estado["usando"] = max(0, _estado["usando"] - 1)
            _estado["ultimo_uso"] = time.time()
            if _estado["fase"] == "separando" and _estado["usando"] == 0:
                _estado["fase"] = "lista"


# ── vigilante ──────────────────────────────────────────────────────────────────────────────────
def vigilar_una_vez(ahora: float | None = None, log=None) -> str:
    """Una pasada del vigilante (separada para poder probarla sin hilos). Devuelve qué hizo."""
    ahora = ahora or time.time()
    try:
        i = mia()
    except GpuError as e:
        return f"sin respuesta de vast: {e}"
    if not i:
        if _registro():
            _guardar_registro(None)
        if _estado["fase"] not in ("alquilando", "instalando"):
            _estado.update(fase="apagada", usando=0)
        return "nada vivo"
    if not _registro():                                            # adoptada de una web anterior
        d = _de_instancia(i)
        d["creada"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _guardar_registro(d)
        _estado.update(fase="lista", ultimo_uso=ahora)
        _log(log, f"GPU: adopto la instancia {i['id']} que quedó viva; se apaga sola si queda ociosa")
    horas = (ahora - float(i.get("start_date") or ahora)) / 3600
    if horas >= C.GPU_MAX_HORAS:
        if _estado["usando"] == 0:
            destruir(f"tope de {C.GPU_MAX_HORAS:g} h por instancia", log)
            return "destruida por tope de horas"
        if not _estado.get("vencida"):
            _estado["vencida"] = True
            _log(log, f"GPU: pasó el tope de {C.GPU_MAX_HORAS:g} h; se apaga al terminar la separación en curso")
        return "vencida, en uso"
    ociosa_s = ahora - float(_estado.get("ultimo_uso") or ahora)
    if _estado["usando"] == 0 and _estado["fase"] in ("lista", "apagada", "error") and ociosa_s >= C.GPU_OCIO_MIN * 60:
        destruir(f"ociosa {ociosa_s / 60:.0f} min", log)
        return "destruida por ociosa"
    return "viva"


def _vigilante():
    while True:
        try:
            vigilar_una_vez(log=lambda m: print("[gpu] " + m, flush=True))
        except Exception as e:
            print("[gpu] vigilante: " + str(e)[:200], flush=True)
        time.sleep(60)


def iniciar_vigilante():
    global _vigilante_iniciado
    if _vigilante_iniciado or not configurada():
        return
    _vigilante_iniciado = True
    threading.Thread(target=_vigilante, daemon=True, name="gpu-vigilante").start()


# ── estado para la web ─────────────────────────────────────────────────────────────────────────
def estado(consultar: bool = True) -> dict:
    out = dict(configurada=configurada(), modo=C.GPU_MODO, fase=_estado["fase"], detalle=_estado["detalle"],
               usando=_estado["usando"], error=_estado["error"], instancia=None, usd_hoy=None,
               topes=dict(usd_h=C.GPU_MAX_USD_H, horas=C.GPU_MAX_HORAS, ocio_min=C.GPU_OCIO_MIN, usd_dia=C.GPU_USD_TOPE_DIA))
    if not out["configurada"]:
        out["usd_hoy"] = usd_hoy()
        return out
    if consultar:
        try:
            i = mia()
            if i:
                horas = (time.time() - float(i.get("start_date") or time.time())) / 3600
                out["instancia"] = dict(id=i["id"], gpu=i.get("gpu_name"), usd_h=i.get("dph_total"), estado=i.get("actual_status"),
                                        horas=round(horas, 2), usd=round(horas * float(i.get("dph_total") or 0), 2))
                if _estado["fase"] == "apagada":
                    out["fase"] = "viva"
            out["usd_hoy"] = usd_hoy(i)
        except GpuError as e:
            out["error"] = str(e)[:200]
    return out
