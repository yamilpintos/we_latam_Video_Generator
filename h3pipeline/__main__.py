"""CLI de conveniencia. La app usa las funciones; esto es para trabajar a mano.

    python -m h3pipeline estructuras                    # qué estructuras hay
    python -m h3pipeline brief <proyecto.json>          # el documento de dirección
    python -m h3pipeline construir <proyecto.json>      # storyboard.json + planos.json
    python -m h3pipeline frames <proyecto.json>         # los primeros fotogramas
    python -m h3pipeline empaquetar <proyecto.json>     # el ZIP para subir
    python -m h3pipeline costo <proyecto.json>          # qué va a salir
    python -m h3pipeline gpu <proyecto.json>            # dónde correrlo
    python -m h3pipeline montar <proyecto.json> <clips> # el corte solo (diálogo en boca)
    python -m h3pipeline mezclar <proyecto.json> <clips># el MÁSTER: corte + voz en off +
                                                       # música + subtítulos quemados
    python -m h3pipeline alquilar <proyecto.json> [id] # ALQUILA (cobra) y sube el ZIP;
                                                       # sin id, elige la más barata
    python -m h3pipeline generar <proyecto.json> <iid>  # deja la corrida andando sola
    python -m h3pipeline seguir  <proyecto.json> <iid>  # cuántos clips van
    python -m h3pipeline bajar   <proyecto.json> <iid>  # monta si falta y baja todo
    python -m h3pipeline instancias                     # qué tenés prendido
    python -m h3pipeline destruir <id>                  # borra y deja de cobrar

El camino corto, de punta a punta:

    python -m h3pipeline alquilar mi-video/proyecto.json --si --generar

elige la máquina más barata que cumple (4 placas de >=32 GB, por costo total
del trabajo), la alquila, instala H3 y lanza la generación, todo solo. Después
`seguir` hasta que estén todos, `bajar`, y SIEMPRE `destruir`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import (costos, empaquetar as emp, estructura as est, frames, montaje,
               tts as ttsmod, vast, voz as vozmod)
from .config import ConfigFaltante
from .frames import SinCredito
from .estructura import EstructuraInvalida
from .proyecto import Proyecto, ProyectoInvalido

for flujo in (sys.stdout, sys.stderr):
    try:
        flujo.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass


def _p(ruta) -> Proyecto:
    return Proyecto.cargar(ruta)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="h3pipeline", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("estructuras", help="lista las estructuras disponibles")

    for nombre, ayuda in (("brief", "el documento de dirección"),
                          ("construir", "escribe storyboard.json y planos.json"),
                          ("costo", "qué va a salir generarlo")):
        s = sub.add_parser(nombre, help=ayuda)
        s.add_argument("proyecto")

    s = sub.add_parser("frames", help="genera los primeros fotogramas")
    s.add_argument("proyecto")
    s.add_argument("--force", action="store_true", help="rehace los que ya existen")
    s.add_argument("--madre", action="store_true", help="genera los assets madre primero")
    s.add_argument("--motor", choices=("nanobanana", "nanobanana-pro", "openai"),
                   default="nanobanana",
                   help="qué generador usar para los fotogramas de plano "
                        "(nanobanana = Gemini Flash, ~$0,039; nanobanana-pro, ~$0,13)")
    s.add_argument("--motor-madre", choices=("nanobanana", "nanobanana-pro", "openai"),
                   default=None,
                   help="generador de los assets madre; por defecto, el mismo que --motor. "
                        "Las hojas de modelo y las locaciones son las que sostienen la "
                        "identidad: ahí el Pro se paga solo.")
    s.add_argument("--modelo-openai", default=frames.MODELO_OPENAI,
                   help="modelo de OpenAI cuando el motor es openai "
                        "(p. ej. gpt-image-2.5-sunburst)")
    s.add_argument("--hilos", type=int, default=1,
                   help="imágenes en paralelo (OpenAI tarda ~85 s por imagen con referencias)")

    s = sub.add_parser("reescribir", help="escribe el prompt oficial de H3 de cada plano (GPT + validación)")
    s.add_argument("proyecto")
    s.add_argument("--forzar", action="store_true", help="rehacer aunque el pedido no haya cambiado")
    s.add_argument("--solo", nargs="+", metavar="ID")

    s = sub.add_parser("empaquetar", help="arma el ZIP para subir")
    s.add_argument("proyecto")
    s.add_argument("--solo", nargs="+", metavar="ID", help="sólo estos planos (rehacer)")
    s.add_argument("--sin-zip", action="store_true")
    s.add_argument("--sin-reescribir", action="store_true",
                   help="no pasar los prompts por el reescritor antes de empaquetar")

    s = sub.add_parser("gpu", help="busca dónde correrlo")
    s.add_argument("proyecto", nargs="?")
    s.add_argument("--pasos", type=int, default=8)
    s.add_argument("--sin-licencia", action="store_true",
                   help="no filtrar por los países que excluye la licencia de H3")
    s.add_argument("--gpus", type=int, default=vast.GPUS)
    s.add_argument("--vram", type=int, default=vast.VRAM_GB, help="GB por placa")

    s = sub.add_parser("voz", help="densidad y emoción de cada línea hablada")
    s.add_argument("proyecto")
    s.add_argument("--generar", action="store_true",
                   help="sintetiza con ElevenLabs; GASTA CRÉDITOS")
    s.add_argument("--cache", default=None, help="dónde se cachean las tomas")

    s = sub.add_parser("montar", help="arma el MP4 final desde los clips bajados")
    s.add_argument("proyecto")
    s.add_argument("clips")
    s.add_argument("--salida")

    s = sub.add_parser("mezclar", help="el máster: clips + voz en off + música, y subtítulos quemados")
    s.add_argument("proyecto")
    s.add_argument("clips", help="carpeta con los clips bajados (la de `bajar`)")
    s.add_argument("--musica", help="mp3 de la música; default <proyecto>/musica.mp3 si existe")
    s.add_argument("--sin-subtitulos", action="store_true",
                   help="no quemar los subtítulos de la voz en off")
    s.add_argument("--sin-1080", action="store_true", help="largos: no reescalar a 1920×1080")
    s.add_argument("--salida")

    s = sub.add_parser("alquilar", help="alquila una oferta y sube el paquete · COBRA")
    s.add_argument("proyecto")
    s.add_argument("id", type=int, nargs="?",
                   help="id de oferta (el de `gpu`); sin él, elige sola la más "
                        "barata por costo total del trabajo")
    s.add_argument("--si", action="store_true",
                   help="confirma el alquiler; sin esto no hace nada")
    s.add_argument("--disco", type=int, default=vast.DISCO_GB)
    s.add_argument("--generar", action="store_true",
                   help="apenas sube el ZIP, deja la corrida entera andando sola")
    s.add_argument("--pasos", type=int, default=8)
    s.add_argument("--cualquier-gpu", action="store_true",
                   help="permite elegir otra placa que no sea la RTX 5090")
    s.add_argument("--ref2va", action="store_true",
                   help="baja también Ref2VA aunque este paquete no lo use (para la "
                        "etapa siguiente de una muestra en la misma instancia)")

    s = sub.add_parser("generar", help="deja la corrida andando dentro de la instancia")
    s.add_argument("proyecto")
    s.add_argument("id", type=int, help="id de INSTANCIA (el de `instancias`)")
    s.add_argument("--pasos", type=int, default=8)
    s.add_argument("--ref2va", action="store_true", help="baja también Ref2VA")

    s = sub.add_parser("seguir", help="cuántos clips van y qué dicen los logs")
    s.add_argument("proyecto")
    s.add_argument("id", type=int, help="id de instancia")

    s = sub.add_parser("bajar", help="monta en la máquina si falta y baja todo acá")
    s.add_argument("proyecto")
    s.add_argument("id", type=int, help="id de instancia")
    s.add_argument("--destino", help="default: <proyecto>/clips/")
    s.add_argument("--parcial", action="store_true",
                   help="baja lo que haya aunque falten planos")

    sub.add_parser("instancias", help="qué tenés alquilado ahora mismo")

    s = sub.add_parser("destruir", help="borra la instancia y deja de cobrar")
    s.add_argument("id", type=int)
    s.add_argument("--si", action="store_true")

    a = ap.parse_args(argv)

    if a.cmd == "estructuras":
        for n in est.disponibles():
            e = est.Estructura.cargar(n)
            print(f"  {n:<10} {e.formato:<6} {e.duracion_objetivo:>4.0f} s   "
                  f"{len(e.tramos)} tramos: {' '.join(t.id for t in e.tramos)}")
        return 0

    if a.cmd == "instancias":
        print(vast.resumen_instancias())
        return 0

    if a.cmd == "destruir":
        if not a.si:
            print(f"Esto BORRA la instancia {a.id} y todo su disco. No hay vuelta atrás.")
            print("Bajate los archivos primero. Después: --si")
            return 1
        vast.destruir(a.id, confirmar=True)
        print(f"instancia {a.id} destruida · dejaste de pagar")
        return 0

    if a.cmd == "gpu":
        planos = None
        if a.proyecto:
            planos = _p(a.proyecto).construir()[1]["planos"]
        ofertas = vast.buscar(planos=planos, gpus=a.gpus, vram_gb=a.vram,
                              respetar_licencia=not a.sin_licencia, pasos=a.pasos)
        print(vast.tabla(ofertas, planos, a.pasos))
        if ofertas:
            print("\nPara alquilar: elegí el id y usá la web, o desde Python:")
            print(f"  vast.crear({ofertas[0].id}, confirmar=True)   "
                  f"# ${ofertas[0].dph:.3f}/h, empieza a cobrar ya")
        return 0

    p = _p(a.proyecto)

    if a.cmd == "brief":
        print(p.brief())
        return 0

    if a.cmd == "construir":
        p.escribir()
        print()
        print(p.resumen(p.construir()[1]["planos"]))
        return 0

    if a.cmd == "frames":
        sb, _pl = p.construir()
        if a.madre and p.madre:
            print("assets madre:")
            frames.generar_storyboard(
                {"aspecto": p.aspecto, "refs": p.refs_estilo, "assets": p.madre},
                p.raiz / "assets", p.raiz, a.force,
                motor=a.motor_madre or a.motor, modelo_openai=a.modelo_openai,
                hilos=a.hilos)
        print("primeros fotogramas:")
        hechos, bloqueados = frames.generar_storyboard(sb, p.raiz / "assets", p.raiz,
                                                       a.force, motor=a.motor,
                                                       modelo_openai=a.modelo_openai,
                                                       hilos=a.hilos)
        print(f"\n{len(hechos)} dibujos en {p.raiz / 'assets'}")
        if bloqueados:
            print("  bloqueados (reintentá, el filtro es intermitente): "
                  + " ".join(bloqueados))
        return 1 if bloqueados else 0

    if a.cmd == "reescribir":
        from . import reescritor
        n = reescritor.completar(Path(a.proyecto), forzar=a.forzar, solo=a.solo)
        print(f"{n} prompt(s) reescritos")
        return 0

    if a.cmd == "empaquetar":
        if not a.sin_reescribir:
            # Todo prompt que llega a H3 pasa antes por el reescritor: acá ya
            # están los dibujos, así que el primer fotograma se describe de la
            # imagen real. Los planos al día no se tocan.
            from . import reescritor
            print("prompts para H3:")
            n = reescritor.completar(Path(a.proyecto), solo=a.solo)
            print(f"  {n} reescritos, el resto estaba al día")
            p = Proyecto.cargar(Path(a.proyecto))
        emp.empaquetar(p, solo=a.solo, zip_=not a.sin_zip)
        return 0

    if a.cmd == "costo":
        planos = p.construir()[1]["planos"]
        print(costos.comparar(planos))
        print()
        print(costos.estimar(planos))
        return 0

    if a.cmd == "alquilar":
        zip_ = Path(a.proyecto).parent / f"{p.slug}-para-vast.zip"
        if not zip_.exists():
            print(f"!! falta {zip_.name}. Corré antes: "
                  f"python -m h3pipeline empaquetar {a.proyecto}")
            return 1
        planos = p.construir()[1]["planos"]
        if a.id is None:
            # Sin id: la elige el módulo, y POR DEFECTO SÓLO ENTRE 4× RTX 5090.
            # La lección salió cara: la estimación por costo total usa la curva
            # de la 5090, y en la A100 el trabajo rindió ~15 % menos y costó
            # 2,5× lo previsto (COSTOS-H3 §13). Hasta que el estimador sepa
            # distinguir familias, se compara sólo dentro de la familia medida.
            # Si no hay ninguna 5090 disponible, la respuesta es ESPERAR, no
            # alquilar una cara — o pasar --cualquier-gpu a conciencia.
            ofertas = vast.buscar(planos=planos, pasos=a.pasos,
                                  gpu=None if a.cualquier_gpu else "RTX 5090")
            if not ofertas:
                if not a.cualquier_gpu:
                    print("No hay ninguna 4× RTX 5090 disponible ahora mismo.")
                    print("  Lo barato es ESPERAR y volver a probar en un rato.")
                    print("  Para ver qué otras placas hay: --cualquier-gpu "
                          "(la estimación de costo será menos confiable).")
                else:
                    print(vast.tabla(ofertas))
                return 1
            print("Sin id de oferta: va la 4× RTX 5090 de menor costo total."
                  if not a.cualquier_gpu else
                  "Sin id de oferta: va la de menor costo total del trabajo.")
            print(vast.tabla(ofertas, planos, a.pasos, cuantas=3))
            oid = ofertas[0].id
            # Ojo con el nombre: `est` es el módulo estructura, importado arriba.
            estimacion = costos.estimar(planos, ofertas[0].a_maquina(), a.pasos)
        else:
            oid = a.id
            estimacion = costos.estimar(planos)
        print()
        print(f"Oferta {oid} · {zip_.name} ({zip_.stat().st_size / 1e6:.0f} MB)")
        print(f"Estimado del trabajo: {estimacion.minutos_total:.0f} min · "
              f"${estimacion.costo_total:.2f}")
        if not a.si:
            print()
            print("Esto ALQUILA y empieza a cobrar de inmediato. Para confirmar: --si")
            return 1
        print()
        r = vast.crear(oid, confirmar=True, disco_gb=a.disco)
        iid = int(r.get("new_contract") or r.get("id"))
        print(f"instancia {iid} creada")
        # La clave va a la INSTANCIA, no a la cuenta: una API key de team no
        # puede registrar claves de cuenta, y sin clave el SSH ni saluda.
        vast.autorizar_clave(iid)
        print("  clave SSH autorizada en la instancia")
        inst = vast.esperar_lista(iid)
        # El taxímetro: desde acá, `seguir` y `bajar` muestran los dólares
        # acumulados contra el estimado. Un video de 4 min costó $10 el 31/8
        # y nadie vio el reloj hasta el final: nunca más un gasto invisible.
        import time as _t
        (p.raiz / "corrida.json").write_text(json.dumps(
            {"instancia": iid, "dph": float(inst.get("dph_total") or 0),
             "inicio": _t.time(), "estimado": round(estimacion.costo_total, 2)}),
            encoding="utf-8")
        vast.subir(inst, zip_)
        print()
        if a.generar:
            vast.generar(inst, zip_.name, pasos=a.pasos, ref2va=a.ref2va)
            print()
            print("La corrida quedó andando sola. Para seguirla:")
            print(f"  python -m h3pipeline seguir {a.proyecto} {iid}")
            print(f"y cuando estén todos los clips:")
            print(f"  python -m h3pipeline bajar  {a.proyecto} {iid}")
        else:
            print("Ya está arriba. Para dejar la corrida andando sola:")
            print(f"  python -m h3pipeline generar {a.proyecto} {iid}")
            print("o a mano, por SSH:")
            print(f"  {vast.ssh_de(inst)}")
            print(f"  cd /workspace/refs && unzip -o {zip_.name}")
            print("  sed -i 's/\r$//' /workspace/refs/*.sh /workspace/refs/*.py")
            print("  bash /workspace/refs/setup.sh")
            print("  PASOS=8 bash /workspace/refs/lanzar.sh")
        print()
        print(f"CUANDO TERMINES, para dejar de pagar:")
        print(f"  python -m h3pipeline destruir {iid} --si")
        return 0

    if a.cmd == "generar":
        inst = vast.instancia(a.id)
        zip_ = Path(a.proyecto).parent / f"{p.slug}-para-vast.zip"
        # Si el ZIP no está en la máquina (instancia alquilada desde la web,
        # por ejemplo), se sube acá mismo antes de lanzar.
        try:
            vast.ejecutar(inst, f"test -f /workspace/refs/{zip_.name}", timeout=30)
        except vast.ErrorVast:
            if not zip_.exists():
                print(f"!! falta {zip_.name}, ni acá ni en la máquina. Corré antes: "
                      f"python -m h3pipeline empaquetar {a.proyecto}")
                return 1
            vast.subir(inst, zip_)
        vast.generar(inst, zip_.name, pasos=a.pasos, ref2va=a.ref2va)
        print()
        print("Quedó andando sola: setup (~59 GB) y después la generación.")
        print(f"  python -m h3pipeline seguir {a.proyecto} {a.id}")
        return 0

    if a.cmd == "seguir":
        inst = vast.instancia(a.id)
        planos = p.construir()[1]["planos"]
        pr = vast.progreso(inst, planos, p.slug)
        destino_ = Path(a.destino or p.raiz / "clips")
        # Lo que ya está bajado de una corrida anterior no se pide (21/9: la
        # segunda vuelta genera sólo los planos que faltaban).
        faltan = [x["id"] for x in planos if not x.get("clip_de") and x["id"] not in pr["hechos"]
                  and not (destino_.exists() and montaje.buscar_clip(destino_, x["id"]))]
        ya_locales = destino_.exists() and any(montaje.buscar_clip(destino_, x["id"]) for x in planos if not x.get("clip_de"))
        print(f"{len(pr['hechos'])}/{pr['total']} clips"
              + (f" · falta: {' '.join(faltan)}" if faltan else " · TODOS")
              + (" · MP4 final montado" if pr["final"] else ""))
        if pr["logs"]:
            print()
            print(pr["logs"].rstrip())
        print()
        if not faltan:
            print(f"Listo para bajar: python -m h3pipeline bajar {a.proyecto} {a.id}")
        dph = float(inst.get("dph_total") or 0)
        print(f"La instancia sigue cobrando ${dph:.3f}/h hasta que la destruyas.")
        # El taxímetro, si esta corrida lo dejó anotado.
        rj = p.raiz / "corrida.json"
        if rj.exists():
            import time as _t
            r = json.loads(rj.read_text(encoding="utf-8"))
            if int(r.get("instancia", 0)) == a.id:
                gasto = (_t.time() - r["inicio"]) / 3600 * r["dph"]
                print(f"TAXÍMETRO: ${gasto:.2f} acumulados · estimado ${r['estimado']:.2f}")
                if r["estimado"] and gasto > 2 * r["estimado"]:
                    print("  !! YA VA AL DOBLE DEL ESTIMADO. Algo está mal: mirá los logs "
                          "y decidí si seguir o destruir y replantear.")
        return 0

    if a.cmd == "bajar":
        inst = vast.instancia(a.id)
        planos = p.construir()[1]["planos"]
        pr = vast.progreso(inst, planos, p.slug)
        faltan = [x["id"] for x in planos if x["id"] not in pr["hechos"]]
        if faltan and not a.parcial:
            print(f"!! faltan {len(faltan)} planos: {' '.join(faltan)}")
            print("   Miralo con `seguir`, o bajá lo que haya con --parcial.")
            return 1
        if not faltan and not pr["final"] and not ya_locales:
            print("montando en la máquina…")
            print(vast.ejecutar(
                inst, "export PATH=/venv/main/bin:$PATH && "
                      "python /root/runner.py --montar", timeout=900).rstrip())
            pr = vast.progreso(inst, planos, p.slug)
        destino = Path(a.destino or p.raiz / "clips")
        quiero = [x for x in pr["archivos"]
                  if x.endswith((".mp4", ".srt")) or x == "metricas.json"]
        vast.bajar(inst, quiero, destino)
        print(f"{len(quiero)} archivo(s) en {destino}")
        # Control de calidad ANTES de sugerir destruir: el 31/8 una placa
        # defectuosa devolvió once clips de ruido puro y se destruyó la
        # instancia sin mirarlos. Rehacerlos costó otro alquiler.
        ruido = [x["id"] for x in planos
                 if (c := montaje.buscar_clip(destino, x["id"])) and montaje.es_ruido(c)]
        print()
        if ruido:
            print(f"!! {len(ruido)} clip(s) son RUIDO PURO (placa defectuosa): {' '.join(ruido)}")
            print("   NO destruyas todavía. Rehacelos en otra placa:")
            print(f"   python -m h3pipeline empaquetar {a.proyecto} --solo {' '.join(ruido)}")
            print(f"   y subí/generá de nuevo en la instancia, o alquilá otro host.")
            return 2
        print("Los clips pasan el control de ruido. YA BAJASTE TODO. Dejá de pagar:")
        print(f"  python -m h3pipeline destruir {a.id} --si")
        return 0

    if a.cmd == "voz":
        lineas = p.lineas_de_voz()
        if not lineas:
            print("Este proyecto no tiene líneas habladas.")
            return 0
        print(vozmod.tabla(lineas))
        avisos = vozmod.revisar(lineas)
        if avisos:
            print()
            print(f"{len(avisos)} aviso(s) — se arreglan en el TEXTO, no en el audio:")
            for x in avisos:
                print(f"  ⚠ {x}")
        if not a.generar:
            print()
            print("Para sintetizar: agregá --generar (gasta créditos de ElevenLabs).")
            return 0
        # Las líneas «boca» sin voz de ElevenLabs las dice H3 dentro del clip
        # (diálogos en cámara de un largo narrado): no se sintetizan acá.
        lineas = [x for x in lineas if x.tipo == "off" or x.voz_id]
        sin_voz = [x for x in lineas if not x.voz_id]
        if sin_voz:
            print()
            print(f"!! {len(sin_voz)} líneas sin voz asignada. Declará `voces` "
                  f"(personaje → voice_id) en el proyecto.")
            return 1
        print()
        destino = Path(a.cache or p.raiz / "voz")
        r = ttsmod.generar(lineas, destino)
        print()
        print(f"{len(r)} de {len(lineas)} líneas generadas en {destino}")
        return 0

    if a.cmd == "mezclar":
        planos = p.construir()[1]["planos"]
        clips = Path(a.clips)
        faltan = montaje.faltantes(planos, clips)
        if faltan:
            print("!! faltan clips: " + " ".join(faltan))
            return 1
        # 0. Diálogos en cámara (largo narrado, 21/9): la boca manda el corte.
        realces, subs_dlg = [], []
        if any(x.get("dialogo") for x in planos):
            print("diálogos en cámara: midiendo la voz de cada plano hablado…")
            montaje.ajustar_usa_por_voz(planos, clips, idioma=getattr(p, "idioma", "es") or "es")
        # 1. El corte: los clips en orden, recortados a `usa` si hace falta.
        corte = p.raiz / f"{p.slug}-corte.mp4"
        if any(x.get("usa") for x in planos):
            montaje.recortar_y_concatenar(planos, clips, corte)
        else:
            montaje.concatenar(planos, clips, corte)
        # 2. La voz: el mp3 que ganó en cada línea (caché de `voz --generar`,
        #    no vuelve a pagar) con su duración REAL medida, para el SRT.
        lineas = [x for x in p.lineas_de_voz(planos) if x.tipo == "off"]
        if not lineas:
            print("!! el proyecto no tiene voz en off; para diálogo en boca usá `montar`")
            return 1
        voces, subs = [], []
        for x in lineas:
            r = ttsmod.elegir(x, p.raiz / "voz", log=lambda *_a: None)
            if r["tabla"][0]["nuevo"]:
                print(f"  (sintetizada ahora: {x.id})")
            voces.append((x.t, r["mp3"]))
            subs.append((x.t, x.t + r["tabla"][0]["dur"], vozmod.limpiar(r["texto"])))
        if any(x.get("dialogo") for x in planos):
            from . import voz_clip
            lt_ = dict(zip((x["id"] for x in planos), p.estructura_resuelta().linea_de_tiempo(planos)))
            for x in planos:
                v = x.get("voz_medida")
                if not x.get("dialogo") or not v or v.get("fuente") == "nada":
                    continue
                t0 = lt_[x["id"]][0]
                u0 = (x.get("usa") or [0.0])[0]
                realces.append((max(0.0, t0 + v["ini"] - u0 - 0.15), t0 + v["fin"] - u0 + 0.35))
                for a_, b_, texto in voz_clip.lineas_en_tiempo(v, x["dialogo"]):
                    txt = texto.split(":", 1)[1].strip() if ":" in texto[:40] else texto
                    subs_dlg.append((max(t0, t0 + a_ - u0 - 0.1), t0 + b_ - u0 + 0.25, txt))
            subs += subs_dlg
            print(f"  {len(realces)} diálogo(s) en cámara con el audio de H3 al frente")
        # 3. Música, si hay.
        musica_ = Path(a.musica) if a.musica else p.raiz / "musica.mp3"
        musica_ = musica_ if musica_.exists() else None
        # 4. Las tres capas + máster a -14 LUFS.
        salida = Path(a.salida or p.raiz / f"{p.titulo} - final.mp4")
        mezclado = salida if a.sin_subtitulos else salida.with_name(salida.stem + " (sin subs).mp4")
        montaje.mezclar(corte, voces, mezclado, musica=musica_, realces=realces)
        # 5. Los subtítulos de la voz, con los tiempos medidos, quemados.
        srt_ = p.raiz / f"{p.slug}.srt"
        n = montaje.srt_voz(subs, srt_)
        print(f"{n} subtítulos en {srt_.name}")
        if not a.sin_subtitulos:
            # Largos a 1080p: H3 entrega 1344×768 y YouTube lo listaría como 720p.
            montaje.quemar_srt(mezclado, srt_, salida, escala=montaje.ESCALA_1080 if (p.formato == "largo" and not a.sin_1080) else None)
        print(f"\nMÁSTER: {salida}")
        return 0

    if a.cmd == "montar":
        planos = p.construir()[1]["planos"]
        faltan = montaje.faltantes(planos, Path(a.clips))
        if faltan:
            print("!! faltan clips: " + " ".join(faltan))
            return 1
        salida = Path(a.salida or p.raiz / f"{p.slug}.mp4")
        if any(x.get("dialogo") for x in planos):
            print("la boca manda el corte: midiendo la voz de cada clip hablado…")
            idioma = json.loads((p.raiz / "proyecto.json").read_text(encoding="utf-8")).get("idioma", "es") if (p.raiz / "proyecto.json").exists() else "es"
            nc = montaje.ajustar_usa_por_voz(planos, Path(a.clips), idioma=idioma)
            print(f"{nc} corte(s) corridos a la voz")
        if any(x.get("usa") for x in planos):
            montaje.recortar_y_concatenar(planos, Path(a.clips), salida)
        else:
            montaje.concatenar(planos, Path(a.clips), salida)
        n = montaje.srt(planos, salida.with_suffix(".srt"))
        print(f"{n} subtítulos en {salida.with_suffix('.srt').name}")
        if p.voz:
            print("\nFalta ponerle encima, en tu editor:")
            for t, pid, texto in p.guion_de_voz(planos):
                print(f"  {t:6.1f} s  {texto}")
        return 0

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ConfigFaltante, EstructuraInvalida, ProyectoInvalido, vast.ErrorVast,
            montaje.ErrorMontaje, SinCredito, FileNotFoundError) as e:
        # Estos errores son para leer, no para depurar: el traceback no agrega nada.
        print(f"!! {e}", file=sys.stderr)
        raise SystemExit(1)
