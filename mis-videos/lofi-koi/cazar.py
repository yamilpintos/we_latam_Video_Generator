"""Caza una 4×RTX 5090 permitida: consulta Vast cada minuto y, cuando aparece,
la alquila y deja la corrida del proyecto lanzada.

    python -X utf8 -u cazar.py mis-videos/lofi-koi/proyecto.json

Elige por fiabilidad (y a igual fiabilidad, por ancho de banda), nunca por
precio, y descarta Shanghái (regla 2 de la corrida limpia en VAST.md).
Imprime una línea por consulta sólo cuando cambia algo, y termina al alquilar.
"""
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from h3pipeline import vast  # noqa: E402

proyecto = sys.argv[1]
ultimo = None
n = 0
while True:
    n += 1
    try:
        ofertas = vast.buscar(gpu="RTX 5090")
    except Exception as e:  # red inestable: se sigue intentando
        print(f"consulta {n}: error {e}", flush=True)
        time.sleep(60)
        continue
    # Techo de precio: el 11/9 apareció una 4×5090 en Noruega a $213/h (precio
    # erróneo del host). Vast la rechazó por su propio máximo, pero el cazador
    # la intentó igual. Nunca más de TECHO_DPH.
    TECHO_DPH = 4.0
    buenas = [o for o in ofertas if "shanghai" not in o.geo.lower() and o.dph <= TECHO_DPH]
    caras = ", ".join(f"{o.id} ${o.dph:.0f}/h {o.geo}" for o in ofertas if o.dph > TECHO_DPH)
    estado_caras = caras
    if estado_caras != globals().get("ultimo_caras"):
        globals()["ultimo_caras"] = estado_caras
        if caras:
            print(f"consulta {n}: descartadas por precio: {caras}", flush=True)
    estado = f"{len(buenas)} permitidas"
    if estado != ultimo:
        print(f"consulta {n} ({time.strftime('%H:%M')}): {estado}", flush=True)
        ultimo = estado
    if not buenas:
        time.sleep(60)
        continue
    elegida = max(buenas, key=lambda o: (o.fiabilidad, o.inet_down))
    print("OFERTA:", vast.tabla(buenas[:5]), flush=True)
    print(f"ALQUILANDO {elegida.id}", flush=True)
    r = subprocess.run([sys.executable, "-X", "utf8", "-u", "-m", "h3pipeline", "alquilar",
                        proyecto, str(elegida.id), "--si", "--generar"],
                       cwd=str(RAIZ), capture_output=True, text=True)
    print(r.stdout[-3000:], flush=True)
    if r.returncode:
        print("FALLÓ EL ALQUILER:", r.stderr[-1500:], flush=True)
        time.sleep(60)
        continue
    print("LISTO: corrida lanzada", flush=True)
    break
