"""EL REESCRITOR: de lo que alguien quiere al prompt que MiniMax H3 espera.

Nadie que use La Fábrica tiene por qué saber escribir el formato oficial de H3
(`[Shot 1]`, `<d>[Spanish] …</d>`, `overall_soundscape`, cámara con tipo +
amplitud + velocidad, ni las trampas que medimos: los negativos invocan lo que
prohíben, la boca tapada no habla, el género de origen trae subtítulos). MiniMax
resuelve eso con su reescritor H3-Context-IR antes de que el prompt llegue al
modelo, y su README lo llama "critical to the quality". Local no hay Context-IR:
esto es el nuestro.

Entra un PEDIDO (dict) con lo que se sabe del plano —duración, formato, estilo,
qué se ve en el primer fotograma (y la imagen misma si ya existe), qué pasa, qué
se oye, qué dice quién y en qué idioma— y sale UN prompt en el formato oficial
I2VA, validado. Si el modelo falla dos veces, sale la plantilla determinista
(`prompts.oficial_i2va`) para que nunca se mande texto libre.

Se usa en los cuatro caminos: short, largo y music video (por plano, al
traducir el guion y al empaquetar, cuando ya está el dibujo) y Libre (por turno,
con la foto).

    python -m h3pipeline reescribir mis-videos/<slug>/proyecto.json [--forzar] [--solo P01 P02]
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from . import config, grilla, prompts

API = "https://api.openai.com/v1/chat/completions"
MODELO = "gpt-5.1"
MODELO_RESPALDO = "gpt-4.1"
IDIOMAS = {"es": "Spanish", "en": "English", "pt": "Portuguese", "it": "Italian", "fr": "French"}


class ErrorReescritor(Exception):
    pass


# ───────────────────────────────────────────────────────────── la guía

GUIA = """You rewrite a video request into the exact prompt format of MiniMax H3 (mode I2VA: one reference image is the first frame). You are the equivalent of MiniMax's official prompt rewriter. Output ONLY the final prompt, nothing else: no title, no commentary, no code fences.

FORMAT (exact field names, this order, one blank line between parts):
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] <style tag>, <shot size>, <everything visible in the first frame: subject(s), clothing, key objects, place, light> ... <what happens over time> ... <camera>.

overall_soundscape: <1-4 sentences: ambience, physical sounds, breathing; never the dialogue>

non_diegetic_music: N/A

RULES
1. Everything in English, except the words inside <d>…</d>, which stay exactly in their original language.
2. ONE shot: a single [Shot 1] with no timestamp. Never add [Shot 2] unless the request lists INTERNAL CUTS. When it does, write one extra shot per listed cut, in order, each starting with its exact time: "[Shot 2] At 00:05.000, the camera cuts to a close-up of …". Same place, same character(s) with the same clothing, same light and same voices across every shot: it is one continuous scene edited in camera. Each cut introduces new information (a new shot size, angle, state or object), as the listed cut says. If a line of dialogue is spoken across a cut, put <scenetrans> at the connecting points in both parts and say the audio continues uninterrupted across the cut. Keep the first-frame instruction line exactly as it is: <Picture 1> anchors [Shot 1] only.
3. First anchor the first frame: state the visual style (Live-action / 2D-animated / 3D CG / photorealistic…), the shot size, and describe concretely what the image shows (people with clothing and position, objects, place, time of day, light). When an image is attached, describe THAT image faithfully; the video must preserve its identity, clothing, framing and layout. Only then describe the action in time, with the phrases "Early in the clip…", "As the clip progresses…", "Throughout the remainder of the clip…". Match the total action to the requested duration.
4. Camera: motion type + amplitude + speed written as prose, using this vocabulary: Zoom In/Out, Push In/Pull Out, Pan Left/Right, Truck Left/Right, Tilt Up/Down, Pedestal Up/Down, Arc Shot, Tracking Shot, Static Shot, Shake Slightly/Strongly, POV, Roll; "with small/large amplitude", "at slow/fast speed". Example: "The camera pushes in with small amplitude at slow speed toward her hands." If no camera move is requested, say the camera holds a static shot throughout.
5. Speech. Each speaker gets a stable ID (S1), (S2). The first time a speaker appears, describe the voice: age, gender, pitch, timbre, pace, accent. Put the ID, action and delivery OUTSIDE <d>. Inside <d> put only the language tag and the literal line: <d>[Spanish] Cuéntame.</d>. Copy every line VERBATIM, word for word, same punctuation, in the given order. Do not translate, shorten, merge or add lines.
   - On-screen speaker: make the mouth visible and moving. If something covers the mouth in the first frame (a pen, a cup, a hand, a scarf), the character moves it away before speaking. Write "its/his/her mouth opens and closes clearly in sync with each word" for each line.
   - Before the first line the lips stay closed; after the last line write "Exactly as the voice stops, the lips close and the jaw stops moving" and that the character does not speak again for the rest of the clip.
   - Off-screen voice: use exactly "says in an off-screen voiceover: <d>…</d>" and, right after, that the on-screen character's lips remain completely closed. A narrator who is never seen is off-screen.
   - Characters that never speak: nothing about speech is written for them, except that their lips stay closed if a voice-over plays.
6. NEVER write prohibitions or negatives: no "no", "not", "never", "without", "do not", "avoid", "free of". Naming something to forbid it makes the model draw it. Describe only what IS there and what DOES happen. If the request says the scene must stay still, write it positively: "Everything stays exactly as in the first frame for the whole shot: the same place, objects and light; the only motion is …".
7. Do not invent people, animals, vehicles, fire, smoke, text or signs that the request or the image does not contain. Add only small, natural details consistent with the scene (dust in a light beam, breathing, fabric moving).
8. On-screen text only if the request gives it, in English double quotes, verbatim. Never mention subtitles, captions, watermarks or the name of a franchise, show or game.
9. overall_soundscape: concrete sounds in one paragraph. If the request says the music is added later or asks for a silent ambience, keep it to room tone and physical sounds.
10. non_diegetic_music is always "N/A" unless the request explicitly asks H3 to compose music.
11. Length: about 180-350 words for clips up to 7 seconds, 300-550 words for 10-15 seconds. Concrete nouns and verbs; adjectives like "beautiful", "stunning", "epic" add nothing.

EXAMPLE (official, I2VA, 6 s, one speaker on screen):
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, the young woman shown in <Picture 1> remains beside the rain-covered train window, preserving her appearance, clothing, seat position, and the carriage layout. The camera trucks right with small amplitude at slow speed as she lifts her gaze from the folded letter toward the passing city lights. Her reflection moves across the glass while the quiet, breathy young woman (S1) says, her mouth opening and closing clearly in sync with each word: <d>[English] I get off at the next station.</d> Exactly as her voice stops, her lips close and her jaw stops moving; she folds the letter along its existing crease and holds it in her lap through the end of the clip.

overall_soundscape: The train wheels produce a steady metallic rhythm beneath a low ventilation hum. Rain ticks against the window while paper rustles softly in her hands.

non_diegetic_music: N/A
"""


# ───────────────────────────────────────────────────────────── el pedido

_OFF = re.compile(r"\((?:fuera de cuadro|en off|off|voz en off|off-screen|voice-?over|v\.?o\.?)\)", re.I)


def lineas_de(dialogo: dict) -> list[dict]:
    """Las líneas habladas: [{quien, texto, off}]. `texto` puede venir como una
    sola línea, varias, o con rótulo «QUIÉN: texto» por línea (el rótulo no se
    dice; «(fuera de cuadro)» u «(off)» en el rótulo marca voz en off)."""
    out = []
    for cruda in (dialogo.get("texto") or "").splitlines():
        s = cruda.strip()
        if not s:
            continue
        quien, off = dialogo.get("quien"), bool(dialogo.get("off"))
        m = re.match(r"^([^:：]{1,40})[:：]\s*(.+)$", s)
        if m and not re.search(r"[.!?¿¡]", m.group(1)):
            rotulo = m.group(1).strip()
            off = off or bool(_OFF.search(rotulo))
            quien = _OFF.sub("", rotulo).strip(" -–—") or quien
            s = m.group(2).strip()
        out.append({"quien": quien, "texto": s, "off": off})
    return out


def pedido_texto(p: dict) -> str:
    """El pedido como texto para el modelo (lo que hay; lo que falta se omite)."""
    L = []
    dur = float(p.get("duracion") or grilla.MINIMO)
    L.append(f"Duration: {dur:.2f} seconds. Frame: {p.get('aspecto', '16:9')} "
             f"({'vertical' if p.get('aspecto') == '9:16' else 'horizontal'}).")
    if p.get("estilo"):
        L.append(f"Visual style: {p['estilo']}")
    if p.get("medio"):
        L.append(f"Medium: {p['medio']}")
    if p.get("tamano"):
        L.append(f"Shot size: {p['tamano']}")
    if p.get("primer_fotograma"):
        L.append("First frame (what the reference image shows"
                 + (", and the image itself is attached" if p.get("imagen") else "") + f"): {p['primer_fotograma']}")
    elif p.get("imagen"):
        L.append("First frame: the attached image. Describe it faithfully.")
    if p.get("personajes"):
        L.append("Characters present (keep them exactly like this): " + " | ".join(p["personajes"]))
    if p.get("accion"):
        L.append(f"What happens during the clip: {p['accion']}")
    if p.get("camara"):
        L.append(f"Camera: {p['camara']}")
    if p.get("cortes"):
        L.append("INTERNAL CUTS inside this single clip (one continuous scene edited in camera: same place, same character, same "
                 "clothing, same voice; the story simply continues): "
                 + "; ".join(f"at {float(c['t']):.1f} s the camera cuts to {c.get('tamano', 'a new shot')}: {c.get('ve', '')}".rstrip(": ") for c in p["cortes"])
                 + ". Number them [Shot 2], [Shot 3]… with exactly those times (mm:ss.mmm). Put each dialogue line in the shot where it is spoken.")
    if p.get("quieto"):
        L.append("The scene is still: everything stays as in the first frame; only the motion described above happens. Write this positively.")
    if p.get("audio"):
        L.append(f"Sounds heard: {p['audio']}")
    d = p.get("dialogo")
    lineas = lineas_de(d) if d else []
    if lineas:
        lengua = IDIOMAS.get(d.get("idioma", "es"), "Spanish")
        voz = f" Voice notes: {d['voz']}." if d.get("voz") else ""
        quien_gen = f" Speaker(s): {d['quien']}." if d.get("quien") and not any(l["quien"] and l["quien"] != d.get("quien") for l in lineas) else ""
        L.append(f"Speech in {lengua}, in this exact order.{quien_gen}{voz} The speaker label is WHO says it (it is never spoken); "
                 "the text after «» is the literal line to copy inside <d>:")
        for l in lineas:
            donde = "off-screen, voice-over, never seen" if l["off"] else "on screen, mouth visible and moving"
            L.append(f"- {l['quien'] or 'the character on screen'} ({donde}): «{l['texto']}»")
        if d.get("inicio"):
            L.append(f"The first word starts at about {float(d['inicio']):.1f} s; before that the lips are closed.")
    elif p.get("personajes"):
        L.append("Nobody speaks in this clip; lips stay closed. The voice-over is added later, outside H3.")
    else:
        L.append("Nobody speaks in this clip.")
    L.append("Music is added later, outside H3: non_diegetic_music must be N/A."
             if p.get("musica_aparte", True) else "H3 may compose background music.")
    if p.get("notas"):
        L.append(f"Notes from the director: {p['notas']}")
    return "\n".join(L)


def huella(p: dict) -> str:
    """Identifica el pedido: si no cambia, el prompt guardado sirve."""
    q = {k: v for k, v in p.items() if k != "imagen"}
    q["imagen"] = bool(p.get("imagen"))
    return hashlib.sha1(json.dumps(q, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


# ───────────────────────────────────────────────────────────── validación

NEGACIONES = re.compile(r"\b(no|not|never|without|don't|doesn't|avoid|nothing)\b", re.I)


def _normal(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    s = s.replace("…", "...")
    return re.sub(r"\s+", " ", s).strip().lower()


def validar(prompt: str, p: dict) -> list[str]:
    """Los problemas del prompt; vacío si está bien."""
    e = []
    t = prompt.strip()
    if not t.startswith(prompts.INSTRUCCION_I2VA):
        e.append("the first line must be exactly the I2VA instruction line")
    for campo in ("integrated_multimodal_description:", "overall_soundscape:", "non_diegetic_music:"):
        if campo not in t:
            e.append(f"missing field {campo}")
    if "[Shot 1]" not in t:
        e.append("missing [Shot 1]")
    cuerpo = t.split("integrated_multimodal_description:", 1)[-1].split("overall_soundscape:", 1)[0]
    n_shots = len(re.findall(r"\[Shot [1-9]\]", cuerpo))   # sólo el cuerpo: la línea de instrucción también dice [Shot 1]
    if n_shots > 1 and not p.get("cortes"):
        e.append("only one shot is allowed: remove [Shot 2] and later")
    if p.get("cortes") and n_shots != len(p["cortes"]) + 1:
        e.append(f"there must be exactly {len(p['cortes']) + 1} shots ([Shot 1] plus one per internal cut); found {n_shots}")
    d = p.get("dialogo")
    lineas = lineas_de(d) if d else []
    if lineas:
        bloques = re.findall(r"<d>\s*\[[^\]]+\]\s*(.*?)</d>", t, re.S)
        dentro = _normal(" ".join(bloques))
        for l in lineas:
            if _normal(l["texto"]) not in dentro:
                e.append(f"this line is missing or altered inside <d>: {l['texto']!r}")
            elif l["quien"] and any(_normal(b).startswith(_normal(l["quien"]) + ":") for b in bloques):
                e.append(f"the speaker label {l['quien']!r} must stay outside <d>; inside goes only the spoken text")
        if len(bloques) > len(lineas):
            e.append(f"there are {len(bloques)} <d> blocks for {len(lineas)} lines: one block per line, and nothing invented")
        lengua = IDIOMAS.get(d.get("idioma", "es"), "Spanish")
        if f"[{lengua}]" not in t:
            e.append(f"the language tag inside <d> must be [{lengua}]")
        if any(l["off"] for l in lineas) and "off-screen voiceover" not in t:
            e.append('an off-screen line must use the phrase "says in an off-screen voiceover"')
    elif "<d>" in t:
        e.append("the request has no speech: remove every <d>…</d> line")
    if p.get("musica_aparte", True) and not re.search(r"non_diegetic_music:\s*N/A", t):
        e.append("non_diegetic_music must be N/A")
    negs = NEGACIONES.findall(t)
    if len(negs) > 2:
        e.append(f"remove the negatives ({', '.join(sorted(set(x.lower() for x in negs)))}): describe only what is there and what happens")
    n = len(t.split())
    dur = float(p.get("duracion") or grilla.MINIMO)
    lim = (150, 420) if dur <= 7.5 else (240, 650)
    if n < lim[0]:
        e.append(f"too short ({n} words): describe the first frame and the action concretely, aim for {lim[0]}-{lim[1]} words")
    # Pasarse un poco es normal (los ejemplos oficiales de 8 s llegan a 700
    # palabras); sólo se reintenta si se va de mambo, para no pagar dos veces.
    if n > lim[1] + 250:
        e.append(f"too long ({n} words): keep it under {lim[1]} words")
    return e


# ───────────────────────────────────────────────────────────── el modelo

def _imagen_b64(ruta: Path, lado: int = 768) -> str | None:
    try:
        from PIL import Image
        im = Image.open(ruta).convert("RGB")
        im.thumbnail((lado, lado))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=82)
        return base64.b64encode(b.getvalue()).decode()
    except Exception:
        return None


def _chat(mensajes: list[dict], modelo: str = MODELO, clave: str | None = None) -> tuple[str, dict]:
    config.certificados()
    k = clave or config.leer_env("OPENAI_API_KEY")
    cuerpo = {"model": modelo, "messages": mensajes}
    if not modelo.startswith("gpt-5"):
        cuerpo["temperature"] = 0.3
    req = urllib.request.Request(API, data=json.dumps(cuerpo).encode(),
                                 headers={"Authorization": f"Bearer {k}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:600]
        if modelo != MODELO_RESPALDO and e.code in (400, 404):
            return _chat(mensajes, MODELO_RESPALDO, clave)
        raise ErrorReescritor(f"OpenAI HTTP {e.code}: {detalle}") from e
    return d["choices"][0]["message"]["content"], d.get("usage", {})


def _limpiar(texto: str) -> str:
    t = texto.strip()
    if t.startswith("```"):
        t = re.sub(r"^```[a-z]*\s*|\s*```$", "", t, flags=re.S).strip()
    i = t.find("For the target video")
    return t[i:].strip() if i > 0 else t


def plantilla(p: dict) -> str:
    """Salida determinista, sin modelo: el formato oficial armado con los campos
    tal cual. Es el piso: nunca se manda texto libre a H3."""
    partes = [f"{p.get('estilo') or 'Live-action, cinematic'}, {p.get('tamano') or 'medium shot'}."]
    if p.get("primer_fotograma"):
        partes.append(p["primer_fotograma"].rstrip(".") + ".")
    if p.get("personajes"):
        partes.append("Characters, exactly as in the first frame: " + "; ".join(p["personajes"]) + ".")
    if p.get("accion"):
        partes.append("Early in the clip and throughout, " + p["accion"].rstrip(".") + ".")
    if p.get("quieto"):
        partes.append(prompts.QUIETO)
    partes.append(f"The camera {p['camara'].rstrip('.')}." if p.get("camara") else "The camera holds a static shot throughout the entire clip.")
    d = p.get("dialogo")
    lineas = lineas_de(d) if d else []
    if lineas:
        lengua = IDIOMAS.get(d.get("idioma", "es"), "Spanish")
        ids: dict[str, str] = {}
        for l in lineas:
            quien = l["quien"] or d.get("quien") or "The character on screen"
            sid = ids.setdefault(quien, f"S{len(ids) + 1}")
            if l["off"]:
                partes.append(f"{quien} ({sid}) says in an off-screen voiceover: <d>[{lengua}] {l['texto']}</d> while the lips of everyone on screen remain completely closed.")
            else:
                partes.append(f"{quien} ({sid}) says, the mouth opening and closing clearly in sync with each word: <d>[{lengua}] {l['texto']}</d>")
        if any(not l["off"] for l in lineas):
            partes.append("Exactly as the last voice stops, the lips close and the jaw stops moving.")
    desc = "[Shot 1] " + " ".join(partes)
    sonido = p.get("audio") or "Quiet room tone with the small physical sounds of what moves in the frame."
    return prompts.oficial_i2va(desc, sonido, "N/A" if p.get("musica_aparte", True) else "soft background music")


def reescribir(p: dict, log=print, reintentos: int = 2, clave: str | None = None) -> dict:
    """{prompt, origen, intentos, problemas}. `p['imagen']` puede ser la ruta del
    primer fotograma: se manda al modelo para que describa lo que hay de verdad."""
    contenido: list = [{"type": "text", "text": "Rewrite this request into the H3 prompt.\n\n" + pedido_texto(p)}]
    img = p.get("imagen")
    if img and Path(str(img)).exists():
        b = _imagen_b64(Path(str(img)))
        if b:
            contenido.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}", "detail": "low"}})
    mensajes = [{"role": "system", "content": GUIA}, {"role": "user", "content": contenido}]
    problemas: list[str] = []
    salida = ""
    for intento in range(1, reintentos + 2):
        try:
            salida, uso = _chat(mensajes, clave=clave)
        except ErrorReescritor as e:
            log(f"    !! {e}")
            break
        salida = _limpiar(salida)
        problemas = validar(salida, p)
        log(f"    reescritor: intento {intento} · {len(salida.split())} palabras · "
            f"{uso.get('prompt_tokens', '?')}+{uso.get('completion_tokens', '?')} tokens"
            + (f" · {len(problemas)} problema(s)" if problemas else " · OK"))
        if not problemas:
            return {"prompt": salida, "origen": f"reescritor {MODELO}", "intentos": intento, "problemas": []}
        for pr in problemas:
            log(f"      - {pr}")
        mensajes.append({"role": "assistant", "content": salida})
        mensajes.append({"role": "user", "content": "Fix these problems and output the complete corrected prompt only:\n- " + "\n- ".join(problemas)})
    # Piso: la plantilla determinista. Si el modelo dejó algo casi bien (sólo
    # avisos de largo o negaciones) se prefiere su texto.
    graves = [x for x in problemas if not x.startswith(("too short", "too long", "remove the negatives"))]
    if salida and not graves:
        log("    aviso: se usa la salida del modelo con avisos menores")
        return {"prompt": salida, "origen": f"reescritor {MODELO} (con avisos)", "intentos": reintentos + 1, "problemas": problemas}
    log("    !! el modelo no dio un prompt válido: va la plantilla determinista")
    return {"prompt": plantilla(p), "origen": "plantilla", "intentos": reintentos + 1, "problemas": problemas}


# ───────────────────────────────────────────────────────────── proyectos

def pedido_de_plano(d: dict, p: dict, raiz: Path) -> dict:
    """El pedido de un plano a partir del proyecto.json crudo."""
    formato = d.get("formato", "largo")
    aspecto = "9:16" if formato == "short" else "16:9"
    tam = p.get("tipo", "SHORT" if formato == "short" else "PM")
    etiqueta = prompts.TAMANIO.get(tam, ("medium shot", ""))[0].lower()
    personajes = [d.get("personajes", {}).get(n, {}).get("descripcion", n) for n in (p.get("personajes") or [])]
    dialogo = None
    if p.get("dialogo"):
        quien = None
        if p.get("habla") and p["habla"] in d.get("personajes", {}):
            quien = d["personajes"][p["habla"]].get("descripcion")
        elif len(personajes) == 1:
            quien = personajes[0]
        dialogo = {"texto": p["dialogo"], "idioma": d.get("idioma", "es"), "quien": quien,
                   "off": bool(p.get("off") or not personajes), "voz": p.get("voz_desc")}
    segundos = p.get("segundos")
    if not segundos:
        segundos = grilla.encajar(max(grilla.MINIMO, float(p.get("corta") or 8.0) + 0.5))[1]
    img = raiz / "assets" / (p.get("dibujo") or f"sb_{p.get('id', '')}.png")
    ref2va = bool(p.get("modo") == "ref2va" and p.get("voz_ref") and dialogo)
    return {"modo": "ref2va" if ref2va else "i2va", "duracion": round(float(segundos), 3), "aspecto": aspecto,
            "voz_ref": bool(ref2va), "hoja_ref": bool(ref2va and p.get("refs_extra")),
            "habla_desc": (dialogo or {}).get("quien") if ref2va else None,
            "estilo": p.get("cabecera") or d.get("estilo_video") or d.get("estilo_imagen") or "",
            "medio": d.get("medio", "") if formato != "short" else "",
            "tamano": etiqueta, "primer_fotograma": p.get("ve", ""), "personajes": personajes,
            "accion": p.get("mueve", ""), "camara": p.get("camara", ""), "audio": p.get("audio") or d.get("solo_sonidos", ""),
            "dialogo": dialogo, "quieto": not d.get("negativos", True), "musica_aparte": True,
            "cortes": [c for c in (p.get("cortes") or []) if isinstance(c, dict) and c.get("t")],
            "notas": p.get("notas_h3", ""), "imagen": str(img) if img.exists() else None}


def completar(ruta_json: Path, log=print, forzar: bool = False, solo: list[str] | None = None) -> int:
    """Escribe `prompt_h3` en cada plano que no lo tenga al día. Devuelve cuántos
    se reescribieron. Se salta los planos que reusan el clip de otro."""
    ruta_json = Path(ruta_json)
    d = json.loads(ruta_json.read_text(encoding="utf-8"))
    raiz = ruta_json.parent
    hechos = 0
    for p in d.get("planos", []):
        pid = p.get("id", "?")
        if solo and pid not in solo:
            continue
        if p.get("clip_de"):
            continue
        if p.get("prompt_h3_manual"):
            log(f"  {pid}: prompt_h3 escrito a mano, se respeta")
            continue
        pedido = pedido_de_plano(d, p, raiz)
        h = huella(pedido)
        if not forzar and p.get("prompt_h3") and p.get("prompt_h3_de") == h:
            continue
        log(f"  {pid}: reescribiendo ({pedido['duracion']:.2f} s{', con dibujo' if pedido['imagen'] else ''})…")
        r = reescribir(pedido, log=log)
        if pedido.get("modo") == "ref2va":
            # La MISMA voz en todos los clips (21/9): el prompt I2VA validado se
            # envuelve en las seis secciones de Ref2VA con <Picture 2> (la hoja)
            # y <Audio 1> (la voz de referencia). Determinista: sin otra llamada.
            r["prompt"] = a_ref2va(r["prompt"], pedido)
            r["origen"] += " → ref2va"
        p["prompt_h3"] = r["prompt"]
        p["prompt_h3_de"] = h
        p["prompt_h3_origen"] = r["origen"]
        hechos += 1
        ruta_json.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return hechos


# ═══════════════════════════════════════════════ VOZ DE REFERENCIA (Ref2VA)

def _seccion(t: str, desde: str, hasta: str | None) -> str:
    cuerpo = t.split(desde, 1)[-1] if desde in t else ""
    if hasta and hasta in cuerpo:
        cuerpo = cuerpo.split(hasta, 1)[0]
    return cuerpo.strip()


def a_ref2va(prompt_i2va: str, p: dict) -> str:
    """Del prompt I2VA (una imagen = primer fotograma) al formato de referencia
    completa de Ref2VA, sin modelo: <Picture 1> sigue siendo el primer fotograma,
    <Picture 2> es la hoja de la cara del que habla (si viaja), <Audio 1> es su
    voz de referencia. El cuerpo del [Shot …] se conserva tal cual; sólo se le
    cuelga al hablante (S1) «using the voice timbre referenced from <Audio 1>»."""
    t = prompt_i2va.strip()
    cuerpo = _seccion(t, "integrated_multimodal_description:", "overall_soundscape:")
    sonido = _seccion(t, "overall_soundscape:", "non_diegetic_music:") or (p.get("audio") or "Quiet room tone with the small physical sounds of what moves in the frame.")
    musica = _seccion(t, "non_diegetic_music:", None) or "N/A"
    d = p.get("dialogo") or {}
    lengua = IDIOMAS.get(d.get("idioma", "es"), "Spanish")
    quien = (p.get("habla_desc") or d.get("quien") or "the character who speaks on screen").strip().rstrip(".")
    donde = "as shown in <Picture 2> and in <Picture 1>" if p.get("hoja_ref") else "as shown in <Picture 1>"
    marca = "using the voice timbre referenced from <Audio 1>"
    if marca not in cuerpo:
        if "(S1)" in cuerpo:
            cuerpo = cuerpo.replace("(S1)", f"(S1), {marca},", 1)
        elif "<d>" in cuerpo:
            cuerpo = cuerpo.replace("<d>", f"{marca}: <d>", 1)
    # El estilo abre la descripción (la guía pide una o dos frases antes del [Shot 1]).
    estilo = (p.get("estilo") or "Live-action, cinematic").strip().rstrip(".")
    desc = f"The target video is a {estilo[0].lower() + estilo[1:]} scene, {p.get('aspecto', '9:16')} frame, {float(p.get('duracion') or 0):.0f} seconds long.\n{cuerpo}"
    cortes = p.get("cortes") or []
    tramo = (f"one continuous scene edited in camera with {len(cortes)} internal cut(s)" if cortes
             else "one single continuous take")
    sujetos = [
        f"<Picture 1> is the first frame of [Shot 1], showing {(p.get('primer_fotograma') or 'the scene exactly as it starts').strip().rstrip('.')}.",
        f"<Subject 1> is {quien}, {donde}.",
        f"<Audio 1> is the voice-timbre reference for <Subject 1> (S1), containing a spoken {lengua} vocal layer.",
    ]
    resumen = (f"[keyframe completion + reference generation + audio reference] The target video begins from <Picture 1> and "
               f"continues as {tramo} in which <Subject 1> speaks {marca}. Every other character keeps the voice described in the text.")
    retencion = [
        "<Picture 1> ([Shot 1] first frame): fully_preserved - the composition, framing, lens, lighting, set, props and the position of everyone in the frame are kept.",
        f"<Subject 1> (appears in [Shot 1]): fully_preserved - the face, hair, skin or fur details and the clothes are kept exactly{' as in <Picture 2>' if p.get('hoja_ref') else ''}.",
        "<Audio 1>: reference - the target speaker follows <Audio 1>'s voice timbre, pitch and manner of speaking, and says only the lines written in the description.",
    ]
    return prompts.oficial_ref2va(sujetos, resumen, retencion, desc, sonido, musica)


# ═══════════════════════════════════════════════ EDICIÓN DE UN VIDEO (Ref2VA)

GUIA_EDICION = """You rewrite a VIDEO-EDITING request into the exact full-reference prompt format of MiniMax H3 (mode Ref2VA). The source video is <Video 1>; the target video is an edited version of it that keeps everything the user did not ask to change (framing, camera, motion, timing, identity, place, light) and changes only what the user asked (clothing, background, an object, the weather, a spoken line…). Output ONLY the final prompt, nothing else.

FORMAT: six sections, these exact names, this order, each name on its own line followed by a colon, one blank line between sections:
subject_definitions:
<Subject 1> is <the person/thing that appears in <Video 1>, described concretely: hair, face, age, clothing, pose>.
<Subject 2> is <the environment/background in <Video 1>> (add more subjects only if they must be tracked separately).
<Picture 1> is <the reference image: the new outfit / the new background / the object>, ONLY if a reference image is attached.
<Video 1> is the source video for the target video edit.
<Audio 1> is the synchronized audio track of <Video 1> and is reused in the target video. ONLY if the request says to keep the original audio.

summary:
[video editing] or [video editing + reference generation] (if <Picture 1> exists) or [video editing + audio reuse] (if <Audio 1> exists), combined with " + " as needed. Then one short paragraph: "The target video is an edited version of <Video 1>. ..." saying what stays and what changes.

retention_analysis:
One line per label defined above, with these fixed markers: fully_preserved / partially_preserved / attribute_transfer / weak_reference for <Subject N>, <Picture N>, <Video N>; fully_copy / partially_copy / reference / weak_reference for <Audio N>. Format: "<Subject 1> (appears in [Shot 1]): partially_preserved - the identity, face, hair and pose are retained while the clothing changes to …". "<Video 1> (source video editing): fully_preserved - the original framing, camera motion, timing and lighting are maintained while … is edited." "<Audio 1>: fully_copy - <Audio 1> is reused 1:1 as the target video's complete final audio track."

detailed_description:
One or two sentences of overall style, then "[Shot 1] The shot begins from the source <Video 1>, showing <Subject 1> …" and describe, in playback order and matching the requested duration, what is seen: the subject with the EDITED attributes stated explicitly (the new clothing in detail, the new background in detail), the original motion and camera preserved ("the camera keeps the exact framing and movement of <Video 1>"), and the sound. If a reference image exists, say what is taken from <Picture 1> ("wearing the … shown in <Picture 1>"). Speech follows the usual rules: (S1) ids, voice described once, literal lines inside <d>[Language] …</d>, mouth visibly moving for on-screen speech, lips closed when the voice stops.

overall_soundscape:
1-3 sentences of ambience and physical sounds. If the original audio is reused, say the soundscape comes from <Audio 1>.

non_diegetic_music:
N/A

RULES
- Everything in English except the literal words inside <d>…</d>.
- Describe the source video faithfully from the attached frames (people, clothing, place, motion, camera). The edit must be explicit and concrete: never "different clothes", always "a dark green wool coat with a wide collar over a white shirt".
- Keep every unrequested attribute: state what is preserved (identity, face, hair, pose, framing, camera, timing, lighting).
- NEVER write prohibitions ("no", "not", "never", "without", "do not", "avoid"): describe what IS there. The retention lines use the fixed markers, that is the only place a contrast ("… retained while … changes") belongs.
- Do not invent extra people, objects, text or cuts. One [Shot 1] unless the source clearly has cuts.
- Length: 250-600 words in detailed_description, scaled to the duration.

EXAMPLE (official, editing a source video to add speech, keeping its music):
subject_definitions:
<Subject 1> is the young man with short wavy blonde hair, wearing a bright pink suit jacket, matching pink trousers, an unbuttoned white shirt, and silver rings, holding a small black lamb in his arms in <Video 1>.
<Video 1> is the source video for the editing task.
<Audio 1> is the synchronized audio track of <Video 1>, providing the background music.

summary:
[video editing + audio reuse] The target video is an edited version of <Video 1>. <Subject 1>, wearing a bright pink suit and holding a black lamb, stands in a grassy field with other white lambs in the background. The edit animates <Subject 1>'s face to speak the user-provided dialogue while <Audio 1> continues as the background music.

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - the short wavy blonde hair, bright pink suit, unbuttoned white shirt, silver rings and the black lamb are retained.
<Video 1> (source video editing): fully_preserved - the original camera framing, warm golden hour lighting, grassy hill setting, and background white lambs are maintained while the central character is edited to speak.
<Audio 1>: partially_copy - the background music of <Audio 1> continues underneath the new spoken line.

detailed_description:
Live-action, cinematic, warm golden-hour light.
[Shot 1] The shot begins from the source <Video 1>, showing <Subject 1>, a young man with short wavy blonde hair, wearing a bright pink suit jacket, matching pink trousers, and a casually unbuttoned white shirt. He stands in a sunlit green pasture, gently holding a small black lamb in his arms, while several white lambs graze on the rolling hill behind him. The camera keeps the exact framing and slow push-in of <Video 1>. <Subject 1> (S1), a calm young male voice, medium pitch, unhurried, looks forward and speaks, his mouth opening and closing clearly in sync with each word: <d>[English] Follow the wind, live free.</d> Exactly as his voice stops, his lips meet in a relaxed smile and his jaw stops moving; he strokes the lamb's fleece and looks toward the horizon through the end of the video.

overall_soundscape:
The background music of <Audio 1> plays continuously; a light breeze moves through the grass and the lamb shifts softly in his arms.

non_diegetic_music:
N/A
"""

SECCIONES_REF = ("subject_definitions:", "summary:", "retention_analysis:", "detailed_description:",
                 "overall_soundscape:", "non_diegetic_music:")


def pedido_edicion_texto(p: dict) -> str:
    L = [f"Target duration: {float(p['duracion']):.2f} seconds (same timing as the source). Frame: {p.get('aspecto', '16:9')}.",
         f"Source video <Video 1>: {float(p.get('segundos_fuente') or p['duracion']):.1f} s; its frames are attached as a contact sheet "
         "(read left to right, top to bottom)." + (f" Notes about it: {p['fuente_desc']}" if p.get("fuente_desc") else "")]
    L.append(f"WHAT TO CHANGE (the user's request, may be in Spanish; translate the intent): {p['cambio'].strip()}")
    if p.get("imagen_ref"):
        L.append("A reference image is attached AFTER the contact sheet: it is <Picture 1> and shows what the user wants "
                 "(the outfit, the background or the object). Describe it and use it as the source of the change.")
    L.append("The original audio of <Video 1> IS reused (<Audio 1>, fully_copy or partially_copy if speech is added)."
             if p.get("audio_original") else
             "The original audio is discarded: define no <Audio N>; describe the new soundscape from the scene.")
    d = p.get("dialogo")
    lineas = lineas_de(d) if d else []
    if lineas:
        lengua = IDIOMAS.get(d.get("idioma", "es"), "Spanish")
        L.append(f"New speech in {lengua}, in this order (label = who, never spoken; text after «» is literal):")
        for l in lineas:
            L.append(f"- {l['quien'] or 'the person on screen'} ({'off-screen voice-over' if l['off'] else 'on screen, mouth moving'}): «{l['texto']}»")
    else:
        L.append("Nobody speaks in the target video.")
    if p.get("notas"):
        L.append(f"Notes: {p['notas']}")
    return "\n".join(L)


def validar_edicion(prompt: str, p: dict) -> list[str]:
    e = []
    t = prompt.strip()
    pos = [t.find(s) for s in SECCIONES_REF]
    if any(x < 0 for x in pos):
        e.append("missing section(s): " + ", ".join(s for s, x in zip(SECCIONES_REF, pos) if x < 0))
    elif pos != sorted(pos):
        e.append("the six sections must be in the official order")
    if "<Video 1>" not in t.split("summary:")[0]:
        e.append("subject_definitions must define <Video 1> as the source video")
    m = re.search(r"summary:\s*\[([^\]]+)\]", t)
    if not m or "video editing" not in m.group(1):
        e.append("summary must start with a task prefix containing 'video editing', e.g. [video editing + audio reuse]")
    if "[Shot 1]" not in t:
        e.append("detailed_description must contain [Shot 1]")
    if p.get("imagen_ref") and "<Picture 1>" not in t:
        e.append("a reference image is attached: define and use <Picture 1>")
    if not p.get("imagen_ref") and "<Picture 1>" in t:
        e.append("there is no reference image: remove <Picture 1>")
    if p.get("audio_original"):
        if "<Audio 1>" not in t or not re.search(r"<Audio 1>:\s*(fully_copy|partially_copy)", t):
            e.append("the original audio is reused: define <Audio 1> and mark it fully_copy or partially_copy in retention_analysis")
    elif "<Audio 1>" in t:
        e.append("the original audio is discarded: remove <Audio 1>")
    if not re.search(r"non_diegetic_music:\s*N/A", t):
        e.append("non_diegetic_music must be N/A")
    d = p.get("dialogo")
    lineas = lineas_de(d) if d else []
    bloques = re.findall(r"<d>\s*\[[^\]]+\]\s*(.*?)</d>", t, re.S)
    if lineas:
        dentro = _normal(" ".join(bloques))
        for l in lineas:
            if _normal(l["texto"]) not in dentro:
                e.append(f"this line is missing or altered inside <d>: {l['texto']!r}")
        if len(bloques) > len(lineas):
            e.append(f"{len(bloques)} <d> blocks for {len(lineas)} lines: one per line")
    elif bloques:
        e.append("nobody speaks: remove every <d>…</d>")
    cuerpo = t.split("detailed_description:")[-1]
    negs = NEGACIONES.findall(cuerpo)
    if len(negs) > 2:
        e.append(f"remove the negatives in detailed_description ({', '.join(sorted(set(x.lower() for x in negs)))})")
    n = len(cuerpo.split())
    if n < 150:
        e.append(f"detailed_description too short ({n} words): describe the source and the edit concretely")
    return e


def plantilla_edicion(p: dict) -> str:
    """Piso determinista para la edición: seis secciones armadas con los campos."""
    suj = ["<Subject 1> is the main person or object seen in <Video 1>, kept with the same identity, pose and motion.",
           "<Video 1> is the source video for the target video edit."]
    ret = ["<Subject 1> (appears in [Shot 1]): partially_preserved - identity, pose and motion are retained while the requested change is applied.",
           "<Video 1> (source video editing): fully_preserved - the original framing, camera motion, timing and lighting are maintained."]
    tarea = ["video editing"]
    if p.get("imagen_ref"):
        suj.insert(1, "<Picture 1> is the reference image showing the requested change.")
        ret.append("<Picture 1> (reference for the change): attribute_transfer - its look is applied to <Subject 1>.")
        tarea.append("reference generation")
    if p.get("audio_original"):
        suj.append("<Audio 1> is the synchronized audio track of <Video 1> and is reused in the target video.")
        ret.append("<Audio 1>: fully_copy - <Audio 1> is reused 1:1 as the target video's complete final audio track.")
        tarea.append("audio reuse")
    resumen = (f"[{' + '.join(tarea)}] The target video is an edited version of <Video 1>. Everything stays as in the source "
               f"except this change: {p['cambio'].strip()}")
    desc = ("Live-action, same style as the source.\n[Shot 1] The shot begins from the source <Video 1>, showing <Subject 1> with the exact "
            f"framing, camera movement and timing of <Video 1>. The requested change is applied and visible from the first frame: {p['cambio'].strip()}. "
            "Everything else, the identity, the pose, the motion, the place and the light, continues exactly as in the source through the end of the clip.")
    sonido = "The soundscape comes from <Audio 1>." if p.get("audio_original") else "Quiet ambience matching the place, with the physical sounds of what moves."
    return prompts.oficial_ref2va(suj, resumen, ret, desc, sonido, "N/A")


def reescribir_edicion(p: dict, log=print, reintentos: int = 2, clave: str | None = None) -> dict:
    """Como `reescribir`, para editar un video: manda la hoja de fotogramas del
    video fuente (`p['hoja']`) y, si hay, la imagen de referencia (`p['imagen_ref']`)."""
    contenido: list = [{"type": "text", "text": "Rewrite this video-editing request into the H3 full-reference prompt.\n\n" + pedido_edicion_texto(p)}]
    for clave_img, detalle in (("hoja", "high"), ("imagen_ref", "low")):
        ruta = p.get(clave_img)
        if ruta and Path(str(ruta)).exists():
            b = _imagen_b64(Path(str(ruta)), lado=1024 if clave_img == "hoja" else 768)
            if b:
                contenido.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}", "detail": detalle}})
    mensajes = [{"role": "system", "content": GUIA_EDICION}, {"role": "user", "content": contenido}]
    problemas: list[str] = []
    salida = ""
    for intento in range(1, reintentos + 2):
        try:
            salida, uso = _chat(mensajes, clave=clave)
        except ErrorReescritor as e:
            log(f"    !! {e}")
            break
        salida = salida.strip()
        if salida.startswith("```"):
            salida = re.sub(r"^```[a-z]*\s*|\s*```$", "", salida, flags=re.S).strip()
        i = salida.find("subject_definitions:")
        if i > 0:
            salida = salida[i:]
        problemas = validar_edicion(salida, p)
        log(f"    reescritor (edición): intento {intento} · {len(salida.split())} palabras · "
            f"{uso.get('prompt_tokens', '?')}+{uso.get('completion_tokens', '?')} tokens"
            + (f" · {len(problemas)} problema(s)" if problemas else " · OK"))
        if not problemas:
            return {"prompt": salida, "origen": f"reescritor {MODELO}", "intentos": intento, "problemas": []}
        for pr in problemas:
            log(f"      - {pr}")
        mensajes.append({"role": "assistant", "content": salida})
        mensajes.append({"role": "user", "content": "Fix these problems and output the complete corrected prompt only:\n- " + "\n- ".join(problemas)})
    graves = [x for x in problemas if not x.startswith(("detailed_description too short", "remove the negatives"))]
    if salida and not graves:
        return {"prompt": salida, "origen": f"reescritor {MODELO} (con avisos)", "intentos": reintentos + 1, "problemas": problemas}
    log("    !! el modelo no dio un prompt válido: va la plantilla determinista")
    return {"prompt": plantilla_edicion(p), "origen": "plantilla", "intentos": reintentos + 1, "problemas": problemas}
