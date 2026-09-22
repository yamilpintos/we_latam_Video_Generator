"""LARGO ACTUADO POR ESCENAS: pocos dibujos, muchos clips.

El problema que resuelve (22/9/2026, midiendo diez videos de referencia contra
«EL CAMIÓN DE MI PADRE»): nuestros largos dibujaban **una imagen por plano** —79
dibujos para siete minutos— y cada dibujo es una tirada de dados sobre la cara
del personaje. A los 79 dibujos el protagonista tenía cuatro caras. Los videos
de referencia cambian de imagen **cada 44 segundos** y su protagonista es el
mismo señor durante 5:46.

La solución NO es encadenar (`sigue_de`). Encadenar tiene dos techos medidos:
máximo 3 eslabones —al cuarto la identidad se degrada, REGLAS §38— y máximo
5,9 s por eslabón en 32 GB. Encima el montaje corta la cola del clip anterior
y rompe la juntura (1,29 s perdidos en CONTRAMANO).

La solución es `dibujo`: **varios planos arrancan del MISMO dibujo**. Cada clip
está a UNA generación del dibujo, igual que un plano suelto, así que no hay
degradación por más clips que cuelguen de él; se generan todos en paralelo, y
una falla no arrastra a nadie. El precio es que cada clip vuelve a la pose
inicial: por eso la escena se escribe con la cámara quieta y los personajes
parados, que es exactamente como están compuestos los videos de referencia.

    escena = un lugar, un encuadre, varios clips de 5,17 s
    toma   = el grupo de clips que comparten UN dibujo

La voz no se escribe por código como en `narrado`: acá cada línea del guion es
un clip y H3 la dice en cámara (Ref2VA con la voz del banco). El guion entra
con esta forma:

    ## ESCENA 1 · El campo seco, atardecer
    [TOMA 1]
    ROSA: ¿Nada, Antonio?
    ANTONIO: Nada, Rosa. La seca se llevó todo.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import grilla, prompts
from .guionista import ErrorGuionista, _json, _llamar
from .proyecto import Proyecto, ProyectoInvalido

SEGUNDOS = round(grilla.MINIMO, 3)      # 5,167 s: el escalón seguro con referencias
MAX_PALABRAS = 14                       # una línea más larga no entra hablada en 5,17 s
# Cuánto ocupa una línea EN EL VIDEO TERMINADO. No son los 5,167 s del clip:
# el montaje recorta cada uno a la voz medida y se lleva las pausas muertas.
# Medido en «LA SANGRE ENCUENTRA EL CAMINO»: 70 líneas → 249,3 s.
SEG_POR_LINEA_MONTADA = 3.56
TAMANOS = ("PGE", "PG", "PA", "PM", "PP", "PD")


@dataclass
class Linea:
    quien: str                  # id del personaje que habla ("" = plano sin diálogo)
    texto: str


@dataclass
class Toma:
    """Los clips que comparten un dibujo."""
    lineas: list[Linea] = field(default_factory=list)


@dataclass
class Escena:
    titulo: str
    lugar: str                  # lo que dice el guion, en castellano
    tomas: list[Toma] = field(default_factory=list)

    @property
    def clips(self) -> int:
        return sum(len(t.lineas) for t in self.tomas)


def parsear(texto: str, alias: dict[str, str]) -> list[Escena]:
    """Del guion a escenas. Acepta las dos formas que se escriben:

        ## ESCENA 1 · El campo seco, atardecer      (markdown, a mano)
        [ESCENA 1] El campo seco, atardecer         (la que devuelve GPT)

    y debajo `[TOMA k]` con las líneas `NOMBRE: lo que dice`. `alias` mapea el
    rótulo del guion (ROSA, ANTONIO) al id del personaje en el reparto."""
    escenas: list[Escena] = []
    for linea in texto.splitlines():
        l = linea.strip()
        cab = None
        if l.startswith("## "):
            cab = l[3:].strip()
        else:
            m = re.match(r"^\[ESCENA[^\]]*\]\s*(.*)$", l, re.I)
            if m:
                cab = m.group(1).strip() or f"ESCENA {len(escenas) + 1}"
        if cab is not None:
            m = re.match(r"^ESCENA\s+\d+\s*[·.\-:]\s*(.+)$", cab, re.I)
            lugar = (m.group(1) if m else cab).strip()
            escenas.append(Escena(titulo=cab, lugar=lugar))
        elif re.match(r"^\[TOMA\b", l, re.I):
            if not escenas:
                # Guion de una sola escena que arranca directo en [TOMA 1].
                escenas.append(Escena(titulo="ESCENA 1", lugar=""))
            escenas[-1].tomas.append(Toma())
        elif ":" in l and escenas and escenas[-1].tomas:
            rotulo, dicho = l.split(":", 1)
            rotulo, dicho = rotulo.strip(), dicho.strip()
            if not dicho or len(rotulo.split()) > 3 or rotulo != rotulo.upper():
                continue          # prosa, no una línea de diálogo
            quien = alias.get(rotulo) or alias.get(rotulo.title()) or ""
            if not quien:
                raise ErrorGuionista(f"«{rotulo}» no está en el reparto: agregalo o corregí el rótulo")
            escenas[-1].tomas[-1].lineas.append(Linea(quien, dicho))
    return [e for e in escenas if e.clips]


def reagrupar(e: Escena, por_dibujo: int) -> None:
    """Rearma las tomas de la escena para que cada dibujo aguante `por_dibujo`
    clips. Sirve para probar cuántos clips tolera un mismo dibujo antes de que
    el salto a la pose inicial se note."""
    todas = [l for t in e.tomas for l in t.lineas]
    e.tomas = [Toma(todas[i:i + por_dibujo]) for i in range(0, len(todas), por_dibujo)]


def _pedido(e: Escena, ids: list[list[str]], reparto: dict, locaciones: dict,
            estilo_imagen: str, medio: str, notas: str, k: int, total: int) -> str:
    pers = "\n".join(f"  - id `{pid}`: {v['descripcion']}" for pid, v in (reparto.get("personajes") or {}).items())
    locs = "\n".join(f"  - id `{lid}`: {v['descripcion']}" for lid, v in locaciones.items()) or "  (ninguna todavía)"
    bloques = []
    for j, (t, grupo) in enumerate(zip(e.tomas, ids)):
        dichos = "\n".join(f"      {i} · {l.quien}: «{l.texto}»" for i, l in zip(grupo, t.lineas))
        bloques.append(f"  TOMA {j + 1} — un solo dibujo, {len(grupo)} clips de {SEGUNDOS} s:\n{dichos}")
    return (
        f"Sos director de fotografía de un drama actuado en {medio or 'live-action film'}, para 16:9.\n"
        f"Estilo visual, idéntico en todo el video: {estilo_imagen}\n\n"
        f"ESCENA {k + 1} de {total}: {e.titulo}\n"
        f"Lugar: {e.lugar}\n\n"
        f"REPARTO FIJO (usá SÓLO estos ids; nadie más tiene cara):\n{pers}\n\n"
        f"LOCACIONES YA DEFINIDAS (reusá el id si es el mismo lugar):\n{locs}\n\n"
        "Esta escena se filma con LA CÁMARA QUIETA. Cada TOMA es UN dibujo, y de ese mismo dibujo "
        "arrancan todos sus clips: cada clip vuelve a la pose del dibujo, así que la escena tiene que "
        "estar compuesta para que eso no se note.\n\n"
        + "\n".join(bloques) + "\n\n"
        "REGLAS DEL DIBUJO (`ve`), una por TOMA:\n"
        "- Es una FOTO en inglés del primer fotograma: tamaño de plano en mayúsculas, quién está y dónde, "
        "con su ropa, la luz, 2-3 objetos concretos del lugar.\n"
        "- LOS PERSONAJES ESTÁN PARADOS O SENTADOS Y QUIETOS, en una pose de reposo: si el clip vuelve a "
        "esta pose cada 5 segundos, no puede ser un gesto a mitad de camino. Nadie caminando, nadie "
        "entrando ni saliendo.\n"
        "- PERO SE LES TIENE QUE VER LA CARA. Están enfrentados entre ellos y girados HACIA LA CÁMARA en "
        "TRES CUARTOS: se ven los dos ojos y la boca entera de cada uno. NUNCA de perfil puro, nunca de "
        "espaldas ni de tres cuartos de espaldas. Decilo con esas palabras en el `ve` («turned three "
        "quarters toward camera, both eyes and mouth fully visible»): esto es lo que más se falla, y una "
        "cara de perfil arruina el plano porque no se le ve hablar (medido el 22/9).\n"
        f"- `tipo`: uno de {', '.join(TAMANOS)}. Preferí PM (plano medio) y PA (plano entero) con los dos "
        "personajes en el cuadro, uno a cada lado, como en una obra de teatro filmada. PP sólo en el pico "
        "emocional de la escena. NADA de PD (insertos de objetos): este formato vive de caras.\n"
        "- Dos TOMAS seguidas de la misma escena NO pueden tener el mismo tipo: si la primera es PA, la "
        "segunda es PM o PP. Cambiá la distancia, no el lugar.\n"
        "- Sin texto ni carteles legibles. Si el lugar necesita un cartel, que esté en CASTELLANO.\n\n"
        "REGLAS DEL MOVIMIENTO (`mueve`), una por CLIP:\n"
        f"- Qué pasa durante los {SEGUNDOS} s, en inglés. El que habla, habla mirando al otro; el otro "
        "escucha y reacciona con la cara. La cámara NO se mueve.\n"
        "- TIENE QUE PASAR ALGO VISIBLE: una mano que sube y baja, la cabeza que se gira y vuelve, los "
        "hombros que caen, los ojos que se cierran un momento, el sombrero que se aprieta. El 22/9 pedí "
        "sólo «movimiento chico» y los personajes quedaron como estatuas hablando.\n"
        "- El movimiento ARRANCA Y TERMINA en la pose del dibujo: va y vuelve, como una respiración. Así "
        "el clip siguiente, que empieza en esa misma pose, engancha sin que se note el corte.\n\n"
        "LOCACIÓN: reusá una ya definida si es el mismo lugar (el mismo lugar con otra luz es LA MISMA "
        "locación: la luz va en `ve`). Si es un lugar nuevo, definilo en `locacion_nueva`.\n\n"
        + (f"Notas del director: {notas}\n\n" if notas.strip() else "")
        + 'Devolvé JSON: {"loc": "id", "locacion_nueva": {"id": "…", "descripcion": "inglés, el lugar SIN gente, '
          'luz, materiales, época", "prompt": "inglés, para dibujar el lugar vacío en 16:9"}, '
          '"tomas": [{"tipo": "PM", "ve": "…"}], '
          '"clips": [{"id": "S01", "mueve": "…", "audio": "[SFX] … [Ambient] … [Foley] …"}]}\n'
        f'Tiene que haber exactamente {len(e.tomas)} tomas y {e.clips} clips, con estos ids en este orden: '
        f'{", ".join(i for g in ids for i in g)}.'
    )


def traducir_escenas(guion: str, reparto: dict, *, titulo: str = "", estilo_imagen: str = "",
                     estilo_video: str = "", cierre_video: str = "", medio: str = "",
                     notas: str = "", por_dibujo: int | None = None,
                     por_dibujo_por_escena: dict[int, int] | None = None,
                     locaciones: dict | None = None, clave: str | None = None,
                     log=print) -> dict:
    """Del guion actuado al proyecto. `por_dibujo` rearma todas las escenas a N
    clips por dibujo; `por_dibujo_por_escena` lo hace escena por escena (para
    comparar en una misma corrida cuántos clips aguanta un dibujo)."""
    alias = {}
    for pid, v in (reparto.get("personajes") or {}).items():
        alias[pid.upper()] = pid
        nombre = str(v.get("nombre") or "").strip()
        if nombre:
            alias[nombre.upper().split()[0]] = pid
            alias[nombre.upper()] = pid
    escenas = parsear(guion, alias)
    if not escenas:
        raise ErrorGuionista("el guion no tiene ninguna escena con diálogo")
    for i, e in enumerate(escenas):
        n = (por_dibujo_por_escena or {}).get(i + 1, por_dibujo)
        if n:
            reagrupar(e, n)

    locaciones = dict(locaciones or {})
    madre_locs: list[dict] = []
    planos: list[dict] = []
    llamadas = 0
    k = 0
    for i, e in enumerate(escenas):
        ids = []
        for t in e.tomas:
            ids.append([f"S{k + j + 1:02d}" for j in range(len(t.lineas))])
            k += len(t.lineas)
        pedido = _pedido(e, ids, reparto, locaciones, estilo_imagen, medio, notas, i, len(escenas))
        for intento in range(3):
            llamadas += 1
            r = _json(_llamar([{"role": "system", "content": "Sos director de fotografía. Respondés sólo JSON, en el formato pedido."},
                               {"role": "user", "content": pedido}], clave=clave))
            if len(r.get("tomas") or []) == len(e.tomas) and len(r.get("clips") or []) == e.clips:
                break
            log(f"  escena {i + 1}: el modelo devolvió {len(r.get('tomas') or [])} tomas y "
                f"{len(r.get('clips') or [])} clips; reintento {intento + 1}/3")
        else:
            raise ErrorGuionista(f"la escena {i + 1} no se pudo traducir")

        nueva = r.get("locacion_nueva") or {}
        loc = re.sub(r"[^a-z0-9_]+", "_", str(r.get("loc") or "").lower()).strip("_")
        if loc not in locaciones and isinstance(nueva, dict) and nueva.get("descripcion"):
            loc = re.sub(r"[^a-z0-9_]+", "_", str(nueva.get("id") or loc or f"loc_{i + 1}").lower()).strip("_")
            locaciones[loc] = {"imagen": f"l_{loc}", "descripcion": str(nueva["descripcion"]).strip()}
            madre_locs.append({"id": f"l_{loc}", "aspecto": "16:9", "refs": [],
                               "prompt": (str(nueva.get("prompt") or nueva["descripcion"]).strip()) + f" {estilo_imagen}"})
        if loc not in locaciones:
            loc = next(iter(locaciones), None)

        mueves = {str(c.get("id")): c for c in r["clips"] if isinstance(c, dict)}
        for j, (t, grupo) in enumerate(zip(e.tomas, ids)):
            tv = r["tomas"][j] if isinstance(r["tomas"][j], dict) else {}
            tipo = str(tv.get("tipo") or "PM").upper()
            if tipo not in TAMANOS:
                tipo = "PM"
            cabeza = grupo[0]
            for pid_, l in zip(grupo, t.lineas):
                c = mueves.get(pid_, {})
                pers = sorted({l.quien} | {x.quien for x in t.lineas if x.quien})
                p = {"id": pid_, "tipo": tipo, "corta": SEGUNDOS, "segundos": SEGUNDOS,
                     "loc": loc, "personajes": pers,
                     "refs": ([f"l_{loc}"] if loc else []) + [f"m_{q}" for q in pers],
                     "funcion": f"{e.titulo} · toma {j + 1}",
                     "ve": str(tv.get("ve") or "").strip(),
                     "mueve": str(c.get("mueve") or "").strip(),
                     "audio": str(c.get("audio") or "").strip(),
                     "dialogo": l.texto, "habla": l.quien, "off": False}
                if pid_ != cabeza:
                    # El mismo dibujo que la cabeza de la toma: ni storyboard ni
                    # generación aparte. Es lo que baja 79 dibujos a ~19.
                    p["dibujo"] = f"sb_{cabeza}.png"
                if j == 0:
                    p["interrupcion"] = True        # arranca escena: lugar y luz nuevos
                planos.append(p)
        log(f"  escena {i + 1}/{len(escenas)}: {len(e.tomas)} dibujo(s), {e.clips} clips · loc {loc}")

    usados = {q for p in planos for q in p["personajes"]}
    d = {"titulo": titulo or "SIN TÍTULO", "formato": "largo", "estructura": "largo",
         "duracion_objetivo": round(len(planos) * SEGUNDOS, 2),
         "_concepto": escenas[0].titulo, "estilo_imagen": estilo_imagen, "estilo_video": estilo_video,
         "cierre_video": cierre_video, "medio": medio or "live-action film", "solo_sonidos": "",
         "negativos": True, "idioma": "es",
         "personajes": {pid: {"hoja": v["hoja"], "descripcion": v["descripcion"]}
                        for pid, v in (reparto.get("personajes") or {}).items() if pid in usados},
         "locaciones": {lid: v for lid, v in locaciones.items() if any(p["loc"] == lid for p in planos)},
         "madre": [m for m in madre_locs if any(p["loc"] == m["id"][2:] for p in planos)],
         "planos": planos, "voz": []}
    avisos = revisar(d)
    try:
        pr = Proyecto.desde_dict(d)
        avisos += pr.validar()
    except (ProyectoInvalido, KeyError, TypeError, ValueError) as e_:
        raise ErrorGuionista(f"el proyecto no carga: {e_}")
    return {"proyecto": d, "avisos": avisos, "intentos": llamadas,
            "dibujos": sum(1 for p in planos if not p.get("dibujo")), "clips": len(planos)}


def revisar(d: dict) -> list[str]:
    """Los defectos que medí en «EL CAMIÓN DE MI PADRE» y que nadie chequeaba."""
    avisos = []
    planos = d.get("planos") or []
    pd = [p for p in planos if p.get("tipo") == "PD"]
    if len(pd) > max(1, len(planos) // 20):
        avisos.append(f"{len(pd)} insertos de objeto (PD) en {len(planos)} planos: el tope es 1 cada 20")
    for a, b in zip(planos, planos[1:]):
        if b.get("dibujo"):
            continue        # comparten dibujo a propósito: no es un corte
        if (a.get("tipo"), a.get("loc"), tuple(a.get("personajes") or [])) == \
           (b.get("tipo"), b.get("loc"), tuple(b.get("personajes") or [])):
            avisos.append(f"{a['id']}→{b['id']}: mismo tipo, misma locación y mismo reparto (es un brinco, no un corte)")
    racha, cur = 0, None
    for p in planos:
        racha = racha + 1 if p.get("loc") == cur else 1
        cur = p.get("loc")
        if racha == 13:
            avisos.append(f"{p['id']}: más de 12 planos seguidos en «{cur}»")
    for p in planos:
        n = len(str(p.get("dialogo") or "").split())
        if n > MAX_PALABRAS:
            avisos.append(f"{p['id']}: la línea tiene {n} palabras; en {SEGUNDOS} s entran {MAX_PALABRAS}")
    if re.search(r"\b(sign|poster|banner|label)\b.{0,40}\b(reading|that says|with the words)\b",
                 json.dumps(planos, ensure_ascii=False), re.I):
        avisos.append("algún `ve` pide un cartel con texto legible: revisá que esté en castellano")
    return avisos
