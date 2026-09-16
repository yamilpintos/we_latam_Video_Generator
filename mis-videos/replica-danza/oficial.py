# -*- coding: utf-8 -*-
"""Los prompts de la réplica en el FORMATO OFICIAL de MiniMax H3 (14/9/2026).

Fuentes: models/MiniMax-H3/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md (I2VA),
..._ref_en.md (referencia completa), los prompts de H3-Context-IR en
docs-extra/scripts/ y el resumen docs-extra/PLAN-H3-AL-MAXIMO.md.

Qué se hace distinto al formato viejo, y por qué:
- instrucción de primer fotograma + los tres campos (I2VA) o las seis secciones
  (Ref2VA), con los nombres y el orden exactos
- el primer fotograma se describe ENTERO antes de la acción, y la acción va en el
  tiempo ("Early in the clip…", "As the clip progresses…"), como Context-IR
- cámara con tipo + amplitud + velocidad
- hablante con ID (S1), voz descripta, <d>[English] …</d>, labios cerrados antes y
  "Exactly as his voice stops, his lips close…" después (mitigación del issue
  #16155 para el balbuceo con voz de referencia)
- non_diegetic_music: N/A — la música es la del original, no la compone H3
- sin listas de negativos
"""
import re

TAM = {"PGE": "an extreme wide shot", "PG": "a wide shot", "PA": "a full shot",
       "PM": "a medium shot", "PP": "a close-up", "PD": "an insert close-up"}

ESTILO = ("Live-action, cinematic, a photographic vertical 9:16 frame with shallow depth of field, "
          "natural skin texture and subtle film grain")

LUZ = {
    "cabina_ventana": ("Bright daylight glows through the white lace curtains behind, while warm "
                       "brass lamps light the glossy mahogany compartment."),
    "cabina_puerta": ("Warm golden light from the crystal chandeliers falls over the gold brocade "
                      "curtains, the red silk roses and the dark mahogany."),
    "pasillo": ("Bright overcast daylight comes through the corridor windows and gleams along the "
                "polished honey-coloured wood."),
    "vagon_blanco": "Flat, bright daylight fills the cream-white carriage.",
    "campo": ("Soft late-afternoon golden light falls from a pale, hazy sky, warm on skin and "
              "grass."),
}

TREN = "The steady rumble and rhythmic clack of the train on the rails continue underneath."

# Cámara de cada encuadre, con el vocabulario de la guía (sección 4.3). Lo que
# no está acá es un plano quieto con peso de cámara en mano.
CAMARA = {
    "E01": "The camera trucks right with small amplitude at slow speed.",
    "E02": "The camera tracks backward low to the ground at the pace of her steps.",
    "E03": "The camera tracks backward with her, handheld, keeping the frame on her hands.",
    "E04": "The camera pulls out at slow speed, tracking backward ahead of her.",
    "E05": "The camera holds a low-angle static shot with a slight handheld sway.",
    "E06": "The camera pans right with small amplitude at slow speed, following the train.",
    "E10": "The camera holds a low-angle static shot.",
    "E12": "The camera holds a static shot.",
    "E14b": "The camera pushes in with small amplitude at slow speed.",
    "E15": "The camera holds a static shot and shakes slightly as the doors burst open.",
    "E16": "The camera pulls out at slow speed, tracking backward ahead of him.",
    "E17": "The camera holds a static shot with a slight handheld sway.",
    "E18": "The camera holds a static shot and shakes slightly as she spins around.",
    "E25": "The camera holds a static wide shot.",
    "E29": "The camera shakes slightly, handheld, as passengers rush across the lens.",
    "E30": "The camera holds a low-angle shot and shakes strongly with each gunshot.",
    "E31": "The camera shakes slightly, handheld, as he bursts in.",
    "E34": "The camera shakes slightly, handheld.",
    "E35": "The camera tracks forward with small amplitude behind the gunmen.",
    "E41": "The camera holds a static wide shot.",
    "E42": "The camera shakes slightly as he turns with her.",
    "E58": "The camera shakes slightly, handheld, over the passenger's shoulder.",
    "E59": "The camera shakes strongly as Luka shoves the passenger.",
    "E60": "The camera shakes slightly, handheld.",
    "E68": "The camera pans left with small amplitude at fast speed as he bolts for the door.",
    "E69": "The camera shakes strongly as the gunmen rush toward the lens.",
    "E72": "The camera holds a static macro shot.",
    "E79": "The camera shakes strongly as the door is kicked in.",
    "E80": "The camera holds a point-of-view shot and shakes slightly as they level their guns at it.",
}
CAMARA_DEFAULT = "The camera holds a static shot with a slight handheld sway."

# Lo que pasa en los clips que hablan: antes (labios cerrados), cómo lo dice, y
# después (labios cerrados). La LÍNEA sale de tomas.LINEAS por encuadre.
ENTREGA = {
    "E22": ("she presses back against the window frame, eyes wide, breathing hard",
            "in a frightened shout", "a black-gloved hand clamps over her mouth"),
    "E23": ("he leans in until his face is inches from hers, eyes locked on hers",
            "in a long, soft hush", "he keeps staring at her, completely still"),
    "E30": ("he fires a long burst from the AK-47 into the ceiling, muzzle flash lighting his face",
            "in a furious roar at the passengers", "he swings the rifle down, glaring"),
    "E36": ("he pushes himself off the wood-panelled wall and grips his rifle",
            "in a loud, rough shout up the corridor", "he stays in place, breathing hard, glaring"),
    "E43": ("she looks down at him, confused, as his hand draws a black knife",
            "in a breathless, bewildered whisper", "she freezes, staring at the blade"),
    "E44": ("he raises the black knife close to his face, eyes on her",
            "in a soft, slow hush, twice", "he holds the knife still between them"),
    "E46": ("they stare at each other in profile, the knife upright between them",
            "in a single low, pleased murmur", "a slow smile stays on his face and his eyes flick toward the door"),
    "E47": ("he studies her face, the knife held near her throat",
            "low and slow, almost tender, with a dangerous half smile", "he keeps his eyes on hers"),
    "E49": ("his cold eyes stay on her, the knife steady in his gloved hand",
            "slowly and quietly, with a pause after the first word", "he tilts his head, waiting"),
    "E52": ("tears run down her cheeks as the flat of the blade presses against her neck",
            "in a pleading, broken voice through tears", "she keeps crying silently"),
    "E53": ("he watches her closely, the knife steady",
            "in a quick, curious question, tilting his head", "he waits for her answer"),
    "E54": ("she swallows, trembling, the blade against her neck",
            "in a single shaking word", "she keeps her eyes on him, crying"),
    "E55": ("a wolfish smile spreads across his face",
            "with dark amusement", "the smile stays on his face"),
    "E61": ("he paces in fury, the rifle across his chest",
            "in an enraged shout, jabbing a finger", "he glares, jaw clenched"),
    "E62": ("he looks at someone off camera, scared and agitated",
            "fast and nervous, gesturing with his free hand", "he keeps looking at the boss, afraid"),
    "E64": ("his eyes go wide as he gestures",
            "very fast, panicking, counting on his fingers", "he stares, breathing hard"),
    "E65": ("he yanks Wady in by the lapel of the olive coat and pulls him close",
            "in a low growl that rises into a shout", "he shoves him away"),
    "E68": ("he grips his pistol and turns toward the doorway",
            "in a loud barked order", "he bolts through the door"),
    "E73": ("he leans close to her bare shoulder, eyes on her face",
            "slowly, leaving a pause between the words", "he waits, eyes on hers"),
    "E74": ("his gloved hand grips her shoulder, their faces very close",
            "in a menacing whisper", "his eyes slide toward the door while she trembles"),
    "E75": ("she holds her breath for about two seconds, trembling",
            "in a quick, broken whisper, nodding as she gives in", "she closes her eyes"),
    "E81": ("her face snaps toward the door and her eyes go wide",
            "in a loud, startled gasp", "her mouth stays open in shock"),
}

PRONOMBRE = {"hannah": ("she", "her"), "jack": ("he", "his"), "luka": ("he", "his"),
             "wady": ("he", "his"), "matones": ("he", "his")}
NOMBRE = {"hannah": "Hannah", "jack": "Jack", "luka": "Luka", "wady": "Wady"}


def _frases(texto):
    return [f.strip() for f in re.split(r"(?<=[.!?])\s+", texto.strip()) if f.strip()]


def _accion(mueve):
    """La acción del formato viejo, llevada al tiempo como la escribe Context-IR."""
    fr = _frases(mueve)
    if not fr:
        return ""
    txt = "Early in the clip, " + fr[0][0].lower() + fr[0][1:]
    if len(fr) > 1:
        txt += " As the clip progresses, " + " ".join(fr[1:])[0].lower() + " ".join(fr[1:])[1:]
    return txt


def _sonido(audio, loc, interior=True):
    """Las capas [SFX]/[Ambient]/[Foley] del formato viejo, en 1-4 frases. El
    habla no va acá (la guía la manda a la descripción)."""
    partes = re.split(r"\[(?:SFX|Ambient|Foley|Speech)\]", audio)
    etiquetas = re.findall(r"\[(SFX|Ambient|Foley|Speech)\]", audio)
    frases = []
    for et, txt in zip(etiquetas, partes[1:]):
        txt = txt.strip().rstrip(".")
        if et == "Speech" or not txt:
            continue
        frases.append(txt[0].upper() + txt[1:] + ".")
    if loc not in (None, "campo") and interior:
        frases.append(TREN)
    return " ".join(frases[:4]) or "Quiet room tone continues throughout."


def _cierre_labios(pron):
    s, p = pron
    return (f"Exactly as {p} voice stops, {p} lips close and {p} jaw stops moving; "
            f"{s} does not speak again for the rest of the clip.")


def encuadre(ve, tipo):
    """«WIDE SHOT of the whole compartment…» → «a wide shot of the whole
    compartment…». Los `ve` vienen de los prompts de imagen, con el tamaño en
    mayúsculas; esa etiqueta es más precisa que la genérica («close two-shot in
    profile»), así que manda ella y no se repite."""
    m = re.match(r"^((?:[A-Z][A-Z\-]+[\s,:]+)+)", ve)
    if not m:
        return f"{TAM[tipo]}: {ve}"
    crudo = m.group(1).rstrip()
    sep = ": " if crudo.endswith(":") else ", " if crudo.endswith(",") else " "
    etiqueta = crudo.strip(" ,:").lower()
    resto = ve[m.end():].lstrip(" ,:")
    art = "an" if etiqueta[0] in "aeiou" else "a"
    return f"{art} {etiqueta}{sep}{resto}"


def solo_lo_visible(A, ve, tipo):
    """En un primer plano o un plano medio, la ropa que queda fuera de cuadro no
    se nombra. Muestra A (14/9): los dos castings de Hannah —primer plano con el
    cuchillo en el cuello— describían short, medias, polainas y zapatillas de
    ballet, y H3 CORTÓ a mitad de clip a un plano entero para mostrarlos, en las
    dos semillas. Es la misma familia que «los negativos inducen»: lo que se
    nombra, H3 lo pone en pantalla aunque tenga que inventar un corte."""
    # Los insertos (PD) no: el de las zapatillas NECESITA las polainas.
    if tipo not in ("PP", "PM"):
        return ve
    arriba = f"{A.HANNAH_CARA}, wearing an oversized worn brown-and-cream plaid flannel shirt"
    if tipo == "PM":
        arriba += (" hanging open over a pale pink camisole leotard, the waistband of frayed "
                   "denim shorts at the bottom edge")
    else:
        arriba += " hanging open over a pale pink camisole leotard"
    for completo in (A.HANNAH, A.HANNAH_CAMPO):
        ve = ve.replace(completo, arriba)
    ve = ve.replace(A.JACK_CAMISA, f"{A.JACK_CARA}, in a crisp white dress shirt with the sleeves "
                                   "rolled to the forearm, a black leather shoulder-holster harness "
                                   "and black fingerless leather driving gloves")
    return ve


def descripcion_shot(A, k, tipo, loc, pers, habla=None, voz_ref=False):
    """[Shot 1] … para I2VA, o el cuerpo de detailed_description para Ref2VA."""
    ve, mueve, audio = A.E[k]
    ve = solo_lo_visible(A, ve, tipo)
    ancla = "<Picture 1>"
    t = [f"[Shot 1] {ESTILO}. The shot begins exactly on {ancla}, {encuadre(ve, tipo)}"]
    if loc in LUZ:
        t.append(LUZ[loc])
    if loc == "pasillo" and tipo in ("PG", "PA", "PM"):
        t.append("The whole frame is tilted in a Dutch angle of about twenty degrees, the corridor "
                 "verticals leaning diagonally.")
    if habla:
        quien, linea = habla
        s, p = PRONOMBRE[quien]
        antes, entrega, despues = ENTREGA[k]
        sujeto = "<Subject 1> (S1)" if voz_ref else f"{NOMBRE[quien]} (S1)"
        timbre = (f", using the voice timbre referenced from <Audio 1>," if voz_ref
                  else f", {A.VOCES[quien]},")
        t.append(f"For about the first second of the clip {p} lips stay completely closed while "
                 f"{antes}.")
        if len(linea.split()) <= 2:
            # Corrida del 14/9: con «Shh.» y «Ah!», H3 llenó los segundos
            # sobrantes leyendo en voz alta el texto que seguía a </d> («Exactly
            # as his…»). En las líneas de una o dos palabras la línea va ÚLTIMA:
            # lo que pasa después se dice antes, y después de </d> no hay texto.
            t.append(CAMARA.get(k, CAMARA_DEFAULT))
            t.append(f"Throughout the clip the framing, the light, the set and the people stay "
                     f"exactly as established by {ancla}.")
            quieto = ("stays silent" if "mouth" in despues
                      else f"stays silent with {p} lips closed")
            t.append(f"Then {sujeto}{timbre} makes one short sound {entrega}, and for the rest of "
                     f"the clip {s} {quieto} while {despues}. The sound is: "
                     f"<d>[English] {linea}</d>")
            return " ".join(x.strip() for x in t if x)
        t.append(f"Then {sujeto}{timbre} says {entrega}: <d>[English] {linea}</d> "
                 + _cierre_labios(PRONOMBRE[quien]) + f" Afterwards {despues}.")
    else:
        t.append(_accion(mueve))
        # 16/9: en T33 Wady movía la boca como hablando y no había voz (el audio
        # del clip no se usa). Dicho en positivo, como la guía: labios cerrados.
        if pers:
            t.append("Nobody speaks in this shot: every mouth stays closed the whole time.")
    t.append(CAMARA.get(k, CAMARA_DEFAULT))
    t.append(f"Throughout the clip the framing, the light, the set and the people stay exactly as "
             f"established by {ancla}.")
    return " ".join(x.strip() for x in t if x)


def prompt_i2va(A, k, tipo, loc, pers, habla=None):
    from h3pipeline import prompts
    _ve, _m, audio = A.E[k]
    return prompts.oficial_i2va(descripcion_shot(A, k, tipo, loc, pers, habla),
                                _sonido(audio, loc))


def prompt_ref2va_mudo(A, k, tipo, loc, pers, sujetos_con_hoja):
    """Toma SIN diálogo pero con actores: primer fotograma + la hoja de cara de
    cada personaje presente (<Picture 2>, <Picture 3>…), sin audio de referencia.

    Pedido del usuario (15/9, noche): en las tomas donde el actor está pero la
    cara no se ve en el primer cuadro (de espaldas, perfil, entra después), H3
    inventaba una cara. Con la hoja como referencia y `fully_preserved`, tiene
    de dónde sacarla. En PP/PD sólo el primer personaje es sujeto (REGLAS 57).
    `sujetos_con_hoja` = [(nombre_personaje, índice_de_picture), …] en orden."""
    from h3pipeline import prompts
    ve, _m, audio = A.E[k]
    ve = solo_lo_visible(A, ve, tipo)
    sujetos = [f"<Picture 1> is the first frame of [Shot 1], showing {encuadre(ve, tipo)}"]
    retencion = ["<Picture 1> ([Shot 1] first frame): fully_preserved - the composition, framing, "
                 "lens, lighting, set and the positions of everyone in the frame are kept."]
    for i, (n, pic) in enumerate(sujetos_con_hoja, start=1):
        sujetos.append(f"<Subject {i}> is {solo_lo_visible(A, A.PERSONAJES[n]['descripcion'], tipo)}, "
                       f"as shown in <Picture {pic}>; the same person as in <Picture 1>.")
        retencion.append(f"<Subject {i}> (appears in [Shot 1]): fully_preserved - face, hair, skin "
                         f"details and clothes are kept exactly as in <Picture {pic}>, including "
                         f"whenever the face turns towards the camera.")
    tam = TAM[tipo].split(" ", 1)[1]        # «an insert close-up» → «insert close-up»
    resumen = (f"[keyframe completion + reference generation] The target video begins from "
               f"<Picture 1> and continues as one {tam}, a single continuous take with no cut, in "
               f"which the people keep the identities defined above.")
    cuerpo = ("The target video is a live-action, photographic thriller scene with shallow depth "
              "of field and natural skin texture.\n"
              + descripcion_shot(A, k, tipo, loc, pers).replace(f"[Shot 1] {ESTILO}. ", "[Shot 1] "))
    return prompts.oficial_ref2va(sujetos, resumen, retencion, cuerpo, _sonido(audio, loc))


def prompt_ref2va(A, k, tipo, loc, pers, quien, linea, hoja_de):
    """Primer fotograma (<Picture 1>) + hoja del que habla (<Picture 2>) + voz
    (<Audio 1>). Las otras personas visibles quedan definidas desde <Picture 1>."""
    from h3pipeline import prompts
    ve, _m, audio = A.E[k]
    ve = solo_lo_visible(A, ve, tipo)
    habla_n = next(n for n in pers if n.startswith(quien))
    # En un primer plano, los demás no se definen como sujetos. Muestra B (14/9):
    # en tres de los cuatro primeros planos de Jack —Hannah apenas un borde de
    # pelo desenfocado— H3 CORTÓ a un plano de Hannah, porque <Subject 2> con su
    # descripción completa la pedía en pantalla. Con I2VA y el mismo encuadre
    # (muestra A) no cortaba. Siguen nombrados en la descripción, como en el
    # dibujo; sólo dejan de ser sujetos a preservar.
    otros = [] if tipo in ("PP", "PD") else [n for n in pers if n != habla_n]
    s, p = PRONOMBRE[quien]
    sujetos = [
        f"<Picture 1> is the first frame of [Shot 1], showing {encuadre(ve, tipo)}",
        f"<Subject 1> is {solo_lo_visible(A, A.PERSONAJES[habla_n]['descripcion'], tipo)}, as shown in <Picture 2> and in "
        f"<Picture 1>.",
    ]
    for i, n in enumerate(otros, start=2):
        sujetos.append(f"<Subject {i}> is {solo_lo_visible(A, A.PERSONAJES[n]['descripcion'], tipo)}, as visible in <Picture 1>.")
    sujetos.append(f"<Audio 1> is the voice-timbre reference for <Subject 1> (S1), containing a "
                   f"spoken English vocal layer.")
    resumen = (f"[keyframe completion + reference generation + audio reference] The target video "
               f"begins from <Picture 1> and continues as one {TAM[tipo][2:] if TAM[tipo].startswith('a ') else TAM[tipo]} "
               f"in which <Subject 1> says one line of dialogue using the voice timbre referenced "
               f"from <Audio 1>. The whole clip is a single continuous take on <Subject 1>.")
    retencion = [
        "<Picture 1> ([Shot 1] first frame): fully_preserved - the composition, framing, lens, "
        "lighting, set and the positions of everyone in the frame are kept.",
        f"<Subject 1> (appears in [Shot 1]): fully_preserved - {p} face, hair, skin details and "
        f"clothes are kept exactly.",
    ]
    for i, _n in enumerate(otros, start=2):
        retencion.append(f"<Subject {i}> (appears in [Shot 1]): fully_preserved - face, hair and "
                         f"clothes are kept.")
    retencion.append("<Audio 1>: reference - the target speaker follows <Audio 1>'s voice timbre "
                     "without copying its words or its signal.")
    cuerpo = ("The target video is a live-action, photographic thriller scene with shallow depth "
              "of field and natural skin texture.\n"
              + descripcion_shot(A, k, tipo, loc, pers, habla=(quien, linea), voz_ref=True)
              .replace(f"[Shot 1] {ESTILO}. ", "[Shot 1] "))
    return prompts.oficial_ref2va(sujetos, resumen, retencion, cuerpo, _sonido(audio, loc))


# ───────────────────────────── voz en off y casting ──────────────────────────

def prompt_voz_off(A, k, tipo, loc, pers, frase, voz_ref=True):
    """Un inserto (botas, puntas, pies) con la narración de Hannah en off. La guía:
    'says in an off-screen voiceover: <d>…</d> while her lips remain completely
    closed' — acá no hay labios en cuadro, así que se dice que ella no está."""
    from h3pipeline import prompts
    ve, mueve, audio = A.E[k]
    voz = ("<Subject 1> (S1), using the voice timbre referenced from <Audio 1>,"
           if voz_ref else f"Hannah (S1), {A.VOCES['hannah']},")
    cuerpo = (f"[Shot 1] The shot begins exactly on <Picture 1>, {encuadre(ve, tipo)} "
              f"{LUZ.get(loc, '')} {_accion(mueve)} {CAMARA.get(k, CAMARA_DEFAULT)} "
              f"Over the image, {voz} says in an off-screen voiceover, calm and wistful: "
              f"<d>[English] {frase}</d> The frame stays on this detail for the whole clip.")
    if not voz_ref:
        return prompts.oficial_i2va(f"[Shot 1] {ESTILO}. " + cuerpo[len('[Shot 1] '):],
                                    _sonido(audio, loc))
    sujetos = [f"<Picture 1> is the first frame of [Shot 1], showing {encuadre(ve, tipo)}",
               f"<Subject 1> is Hannah, the young woman narrating off-screen, as shown in <Picture 2>.",
               "<Audio 1> is the voice-timbre reference for <Subject 1> (S1), containing a spoken "
               "English vocal layer."]
    resumen = ("[keyframe completion + reference generation + audio reference] The target video "
               "begins from <Picture 1> while <Subject 1> narrates one sentence off-screen using the "
               "voice timbre referenced from <Audio 1>.")
    retencion = ["<Picture 1> ([Shot 1] first frame): fully_preserved - composition, framing, "
                 "light and set are kept.",
                 "<Audio 1>: reference - the narrator follows <Audio 1>'s voice timbre without "
                 "copying its words or its signal."]
    return prompts.oficial_ref2va(
        sujetos, resumen, retencion,
        "The target video is a live-action, photographic scene with shallow depth of field.\n" + cuerpo,
        _sonido(audio, loc))


# Líneas de casting: no están en la película; sirven para que H3 invente la voz de
# cada personaje con una frase larga y limpia (2-4 s de habla), de la que sale la
# referencia. Cada una en el registro del personaje.
CASTING = {
    "jack": ("E47", "Stay quiet, and do exactly what I tell you."),
    "hannah": ("E52", "Please, I don't know who you are. I just want to go home."),
    "luka": ("E36", "Search every car! He's on this train, and I want him found!"),
    "wady": ("E62", "Boss, listen to me, this guy is not normal, okay?"),
}
