"""Los bloques de prompt que se repiten en todos los planos, y los armadores.

Cada bloque está acá por una razón que costó plata aprender. Se documenta al
lado de cada uno para que nadie lo saque "porque parece redundante".
"""
from __future__ import annotations

# ---------------------------------------------------------------- tamaños
# Cómo se describe cada tamaño de plano. La escala va en la imagen Y en el
# prompt de video: si va en uno solo, H3 la corrige por su cuenta y los
# personajes salen gigantes dentro del espacio.
TAMANIO: dict[str, tuple[str, str]] = {
    "PGE": ("EXTREME WIDE SHOT",
            "The figures are TINY, each about ONE TENTH of the image height, "
            "dwarfed by the landscape. The vastness is the point."),
    "PG":  ("WIDE SHOT",
            "The figures are SMALL, each about ONE SIXTH of the image height. "
            "They read as normal-sized people inside a large space, never as "
            "giants. Their feet are on the ground."),
    "PA":  ("FULL SHOT",
            "The figure is seen head to toe and fills about HALF the image "
            "height, with clear space above the head and below the feet."),
    # "waist up" a secas no alcanzaba: el generador de imágenes dibujaba el
    # personaje entero siete veces de siete. Hay que decir que el borde CORTA.
    "PM":  ("MEDIUM SHOT",
            "The bottom edge of the frame CROPS the character at the waist: "
            "the legs, the knees and the feet are NOT in the picture at all. "
            "The head and shoulders take up the upper half of the frame, with "
            "a little headroom. This is not a full-body shot."),
    "PP":  ("CLOSE UP",
            "The face fills most of the frame, cropped just above the "
            "hairline and just below the chin."),
    "PD":  ("INSERT / EXTREME CLOSE UP of an object",
            "The object fills the frame. No full figures visible, at most a "
            "pair of hands."),
}
NOMBRE_TAMANIO = {"PGE": "plano general extremo", "PG": "plano general",
                  "PA": "plano entero", "PM": "plano medio", "PP": "primer plano",
                  "PD": "plano detalle", "SHORT": "plano de short"}

# ---------------------------------------------------------------- bloques
# Va en TODOS los planos con voz posible, hablen o no. Sin él, H3 mete murmullos
# y chusmerío de fondo en inglés. No se pide silencio: se pide que si alucina,
# alucine en castellano.
IDIOMA = ("SPOKEN LANGUAGE: SPANISH. Every voice, word, murmur, shout or "
          "crowd chatter heard in this shot is in Spanish. NEVER English. If "
          "any voice appears at all, it is Spanish.")

# `"idioma"` del proyecto. El castellano es el default y sigue siendo el bloque
# de arriba, textual. El inglés entró con la réplica de «danza peligrosa»
# (14/9/2026): el original de Kling se filmó en inglés, así que en inglés la
# boca que anima H3 y la voz que se monta encima dicen lo mismo.
IDIOMAS = {
    "es": ("Spanish", IDIOMA),
    "en": ("English", "SPOKEN LANGUAGE: ENGLISH. Every voice, word, murmur, shout or "
                      "crowd chatter heard in this shot is in English. If any voice "
                      "appears at all, it is English."),
}


def _idioma(idioma: str) -> tuple[str, str]:
    if idioma not in IDIOMAS:
        raise ValueError(f"idioma {idioma!r}: hay {', '.join(IDIOMAS)}")
    return IDIOMAS[idioma]

# La corrección más importante de la primera corrida larga: H3 arranca clavado
# en el dibujo y después inventa (cactus en el desierto, fuego, caras ajenas).
NO_INVENTES = (
    "DO NOT ADD ANYTHING that is not already in the first frame. No new "
    "characters, no new faces, no extra people, no new landscape features, no "
    "cacti, no fire, no flames, no magical glows, no weather. The location, "
    "the terrain, the architecture, the time of day, the light and the NUMBER "
    "OF CHARACTERS stay exactly as in the first frame from beginning to end. "
    "Nothing enters frame that was not there. Animate what is in the picture; "
    "invent nothing.")

# H3 dibuja el humo como cúmulos redondos de caricatura. Solo se agrega cuando
# el plano lo necesita: cargar todo con restricciones que no aplican diluye
# las que sí.
HUMO = (
    "Any smoke, dust or vapour is soft and wispy, painted with the same brush "
    "and texture as the rest of the image, drifting and dissipating. NEVER "
    "rounded cartoon cumulus puffs, never white bubble clouds.")
PALABRAS_HUMO = ("smoke", "dust", "silt", "vapour", "vapor", "cloud", "mist", "fog")

# Para el short: ninguna voz sale de H3. La voz en off va encima, de ElevenLabs.
NO_SPEECH = ("NO SPEECH. No voices, no words, no dialogue, no singing, no "
             "crowd chatter.")

FRAME_LIMPIO = ("This is a single film frame, not a poster: no text, no borders, "
                "no panel divisions, no title, no watermark.")

# Continuidad cinética, para los planos que arrancan del ÚLTIMO FOTOGRAMA del
# anterior en vez de un dibujo. La línea que hace el trabajo es la segunda:
# declarar que el fotograma recibido es un INSTANTE INTERMEDIO y no el comienzo
# de una toma nueva. `first_frame` fija el punto visual pero no lleva
# información de velocidad ni de fase del movimiento, así que sin decirlo el
# modelo arranca de cero y se ve el "restart".
CONTINUIDAD = """Seamless continuation of the exact same uninterrupted cinematic take.
THE SUPPLIED FIRST FRAME IS A MID-ACTION FRAME, NOT THE BEGINNING OF A NEW SHOT.
Preserve the exact ongoing momentum from frame one.
CAMERA: continue the existing camera state at the same direction, speed, height and trajectory. No pause, no restart, no sudden acceleration, no camera reset.
SUBJECTS: continue the current body movement without resetting posture or position. Preserve identity, proportions, orientation and relative placement.
DYNAMIC ELEMENTS: continue smoke, dust, wind, fabric, fire, water, sparks and debris with the same direction, speed, density and physical behaviour.
VISUAL CONTINUITY: identical lighting direction, exposure, environment, lens character, framing and overall style.
Do not restart the action. Do not re-pose the subject. Treat this as the next uninterrupted seconds of the same take."""

# El encuadre vertical se cuela sobre todo en los planos detalle, donde no hay
# figura que sugiera orientación. Igual se pide por parámetro de la API: esto
# es el refuerzo por texto.
FORMATO = {
    "16:9": "FORMAT: a WIDE 16:9 landscape frame, clearly wider than tall. "
            "Never square, never vertical.",
    "9:16": "FORMAT: a TALL 9:16 vertical frame, clearly taller than wide. "
            "Never square, never landscape.",
}


def cuadros(n: int) -> str:
    return ", ".join(f"<Picture {i + 1}>" for i in range(n))


# ------------------------------------------------------------ largo (16:9)

def storyboard_largo(estilo: str, tam: str, refs: int, personajes_desc: list[str],
                     que_se_ve: str, aspecto: str = "16:9",
                     intencion: str = "") -> str:
    """El prompt del PRIMER FOTOGRAMA de un plano con personajes y locación."""
    etiqueta, escala = TAMANIO[tam]
    p = [estilo]
    if refs:
        resto = ("the rest are character model sheets" if refs > 1
                 else "there are no characters in this shot")
        p.append(f"Use {cuadros(refs)} as reference: <Picture 1> is the location, {resto}.")
    p.append(f"{etiqueta}. {que_se_ve}")
    if personajes_desc:
        p.append("CHARACTERS, drawn exactly as in their model sheets: "
                 + "; ".join(personajes_desc) + ".")
    p.append(f"FRAMING AND SCALE: {escala}")
    if intencion:
        p.append(f"NARRATIVE INTENT OF THIS FRAME: {intencion}")
    p.append(FORMATO[aspecto])
    p.append(FRAME_LIMPIO)
    return "\n".join(p)


# La versión POSITIVA del «no inventes», para proyectos con `negativos: false`.
# Medido el 10/9/2026 en LLUVIA EN LA VENTANA (12 clips, cuarto vacío, sin
# gente): con el bloque negativo, 7 de 12 clips trajeron exactamente lo que
# prohíbe —gente en la ventana, cactus, fuego, nubes de caricatura—. En una
# escena donde nada de eso es natural, nombrarlo lo invoca (misma lección que
# «NO subtitles», regla 5 de la corrida limpia). Acá se describe lo que SÍ
# pasa, sin nombrar nunca lo que no tiene que aparecer.
QUIETO = (
    "Everything in the frame stays exactly as it is in the first frame for the "
    "whole shot: the same place, the same objects in the same positions, the "
    "same time of night, the same light. The frame holds only what the first "
    "frame shows, from beginning to end. Animate only the gentle motion "
    "described above; the rest of the picture stays still.")


def video_largo(tam: str, personajes_desc: list[str], movimiento: str, audio: str,
                dialogo: str | None, medio: str = "2D animated film",
                negativos: bool = True, idioma: str = "es") -> str:
    """`negativos=False` reemplaza los bloques negativos fijos (NO_INVENTES,
    HUMO, IDIOMA) por QUIETO. Para escenas quietas y sin gente, donde los
    negativos inducen justo lo que prohíben."""
    lengua, bloque_idioma = _idioma(idioma)
    etiqueta, escala = TAMANIO[tam]
    p = [f"{etiqueta}, {medio}.",
         f"MOTION: {movimiento}",
         f"FRAMING: hold the shot size of the first frame. {escala}"]
    if personajes_desc:
        p.append("CHARACTERS, unchanged from the first frame: "
                 + "; ".join(personajes_desc) + ".")
    p.append(f"AUDIO: {audio}")
    if dialogo:
        p.append(f'SPOKEN LINE, in {lengua}, exactly this: "{dialogo}"')
    if not negativos:
        # La escala de TAMANIO habla de «figures», «people» y «a pair of
        # hands»: en una escena vacía eso también invoca (P12 de LLUVIA EN LA
        # VENTANA terminó con manos sosteniendo los auriculares). Sin gente,
        # la composición del primer fotograma alcanza para fijar el tamaño.
        p[2] = "FRAMING: hold the exact shot size and composition of the first frame."
        p.append(QUIETO)
        return "\n".join(p)
    p.append(NO_INVENTES)
    if any(x in (movimiento + " " + audio).lower() for x in PALABRAS_HUMO):
        p.append(HUMO)
    p.append(bloque_idioma)
    return "\n".join(p)


# ------------------------------------------------------- formato OFICIAL
# Desde el 14/9/2026. Las guías de MiniMax (models/MiniMax-H3/docs/
# VIDEO_PROMPT_WRITING_GUIDE_base_en.md y _ref_en.md) y los prompts que devuelve
# su reescritor oficial H3-Context-IR (docs-extra/scripts/). El README lo llama
# "critical to the quality". Los armadores de más arriba son el formato viejo
# en texto libre, que queda sólo para los videos anteriores.
#
# Reglas que estos armadores dan por hechas y que el que escribe el texto tiene
# que cumplir (resumen de las guías):
#   - todo en inglés salvo lo que va dentro de <d>…</d>
#   - [Shot 1] sin hora; los siguientes "[Shot N] At MM:SS.mmm, the camera cuts to…"
#   - cámara = tipo + amplitud + velocidad, en prosa ("pushes in with small
#     amplitude at slow speed")
#   - hablantes con ID estable (S1) descriptos la primera vez (edad, timbre,
#     ritmo, acento); diálogo <d>[English] texto literal</d>
#   - voz en off: "says in an off-screen voiceover: <d>…</d> while her lips
#     remain completely closed"
#   - overall_soundscape: 1-4 frases, sin diálogo; non_diegetic_music: N/A si no hay
#   - SIN listas de negativos: lo que se nombra, se invoca (medido el 10/9)

INSTRUCCION_I2VA = ("For the target video, at 0.00 seconds into the target video, "
                    "<Picture 1> (from [Shot 1]) is fully referenced.")


def oficial_i2va(descripcion: str, sonido: str, musica: str = "N/A") -> str:
    """Primer fotograma → video (FL2VA con una imagen). `descripcion` empieza con
    "[Shot 1] …"."""
    return (f"{INSTRUCCION_I2VA}\n\n"
            f"integrated_multimodal_description: {descripcion.strip()}\n\n"
            f"overall_soundscape: {sonido.strip()}\n\n"
            f"non_diegetic_music: {musica.strip()}")


def oficial_ref2va(sujetos: list[str], resumen: str, retencion: list[str],
                   descripcion: str, sonido: str, musica: str = "N/A") -> str:
    """Modo referencia completa: las seis secciones en su orden. `resumen` lleva
    el prefijo de tarea entre corchetes; `descripcion` abre con una o dos frases
    de estilo y sigue con "[Shot 1] …" (350-500 palabras según la guía)."""
    return ("subject_definitions:\n" + "\n".join(s.strip() for s in sujetos) + "\n\n"
            f"summary:\n{resumen.strip()}\n\n"
            "retention_analysis:\n" + "\n".join(r.strip() for r in retencion) + "\n\n"
            f"detailed_description:\n{descripcion.strip()}\n\n"
            f"overall_soundscape:\n{sonido.strip()}\n\n"
            f"non_diegetic_music:\n{musica.strip()}")


# ------------------------------------------------------------ short (9:16)

def storyboard_short(estilo: str, que_se_ve: str, sujeto: str | None,
                     intencion: str = "", aspecto: str = "9:16") -> str:
    p = [estilo, que_se_ve]
    if sujeto:
        # El sujeto se describe igual en todos los planos: es lo único que
        # sostiene que sea la misma persona cuando no hay hoja de modelo.
        p.append(f"THE SUBJECT, identical in every shot: {sujeto}.")
    if intencion:
        p.append(f"NARRATIVE INTENT OF THIS FRAME: {intencion}")
    p.append(FORMATO[aspecto])
    p.append(FRAME_LIMPIO)
    return "\n".join(p)


def video_short(cabecera: str, movimiento: str, audio: str, dialogo: str | None,
                cierre: str, solo_sonidos: str = "", idioma: str = "es") -> str:
    lengua, bloque_idioma = _idioma(idioma)
    p = [cabecera, f"MOTION: {movimiento}", f"AUDIO: {audio}"]
    if dialogo:
        p.append(f'SPOKEN LINE, in {lengua}, exactly this: "{dialogo}"')
        p.append(bloque_idioma)
    else:
        p.append(NO_SPEECH + (f" The only sounds are {solo_sonidos}." if solo_sonidos else ""))
    p.append(cierre)
    return "\n".join(p)
