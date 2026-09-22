"""DIÁLOGOS ACTUADOS DENTRO DE UN LARGO NARRADO (pedido del usuario, 21/9/2026).

En «EL CAMIÓN DE MI PADRE» Pablo narra todo, incluidas las frases que dicen
los personajes («Tomás, estás despedido»). El usuario: «en los momentos donde
la señora dijo… ¿no lo podemos hacer hablado por los personajes?», y después:
«usás las mismas imágenes y todo, sólo los videos».

Cómo, sin tocar nada de lo ya generado:

  1. Se buscan las citas entre comillas en la voz en off. Cada cita corta
     (≤ `MAX_PALABRAS`) con un hablante del reparto pasa a ser un plano nuevo
     `D01, D02…` donde ESE personaje la dice en cámara (Ref2VA con su voz de
     referencia). Las largas siguen en la voz del narrador.
  2. Se saca de la línea de tiempo exactamente la ventana en la que el narrador
     leía la cita —de la voz Y de la imagen— y en su lugar entra el plano D.
     Así la narración y los planos de después se corren lo mismo: no hay
     deriva. El plano cortado se parte con `usa` (la primera parte conserva su
     id; la segunda es `<id>b`, `clip_de` el mismo clip): los clips ya bajados
     sirven tal cual.
  3. El primer fotograma del plano D es un dibujo YA HECHO (`dibujo`): el del
     plano más cercano donde se ve a ese personaje, preferentemente en PM/PP.
  4. Lo que queda del texto de la línea (lo que va antes y después de las
     comillas) sigue en la voz del narrador; las colas de 1 a 4 palabras
     («dijo», «murmuró sin mirarme») se sacan: ahora se ve quién habla.

Al masterizar, `montaje.ajustar_usa_por_voz` recorta cada D alrededor de la voz
medida y la narración de después se corre sola (está anclada a sus planos).
"""
from __future__ import annotations

import json
import re

from . import grilla
from .proyecto import Proyecto

MAX_PALABRAS = 12          # en 5,17 s (el largo probado en 5090 con referencias) entran ~12 palabras
COLA_MAX = 4               # palabras: «dijo», «murmuró sin mirarme» → se sacan
ARRANQUE_H3 = 0.6          # s: donde se estima que empieza a usarse el plano D
PALABRA_S = 0.42           # s por palabra hablada (estimado; el montaje mide la real)
SOBRA_MIN = 1.0            # s: un pedacito de plano más corto que esto entre dos cortes se saca
_RE_CITA = re.compile(r"[“\"«]([^”\"»]+)[”\"»]")


def _palabras(t: str) -> int:
    return len(re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ']+", t))


def _limpiar_cola(t: str) -> str:
    t = re.sub(r"^\s*[,.;:—–-]+\s*", "", t).strip()
    return t


def citas_de(voz: list[dict], tiempos: list[float], cps: float) -> list[dict]:
    """Las citas de la voz en off, con su ventana estimada. Una cita puede
    abarcar varias líneas (el partidor de oraciones corta dentro de las
    comillas: «“Tomás, estás despedido.» / «Andate ya del predio.”»)."""
    # Todo el texto en una tira, con el tiempo de cada carácter.
    tira, t_car, linea_de = "", [], []
    for k, (v, t) in enumerate(zip(voz, tiempos)):
        txt = v["texto"]
        if tira:
            tira += " "
            t_car.append(t)
            linea_de.append(k)
        for j, _ch in enumerate(txt):
            t_car.append(t + j / cps)
            linea_de.append(k)
        tira += txt
    out = []
    for m in _RE_CITA.finditer(tira):
        texto = re.sub(r"\s+", " ", m.group(1)).strip()
        a, b = m.start(), m.end()
        out.append({"texto": texto, "palabras": _palabras(texto),
                    "t0": t_car[a], "t1": t_car[b - 1] + 1 / cps,
                    "lineas": sorted(set(linea_de[a:b])), "car": (a, b)})
    return out, tira, t_car, linea_de


def _partir(c: dict, tira: str, t_car: list[float]) -> list[dict]:
    """La cita `c` partida por oraciones, cada una con su tramo de caracteres y
    su ventana. Vacío si es una sola oración."""
    a, b = c["car"]
    interior = tira[a + 1:b - 1]
    cortes = [m.end() for m in re.finditer(r"[.!?…]+\s+", interior)]
    if not cortes:
        return []
    out, ini = [], 0
    for fin in cortes + [len(interior)]:
        trozo = interior[ini:fin]
        if trozo.strip():
            # el primer trozo se lleva la comilla de apertura; el último, la de cierre
            ca = a if ini == 0 else a + 1 + ini
            cb = b if fin == len(interior) else a + 1 + fin
            texto = re.sub(r"\s+", " ", trozo).strip()
            out.append({"texto": texto, "palabras": _palabras(texto), "car": (ca, cb),
                        "t0": t_car[ca], "t1": t_car[cb - 1] + 1e-3})
        ini = fin
    return out if len(out) > 1 else []


def insertar(d: dict, hablantes: dict[str, str | None], cps: float, log=print) -> dict:
    """Modifica `d` (proyecto.json de un largo narrado) en el lugar. `hablantes`:
    {texto de la cita → id de personaje o None}. Devuelve un resumen."""
    p = Proyecto.desde_dict(d)
    base = p.construir()[1]["planos"]
    est = p.estructura_resuelta()
    lt = dict(zip((x["id"] for x in base), est.linea_de_tiempo(base)))
    # Tiempos absolutos de cada línea de voz (orden original).
    voz = list(d.get("voz") or [])
    tiempos = []
    for v in voz:
        if v.get("plano") in lt:
            tiempos.append(lt[v["plano"]][0] + float(v.get("offset", 0.4)))
        else:
            tiempos.append(float(v.get("t") or 0.0))
    citas, tira, t_car, linea_de = citas_de(voz, tiempos, cps)
    pers = d.get("personajes") or {}
    elegidas = []
    for c in citas:
        pid = hablantes.get(c["texto"])
        if not pid or pid not in pers:
            continue
        if c["palabras"] > MAX_PALABRAS:
            # Una cita de varias oraciones se parte en planos seguidos del mismo
            # personaje si cada oración entra («Este camión fue de mi padre y
            # después mío. / Si lo manejás vos, va a ser para pagar lo que rompiste.»).
            partes = _partir(c, tira, t_car)
            if partes and all(x["palabras"] <= MAX_PALABRAS for x in partes):
                for x in partes:
                    x["pid"] = pid
                    elegidas.append(x)
                continue
            log(f"  cita larga ({c['palabras']} palabras), sigue narrada: «{c['texto'][:50]}…»")
            continue
        c["pid"] = pid
        elegidas.append(c)
    if not elegidas:
        return {"dialogos": 0}

    # ── 1 · la voz: se saca el texto de cada cita (y su cola corta) ────────────
    quitar = [False] * len(tira)
    for c in elegidas:
        a, b = c["car"]
        for i in range(a, b):
            quitar[i] = True
        # la cola: lo que sigue a la cita hasta el fin de la oración, si es corto
        resto = tira[b:]
        m = re.match(r"([^.!?…“\"«]*[.!?…]?)", resto)
        cola = m.group(1) if m else ""
        if cola and _palabras(cola) <= COLA_MAX and not re.match(r"\s*[“\"«]", resto):
            for i in range(b, b + len(cola)):
                quitar[i] = True
    # Reconstruir cada línea con lo que queda, con el tiempo de su primer carácter.
    piezas: list[dict] = []
    actual, t_ini, k_act = "", None, None
    for i, ch in enumerate(tira):
        k = linea_de[i]
        if k != k_act:
            if actual.strip():
                piezas.append({"texto": actual, "t": t_ini})
            actual, t_ini, k_act = "", None, k
        if quitar[i]:
            if actual.strip():
                piezas.append({"texto": actual, "t": t_ini})
            actual, t_ini = "", None
            continue
        if t_ini is None and not ch.isspace():
            t_ini = t_car[i]
        actual += ch
    if actual.strip():
        piezas.append({"texto": actual, "t": t_ini})
    piezas = [{"texto": re.sub(r"\s+", " ", _limpiar_cola(x["texto"])).strip(), "t": x["t"]} for x in piezas]
    piezas = [x for x in piezas if _palabras(x["texto"]) >= 2 or re.search(r"\d", x["texto"])]

    # ── 2 · los planos D y la línea de tiempo nueva ────────────────────────────
    ventanas = []
    for n, c in enumerate(elegidas, 1):
        nom = pers[c["pid"]].get("nombre") or c["pid"]
        hablado = 1.0 + c["palabras"] * PALABRA_S
        seg = grilla.MINIMO   # siempre 5,17: Ref2VA con hoja + voz en 32 GB sólo está probado a ese largo
        usa = [ARRANQUE_H3, round(min(seg - 0.05, ARRANQUE_H3 + hablado + 0.4), 2)]
        ventanas.append({"t0": c["t0"], "t1": c["t1"], "pid": c["pid"], "texto": c["texto"],
                         "id": f"D{n:02d}", "segundos": round(seg, 3), "usa": usa, "nombre": nom})
    # Nuevo orden de planos: se recorta de la imagen la ventana de cada cita.
    originales = [x for x in d["planos"]]
    ids_base = [x["id"] for x in base]
    nuevos: list = []
    vi = 0
    hasta = -1.0          # lo que ya se comió una ventana anterior (puede cruzar planos)
    for po, pid in zip(originales, ids_base):
        a, b = lt[pid]
        cursor = max(a, hasta)
        partes = []
        while vi < len(ventanas) and ventanas[vi]["t0"] < b:
            w = ventanas[vi]
            if w["t0"] > cursor + SOBRA_MIN:
                partes.append(("clip", cursor, w["t0"]))
            partes.append(("D", w))
            cursor = max(cursor, w["t1"])
            hasta = max(hasta, w["t1"])
            vi += 1
        if cursor < b - SOBRA_MIN:
            partes.append(("clip", cursor, b))
        n_clip = 0
        for parte in partes:
            if parte[0] == "D":
                nuevos.append(("D", parte[1]))
                continue
            _k, x0, x1 = parte
            q = dict(po)
            if abs(x0 - a) < 0.01 and abs(x1 - b) < 0.01:
                nuevos.append(("P", q))
                n_clip += 1
                continue
            q["usa"] = [round(x0 - a, 3), round(x1 - a, 3)]
            if n_clip:
                q = {**q, "id": f"{pid}{'bcdefg'[n_clip - 1]}", "clip_de": pid}
                q.pop("prompt_h3", None)
            nuevos.append(("P", q))
            n_clip += 1

    # Plano D: el dibujo ya hecho más cercano con ese personaje (PM/PP primero).
    def dibujo_para(w: dict) -> dict:
        cand = []
        for po, pid in zip(originales, ids_base):
            if w["pid"] in (po.get("personajes") or []):
                a, _b = lt[pid]
                pref = 0 if po.get("tipo") in ("PM", "PP", "PA") else 1
                solo = 0 if len(po.get("personajes") or []) == 1 else 1
                cand.append((pref, solo, abs(a - w["t0"]), po))
        if not cand:
            return originales[0]
        cand.sort(key=lambda x: (x[2] > 40, x[0], x[1], x[2]))
        return cand[0][3]

    planos_final = []
    for tipo, x in nuevos:
        if tipo == "P":
            planos_final.append(x)
            continue
        w = x
        src = dibujo_para(w)
        nom = w["nombre"]
        planos_final.append({
            "id": w["id"], "tipo": src.get("tipo", "PM"), "tramo": src.get("tramo"), "segundos": w["segundos"],
            "usa": w["usa"], "loc": src.get("loc"), "personajes": list(dict.fromkeys([w["pid"]] + list(src.get("personajes") or []))),
            "refs": list(src.get("refs") or []), "dibujo": f"sb_{src['id']}.png", "texto": "",
            "funcion": f"DIÁLOGO: {nom} dice en cámara «{w['texto']}»",
            "ve": (src.get("ve") or "").rstrip() + f" {nom} faces the camera (front or three-quarter view), face and mouth clearly visible and free.",
            "mueve": f"{nom} looks at the person in front of them and says one short line, with a small natural gesture; then stays silent, lips closed.",
            "audio": src.get("audio", ""), "dialogo": f"{nom}: {w['texto']}", "habla": w["pid"], "off": False,
            "cita_de": src["id"],
        })

    # ── 3 · la voz, anclada a los planos nuevos ────────────────────────────────
    # t_nuevo = t_viejo + Σ (largo_D − largo_ventana) de las ventanas anteriores.
    def corrimiento(t: float) -> float:
        s = 0.0
        for w in ventanas:
            if w["t1"] <= t + 0.01:
                s += (w["usa"][1] - w["usa"][0]) - (w["t1"] - w["t0"])
        return s
    d2 = dict(d, planos=planos_final, voz=[])
    p2 = Proyecto.desde_dict(d2)
    b2 = p2.construir()[1]["planos"]
    lt2 = list(zip((x["id"] for x in b2), p2.estructura_resuelta().linea_de_tiempo(b2)))
    voz_nueva = []
    for x in piezas:
        tn = x["t"] + corrimiento(x["t"])
        # el plano que contiene tn; si cae dentro de un D (no debería), el siguiente
        dest = next(((pid, a) for pid, (a, b) in lt2 if a <= tn < b), lt2[-1][0:1] + (lt2[-1][1][0],))
        pid, a = dest[0], dest[1]
        if pid.startswith("D"):
            idx = [q[0] for q in lt2].index(pid)
            if idx + 1 < len(lt2):
                pid, a = lt2[idx + 1][0], lt2[idx + 1][1][0]
                tn = max(tn, a + 0.1)
        voz_nueva.append({"plano": pid, "offset": round(max(0.0, tn - a), 2), "texto": x["texto"]})
    d["planos"] = planos_final
    d["voz"] = voz_nueva
    d["dialogos"] = [{"id": w["id"], "habla": w["pid"], "texto": w["texto"]} for w in ventanas]
    return {"dialogos": len(ventanas), "planos": len(planos_final), "voz": len(voz_nueva),
            "detalle": [(w["id"], w["nombre"], w["texto"]) for w in ventanas]}


def citas_del_proyecto(d: dict, cps: float) -> list[dict]:
    """Las citas de la voz en off de un proyecto, con su ventana estimada."""
    p = Proyecto.desde_dict(d)
    base = p.construir()[1]["planos"]
    lt = dict(zip((x["id"] for x in base), p.estructura_resuelta().linea_de_tiempo(base)))
    voz = list(d.get("voz") or [])
    tiempos = [lt[v["plano"]][0] + float(v.get("offset", 0.4)) if v.get("plano") in lt else float(v.get("t") or 0.0) for v in voz]
    return citas_de(voz, tiempos, cps)[0]


def hablantes_por_gpt(citas: list[dict], contexto: str, personajes: dict, narrador: str | None, log=print) -> dict:
    """{cita → id} preguntándole a GPT quién dice cada cita, con el guion entero de contexto."""
    from .guionista import _json, _llamar
    lista = "\n".join(f"{i + 1}. «{c['texto']}»" for i, c in enumerate(citas))
    pers = "\n".join(f"- `{pid}`: {v.get('nombre') or pid}. {v.get('descripcion', '')[:160]}" for pid, v in personajes.items())
    ins = (f"Guion narrado en primera persona" + (f" por `{narrador}`" if narrador else "") + ":\n" + contexto[:9000] +
           f"\n\nPERSONAJES:\n{pers}\n\nCITAS entre comillas:\n{lista}\n\n"
           "Para cada cita decí qué personaje la dice en voz alta, con su id. Si la cita la dice el narrador, es su id. "
           "Si no la dice nadie del reparto (un cartel, un pensamiento, alguien sin id), null.\n"
           "Devolvé JSON: {\"hablantes\": [id o null, … en el mismo orden]}")
    r = _json(_llamar([{"role": "system", "content": "Respondés sólo JSON."}, {"role": "user", "content": ins}]))
    ids = list(r.get("hablantes") or [])
    return {c["texto"]: (ids[i] if i < len(ids) and ids[i] in personajes else None) for i, c in enumerate(citas)}
