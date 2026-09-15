# -*- coding: utf-8 -*-
"""Arma proyecto.json de la réplica a partir del mapa medido en tomas.py.

Se genera con código y no a mano por una razón: el timing es el del original al
centésimo, y una lista de 79 planos escrita a mano se desincroniza del mapa en
la primera corrección. Acá el mapa manda y el JSON es una salida.

    python mis-videos/replica-jcfdlw/armar.py
"""
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI / "../.."))
from tomas import TOMAS, DURACION  # noqa: E402

TXT = AQUI / "../../referencias/jcfdlw/7678030150944001310.txt"
KATE = "EYBbN7OENxAX5QX56IiW"

# ───────────────────────────── el reparto, en el prompt ─────────────────────
# En formato "short" el módulo NO inyecta la descripción de los personajes en el
# prompt (eso es del formato largo): la identidad la sostienen la hoja de modelo
# como referencia y el texto de cada `ve`. Así que el vestuario va escrito acá y
# se interpola en cada plano donde aparece.
MAMA = ("Li Wen, 30, a young Chinese woman with a soft oval face, clear fair skin and "
        "large dark expressive eyes, black hair in a loose bun with strands falling "
        "around her face, a soft red lip and no other makeup")
MAMA_D = f"{MAMA}, in an ivory ribbed knit sweater"          # de día
MAMA_N = f"{MAMA}, in white silk pyjamas with dark piping"   # de noche
NENA = ("Duoduo, 5, a black bob with a blunt fringe and round cheeks, "
        "in a pale pink ruffled dress and a pink cardigan")
NENA_M = f"{NENA}, wearing a bright pink school backpack"
VEND = ("the shop assistant, 28, black hair in a low bun, a black blazer over a "
        "white shirt, a company lanyard with an ID card")

ESTILO_IMAGEN = (
    "Photorealistic contemporary Chinese urban melodrama, the look of a streaming "
    "short-drama series: modern flats in a southern Chinese city, clean warm interiors "
    "in pink-beige and ivory, big soft daylight through sheer curtains, shallow depth of "
    "field, faces sharp and everything behind them dissolved. Natural skin, no glamour "
    "retouching, restrained and believable performances. Shot on a full-frame digital "
    "cinema camera, 50mm and 85mm, gentle contrast, a trace of grain.")

ESTILO_VIDEO = (
    "Photorealistic contemporary Chinese urban melodrama, vertical 9:16, the look of a "
    "streaming short-drama series. Restrained, natural movement; the camera barely moves.")

CIERRE_VIDEO = (
    "Keep the framing of the first frame. Photographic and cinematic, shallow depth of "
    "field, natural skin. Not animated, not illustrated, not CGI-looking, not a video game. "
    # Medido en la primera corrida: con estilo «drama corto chino», H3 quemó
    # subtítulos chinos en 9 de 79 clips. Se prohíbe en cada prompt de video.
    "NO subtitles, NO captions, NO on-screen text, NO watermark, NO logos of any kind.")

SOLO_SONIDOS = ("room tone, the city outside the window, cloth, water and the small "
                "sounds of a flat")

PERSONAJES = {
    "mama": {"hoja": "m_mama", "descripcion": MAMA_D},
    "duoduo": {"hoja": "m_duoduo", "descripcion": NENA},
    "vendedora": {"hoja": "m_vendedora", "descripcion": VEND},
}

LOCACIONES = {
    "azotea": {"imagen": "l_azotea",
               "descripcion": "the open laundry terrace of a city flat, drying racks, the skyline behind"},
    "colegio": {"imagen": "l_colegio",
                "descripcion": "the gate of a kindergarten on a city street"},
    "salon": {"imagen": "l_salon",
              "descripcion": "the living room of the flat, warm pink-beige, sheer curtains"},
    "auto": {"imagen": "l_auto",
             "descripcion": "the inside of a small family car with a child seat in the back"},
    "pasillo": {"imagen": "l_pasillo",
                "descripcion": "the corridor of the flat at night, doors half open"},
    "dormitorio": {"imagen": "l_dormitorio",
                   "descripcion": "the main bedroom with a huge dark-wood sliding wardrobe"},
    "bano": {"imagen": "l_bano",
             "descripcion": "the bathroom, a deep cream bathtub under a window"},
    "tienda": {"imagen": "l_tienda",
               "descripcion": "an electronics shop with glass counters and walls of accessories"},
    "cocina": {"imagen": "l_cocina",
               "descripcion": "the kitchen, a tall fridge, a window over the sink, a steel dish rack"},
    "cosmos": {"imagen": "l_cosmos",
               "descripcion": "a deep purple and blue nebula full of stars"},
}

# Los encuadres que el modelo "corrige" solo. Medido en la primera tanda: los
# planos de detalle salen abiertos (muestra la cara que el original recorta) y
# las nucas en primer término se dan vuelta hacia cámara. Se refuerza por tipo,
# no plano por plano, para que valga también para los que se rehagan.
REFUERZO_PD = (" FRAMING IS THE POINT: this is an insert of that detail and nothing else. "
               "Everything outside it is cut off by the edges of the frame, faces included. "
               "Do not open the shot out to show the whole person.")
REFUERZO_ESPALDA = (" The person closest to the camera is seen FROM BEHIND, out of focus, a "
                    "dark shape occupying part of the frame: do not turn them towards camera "
                    "and do not move them into the background.")
# La sillita infantil se le escapa del auto y aparece en un cuarto: le pasó a
# S49, S51 y S57. La locación se refuerza en todos los planos del auto.
REFUERZO_AUTO = (" This happens INSIDE THE MOVING CAR: the car interior is visible around "
                 "the subject — door card, window with the street sliding past, head rests, "
                 "seat belts, the roof lining. Never a room, never a house.")

SIN_TEXTO = ("This is a single film frame, not a poster: no text, no borders, no titles, "
             "no watermark.")

MADRE = [
    ("l_azotea", "Photorealistic cinematic photograph of the open laundry terrace of a "
     "flat in a southern Chinese city, vertical frame, late afternoon. Metal drying racks "
     "hung with white shirts, towels and underwear; a low parapet; behind it a dense "
     "skyline of pale apartment blocks and green hills, hazy. Soft overcast daylight. "
     "No people."),
    ("l_colegio", "Photorealistic cinematic photograph of the gate of a Chinese "
     "kindergarten on a city street, vertical frame, afternoon. A colourful arch over the "
     "gate with cartoon shapes, a low fence, parents waiting on the pavement, electric "
     "scooters parked along the kerb, plane trees. Warm flat daylight. Figures blurred and "
     "far away, nobody in focus."),
    ("l_salon", "Photorealistic cinematic photograph of the living room of a modern "
     "Chinese flat, vertical frame, afternoon. Pink-beige walls, a cream fabric sofa with "
     "soft toys, a round pouffe, a low wooden table, sheer white curtains glowing with "
     "daylight, a framed print. Warm, soft, slightly out of focus at the back. No people."),
    ("l_auto", "Photorealistic cinematic photograph of the inside of a small family car "
     "seen from the passenger seat, vertical frame, daytime. Grey fabric seats, a black "
     "steering wheel, a child safety seat visible in the back, seat belts, the windscreen "
     "showing a blurred tree-lined avenue. Flat daylight. No people."),
    ("l_pasillo", "Photorealistic cinematic photograph of the corridor of a flat at night, "
     "vertical frame. Dark wooden floor, two doors, one half open with a thin strip of pale "
     "light falling across the floor, a framed picture on the wall, everything else in deep "
     "shadow. Almost no light. No people."),
    ("l_dormitorio", "Photorealistic cinematic photograph of the main bedroom of a modern "
     "Chinese flat, vertical frame, dusk. A whole wall taken by a huge dark-wood sliding "
     "wardrobe, floor to ceiling, its two panels closed; a bed with pale linen at the edge "
     "of frame; a window with grey light behind sheer curtains. Cold, quiet. No people."),
    ("l_bano", "Photorealistic cinematic photograph of a bathroom in a modern Chinese "
     "flat, vertical frame, night. A deep cream bathtub under a small window, chrome taps, "
     "a large mirror, folded towels, warm tungsten light, faint steam in the air. No people."),
    ("l_tienda", "Photorealistic cinematic photograph of a small electronics shop, "
     "vertical frame. Long glass counters with cameras and gadgets under the glass, walls "
     "covered in hanging blister packs of cables and accessories, blue and white signage, "
     "cold fluorescent light. No people."),
    ("l_cocina", "Photorealistic cinematic photograph of the kitchen of a modern Chinese "
     "flat, vertical frame, daytime. A tall two-door fridge, pale cabinets, a window over "
     "the sink with daylight, a steel dish rack with white bowls stacked upside down, a "
     "kettle. Clean and quiet. No people."),
    ("l_cosmos", "Photorealistic astronomical photograph of a deep purple and blue nebula "
     "with a bright warm core low in the frame, vertical, dense with stars and dust lanes. "
     "No planets, no spaceships."),
    ("m_mama", f"Photorealistic character reference photograph, vertical frame, plain dark "
     f"grey background, even soft lighting. {MAMA_D}, from the knees up, beige trousers, "
     f"small stud earrings. She is thirty and looks it: the face of a young television "
     f"drama lead, smooth skin, no lines, but tired around the eyes. Neutral stance, "
     f"facing camera. Every detail sharp and readable: this is the reference for every "
     f"other shot."),
    ("m_duoduo", f"Photorealistic character reference photograph, vertical frame, plain "
     f"dark grey background, even soft lighting. {NENA}, standing full figure, white "
     f"tights and small white shoes, a calm open face. Neutral stance, facing camera. "
     f"Every detail sharp and readable: this is the reference for every other shot."),
    ("m_vendedora", f"Photorealistic character reference photograph, vertical frame, plain "
     f"dark grey background, even soft lighting. {VEND}, from the knees up, dark trousers, "
     f"a polite professional expression. Neutral stance, facing camera. Every detail sharp "
     f"and readable: this is the reference for every other shot."),
]

# ───────────────────────────── los 79 planos ────────────────────────────────
# (toma del mapa, sufijo, tipo, ve, mueve, audio)
# `tipo` sobreescribe el del mapa cuando el original re-encuadra dentro del
# mismo setup: es lo que evita que `validar` lea un salto de eje donde hay un
# cambio de tamaño real.
V = {}   # n -> lista de (sufijo, tipo|None, ve, mueve, audio)


def p(n, ve, mueve, audio, tipo=None, sufijo=""):
    V.setdefault(n, []).append((sufijo, tipo, ve, mueve, audio))


# ── 1-3 · el hallazgo y la salida del cole
p(1, f"WIDE-ISH SHOT on the laundry terrace, vertical frame, late afternoon. {MAMA_D} "
     f"stands at the drying rack with her back three-quarters to camera, taking down "
     f"white clothes. She holds a small piece of white underwear in both hands and looks "
     f"along the empty pegs. The hazy city behind her.",
     "She unpins one more garment, folds it against her chest, then stops and runs her "
     "eyes slowly along the rack, counting. She lifts a hanger, looks behind it, and lets "
     "her hands drop.",
     "[Ambient] a quiet high terrace, distant traffic. [Foley] plastic pegs, cloth "
     "being folded, a hanger sliding on metal.")
p(2, f"WIDE SHOT at the kindergarten gate, vertical frame, afternoon. {NENA_M} runs "
     f"towards camera down the middle of the pavement, laughing, other parents and "
     f"children blurred on both sides, the colourful arch above.",
     "She runs straight at the camera with her arms starting to open, her backpack "
     "bouncing. Behind her a parent turns to watch. The crowd drifts across the frame.",
     "[Ambient] a schoolyard emptying, children, scooters. [Foley] small running shoes "
     "on pavement.")
p(3, f"MEDIUM SHOT at the kindergarten gate, vertical frame. {MAMA_D} has just lifted "
     f"{NENA_M} onto her hip; the girl's arms are round her neck, both faces close "
     f"together, the blurred gate behind.",
     "The mother lifts her the last few centimetres and turns a quarter to the side with "
     "the movement. The girl presses her cheek against her mother's.",
     "[Ambient] the street outside a school. [Foley] cloth, a backpack strap creaking.")

# ── 4-10 · la nena cuenta lo del armario (salón)
p(4, f"WIDE SHOT of the living room, vertical frame, late afternoon. {NENA} sits on a "
     f"round pouffe holding a pale balloon; {MAMA_D} sits on the floor beside her, legs "
     f"folded, a phone face down on the rug.",
     "The girl turns the balloon in her hands and says something; the mother leans in "
     "slightly, still smiling, not yet listening properly.",
     "[Ambient] a quiet flat, faint traffic through glass. [Foley] a balloon squeaking, "
     "clothes on a rug.")
p(5, f"MEDIUM SHOT in profile of {NENA} and {MAMA_D} facing each other in the living "
     f"room, vertical frame, both in soft window light, the room dissolved behind them.",
     "The girl talks steadily, her mouth working; the mother's smile flattens by degrees "
     "as she listens, her head tilting a few centimetres to one side.",
     "[Ambient] the quiet room. [Foley] small movements of cloth.")
p(6, f"CLOSE UP of {MAMA_D} in the living room, vertical frame, warm window light on her "
     f"face. She is mid-sentence, one index finger raised; the dark back of the girl's "
     f"head is a soft shape at the left edge of frame.",
     "She talks, the raised finger moving with the rhythm of what she says, then lowers "
     "it and puts the hand flat on her own knee.",
     "[Ambient] the quiet room. [Foley] cloth, a hand settling on fabric.", tipo="PP", sufijo="a")
p(6, f"MEDIUM SHOT of {MAMA_D} in the living room, vertical frame, framed from the waist "
     f"up and filling most of the frame, sitting and talking; the back of {NENA}'s head is "
     f"a large dark out-of-focus shape in the bottom left corner.",
     "She keeps talking, more softly now, and reaches out to smooth the girl's hair, "
     "leaving her hand resting on the small head.",
     "[Ambient] the quiet room. [Foley] a hand on hair, cloth.", tipo="PM", sufijo="b")
p(7, f"CLOSE UP of {NENA_M}, vertical frame, the living room dissolved to warm colour "
     f"behind her. Her mouth is open, eyes wide and completely serious.",
     "She looks straight up at her mother and says a short sentence; her eyebrows go up "
     "at the end of it. She does not blink.",
     "[Ambient] the quiet room. [Foley] the small sounds of a child breathing.")
p(8, f"CLOSE UP of {NENA_M} in profile, vertical frame, speaking; the edge of {MAMA_D}'s "
     f"face enters the right edge of frame, out of focus.",
     "The girl talks with her chin lifted; the blurred face at the edge of frame turns "
     "towards her.",
     "[Ambient] the quiet room.")
p(9, f"MEDIUM SHOT of {MAMA_D} holding {NENA_M}, vertical frame; the girl has her back to "
     f"camera with the pink backpack still on, the mother's face visible over her shoulder.",
     "The mother rocks her once, side to side, talking over the girl's shoulder in a light "
     "voice, and her eyes go somewhere else, past the camera.",
     "[Ambient] the quiet room. [Foley] cloth, a backpack strap.")
p(10, f"CLOSE UP of {NENA_M}, vertical frame, eyes half closed, her mouth moving.",
      "She speaks with her eyes almost shut, tired, then opens them and looks up.",
      "[Ambient] the quiet room.")

# ── 11-14 · los sesenta días (a la puerta del cole)
p(11, f"WIDE-ISH SHOT at the kindergarten gate, vertical frame, afternoon. {MAMA_D} "
      f"crouches in front of {NENA_M} under the colourful arch, straightening the "
      f"backpack straps with both hands, other parents blurred behind.",
      "She pulls one strap straight, then the other, and looks up into the girl's face "
      "with a question. The girl nods once.",
      "[Ambient] the street outside a school. [Foley] backpack buckles, footsteps.")
p(12, f"MEDIUM SHOT of {NENA_M} on the pavement, vertical frame, parked scooters blurred "
      f"behind her. She is looking down at her own hands, counting on her fingers.",
      "She folds down one finger at a time, lips moving with the count, absolutely "
      "absorbed; a scooter passes behind her, out of focus.",
      "[Ambient] a busy pavement, a scooter passing. [Foley] nothing but the traffic.",
      tipo="PM")
p(13, f"EXTREME CLOSE UP of {NENA_M}'s face on the pavement, vertical frame, eyes and "
      f"mouth filling the frame. She lifts her eyes from her fingers straight up at her "
      f"mother.",
      "Her hands stop below the frame. She raises her chin and says two words, flat and "
      "certain.",
      "[Ambient] a busy pavement.", tipo="PD")
p(14, f"MEDIUM SHOT of {MAMA_D}, alone, standing still on the pavement outside the "
      f"school, vertical frame, framed from the waist up and filling the centre of the "
      f"frame, the street blurred behind her. Her face has stopped: eyes wide, mouth "
      f"slightly open, not breathing.",
      "She does not move. Only her eyes shift a few millimetres, doing a sum. A bus "
      "passes far behind her, out of focus.",
      "[Ambient] a busy street, a bus. [Foley] nothing near.", tipo="PM", sufijo="a")
p(14, f"CLOSE UP of {MAMA_D} on the pavement, vertical frame, tighter on her face, the "
      f"street a wash of colour behind her.",
      "Her eyes fill without her face moving at all. She swallows once, and her jaw sets.",
      "[Ambient] a busy street.", tipo="PP", sufijo="b")

# ── 15-20 · el auto, primera vuelta
p(15, f"DETAIL SHOT inside the car, vertical frame, daytime. {MAMA_D}'s hand on the black "
      f"steering wheel and her torso with the seat belt across it; her face is cut off "
      f"above the frame.",
      "The hand tightens on the wheel until the knuckles go pale, then loosens. The "
      "windscreen light moves across the sleeve.",
      "[Ambient] a car interior at speed, tyres, muffled traffic.")
p(16, f"MEDIUM SHOT of {MAMA_D} driving, vertical frame, seen in profile from the "
      f"passenger side, the blurred avenue running past the window behind her.",
      "She glances at the rear-view mirror, then back at the road, then at the mirror "
      "again, quicker.",
      "[Ambient] a car interior, indicator ticking once.")
p(17, f"CLOSE UP of {MAMA_D} driving in profile, vertical frame, the street outside the "
      f"window completely out of focus behind her cheek.",
      "She talks to herself under her breath, barely moving her lips, eyes fixed forward.",
      "[Ambient] a car interior at speed.")
p(18, f"DETAIL SHOT inside the car, vertical frame: the hand gripping the wheel and the "
      f"seat belt crossing the ivory sweater, low angle.",
      "The fingers open and close once on the wheel; the belt shifts as she breathes in.",
      "[Ambient] a car interior, a turn signal.")
p(19, f"MEDIUM SHOT of {MAMA_D} driving, three-quarters towards camera, vertical frame, "
      f"her shoulders and the head rest in frame, looking straight ahead at the road.",
      "Her eyes move from the road down to nothing and back up. She blinks hard, twice.",
      "[Ambient] a car interior at speed.", tipo="PM")
p(20, f"CLOSE UP of {MAMA_D} from in front, through the top of the steering wheel, "
      f"vertical frame, the windscreen glare behind her. Her eyes are enormous, her face "
      f"coming apart.",
      "Her mouth opens slightly. Her eyes go wet and she does not wipe them; she keeps "
      "driving, staring forward.",
      "[Ambient] a car interior at speed. [Foley] a single unsteady breath.")

# ── 21-25 · el pasillo y el armario
p(21, f"WIDE SHOT down the dark corridor of the flat at night, vertical frame. {MAMA_D} "
      f"stands with her back to camera in front of the bedroom door, small in the frame, "
      f"a kitchen knife hanging point-down in her right hand.",
      "She stands still, then takes one step towards the door. The blade catches the "
      "little light there is.",
      "[Ambient] a flat at night, a fridge humming far away. [Foley] one bare footstep on "
      "wood.")
p(22, f"MEDIUM-WIDE SHOT from behind {MAMA_D}, vertical frame: the back of her head and "
      f"shoulders silhouetted against the closed dark-wood sliding wardrobe that fills the "
      f"whole wall in front of her.",
      "She stands in front of the wardrobe without moving, her shoulders rising and "
      "falling once, twice.",
      "[Ambient] a bedroom at night, absolute quiet. [Foley] breathing.", tipo="PA")
p(23, f"CLOSE SHOT from behind {MAMA_D}, vertical frame, tighter: the back of her neck "
      f"and her hand rising towards the recessed handle of the wardrobe panel.",
      "Her hand comes up slowly and stops a few centimetres from the handle, fingers "
      "spread, and hangs there.",
      "[Ambient] a bedroom at night. [Foley] cloth, breathing.", tipo="PM")
p(24, f"MEDIUM-WIDE SHOT of {MAMA_D} standing in the bedroom in profile, vertical frame, "
      f"looking at the wardrobe; the window behind her with grey night light through "
      f"sheer curtains.",
      "She lowers the hand and turns her head away from the wardrobe, then back to it, "
      "arguing with herself.",
      "[Ambient] a bedroom at night, a distant car.", tipo="PA")
p(25, f"MEDIUM SHOT of {MAMA_D} in the bedroom, vertical frame, half turned to camera. "
      f"She pushes her hand up through her hair at the temple and laughs at herself, an "
      f"embarrassed, relieved laugh.",
      "She rubs her forehead, shakes her head, breathes out through her nose and half "
      "laughs, and lets her shoulders drop.",
      "[Ambient] a bedroom at night. [Foley] a short breath of laughter.")

# ── 26-35 · el baño
p(26, f"WIDE SHOT of the bathroom at night, vertical frame. {NENA} sits in the deep tub "
      f"among foam with a yellow rubber duck; {MAMA_N} sits on the rim beside her, one "
      f"hand washing the girl's hair, warm light.",
      "The mother works shampoo into the small head with both hands; the girl tips her "
      "chin up and says something. Foam slides down.",
      "[Ambient] a bathroom, water. [Foley] hands in wet hair, foam, small splashes.")
p(27, f"MEDIUM SHOT of {MAMA_N} crouched beside the tub, vertical frame, reaching across "
      f"the water for the yellow duck; the girl out of focus at the edge.",
      "She stretches, catches the duck, and holds it up in front of the girl, playing.",
      "[Ambient] a bathroom. [Foley] water, plastic on water.")
p(28, f"CLOSE UP of {NENA} in the bath, vertical frame, wet hair flat on her forehead, "
      f"the yellow duck held in both hands at her chest; her mother's hand at the edge of "
      f"frame in her hair.",
      "She turns the duck over in her hands and talks down at it instead of at her "
      "mother, her mouth pulled to one side.",
      "[Ambient] a bathroom. [Foley] water dripping, plastic squeaking.")
p(29, f"WIDE SHOT of the bathroom from the other side, vertical frame: the chrome taps "
      f"large in the foreground, {NENA} small in the tub beyond them, foam everywhere.",
      "The girl pushes the duck under the foam and lets it pop back up, talking the whole "
      "time.",
      "[Ambient] a bathroom. [Foley] splashing, foam.")
p(30, f"CLOSE UP of {MAMA_N} kneeling by the tub, vertical frame, framed from the "
      f"shoulders up with her face filling most of the frame. Her eyes are very wide and "
      f"completely still; the warm bathroom light behind her, the room out of focus.",
      "Everything stops in her face. She does not blink for a long moment, then her "
      "eyelids come down slowly, once.",
      "[Ambient] a bathroom, water settling.")
p(31, f"MEDIUM SHOT of {NENA} in the bath, vertical frame, holding the duck up, mouth "
      f"open, telling something important.",
      "She lifts the duck as she talks and shakes it for emphasis; water runs off it into "
      "the bath.",
      "[Ambient] a bathroom. [Foley] water, plastic.")
p(32, f"CLOSE UP of {MAMA_N}, vertical frame, looking down and away from the tub, her "
      f"mouth slightly open.",
      "Her gaze drops to the water. Her lips move once without any sound.",
      "[Ambient] a bathroom.")
p(33, f"MEDIUM SHOT of {NENA} in the bath looking up, vertical frame, her mother's hands "
      f"rinsing her hair from above the frame.",
      "Water pours over the small head; the girl squeezes her eyes shut and then opens "
      "them, looking up.",
      "[Ambient] a bathroom. [Foley] a jug of water poured over hair.")
p(34, f"MEDIUM SHOT of {MAMA_N} leaning over the tub, vertical frame, close to the camera "
      f"and framed from the waist up, smiling at the girl with a smile that is being held "
      f"in place on purpose. The bathroom is out of focus behind her.",
      "She smiles and nods at whatever is being said, and her free hand grips the rim of "
      "the tub out of the child's sight.",
      "[Ambient] a bathroom. [Foley] a hand tightening on porcelain.")
p(35, f"CLOSE UP of {MAMA_N}, vertical frame, very tight; her eyes down, the smile gone "
      f"now, warm light on one side of her face.",
      "The smile leaves her face entirely, from the eyes down. She breathes in through "
      "her nose and holds it.",
      "[Ambient] a bathroom, water dripping.")

# ── 36-42 · el celular y el pasillo
p(36, f"CLOSE UP of {MAMA_N} at night, vertical frame, her face lit blue from below by a "
      f"phone screen, the dark living room behind her.",
      "Her eyes move across the screen, line by line, and stop.",
      "[Ambient] a flat at night, deep quiet.", )
p(37, f"DETAIL SHOT of a phone held in two hands, vertical frame, filling most of the "
      f"frame: a messaging app open on a photograph of the Shanghai skyline at night, lit "
      f"towers over black water, with a short message under it.",
      "The thumb scrolls the message up a few centimetres and stops on the photograph. "
      "The screen light flickers on the fingers.",
      "[Ambient] a flat at night. [Foley] a thumb on glass.")
p(38, f"CLOSE SHOT of the hand and forearm holding the phone, vertical frame, the screen "
      f"showing a grid "
      f"of posts with small photographs and the same location label repeated under each "
      f"one.",
      "The thumb drags the grid upwards, post after post, faster, and then stops dead.",
      "[Ambient] a flat at night. [Foley] a thumb dragging on glass.", tipo="PP")
p(39, f"MEDIUM SHOT of {MAMA_N} sitting on the sofa in the dark living room, vertical "
      f"frame, the phone in both hands, her face and chest lit blue, everything else black.",
      "She lowers the phone into her lap and looks up into the dark room, towards the "
      "corridor.",
      "[Ambient] a flat at night, a clock. [Foley] cloth on a sofa.")
p(40, f"WIDE SHOT of the corridor at night, vertical frame, empty: a door standing half "
      f"open with a thin strip of pale light across the floorboards.",
      "Nothing moves. The strip of light shifts a few millimetres, as if the door had "
      "been touched.",
      "[Ambient] a flat at night. [Foley] a floorboard settling.")
p(41, f"WIDE-ISH SHOT of {MAMA_N} ALONE in the dark corridor, vertical frame, seen from "
      f"behind as she walks away from the camera: only her back, her bun and her shoulders "
      f"are visible, never her face. The lit phone hangs in one hand and throws light on "
      f"the wall. Nobody else is in the corridor.",
      "She walks slowly, one hand trailing along the wall, and stops at the bedroom door.",
      "[Ambient] a flat at night. [Foley] bare feet on wood, cloth.")
p(42, f"MEDIUM SHOT of {MAMA_N} in profile at the bedroom door, vertical frame, one hand "
      f"on the handle, the lit phone in the other, her chin down.",
      "Her hand closes on the handle and stays there. Her breathing goes shallow and she "
      "does not push.",
      "[Ambient] a flat at night. [Foley] a hand on a metal handle, breathing.")

# ── 43-47 · la mañana siguiente
p(43, f"MEDIUM SHOT of {NENA} kneeling up on the sofa in daylight, vertical frame, "
      f"talking towards camera; the back of {MAMA_N}'s head and shoulder in the near "
      f"foreground, out of focus.",
      "The girl leans forward and puts a small hand on her mother's arm, peering into her "
      "face.",
      "[Ambient] a flat in the morning, birds outside. [Foley] cloth on a sofa.")
p(44, f"MEDIUM SHOT of {MAMA_N} in the morning living room, vertical frame, smiling with "
      f"dark circles under her eyes; the back of the girl's head in the foreground.",
      "She smiles and waves it away with one hand, then rubs her eye with the back of her "
      "wrist.",
      "[Ambient] a flat in the morning.")
p(45, f"MEDIUM SHOT of {NENA} on the sofa, vertical frame, both hands on her mother's "
      f"knees, asking something.",
      "She shakes her mother's knees gently, insisting, her head tipped to one side.",
      "[Ambient] a flat in the morning. [Foley] small hands on cloth.")
p(46, f"MEDIUM SHOT of {MAMA_N} on the sofa, vertical frame, one finger raised, telling a "
      f"story with mock seriousness.",
      "She raises the finger, draws a small shape in the air with it, and widens her eyes "
      "to make the girl laugh.",
      "[Ambient] a flat in the morning.")
p(47, f"CLOSE UP of {MAMA_N} on the sofa, vertical frame, laughing with both hands "
      f"over her mouth, framed alone.",
      "She laughs behind her hands, and the laugh keeps going a beat longer than it "
      "should, and her eyes stay flat.",
      "[Ambient] a flat in the morning. [Foley] a laugh into cupped hands.", tipo="PP")

# ── 48-59 · el interrogatorio en el auto
def auto_mama(ve_extra, mueve, audio, tipo="PM"):
    return (f"MEDIUM SHOT of {MAMA_D} driving, vertical frame, seen from the passenger "
            f"seat, the blurred avenue through the windscreen. {ve_extra}", mueve, audio, tipo)


p(48, *auto_mama("She is talking towards the back seat without turning her head.",
                 "She talks over her shoulder to the child seat behind, then checks the "
                 "rear-view mirror.",
                 "[Ambient] a car at speed, indicator."))
p(49, f"MEDIUM SHOT of {NENA} strapped into the child seat, vertical frame, a white plush "
      f"rabbit in her arms, the car window behind her.",
      "She talks to the rabbit's ears while she answers, pulling one of them straight.",
      "[Ambient] a car at speed. [Foley] a seat belt, plush fabric.")
p(50, *auto_mama("Her eyes are locked on the road; she asks a short question.",
                 "She asks without turning, and her hands adjust on the wheel.",
                 "[Ambient] a car at speed."))
p(51, f"MEDIUM SHOT of {NENA} in the child seat hugging the rabbit, vertical frame, "
      f"answering brightly.",
      "She squeezes the rabbit against her chest and nods twice as she answers.",
      "[Ambient] a car at speed. [Foley] plush fabric.")
p(52, f"CLOSE UP of {MAMA_D} in the car, vertical frame, very tight on her face in "
      f"profile, jaw locked.",
      "Her jaw tightens visibly. She does not look away from the road.",
      "[Ambient] a car at speed.", tipo="PP")
p(53, *auto_mama("One arm is stretched out to the wheel; she is asking a longer question "
                 "towards the mirror.",
                 "She talks to the rear-view mirror, watching the child's face in it "
                 "instead of the road.",
                 "[Ambient] a car at speed."))
p(54, f"MEDIUM SHOT of {NENA} in the child seat looking down, vertical frame, playing "
      f"with the rabbit's ears while she answers.",
      "She folds the rabbit's ears over its eyes, bored, and answers without looking up.",
      "[Ambient] a car at speed. [Foley] plush fabric.")
p(55, f"CLOSE UP of {NENA} in the child seat, vertical frame, lifting her face towards "
      f"the mirror, suddenly remembering something.",
      "She lifts her chin, her eyes widen a little, and she adds one more thing.",
      "[Ambient] a car at speed.", tipo="PP")
p(56, *auto_mama("She turns her head a few degrees, in profile, asking who.",
                 "Her head turns just enough to break the profile, and comes back.",
                 "[Ambient] a car at speed."))
p(57, f"MEDIUM SHOT of {NENA} in the child seat, vertical frame, shrugging with the "
      f"rabbit held against her.",
      "She shrugs with both shoulders, pulls a face, and shakes her head.",
      "[Ambient] a car at speed. [Foley] a seat belt.")
p(58, f"DETAIL SHOT of the rear-view mirror, vertical frame: {MAMA_D}'s eyes reflected in "
      f"it, the road behind out of focus and reflected upside down at the edges.",
      "The reflected eyes move from the mirror to the road and back. Traffic lights slide "
      "past out of focus.",
      "[Ambient] a car at a junction, an indicator.")
# Dos veces salió con ella asomada por la ventanilla desde ese dibujo. Se
# reencuadra como el S20, que salió perfecto: frontal a través del volante.
p(59, f"CLOSE UP of {MAMA_D} from in front, through the top of the steering wheel, "
      f"vertical frame, seated at the wheel INSIDE the car, the windscreen glare and the "
      f"blurred avenue behind her. Her face has settled and she is counting two things "
      f"out loud.",
      "She counts two things; with the second one her chin comes up and her hands close "
      "on the wheel. She stays seated, facing forward, driving.",
      "[Ambient] a car at speed.", tipo="PP")

# ── 60-69 · la cámara
p(60, f"MEDIUM SHOT of {MAMA_D} leaning over the glass counter of an electronics shop, "
      f"vertical frame, cold fluorescent light, walls of accessories behind her.",
      "She leans in over the glass and asks for something, tapping the counter twice with "
      "one finger.",
      "[Ambient] a small shop, fluorescent hum, distant chatter. [Foley] a fingertip on "
      "glass.")
p(61, f"WIDE-ISH SHOT of {MAMA_D} at the shop counter, vertical frame, the aisle and the "
      f"racks of packaged accessories visible around her.",
      "She holds her thumb and finger apart to show a size, then makes the gap smaller, "
      "and smaller again.",
      "[Ambient] a small shop. [Foley] nothing near.", tipo="PA")
p(62, f"MEDIUM SHOT of {VEND} behind the glass counter, vertical frame, bending to slide "
      f"open the back of the display case.",
      "She slides the case open and reaches in among the boxes.",
      "[Ambient] a small shop. [Foley] a glass door sliding, boxes.")
p(63, f"CLOSE UP of {VEND} behind the counter, vertical frame, holding a tiny black cube "
      f"of a camera up between two fingers.",
      "She turns the little camera between her fingers so its lens catches the light, "
      "explaining.",
      "[Ambient] a small shop. [Foley] a small plastic object handled.", tipo="PP")
p(64, f"WIDE-ISH SHOT of {VEND} behind the counter, vertical frame, her arm stretched out "
      f"across the glass with a tiny black cube of a camera —no bigger than a thumbnail, "
      f"not a normal photo camera— flat on her open palm.",
      "She holds the palm out and taps the camera once with her other hand, listing what "
      "it does.",
      "[Ambient] a small shop.", tipo="PA")
p(65, f"EXTREME DETAIL SHOT, vertical frame: {MAMA_D}'s hand fills the frame, holding a "
      f"tiny black cube of a camera, no bigger than a thumbnail, between finger and thumb "
      f"against the shop's overhead light. The shop behind is a blur of blue and white; "
      f"nothing else is in focus and no other part of her is visible.",
      "She turns it over, finds the magnet on its back, and presses it against a metal "
      "edge of the counter, where it sticks.",
      "[Ambient] a small shop. [Foley] a small magnetic click.")
p(66, f"MEDIUM SHOT of {MAMA_D} leaning on the glass counter INSIDE THE ELECTRONICS "
      f"SHOP, vertical frame, the lit display case under her elbows and the wall of hanging "
      f"blister packs behind her. The little black camera is in one hand and her phone in "
      f"the other, and she compares them.",
      "She looks from the camera to the phone screen and back, then puts the camera down "
      "flat on the glass and pushes it forward.",
      "[Ambient] a small shop. [Foley] a phone on glass.")
p(67, f"CLOSE UP of {MAMA_D} in the corridor of the flat, vertical frame, warm interior "
      f"light behind her, the bedroom door out of focus. She is talking to herself, giving "
      f"herself an order.",
      "She talks herself into it: her chin lifts, she nods once, hard, and her mouth sets.",
      "[Ambient] a flat, quiet.", tipo="PP")
p(68, f"CLOSE UP, vertical frame: {MAMA_D}'s neck and chest and the orange phone held "
      f"up in one hand, her face cut off above the frame.",
      "The hand raises the phone slowly into the frame until the screen is lit.",
      "[Ambient] a flat, quiet. [Foley] cloth.", tipo="PP")
p(69, f"DETAIL SHOT of the orange phone's screen filling the frame, vertical: a live "
      f"camera view of the dim bedroom, the whole dark-wood wardrobe inside the frame, "
      f"with a small recording dot and a timestamp.",
      "The live image refreshes with a faint stutter; nothing in the room moves. The "
      "timestamp counts up.",
      "[Ambient] a flat, quiet. [Foley] a phone speaker hiss.")

# ── 70-76 · la cocina
p(70, f"MEDIUM SHOT of {MAMA_D} crouched in front of the open fridge, vertical frame, "
      f"its cold light on her face, cartons of milk on the shelf in front of her.",
      "She counts the cartons with a finger, touching each one, then goes back and counts "
      "them again.",
      "[Ambient] a kitchen, a fridge compressor. [Foley] a fridge door seal, cardboard "
      "cartons.")
p(71, f"WIDE-ISH SHOT of {MAMA_D} in profile at the open fridge door, vertical frame, "
      f"bent over the egg tray set into the door.",
      "She touches the eggs one by one, stops, straightens up an inch, and starts the "
      "count again from the beginning.",
      "[Ambient] a kitchen, a fridge compressor. [Foley] eggshell on plastic.", tipo="PA")
p(72, f"CLOSE UP of {MAMA_D} standing in front of the OPEN FRIDGE, vertical frame, the "
      f"lit shelves of the fridge filling the background right beside her and its cold "
      f"white light falling on one side of her face. Her mouth is open.",
      "Her lips move on the numbers and then stop between two of them. Her eyes go up "
      "and to the side.",
      "[Ambient] a kitchen, a fridge compressor.")
p(73, f"MEDIUM SHOT of {MAMA_D} straightening up in the kitchen, vertical frame, the open "
      f"fridge still throwing light behind her, turning her head towards the sink.",
      "She stands up out of the crouch and turns her head slowly towards the window and "
      "the dish rack.",
      "[Ambient] a kitchen. [Foley] a fridge door, a floor.")
p(74, f"EXTREME DETAIL SHOT, vertical frame, of five identical white bowls in a steel "
      f"dish rack by a window, seen from the side at bowl height, daylight raking across "
      f"them. Four of the bowls are FACE DOWN: domes of smooth white porcelain, no hollow "
      f"visible. The bowl in the centre is FACE UP: you can see straight into its empty "
      f"hollow, and there is a drop of water in it. The contrast between the four domes "
      f"and the one open bowl is the whole shot.",
      "The daylight moves a little across the rim of the one bowl that is the wrong way "
      "up. Nothing else changes.",
      "[Ambient] a kitchen, quiet. [Foley] a tap dripping once.")
p(75, f"MEDIUM SHOT of {MAMA_D} standing in the kitchen, vertical frame, holding the "
      f"single bowl in one hand, looking off to the side; a bead of sweat at her temple.",
      "She turns the bowl over in her hand, and her eyes go to the corridor without her "
      "head following.",
      "[Ambient] a kitchen. [Foley] ceramic in a hand.")
p(76, f"EXTREME DETAIL SHOT, vertical frame: a fingertip running slowly around the inside "
      f"of the white bowl, warm shallow light, everything else out of focus.",
      "The fingertip goes round the inside of the bowl once and stops, and stays there.",
      "[Ambient] a kitchen, silence. [Foley] skin on dry ceramic.")

# ── 77 · placa final
p(77, "A deep purple and blue nebula filling the ENTIRE vertical frame edge to edge, dense "
      "with stars, a warm bright core low in the frame. This is outer space seen directly: "
      "ABSOLUTELY NO PERSON, no silhouette, no face, no room, no window, no furniture, no "
      "foreground object of any kind. Only the nebula and the stars. No text.",
      "Only the starfield drifts slowly upwards and the core pulses once, very softly. "
      "Nothing and nobody enters the frame.",
      "[Ambient] a low cosmic drone.")


# ─────────────────────────────── armado ─────────────────────────────────────
def lineas_de_voz():
    out = []
    for l in TXT.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*\[\s*([0-9.]+)s\]\s*(.*)", l)
        if m and m.group(2).strip():
            out.append({"t": round(float(m.group(1)), 2), "texto": m.group(2).strip()})
    return out


def planos():
    """Los 79 planos con la duración que les da NUESTRA voz (la imagen sigue a
    la voz, ver `linea_de_tiempo.py`) y un clip generado por ENCUADRE, no por
    toma: las tomas que repiten encuadre reusan el clip de la primera
    (`clip_de`) con otro tramo (`usa`). Techo de generación 5,88 s: 6,58 falló
    4 de 5 veces en la primera corrida."""
    from h3pipeline import grilla
    from linea_de_tiempo import mapa
    f = mapa()
    GRILLA = [5.167, 5.875]          # nunca 6,58
    COLCHON = 0.30

    TECHO = GRILLA[-1] - COLCHON     # 5,575: más que esto se parte en dos
    base = []
    for n, a, b, tipo_mapa, loc, pers, _ve_es in TOMAS:
        partes = list(V[n])
        a2, b2 = f(a), f(b)
        dur = round(b2 - a2, 2)
        # Una toma que, ya estirada a nuestra voz, no entra en 5,88 con colchón
        # se parte en dos planos del mismo encuadre (el segundo, apenas más
        # cerrado para que el corte se lea como acercamiento y no como salto).
        if len(partes) == 1 and dur > TECHO:
            suf, tipo, ve, mueve, audio = partes[0]
            t0 = tipo or tipo_mapa
            mas_cerca = {"PGE": "PG", "PG": "PA", "PA": "PM", "PM": "PP", "PP": "PD"}[t0]
            extra = (" Framed much tighter than before: an extreme close-up on her eyes and "
                     "mouth, the same moment continuing." if mas_cerca == "PD" else
                     " Framed a little tighter than before, the same moment continuing.")
            partes = [("a", t0, ve, mueve, audio), ("b", mas_cerca, ve + extra, mueve, audio)]
        trozos = [round(dur / len(partes), 2) for _ in partes]
        trozos[-1] = round(dur - sum(trozos[:-1]), 2)
        for (suf, tipo, ve, mueve, audio), corta in zip(partes, trozos):
            t = tipo or tipo_mapa
            if loc == "auto":
                ve = ve + REFUERZO_AUTO
            if t == "PD":
                ve = ve + REFUERZO_PD
            if ("her back to camera" in ve
                    or ("back of" in ve and any(w in ve for w in ("head", "neck",
                                                                 "shoulder")))):
                ve = ve + REFUERZO_ESPALDA
            base.append({
                "id": f"S{n:02d}{suf}", "tipo": t, "corta": corta, "loc": loc,
                "personajes": list(pers), "n": n,
                "funcion": f"toma {n} del original · {a:.2f}→{b:.2f} s",
                "ve": ve, "mueve": mueve, "audio": audio,
            })

    # La placa final es un gráfico: no se genera, la pone el mezclador.
    for pl in base:
        if pl["n"] == 77:
            pl["clip_de"] = "PLACA"
            pl["usa"] = [0.0, pl["corta"]]

    # Empaquetado por encuadre: (locación, reparto, tamaño). Una fuente sirve
    # a las tomas siguientes del mismo encuadre mientras le quede clip.
    fuentes = {}          # clave -> dict(id, cap, usado)
    for pl in base:
        if pl.get("clip_de"):
            continue
        clave = (pl["loc"], tuple(pl["personajes"]), pl["tipo"])
        fu = fuentes.get(clave)
        if fu and fu["usado"] + pl["corta"] <= fu["cap"]:
            pl["clip_de"] = fu["id"]
            pl["usa"] = [round(fu["usado"], 2), round(fu["usado"] + pl["corta"], 2)]
            fu["usado"] = round(fu["usado"] + pl["corta"], 2)
            continue
        # Nueva fuente: larga si el encuadre vuelve y hay con qué llenarla.
        largo = 5.875 if pl["corta"] > GRILLA[0] - COLCHON or any(
            q is not pl and not q.get("clip_de") and
            (q["loc"], tuple(q["personajes"]), q["tipo"]) == clave
            for q in base) else GRILLA[0]
        if pl["corta"] > largo - COLCHON:
            raise SystemExit(f"{pl['id']}: corta {pl['corta']} no entra en {largo}")
        pl["segundos"] = largo
        pl["usa"] = [0.0, pl["corta"]]
        fuentes[clave] = {"id": pl["id"], "cap": largo - COLCHON, "usado": pl["corta"]}

    for pl in base:
        pl.pop("n", None)
    return base


def estructura(pl):
    """Los tramos son las escenas del original, con los cortes que el original
    realmente usa en cada una. No es la ley `recap` (que pide cortes de 5 a 6,1 s
    porque es la ley de nuestros videos): acá la ley es el video que se replica,
    y por eso `validar` sirve de verdad — comprueba que reprodujimos su timing."""
    bloques = [
        ("GANCHO", "La ropa que falta y la vuelta del cole", 1, 3),
        ("LA_NENA", "La nena dice que papá vive en el armario", 4, 10),
        ("SESENTA_DIAS", "Los sesenta días contados con los dedos", 11, 14),
        ("AUTO_1", "El primer viaje: la duda", 15, 20),
        ("EL_ARMARIO", "El pasillo, el cuchillo y el alivio falso", 21, 25),
        ("EL_BANO", "La misión secreta", 26, 35),
        ("EL_MOVIL", "Las publicaciones y la certeza", 36, 42),
        ("LA_MANANA", "Disimular delante de la nena", 43, 47),
        ("INTERROGATORIO", "El segundo viaje: la camisa y la corbata", 48, 59),
        ("LA_CAMARA", "La tienda y la minicámara", 60, 69),
        ("LA_COCINA", "Las cuentas que no dan", 70, 76),
        ("CIERRE", "La placa final", 77, 77),
    ]
    ini = {}
    t = 0.0
    for p_ in pl:
        n = int(p_["id"][1:3])
        ini.setdefault(n, t)
        t += p_["corta"]
    fin_total = t
    tramos = []
    # Las fronteras van 0,15 s ANTES del arranque del primer plano del bloque:
    # `validar` asigna por segundo de arranque y la línea real acumula redondeos
    # de centésimas; sin margen un plano cae en el tramo anterior (error 9 de
    # errores-de-proceso). Ningún corte mide menos de 0,5 s, así que no se
    # cambia ninguna asignación.
    MARGEN = 0.15
    for id_, nombre, na, nb in bloques:
        desde = ini[na] - (MARGEN if na > 1 else 0.0)
        hasta = (ini[nb + 1] - MARGEN) if (nb + 1) in ini else fin_total
        dentro = [x for x in pl if na <= int(x["id"][1:3]) <= nb]
        cortes = [x["corta"] for x in dentro]
        tramos.append({
            "id": id_, "nombre": nombre,
            "desde": round(desde, 2), "hasta": round(hasta, 2),
            "objetivo": f"Reproducir las tomas {na}-{nb} del original con su duración exacta.",
            "corte_min": round(min(cortes) - 0.05, 2),
            "corte_max": round(max(cortes) + 0.05, 2),
            "planos_min": len(dentro),
        })
    return {
        "nombre": "replica-jcfdlw-7678030150944001310",
        "formato": "short",
        "duracion_objetivo": round(fin_total, 2),
        "tolerancia": 0.5,
        "plataformas": ["TikTok"],
        "interrupcion_cada": 0,
        "notas": [
            "ESTO NO ES UNA LEY DE GÉNERO: es el timing medido de un video ajeno, "
            "escrito como estructura para que `construir` pueda verificar que la réplica "
            "lo reproduce. Para escribir un video propio se usa `recap`.",
            "Los cortes van de 0,50 a 3,24 s (media 2,30). Nuestra grilla no baja de "
            "5,17 s por clip, así que casi todos los planos generan de más y se usan "
            "cortos: 412 s generados para 181 s de línea.",
            "Las dos tomas de 6,47 s (la 6 y la 14) son las únicas partidas en dos planos: "
            "6,47 no entra en la grilla con colchón suficiente y 7,3 es apuesta (regla 38). "
            "Son los dos únicos cortes que la réplica agrega al original.",
        ],
        "tramos": tramos,
    }


def main():
    pl = planos()
    doc = {
        "titulo": "REPLICA JCFDLW 7678030150944001310",
        "slug": "replica-jcfdlw",
        "formato": "short",
        "_concepto": (
            "BENCHMARK INTERNO, NO SE PUBLICA. Réplica plano a plano del video "
            "7678030150944001310 de @jcfdlw (3:01, 48.300 vistas): mismo texto literal de "
            "la transcripción, mismas tomas con la misma duración medida, mismo contenido "
            "de imagen — lo único que cambia son las imágenes, generadas por nosotros. "
            "El guion es de ellos: sirve para comparar lado a lado qué puede producir el "
            "pipeline, no para publicar."),
        "_original": (
            "referencias/jcfdlw/7678030150944001310.mp4 · 181,40 s · 30 fps · cuadro real "
            "1080×1440 dentro de 1080×1920. El mapa de las 77 tomas está en "
            "MAPA-ORIGINAL.md y en tomas.py; los cortes salen de la detección de escenas "
            "de ffmpeg y se verificaron mirando el fotograma medio de cada toma."),
        "_desvios": (
            "1) Ellos encuadran 3:4 con barras negras; nosotros generamos 9:16 a sangre, "
            "porque el módulo genera a la resolución nativa de H3. 2) Las tomas 6 y 14 "
            "(6,47 s) se parten en dos planos: son los dos únicos cortes agregados. "
            "3) La voz es Kate, no la de ellos, y corre a ~16,7 cps naturales contra los "
            "20,6 cps del original: el desvío por línea se mide y se anota, el texto NO se "
            "reescribe."),
        "estructura": estructura(pl),
        "estilo_imagen": ESTILO_IMAGEN,
        "estilo_video": ESTILO_VIDEO,
        "cierre_video": CIERRE_VIDEO,
        "solo_sonidos": SOLO_SONIDOS,
        "personajes": PERSONAJES,
        "locaciones": LOCACIONES,
        "voces": {"narrador": KATE},
        "madre": [{"id": i, "aspecto": "9:16", "refs": [],
                   "prompt": f"{pr} {SIN_TEXTO}"} for i, pr in MADRE],
        "planos": pl,
        "voz": lineas_de_voz(),
    }
    (AQUI / "proyecto.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    gen = sum(x.get("segundos", 0) or 0 for x in pl)
    print(f"proyecto.json · {len(pl)} planos · {sum(x['corta'] for x in pl):.2f} s de línea "
          f"· {len(doc['voz'])} líneas de voz · {len(doc['madre'])} assets madre")


if __name__ == "__main__":
    main()
