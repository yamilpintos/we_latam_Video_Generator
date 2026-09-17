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
2. ONE shot: a single [Shot 1] with no timestamp. Never add [Shot 2] unless the request explicitly asks for a cut.
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
    if re.search(r"\[Shot [2-9]\]", t) and not p.get("multi_shot"):
        e.append("only one shot is allowed: remove [Shot 2] and later")
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
    img = raiz / "assets" / f"sb_{p.get('id', '')}.png"
    return {"modo": "i2va", "duracion": round(float(segundos), 3), "aspecto": aspecto,
            "estilo": p.get("cabecera") or d.get("estilo_video") or d.get("estilo_imagen") or "",
            "medio": d.get("medio", "") if formato != "short" else "",
            "tamano": etiqueta, "primer_fotograma": p.get("ve", ""), "personajes": personajes,
            "accion": p.get("mueve", ""), "camara": p.get("camara", ""), "audio": p.get("audio") or d.get("solo_sonidos", ""),
            "dialogo": dialogo, "quieto": not d.get("negativos", True), "musica_aparte": True,
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
        p["prompt_h3"] = r["prompt"]
        p["prompt_h3_de"] = h
        p["prompt_h3_origen"] = r["origen"]
        hechos += 1
        ruta_json.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return hechos
