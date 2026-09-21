"""El paquete que se sube a la máquina alquilada: dibujos, lista de planos y
los tres scripts que se ejecutan allá.

Se arma DESPUÉS de revisar el storyboard entero y ANTES de alquilar nada. Ese
orden es la mitad del ahorro: un encuadre mal salido se descubre mirando un PNG,
no después de siete minutos de generación con el reloj corriendo.

Lo único no obvio que hace es **normalizar los dibujos** a la resolución exacta
a la que renderiza H3. nano banana devuelve la relación de aspecto que le
parece: en una tanda de 42 salieron tres distintas, y siete en cinemascope. Si
entran así, H3 los aplasta y los personajes salen gordos.

Y se sube un ZIP, no la carpeta: el botón Upload de Jupyter **aplasta las
carpetas** y los dibujos caerían sueltos en vez de quedar dentro de `assets/`.
"""
from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from . import costos, frames
from .proyecto import Proyecto

REMOTO = Path(__file__).resolve().parent / "remoto"
SCRIPTS = ("setup.sh", "lanzar.sh", "rescate.sh", "runner.py")


def empaquetar(proyecto: Proyecto, destino: Path | None = None,
               origen_dibujos: Path | None = None, zip_: bool = True,
               solo: list[str] | None = None, log=print) -> Path:
    """Arma la carpeta (y el zip) para subir.

    `solo` empaqueta nada más que esos planos, que es como se rehace una tanda
    fallada sin tocar los que salieron bien.
    """
    _sb, doc = proyecto.construir()
    planos = doc["planos"]
    if solo:
        faltan = set(solo) - {p["id"] for p in planos}
        if faltan:
            raise SystemExit(f"!! no existen estos planos: {' '.join(sorted(faltan))}")
        planos = [p for p in planos if p["id"] in solo]
        doc = dict(doc, planos=planos,
                   _comentario="Sólo los planos a rehacer. Los demás ya están y no se tocan.")

    raiz = Path(proyecto.raiz)
    destino = Path(destino or raiz / "para-vast")
    origen = Path(origen_dibujos or raiz / "assets")
    assets = destino / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    # Los dibujos de una corrida anterior no van: el runner sólo lee los que
    # están en planos.json y de paso la subida pesa menos.
    for viejo in list(assets.glob("*.png")) + list(assets.glob("*.wav")):
        viejo.unlink()

    w, h = proyecto.wh
    recortados, faltan = [], []
    for p in planos:
        # Un plano encadenado no lleva dibujo: su primer fotograma sale del
        # último del clip anterior, ya dentro de la máquina.
        if not p.get("first_frame"):
            continue
        nombre = Path(p["first_frame"]).name
        src = origen / nombre
        if not src.exists():
            faltan.append(f"{p['id']} ({nombre})")
            continue
        perdido = frames.normalizar(src, assets / nombre, w, h)
        # El umbral es 5 % y no 0 porque hay un recorte sistemático de ~2 % que
        # no se puede evitar: la resolución nativa de H3 no es 16:9 exacto
        # (1344/768 = 1,750 contra 1,778) y nano banana devuelve 1376 de lado
        # largo. Avisar de eso en los 42 planos taparía los casos que importan,
        # que son los que vienen en cinemascope y pierden un cuarto del cuadro.
        if perdido > 0.05:
            recortados.append((p["id"], perdido))
        # Ref2VA: las referencias extra (hojas de personaje) viajan SIN
        # normalizar —el nodo las escala conservando su aspecto— y la voz de
        # referencia va como está (ya viene a 32 kHz estéreo y múltiplo de 800
        # muestras, ver voz_ref.py).
        vozs = p.get("voz_ref") or []
        for extra in list(p.get("refs_extra") or []) + ([vozs] if isinstance(vozs, str) else list(vozs)):
            src_x = origen / Path(extra).name
            if not src_x.exists():
                faltan.append(f"{p['id']} ({Path(extra).name})")
            elif not (assets / src_x.name).exists():
                shutil.copy(src_x, assets / src_x.name)
    if faltan:
        raise SystemExit("!! faltan dibujos en " + str(origen) + ":\n   "
                         + "\n   ".join(faltan)
                         + "\n   Generalos con: python -m h3pipeline frames <proyecto.json>")

    # Los planos que reusan el clip de otro (`clip_de`) no viajan: no se generan.
    # El montaje local los resuelve; el runner sólo ve las fuentes.
    doc = dict(doc, planos=[p for p in planos if not p.get("clip_de")])
    (destino / "planos.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
    for s in SCRIPTS:
        shutil.copy(REMOTO / s, destino / s)
    (destino / "LEEME.txt").write_text(leeme(proyecto, planos), encoding="utf-8")

    log(f"{len(planos)} dibujos normalizados a {w}×{h}")
    if recortados:
        log(f"\n  {len(recortados)} venían en otra relación de aspecto y se recortaron al centro:")
        for pid, q in sorted(recortados, key=lambda x: -x[1]):
            log(f"    {pid}  se perdió el {q * 100:.0f} % del cuadro")
        log("  Si alguno pierde algo importante, se regenera ese dibujo y se vuelve a empaquetar.")

    salida = destino
    if zip_:
        salida = destino.parent / f"{proyecto.slug}-para-vast.zip"
        with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for f in sorted(destino.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(destino).as_posix())
        log(f"\n{salida.name}   {salida.stat().st_size / 1e6:.1f} MB")
    else:
        peso = sum(f.stat().st_size for f in destino.rglob("*") if f.is_file()) / 1e6
        log(f"\n{destino}   {peso:.0f} MB")
    return salida


def leeme(proyecto: Proyecto, planos: list[dict]) -> str:
    """Las instrucciones, dentro del paquete: cuando estás en Jupyter a las tres
    de la mañana no querés volver a buscar el comando en otra ventana."""
    w, h = proyecto.wh
    seg_gen = sum(p["segundos"] for p in planos)
    est = costos.estimar(planos)
    L = [
        f"{proyecto.titulo}  —  {len(planos)} planos  —  {w}x{h}",
        "=" * 70, "",
        f"Formato: {proyecto.formato}. Se generan {seg_gen:.0f} s de video.",
        "",
        "Cada plano arranca de su propio dibujo de storyboard, dura lo que tiene",
        "que durar y se une al resto con un CORTE.", ""] + ([
        f"{sum(1 for x in planos if x.get('sigue_de'))} planos van ENCADENADOS: arrancan en el ultimo fotograma del",
        "clip anterior en vez de un dibujo, para que la accion no reinicie en cada",
        "corte. Esos van en serie y en la misma placa; el resto paraleliza.", "",
        ] if any(x.get("sigue_de") for x in planos) else []) + [
        "LOS CUATRO COMANDOS", "-" * 20,
        "Subi este ZIP por el boton Upload de Jupyter. Despues, en una Terminal:",
        "",
        "  1)  mkdir -p /workspace/refs && cd /workspace/refs \\",
        f"        && unzip -o ~/{proyecto.slug}-para-vast.zip",
        "",
        "  2)  sed -i 's/\\r$//' /workspace/refs/*.sh /workspace/refs/*.py",
        "      bash /workspace/refs/setup.sh",
        "",
        "      Baja ~59 GB (solo FL2VA: Ref2VA no se usa nunca en este pipeline).",
        "      Entre 5 y 30 minutos segun el enlace del host. Las cinco lineas de",
        "      la verificacion final tienen que decir OK. Si alguna dice !!:",
        "        supervisorctl restart comfyui   y volve a correr el setup.",
        "",
        "  3)  PASOS=8 bash /workspace/refs/lanzar.sh",
        "",
        f"      Estimado: {est.minutos_pared:.0f} min de pared con 4 placas, "
        f"${est.costo_generacion:.2f}.",
        "      Seguilo con:  tail -n3 /root/gpu?.log",
        "",
        "  4)  python /root/runner.py --montar",
        "",
        f"      Escribe {proyecto.titulo.upper().replace(' ', '_')[:32]}.mp4 y su .srt en",
        "      /workspace/ComfyUI/output/video/",
        "",
        "BAJATE TODO ANTES DE DESTROY", "-" * 28,
        "Bajate tambien los planos sueltos si pensas retocar en un editor, y",
        "metricas.json, que trae el tiempo real de cada plano con su duracion al",
        "lado: con eso se reajusta la estimacion de costo.",
        "",
        "  STOP    apaga la GPU pero sigue cobrando el disco. Conviene si volves",
        "          en unos dias: te ahorra rebajar los 59 GB.",
        "  DESTROY borra todo y dejas de pagar. No hay vuelta atras.",
        "",
        "SI ALGO SALE MAL", "-" * 16,
        "  Un plano feo .......... rm .../P17_*  y  python /root/runner.py --gpu 0 --total 1",
        "  Se corto a la mitad ... volve a lanzar: saltea lo que ya existe",
        "  value_not_in_list ..... supervisorctl restart comfyui, esperá un minuto",
        "  Una placa no responde . cat /root/comfy1.log; suele ser VRAM. GPUS=2 bash lanzar.sh",
        "  El ENCUADRE esta mal .. eso no se arregla con el prompt de video: se",
        "                          regenera el DIBUJO en tu maquina y se re-empaqueta",
        "",
        "LOS PLANOS", "-" * 10,
    ]
    for p in planos:
        usa = f"  usa {p['usa'][0]:.1f}-{p['usa'][1]:.1f}" if p.get("usa") else ""
        dia = f'  habla: "{p["dialogo"]}"' if p.get("dialogo") else ""
        enc = f"  <- sigue de {p['sigue_de']}" if p.get("sigue_de") else ""
        L.append(f"  {p['id']:<5} {p.get('tipo', ''):<5} {p['segundos']:5.1f}s"
                 f"{usa}  {p.get('tramo') or ''}{enc}{dia}")
    return "\n".join(L) + "\n"
