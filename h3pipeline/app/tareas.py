"""Tareas en segundo plano: un proceso por tarea, con su log en disco.

Se lanza `python -X utf8 -u -m h3pipeline <comando> ...` (o cualquier script)
como subproceso, con stdout y stderr al mismo archivo. La página consulta el
estado y la cola del log cada dos segundos. Los procesos sobreviven a que se
cierre la pestaña; no sobreviven a que se cierre el servidor.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LOGS = Path(__file__).resolve().parent / "logs"
LOGS.mkdir(exist_ok=True)


@dataclass
class Tarea:
    id: str
    nombre: str
    args: list[str]
    slug: str | None
    log: Path
    inicio: float
    fin: float | None = None
    rc: int | None = None
    proc: subprocess.Popen | None = field(default=None, repr=False)

    @property
    def estado(self) -> str:
        if self.rc is None:
            return "corriendo"
        return "ok" if self.rc == 0 else "error"

    def cola(self, lineas: int = 40) -> str:
        try:
            texto = self.log.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""
        return "\n".join(texto.splitlines()[-lineas:])

    def a_dict(self, lineas: int = 40) -> dict:
        return {"id": self.id, "nombre": self.nombre, "slug": self.slug,
                "estado": self.estado, "rc": self.rc, "inicio": self.inicio,
                "fin": self.fin, "segundos": round((self.fin or time.time()) - self.inicio),
                "log": self.cola(lineas)}


_registro: dict[str, Tarea] = {}
_lock = threading.Lock()


def lanzar(nombre: str, args: list[str], slug: str | None = None,
           cwd: Path | None = None, python: bool = True) -> Tarea:
    """Arranca el proceso y vuelve enseguida. `args` son los argumentos DESPUÉS
    de `python -X utf8 -u` (por ejemplo `["-m", "h3pipeline", "frames", ...]`)."""
    tid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    log = LOGS / f"{tid}.log"
    cmd = ([sys.executable, "-X", "utf8", "-u"] if python else []) + args
    f = open(log, "w", encoding="utf-8")
    f.write("$ " + " ".join(cmd) + "\n\n")
    f.flush()
    proc = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=str(cwd or RAIZ),
                            env=_entorno())
    t = Tarea(id=tid, nombre=nombre, args=args, slug=slug, log=log,
              inicio=time.time(), proc=proc)
    with _lock:
        _registro[tid] = t
    threading.Thread(target=_vigilar, args=(t, f), daemon=True).start()
    return t


def _entorno() -> dict:
    import os
    e = dict(os.environ)
    e["PYTHONIOENCODING"] = "utf-8"
    e["PYTHONUTF8"] = "1"
    return e


def _vigilar(t: Tarea, f) -> None:
    rc = t.proc.wait()
    f.write(f"\n[fin · código {rc}]\n")
    f.close()
    t.rc = rc
    t.fin = time.time()


def obtener(tid: str) -> Tarea | None:
    return _registro.get(tid)


def listar(slug: str | None = None, cuantas: int = 30) -> list[dict]:
    ts = sorted(_registro.values(), key=lambda x: x.inicio, reverse=True)
    if slug:
        ts = [t for t in ts if t.slug == slug]
    return [t.a_dict(lineas=6) for t in ts[:cuantas]]


def corriendo(slug: str | None = None) -> list[Tarea]:
    return [t for t in _registro.values() if t.rc is None and (slug is None or t.slug == slug)]


def matar(tid: str) -> bool:
    t = _registro.get(tid)
    if not t or t.rc is not None:
        return False
    t.proc.terminate()
    return True
