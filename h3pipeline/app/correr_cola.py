"""Tarea: correr la cola entera con una sola máquina.

    python -X utf8 -u -m h3pipeline.app.correr_cola

Enciende si hace falta (y caza si no hay 5090), espera la instalación, y por
cada proyecto pendiente: genera → espera los clips → baja. Al final apaga si la
cola lo pide. Todo queda en `cola.json`, `maquina.json` y este log.
"""
import time

from .. import vast
from . import cola, maquina


def log(s: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True)


def main() -> int:
    d = cola.leer()
    d["corriendo"] = True
    cola.escribir(d)
    try:
        pend = cola.pendientes()
        if not pend:
            log("la cola está vacía")
            return 0
        log(f"cola: {', '.join(pend)}")
        m = maquina.leer()
        if m.get("fase") in ("apagada", "fallo") or not m.get("instancia"):
            log("no hay máquina: enciendo")
            inst = maquina.encender(None, log=log)
            if not inst:
                return 1
            if not maquina.esperar_instalacion(inst, log=log):
                return 1
        elif m.get("fase") in ("arrancando", "instalando", "buscando"):
            log(f"la máquina está en fase {m['fase']}: espero")
            t0 = time.time()
            while maquina.leer().get("fase") not in ("lista", "apagada", "fallo") and time.time() - t0 < 60 * 60:
                m2 = maquina.leer()
                if m2.get("fase") == "instalando" and m2.get("instancia"):
                    try:
                        inst = vast.instancia(int(m2["instancia"]))
                        if maquina.progreso_instalacion(inst, cada=0)["listo"]:
                            maquina.escribir(fase="lista", lista_desde=time.time())
                            break
                    except Exception:
                        pass
                time.sleep(30)
            if maquina.leer().get("fase") != "lista":
                log("!! la máquina no llegó a lista")
                return 1
        for slug in cola.pendientes():
            cola.marcar(slug, "generando")
            try:
                maquina.generar_proyecto(slug, log=log)
                ok = maquina.esperar_clips(slug, log=log)
                cola.marcar(slug, "bajando", "" if ok else "clips incompletos")
                if maquina.bajar(slug, log=log):
                    cola.marcar(slug, "bajado", "" if ok else "parcial")
                else:
                    cola.marcar(slug, "error", "la bajada falló")
            except Exception as e:
                log(f"!! {slug}: {e}")
                cola.marcar(slug, "error", str(e)[:200])
        if cola.leer().get("apagar_al_final", True):
            r = maquina.apagar(log=log)
            log(f"máquina apagada · gastó ${r.get('gasto_final')} en {r.get('minutos')} min")
        else:
            log("la máquina queda encendida (la cola pidió no apagar). Acordate de apagarla.")
        return 0
    finally:
        d = cola.leer()
        d["corriendo"] = False
        cola.escribir(d)


if __name__ == "__main__":
    raise SystemExit(main())
