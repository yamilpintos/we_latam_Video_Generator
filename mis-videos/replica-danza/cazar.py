"""Caza una 4×RTX 5090 para la muestra de la réplica y la deja corriendo.

    python -X utf8 -u mis-videos/replica-danza/cazar.py

Pedido del 14/9/2026: alquilar, correr la muestra y NO destruir al terminar
(después va el video entero en la misma instancia). Mismo criterio que el
cazador del koi, con tres diferencias:

- Descarga Ref2VA desde el principio (`--ref2va`): la etapa B de la muestra lo
  necesita y va en la misma instancia.
- Si la máquina no arranca en 10 min, se destruye y se sigue buscando, y esa
  máquina queda anotada para no volver a elegirla (trampa 16 y regla 2 de la
  corrida limpia: una host colgada cobra sin servir). Eso NO es "destruir al
  terminar": nunca llegó a generar.
- Techo de precio de $4/h (trampa 15).

Termina en cuanto la corrida queda lanzada; `seguir` la sigue desde ahí.
"""
import json
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(RAIZ))
from h3pipeline import vast  # noqa: E402

ZIP = AQUI / "replica-danza-muestra-a-para-vast.zip"
# `--solo-setup ZIP`: alquila, sube ese ZIP y corre SOLO setup.sh (los ~87 GB de
# modelos), sin lanzar nada. Para adelantar la descarga mientras acá se termina
# el paquete (15/9: los primeros fotogramas del original todavía se limpiaban).
SOLO_SETUP = "--solo-setup" in sys.argv
if SOLO_SETUP:
    ZIP = Path(sys.argv[sys.argv.index("--solo-setup") + 1]).resolve()
TECHO_DPH = 4.0
ARRANQUE_MIN = 10
COLGADAS = AQUI / "hosts-colgados.json"

colgadas = set(json.loads(COLGADAS.read_text())) if COLGADAS.exists() else set()
ultimo, n = None, 0
while True:
    n += 1
    try:
        ofertas = vast.buscar(gpu="RTX 5090")
    except Exception as e:           # red inestable: se sigue intentando
        print(f"consulta {n}: error {e}", flush=True)
        time.sleep(60)
        continue
    # China continental no: el 14/9 la máquina 138100 (Shanghái) arrancó bien
    # pero no llegaba a huggingface.co ni a github.com, el espejo hf-mirror
    # redirige al almacenamiento bloqueado, y ModelScope daba ~1 MB/s: 76 GB en
    # más de 20 h. Se destruyó a los 35 min ($1,70). Hong Kong sí tiene salida.
    BLOQUEADOS = (", cn", "china", "shanghai", "beijing", "shenzhen", "guangdong")
    buenas = [o for o in ofertas if o.dph <= TECHO_DPH and o.maquina not in colgadas
              and not any(b in o.geo.lower() for b in BLOQUEADOS)]
    estado = (f"{len(buenas)} permitidas"
              + (f" · descartadas: {', '.join(f'{o.geo} ${o.dph:.2f}' for o in ofertas if o not in buenas)}"
                 if len(buenas) < len(ofertas) else ""))
    if estado != ultimo:
        print(f"consulta {n} ({time.strftime('%H:%M')}): {estado}", flush=True)
        ultimo = estado
    if not buenas:
        time.sleep(60)
        continue

    # Por fiabilidad y ancho de banda, nunca por precio (regla 2).
    elegida = max(buenas, key=lambda o: (o.fiabilidad, o.inet_down))
    print(vast.tabla(buenas[:5]), flush=True)
    print(f"ALQUILANDO {elegida.id} · máquina {elegida.maquina} · {elegida.geo} · "
          f"${elegida.dph:.3f}/h", flush=True)
    try:
        r = vast.crear(elegida.id, confirmar=True)
        iid = int(r.get("new_contract") or r.get("id"))
        print(f"instancia {iid} creada", flush=True)
    except Exception as e:
        print(f"no se pudo alquilar: {e}", flush=True)
        time.sleep(60)
        continue

    try:
        vast.autorizar_clave(iid)
        inst = vast.esperar_lista(iid, minutos=ARRANQUE_MIN,
                                  log=lambda m: print(m, flush=True))
    except Exception as e:
        print(f"NO ARRANCÓ: {e}", flush=True)
        try:
            vast.destruir(iid, confirmar=True)
            print(f"  instancia {iid} destruida (nunca generó); sigo buscando", flush=True)
        except Exception as e2:
            print(f"  !! no pude destruir {iid}: {e2} — HACERLO A MANO", flush=True)
            sys.exit(2)
        colgadas.add(elegida.maquina)
        COLGADAS.write_text(json.dumps(sorted(colgadas)))
        continue

    # ¿Llega a Hugging Face? Si no, no va a poder bajar los modelos: se destruye
    # ya, antes de pagar la espera de una descarga que no avanza.
    try:
        salida = vast.ejecutar(inst, "curl -s -o /dev/null -m 20 -w '%{http_code}' "
                                     "https://huggingface.co/api/models/Comfy-Org/MiniMax-H3",
                               timeout=60)
        llega = salida.strip().endswith("200")
    except Exception:
        llega = False
    if not llega:
        print(f"SIN SALIDA A HUGGING FACE desde {elegida.geo}: destruyo {iid} y sigo", flush=True)
        try:
            vast.destruir(iid, confirmar=True)
        except Exception as e2:
            print(f"  !! no pude destruir {iid}: {e2} — HACERLO A MANO", flush=True)
            sys.exit(2)
        colgadas.add(elegida.maquina)
        COLGADAS.write_text(json.dumps(sorted(colgadas)))
        continue

    # El taxímetro: `seguir` y `bajar` muestran lo acumulado desde acá.
    (AQUI / "corrida.json").write_text(json.dumps(
        {"instancia": iid, "dph": float(inst.get("dph_total") or elegida.dph),
         "inicio": time.time(), "estimado": 9.0, "maquina": elegida.maquina,
         "geo": elegida.geo}), encoding="utf-8")
    vast.subir(inst, ZIP, log=lambda m: print(m, flush=True))
    if SOLO_SETUP:
        cmd = ("export PATH=/venv/main/bin:$PATH && cd /workspace/refs && "
               f"unzip -oq {ZIP.name} && sed -i 's/\\r$//' *.sh *.py && SOLO_FL=0 bash setup.sh")
        vast.lanzar(inst, cmd, log="/root/setup.log")
        print(f"LISTO: instancia {iid} bajando modelos (log /root/setup.log). "
              f"Falta subir el paquete y correr lanzar.sh.", flush=True)
        break
    vast.generar(inst, ZIP.name, pasos=8, ref2va=True, log=lambda m: print(m, flush=True))
    print(f"LISTO: muestra A lanzada en la instancia {iid}. NO se destruye al terminar.",
          flush=True)
    print(f"  seguir: python -m h3pipeline seguir mis-videos/replica-danza/muestra-A.json {iid}",
          flush=True)
    break
