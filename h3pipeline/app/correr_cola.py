"""Tarea: correr la cola entera con una sola máquina.

    python -X utf8 -u -m h3pipeline.app.correr_cola

Enciende si hace falta (y caza si no hay 5090), espera la instalación, y por
cada proyecto pendiente: genera → espera los clips → baja. Al final apaga si la
cola lo pide. Todo queda en `cola.json`, `maquina.json` y este log.
"""
import json
import subprocess
import sys
import time

from .. import vast
from . import cola, maquina


def log(s: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {s}", flush=True)


def necesita_ref2va(slug: str) -> bool:
    """¿Algún plano del proyecto va en Ref2VA (voz de referencia, edición)?"""
    try:
        d = json.loads((maquina.MIS / slug / "proyecto.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    return any(pl.get("modo") == "ref2va" for pl in d.get("planos") or [])


def asegurar_ref2va(log=print, minutos: int = 40) -> None:
    """La máquina se instala sólo con FL2VA (59 GB). Si un proyecto de la cola
    lleva voz de referencia hace falta el modelo Ref2VA (24 GB + LoRA): setup.sh
    es idempotente y con SOLO_FL=0 agrega lo que falta. Espera a que esté."""
    from . import editar
    m = maquina.leer()
    inst = vast.instancia(int(m["instancia"]))
    if editar.ref2va_presente(inst):
        return
    log("la cola lleva voz de referencia: instalo Ref2VA en la máquina (24 GB, ~5 min a 1 Gbps)")
    editar.instalar_ref2va(inst, log=log)
    t0 = time.time()
    while time.time() - t0 < minutos * 60:
        time.sleep(30)
        if editar.ref2va_presente(inst):
            log("Ref2VA instalado")
            # Los ComfyUI ya levantados no conocen el modelo nuevo: se reinician
            # (la placa 0 por supervisor, las otras las relanza lanzar.sh).
            vast.ejecutar(inst, "supervisorctl restart comfyui >/dev/null 2>&1 || true", timeout=90)
            vast.ejecutar(inst, "pkill -f '[m]ain.py --disable-auto-launch --port 1819' || true", timeout=30)
            time.sleep(20)
            return
        pr = editar.progreso_ref2va(inst)
        log(f"  Ref2VA: {pr.get('gb') or 0} de 23,9 GB")
    raise RuntimeError("Ref2VA no terminó de bajar en 40 min")


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
        bajada_fallida = False
        for slug in cola.pendientes():
            cola.marcar(slug, "generando")
            try:
                if necesita_ref2va(slug):
                    asegurar_ref2va(log)
                # Segunda vuelta de un proyecto con clips ya bajados: sólo los que faltan.
                hechos = maquina.clips_locales(slug)
                if hechos:
                    faltan = [x for x in maquina.fuentes(slug) if x not in hechos]
                    if not faltan:
                        log(f"{slug}: ya tiene todos los clips; nada que generar")
                        cola.marcar(slug, "bajado", "")
                        continue
                    log(f"{slug}: {len(hechos)} clips ya bajados; se reempaquetan sólo los {len(faltan)} que faltan")
                    r = subprocess.run([sys.executable, "-X", "utf8", "-u", "-m", "h3pipeline", "empaquetar",
                                        str(maquina.MIS / slug / "proyecto.json"), "--sin-reescribir", "--solo", *faltan],
                                       cwd=str(maquina.RAIZ), capture_output=True, text=True, encoding="utf-8", errors="replace")
                    if r.returncode:
                        raise RuntimeError("no pude reempaquetar los que faltan: " + (r.stdout or "")[-300:])
                maquina.generar_proyecto(slug, log=log)
                ok = maquina.esperar_clips(slug, log=log)
                if not ok:
                    # Una placa muerta o el plazo corto: se relanzan los runners UNA
                    # vez (saltean lo hecho) y se espera otra mitad del plazo.
                    maquina.relanzar(slug, log=log)
                    ok = maquina.esperar_clips(slug, log=log, minutos=max(45, maquina.plazo_minutos(slug) // 2))
                cola.marcar(slug, "bajando", "" if ok else "clips incompletos: bajo lo que hay")
                if maquina.bajar(slug, log=log, parcial=not ok):
                    if ok:
                        cola.marcar(slug, "bajado", "")
                    else:
                        n = len(maquina.clips_locales(slug))
                        t = len(maquina.fuentes(slug))
                        cola.marcar(slug, "error", f"faltan {t - n} de {t} clips (bajados {n}); volvé a correr la cola: rehace sólo los que faltan")
                else:
                    cola.marcar(slug, "error", "la bajada falló: la máquina sigue encendida con los clips adentro")
                    raise RuntimeError("bajada fallida")
            except Exception as e:
                log(f"!! {slug}: {e}")
                if "bajada fallida" in str(e):
                    bajada_fallida = True
                    log("!! NO apago la máquina: tiene clips sin bajar. Bajalos o apagala desde la web.")
                else:
                    cola.marcar(slug, "error", str(e)[:200])
        if cola.leer().get("apagar_al_final", True) and not bajada_fallida:
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
