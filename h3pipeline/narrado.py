"""EL TRADUCTOR NARRADO: la voz es la columna, los planos la ilustran (regla 40).

El 21/9/2026 el primer largo de 8 minutos («EL CAMIÓN DE MI PADRE») pasó por el
traductor general: GPT devolvió 20 planos (103 s) y UNA línea de voz para un
guion de 4.300 caracteres, tres veces seguidas. Un JSON de 90 planos con toda
la voz en una sola llamada es más de lo que el modelo sostiene. Acá se hace al
revés y por partes:

  1. La voz en off se arma POR CÓDIGO: cada oración del guion es una línea,
     su duración sale de la velocidad medida de la voz (Pablo 10,5 cps), y la
     línea de tiempo se construye sumando. Nada se pierde ni se inventa.
  2. Los planos salen de esa línea de tiempo: uno cada `CORTA` segundos
     (4,7 en línea, 5,17 generados), en orden, con la voz que cae en cada uno.
  3. GPT sólo escribe LO VISUAL, párrafo por párrafo (3-10 planos por llamada):
     tamaño, locación, personajes, `ve`, `mueve`, `audio`, con el reparto fijo
     de la serie y las locaciones ya definidas por los párrafos anteriores.

Entra el guion como lo escribe el guionista de la serie: párrafos de voz en
off con, al final, UNA acotación entre corchetes de qué se ve.
"""
from __future__ import annotations

import json
import math
import re

from . import grilla
from .estructura import Estructura
from .guionista import ErrorGuionista, VOCES, _json, _llamar, densidad_contra_voz
from .proyecto import Proyecto, ProyectoInvalido

# En el largo el plano se usa ENTERO (proyecto._duraciones): el corte es el clip
# completo, 5,17 s. En el short el corte manda (4,7 en línea, 5,17 generados).
CORTA_LARGO, CORTA_SHORT = round(grilla.MINIMO, 3), 4.7
CORTA = CORTA_LARGO             # se fija por formato en traducir_narrado()
SEGUNDOS = round(grilla.MINIMO, 2)   # 5.17 generados
PAUSA_ORACION = 0.25            # s entre oraciones
PAUSA_PARRAFO = 0.7             # s entre párrafos
ARRANQUE = 0.4                  # s antes de la primera palabra
LARGO_MAX_LINEA = 150           # caracteres: más que eso se parte en la coma

TAMANOS = "PGE (extreme wide) · PG (wide) · PA (full shot) · PM (medium) · PP (close-up) · PD (detail)"


def _parrafos(guion: str) -> list[dict]:
    """[{voz, nota}] por párrafo: la voz sin los corchetes, la nota = los corchetes."""
    out = []
    for bloque in re.split(r"\n\s*\n", guion.strip()):
        bloque = bloque.strip()
        if not bloque:
            continue
        notas = re.findall(r"\[([^\]]*)\]", bloque)
        voz = re.sub(r"\[[^\]]*\]", "", bloque)
        voz = re.sub(r"\s+", " ", voz).strip()
        if not voz and not notas:
            continue
        out.append({"voz": voz, "nota": " ".join(n.strip() for n in notas)})
    return out


def _oraciones(texto: str) -> list[str]:
    """Oraciones enteras; las muy largas se partan en una coma o punto y coma."""
    partes = re.split(r"(?<=[.!?…])\s+(?=[“\"¿¡A-ZÁÉÍÓÚÑ0-9])", texto)
    out = []
    for p in partes:
        p = p.strip()
        if not p:
            continue
        # Cierre de comillas o paréntesis que quedó separado
        if out and re.fullmatch(r"[”\")\]]+[.!?…]?", p):
            out[-1] += p
            continue
        while len(p) > LARGO_MAX_LINEA:
            corte = max(p.rfind(", ", 40, LARGO_MAX_LINEA), p.rfind("; ", 40, LARGO_MAX_LINEA), p.rfind(": ", 40, LARGO_MAX_LINEA))
            if corte < 0:
                break
            out.append(p[:corte + 1].strip())
            p = p[corte + 1:].strip()
        out.append(p)
    return out


def linea_de_tiempo(parrafos: list[dict], cps: float) -> tuple[list[dict], float]:
    """[{t, texto, parrafo}] y el total. La duración de cada línea es
    caracteres / cps (medido), más las pausas."""
    lineas, t = [], ARRANQUE
    for k, par in enumerate(parrafos):
        ors = _oraciones(par["voz"])
        for j, o in enumerate(ors):
            lineas.append({"t": round(t, 2), "texto": o, "parrafo": k})
            t += len(o) / cps + PAUSA_ORACION
        if ors:
            t += PAUSA_PARRAFO - PAUSA_ORACION
    return lineas, round(t, 2)


def _planos_vacios(total: float, prefijo: str = "S") -> list[dict]:
    n = max(3, math.ceil((total + 0.6) / CORTA))
    return [{"id": f"{prefijo}{i + 1:02d}", "corta": CORTA, "segundos": SEGUNDOS, "desde": round(i * CORTA, 2)} for i in range(n)]


def _texto_en_plano(lineas: list[dict], desde: float, hasta: float, cps: float) -> str:
    """Qué palabras de la voz se oyen durante ese plano (aproximado, por proporción)."""
    trozos = []
    for l in lineas:
        dur = len(l["texto"]) / cps
        a, b = l["t"], l["t"] + dur
        if b <= desde or a >= hasta:
            continue
        palabras = l["texto"].split()
        if not palabras:
            continue
        i0 = int(max(0.0, (desde - a) / dur) * len(palabras))
        i1 = int(min(1.0, (hasta - a) / dur) * len(palabras) + 0.999)
        trozos.append(" ".join(palabras[i0:i1]))
    return " ".join(x for x in trozos if x)


def _pedido_parrafo(k: int, par: dict, planos: list[dict], lineas: list[dict], cps: float, est: Estructura,
                    reparto: dict, locaciones: dict, estilo_imagen: str, medio: str, notas: str, total_parrafos: int) -> str:
    ids = [p["id"] for p in planos]
    desc_planos = []
    for p in planos:
        tr = est.tramo_en(p["desde"] + 0.1)
        desc_planos.append(f"- {p['id']} ({p['desde']:.1f}-{p['desde'] + CORTA:.1f} s, tramo {tr.id if tr else '?'}): se oye «{_texto_en_plano(lineas, p['desde'], p['desde'] + CORTA, cps)}»")
    pers = "\n".join(f"  - id `{pid}`: {v['descripcion']}" for pid, v in (reparto.get("personajes") or {}).items())
    locs = "\n".join(f"  - id `{lid}`: {v['descripcion']}" for lid, v in locaciones.items()) or "  (ninguna todavía)"
    tramos = ", ".join(sorted({(est.tramo_en(p["desde"] + 0.1).objetivo or est.tramo_en(p["desde"] + 0.1).id) for p in planos if est.tramo_en(p["desde"] + 0.1)}))
    return (
        f"Sos director de fotografía y de arte de un video narrado (voz en off continua) en {medio or 'live-action film'}. "
        f"Estilo visual (idéntico en todo el video): {estilo_imagen}\n"
        f"Este es el PÁRRAFO {k + 1} de {total_parrafos} del guion. La voz en off dice, en este orden:\n«{par['voz']}»\n"
        + (f"El guionista indicó qué se ve: {par['nota']}\n" if par["nota"] else "")
        + f"Función narrativa de estos planos: {tramos}\n\n"
        f"REPARTO FIJO (usá SÓLO estos ids en `personajes`; nadie más tiene cara; la gente extra va como figuras de fondo sin id):\n{pers}\n\n"
        f"LOCACIONES YA DEFINIDAS (reusá el id si es el mismo lugar; si hace falta un lugar nuevo, definilo en `locaciones_nuevas`):\n{locs}\n\n"
        f"Escribí exactamente estos {len(planos)} planos, de {CORTA} s cada uno, en este orden; cada uno ilustra lo que se oye en ese momento:\n"
        + "\n".join(desc_planos) + "\n\n"
        "REGLAS:\n"
        f"- `tipo`: {TAMANOS}. Este género vive de caras: emociones en PM/PA; PP sólo en el pico del párrafo; PD para objetos clave (llaves, lata, cheque). "
        "Dos planos seguidos NUNCA con el mismo tipo + misma locación + mismos personajes (eso es un salto, no un corte).\n"
        "- `ve` es una FOTO (el primer fotograma), en inglés: tamaño en mayúsculas, quién está y dónde, con su ropa, qué hace, luz, 2-3 objetos concretos. "
        "Sin texto ni carteles legibles salvo que la nota lo pida. Sin el nombre del personaje: la hoja de modelo pone la cara; describilo por su ropa y su cuerpo.\n"
        "- `mueve`: qué pasa DESPUÉS de esa foto durante 5 s (sujeto → entorno → cámara), en inglés, una acción visible, sin diálogo (la voz va encima).\n"
        "- `audio`: tres capas `[SFX] … [Ambient] … [Foley] …`, sólo lo que nace y muere en el plano; NUNCA voces ni palabras.\n"
        "- `personajes`: lista de ids del reparto que se VEN en el plano (puede ser vacía). `loc`: id de locación.\n"
        "- `funcion`: una frase en castellano de qué cuenta este plano.\n"
        "- `interrupcion`: true sólo si cambia el régimen (luz nueva, lugar nuevo, sonido que aparece).\n"
        "- LOCACIONES: reusá las ya definidas siempre que sea el mismo lugar (el mismo lugar con otra luz u otra hora es LA MISMA locación: la luz va en `ve`). "
        "Como mucho UNA locación nueva por párrafo, y sólo si la historia cambia de lugar de verdad.\n"
        "- Locaciones nuevas: id en minúsculas con guion bajo; `descripcion` en inglés (lugar sin gente, luz, materiales, época); `prompt` en inglés para dibujar UNA imagen del lugar vacío en 16:9, con el estilo visual.\n"
        + (f"- Notas del director: {notas}\n" if notas.strip() else "")
        + "\nDevolvé JSON: {\"locaciones_nuevas\": {\"id\": {\"descripcion\": \"…\", \"prompt\": \"…\"}}, "
          "\"planos\": [{\"id\": \"S01\", \"tipo\": \"PM\", \"loc\": \"id\", \"personajes\": [\"id\"], \"ve\": \"…\", \"mueve\": \"…\", \"audio\": \"…\", \"funcion\": \"…\", \"interrupcion\": false}]}"
        f"\nLos ids de los planos tienen que ser exactamente: {', '.join(ids)}."
    )


def traducir_narrado(guion: str, *, formato: str, estructura: str, estilo_imagen: str, estilo_video: str = "",
                     cierre_video: str = "", medio: str = "", voz: str = "pablo", titulo: str = "", notas: str = "",
                     duracion: float | None = None, reparto: dict | None = None, log=print, por_llamada: int = 1) -> dict:
    """Guion narrado → proyecto. Devuelve {"proyecto", "avisos", "intentos", "instruccion", "total_voz"}."""
    if voz not in VOCES:
        raise ErrorGuionista(f"voz {voz!r} desconocida")
    global CORTA
    CORTA = CORTA_LARGO if formato == "largo" else CORTA_SHORT
    cps = VOCES[voz]["cps"]
    reparto = reparto or {"personajes": {}, "locaciones": {}}
    parrafos = _parrafos(guion)
    if not parrafos:
        raise ErrorGuionista("el guion no tiene párrafos de voz")
    lineas, total = linea_de_tiempo(parrafos, cps)
    planos = _planos_vacios(total, "P" if formato == "largo" else "S")
    dur_video = round(len(planos) * CORTA, 2)
    log(f"voz en off: {len(lineas)} líneas · {sum(len(l['texto']) for l in lineas)} caracteres · {total:.0f} s a {cps} cps → "
        f"{len(planos)} planos de {CORTA} s = {dur_video:.0f} s" + (f" (pedido: {duracion:.0f} s)" if duracion else ""))
    if duracion and dur_video > duracion * 1.15:
        log(f"  aviso: la voz pide {dur_video:.0f} s y el capítulo era de {duracion:.0f}: el video dura lo que dura la voz")
    est = Estructura.cargar(estructura)
    if abs(est.duracion_objetivo - dur_video) > 0.01:
        est = est.con_duracion(dur_video)
    # Qué planos le tocan a cada párrafo: el plano pertenece al párrafo cuya voz
    # suena cuando el plano arranca (o el último que empezó antes).
    inicio_parrafo = {}
    for l in lineas:
        inicio_parrafo.setdefault(l["parrafo"], l["t"])
    def parrafo_de(t: float) -> int:
        k = 0
        for kk, t0 in sorted(inicio_parrafo.items()):
            if t0 <= t + 0.6:
                k = kk
        return k
    por_parrafo: dict[int, list[dict]] = {}
    for p in planos:
        por_parrafo.setdefault(parrafo_de(p["desde"]), []).append(p)
    locaciones: dict[str, dict] = {lid: {"imagen": v["imagen"], "descripcion": v["descripcion"]} for lid, v in (reparto.get("locaciones") or {}).items()}
    madre_locs: list[dict] = []
    salida_planos: list[dict] = []
    llamadas = 0
    grupos = sorted(por_parrafo.items())
    i = 0
    while i < len(grupos):
        lote = grupos[i:i + por_llamada]
        i += por_llamada
        for k, ps in lote:
            par = parrafos[k]
            ins = _pedido_parrafo(k, par, ps, lineas, cps, est, reparto, locaciones, estilo_imagen, medio, notas, len(parrafos))
            mensajes = [{"role": "system", "content": "Sos director de fotografía de un video narrado con IA. Respondés sólo JSON, en el formato pedido."},
                        {"role": "user", "content": ins}]
            r = None
            for intento in range(1, 4):
                llamadas += 1
                try:
                    r = _json(_llamar(mensajes))
                except (ErrorGuionista, ValueError) as e:
                    log(f"  párrafo {k + 1}: intento {intento} sin JSON válido ({e})")
                    continue
                devueltos = {x.get("id"): x for x in (r.get("planos") or []) if isinstance(x, dict)}
                faltan = [p["id"] for p in ps if p["id"] not in devueltos]
                if faltan:
                    log(f"  párrafo {k + 1}: intento {intento} faltan {', '.join(faltan)}")
                    mensajes.append({"role": "assistant", "content": json.dumps(r, ensure_ascii=False)})
                    mensajes.append({"role": "user", "content": f"Faltan los planos {', '.join(faltan)}. Devolvé el JSON completo con TODOS los planos pedidos."})
                    r = None
                    continue
                break
            if r is None:
                raise ErrorGuionista(f"el párrafo {k + 1} no se pudo traducir a planos")
            for lid, v in (r.get("locaciones_nuevas") or {}).items():
                lid2 = re.sub(r"[^a-z0-9_]+", "_", str(lid).lower()).strip("_") or f"loc_{len(locaciones) + 1}"
                if lid2 not in locaciones and isinstance(v, dict):
                    locaciones[lid2] = {"imagen": f"l_{lid2}", "descripcion": str(v.get("descripcion", "")).strip()}
                    madre_locs.append({"id": f"l_{lid2}", "aspecto": "16:9" if formato == "largo" else "9:16", "refs": [],
                                       "prompt": (str(v.get("prompt", "")).strip() or locaciones[lid2]["descripcion"]) + f" {estilo_imagen}"})
            devueltos = {x.get("id"): x for x in r["planos"] if isinstance(x, dict)}
            for p in ps:
                x = devueltos[p["id"]]
                pers = [q for q in (x.get("personajes") or []) if q in (reparto.get("personajes") or {})]
                loc = str(x.get("loc") or "").strip()
                loc = re.sub(r"[^a-z0-9_]+", "_", loc.lower()).strip("_")
                if loc not in locaciones:
                    loc = next(iter(locaciones), None)
                tipo = str(x.get("tipo") or "PM").upper()
                if tipo not in ("PGE", "PG", "PA", "PM", "PP", "PD"):
                    tipo = "PM"
                refs = ([f"l_{loc}"] if loc else []) + [f"m_{q}" for q in pers]
                tr = est.tramo_en(p["desde"] + 0.1)
                salida_planos.append({"id": p["id"], "tipo": tipo, "tramo": tr.id if tr else None, "corta": CORTA, "segundos": SEGUNDOS,
                                      "loc": loc, "personajes": pers, "refs": refs, "funcion": str(x.get("funcion") or "").strip(), "texto": "",
                                      "ve": str(x.get("ve") or "").strip(), "mueve": str(x.get("mueve") or "").strip(),
                                      "audio": str(x.get("audio") or "").strip(), **({"interrupcion": True} if x.get("interrupcion") else {})})
            log(f"  párrafo {k + 1}/{len(parrafos)}: {len(ps)} plano(s) · {len(locaciones)} locaciones")
    salida_planos.sort(key=lambda p: p["id"])
    # La voz: cada línea anclada al plano donde arranca, con su offset.
    voz_lista = []
    for l in lineas:
        idx = min(len(planos) - 1, int(l["t"] // CORTA))
        voz_lista.append({"plano": planos[idx]["id"], "offset": round(l["t"] - planos[idx]["desde"], 2), "texto": l["texto"]})
    d = {"titulo": titulo or "SIN TÍTULO", "formato": formato, "estructura": estructura, "duracion_objetivo": dur_video,
         "_concepto": parrafos[0]["voz"][:300], "estilo_imagen": estilo_imagen, "estilo_video": estilo_video, "cierre_video": cierre_video,
         "medio": medio or "live-action film", "solo_sonidos": "", "negativos": True, "idioma": "es",
         "voces": {"narrador": VOCES[voz]["id"]},
         "personajes": {pid: {"hoja": v["hoja"], "descripcion": v["descripcion"]} for pid, v in (reparto.get("personajes") or {}).items()
                        if any(pid in p["personajes"] for p in salida_planos)},
         "locaciones": {lid: v for lid, v in locaciones.items() if any(p["loc"] == lid for p in salida_planos)},
         "madre": [m for m in madre_locs if any(p["loc"] == m["id"][2:] for p in salida_planos)],
         "planos": salida_planos, "voz": voz_lista}
    try:
        pr = Proyecto.desde_dict(d)
        avisos = pr.validar() + densidad_contra_voz(pr, cps)
    except (ProyectoInvalido, KeyError, TypeError, ValueError) as e:
        raise ErrorGuionista(f"el proyecto no carga: {e}")
    return {"proyecto": d, "avisos": avisos, "intentos": llamadas, "instruccion": "narrado: voz por código, planos por párrafo", "total_voz": total}
