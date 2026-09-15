# -*- coding: utf-8 -*-
"""Arma proyecto.json de la réplica de «danza peligrosa» desde el mapa medido.

Mismo criterio que la réplica de @jcfdlw: el mapa (`tomas.py`) manda y el JSON
es una salida. Lo nuevo acá:

1. **Un clip por ENCUADRE, declarado a mano** (no inferido): varias tomas del
   mismo encuadre salen del mismo clip con otro `usa`. Se respeta el tiempo
   real entre tomas cuando entra en el clip (la toma 20 es 3,42 s después de la
   18 en el mismo plano), y si no entra se usa lo que sigue.
2. **La boca manda el `usa`.** En un clip que habla, H3 arranca la línea después
   de un silencio (`ONSET`, 1,0 s por defecto: el prompt lo pide así). Cada toma
   de ese encuadre usa el tramo que coincide con la voz del original:
   `usa_ini = ONSET + (inicio_toma - t0_línea)`. Después de generar se mide el
   arranque real de cada clip y se carga en `ONSETS_MEDIDOS`: no se regenera
   nada, se vuelve a correr esto.
3. **En inglés** (`"idioma": "en"`): el original de Kling se filmó en inglés.
4. **Clips de 5,17 s y nada más** (manual, 0.5): la toma más larga que queda
   es 4,54 s; la 14 se partió en el mapa.

    /c/Python314/python -X utf8 mis-videos/replica-danza/armar.py
"""
import json
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parents[1]))   # la raíz, para importar h3pipeline
from tomas import TOMAS, LINEAS, PLACAS, DURACION  # noqa: E402
import oficial  # noqa: E402  (los prompts en formato oficial de MiniMax)

SEGUNDOS = 5.17
TECHO = 4.87          # 5,17 − 0,30 de colchón: la cola de H3 deriva
ONSET = 1.0           # arranque de la voz que se le pide a H3 en cada clip que habla
ONSETS = {"E30": 1.5}  # Luka dispara un segundo y medio antes de gritar
ONSETS_MEDIDOS = {"E22": 0.36, "E23": 4.41, "E30": 3.77, "E36": 4.1, "E43": 4.51, "E44": 2.85, "E46": 2.68, "E47": 3.51, "E49": 1.64, "E52": 1.12, "E53": 1.06, "E54": 4.09, "E55": 0.62, "E61": 1.87, "E62": 1.0, "E64": 1.22, "E65": 0.31, "E68": 1.26, "E73": 2.21, "E74": 2.64, "E75": 2.34, "E81": 4.33}   # medido con montar.py medir

# ───────────────────────────── estilo ───────────────────────────────────────
# Sin nombrar el género de origen: «short-drama» trajo subtítulos chinos
# quemados en 9 clips de la réplica anterior (manual, 0.3).
ESTILO_IMAGEN = (
    "Photorealistic still from a premium romance-thriller series, shot on a full-frame "
    "digital cinema camera with 50mm and 85mm lenses, shallow depth of field, natural skin "
    "texture with pores and freckles, no beauty retouching, believable performances, warm "
    "practical light and bright window light, subtle film grain.")
ESTILO_VIDEO = (
    "Photorealistic cinematic footage, vertical 9:16, inside a restored vintage luxury train "
    "crossing the countryside. Natural, motivated movement; handheld weight.")
CIERRE_VIDEO = (
    "Keep the framing, the lens and the light of the first frame. The same people as in the "
    "first frame, in the same clothes, and nobody else; the place stays the same place. "
    "Photographic and cinematic, natural skin. Not animated, not illustrated, not CGI-looking.")
SOLO_SONIDOS = "the train rolling on the rails, fabric, footsteps and breathing"
SIN_TEXTO = "A single film frame: no text, no captions, no borders, no watermark, no logo."
LIENZO = ("VERTICAL 9:16 frame; keep the subject centred and nothing important near the left "
          "and right edges (the sides get trimmed).")

# ───────────────────────────── reparto ──────────────────────────────────────
HANNAH_CARA = ("Hannah, 22, a slim ballet dancer with a delicate oval face, light freckles "
               "across the nose, hazel-green eyes, honey-brown hair in a messy low bun with loose "
               "strands around her face, a faint smudge of farm dirt on her left cheekbone")
HANNAH_ROPA = ("an oversized worn brown-and-cream plaid flannel shirt hanging open over a pale "
               "pink camisole leotard, frayed light-blue denim cut-off shorts over pale pink tights")
HANNAH = f"{HANNAH_CARA}, wearing {HANNAH_ROPA}, chunky pink ribbed leg warmers and pink ballet slippers"
HANNAH_CAMPO = (f"{HANNAH_CARA}, wearing {HANNAH_ROPA} and worn tan embroidered cowboy boots, a "
                "canvas tote bag on her shoulder with pink pointe shoes hanging from it by their ribbons")
JACK_CARA = ("Jack, 32, a tall lean dangerously handsome man, dark brown hair swept back with "
             "short sides, a trimmed dark beard, pale blue-grey eyes, a fresh spray of blood on the "
             "LEFT side of HIS forehead and cheekbone, black ink tattoos up the side of his neck")
JACK_CAMISA = (f"{JACK_CARA}, in a crisp white dress shirt with the sleeves rolled to the "
               "forearm, a black leather shoulder-holster harness, black trousers and black "
               "fingerless leather driving gloves")
JACK_ABRIGO = (f"{JACK_CARA}, in a long black wool overcoat over a white shirt, a loose black "
               "silk scarf at the neck, a black wide-brimmed fedora and black fingerless leather "
               "gloves")
# En el original se saca el sombrero en la toma 21 y ya no lo vuelve a usar; la hoja
# de abrigo lo trae puesto, así que desde la 23 se dice explícito.
JACK_SIN_SOMBRERO = (f"{JACK_CARA}, BARE-HEADED with NO hat (he has taken the fedora off), in "
                     "a long black wool overcoat over a white shirt, a loose black silk scarf at "
                     "the neck and black fingerless leather gloves")
LUKA = ("Luka, 45, a thick-necked brute with a dark buzz cut, heavy stubble and a hard furious "
        "face, a worn dark-brown leather bomber jacket with a shearling collar over a black shirt, "
        "a bandolier of rifle cartridges across his chest, carrying an AK-47 rifle")
WADY = ("Wady, 33, messy dirty-blond wavy hair, a short blond beard, pale blue eyes, an "
        "olive-green canvas field coat over a grey hoodie, holding a black pistol")
MATONES = ("gang gunmen, half Italian mob and half street gang: a bald bearded man with "
           "tattooed arms in a black tank top holding a rifle, a man in a black studded leather "
           "jacket, a tattooed man in a sleeveless denim vest")
PASAJEROS = ("ordinary train passengers: a bald middle-aged man in a light grey sweater, a "
             "young woman with curly dark hair, round glasses and a cream cardigan")

# La voz sale de H3, en inglés (decisión del usuario, 14/9). H3 no tiene voice
# ID: cada clip inventa una voz. Lo único que la sostiene entre clips es
# describirla EXACTAMENTE igual en todos los prompts del personaje; la entrega
# de cada línea (grita, susurra) va aparte, en el [Speech] de cada encuadre.
VOCES = {
    "hannah": ("a young American woman in her early twenties, a light, clear, slightly husky "
               "voice with a soft breathy edge, General American accent"),
    "jack": ("a man in his early thirties, a deep, low, smooth baritone with a slight rasp, calm "
             "and unhurried, General American accent"),
    "luka": ("a heavy-set man in his forties, a rough, gravelly, loud bass voice with a thick "
             "Eastern European accent"),
    "wady": ("a man in his early thirties, a mid-pitched, reedy, jittery voice that speeds up "
             "when scared, General American accent"),
}

PERSONAJES = {
    "hannah": {"hoja": "m_hannah", "descripcion": HANNAH},
    "jack_abrigo": {"hoja": "m_jack_abrigo", "descripcion": JACK_ABRIGO},
    "jack_camisa": {"hoja": "m_jack_camisa", "descripcion": JACK_CAMISA},
    "luka": {"hoja": "m_luka", "descripcion": LUKA},
    "wady": {"hoja": "m_wady", "descripcion": WADY},
    "matones": {"hoja": "m_matones", "descripcion": MATONES},
    "pasajeros": {"hoja": "m_pasajeros", "descripcion": PASAJEROS},
}

CAB_VENTANA = ("the private compartment of a restored vintage luxury train car: glossy mahogany "
               "wall panels, tall windows with white lace curtains and red-and-cream striped side "
               "drapes glowing with bright daylight, a brass handrail under the windows like a "
               "ballet barre, a mustard-gold tufted velvet banquette with red fringe, deep red "
               "carpet, a coffered dark wood ceiling with cream panels and a brass ceiling fan")
CAB_PUERTA = ("the door end of the same luxury train car: a double mahogany door with a heavy "
              "brass sliding bolt, framed by heavy gold brocade curtains draped with garlands of "
              "dark red silk roses, ornate gold-and-crystal chandeliers, coffered mahogany ceiling, "
              "deep red carpet")
PASILLO = ("the narrow side corridor of a vintage train: polished honey-coloured wood paneling "
           "and compartment doors on one side, windows with cream pleated curtains on the other, "
           "a red carpet runner, ceiling vents, bright overcast daylight")
VAGON_BLANCO = ("a vintage train carriage painted cream-white: panelled walls and doors with "
                "brass fittings, small stained-glass transom windows, gold curtains, red velvet "
                "seats, flat bright daylight")
CAMPO = ("a golden-hour grassy field beside railway tracks, utility poles and power lines, "
         "distant low industrial buildings and a few palm trees, hazy warm sky")

LOCACIONES = {
    "campo": {"imagen": "l_campo", "descripcion": CAMPO},
    "cabina_ventana": {"imagen": "l_cabina_ventana", "descripcion": CAB_VENTANA},
    "cabina_puerta": {"imagen": "l_cabina_puerta", "descripcion": CAB_PUERTA},
    "pasillo": {"imagen": "l_pasillo", "descripcion": PASILLO},
    "vagon_blanco": {"imagen": "l_vagon_blanco", "descripcion": VAGON_BLANCO},
}

HOJA = ("{estilo} CHARACTER REFERENCE SHEET on a plain mid-grey studio background with even soft "
        "light: the same person shown four times side by side, full body, head to toe — front "
        "view, three-quarter view, side profile, and back view — with identical face, hair and "
        "clothing in all four. {quien}. Neutral standing pose, arms relaxed. Every detail sharp: "
        "this sheet is the reference for every other shot. {sin_texto}")
LUGAR = "{estilo} {que}. Nobody in the frame: an empty set. " + LIENZO + " {sin_texto}"

# Las dos hojas aprobadas en la prueba de motores se copian tal cual (m_hannah,
# m_jack_camisa): son las caras que el usuario eligió. Las demás se generan;
# la de Jack de abrigo toma la cara de su hoja de camisa.
MADRE = [
    ("m_hannah", [], HOJA.format(estilo=ESTILO_IMAGEN, quien=HANNAH, sin_texto=SIN_TEXTO)),
    ("m_jack_camisa", [], HOJA.format(estilo=ESTILO_IMAGEN, quien=JACK_CAMISA, sin_texto=SIN_TEXTO)),
    ("m_jack_abrigo", ["assets/m_jack_camisa.png"],
     HOJA.format(estilo=ESTILO_IMAGEN, sin_texto=SIN_TEXTO, quien=(
         "Use the reference image for the face, hair, beard, tattoos and blood: the SAME man. "
         f"{JACK_ABRIGO}. Only the clothes change from the reference"))),
    ("m_luka", [], HOJA.format(estilo=ESTILO_IMAGEN, sin_texto=SIN_TEXTO, quien=LUKA)),
    ("m_wady", [], HOJA.format(estilo=ESTILO_IMAGEN, sin_texto=SIN_TEXTO, quien=WADY)),
    ("m_matones", [], (
        f"{ESTILO_IMAGEN} CHARACTER LINE-UP on a plain mid-grey studio background with even soft "
        f"light: three different men standing side by side, full body, facing camera — "
        f"{MATONES}. Each one clearly distinct. {SIN_TEXTO}")),
    ("m_pasajeros", [], (
        f"{ESTILO_IMAGEN} CHARACTER LINE-UP on a plain mid-grey studio background with even soft "
        f"light: two different people standing side by side, full body, facing camera — "
        f"{PASAJEROS}. {SIN_TEXTO}")),
    ("l_campo", [], LUGAR.format(estilo=ESTILO_IMAGEN, que=CAMPO, sin_texto=SIN_TEXTO)),
    ("l_cabina_ventana", [], LUGAR.format(estilo=ESTILO_IMAGEN, sin_texto=SIN_TEXTO,
                                          que=f"Looking at the window wall of {CAB_VENTANA}")),
    ("l_cabina_puerta", [], LUGAR.format(estilo=ESTILO_IMAGEN, sin_texto=SIN_TEXTO,
                                         que=f"Looking at the door wall of {CAB_PUERTA}")),
    ("l_pasillo", [], LUGAR.format(estilo=ESTILO_IMAGEN, sin_texto=SIN_TEXTO,
                                   que=f"Looking straight down {PASILLO}")),
    ("l_vagon_blanco", [], LUGAR.format(estilo=ESTILO_IMAGEN, que=VAGON_BLANCO, sin_texto=SIN_TEXTO)),
]

# ───────────────────────────── refuerzos ─────────────────────────────────────
# Medidos en la réplica anterior: el detalle se abre y muestra la cara; la nuca
# en primer término se da vuelta. En la prueba de motores: el primer plano se
# abrió hasta el short.
REFUERZO = {
    "PD": (" FRAMING IS THE POINT: this is an insert of that detail and nothing else; everything "
           "outside it is cut off by the edges of the frame, faces included."),
    "PP": (" TIGHT CLOSE UP: the face fills the upper half of the frame and the bottom edge cuts "
           "across the chest; no waist, no hips, no legs in the picture."),
    "PM": (" MEDIUM SHOT: the bottom edge of the frame crops at the waist; no knees, no feet."),
}
ESPALDA = (" The person closest to the camera is seen FROM BEHIND, out of focus, a dark shape at "
           "the edge of the frame: do not turn them towards camera.")
# Tanda 1 y 2 (14/9): GPT abrió estos seis a cuerpo entero aunque el texto pedía
# plano medio cerrado; en el original son de pecho para arriba. Se pide con una
# imagen de televisión concreta y nombrando lo que no puede entrar.
# Ni así: en la tanda 3 cortaban a la cintura. Los PNG que se usan son esos
# mismos RECORTADOS A MANO desde arriba (80 % superior, 9:16) — las versiones
# sin recortar están en _descartados/tanda3_sin_recorte/. Si se regeneran con
# `frames --force`, hay que volver a recortarlos.
CERRAR = {"E24", "E27", "E43", "E46", "E70", "E74"}
REFUERZO_CERRADO = (" CROP LIKE A TIGHT TV CLOSE TWO-SHOT: the camera is less than a metre from their "
                    "faces; the two heads and shoulders fill the whole frame and the BOTTOM EDGE of "
                    "the frame cuts across their chests. The denim shorts, the waist, the belt, the "
                    "hips and the legs are completely outside the picture.")
# l_campo salió con un sol naranja de postal; el original es una hora dorada
# suave con el cielo pálido.
LUZ_CAMPO = (" LIGHT: soft late-afternoon golden hour, the sun low but out of frame, a pale "
             "blue-white hazy sky, gentle warm light on skin; not an orange sunset.")
HOLANDES = (" DUTCH ANGLE: the whole camera is tilted about 20 degrees, the verticals of the "
            "corridor lean diagonally across the frame.")


# ───────────────────────────── los 73 encuadres ─────────────────────────────
# clave → (qué se ve, qué se mueve, audio). El tamaño, la locación y el reparto
# salen del mapa (primera toma del encuadre).
E = {}


def e(k, ve, mueve, audio):
    E[k] = (ve, mueve, audio)


# ── 1 · El pasado (voz en off, sin bocas)
e("E01", "WIDE SHOT of a vast bright green prairie under a deep blue sky with a few white clouds, "
         "a herd of brown-and-white cattle grazing in a line across the middle distance, three cows "
         "close in the foreground, one lifting its head. No people, no buildings.",
  "The cows graze slowly; one in front lifts its head and chews; a light wind moves the grass in "
  "waves. The camera drifts gently sideways.",
  "[Ambient] open prairie wind, distant cattle. [SFX] a cow lowing once far away.")
e("E02", "EXTREME CLOSE INSERT, camera almost on the ground: ONLY a woman's lower legs from just "
         "above the knees down, in pale pink tights and worn tan embroidered cowboy boots, one boot "
         "stepping towards camera through the grass; the top edge of the frame cuts above the knees, "
         "so no shorts, no hands, no bag, no body above the knees; blurred railway buildings behind.",
  "Step after step the boots come towards camera through the grass, the camera tracking backwards "
  "just ahead of them, the low sun flaring between the legs.",
  "[Foley] boots crunching dry grass, a canvas bag swinging.")
e("E03", f"INSERT of a young woman's torso while she walks: the open plaid flannel shirt over the "
         f"pale pink leotard, her hands hooking a pair of worn pink pointe shoes by their ribbons onto "
         f"a canvas tote bag on her shoulder; her face cut off above the frame; warm backlight. "
         f"She is {HANNAH_CAMPO}.",
  "Her fingers loop the satin ribbons over the bag strap and let the pointe shoes swing against "
  "the canvas as she keeps walking.",
  "[Foley] satin ribbons, canvas, footsteps in grass.")
e("E04", f"MEDIUM SHOT of {HANNAH_CAMPO}, walking towards camera through a golden-hour field "
         f"beside the railway, utility poles and power lines behind her, hazy low sun on her hair. "
         f"She looks off to the side, determined and a little sad.",
  "She walks steadily towards camera, the camera backing away at her pace; she turns her head to "
  "look at something off to the side, then back ahead; loose strands of hair lift in the wind.",
  "[Ambient] warm evening wind, a distant train horn. [Foley] footsteps in grass, the bag swinging.")
e("E05", f"FULL SHOT from a very LOW ANGLE of {HANNAH_CAMPO}, standing in the field, seen against a "
         f"flat pale white sky, dry bare branches at the lower edge of frame. She looks up and away, "
         f"the plaid shirt moving in the wind.",
  "She looks up at the sky, takes a breath and pulls the shirt closer around her; the wind moves "
  "her hair and the dry branches.",
  "[Ambient] wind across an open field.")
e("E06", "EXTREME WIDE SHOT from high above: a sky-blue and white passenger train running along a "
         "curving track through golden scrubland and green bushes at sunset, long warm shadows. "
         "The train is small in the frame. No people visible.",
  "The train runs smoothly from left to right along the curve; the camera pans slowly to follow it.",
  "[Ambient] a distant train rolling on rails, wind.")

# ── 1b · La cabina: calentamiento y la llamada
e("E07", f"INSERT inside the train compartment: a dancer's hands tying the satin ribbons of a "
         f"pink pointe shoe around her ankle, her leg in pale pink tights and a pink leg warmer "
         f"resting on the mustard velvet banquette with red fringe; red carpet below. She is {HANNAH}.",
  "Her fingers cross the ribbons around the ankle, pull them tight and tuck the knot in.",
  "[Foley] satin ribbon pulled tight, velvet. [Ambient] the train rolling.")
e("E08", f"CLOSE UP of {HANNAH}, sitting on the banquette in the train compartment, eyes lowered, "
         f"lost in thought, a red-and-cream striped drape and a brass lamp softly out of focus behind her.",
  "She breathes out slowly, lifts her eyes for a moment towards the window, and lowers them again.",
  "[Ambient] the train rolling, the carriage creaking softly.")
e("E09", "INSERT at floor level in the train compartment: two feet in pink satin pointe shoes rising "
         "onto full pointe on the deep red carpet, pink ribbed leg warmers, pale pink tights, the "
         "bottom of a bright window and a brass rail behind.",
  "The feet rise onto full pointe, hold, and come down softly, then rise again.",
  "[Foley] satin shoes on carpet, a soft creak of the floor. [Ambient] the train rolling.")
e("E10", f"MEDIUM SHOT from a LOW ANGLE of {HANNAH}, stretching one arm high above her head in front "
         f"of a bright window, backlit, head tilted back, eyes half closed, the plaid shirt falling "
         f"open from her raised arm.",
  "She reaches higher, arches her back and lets her head fall back, breathing out, then slowly "
  "brings the arm down.",
  "[Foley] a long controlled breath, fabric. [Ambient] the train rolling.")
e("E11", f"MEDIUM-WIDE SHOT from the knees up in the train compartment of {HANNAH}, one leg extended along the brass handrail "
         f"under the lace-curtained window like a ballet barre, folding her body down over the leg, "
         f"her face close to her knee.",
  "She folds deeper over the extended leg, reaching for her foot, then slowly rises.",
  "[Foley] a slow breath, fabric sliding on brass. [Ambient] the train rolling.")
e("E12", f"WIDE SHOT of the whole train compartment: {HANNAH} stands at the window with one leg "
         f"raised onto the brass handrail, stretching; the mustard velvet banquette with red fringe "
         f"along the left, two tall bright windows with white lace curtains, deep red carpet, a phone "
         f"lying on the banquette. She is small in the frame, about one third of the image height.",
  "She folds forward over the raised leg, rises, sweeps one arm up over her head in a graceful port "
  "de bras, then bends down to the leg again.",
  "[Ambient] the train rolling, the carriage swaying. [Foley] soft breathing.")
e("E13", "INSERT at the lace-curtained window of the train compartment: a dancer's leg in a pink leg "
         "warmer resting along the brass handrail, and her hand reaching into frame to pick up a "
         "smartphone that lies buzzing on the windowsill.",
  "The phone vibrates on the sill; the hand picks it up and lifts it out of frame.",
  "[SFX] a phone vibrating on wood. [Ambient] the train rolling.")
e("E14a", f"MEDIUM SHOT of {HANNAH}, standing by a dark mahogany wall in the train compartment, "
          f"looking down at the phone in her hand, her other hand at her hair, her face serious and "
          f"annoyed, lit by soft window light.",
  "She reads the screen, her jaw tightening; she pushes a loose strand of hair back and keeps "
  "staring at the phone.",
  "[SFX] the phone still buzzing. [Ambient] the train rolling.")
e("E14b", f"CLOSE UP of {HANNAH}, looking down at the phone in her hand, eyes cold and determined, "
          f"a dark mahogany wall behind her.",
  "Her eyes narrow at the screen; she presses her lips together and lets the call ring out.",
  "[Ambient] the train rolling. [SFX] the phone buzzing, then stopping.")

# ── 2 · Entra la Víbora
e("E15", "INSERT: a pair of dark mahogany double doors with brass handles, closed, filling the frame, "
         "gold curtains at both edges.",
  "The doors burst open violently towards camera, both leaves swinging, a dark figure blurring "
  "through the gap.",
  "[SFX] gunshots in the corridor, the doors banging open.")
e("E16", f"WIDE SHOT down the luxury train car towards its double doors: {JACK_ABRIGO} walks towards "
         f"camera between heavy gold curtains with red rose garlands, under gold-and-crystal "
         f"chandeliers, a pistol low in his gloved hand, the fedora brim hiding his eyes. He is about "
         f"one third of the image height.",
  "He walks steadily and silently towards camera, the coat swinging; the camera backs away slowly. "
  "As he gets closer he lifts his chin and his eyes appear under the brim.",
  "[Foley] heavy footsteps on carpet, a coat moving. [Ambient] the train rolling.")
e("E17", f"CLOSE UP of the man's face under a black fedora brim: the brim hides his eyes, only his "
         f"bearded jaw, the blood on the left side of his face and the tattoos on his neck are "
         f"visible, gold curtains out of focus. He is {JACK_ABRIGO}.",
  "He lowers his head a little further so the brim covers even more, then stops walking.",
  "[Foley] breathing, leather gloves creaking.")
e("E18", f"MEDIUM SHOT of {HANNAH} at the bright lace-curtained window of the train compartment, "
         f"one hand on the window frame, turning sharply away from the glass towards camera, startled.",
  "She spins around from the window, her hair flying, and freezes facing camera, eyes wide, lips "
  "parted, her hand still gripping the window frame.",
  "[Foley] a sharp gasp, fabric. [Ambient] the train rolling.")
e("E21", f"FULL SHOT over the shoulder of Hannah towards the door end of the train car: {JACK_ABRIGO} "
         f"stands under the chandeliers between gold curtains and pulls off his fedora with one "
         f"gloved hand; the back of Hannah's head and her plaid shirt fill the right edge of the "
         f"frame, out of focus. She is {HANNAH}.",
  "He sweeps the hat off, tosses it aside and takes a quick step towards her.",
  "[Foley] a hat landing on velvet, footsteps.")
e("E22", f"CLOSE UP of {HANNAH} against the bright window, frightened, mouth open to shout; at the "
         f"left edge of frame the black-gloved hand of a man is coming towards her face.",
  "She stays silent for about one second, then shouts the line at him — and on the last word the "
  "black-gloved hand clamps over her mouth, muffling her.",
  "[Speech] a young woman shouting, frightened, cut off by a hand. [Foley] a leather glove on skin.")
e("E23", f"CLOSE UP over Hannah's shoulder of {JACK_SIN_SOMBRERO}, very close to her, blood on his face, "
         f"gold curtains and a chandelier out of focus behind him; the back of her head blurred at "
         f"the right edge. He looks straight at her.",
  "He holds still and silent for about one second, then brings his lips close and hushes her with "
  "a long soft 'shh', eyes locked on hers.",
  "[Speech] a man hushing softly, very close. [Ambient] the train rolling.")
e("E24", f"MEDIUM SHOT at the bright lace window: {JACK_SIN_SOMBRERO} pins {HANNAH} against the window "
         f"frame, one gloved finger pressed on her lips; she stares at him with wide eyes, breathing hard.",
  "He keeps the finger on her lips and glances towards the door; her chest rises and falls fast; "
  "neither of them speaks.",
  "[Foley] fast breathing, a leather glove. [SFX] muffled gunshots somewhere in the train.")
e("E25", f"WIDE SHOT of the whole compartment: {JACK_SIN_SOMBRERO} crowds {HANNAH} against the far window "
         f"between the brass rail and the lace curtains, the mustard banquette on the left, red carpet. "
         f"Both about one third of the image height.",
  "He pushes her back against the window and turns his head towards the door.",
  "[Foley] a body against glass. [Ambient] the train rolling.")
e("E26", "INSERT of a heavy brass sliding bolt on a mahogany door: a black fingerless-gloved hand "
         "grabs the knob of the bolt.",
  "The gloved hand slams the brass bolt across, locking the door with one hard push.",
  "[SFX] a brass bolt shooting home, metallic and loud.")
e("E27", f"MEDIUM SHOT at the bright window: {JACK_SIN_SOMBRERO} and {HANNAH} pressed together, both turning "
         f"their heads towards the door off camera, alert and frozen.",
  "Both heads turn slowly to look at the door; he tightens his grip on her arm; they hold their "
  "breath.",
  "[SFX] footsteps and shouting getting closer outside. [Foley] held breath.")
e("E28", f"FULL SHOT of {JACK_SIN_SOMBRERO} seen from behind at the door end of the car, peering out through "
         f"a gap in the heavy gold curtain; Hannah's shoulder in plaid out of focus in the right "
         f"foreground.",
  "He pulls the curtain an inch aside, looks out, and lets it fall back.",
  "[Foley] heavy curtain fabric. [SFX] shouting in the corridor.")

# ── 3 · Los matones
e("E29", f"WIDE SHOT down {PASILLO}; blurred panicking passengers cross the foreground, and far down "
         f"the corridor a gunman appears. The people are {PASAJEROS}.",
  "Passengers rush across the frame in a blur; at the end of the corridor an armed man steps out "
  "and advances.",
  "[Ambient] panicked passengers, screams. [Foley] running footsteps.")
e("E30", f"MEDIUM SHOT from a LOW ANGLE of {LUKA}, standing in the train corridor, raising the AK-47 "
         f"towards the ceiling, face twisted with rage.",
  "For about a second and a half he fires a burst into the ceiling, muzzle flash lighting his "
  "face; then he swings the rifle down and shouts the line at the passengers.",
  "[SFX] a burst of AK-47 fire, deafening. [Speech] a man shouting in rage.")
e("E31", f"MEDIUM SHOT: a gunman bursts through a cream-white door into the carriage, rifle raised, "
         f"scanning. He is one of the {MATONES}.",
  "He shoves the door open with his shoulder and sweeps the rifle across the carriage.",
  "[Foley] a door banging, boots. [Ambient] screams.")
e("E33", f"MEDIUM SHOT of {WADY}, in the train corridor, grinning wildly, pistol raised next to his face.",
  "He grins, cocks his head and waves the pistol, enjoying the chaos.",
  "[Foley] a pistol slide racked. [Ambient] panic in the corridor.")
e("E34", f"MEDIUM SHOT in the train corridor: a terrified passenger peeks out of a compartment door "
         f"and screams. She is from the {PASAJEROS}.",
  "She screams, turns and flees back through the doorway, slamming into the frame.",
  "[Speech] a woman screaming, no words. [Foley] a door slamming.")
e("E35", f"FULL SHOT from behind: {MATONES} push into compartments along the cream-white carriage, "
         f"rifles raised, backs to camera.",
  "They move off down the carriage, one kicking a door open, another checking behind a curtain.",
  "[Foley] boots, a door kicked open. [Speech] a man shouting one word off camera.")
e("E36", f"FULL SHOT of {LUKA}, leaning against the polished wood wall of the train corridor, rifle "
         f"hanging from his hand, looking straight at camera.",
  "He pushes off the wall, holds a silent beat for about one second, then shouts the line up the "
  "corridor, glaring into camera, and goes quiet, breathing hard.",
  "[Speech] a man shouting a short question. [Ambient] the train rolling.")

# ── 4 · La levanta y el cuchillo
e("E38", f"MEDIUM SHOT from behind of {JACK_CAMISA}, at the door end of the car between gold curtains, "
         f"shrugging the long black overcoat off his shoulders, revealing the white shirt and the "
         f"black shoulder-holster harness.",
  "He shrugs the coat off in one move and lets it drop.",
  "[Foley] a heavy wool coat sliding off, leather straps creaking.")
e("E39", f"MEDIUM SHOT over his shoulder: {HANNAH} stands by the bright window watching him, confused "
         f"and scared, arms close to her body; his white shirt and holster strap blurred in the left "
         f"foreground.",
  "She watches him, frowning, takes half a step back against the window.",
  "[Foley] fabric, a nervous breath.")
e("E40", f"FULL SHOT of {JACK_CAMISA} under the chandeliers between the gold curtains, turning to face "
         f"camera; the back of Hannah's head and plaid shirt blurred in the right foreground.",
  "He turns round towards her with purpose and strides forward.",
  "[Foley] footsteps, leather harness creaking.")
# Rechazado por el filtro de OpenAI con «las piernas alrededor de la cadera».
# Se cuenta como lo que es en la escena: un movimiento brusco para esconderla.
e("E41", f"WIDE SHOT of the compartment in front of the bright window: {JACK_CAMISA} grabs {HANNAH} "
         f"and lifts her clean off the floor in a tight protective hold, her arms thrown around his "
         f"neck in surprise, her feet off the ground; he is seen from behind, she looks over his "
         f"shoulder, startled. They fill about half the image height.",
  "He swings her up off the floor in one move and turns with her; she clings to his neck, startled.",
  "[Foley] a gasp, fabric, a body lifted.")
e("E42", "INSERT from behind: a man's back in a white shirt crossed by a black leather holster "
         "harness, a woman's arms in plaid flannel sleeves wrapped around his neck.",
  "Her hands grip his shoulders as he turns; the harness straps tighten across his back.",
  "[Foley] leather creaking, fabric.")
e("E43", f"TIGHT MEDIUM SHOT from the chest up at the lace window: {HANNAH} fills the right two thirds "
         f"of the frame, just set down, looking down at him, confused; Jack's head and shoulder in "
         f"the white shirt are large and out of focus in the lower left foreground, his gloved hand "
         f"drawing a black tactical knife. Jack is {JACK_CAMISA}. No legs, no shorts in the frame.",
  "She stays silent for about one second, then asks the line, bewildered, as the black knife comes "
  "up between them.",
  "[Speech] a young woman asking, breathless. [Foley] a knife drawn from a sheath.")
e("E44", f"CLOSE UP of {JACK_CAMISA}, three-quarter view, raising a black tactical knife close to his "
         f"face, eyes on her, lace window out of focus behind.",
  "He holds a silent beat for about one second, then hushes her softly — 'shh, shh' — bringing the "
  "knife up.",
  "[Speech] a man hushing softly twice, close. [Ambient] the train rolling.")
e("E45", f"CLOSE UP from a LOW ANGLE of {HANNAH}, the flat black blade of a knife held vertically "
         f"against her lips by a black-gloved hand; dark wood ceiling beams above her; her eyes wet.",
  "She holds perfectly still, trembling, eyes darting down to the blade.",
  "[Foley] shaky breathing. [Ambient] the train rolling.")
e("E46", f"CLOSE TWO-SHOT IN PROFILE at the lace window, framed from the chest up so the two faces "
         f"fill the upper half of the frame: on the left {JACK_CAMISA}, facing right; on the right "
         f"{HANNAH}, facing left; faces a hand's width apart; he holds the black knife upright "
         f"between them. No waist, no legs in the frame.",
  "He holds a silent beat for about one second, then murmurs a single word with a slow smile, and "
  "keeps staring at her; later his eyes flick towards the door.",
  "[Speech] a man murmuring one word. [Foley] breathing.")
e("E47", f"CLOSE UP of {JACK_CAMISA}, three-quarter view, close to her, a red-and-cream striped drape "
         f"out of focus behind, the black knife held near her throat at the bottom edge; her hair "
         f"blurred at the right edge.",
  "He holds a silent beat for about one second, then says the line low and slow, almost tender, "
  "with a dangerous half smile.",
  "[Speech] a man speaking low and slow, intimate and menacing.")
e("E48", f"CLOSE UP in profile of {HANNAH}, facing left, the black blade held upright in front of her "
         f"lips by a gloved hand, a bright window out of focus behind her.",
  "She trembles, then slowly tips her head back as the blade slides down under her chin, her eyes "
  "closing.",
  "[Foley] a shaky breath. [Ambient] the train rolling.")
e("E49", f"CLOSE UP of {JACK_CAMISA}, three-quarter view, close to her, a red-and-cream striped drape "
         f"out of focus behind, his gloved hand with the knife at the bottom edge; her hair blurred "
         f"at the right edge.",
  "He holds a silent beat for about one second, then says the line slowly, with a pause after the "
  "first word, eyes cold.",
  "[Speech] a man threatening, slow and quiet.")
e("E52", f"CLOSE UP from a LOW ANGLE of {HANNAH}, tears on her cheeks, the flat of a black knife held "
         f"against the side of her neck by a gloved hand, dark wood ceiling beams and cream ceiling "
         f"panels above; his shoulder in a white shirt blurred at the lower left.",
  "She stays silent for about one second, then pleads the line through tears, her voice breaking.",
  "[Speech] a young woman pleading through tears.")
e("E53", f"CLOSE UP of {JACK_CAMISA}, three-quarter view, a red-and-cream striped drape out of focus "
         f"behind, knife hand at the bottom edge; her hair blurred at the right edge.",
  "He holds a silent beat for about one second, then asks the line quickly, tilting his head.",
  "[Speech] a man asking a short question.")
e("E54", f"CLOSE UP from a LOW ANGLE of {HANNAH}, crying, the black knife against her neck, dark wood "
         f"ceiling beams above.",
  "She stays silent for about one second, then answers with a single word, voice shaking.",
  "[Speech] a young woman answering in one word, shaking.")
e("E55", f"CLOSE UP of {JACK_CAMISA}, three-quarter view, a red-and-cream striped drape out of focus "
         f"behind, knife hand at the bottom edge; her hair blurred at the right edge.",
  "He holds a silent beat for about one second, then breaks into a wolfish smile and says the line.",
  "[Speech] a man speaking with amusement.")
e("E56", f"CLOSE UP from a LOW ANGLE of {HANNAH}, sobbing silently, eyes lifted, the black knife "
         f"against her neck, dark wood ceiling beams above.",
  "She cries without a sound, swallowing, her eyes searching his face.",
  "[Foley] a trembling breath. [Ambient] the train rolling.")

# ── 5 · La recompensa (vagón blanco)
e("E58", f"FULL SHOT over the shoulder of a bald passenger in a grey sweater (out of focus, right "
         f"foreground): {LUKA} storms through a cream-white doorway into the carriage, rifle first.",
  "Luka barges through the door and points the rifle at the passenger, who shrinks back.",
  "[Foley] a door banging, boots. [Speech] a frightened gasp.")
e("E59", f"MEDIUM SHOT in the cream-white carriage: {LUKA} shoves a bald passenger in a grey sweater, "
         f"who raises both hands in terror.",
  "Luka shoves the man hard with his forearm; the man stumbles back with his hands up.",
  "[Foley] a shove, a grunt. [Speech] a man whimpering.")
e("E60", f"WIDE SHOT down the train corridor: gunmen pin passengers against the wood-panelled wall at "
         f"gunpoint. The gunmen are {MATONES}; the passengers are {PASAJEROS}.",
  "A gunman shoves a passenger against the wall and presses the rifle to him; the others hold "
  "their hands up.",
  "[Ambient] panic, crying. [Foley] bodies against wood.")
e("E61", f"MEDIUM SHOT in the cream-white carriage over Wady's shoulder (his olive coat blurred in the "
         f"left foreground): {LUKA} faces camera, furious, rifle across his chest.",
  "Luka paces, holds a silent beat for about one second, then spits the line out in fury, "
  "jabbing a finger.",
  "[Speech] a man shouting in fury.")
e("E62", f"MEDIUM SHOT of {WADY}, in the cream-white carriage, scared and agitated, pleading towards "
         f"someone off camera.",
  "He holds a silent beat for about one second, then says the line fast and nervous, gesturing "
  "with his free hand.",
  "[Speech] a man talking fast, nervous.")
e("E63", f"MEDIUM SHOT in the cream-white carriage over Wady's shoulder (blurred in the left "
         f"foreground): {LUKA} listens, jaw clenched, glaring.",
  "Luka listens without a word, breathing through his nose; at the end he shoves Wady hard in the "
  "chest.",
  "[Foley] heavy breathing, a shove.")
e("E64", f"MEDIUM SHOT of {WADY}, in the cream-white carriage, wide-eyed, talking fast.",
  "He holds a silent beat for about one second, then says the line very fast, counting on his "
  "fingers, panicking.",
  "[Speech] a man talking very fast, panicking.")
e("E65", f"MEDIUM SHOT in the cream-white carriage over Wady's shoulder (blurred in the left "
         f"foreground): {LUKA} grabs the lapel of Wady's olive coat and pulls him close, snarling.",
  "Luka yanks him in, holds a silent beat for about one second, then growls the line into his face "
  "and shouts the end of it.",
  "[Speech] a man growling, then shouting.")
e("E66", f"MEDIUM SHOT in the train corridor: a bald bearded gunman with tattooed arms in a black tank "
         f"top, rifle ready, looks round in alarm. He is one of the {MATONES}.",
  "He turns his head sharply, grips the rifle and steps forward.",
  "[Foley] boots, a rifle strap.")
e("E68", f"FULL SHOT in the cream-white carriage: {WADY} runs for the doorway, pistol up, shoving past a "
         f"gunman.",
  "He stays silent for about one second, then shouts the line and bolts through the door.",
  "[Speech] a man shouting orders. [Foley] running footsteps.")
e("E69", f"WIDE SHOT down the train corridor: {MATONES} and Wady run towards camera, weapons up.",
  "They charge down the corridor towards camera, shoving through.",
  "[Foley] running boots, weapons rattling. [Speech] a man shouting one word.")

# ── 6 · El tirante y la patada
e("E70", f"TIGHT MEDIUM SHOT from the chest up at the lace window, both faces in the upper half of the "
         f"frame: {JACK_CAMISA} on the left slides the plaid flannel shirt off {HANNAH}'s right "
         f"shoulder with his gloved hand, uncovering the thin strap of her pink camisole leotard; "
         f"she is on the right, fully dressed underneath, frozen, looking at him. No waist, no "
         f"shorts, no legs in the frame.",
  "His hand pushes the shirt down off her shoulder slowly; she holds her breath and does not move.",
  "[Foley] flannel sliding, a held breath.")
e("E71", f"CLOSE UP of {JACK_CAMISA}, three-quarter view, looking down at her bare shoulder in the "
         f"foreground (the thin pink leotard strap visible), a striped drape out of focus behind.",
  "His eyes move down to her shoulder and back up to her face; a slow breath.",
  "[Foley] breathing. [Ambient] the train rolling.")
e("E72", "INSERT: the tip of a black knife held in a gloved hand slips under the thin strap of a pale "
         "pink camisole leotard on a woman's shoulder; the plaid shirt pushed off the shoulder.",
  "The blade lifts the strap away from the skin and slices it; the strap springs loose and falls "
  "onto the shoulder. The leotard stays in place.",
  "[SFX] a sharp slice of fabric. [Foley] a gasp.")
e("E73", f"CLOSE UP of {JACK_CAMISA}, three-quarter view, close to her, a striped drape out of focus "
         f"behind, her bare shoulder blurred at the lower right.",
  "He holds a silent beat for about one second, then says the line slowly, leaving a pause "
  "between the words.",
  "[Speech] a man speaking slowly, menacing and intimate.")
e("E74", f"CLOSE TWO-SHOT IN PROFILE at the lace window, framed from the chest up so the two faces "
         f"fill the upper half of the frame: on the left {JACK_CAMISA}, facing right, his gloved "
         f"hand gripping her shoulder; on the right {HANNAH}, facing left, chin lifted; faces very "
         f"close. No waist, no legs in the frame.",
  "He holds a silent beat for about one second, then finishes the threat in a whisper; after "
  "that his eyes slide towards the door while she trembles.",
  "[Speech] a man whispering a short threat.")
e("E75", f"CLOSE UP from a LOW ANGLE of {HANNAH}, the black knife in a gloved hand near her bare "
         f"shoulder, dark wood ceiling beams above, crying and scared.",
  "She holds her breath for about two seconds, then nods quickly and whispers the line, giving in.",
  "[Speech] a young woman whispering, giving in.")
# Rechazado por el filtro («sentada a horcajadas»). Se pide el abrazo que
# esconde a Jack, que es lo que la toma le muestra a los matones.
e("E77", f"FULL SHOT at the lace window: {HANNAH} and {JACK_CAMISA} on the banquette in a tight "
         f"embrace, seen from behind her: her back and the plaid shirt slipping off one shoulder "
         f"fill the frame, his arms around her in a protective hug, his face hidden behind her "
         f"shoulder so only his dark hair shows; both fully dressed.",
  "He pulls her in closer and she clutches his shoulders, rocking slightly with the train.",
  "[Foley] fabric, velvet creaking. [Ambient] the train rolling.")
# Rechazado por el filtro de OpenAI («mano apretando la cadera sobre el short»).
# La mano va a la espalda, sobre la camisa: el gesto de acercarla se lee igual.
e("E78", "INSERT: a black fingerless leather glove pressed flat against the back of a worn "
         "brown-and-cream plaid flannel shirt, between the shoulder blades, pulling the wearer close; "
         "nothing else in the frame but the glove and the flannel.",
  "The gloved hand presses in and draws her closer; the flannel creases under the fingers.",
  "[Foley] a leather glove on flannel.")
e("E79", f"FULL SHOT at the door end of the car: {WADY} kicks the door and bursts through the heavy "
         f"gold curtain into the car, blurred with motion.",
  "He smashes through with a kick, the curtain whipping aside.",
  "[SFX] a door kicked in, wood splintering.")
e("E80", f"WIDE SHOT point of view from inside the car towards the door: {WADY} at the front with "
         f"his pistol raised and {MATONES} crowding behind him under the gold-and-crystal "
         f"chandeliers, all aiming straight at camera; a blurred plaid shoulder in the foreground.",
  "They push in and level their guns at camera; Wady grins.",
  "[Foley] guns cocked, boots. [Speech] a woman's gasp off camera.")
# Rechazado por el filtro («cabeza atrás, él hundido en su cuello»). Lo que
# cuenta la toma es el susto al ver las armas, y eso sí se puede pedir.
e("E81", f"CLOSE UP in profile of {HANNAH}, her face snapping towards the door off camera, eyes wide "
         f"in shock, mouth open in a startled gasp; Jack's dark hair out of focus at the lower left "
         f"edge, hiding his face behind her shoulder; dark wood ceiling above.",
  "She stays still for about one second, then gasps loudly, mouth open, eyes wide towards the door.",
  "[Speech] a young woman gasping loudly.")


# ─────────────────────────────── armado ──────────────────────────────────────
DIALOGO = {boca: (t0, t1, en) for (_q, t0, t1, boca, _es, en) in LINEAS if boca}

# Habla neta de cada línea en el original: la suma de sus palabras según
# Whisper, sin las pausas. Es la ventana de la boca (ISOCRONIA.md); el tramo
# t0-t1 incluye los silencios de «Bien… ahora gime para mí».
_WHISPER = json.loads((AQUI / "../../referencias/danza-peligrosa/transcripcion.json")
                      .read_text(encoding="utf-8"))
_PALABRAS = [w for s in _WHISPER["segments"] for w in s["words"]]


def habla_neta(t0, t1):
    dentro = [w for w in _PALABRAS if t0 - 0.05 <= w["start"] < t1]
    return round(sum(w["end"] - w["start"] for w in dentro), 2) or round(t1 - t0, 2)


def onset(k):
    return ONSETS_MEDIDOS.get(k, ONSETS.get(k, ONSET))


def refs_de(loc, pers):
    """Ids sin ruta: `construir` les pone `assets/…png` y `validar` los cruza
    contra `madre`."""
    out = [LOCACIONES[loc]["imagen"]] if loc else []
    for n in pers:
        h = PERSONAJES[n]["hoja"]
        if h not in out:
            out.append(h)
    return out


def planos():
    grupos = {}
    for t in TOMAS:
        grupos.setdefault(t[6], []).append(t)
    faltan = set(grupos) - set(E)
    if faltan:
        raise SystemExit(f"encuadres sin escribir: {sorted(faltan)}")

    usas = {}
    for k, tomas in grupos.items():
        if k in DIALOGO:
            t0, t1, _en = DIALOGO[k]
            on = onset(k)
            fin_voz = on + (t1 - t0)
            ocupado = 0.0
            for t in tomas:              # primero las alineadas con la voz
                ini = on + (t[1] - t0)
                dur = t[2] - t[1]
                # Con los arranques medidos (15/9) H3 habló tarde en varios
                # clips: si el tramo se pasa del techo por poco, se corre hasta
                # el techo en vez de mandar la toma detrás de la voz. montar.py
                # ubica la voz según esta ventana real, así la boca no se desfasa.
                if -0.6 <= ini and ini + dur <= TECHO + 0.6:
                    ini = max(0.0, min(ini, TECHO - dur))
                    usas[t[0]] = ini
                    ocupado = max(ocupado, ini + dur)
            for t in tomas:              # después las mudas, detrás de la voz
                if t[0] not in usas:
                    ini = max(0.0, min(max(fin_voz + 0.2, ocupado), TECHO - (t[2] - t[1])))
                    usas[t[0]] = ini
                    ocupado = ini + (t[2] - t[1])
        else:
            base, ocupado = tomas[0][1], 0.0
            for t in tomas:
                real = t[1] - base
                ini = real if real >= ocupado and real + (t[2] - t[1]) <= TECHO else ocupado
                usas[t[0]] = ini
                ocupado = ini + (t[2] - t[1])

    out, fuente = [], {}
    placas = {round(a, 2): txt for a, _b, txt in PLACAS}
    for (tid, a, b, tipo, loc, pers, k, que_es) in TOMAS:
        corta = round(b - a, 2)
        ini = round(usas[tid], 2)
        fin = round(ini + corta, 2)
        if fin > TECHO + 0.005:
            raise SystemExit(f"toma {tid}: usa {ini}-{fin} se pasa del techo {TECHO} en {k}")
        pl = {"id": f"T{tid}", "tipo": tipo, "corta": corta, "loc": loc,
              "funcion": f"toma {tid} del original · {a:.2f}→{b:.2f} s · {k} · {que_es}",
              "usa": [ini, fin]}
        if round(a, 2) in placas:
            pl["texto"] = placas[round(a, 2)]
        if k in fuente:
            pl.update({"clip_de": fuente[k], "personajes": list(pers),
                       "ve": "(reusa el clip)", "mueve": "(reusa el clip)"})
        else:
            ve, mueve, audio = E[k]
            ve = ve + REFUERZO.get(tipo, "")
            if "over the shoulder" in ve.lower() or "from behind" in ve.lower():
                ve += ESPALDA
            if loc == "pasillo" and tipo in ("PG", "PA", "PM"):
                ve += HOLANDES
            if loc == "campo":
                ve += LUZ_CAMPO
            if k in CERRAR:
                ve += REFUERZO_CERRADO
            refs = refs_de(loc, pers)
            if refs:
                nombres = ", ".join(refs)
                ve = (f"Reference images, in this order: {nombres}. The location image sets the "
                      f"set and light; the character sheets set faces, hair and clothes exactly. "
                      + ve)
            ve = f"{ve} {LIENZO}"
            pl.update({"segundos": SEGUNDOS, "ve": ve, "mueve": mueve, "audio": audio,
                       "refs": refs})
            if k in DIALOGO:
                quien = next(q for (q, t0, _t1, boca, _es, _en) in LINEAS if boca == k)
                habla = next(n for n in pers if n.startswith(quien) or quien == n)
                pl["personajes"] = [habla]
                pl["dialogo"] = DIALOGO[k][2]
                pl["audio"] = (f"VOICE of {quien.capitalize()}, identical in every shot: "
                               f"{VOCES[quien]}. " + audio)
                voz = AQUI / "assets" / f"voz_{quien}.wav"
                if voz.exists():
                    # Ya hay voz elegida en el casting: Ref2VA con primer
                    # fotograma + hoja del que habla + esa voz como timbre.
                    pl.update({"modo": "ref2va", "voz_ref": voz.name,
                               "refs_extra": [f"{PERSONAJES[habla]['hoja']}.png"],
                               "prompt_h3": oficial.prompt_ref2va(
                                   sys.modules[__name__], k, tipo, loc, pers, quien,
                                   DIALOGO[k][2], PERSONAJES)})
                else:
                    pl["prompt_h3"] = oficial.prompt_i2va(sys.modules[__name__], k, tipo, loc,
                                                          pers, habla=(quien, DIALOGO[k][2]))
                # La ventana es la del original, no la de esta toma: muchas
                # líneas cruzan dos o tres tomas (la 49 empieza en una y
                # termina dos después).
                pl["ventana_dialogo"] = habla_neta(DIALOGO[k][0], DIALOGO[k][1])
            else:
                pl["personajes"] = list(pers)
                pl["prompt_h3"] = oficial.prompt_i2va(sys.modules[__name__], k, tipo, loc, pers)
            fuente[k] = pl["id"]
        out.append(pl)
    return out


BLOQUES = [
    ("PASADO", "El pasado: la granja y el calentamiento", "01", "14b"),
    ("VIBORA", "Entra la Víbora y cierra la puerta", "15", "28"),
    ("MATONES", "Los matones en el pasillo", "29", "37"),
    ("CUCHILLO", "La levanta y el cuchillo", "38", "57"),
    ("RECOMPENSA", "Luka pone precio a la cabeza", "58", "69"),
    ("PATADA", "El tirante, la patada y la cara", "70", "81"),
]


def estructura(pl):
    ids = [p["id"][1:] for p in pl]
    ini, t = {}, 0.0
    for p in pl:
        ini[p["id"][1:]] = t
        t += p["corta"]
    tramos = []
    for i, (bid, nombre, na, nb) in enumerate(BLOQUES):
        dentro = pl[ids.index(na): ids.index(nb) + 1]
        cortes = [x["corta"] for x in dentro]
        desde = ini[na] - (0.15 if i else 0.0)
        hasta = (ini[BLOQUES[i + 1][2]] - 0.15) if i + 1 < len(BLOQUES) else t
        tramos.append({"id": bid, "nombre": nombre, "desde": round(desde, 2),
                       "hasta": round(hasta, 2),
                       "objetivo": f"Reproducir las tomas {na}-{nb} del original con su duración exacta.",
                       "corte_min": round(min(cortes) - 0.05, 2),
                       "corte_max": round(max(cortes) + 0.05, 2),
                       "planos_min": len(dentro)})
    return {"nombre": "replica-danza-peligrosa-ep1", "formato": "short",
            "duracion_objetivo": round(t, 2), "tolerancia": 0.1, "plataformas": ["competencia"],
            "interrupcion_cada": 0,
            "notas": ["NO ES UNA LEY DE GÉNERO: es el timing medido del original, escrito como "
                      "estructura para que `construir` verifique que la réplica lo reproduce."],
            "tramos": tramos}


def _encuadre_info(k):
    """(id de la primera toma, tipo, loc, personajes) de un encuadre."""
    t = next(t for t in TOMAS if t[6] == k)
    return t[0], t[3], t[4], t[5]


def muestra(etapa):
    """La muestra que decide la configuración ANTES de generar los 73 (plan en
    models/MiniMax-H3/docs-extra/PLAN-H3-AL-MAXIMO.md §5). Usa los dibujos ya
    hechos (`dibujo`) y escribe muestra-A.json / muestra-B.json al lado del
    proyecto, así empaquetar encuentra los assets.

    A (sin voces todavía): formato viejo vs oficial vs 20 pasos, y el casting de
      las cuatro voces con dos semillas cada una.
    B (con assets/voz_<quien>.wav ya elegidas): Ref2VA con voz de referencia,
      con y sin ancla del primer fotograma, turbo vs 20 pasos, y la voz en off.
    """
    me = sys.modules[__name__]
    base_prompts = {p["id"]: p for p in planos()}
    out = []

    def plano(pid, k, **extra):
        tid, tipo, loc, pers = _encuadre_info(k)
        src = base_prompts[f"T{tid}"]
        pl = {"id": pid, "tipo": tipo, "loc": loc, "personajes": [src["personajes"][0]]
              if src["personajes"] else [], "corta": 5.0, "segundos": SEGUNDOS,
              "usa": [0.0, 5.0], "dibujo": f"sb_T{tid}.png", "ve": src["ve"],
              "mueve": src["mueve"], "audio": src["audio"],
              "funcion": f"muestra {etapa} · {k} (toma {tid}) · {extra.pop('nota', '')}"}
        pl.update(extra)
        out.append(pl)

    if etapa == "VO":
        # La narración de Hannah (0-30 s del original) no tiene boca en cuadro:
        # no entra en los 73. Se genera aparte, en tramos que caben en un clip de
        # 5,17 s con ~1 s de silencio al principio (≤ ~55 caracteres), sobre
        # insertos; del clip se usa sólo el audio. Se corta en las comas de la
        # frase original para que la entonación de cada tramo quede natural.
        tramos = [
            ("E02", "Before my mother died, she arranged my marriage to Elliott Hargrove."),
            ("E03", "To secure my future as a dancer with the Hargrove Ballet Company."),
            ("E07", "Against her wishes, my father and stepmother"),
            ("E09", "shipped me off to a farm in Indiana."),
            ("E07", "But I never stopped training, waiting to marry Elliott"),
            ("E09", "and finally live the dream they stole from me."),
            ("E13", "Dad wants me in New York to break off my engagement."),
            ("E13", "But I won't let him ruin my dreams again."),
        ]
        for n, (k, frase) in enumerate(tramos, start=1):
            tid, tipo, loc, pers = _encuadre_info(k)
            plano(f"VO{n:02d}", k, modo="ref2va", voz_ref="voz_hannah.wav",
                  refs_extra=["m_hannah.png"],
                  prompt_h3=oficial.prompt_voz_off(me, k, tipo, loc, pers, frase),
                  nota=f"VOZ EN OFF tramo {n}: «{frase}»")
    elif etapa == "A":
        tid, tipo, loc, pers = _encuadre_info("E47")
        linea = DIALOGO["E47"][2]
        # M1: el formato viejo (texto libre) con la configuración nueva de turbo.
        plano("MA01", "E47", dialogo=linea, nota="formato VIEJO, turbo 8 pasos shift 6")
        plano("MA02", "E47", prompt_h3=oficial.prompt_i2va(me, "E47", tipo, loc, pers,
                                                         habla=("jack", linea)),
              nota="formato OFICIAL, turbo 8 pasos shift 6")
        plano("MA03", "E47", prompt_h3=out[-1]["prompt_h3"], turbo=0, pasos=20,
              nota="formato OFICIAL, SIN turbo, 20 pasos")
        n = 4
        for quien, (k, frase) in oficial.CASTING.items():
            tid, tipo, loc, pers = _encuadre_info(k)
            for semilla in (101, 202):
                plano(f"MA{n:02d}", k, seed=semilla,
                      prompt_h3=oficial.prompt_i2va(me, k, tipo, loc, pers, habla=(quien, frase)),
                      nota=f"CASTING {quien} semilla {semilla}: «{frase}»")
                n += 1
    else:
        faltan = [q for q in ("jack", "hannah", "luka", "wady")
                  if not (AQUI / "assets" / f"voz_{q}.wav").exists()]
        if faltan:
            raise SystemExit(f"falta elegir la voz de: {', '.join(faltan)} "
                             f"(assets/voz_<quien>.wav, con h3pipeline.voz_ref)")

        def ref(pid, k, **extra):
            tid, tipo, loc, pers = _encuadre_info(k)
            quien = next(q for (q, _t0, _t1, boca, _es, _en) in LINEAS if boca == k)
            habla = next(n for n in pers if n.startswith(quien))
            plano(pid, k, modo="ref2va", voz_ref=f"voz_{quien}.wav",
                  refs_extra=[f"{PERSONAJES[habla]['hoja']}.png"],
                  prompt_h3=oficial.prompt_ref2va(me, k, tipo, loc, pers, quien,
                                                  DIALOGO[k][2], PERSONAJES), **extra)

        ref("MB01", "E49", nota="Ref2VA voz Jack, turbo")
        ref("MB02", "E55", nota="Ref2VA voz Jack, turbo (¿la misma voz que MB01?)")
        ref("MB03", "E55", turbo=0, pasos=20, nota="Ref2VA voz Jack, SIN turbo 20 pasos beta")
        ref("MB04", "E49", guia0=True, nota="Ref2VA voz Jack, turbo + ANCLA cuadro 0")
        ref("MB05", "E52", nota="Ref2VA voz Hannah, turbo")
        ref("MB06", "E30", nota="Ref2VA voz Luka, turbo")
        ref("MB07", "E64", nota="Ref2VA voz Wady, turbo")
        tid, tipo, loc, pers = _encuadre_info("E09")
        plano("MB08", "E09", modo="ref2va", voz_ref="voz_hannah.wav", refs_extra=["m_hannah.png"],
              prompt_h3=oficial.prompt_voz_off(
                  me, "E09", tipo, loc, pers,
                  "Before my mother died, she arranged my marriage to Elliott Hargrove."),
              nota="VOZ EN OFF de Hannah sobre un inserto, Ref2VA")

    total = round(sum(p["corta"] for p in out), 2)
    doc = {
        "titulo": f"MUESTRA {etapa} REPLICA DANZA", "slug": f"replica-danza-muestra-{etapa.lower()}",
        "formato": "short", "idioma": "en",
        "estructura": {"nombre": f"muestra-{etapa}", "formato": "short",
                       "duracion_objetivo": total, "tolerancia": 1, "plataformas": ["prueba"],
                       "interrupcion_cada": 0,
                       "tramos": [{"id": "MUESTRA", "nombre": "muestra", "desde": 0,
                                   "hasta": total, "objetivo": "comparar configuraciones",
                                   "corte_min": 4.9, "corte_max": 5.1,
                                   "planos_min": len(out)}]},
        "estilo_imagen": ESTILO_IMAGEN, "estilo_video": ESTILO_VIDEO,
        "cierre_video": CIERRE_VIDEO, "solo_sonidos": SOLO_SONIDOS,
        "personajes": PERSONAJES, "locaciones": LOCACIONES,
        "planos": out,
    }
    ruta = AQUI / f"muestra-{etapa}.json"
    ruta.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{ruta.name} · {len(out)} clips · {sum(1 for p in out if p.get('modo') == 'ref2va')} "
          f"Ref2VA")


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--muestra":
        return muestra(sys.argv[2].upper())
    pl = planos()
    total = sum(p["corta"] for p in pl)
    assert abs(total - DURACION) < 0.02, total
    doc = {
        "titulo": "REPLICA DANZA PELIGROSA EP1",
        "slug": "replica-danza",
        "formato": "short",
        "idioma": "en",
        "_concepto": ("Competencia (14/9/2026): réplica toma por toma, con MiniMax H3, del episodio 1 "
                      "de «El amor es una danza peligrosa» de ReelShort, hecho con Kling. Mismas "
                      "tomas y tiempos medidos; voces en inglés de ElevenLabs sobre la música y los "
                      "efectos del original separados con demucs; subtítulos en castellano."),
        "_original": ("Video realshort/Episodio 1 - [doblado] El amor es una danza peligrosa.mp4 · "
                      "126,92 s · 720×1280 · 24 fps. Mapa en referencias/danza-peligrosa/MAPA.md."),
        "_desvios": ("1) La toma 14 se parte en PM + PP (5,82 s no entran en un clip de 5,17). "
                     "2) Tomas 70-78: el tirante se corta pero no hay semidesnudo. "
                     "3) Voces en inglés, no el doblaje en castellano."),
        "_avisos_aceptados": (
            "Quedan 10 avisos de `validar` a propósito. 1) T02/T03 son dos insertos seguidos: el "
            "original corta así. 2) Nueve de 'boca moviéndose sin voz': el chequeo supone una boca "
            "que ya existe y una voz que se escribe para ella. Acá H3 anima la boca CON la misma "
            "línea en inglés que después dice ElevenLabs, así que coinciden por construcción; y "
            "las líneas lentas (el susurro de Jack, «Shh», «Ah!») son lentas en el original. "
            "Alargarlas para callar el aviso rompería la fidelidad."),
        "estructura": estructura(pl),
        "estilo_imagen": ESTILO_IMAGEN,
        "estilo_video": ESTILO_VIDEO,
        "cierre_video": CIERRE_VIDEO,
        "solo_sonidos": SOLO_SONIDOS,
        "personajes": PERSONAJES,
        "locaciones": LOCACIONES,
        "madre": [{"id": i, "aspecto": "9:16", "refs": r, "prompt": pr} for i, r, pr in MADRE],
        "_lineas": [{"quien": q, "t0": t0, "t1": t1, "boca": b, "es": es, "en": en}
                    for q, t0, t1, b, es, en in LINEAS],
        "planos": pl,
    }
    (AQUI / "proyecto.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    fuentes = [p for p in pl if not p.get("clip_de")]
    print(f"proyecto.json · {len(pl)} tomas · {total:.2f} s · {len(fuentes)} clips a generar "
          f"({len(fuentes) * SEGUNDOS:.1f} s) · {sum(1 for p in fuentes if p.get('dialogo'))} con boca "
          f"· {len(MADRE)} madres nuevas")


if __name__ == "__main__":
    main()
