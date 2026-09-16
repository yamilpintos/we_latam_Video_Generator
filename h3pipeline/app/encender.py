"""Tarea: encender la máquina. Busca (o toma) una 4×5090 apta, la alquila,
espera el SSH, sube los scripts e instala H3. Deja la instancia en fase
`instalando`; el servidor mide el avance por SSH y la pasa a `lista`.

    python -X utf8 -u -m h3pipeline.app.encender [id_de_oferta]

Sin id, CAZA: consulta Vast cada minuto hasta que aparezca una apta (con techo
de precio y sin Shanghái, trampas 15 y 16). Si la instancia no arranca en 20
minutos, la destruye y vuelve a buscar, hasta tres veces.
"""
import sys
import time

from .. import vast
from . import maquina


def alquilar(oferta) -> dict | None:
    print(f"ALQUILANDO {oferta.id} · {oferta.geo} · ${oferta.dph:.3f}/h · {oferta.inet_down:.0f} Mbps · "
          f"fiab {oferta.fiabilidad:.3f}", flush=True)
    r = vast.crear(oferta.id, confirmar=True, disco_gb=vast.DISCO_GB)
    iid = int(r.get("new_contract") or r.get("id"))
    maquina.escribir(fase="arrancando", instancia=iid, dph=float(oferta.dph), inicio=time.time(),
                     oferta={"id": oferta.id, "geo": oferta.geo, "gpu": oferta.gpu, "gpus": oferta.gpus,
                             "inet": round(oferta.inet_down), "fiabilidad": round(oferta.fiabilidad, 4)},
                     fin=None, gasto_final=None, proyecto=None)
    print(f"instancia {iid} creada", flush=True)
    vast.autorizar_clave(iid)
    try:
        inst = vast.esperar_lista(iid)
    except Exception as e:
        print(f"!! no arrancó: {e}. La destruyo.", flush=True)
        try:
            vast.destruir(iid, confirmar=True)
        except Exception:
            pass
        maquina.escribir(fase="fallo", fin=time.time())
        return None
    maquina.escribir(dph=float(inst.get("dph_total") or oferta.dph))
    return inst


def main() -> int:
    pedido = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    intentos = 0
    inst = None
    while inst is None and intentos < 3:
        oferta = None
        if pedido and intentos == 0:
            lista = vast.buscar(gpu="RTX 5090", solo_verificadas=False, inet_mbps=0, fiabilidad=0)
            oferta = next((o for o in lista if o.id == pedido), None)
            if oferta is None:
                print(f"la oferta {pedido} ya no está; busco otra apta", flush=True)
        if oferta is None:
            n = 0
            while oferta is None:
                n += 1
                try:
                    oferta = maquina.mejor_oferta()
                except Exception as e:
                    print(f"consulta {n}: error {e}", flush=True)
                if oferta is None:
                    if n == 1 or n % 10 == 0:
                        print(f"consulta {n} ({time.strftime('%H:%M')}): ninguna 4×5090 apta; sigo cada minuto",
                              flush=True)
                    maquina.escribir(fase="buscando", instancia=None, proyecto=None)
                    time.sleep(60)
        intentos += 1
        inst = alquilar(oferta)
    if inst is None:
        print("!! tres intentos sin arrancar. Me rindo.", flush=True)
        return 1
    z = maquina.zip_setup()
    vast.subir(inst, z)
    cmd = ("export PATH=/venv/main/bin:$PATH && cd /workspace/refs && "
           f"unzip -oq {z.name} && sed -i 's/\\r$//' *.sh *.py && bash setup.sh")
    vast.lanzar(inst, cmd, log=vast.LOG_CORRIDA)
    maquina.escribir(fase="instalando")
    print(f"instalando H3 (59 GB) · log en {vast.LOG_CORRIDA} · {vast.ssh_de(inst)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
