"""SERIES: producción en masa. La unidad deja de ser «un video» y pasa a ser
**la serie**: personajes fijos con su hoja de modelo, locaciones, un estilo, una
idea, una voz; y de ahí una lista de capítulos que se escriben, se dibujan, se
empaquetan y entran a la cola, reusando todo lo que ya hace La Fábrica.

Lo que fijó el usuario (18/9/2026):
  - vos aprobás la lista de capítulos y cada guion; dibujos y paquete salen solos;
  - personajes por texto (GPT dibuja la hoja) o por imagen de referencia;
  - continuidad por serie: antología (capítulos sueltos) o serial (el N sabe del N-1);
  - un formato por serie: short, largo o music video;
  - un narrador fijo por serie (Pablo o Kate) o sin voz;
  - en music video cada capítulo compone otra pista del mismo género y otra
    escena del mismo universo;
  - la cantidad de capítulos por tanda la elegís al planificar (5 a 50).

Dónde vive: `mis-videos/_series/<slug>/serie.json` + `assets/` (hojas `m_<id>.png`
y locaciones `l_<id>.png`, que se copian a cada capítulo para que las caras no
cambien entre videos) + `refs/` (imágenes de referencia subidas).

Cada capítulo producido es un proyecto normal en `mis-videos/<serie>-<nn>-<titulo>/`
con su guion.json, proyecto.json, voz, dibujos y ZIP: se sigue en `#/p/<slug>`
y se genera con la cola. Lo que gasta API (GPT, ElevenLabs, imágenes) corre como
tarea después de que apretás; lo que gasta GPU, la cola con su confirmación.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .. import config, frames, grilla, guionista, reescritor, web
from ..estructura import Estructura
from ..proyecto import Proyecto
from . import cola, maquina

DIR = maquina.MIS / "_series"
FORMATOS = {"short": "short-15", "largo": "recap", "musica": "loop"}
ESTADOS_CAP = ("propuesto", "aprobado", "escribiendo", "guion", "produciendo", "producido", "error", "descartado")
ACTIVOS_CAP = ("escribiendo", "produciendo")


# ───────────────────────────────────────────────────────────── archivo

def _slug(t: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", t.lower().replace("ñ", "n")).strip("-")
    return s[:40] or "serie"


def _id(t: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", t.lower().replace("ñ", "n")).strip("_")
    return s[:24] or "x"


def carpeta(slug: str) -> Path:
    return DIR / slug


def leer(slug: str) -> dict:
    """Con dos reintentos cortos: en Render el disco persistente se vuelve a
    montar en cada redeploy y un pedido que cae en ese segundo veía «no existe
    esa serie» (18/9). Un archivo a medio escribir también se reintenta."""
    f = carpeta(slug) / "serie.json"
    for intento in range(3):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            if intento == 2:
                break
            time.sleep(0.4)
    raise KeyError(slug)


def guardar(s: dict) -> dict:
    c = carpeta(s["slug"])
    c.mkdir(parents=True, exist_ok=True)
    tmp = c / "serie.json.tmp"
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(c / "serie.json")           # atómico: nunca se lee un JSON a medias
    return s


def listar() -> list[dict]:
    out = []
    if not DIR.exists():
        return out
    for f in sorted(DIR.glob("*/serie.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        caps = s.get("capitulos", [])
        out.append({"slug": s["slug"], "titulo": s["titulo"], "formato": s["formato"], "creado": s.get("creado"),
                    "personajes": len(s.get("personajes", {})), "capitulos": len(caps),
                    "producidos": len([c for c in caps if c["estado"] == "producido"]),
                    "aprobados": len([c for c in caps if c["estado"] in ("aprobado", "guion")])})
    return out


def crear(titulo: str, formato: str, idea: str, *, estructura: str | None = None, duracion: float | None = None,
          voz: str | None = "pablo", estilo: int | None = 0, estilo_libre: str = "", continuidad: str = "antologia",
          musica: dict | None = None, modo: str = "narrado", toma: str | None = None) -> dict:
    """`modo`: «narrado» (una voz en off fija cuenta; los personajes hablan poco) o
    «actuado» (sin narrador: cada personaje dice sus líneas en cámara y las
    genera H3 dentro del clip). `toma` (shorts): «una» = TOMAS DE 15 s, cada
    una un clip continuo con su bloque de diálogo adentro (1 toma = 15 s,
    2 = 30, 3 = 45, 4 = 60; `duracion` lo dice); el corte cae entre tomas,
    nunca en medio de una frase (pedido del usuario, 20/9: con planos de 4 s
    cada línea salía cortada y no se entendía nada). «cortes» = planos de 5,17 s
    editados, lo de siempre para narrado."""
    if formato not in FORMATOS:
        raise ValueError("formato: short, largo o musica")
    if modo not in ("narrado", "actuado"):
        modo = "narrado"
    if modo == "actuado":
        voz = None
    if toma not in ("una", "cortes"):
        toma = "una" if (modo == "actuado" and formato == "short") else "cortes"
    if formato != "short":
        toma = "cortes"
    if toma == "una":
        n = max(1, min(4, int(round(float(duracion or grilla.MAXIMO) / grilla.MAXIMO))))
        duracion = round(n * grilla.MAXIMO, 3)
    slug = _slug(titulo)
    if (carpeta(slug) / "serie.json").exists():
        raise ValueError(f"ya existe la serie {slug}")
    est = web.ESTILOS[estilo] if estilo is not None and 0 <= estilo < len(web.ESTILOS) else None
    imagen = (estilo_libre.strip() or (est["prompt"] if est else "")).strip()
    if not imagen:
        raise ValueError("falta el estilo visual")
    if formato == "musica":
        voz = None
    s = {"slug": slug, "titulo": titulo.strip(), "creado": time.time(), "formato": formato,
         "estructura": estructura or FORMATOS[formato],
         "duracion": duracion if duracion else (5.167 if formato == "musica" else None),
         "toma": toma,
         "voz": voz if voz in guionista.VOCES else None,
         "estilo": {"preset": estilo if est else None, "libre": estilo_libre.strip(), "imagen": imagen,
                    "video": est["cabecera"] if est else "", "cierre": est["cierre"] if est else "",
                    "medio": est["medio"] if est else ""},
         "modo": modo if formato != "musica" else "narrado",
         "idea": idea.strip(), "continuidad": continuidad if continuidad in ("antologia", "serial") else "antologia",
         "musica": {"genero": (musica or {}).get("genero", "lofi"), "tipo": (musica or {}).get("tipo", ""),
                    "duracion": int((musica or {}).get("duracion", 180))} if formato == "musica" else None,
         "personajes": {}, "locaciones": {}, "capitulos": [], "notas": ""}
    return guardar(s)


def actualizar(slug: str, **campos) -> dict:
    s = leer(slug)
    for k, v in campos.items():
        if k == "estilo" and isinstance(v, dict):
            est = web.ESTILOS[v["preset"]] if v.get("preset") is not None and 0 <= v["preset"] < len(web.ESTILOS) else None
            imagen = (v.get("libre", "").strip() or (est["prompt"] if est else "")).strip()
            if imagen:
                s["estilo"] = {"preset": v.get("preset") if est else None, "libre": v.get("libre", "").strip(), "imagen": imagen,
                               "video": est["cabecera"] if est else "", "cierre": est["cierre"] if est else "", "medio": est["medio"] if est else ""}
        elif k == "modo" and v in ("narrado", "actuado"):
            s["modo"] = v
            if v == "actuado":
                s["voz"] = None
        elif k == "toma" and v in ("una", "cortes") and s["formato"] == "short":
            s["toma"] = v
            if v == "una":
                n = max(1, min(4, int(round(float(s.get("duracion") or grilla.MAXIMO) / grilla.MAXIMO))))
                s["duracion"] = round(n * grilla.MAXIMO, 3)
            else:
                s["duracion"] = None
        elif k in ("titulo", "idea", "notas", "continuidad", "estructura", "voz", "duracion", "musica"):
            s[k] = v
    return guardar(s)


def borrar(slug: str) -> None:
    s = leer(slug)
    if any(c["estado"] in ACTIVOS_CAP for c in s["capitulos"]):
        raise RuntimeError("hay un capítulo en curso")
    shutil.rmtree(carpeta(slug), ignore_errors=True)


# ───────────────────────────────────────────────────────────── GPT

def _gpt(instruccion: str, sistema: str, log=print) -> dict:
    """Una llamada que devuelve JSON, con un reintento si no parsea."""
    mensajes = [{"role": "system", "content": sistema}, {"role": "user", "content": instruccion}]
    for intento in (1, 2):
        log(f"  · llamada {intento} a OpenAI ({guionista.MODELO})…")
        crudo = guionista._llamar(mensajes)
        try:
            return guionista._json(crudo)
        except Exception as e:
            if intento == 2:
                raise RuntimeError(f"la respuesta no es JSON: {e}")
            mensajes.append({"role": "assistant", "content": crudo})
            mensajes.append({"role": "user", "content": "Eso no es JSON válido. Devolvé ÚNICAMENTE el JSON."})
    raise RuntimeError("sin respuesta")


def biblia(s: dict) -> str:
    """La serie contada para GPT: lo que no cambia entre capítulos."""
    L = [f"SERIE: «{s['titulo']}» · formato {s['formato']} · estructura {s['estructura']}"
         + (f" · {s['duracion']:g} s" if s.get("duracion") else ""),
         f"IDEA GENERAL: {s['idea']}",
         f"CONTINUIDAD: {'serial (cada capítulo continúa al anterior)' if s['continuidad'] == 'serial' else 'antología (capítulos independientes, mismo universo)'}",
         f"ESTILO VISUAL: {s['estilo']['imagen']}"]
    if s.get("toma") == "una":
        n = tomas_de(s)
        L.append(f"TOMAS DE 15 SEGUNDOS: cada capítulo son {n} toma{'s' if n > 1 else ''} continua{'s' if n > 1 else ''} de 15 s "
                 f"({round(n * 15)} s en total), cámara casi fija en cada una, y el corte sólo entre tomas. "
                 + ("Sin narrador: los personajes hablan en cámara, 3 a 4 líneas cortas por toma, uno o dos personajes que se turnan. "
                    if s.get("modo") == "actuado" else "")
                 + "La historia entera tiene que entenderse sola: planteo, giro y remate.")
    elif s.get("modo") == "actuado":
        L.append("MODO ACTUADO: no hay narrador. Los personajes hablan en cámara, en castellano rioplatense, "
                 "una línea corta por plano (máximo 12 palabras), un solo personaje hablando por plano. "
                 "Las reacciones en silencio también cuentan como planos.")
    elif s.get("voz"):
        v = guionista.VOCES[s["voz"]]
        L.append(f"VOZ EN OFF: {v['nombre']}, un solo narrador en toda la serie.")
    else:
        L.append("SIN voz en off: cargan la imagen, el sonido y el texto en pantalla.")
    if s.get("musica"):
        L.append(f"MÚSICA: género {s['musica']['genero']}; {s['musica'].get('tipo') or 'instrumental'}; pistas de {s['musica']['duracion']} s.")
    if s["personajes"]:
        L.append("PERSONAJES (id → cómo son; usá estos ids exactos):")
        for pid, p in s["personajes"].items():
            L.append(f"  - {pid}: {p['nombre']}. {p.get('descripcion_es') or p['descripcion']}"
                     + (f" Voz: {p['voz']}" if s.get("modo") == "actuado" and p.get("voz") else ""))
    if s["locaciones"]:
        L.append("LOCACIONES (id → qué son):")
        for lid, l in s["locaciones"].items():
            L.append(f"  - {lid}: {l['nombre']}. {l.get('descripcion_es') or l['descripcion']}")
    if s.get("notas"):
        L.append(f"NOTAS DEL DIRECTOR: {s['notas']}")
    return "\n".join(L)


# ───────────────────────────────────────────────────────────── personajes y locaciones

def tomas_de(s: dict) -> int:
    """Cuántas tomas de 15 s tiene cada capítulo (1 a 4) cuando `toma` es «una»."""
    if s.get("toma") != "una":
        return 0
    return max(1, min(4, int(round(float(s.get("duracion") or grilla.MAXIMO) / grilla.MAXIMO))))


def agregar_personaje(slug: str, nombre: str, descripcion: str, b64: str | None = None, log=print) -> dict:
    """Alta de un personaje. La descripción se escribe en castellano; GPT la pasa
    a la descripción en inglés que el pipeline inyecta en TODOS los prompts
    (vestuario completo: la hoja sostiene la cara, el texto sostiene la ropa)."""
    s = leer(slug)
    if not nombre.strip() or len(descripcion.strip()) < 10:
        raise ValueError("nombre y una descripción de al menos diez caracteres")
    pid = _id(nombre)
    if pid in s["personajes"]:
        raise ValueError(f"ya hay un personaje con id {pid}")
    r = _gpt(
        f"Personaje de una serie de videos generados con IA.\n{biblia(s)}\n\n"
        f"NOMBRE: {nombre.strip()}\nDESCRIPCIÓN DEL DIRECTOR (castellano): {descripcion.strip()}\n\n"
        "Devolvé JSON con:\n"
        "- \"descripcion\": UNA frase en inglés, 30-60 palabras, que empiece con el nombre y diga edad aparente, "
        "cuerpo, cara, pelo, y el VESTUARIO base concreto (prendas, colores) que va a llevar en toda la serie. Es lo que se "
        "pega en cada prompt para que no cambie entre planos. Sin adjetivos vagos. REGLA: si por la idea de la serie o por "
        "la descripción del director la ropa cambia según el capítulo (oficios distintos, disfraces, uniformes), el vestuario "
        "base es NEUTRO y básico (por ejemplo una remera lisa y un jean) y SIN accesorios de oficio (nada de credenciales, "
        "guardapolvos, herramientas): la ropa de cada capítulo se agrega después, capítulo por capítulo. La hoja de modelo "
        "sostiene la cara; el texto de cada capítulo sostiene la ropa.\n"
        "- \"descripcion_es\": la misma, en castellano, para mostrarla.\n"
        "- \"voz\": cómo suena si habla (una frase en inglés: edad, timbre, ritmo, acento).",
        "Sos director de arte de una serie. Respondés sólo JSON.", log=log)
    ref = None
    if b64:
        from PIL import Image
        import io
        (carpeta(slug) / "refs").mkdir(parents=True, exist_ok=True)
        if "," in b64[:64]:
            b64 = b64.split(",", 1)[1]
        im = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        im.thumbnail((1536, 1536))
        f = carpeta(slug) / "refs" / f"{pid}.png"
        im.save(f, "PNG")
        ref = f"refs/{pid}.png"
    s["personajes"][pid] = {"nombre": nombre.strip(), "pedido": descripcion.strip(),
                            "descripcion": str(r.get("descripcion", "")).strip(), "descripcion_es": str(r.get("descripcion_es", "")).strip(),
                            "voz": str(r.get("voz", "")).strip(), "imagen_ref": ref, "hoja": None, "aprobada": False, "creado": time.time()}
    return guardar(s)


def quitar_personaje(slug: str, pid: str) -> dict:
    s = leer(slug)
    p = s["personajes"].pop(pid, None)
    if p:
        for k in ("hoja", "imagen_ref"):
            if p.get(k):
                (carpeta(slug) / p[k]).unlink(missing_ok=True)
    return guardar(s)


def aprobar_personaje(slug: str, pid: str, aprobada: bool = True) -> dict:
    s = leer(slug)
    if pid not in s["personajes"]:
        raise KeyError(pid)
    s["personajes"][pid]["aprobada"] = bool(aprobada)
    return guardar(s)


def editar_personaje(slug: str, pid: str, **campos) -> dict:
    s = leer(slug)
    p = s["personajes"].get(pid)
    if not p:
        raise KeyError(pid)
    for k in ("nombre", "descripcion", "descripcion_es", "voz"):
        if k in campos and campos[k] is not None:
            p[k] = str(campos[k]).strip()
    return guardar(s)


def agregar_locacion(slug: str, nombre: str, descripcion: str, log=print) -> dict:
    s = leer(slug)
    lid = _id(nombre)
    if lid in s["locaciones"]:
        raise ValueError(f"ya hay una locación con id {lid}")
    r = _gpt(
        f"Locación fija de una serie de videos generados con IA.\n{biblia(s)}\n\nNOMBRE: {nombre.strip()}\n"
        f"DESCRIPCIÓN DEL DIRECTOR (castellano): {descripcion.strip()}\n\nDevolvé JSON con \"descripcion\" (una frase en inglés, "
        "15-30 palabras: qué lugar es, luz, época, lo que lo hace reconocible; SIN gente) y \"descripcion_es\" (en castellano).",
        "Sos director de arte. Respondés sólo JSON.", log=log)
    s["locaciones"][lid] = {"nombre": nombre.strip(), "pedido": descripcion.strip(),
                            "descripcion": str(r.get("descripcion", "")).strip(), "descripcion_es": str(r.get("descripcion_es", "")).strip(),
                            "imagen": None, "creado": time.time()}
    return guardar(s)


def quitar_locacion(slug: str, lid: str) -> dict:
    s = leer(slug)
    l = s["locaciones"].pop(lid, None)
    if l and l.get("imagen"):
        (carpeta(slug) / l["imagen"]).unlink(missing_ok=True)
    return guardar(s)


def aspecto(s: dict) -> str:
    return "16:9" if s["formato"] in ("largo", "musica") else "9:16"


def prompt_hoja(s: dict, p: dict) -> str:
    """La hoja de modelo: el mismo molde que usan los proyectos hechos (LOCO DEL
    CARBÓN): fondo gris liso, luz pareja, de las rodillas para arriba, todo
    legible. Con imagen de referencia se pide la MISMA persona."""
    vertical = aspecto(s) == "9:16"
    medio = s["estilo"].get("medio") or "live-action film"
    base = ("Photorealistic character reference photograph" if "live" in medio.lower() or "photo" in medio.lower()
            else f"Character reference sheet in the style of {medio}")
    ref = (" The character must be the SAME individual as in the reference image: same face, same features, same fur or hair, "
           "same body; keep the identity exactly. Only the clothing described here changes: dress the character exactly as "
           "described and do not keep any garment from the reference image that is not described." if p.get("imagen_ref") else "")
    return (f"{base}, {'vertical' if vertical else 'horizontal'} frame, plain dark grey background, even soft lighting. "
            f"{p['descripcion']} Shown from the knees up, neutral stance, facing camera, hands visible.{ref} "
            f"Every detail sharp and readable: this is the reference for every other shot. "
            f"Style: {s['estilo']['imagen']} This is a single film frame, not a poster: no text, no borders, no titles, no watermark.")


def prompt_locacion(s: dict, l: dict) -> str:
    vertical = aspecto(s) == "9:16"
    return (f"Establishing shot, {'vertical' if vertical else 'horizontal'} frame. {l['descripcion']} No people. "
            f"Style: {s['estilo']['imagen']} This is a single film frame, not a poster: no text, no borders, no titles, no watermark.")


def generar_hojas(slug: str, ids: list[str] | None = None, motor: str = "openai", rehacer: bool = False, log=print) -> dict:
    """Dibuja las hojas de modelo (y las locaciones) que faltan. OpenAI por
    defecto (nano banana sin créditos, 16/9). Cuesta una imagen por asset."""
    s = leer(slug)
    c = carpeta(slug)
    (c / "assets").mkdir(parents=True, exist_ok=True)
    clave = config.leer_env("OPENAI_API_KEY") if motor == "openai" else config.leer_env("nanobanana")
    asp = aspecto(s)
    tareas_ = []
    for pid, p in s["personajes"].items():
        if ids and pid not in ids:
            continue
        salida = c / "assets" / f"m_{pid}.png"
        if salida.exists() and not rehacer:
            continue
        refs = [c / p["imagen_ref"]] if p.get("imagen_ref") else []
        tareas_.append(("personaje", pid, prompt_hoja(s, p), refs, salida))
    for lid, l in s["locaciones"].items():
        if ids and lid not in ids:
            continue
        salida = c / "assets" / f"l_{lid}.png"
        if salida.exists() and not rehacer:
            continue
        tareas_.append(("locacion", lid, prompt_locacion(s, l), [], salida))
    if not tareas_:
        log("nada que dibujar: todas las hojas existen")
        return s
    for tipo, xid, prompt, refs, salida in tareas_:
        t0 = time.time()
        log(f"  · {tipo} {xid} …")
        if salida.exists():
            resp = c / "assets" / "_rehechas"
            resp.mkdir(exist_ok=True)
            shutil.move(str(salida), str(resp / f"{salida.stem}-{int(time.time())}.png"))
        try:
            if motor == "openai":
                datos = frames.generar_openai(prompt, refs, clave, asp, log=log)
            else:
                datos = frames.generar(prompt, refs, clave, asp, log=log, modelo=frames.MODELO_PRO if motor == "nanobanana-pro" else frames.MODELO)
        except Exception as e:
            log(f"    FALLÓ {xid}: {str(e)[:200]}")
            continue
        salida.write_bytes(datos)
        log(f"    {xid}: {salida.stat().st_size // 1024} KB en {time.time() - t0:.0f} s")
        s = leer(slug)
        if tipo == "personaje":
            s["personajes"][xid]["hoja"] = f"assets/{salida.name}"
            s["personajes"][xid]["aprobada"] = False
        else:
            s["locaciones"][xid]["imagen"] = f"assets/{salida.name}"
        guardar(s)
    return leer(slug)


# ───────────────────────────────────────────────────────────── el plan

def planificar(slug: str, n: int, pista: str = "", log=print) -> dict:
    """GPT propone `n` capítulos (título + premisa + quiénes + dónde). Se agregan
    como `propuesto`; vos aprobás, editás o descartás."""
    s = leer(slug)
    n = max(1, min(50, int(n)))
    if len((s.get("idea") or "").strip()) < 20:
        raise ValueError("escribí primero la idea general de la serie (nombrando a los personajes)")
    hechos = [c for c in s["capitulos"] if c["estado"] != "descartado"]
    prev = "\n".join(f"  {c['n']}. {c['titulo']} — {c['premisa']}" for c in hechos) or "  (ninguno todavía)"
    serial = s["continuidad"] == "serial"
    dur = Estructura.cargar(s["estructura"]).duracion_objetivo if s["formato"] != "musica" else None
    ins = (f"{biblia(s)}\n\nCAPÍTULOS QUE YA EXISTEN (no los repitas ni en tema ni en título):\n{prev}\n\n"
           f"Proponé {n} capítulos NUEVOS" + (f", numerados a continuación del {hechos[-1]['n']}" if hechos else "") + ".\n"
           + (f"Cada capítulo es un video de ~{dur:g} s con voz en off: una historia lineal, simple, con UN giro o UNA imagen que se recuerde (regla de oro: el guion es la voz en off contada primero como historia; los planos la sirven).\n" if dur else
              "Cada capítulo es un music video: una pista nueva del género de la serie y UNA escena del mismo universo (un lugar, una hora, una luz, qué se mueve despacio; se mira en loop).\n")
           + ("Es un SERIAL: cada premisa continúa la anterior y deja algo abierto para la siguiente; la primera nueva sigue al último capítulo existente.\n" if serial else
              "Es una ANTOLOGÍA: cada capítulo se entiende solo; variá situaciones, tonos y qué personaje lleva la historia.\n")
           + (f"PISTA DEL DIRECTOR PARA ESTA TANDA: {pista.strip()}\n" if pista.strip() else "")
           + "\nDevolvé JSON: {\"capitulos\": [{\"titulo\": \"corto, en castellano, en MAYÚSCULAS\", \"premisa\": \"2-3 frases en castellano: qué pasa, qué se ve, con qué termina\", "
             "\"personajes\": [ids de la serie que aparecen], \"locacion\": \"id de la serie o una descripción corta si es un lugar nuevo\", "
             "\"vestuario\": {\"id del personaje\": \"qué lleva puesto en ESTE capítulo, concreto, en inglés (prendas, colores, accesorios); vacío si va con su ropa base\"}"
           + (", \"musica\": \"cómo suena esta pista en particular, una frase\"" if s["formato"] == "musica" else "") + "}]}")
    r = _gpt(ins, "Sos showrunner de una serie de videos cortos generados con IA. Respondés sólo JSON.", log=log)
    caps = r.get("capitulos") or []
    if not isinstance(caps, list) or not caps:
        raise RuntimeError("GPT no devolvió capítulos")
    s = leer(slug)
    sig = (max([c["n"] for c in s["capitulos"]] or [0])) + 1
    por_nombre = {_id(p["nombre"]): pid for pid, p in s["personajes"].items()}
    for c in caps[:n]:
        pers = []
        for x in (c.get("personajes") or []):
            xid = _id(str(x))
            pid = xid if xid in s["personajes"] else por_nombre.get(xid) or _alias_de(s, [xid]).get(xid)
            if pid and pid not in pers:
                pers.append(pid)
        s["capitulos"].append({"n": sig, "titulo": str(c.get("titulo", f"CAPÍTULO {sig}")).strip()[:80],
                               "premisa": str(c.get("premisa", "")).strip(), "personajes": pers,
                               "locacion": str(c.get("locacion") or "").strip(), "musica": str(c.get("musica") or "").strip() or None,
                               "vestuario": {k: str(v).strip() for k, v in (c.get("vestuario") or {}).items() if isinstance(c.get("vestuario"), dict) and str(v).strip()},
                               "estado": "propuesto", "guion": "", "resumen": "", "slug": None, "nota": "", "creado": time.time()})
        sig += 1
    log(f"{len(caps[:n])} capítulos propuestos")
    return guardar(s)


def capitulo(s: dict, n: int) -> dict:
    for c in s["capitulos"]:
        if int(c["n"]) == int(n):
            return c
    raise KeyError(n)


def _estado(slug: str, n: int, estado: str, nota: str | None = None) -> dict:
    """Cambio de estado desde adentro del flujo (sin el guardián de «en curso»:
    el 18/9 producir se marcaba «produciendo» dos veces y su propio guardián
    tiraba los cinco capítulos con el proyecto ya traducido)."""
    s = leer(slug)
    c = capitulo(s, n)
    c["estado"] = estado
    if nota is not None:
        c["nota"] = nota
    return guardar(s)


def editar_capitulo(slug: str, n: int, **campos) -> dict:
    s = leer(slug)
    c = capitulo(s, n)
    if c["estado"] in ACTIVOS_CAP and "estado" in campos:
        raise RuntimeError("el capítulo está en curso")
    for k in ("titulo", "premisa", "guion", "locacion", "musica", "nota"):
        if k in campos and campos[k] is not None:
            c[k] = str(campos[k]).strip()
    if "personajes" in campos and campos["personajes"] is not None:
        c["personajes"] = [p for p in campos["personajes"] if p in s["personajes"]]
    if "vestuario" in campos and isinstance(campos["vestuario"], dict):
        c["vestuario"] = {k: str(v).strip() for k, v in campos["vestuario"].items() if str(v).strip()}
    if "estado" in campos and campos["estado"] in ESTADOS_CAP:
        c["estado"] = campos["estado"]
    return guardar(s)


# ───────────────────────────────────────────────────────────── el guion

def _presupuesto_caracteres(s: dict) -> tuple[float, int]:
    est = Estructura.cargar(s["estructura"])
    dur = float(s.get("duracion") or est.duracion_objetivo)
    if not s.get("voz"):
        return dur, 0
    cps = guionista.VOCES[s["voz"]]["cps"]
    # La voz no habla todo el tiempo: ~85 % de la duración con texto, al 92 % del ritmo medido.
    return dur, int(dur * 0.85 * cps * 0.92)


def escribir_guion(slug: str, n: int, log=print) -> dict:
    """GPT escribe el guion del capítulo: la voz en off como historia lineal
    (regla 40), medida al presupuesto de caracteres de la voz de la serie. En
    serial recibe los resúmenes de los capítulos anteriores. Queda en `guion`
    para que lo leas, lo edites y lo apruebes."""
    s = leer(slug)
    c = capitulo(s, n)
    if c["estado"] in ACTIVOS_CAP:
        raise RuntimeError("el capítulo está en curso")
    _estado(slug, n, "escribiendo")
    try:
        anteriores = [x for x in s["capitulos"] if x["n"] < c["n"] and x["estado"] != "descartado" and (x.get("resumen") or x.get("premisa"))]
        ctx = ""
        if s["continuidad"] == "serial" and anteriores:
            ctx = "LO QUE PASÓ ANTES (en orden):\n" + "\n".join(f"  {x['n']}. {x['titulo']}: {x.get('resumen') or x['premisa']}" for x in anteriores[-8:]) + "\n\n"
        pers = ", ".join(f"{p} ({s['personajes'][p]['nombre']})" for p in c["personajes"] if p in s["personajes"]) or "los que hagan falta"
        if c.get("vestuario"):
            pers += ". ROPA EN ESTE CAPÍTULO: " + "; ".join(f"{s['personajes'][k]['nombre'] if k in s['personajes'] else k}: {v}" for k, v in c["vestuario"].items())
        if s["formato"] == "musica":
            ins = (f"{biblia(s)}\n\n{ctx}CAPÍTULO {c['n']}: «{c['titulo']}»\nPREMISA: {c['premisa']}\nPERSONAJES: {pers}\nLUGAR: {c.get('locacion') or 'a elección'}\n"
                   f"MÚSICA DE ESTE CAPÍTULO: {c.get('musica') or 'según el género de la serie'}\n\n"
                   "Escribí la ESCENA del music video en castellano (120-250 palabras): un solo lugar visto en UN plano fijo que se va a mirar en loop "
                   "(un lugar, una hora, una luz, qué se mueve despacio y cíclico: lluvia, vapor, agua, una respiración). Si hay un personaje, está quieto, en una acción "
                   "mínima y repetible. Nada abstracto, ninguna ventana con ciudad, nada que cambie de estado. Y una frase para la música.\n"
                   "Devolvé JSON: {\"guion\": \"la escena\", \"musica\": \"la descripción de la pista para el compositor, en castellano, una o dos frases: ánimo, instrumentos, tempo\", "
                   "\"resumen\": \"una línea\"}")
        elif s.get("toma") == "una":
            n = tomas_de(s)
            voces = "\n".join(f"  - {s['personajes'][p]['nombre']}: {s['personajes'][p].get('voz') or 'voz a definir'}" for p in c["personajes"] if p in s["personajes"])
            actuado_txt = ("sin narrador: los personajes hablan en cámara. En cada toma, entre 3 y 4 líneas de diálogo, cada una de 5 a 9 palabras, "
                           "con el formato `NOMBRE: lo que dice`, una por renglón, en el orden en que se dicen; uno o dos personajes como mucho por toma, "
                           "que se turnan sin pisarse. Todo lo hablado de una toma dura menos de 10 segundos a ritmo normal (unas 30 palabras por toma, no más); "
                           "el resto son pausas, gestos y reacciones, que también contás entre corchetes [así]."
                           if s.get("modo") == "actuado" else
                           f"con voz en off ({guionista.VOCES[s['voz']]['nombre'] if s.get('voz') else 'sin voz'}): párrafos de la voz en off y entre corchetes qué se ve [así].")
            ins = (f"{biblia(s)}\n\n{ctx}CAPÍTULO {c['n']}: «{c['titulo']}»\nPREMISA: {c['premisa']}\nPERSONAJES: {pers}\nLUGAR: {c.get('locacion') or 'a elección entre las locaciones de la serie'}\n"
                   f"VOCES:\n{voces}\n\n"
                   f"Escribí el GUION de este video de {round(n * 15)} segundos como {n} TOMA{'S' if n > 1 else ''} CONTINUA{'S' if n > 1 else ''} DE 15 SEGUNDOS, en castellano rioplatense, {actuado_txt}\n"
                   f"Marcá cada toma con un renglón `[TOMA k]` (k de 1 a {n}). Cada toma es un solo lugar y un solo encuadre (cámara casi fija, plano medio o americano, "
                   "los personajes de frente); entre tomas puede cambiar el encuadre o pasar un poco de tiempo, pero es la misma historia.\n"
                   "La historia completa tiene que entenderse sola: la primera línea ya plantea la situación, hay un giro, y la última línea remata "
                   "(chiste, revelación o vuelta de tuerca). Nada que necesite un antes o un después.\n"
                   "Devolvé JSON: {\"guion\": \"el texto con los [TOMA k]\", \"resumen\": \"una línea de qué pasó\", \"lineas\": número de líneas de diálogo, \"palabras_habladas\": número}")
        elif s.get("modo") == "actuado":
            dur, _ = _presupuesto_caracteres(s)
            planos = max(3, int(round(dur / 5.167)))
            voces = "\n".join(f"  - {s['personajes'][p]['nombre']}: {s['personajes'][p].get('voz') or 'voz a definir'}" for p in c["personajes"] if p in s["personajes"])
            ins = (f"{biblia(s)}\n\n{ctx}CAPÍTULO {c['n']}: «{c['titulo']}»\nPREMISA: {c['premisa']}\nPERSONAJES: {pers}\nLUGAR: {c.get('locacion') or 'a elección entre las locaciones de la serie'}\n"
                   f"VOCES:\n{voces}\n\n"
                   f"Escribí el GUION ACTUADO de este video de {dur:g} s, en castellano rioplatense: sin narrador, los personajes hablan en cámara. "
                   f"El video son {planos} planos de 5 segundos: escribí como mucho {planos} líneas de diálogo, y dejá {max(1, planos // 4)} o más planos SIN "
                   "diálogo para reacciones, silencios y acciones (son los que respiran).\n"
                   "Cada línea la dice UN solo personaje, mide como mucho 12 palabras (unas 55 letras; se tiene que decir en 4 segundos) y va en su propia "
                   "línea con el formato `NOMBRE: lo que dice`. Nunca dos personajes en el mismo renglón. Entre líneas, cuando haga falta, una acotación entre "
                   "corchetes de qué se ve [así], nombrando a los personajes por su nombre; el que habla siempre está de frente y con la boca libre.\n"
                   "Historia lineal y simple: un gancho en la primera línea, un giro o una imagen que se recuerde, un cierre que deje algo. "
                   "Las líneas suenan a gente hablando, no a texto leído: cortas, con intención, con subtexto.\n"
                   "Devolvé JSON: {\"guion\": \"el texto\", \"resumen\": \"dos líneas de qué pasó, para el capítulo siguiente\", \"lineas\": número de líneas de diálogo}")
        else:
            dur, chars = _presupuesto_caracteres(s)
            voz = (f"La voz en off es {guionista.VOCES[s['voz']]['nombre']}. El texto de la voz en off tiene que medir ENTRE {int(chars * 0.85)} Y {chars} CARACTERES "
                   f"en total (contá; es lo que entra en {dur:g} s a su ritmo medido). Ni una frase más." if s.get("voz") else
                   "NO hay voz en off: contá la historia en imágenes y con 3-6 textos en pantalla cortos (máximo 6 palabras cada uno).")
            ins = (f"{biblia(s)}\n\n{ctx}CAPÍTULO {c['n']}: «{c['titulo']}»\nPREMISA: {c['premisa']}\nPERSONAJES: {pers}\nLUGAR: {c.get('locacion') or 'a elección entre las locaciones de la serie'}\n\n"
                   f"Escribí el GUION de este video de {dur:g} s, en castellano rioplatense, para que después otro modelo lo traduzca a planos.\n"
                   "Regla de oro (regla 40 del proyecto): primero la historia, lineal y simple, contada por la voz en off como si se la contaras a alguien; "
                   "los planos la sirven, no al revés. Un gancho en la primera frase (el resultado concreto, no la promesa), un giro o una imagen que se recuerde, un cierre que deje algo.\n"
                   f"{voz}\n"
                   "Formato del guion: párrafos de la voz en off en primera o tercera persona, y entre corchetes, cuando haga falta, qué se ve [así], nombrando a los personajes por su nombre. "
                   "Nada de encabezados técnicos ni números de plano.\n"
                   "Devolvé JSON: {\"guion\": \"el texto\", \"resumen\": \"dos líneas de qué pasó, para el capítulo siguiente\", \"caracteres_voz\": número}")
        r = _gpt(ins, "Sos guionista de una serie de videos con IA. Respondés sólo JSON.", log=log)
        guion = str(r.get("guion", "")).strip()
        if len(guion) < 40:
            raise RuntimeError("el guion salió vacío")
        s = leer(slug)
        c = capitulo(s, n)
        c.update(guion=guion, resumen=str(r.get("resumen", "")).strip(), estado="guion", nota="")
        if s["formato"] == "musica" and r.get("musica"):
            c["musica"] = str(r["musica"]).strip()
        if s.get("modo") == "actuado" and s["formato"] != "musica":
            lineas = [l for l in guion.splitlines() if re.match(r"^\s*[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑáéíóúñ ]{1,30}:\s*\S", l) and not l.strip().upper().startswith("[TOMA")]
            tope = 9 if s.get("toma") == "una" else 12
            largas = [l for l in lineas if len(l.split(":", 1)[1].split()) > tope]
            habladas = sum(len(l.split(":", 1)[1].split()) for l in lineas)
            tomas = len(re.findall(r"^\s*\[TOMA\s*\d+\]", guion, re.M | re.I))
            c["nota"] = (f"{len(lineas)} líneas · {habladas} palabras habladas" + (f" · {tomas} toma(s)" if s.get("toma") == "una" else "")
                         + (f" · {len(largas)} pasan de {tope} palabras: acortalas" if largas else "")
                         + (f" · más de {32 * max(1, tomas_de(s))} palabras: no entran, acortá" if s.get("toma") == "una" and habladas > 32 * max(1, tomas_de(s)) else ""))
        elif s.get("voz") and s["formato"] != "musica":
            dur, chars = _presupuesto_caracteres(s)
            c["nota"] = f"{len(guion)} caracteres (presupuesto ~{chars} para {dur:g} s)"
        log(f"guion escrito: {len(guion)} caracteres")
        return guardar(s)
    except Exception as e:
        _estado(slug, n, "aprobado", f"no pude escribir el guion: {e}")
        raise


# ───────────────────────────────────────────────────────────── producir

def reparto(s: dict, c: dict | None = None) -> dict:
    """Lo que el traductor tiene que respetar tal cual: ids, descripciones y
    hojas de los personajes aprobados y las locaciones con imagen. Con el
    capítulo `c`, la descripción suma la ropa de ESE capítulo («vestuario»):
    la hoja sostiene la cara, el texto sostiene la ropa."""
    vest = (c or {}).get("vestuario") or {}
    pers = {}
    for pid, p in s["personajes"].items():
        if not p.get("hoja"):
            continue
        desc = p["descripcion"].strip()
        if vest.get(pid):
            desc = desc.rstrip(".") + f". In this episode {p['nombre']} wears: {vest[pid].rstrip('.')}. This outfit replaces the base clothing in every shot."
        pers[pid] = {"hoja": f"m_{pid}", "descripcion": desc}
    locs = {lid: {"imagen": f"l_{lid}", "descripcion": l["descripcion"]}
            for lid, l in s["locaciones"].items() if l.get("imagen")}
    voces = {pid: p["voz"] for pid, p in s["personajes"].items() if p.get("voz")} if s.get("modo") == "actuado" else {}
    return {"personajes": pers, "locaciones": locs, "voces": voces}


def _python(*args: str, log=print, cwd: Path | None = None) -> None:
    cmd = [sys.executable, "-X", "utf8", "-u", *args]
    log("$ " + " ".join(a if " " not in a else f'"{a}"' for a in cmd[3:]))
    r = subprocess.run(cmd, cwd=str(cwd or maquina.RAIZ), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    salida = r.stdout.decode("utf-8", "replace")
    for linea in salida.splitlines()[-40:]:
        log("  " + linea)
    if r.returncode:
        raise RuntimeError(f"{args[1] if len(args) > 1 else args[0]} terminó con código {r.returncode}")


def _alias_de(s: dict, ids: list[str]) -> dict[str, str]:
    """{id inventado → id de la serie} para los personajes que el traductor
    renombró: «monky_zen» → «monky», «el_alumno» → «alumno», o por el nombre."""
    out = {}
    serie = {pid: p for pid, p in s["personajes"].items()}
    for x in set(ids):
        if x in serie:
            continue
        xl = x.lower()
        for pid, p in serie.items():
            nom = _id(p["nombre"])
            if xl.startswith(pid + "_") or xl.endswith("_" + pid) or xl == nom or xl.startswith(nom + "_") or (len(pid) > 3 and pid in xl):
                out[x] = pid
                break
    return out


def hojas_de_capitulo(s: dict, c: dict, d: dict, formato: str) -> list[str]:
    """La HOJA DEL CAPÍTULO (pedido del usuario, 20/9): la hoja de la serie es la
    referencia de identidad; cuando el capítulo viste distinto al personaje, se
    dibuja primero una hoja nueva del MISMO personaje con esa ropa, usando la de
    la serie como referencia, y todos los fotogramas del capítulo referencian
    ESA. Antes cada fotograma recibía la hoja neutra más un texto que decía «va
    de cirujano», y el generador obedecía a veces al texto y a veces a la
    imagen: cuatro monos distintos en un mismo capítulo. Devuelve los ids de las
    hojas nuevas (van a `madre`, se generan antes que los fotogramas)."""
    vest = c.get("vestuario") or {}
    asp = "16:9" if formato == "largo" else "9:16"
    nuevas = []
    d.setdefault("madre", [])
    for pid, ropa in vest.items():
        pj = s["personajes"].get(pid)
        if not pj or not pj.get("hoja") or not str(ropa).strip():
            continue
        usado = pid in d.get("personajes", {}) or any(pid in (pl.get("personajes") or []) for pl in d["planos"])
        if not usado:
            continue
        hid = f"m_{pid}_ep"
        desc = pj["descripcion"].rstrip(".") + f". Now wearing, for this episode: {str(ropa).rstrip('.')}. This outfit replaces the base clothing."
        d["madre"] = [m for m in d["madre"] if m.get("id") != hid]
        # Referencias: la hoja de la serie y, si el personaje nació de una foto
        # subida, la foto original también (se copia al capítulo como m_<id>_foto):
        # así la fidelidad no se degrada de copia en copia.
        refs = [f"assets/m_{pid}.png"]
        if pj.get("imagen_ref") and (carpeta(s["slug"]) / pj["imagen_ref"]).exists():
            refs.append(f"assets/m_{pid}_foto.png")
        d["madre"].append({"id": hid, "aspecto": asp, "refs": refs,
                           "prompt": prompt_hoja(s, {**pj, "descripcion": desc, "imagen_ref": True})})
        d.setdefault("personajes", {}).setdefault(pid, {"descripcion": desc})["hoja"] = hid
        for pl in d["planos"]:
            if pl.get("refs"):
                pl["refs"] = [f"assets/{hid}.png" if r in (f"m_{pid}", f"assets/m_{pid}.png") else r for r in pl["refs"]]
        nuevas.append(hid)
    return nuevas


CONTINUIDAD = (" CONTINUITY WITH THE PREVIOUS TAKE: one of the reference images is the first frame of the previous take of this same "
               "scene. Keep the SAME room, the same furniture and props in the same places, the same light and colour, and the "
               "character wearing exactly the same; the action simply continues a few moments later, possibly from a different angle.")


def encadenar_fotogramas(d: dict, rep_: dict) -> int:
    """Tomas de 15 s (20/9): el primer fotograma de la toma k se dibuja con el de
    la toma k-1 como referencia, más la cláusula de continuidad en `ve`. Así
    el set, los objetos y la luz se sostienen de toma en toma (la identidad ya
    la sostiene la hoja del capítulo). `frames` los dibuja en orden."""
    planos = d.get("planos") or []
    n = 0
    for k in range(1, len(planos)):
        ant, pl = planos[k - 1], planos[k]
        if pl.get("sigue_de") or pl.get("clip_de") or pl.get("dibujo"):
            continue
        refs = list(pl.get("refs") or [])
        if not refs:
            loc = pl.get("loc")
            if loc and loc in d.get("locaciones", {}):
                refs.append(d["locaciones"][loc]["imagen"])
            for x in (pl.get("personajes") or []):
                h = d.get("personajes", {}).get(x, {}).get("hoja")
                if h and h not in refs:
                    refs.append(h)
        prev = f"sb_{ant['id']}"
        if prev not in refs and f"assets/{prev}.png" not in refs:
            refs.append(prev)
        pl["refs"] = refs
        if "CONTINUITY WITH THE PREVIOUS TAKE" not in (pl.get("ve") or ""):
            pl["ve"] = (pl.get("ve") or "").rstrip() + CONTINUIDAD
        n += 1
    return n


def _proyecto_coincide(pc: Path, s: dict) -> bool:
    """¿El proyecto.json que ya existe usa el reparto de la serie? Si tiene
    personajes que no son de la serie (los inventó el traductor) hay que
    volver a traducir: reutilizarlo dibujaría caras que no son."""
    try:
        d = json.loads((pc / "proyecto.json").read_text(encoding="utf-8"))
    except Exception:
        return False
    usados = set(d.get("personajes", {}).keys()) | {x for pl in d.get("planos", []) for x in (pl.get("personajes") or [])}
    return usados.issubset(set(s["personajes"].keys()))


def _limpiar_proyecto(pc: Path, log=print) -> None:
    """Borra lo derivado de una traducción mala (proyecto, storyboard, planos,
    dibujos, voz, ZIP) y deja el guion. Los clips bajados, si los hubiera, quedan."""
    for n in ("proyecto.json", "storyboard.json", "planos.json", "madre.json", "brief.md", "voz_en_off.txt", "texto_en_pantalla.txt"):
        (pc / n).unlink(missing_ok=True)
    for z in pc.glob("*-para-vast.zip"):
        z.unlink(missing_ok=True)
    for d in ("assets", "voz", "para-vast"):
        shutil.rmtree(pc / d, ignore_errors=True)
    log("proyecto anterior descartado: se vuelve a traducir con el reparto de la serie")


def producir(slug: str, n: int, hasta: str = "cola", motor: str = "openai", log=print, rehacer: bool = False) -> dict:
    """Capítulo con guion aprobado → proyecto completo listo para la cola:
    traducir (GPT, con el reparto fijo) → hojas de la serie copiadas → voz
    (ElevenLabs) → dibujos (imágenes) → ZIP → cola. En music video, además
    compone la pista del capítulo. `hasta`: proyecto | dibujos | cola."""
    s = leer(slug)
    c = capitulo(s, n)
    if c["estado"] not in ("guion", "error", "producido"):
        raise RuntimeError(f"el capítulo está en estado {c['estado']}; primero escribí y aprobá el guion")
    if len(c.get("guion", "")) < 40:
        raise RuntimeError("el capítulo no tiene guion")
    # TODOS los personajes de la serie tienen que tener su hoja antes de producir:
    # sin hoja no entran al reparto fijo y el traductor inventa otros (el 18/9
    # salieron `m_monky_zen` y `m_alumno_off` en vez del Monky de la serie).
    if not s["personajes"]:
        raise RuntimeError("la serie no tiene personajes: cargá al menos uno y dibujale la hoja")
    sin_hoja = [p["nombre"] for p in s["personajes"].values() if not p.get("hoja")]
    if sin_hoja:
        raise RuntimeError(f"faltan las hojas de modelo de: {', '.join(sin_hoja)}. Dibujalas y aprobalas (paso 1) antes de producir")
    sin_aprobar = [p["nombre"] for p in s["personajes"].values() if p.get("hoja") and not p.get("aprobada")]
    if sin_aprobar:
        log(f"aviso: hojas sin aprobar ({', '.join(sin_aprobar)}); se usan igual")
    _estado(slug, n, "produciendo", "")
    pslug = c.get("slug") or f"{slug}-{c['n']:02d}-{_slug(c['titulo'])[:24]}"
    pc = maquina.MIS / pslug
    try:
        # 1 · guion.json + traducir con el reparto fijo
        pc.mkdir(parents=True, exist_ok=True)
        es_musica = s["formato"] == "musica"
        actuado = s.get("modo") == "actuado" and not es_musica
        formato = "largo" if es_musica else s["formato"]
        rep = reparto(s, c)
        pedido = {"guion": c["guion"], "formato": formato, "estructura": s["estructura"], "titulo": c["titulo"],
                  "estilo_imagen": s["estilo"]["imagen"], "estilo_video": s["estilo"].get("video", ""),
                  "cierre_video": s["estilo"].get("cierre", ""), "medio": s["estilo"].get("medio", ""),
                  "voz": None if (es_musica or actuado) else s.get("voz"), "negativos": not es_musica,
                  "notas": f"Serie «{s['titulo']}», capítulo {c['n']}. " + (s.get("notas") or ""),
                  "slug": pslug, "duracion": s.get("duracion") if (es_musica or s.get("toma") == "una") else None, "serie": slug, "capitulo": c["n"],
                  "actuado": actuado, "tomas": tomas_de(s)}
        (pc / "guion.json").write_text(json.dumps(pedido, ensure_ascii=False, indent=2), encoding="utf-8")
        (pc / "guion.txt").write_text(c["guion"], encoding="utf-8")
        if (pc / "proyecto.json").exists() and (rehacer or not _proyecto_coincide(pc, s)):
            _limpiar_proyecto(pc, log=log)
        if not (pc / "proyecto.json").exists():
            log(f"traduciendo el guion del capítulo {c['n']} ({len(c['guion'])} caracteres)…")
            r = guionista.traducir(c["guion"], formato=formato, estructura=s["estructura"], estilo_imagen=s["estilo"]["imagen"],
                                   estilo_video=pedido["estilo_video"], cierre_video=pedido["cierre_video"], medio=pedido["medio"],
                                   voz=pedido["voz"], titulo=c["titulo"], negativos=pedido["negativos"], notas=pedido["notas"],
                                   duracion=pedido["duracion"], reparto=rep, actuado=actuado, tomas=tomas_de(s),
                                   reintentos=1 if tomas_de(s) else 2, log=log)
            d = r["proyecto"]
            d["slug"] = pslug
            d["serie"] = {"slug": slug, "capitulo": c["n"], "modo": s.get("modo", "narrado")}
            if actuado:
                # Sin narrador: nada de `voz`/`voces` de ElevenLabs. Cada línea la
                # dice H3 en el clip: el que habla está en el plano, con su voz.
                d.pop("voz", None)
                d["voces"] = {}
                for pl in d["planos"]:
                    if not pl.get("dialogo"):
                        continue
                    quien = pl.get("habla") or pl.get("voz_de") or (pl.get("personajes") or [None])[0]
                    if quien and quien not in (pl.get("personajes") or []):
                        pl.setdefault("personajes", []).append(quien)
                    pl["habla"] = quien
                    pl["off"] = False
                    if not pl.get("voz_desc") and quien in rep["voces"]:
                        pl["voz_desc"] = rep["voces"][quien]
            # El reparto manda: mismas descripciones e ids que en toda la serie, y
            # las madres que ya existen no se vuelven a pedir.
            d.setdefault("personajes", {})
            # Si el traductor igual renombró a alguien («monky_zen» por «monky»),
            # se lo vuelve al id de la serie: misma hoja, misma cara.
            alias = _alias_de(s, list(d["personajes"].keys()) + [x for pl in d["planos"] for x in (pl.get("personajes") or [])])
            if alias:
                log("personajes renombrados por el traductor, vueltos al reparto: " + ", ".join(f"{a}→{b}" for a, b in alias.items()))
                for a, b in alias.items():
                    d["personajes"].pop(a, None)
                    for pl in d["planos"]:
                        pl["personajes"] = [b if x == a else x for x in (pl.get("personajes") or [])]
                        pl["personajes"] = list(dict.fromkeys(pl["personajes"]))
                        if pl.get("refs"):
                            pl["refs"] = list(dict.fromkeys(f"m_{b}" if r == f"m_{a}" else r for r in pl["refs"]))
                        for k in ("habla", "voz_de"):
                            if pl.get(k) == a:
                                pl[k] = b
                    d["madre"] = [m for m in (d.get("madre") or []) if m.get("id") != f"m_{a}"]
            for pid, p in rep["personajes"].items():
                if pid in d["personajes"] or any(pid in (pl.get("personajes") or []) for pl in d["planos"]):
                    d["personajes"][pid] = dict(p)
            d.setdefault("locaciones", {})
            for lid, l in rep["locaciones"].items():
                if lid in d["locaciones"] or any(pl.get("loc") == lid for pl in d["planos"]):
                    d["locaciones"][lid] = dict(l)
            existentes = {v["hoja"] for v in rep["personajes"].values()} | {v["imagen"] for v in rep["locaciones"].values()}
            d["madre"] = [m for m in (d.get("madre") or []) if m.get("id") not in existentes]
            # Las hojas y locaciones de la serie se declaran igual (el PNG ya está y
            # `frames` lo saltea): sin la declaración el validador avisaba «assets
            # madre usados pero no declarados» en cada capítulo.
            usadas = set()
            for pl in d["planos"]:
                for x in (pl.get("personajes") or []):
                    if x in rep["personajes"]:
                        usadas.add(rep["personajes"][x]["hoja"])
                if pl.get("loc") in rep["locaciones"]:
                    usadas.add(rep["locaciones"][pl["loc"]]["imagen"])
            asp = "16:9" if formato == "largo" else "9:16"
            for mid in sorted(usadas):
                d["madre"].append({"id": mid, "aspecto": asp, "refs": [],
                                   "prompt": f"(hoja de la serie «{s['titulo']}»: ya dibujada y aprobada; no se rehace)"})
            nuevas = hojas_de_capitulo(s, c, d, formato)
            if nuevas:
                log("hoja(s) del capítulo (mismo personaje, con la ropa de este capítulo): " + ", ".join(nuevas))
            if tomas_de(s) > 1:
                ne = encadenar_fotogramas(d, rep)
                log(f"continuidad entre tomas: {ne} fotograma(s) referencian al anterior")
            (pc / "proyecto.json").write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            p = Proyecto.cargar(pc / "proyecto.json")
            p.escribir(log=lambda *_: None)
            for a in r["avisos"]:
                log(f"  ⚠ {a}")
            log(f"proyecto.json: {len(d['planos'])} planos · {len(d.get('voz', []))} líneas de voz")
            nprom = reescritor.completar(pc / "proyecto.json", log=lambda *_: None)
            log(f"prompts H3 en formato oficial: {nprom}")
        else:
            log("proyecto.json ya existía: no se vuelve a traducir")
        # 2 · las hojas de la serie, tal cual, a los assets del capítulo
        (pc / "assets").mkdir(exist_ok=True)
        copiadas = 0
        for pid, p in s["personajes"].items():
            if p.get("hoja") and not (pc / "assets" / f"m_{pid}.png").exists():
                shutil.copy(carpeta(slug) / p["hoja"], pc / "assets" / f"m_{pid}.png")
                copiadas += 1
            if p.get("imagen_ref") and (carpeta(slug) / p["imagen_ref"]).exists() and not (pc / "assets" / f"m_{pid}_foto.png").exists():
                shutil.copy(carpeta(slug) / p["imagen_ref"], pc / "assets" / f"m_{pid}_foto.png")
        for lid, l in s["locaciones"].items():
            if l.get("imagen") and not (pc / "assets" / f"l_{lid}.png").exists():
                shutil.copy(carpeta(slug) / l["imagen"], pc / "assets" / f"l_{lid}.png")
                copiadas += 1
        log(f"hojas y locaciones de la serie copiadas: {copiadas}")
        _estado(slug, n, "produciendo")
        s2 = leer(slug)
        capitulo(s2, n)["slug"] = pslug
        guardar(s2)
        if hasta == "proyecto":
            _estado(slug, n, "producido", "proyecto listo (sin dibujos)")
            return leer(slug)
        # 3 · música del capítulo (music video)
        if es_musica:
            from . import componer  # noqa: F401  (la tarea vive ahí; se llama por subproceso)
            pm = {"slug": pslug, "tipo": c.get("musica") or s["musica"].get("tipo", ""), "duracion": int(s["musica"]["duracion"]),
                  "genero": s["musica"]["genero"], "loopeable": True, "con_letra": False, "letra": "", "idioma_letra": "es",
                  "voz_letra": "femenina", "nombre": _slug(c["titulo"])[:30] or "musica"}
            if not list(pc.glob("*.mp3")) and not list(pc.glob("*.wav")):
                (pc / "musica-pedido.json").write_text(json.dumps(pm, ensure_ascii=False), encoding="utf-8")
                log("componiendo la pista del capítulo (ElevenLabs Music)…")
                _python("-m", "h3pipeline.app.componer", str(pc / "musica-pedido.json"), log=log)
        # 4 · voz (sólo narrado: en actuado la voz la genera H3 dentro del clip)
        elif s.get("voz") and not actuado:
            log("voz en off (ElevenLabs)…")
            _python("-m", "h3pipeline", "voz", str(pc / "proyecto.json"), "--generar", log=log)
        # 5 · dibujos
        log(f"dibujos ({motor})…")
        _python("-m", "h3pipeline", "frames", str(pc / "proyecto.json"), "--motor", motor, "--madre", log=log)
        if hasta == "dibujos":
            _estado(slug, n, "producido", "dibujos listos; falta empaquetar")
            return leer(slug)
        # 6 · ZIP y cola
        log("empaquetando…")
        _python("-m", "h3pipeline", "empaquetar", str(pc / "proyecto.json"), log=log)
        cola.agregar(pslug)
        _estado(slug, n, "producido", "en la cola: se genera cuando la corras")
        log(f"capítulo {c['n']} en la cola como {pslug}")
        return leer(slug)
    except Exception as e:
        _estado(slug, n, "error", f"{e}")
        s3 = leer(slug)
        capitulo(s3, n)["slug"] = pslug if (pc / "proyecto.json").exists() else None
        guardar(s3)
        raise


def masterizar_todos(slug: str, log=print) -> int:
    """El máster de cada capítulo con todos sus clips bajados: `montar` si no
    hay voz en off (actuado: el audio de H3 es la pista), `mezclar` si la hay.
    Devuelve cuántos salieron. Uno que falla no frena a los demás."""
    from .. import montaje
    s = leer(slug)
    hechos = 0
    for c in s["capitulos"]:
        if c["estado"] != "producido" or not c.get("slug"):
            continue
        pc = maquina.MIS / c["slug"]
        if not (pc / "proyecto.json").exists():
            continue
        if any(f.suffix == ".mp4" and "corte" not in f.name.lower() for f in pc.glob("*.mp4")):
            hechos += 1
            continue
        try:
            pr = Proyecto.cargar(pc / "proyecto.json")
            planos = pr.construir()[1]["planos"]
            faltan = montaje.faltantes(planos, pc / "clips") if (pc / "clips").exists() else ["(sin clips)"]
        except Exception as e:
            log(f"!! capítulo {c['n']}: no pude leer el proyecto ({e})")
            continue
        if faltan:
            log(f"— capítulo {c['n']}: faltan {len(faltan)} clip(s); sin máster")
            continue
        que = "mezclar" if pr.voz else "montar"
        log(f"— capítulo {c['n']}: máster ({que})")
        try:
            _python("-m", "h3pipeline", que, str(pc / "proyecto.json"), str(pc / "clips"), log=log)
            hechos += 1
            _estado(slug, c["n"], "producido", "máster listo")
        except Exception as e:
            log(f"!! capítulo {c['n']}: el máster falló: {e}")
    return hechos


def masa(slug: str, motor: str = "openai", correr_cola: bool = True, apagar: bool = True, log=print) -> dict:
    """PRODUCCIÓN EN MASA: el último botón. Todo lo que no esté descartado ni
    producido se aprueba, se le escribe el guion si no lo tiene, se produce
    (rehaciendo lo que quedó mal) y va a la cola; después la cola enciende la
    máquina, genera, baja y apaga; y al final sale el máster de cada capítulo.
    Alquila GPU: la confirmación con el costo la dio el usuario al apretar.
    Se puede volver a apretar en cualquier punto: retoma donde quedó."""
    s = leer(slug)
    if len((s.get("idea") or "").strip()) < 20:
        raise RuntimeError("falta la idea general de la serie (paso 2)")
    sin_hoja = [p["nombre"] for p in s["personajes"].values() if not p.get("hoja")]
    if sin_hoja:
        raise RuntimeError(f"faltan las hojas de: {', '.join(sin_hoja)} (paso 1)")
    pendientes = [c["n"] for c in sorted(s["capitulos"], key=lambda c: c["n"]) if c["estado"] in ("propuesto", "aprobado", "guion", "error")]
    log(f"producción en masa: {len(pendientes)} capítulo(s)")
    hechos, fallados = [], []
    for n in pendientes:
        try:
            c = capitulo(leer(slug), n)
            if c["estado"] == "propuesto":
                _estado(slug, n, "aprobado")
            c = capitulo(leer(slug), n)
            if len(c.get("guion") or "") < 40:
                log(f"— capítulo {n}: guion")
                escribir_guion(slug, n, log=log)
            log(f"— capítulo {n}: producir")
            producir(slug, n, motor=motor, log=log, rehacer=(c["estado"] == "error"))
            hechos.append(n)
        except Exception as e:
            log(f"!! capítulo {n}: {e}")
            fallados.append(n)
    log(f"en masa: {len(hechos)} producidos, {len(fallados)} fallados" + (f" ({', '.join(map(str, fallados))})" if fallados else ""))
    # los producidos de antes que quedaron fuera de la cola (p. ej. una corrida
    # anterior sin cola) vuelven a entrar si todavía no tienen clips
    for c in leer(slug)["capitulos"]:
        if c["estado"] == "producido" and c.get("slug") and (maquina.MIS / c["slug"] / "proyecto.json").exists():
            pc = maquina.MIS / c["slug"]
            if any(pc.glob("*-para-vast.zip")) and not (pc / "clips").exists():
                cola.agregar(c["slug"])
    if correr_cola and cola.pendientes():
        from . import correr_cola as cc
        d = cola.leer()
        d["apagar_al_final"] = bool(apagar)
        cola.escribir(d)
        log(f"=== la cola: enciendo la máquina y genero {len(cola.pendientes())} capítulo(s) ===")
        rc = cc.main()
        log(f"cola terminada con código {rc}")
    elif correr_cola:
        log("la cola está vacía: nada que generar")
    n = masterizar_todos(slug, log=log)
    log(f"=== másters: {n} listos ===")
    return leer(slug)


def guiones_todos(slug: str, log=print) -> dict:
    """Aprueba todos los propuestos y escribe el guion de todos los que no lo
    tienen. Para acá: los guiones se leen y después se produce (en masa o de
    a uno). No gasta más que GPT."""
    s = leer(slug)
    if len((s.get("idea") or "").strip()) < 20:
        raise RuntimeError("falta la idea general de la serie (paso 2)")
    pend = [c["n"] for c in sorted(s["capitulos"], key=lambda c: c["n"])
            if c["estado"] in ("propuesto", "aprobado", "error") and len(c.get("guion") or "") < 40]
    log(f"{len(pend)} capítulo(s) sin guion")
    hechos = 0
    for n in pend:
        try:
            c = capitulo(leer(slug), n)
            if c["estado"] in ("propuesto", "error"):
                _estado(slug, n, "aprobado", "")
            log(f"— capítulo {n}: guion")
            escribir_guion(slug, n, log=log)
            hechos += 1
        except Exception as e:
            log(f"!! capítulo {n}: {e}")
    log(f"{hechos} guion(es) escritos; leelos y después «Producir en masa»")
    return leer(slug)


def producir_aprobados(slug: str, motor: str = "openai", log=print) -> dict:
    """Todos los capítulos con guion aprobado, uno tras otro. Uno que falla no
    frena a los demás."""
    s = leer(slug)
    pendientes = [c["n"] for c in s["capitulos"] if c["estado"] == "guion"]
    log(f"{len(pendientes)} capítulo(s) con guion aprobado")
    for n in pendientes:
        try:
            producir(slug, n, motor=motor, log=log)
        except Exception as e:
            log(f"!! capítulo {n}: {e}")
    return leer(slug)


def estado_proyectos(s: dict) -> dict:
    """Qué hay en la carpeta de cada capítulo producido (para la vista)."""
    out = {}
    for c in s["capitulos"]:
        if not c.get("slug"):
            continue
        pc = maquina.MIS / c["slug"]
        if not (pc / "proyecto.json").exists():
            continue
        try:
            d = json.loads((pc / "proyecto.json").read_text(encoding="utf-8"))
            planos = len(d.get("planos", []))
        except Exception:
            planos = 0
        assets = list((pc / "assets").glob("*.png")) if (pc / "assets").exists() else []
        clips = list((pc / "clips").glob("*.mp4")) if (pc / "clips").exists() else []
        masters = [f.name for f in pc.glob("*.mp4") if "corte" not in f.name.lower()]
        out[c["slug"]] = {"planos": planos, "assets": len(assets), "clips": len(clips), "masters": masters,
                          "zip": any(pc.glob("*-para-vast.zip")),
                          "en_cola": any(i["slug"] == c["slug"] for i in cola.leer()["items"])}
    return out
