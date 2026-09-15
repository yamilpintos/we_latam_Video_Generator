"""Arma la lista de planos de Aladino y de ahi saca los dos JSON que consume
todo lo demas: storyboard.json (para nanobanana) y planos.json (para H3).

Esto reemplaza a armar_guion.py, que armaba 10 escenas de 30 s haciendo pasar
tres clips encadenados por una sola toma continua. No funcionaba: las junturas
se veian, la camara tenia que frenar en cada una y la identidad del personaje
se degradaba porque el tercer clip estaba a dos generaciones del dibujo.

Aca cada plano es un plano de verdad. Dura entre 5 y 15 segundos, sale directo
de su propia imagen de storyboard, y no depende de ningun otro plano. Se cortan
en el montaje, que es como se resuelve esto en cine desde hace cien anios.

Lo que se gana:
  - no hay junturas que disimular, hay cortes
  - la camara puede moverse, porque el corte tapa cualquier cosa
  - todos los planos son independientes: paralelizan de a 4 sin esperarse
  - si uno sale mal se rehace solo, no arrastra a los dos siguientes
"""
import json
import pathlib

RAIZ = pathlib.Path(__file__).parent

# ---------------------------------------------------------------- duraciones
# H3 solo acepta length = 17k+5 fotogramas a 24 fps, y esta entrenado en un
# rango de mas o menos 124 a 362. Eso da un plano minimo de 5.2 s y uno maximo
# de 15.1 s. Cualquier duracion que pida el director se acomoda a esa grilla.
GRILLA = [(17 * k + 5, (17 * k + 5) / 24) for k in range(7, 22)]


def encajar(seg):
    """Devuelve el (length, duracion_real) de la grilla mas cercano a seg."""
    return min(GRILLA, key=lambda g: abs(g[1] - seg))


# ------------------------------------------------------------------- estilo
ESTILO = ("Original 2D animated illustration, exact same art style, line "
          "weight, flat cel shading and colour treatment as the references.")

# Como se describe cada tamanio de plano. La escala va en la imagen Y en el
# prompt de video: si solo va en uno de los dos, H3 la corrige por su cuenta y
# los personajes vuelven a salir gigantes.
TAMANIO = {
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
    # El "waist up" a secas no alcanzaba: nanobanana dibujaba el personaje
    # entero parado en la locacion siete veces de siete. Hay que decirle que
    # el borde de abajo CORTA, y nombrar lo que no tiene que estar.
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

# Descripcion de vestuario que va en TODO prompt donde aparece el personaje.
# Repetirla en cada plano es lo que frena la deriva de identidad: la hoja de
# modelo da la cara, el texto sostiene el vestuario.
PERS = {
    "aladino":  ("m_aladino",  "the young man with tousled dark hair, in a "
                 "patched ochre tunic with visible cloth patches, a frayed "
                 "dark red sash, loose brown trousers and worn sandals"),
    "aladino_rico": ("m_aladino", "the same young man with tousled dark hair, "
                     "now dressed in fine embroidered robes of deep teal and "
                     "gold instead of his patched tunic"),
    "mago":     ("m_mago",     "the tall gaunt old man with a long grey beard "
                 "reaching mid-chest, in dark indigo robes with faded gold "
                 "embroidery and a long black travelling cloak"),
    "princesa": ("m_princesa", "the young woman with dark hair in two braids "
                 "falling forward over her shoulders, in a long cream and "
                 "gold embroidered silk dress with a blue-green gem at the "
                 "waist"),
    "genio":    ("m_genio",    "the huge blue-violet smoke spirit with glowing "
                 "gold geometric markings on its forearms and chest, a heavy "
                 "gold collar and wide gold cuffs, its lower body trailing "
                 "into a column of dark smoke"),
}

LOC = {
    "bazar":    ("l_bazar",    "the crowded persian bazaar in daylight"),
    "desierto": ("l_desierto", "the desert dunes at dusk"),
    "cueva":    ("l_cueva",    "the underground treasure cavern"),
    "palacio":  ("l_palacio",  "the great palace courtyard"),
    "alcoba":   ("l_alcoba",   "the candlelit palace bedchamber at night"),
}

# El bloque de idioma va en TODOS los planos, hablen o no. Sin el, H3 mete
# murmullos y chusmerio de fondo en ingles, que fue exactamente lo que arruino
# el audio de la version anterior.
IDIOMA = ("SPOKEN LANGUAGE: SPANISH. Every voice, word, murmur, shout or "
          "crowd chatter heard in this shot is in Spanish. NEVER English. If "
          "any voice appears at all, it is Spanish.")

# H3 RELLENA TODO HUECO DE AUDIO. Si el clip dura mas que lo que se pide, el
# modelo sintetiza murmullos, voces de fondo y personajes que nadie pidio: eso
# es lo que despues hay que doblar. La documentacion del modelo dice que no
# alcanza con pedir silencio; hay que CERRAR las vias de voz una por una y
# ademas dar audio que no sea voz para llenar la duracion.
SIN_VOCES = (
    "SOUNDSCAPE RESTRICTION: No voiceover. No narration. No singing. No "
    "lyrics. No random voices. No individual background speech. No crowd "
    "chatter. No whispering. Fill the entire duration with the ambience "
    "described in AUDIO and nothing else.")

# Solo en planos con dialogo: cierra las voces AJENAS sin cerrar la propia.
SOLO_UNO = (
    "SOUNDSCAPE RESTRICTION: (S1) is the only voice in this shot. No other "
    "character speaks. No voiceover, no narration, no singing, no lyrics, no "
    "random voices, no individual background speech, no crowd chatter.")

# El campo de musica no diegetica se declara SIEMPRE. Si queda vacio, el modelo
# a veces mete voces creyendo que son parte de una pista musical.
SIN_MUSICA = "NON-DIEGETIC MUSIC: N/A."

# La correccion mas importante de la primera corrida. H3 arranca clavado en el
# dibujo pero despues va inventando: aparecieron cactus saguaro en el desierto
# arabe, fuego alrededor del mago, un chico de rojo que no existe, y en un
# primer plano se colo la cara de otro personaje. 5 planos de 39 quedaron
# inservibles por esto. La duracion no tiene nada que ver: la correlacion
# entre largo del plano y deriva fue -0.04, o sea ninguna.
NO_INVENTES = (
    "DO NOT ADD ANYTHING that is not already in the first frame. No new "
    "characters, no new faces, no extra people, no new landscape features, no "
    "cacti, no fire, no flames, no magical glows, no weather. The location, "
    "the terrain, the architecture, the time of day, the light and the NUMBER "
    "OF CHARACTERS stay exactly as in the first frame from beginning to end. "
    "Nothing enters frame that was not there. Animate what is in the picture; "
    "invent nothing.")

# H3 dibuja el humo y el polvo como cumulos redondos de caricatura, que chocan
# con el resto del estilo. Hay que pedirle explicitamente la textura.
HUMO = (
    "Any smoke, dust or vapour is soft and wispy, painted with the same brush "
    "and texture as the rest of the image, drifting and dissipating. NEVER "
    "rounded cartoon cumulus puffs, never white bubble clouds.")


# --------------------------------------------------------------- los planos
# (escena, seg, tamanio, locacion, [personajes], storyboard, camara+accion,
#  audio, dialogo)
#
# storyboard = que se ve, quieto, para que nanobanana dibuje el primer frame
# camara+accion = que se MUEVE a partir de ese frame, para que H3 lo anime
PLANOS = [
    # ------------------------------------------------------- E01 el robo
    ("E01_robo", 10, "PG", "bazar", [], (
        "The bazaar seen down the length of its main aisle, awnings overhead, "
        "stalls piled with fruit and cloth on both sides, a dozen shoppers in "
        "robes moving through. No one is the focus. Late morning light falls "
        "in slats through the awnings."
    ), (
        "Slow push in down the aisle. The crowd drifts across frame, cloth "
        "sways, dust turns in the light shafts."
    ), "[Ambient] busy market: overlapping voices, footsteps on stone. "
       "[Foley] cloth flapping, a wooden crate set down.", None),

    ("E01_robo", 6, "PM", "bazar", ["aladino"], (
        "The young man stands at a fruit stall piled with pomegranates, half "
        "turned away from it, eyes sliding sideways toward the fruit while he "
        "pretends to look elsewhere."
    ), (
        "He glances left, then right, then his eyes settle on the fruit. "
        "Behind him the crowd keeps moving. Camera holds."
    ), "[Ambient] market voices, closer now. [Foley] his breathing.", None),

    ("E01_robo", 5, "PD", "bazar", [], (
        "A pile of dark red pomegranates on a wooden stall board. ONE single "
        "young hand, with exactly five fingers and dirty fingernails, enters "
        "from the top right and is closing around the topmost fruit. There is "
        "only ONE hand in the picture and no other limbs."
    ), (
        "The hand closes on the pomegranate and lifts it clear of the pile. "
        "The pile shifts and one fruit rolls a little."
    ), "[Foley] fruit rolling on wood, a single soft scrape.", None),

    ("E01_robo", 8, "PG", "bazar", ["aladino"], (
        "The bazaar aisle from behind. The young man is running away from "
        "camera toward the far stone archway, weaving between shoppers. A "
        "stallkeeper is half out of his stall, arm up."
    ), (
        "Camera whip-pans right and follows him running. He dodges a shopper, "
        "vaults a low crate and disappears through the archway. The "
        "stallkeeper shouts after him."
    ), "[Ambient] market. [Foley] running footsteps, a crate knocked over. "
       "[Speech] the stallkeeper shouts angrily after him.", None),

    # ------------------------------------------------------- E02 el mago
    ("E02_mago", 7, "PM", "bazar", ["aladino"], (
        "A narrow shaded side alley off the bazaar. The young man is crouched "
        "low behind a stack of woven baskets, back against the wall, the "
        "pomegranate in both hands, chest heaving."
    ), (
        "He gets his breath back, grins to himself and bites into the fruit. "
        "Then his chewing slows and stops as something off frame catches his "
        "eye."
    ), "[Ambient] the market muffled, one alley away. [Foley] breathing, a "
       "wet bite.", None),

    ("E02_mago", 7, "PG", "bazar", ["aladino", "mago"], (
        "The side alley from a low angle. The young man is crouched small at "
        "the right edge of frame. At the far end of the alley, framed by the "
        "light of the market behind him, the tall old man stands facing him, "
        "a long shadow stretching down the alley toward the boy."
    ), (
        "The shadow slides up the wall as the old man takes three unhurried "
        "steps forward. The boy shrinks back against the baskets. The market "
        "noise behind drops away."
    ), "[Ambient] market noise dropping away to near silence. [Foley] slow "
       "deliberate footsteps on stone.", None),

    ("E02_mago", 6, "PP", "bazar", ["mago"], (
        "Close on the old man's face, lit from the side, unhurried, appraising, "
        "not unkind. He is looking DOWN AND OFF FRAME TO THE RIGHT, at "
        "someone crouched low on the right-hand side, and his eyes are "
        "clearly aimed to the right, never to the left."
    ), (
        "His eyes move slowly, reading the boy up and down. Then one corner "
        "of his mouth lifts. Camera creeps in a fraction."
    ), "[Ambient] near silence, distant market. [Foley] cloth shifting.",
        None),

    ("E02_mago", 9, "PM", "bazar", ["aladino", "mago"], (
        "Two shot in the alley, the old man standing on the left, the young "
        "man half risen on the right. The old man is holding out a gold coin "
        "between two fingers. The old man MUST have his long grey beard "
        "reaching mid-chest and his hair as in his model sheet: he is not "
        "clean-shaven and not bald."
    ), (
        "The old man extends the coin further and speaks. The boy looks at "
        "the coin, then at his face, and slowly straightens up."
    ), "[Ambient] distant market. [Foley] a coin turning between fingers. "
       "[Speech] the old man speaks calmly to the boy.",
        "Tomá. Vení conmigo, muchacho, y no vas a robar nunca más."),

    # ---------------------------------------------------- E03 el desierto
    ("E03_puerta", 10, "PGE", "desierto", ["aladino", "mago"], (
        "The desert at dusk, huge orange dunes filling the frame. Two tiny "
        "figures walk the ridge of a dune in the middle distance, the old man "
        "ahead, the young man trailing behind."
    ), (
        "Camera drifts slowly right, keeping them small in frame. Sand streams "
        "off the ridge in the wind. They keep walking."
    ), "[Ambient] wind over open sand, nothing else.", None),

    ("E03_puerta", 6, "PA", "desierto", ["aladino", "mago"], (
        "The two of them at ground level on SOFT SAND DUNES, nothing but rolling "
        "orange dunes and open sky behind them: no rock formations, no "
        "canyon, no cliffs, no cacti, no vegetation. The old man strides "
        "ahead in his black cloak. The young man is a few paces behind, "
        "dragging his feet, tunic dusty, head down, EXHAUSTED AND MISERABLE, "
        "definitely not smiling."
    ), (
        "They walk toward camera. The boy stumbles in the soft sand, catches "
        "himself, hurries to keep up. The old man does not slow down."
    ), "[Ambient] wind. [Foley] feet sinking into sand, cloak snapping.",
        None),

    ("E03_puerta", 6, "PP", "desierto", ["mago"], (
        "Close on the old man's face against the dusk sky, stopped, looking "
        "down at the ground ahead of him. Wind moving his beard."
    ), (
        "He stops dead. His lips begin to move in a low murmur and he lifts "
        "one hand out of frame. His eyes stay fixed on the ground."
    ), "[Ambient] wind rising. [Speech] the old man murmurs low words under "
       "his breath in Spanish.", None),

    ("E03_puerta", 8, "PG", "desierto", ["aladino", "mago"], (
        "Wide of the dune floor at the base of a dark rock outcrop, the two "
        "small figures standing side by side, facing a bare patch of sand."
    ), (
        "The sand cracks open in front of them and caves inward. Dust blows "
        "up. As it clears, a stone stairway is revealed going down into the "
        "dark. Both figures step back, then look at each other."
    ), "[Ambient] wind. [Foley] a deep grinding of stone, sand pouring, a "
       "low boom.", None),

    # ------------------------------------------------------- E04 la cueva
    ("E04_lampara", 7, "PM", "cueva", ["aladino"], (
        "The young man on a stone stairway in the dark, seen from the front, "
        "cold blue-green light rising from below onto his face and chest."
    ), (
        "He descends step by step toward camera. The blue-green light on him "
        "grows stronger with each step. His eyes widen at something below."
    ), "[Ambient] a deep underground hush, faint dripping. [Foley] sandals "
       "on stone steps, echoing.", None),

    ("E04_lampara", 10, "PG", "cueva", ["aladino"], (
        "The treasure cavern opening out: carved arches, mounds of gold coins "
        "and vessels, blue-green light from above and gold light from the "
        "hoard. The young man is small at the foot of the stair at the back "
        "of frame, standing still."
    ), (
        "Camera cranes slowly up and back, opening the cavern out around him "
        "and making him smaller still. He turns his head to take it in."
    ), "[Ambient] cavern reverb, dripping water. [Foley] a few coins "
       "settling somewhere in the dark.", None),

    ("E04_lampara", 7, "PM", "cueva", ["aladino"], (
        "The young man in a narrow path between two mounds of treasure that "
        "rise HIGHER THAN HIS SHOULDERS on both sides and run off the left "
        "and right edges of the picture, so that he is walking in a trench of "
        "gold. Gold light on his face from below."
    ), (
        "He walks forward, camera tracking with him. He trails one hand along "
        "a mound and coins slide and clatter down behind him. He does not "
        "stop to pick any up."
    ), "[Ambient] cavern reverb. [Foley] coins sliding and clattering.",
        None),

    ("E04_lampara", 6, "PD", "cueva", [], (
        "A small plain brass oil lamp, dented and unpolished, sitting alone "
        "in a carved stone niche in the cavern wall, seen from the side. "
        "Nothing else in the niche. Cold blue-green light from the left, deep "
        "shadow to the right. The carved stonework of the niche runs off both "
        "the left and the right edges of the picture."
    ), (
        "Camera pushes slowly in on the lamp. Dust turns in the light in "
        "front of it. Nothing else moves."
    ), "[Ambient] cavern hush, one drip echoing.", None),

    ("E04_lampara", 5, "PP", "cueva", ["aladino"], (
        "Close on the young man's face, lit cold from one side, looking "
        "slightly off camera at something below eye level."
    ), (
        "He looks at it a long moment, glances back over his shoulder toward "
        "the stair, then reaches forward out of frame."
    ), "[Ambient] cavern hush. [Foley] fabric shifting.", None),

    # ---------------------------------------------------- E05 el encierro
    ("E05_encierro", 7, "PG", "cueva", ["aladino", "mago"], (
        "Sharp low angle from the cavern floor looking straight up the stone "
        "stair to a small square of hot daylight far above. The young man is "
        "small at the foot of the stair holding the brass lamp. Far up in the "
        "square of light, the old man leans in as a silhouette."
    ), (
        "The silhouette above reaches one arm down, insisting. The boy at the "
        "bottom does not move. Dust falls through the shaft of light between "
        "them."
    ), "[Ambient] cavern reverb, wind at the opening far above. [Foley] "
       "falling grit.", None),

    ("E05_encierro", 7, "PP", "cueva", ["mago"], (
        "Close on the old man's face from below, hard daylight behind him "
        "rimming his beard, the rest of him in shadow. He is looking down."
    ), (
        "His patience goes. The lines of his face harden and he speaks down "
        "into the hole, one hand braced on the stone."
    ), "[Ambient] wind at the cave mouth. [Speech] the old man commands, "
       "cold and hard.",
        "Dame la lámpara, muchacho. Dámela y te saco."),

    ("E05_encierro", 7, "PP", "cueva", ["aladino"], (
        "Close on the young man's face from slightly above, cold blue-green "
        "light on him, looking up. He is holding the lamp hard against his "
        "chest with both arms. His expression is STUBBORN AND DEFIANT: jaw "
        "set, brows down, mouth a hard line. He is frightened but refusing. "
        "He is NOT smiling, NOT dreamy, NOT hopeful."
    ), (
        "He tightens his grip on the lamp and holds the old man's eyes. Then "
        "he answers, quiet and stubborn."
    ), "[Ambient] cavern reverb. [Speech] the boy answers quietly, refusing.",
        "No. Primero sacame de acá."),

    ("E05_encierro", 8, "PG", "cueva", ["aladino"], (
        "Low angle up the stair again. The square of daylight far above. The "
        "young man tiny at the bottom, looking up."
    ), (
        "A slab of stone slides across the opening above and the daylight "
        "narrows to a line and then to nothing. The frame goes almost black, "
        "leaving only the faint blue-green glow of the cavern and the boy's "
        "silhouette."
    ), "[Foley] a heavy stone grinding shut, a boom, then dead silence. "
       "[Ambient] cavern hush closing in.", None),

    # ------------------------------------------------------- E06 el genio
    ("E06_genio", 8, "PM", "cueva", ["aladino"], (
        "The young man sitting on the cavern floor with his back against a "
        "carved pillar, knees up, holding the brass lamp in both hands in his "
        "lap. Very low blue-green light. He looks beaten."
    ), (
        "He lets his head fall back against the pillar. Then he looks down at "
        "the lamp in his hands and turns it over slowly."
    ), "[Ambient] deep cavern silence, one distant drip. [Foley] cloth on "
       "stone, metal turning in hands.", None),

    ("E06_genio", 5, "PD", "cueva", [], (
        "Extreme close on the brass lamp held in two dirty hands, a sleeve of "
        "patched ochre cloth beginning to rub across its side."
    ), (
        "The sleeve rubs the brass twice. On the second pass a thread of "
        "light opens along the metal under the cloth."
    ), "[Foley] cloth rubbing metal. [SFX] a low tone rising underneath.",
        None),

    ("E06_genio", 8, "PG", "cueva", ["aladino"], (
        "The cavern with the young man small at the base of the pillar. A "
        "thick rope of dark smoke is pouring up out of the lamp spout and "
        "already fills the upper half of the frame."
    ), (
        "The smoke boils upward and outward, filling the cavern, lit from "
        "within by pulses of gold. The boy scrambles backward against the "
        "pillar, one arm up over his face."
    ), "[SFX] a rushing roar building. [Foley] scrambling on stone.", None),

    ("E06_genio", 9, "PG", "cueva", ["aladino", "genio"], (
        "Extreme low angle from the cavern floor. The smoke has resolved into "
        "the blue-violet spirit, and it is ENORMOUS: its head almost touches "
        "the top edge of the picture, its shoulders run nearly the full width "
        "of the frame, and it fills the upper two thirds. Its gold markings "
        "glow. Its lower body is a column of smoke going down into the lamp. "
        "The young man is a TINY silhouette at the very bottom edge of frame, "
        "on his back, looking up. He is about ONE TWELFTH of the image "
        "height. The size difference between them is the whole point of the "
        "picture."
    ), (
        "The spirit finishes forming, rolls its shoulders and stretches both "
        "arms wide. The smoke column beneath it turns slowly. The boy stays "
        "flat on the floor, tiny."
    ), "[SFX] the roar settling into a low hum. [Foley] a vast slow "
       "exhalation.", None),

    ("E06_genio", 7, "PP", "cueva", ["genio"], (
        "Close on the spirit's face, blue-violet skin, thick brows, gold "
        "collar at the bottom of frame, glowing markings. It is looking down "
        "toward camera."
    ), (
        "It opens its eyes fully, looks down at the boy, and speaks. Smoke "
        "curls past its jaw as it talks."
    ), "[SFX] low hum. [Speech] the spirit speaks in a huge slow voice.",
        "Mil años durmiendo. Y me despierta un ladrón de frutas."),

    # ----------------------------------------------------- E07 la llegada
    ("E07_llegada", 10, "PGE", "palacio", [], (
        "The great palace courtyard at dusk, empty. The lit fountain in the "
        "middle ground, the enormous ornate archway behind it, arcades down "
        "both sides. Warm low sun on the upper stonework."
    ), (
        "Camera cranes slowly down and forward toward the fountain. The water "
        "moves, lanterns along the arcade flicker on one after another as the "
        "light drops."
    ), "[Ambient] evening courtyard, water, distant birds.", None),

    ("E07_llegada", 7, "PA", "palacio", ["aladino_rico"], (
        "The young man in fine teal and gold robes standing beside the "
        "fountain, head to toe, clearly much shorter than the fountain is "
        "wide, the huge archway rising far above and behind him."
    ), (
        "He walks a few paces along the fountain edge, looking up at the "
        "facade, turning slowly as he goes. He is small against all of it."
    ), "[Ambient] fountain water, evening. [Foley] soft footsteps on stone.",
        None),

    ("E07_llegada", 5, "PP", "palacio", ["aladino_rico"], (
        "Close on the young man's face tilted up, warm dusk light on him, "
        "eyes moving as he takes in something enormous above him."
    ), (
        "His eyes travel upward and keep going. His mouth opens slightly. He "
        "lets out a breath and almost laughs."
    ), "[Ambient] fountain. [Foley] a breath, a half laugh.", None),

    ("E07_llegada", 8, "PG", "palacio", ["princesa"], (
        "Wide of the courtyard's far side: a broad stone stairway coming down "
        "from the arcade. The young woman in her cream and gold dress has "
        "just appeared at the top of it, small in frame, attendants behind."
    ), (
        "She starts down the stairway. Her dress moves on the steps. Camera "
        "holds wide and lets her come down into the courtyard."
    ), "[Ambient] evening courtyard. [Foley] slippers on stone, silk moving.",
        None),

    # --------------------------------------------------- E08 el encuentro
    ("E08_encuentro", 6, "PM", "palacio", ["princesa"], (
        "The young woman waist up beside the lit fountain, three quarters to "
        "camera, warm lantern light on her, the dark arcade behind."
    ), (
        "She trails her fingers in the fountain water, then stops as she "
        "senses someone. She turns her head toward camera."
    ), "[Ambient] fountain, evening. [Foley] fingers through water.", None),

    # Este y el siguiente van en primer plano y no en plano medio. Dos planos
    # medios seguidos de la princesa serian un salto de eje, y ademas la
    # pregunta y la respuesta son el corazon de la escena: van de cerca.
    ("E08_encuentro", 7, "PP", "palacio", ["princesa"], (
        "Close on the young woman's face beside the fountain, now turned to "
        "camera, warm lantern light on her, chin slightly up, unafraid."
    ), (
        "She looks him over once, then asks. Her expression stays level, more "
        "curious than alarmed."
    ), "[Ambient] fountain. [Speech] the young woman asks, level and "
       "unafraid.",
        "¿Y vos quién sos?"),

    ("E08_encuentro", 7, "PP", "palacio", ["aladino_rico"], (
        "Close on the young man's face across the fountain, lantern light on "
        "one side of it, the dark courtyard behind him. He is looking OFF "
        "FRAME TO THE RIGHT, at someone standing to his right, and his "
        "eyes and the turn of his head are clearly aimed to the right, "
        "never to the left."
    ), (
        "He opens his mouth to give an answer, stops, and gives a different "
        "one instead, with a small crooked smile at the end."
    ), "[Ambient] fountain. [Speech] the young man answers, a little "
       "amused at himself.",
        "Nadie importante. Todavía."),

    ("E08_encuentro", 8, "PG", "palacio", ["aladino_rico", "princesa"], (
        "Wide of the courtyard at last light. The two of them standing a few "
        "paces apart beside the lit fountain, both small in frame, clearly "
        "shorter than the fountain is wide, the huge archway behind."
    ), (
        "They stand there. She turns back to the water, he takes one step "
        "closer. Camera pulls slowly back, making them smaller, the courtyard "
        "bigger. Lanterns burn along the arcade."
    ), "[Ambient] fountain, evening settling, distant music from inside.",
        None),

    # ------------------------------------------------------ E09 el engano
    ("E09_engano", 7, "PM", "alcoba", ["princesa"], (
        "The candlelit bedchamber at night. The young woman waist up beside a "
        "carved side table. On the table sits the plain dented brass lamp, "
        "clearly out of place among the fine things."
    ), (
        "She picks the old lamp up, turns it over with a puzzled half smile, "
        "and sets it back down. She turns toward a sound at the door."
    ), "[Ambient] quiet room at night, a candle. [Foley] metal set on wood.",
        None),

    # Entero y no medio: hay que verlo de pies a cabeza para que el disfraz
    # se lea, y para que se note que el que entra es el mismo tipo alto del
    # desierto aunque venga encorvado.
    ("E09_engano", 8, "PA", "alcoba", ["mago"], (
        "The open doorway of the bedchamber seen head to toe. The old man "
        "stands in it hunched over and disguised as a pedlar, a shabby head "
        "wrap over his grey hair, carrying a tray of bright new brass lamps."
    ), (
        "He bows low, lifts the tray of shining lamps toward camera and calls "
        "his patter in a thin wheedling voice, keeping his face down."
    ), "[Ambient] quiet room. [Foley] brass clinking on a wooden tray. "
       "[Speech] the pedlar calls out his patter, wheedling.",
        "Lámparas nuevas por lámparas viejas, señora."),

    ("E09_engano", 6, "PD", "alcoba", [], (
        "Extreme close on the side table. Two hands, one young and one old "
        "and knotted, are exchanging a plain dented brass lamp for a bright "
        "new polished one. Candlelight."
    ), (
        "The new lamp is set down as the old one is lifted away. The old "
        "hand closes hard around the dented lamp and pulls it out of frame."
    ), "[Foley] two lamps set down and lifted, a knuckle cracking.", None),

    ("E09_engano", 7, "PG", "alcoba", ["princesa"], (
        "Wide of the bedchamber. The young woman stands by the table with the "
        "new lamp on it. The doorway beyond her is empty, the door swinging."
    ), (
        "The door swings shut on its own. She stays still a moment, then "
        "looks back at the shiny new lamp on the table. The candles gutter "
        "all at once."
    ), "[Ambient] room tone. [Foley] a door swinging shut, candle flames "
       "guttering.", None),

    # ------------------------------------------------------- E10 el final
    ("E10_final", 8, "PG", "palacio", ["aladino_rico", "mago"], (
        "The palace courtyard at dawn in cold blue light, the fountain still. "
        "The old man and the young man face each other across it, about ten "
        "paces apart, both small in frame, dwarfed by the great archway. The "
        "old man holds the dented brass lamp raised in one hand."
    ), (
        "The old man raises the lamp higher. The young man takes one slow "
        "step forward around the fountain. Neither hurries. Cold wind moves "
        "across the courtyard."
    ), "[Ambient] cold empty courtyard at dawn, wind, still water.", None),

    ("E10_final", 7, "PP", "palacio", ["mago"], (
        "Close on the old man's face in cold blue dawn light, his own face "
        "again, no disguise, looking across at someone off camera. The lamp "
        "is just visible raised at the edge of frame."
    ), (
        "He almost smiles and speaks across the courtyard, unhurried, sure of "
        "himself. His beard moves in the wind."
    ), "[Ambient] wind. [Speech] the old man speaks across the courtyard, "
       "calm and certain.",
        "Todo esto era mío antes de ser tuyo."),

    ("E10_final", 5, "PD", "palacio", [], (
        "Extreme close on wet stone paving in cold dawn light. The dented "
        "brass lamp has just hit the ground and is rolling."
    ), (
        "The lamp rolls across the stone, wobbles, and comes to rest on its "
        "side. A thin curl of smoke starts out of the spout."
    ), "[Foley] brass hitting and rolling on wet stone, ringing. [SFX] a "
       "low tone starting.", None),

    ("E10_final", 10, "PG", "palacio", ["aladino_rico"], (
        "Wide of the courtyard at dawn. A column of dark smoke stands where "
        "the old man was. The young man is small on the other side of the "
        "fountain, alone in the enormous empty space."
    ), (
        "The smoke column collapses and blows apart across the paving until "
        "nothing is left. The young man lowers his arm. Camera pulls slowly "
        "back and up, leaving him one small figure in the huge courtyard as "
        "the dawn light warms."
    ), "[SFX] the low tone cutting out. [Ambient] wind, then only the "
       "fountain and morning birds.", None),
]


# ------------------------------------------------------------------ armado
def refs_de(loc, personajes):
    """Locacion primero, despues los personajes sin repetir. El orden importa:
    es el que nombran <Picture 1>, <Picture 2>... en el prompt."""
    out = [LOC[loc][0]]
    for p in personajes:
        hoja = PERS[p][0]
        if hoja not in out:
            out.append(hoja)
    return out


def storyboard_prompt(tam, loc, personajes, que_se_ve):
    etiqueta, escala = TAMANIO[tam]
    refs = refs_de(loc, personajes)
    cuadros = ", ".join(f"<Picture {i+1}>" for i in range(len(refs)))

    p = [ESTILO]
    p.append(f"Use {cuadros} as reference: <Picture 1> is the location, "
             f"{'the rest are character model sheets' if len(refs) > 1 else 'there are no characters in this shot'}.")
    p.append(f"{etiqueta}. {que_se_ve}")
    if personajes:
        quienes = "; ".join(PERS[p_][1] for p_ in personajes)
        p.append(f"CHARACTERS, drawn exactly as in their model sheets: "
                 f"{quienes}.")
    p.append(f"FRAMING AND SCALE: {escala}")
    # El encuadre vertical se cuela sobre todo en los planos detalle, donde no
    # hay figura humana que sugiera la orientacion. Un plano en otra relacion
    # de aspecto entra a H3 deformado o con bandas negras.
    p.append("FORMAT: a WIDE 16:9 landscape frame, clearly wider than tall. "
             "Never square, never vertical.")
    p.append("This is a single film frame, not a poster: no text, no borders, "
             "no panel divisions, no title.")
    return "\n".join(p)


def video_prompt(tam, personajes, movimiento, audio, dialogo):
    etiqueta, escala = TAMANIO[tam]
    p = [f"{etiqueta}, 2D animated film.",
         f"MOTION: {movimiento}",
         f"FRAMING: hold the shot size of the first frame. {escala}"]
    if personajes:
        quienes = "; ".join(PERS[p_][1] for p_ in personajes)
        p.append(f"CHARACTERS, unchanged from the first frame: {quienes}.")
    p.append(f"AUDIO: {audio}")
    if dialogo:
        # Formato documentado de H3: ID de hablante estable + marca de idioma
        # por linea. El ID vale DENTRO del plano —no hay voz persistente entre
        # clips, de ahi el doblaje— pero evita que el modelo reparta la linea
        # entre dos bocas o le invente un interlocutor.
        quien = PERS[personajes[0]][1] if len(personajes) == 1 else None
        p.append(f"SPEAKERS: (S1) is {quien}." if quien
                 else "SPEAKERS: (S1) is the character described in AUDIO.")
        p.append(f'(S1) [Spanish] "{dialogo}"')
        # Anclaje temporal: sin esto la linea flota y H3 rellena los bordes.
        p.append("(S1) starts speaking about one second into the shot and "
                 "finishes before it ends; the rest of the duration is the "
                 "ambience above, with no speech.")
        p.append(SOLO_UNO)
    else:
        p.append(SIN_VOCES)
    p.append(SIN_MUSICA)
    p.append(NO_INVENTES)
    # La regla del humo solo donde hace falta: cargar todos los prompts con
    # restricciones que no aplican diluye las que si.
    if any(x in (movimiento + audio).lower()
           for x in ("smoke", "dust", "silt", "vapour", "cloud")):
        p.append(HUMO)
    p.append(IDIOMA)
    return "\n".join(p)


def main():
    storyboard, planos = [], []
    seg_total = 0

    for i, (esc, seg, tam, loc, pers, ve, mov, aud, dia) in enumerate(PLANOS, 1):
        pid = f"P{i:02d}"
        length, real = encajar(seg)
        seg_total += real

        storyboard.append({
            "id": f"sb_{pid}",
            "refs": [f"assets/{r}.png" for r in refs_de(loc, pers)],
            "prompt": storyboard_prompt(tam, loc, pers, ve),
        })
        planos.append({
            "id": pid,
            "escena": esc,
            "tipo": tam,
            "loc": loc,
            "personajes": pers,
            "length": length,
            "segundos": round(real, 3),
            "first_frame": f"assets/sb_{pid}.png",
            "prompt": video_prompt(tam, pers, mov, aud, dia),
            "dialogo": dia,
        })

    (RAIZ / "storyboard.json").write_text(json.dumps(
        {"_comentario": "Un dibujo por plano. Es el primer fotograma que H3 "
                        "recibe en first_frame. Se revisa y se rehace lo que "
                        "no cierra ANTES de gastar un minuto de GPU.",
         "assets": storyboard}, ensure_ascii=False, indent=2), encoding="utf-8")

    (RAIZ / "planos.json").write_text(json.dumps(
        {"_comentario": "Planos independientes. Ninguno depende de otro, asi "
                        "que todos paralelizan y cualquiera se puede rehacer "
                        "solo. Se montan con cortes.",
         "fps": 24, "planos": planos}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    # --------------------------------------------------------- el reporte
    print(f"{len(planos)} planos   {seg_total/60:.0f}:{seg_total%60:04.1f} "
          f"de pelicula\n")

    for esc in dict.fromkeys(p["escena"] for p in planos):
        de = [p for p in planos if p["escena"] == esc]
        tipos = " ".join(p["tipo"] for p in de)
        print(f"  {esc:<14} {len(de)} planos  "
              f"{sum(p['segundos'] for p in de):5.1f}s   {tipos}")

    print()
    reparto = {}
    for i, p in enumerate(planos):
        reparto.setdefault(i % 4, []).append(p["segundos"])
    for g in sorted(reparto):
        print(f"  GPU {g}: {len(reparto[g])} planos, "
              f"{sum(reparto[g]):.0f}s de video")

    con_voz = [p for p in planos if p["dialogo"]]
    print(f"\n  {len(con_voz)} planos con dialogo, un solo personaje en cada uno")

    # Salto de eje: cortar entre dos planos del mismo tamanio, en la misma
    # locacion y con la misma gente, da un brinco feo en vez de un corte. Se
    # arregla cambiando el tamanio de uno de los dos. Lo chequea la maquina
    # porque a mi se me escapo uno leyendo la lista a ojo.
    saltos = [(a, b) for a, b in zip(planos, planos[1:])
              if a["tipo"] == b["tipo"] and a["loc"] == b["loc"]
              and a["personajes"] == b["personajes"]]
    if saltos:
        print("\n  !! posibles saltos de eje:")
        for a, b in saltos:
            print(f"     {a['id']} y {b['id']}: los dos {a['tipo']} en "
                  f"{a['loc']} con {a['personajes'] or 'nadie'}")
    else:
        print("  sin saltos de eje: ningun corte repite tamanio, "
              "locacion y reparto")

    # Y que ninguna duracion se haya ido del rango entrenado del modelo.
    fuera = [p for p in planos if not 124 <= p["length"] <= 362]
    if fuera:
        print(f"  !! fuera del rango entrenado: "
              f"{' '.join(p['id'] for p in fuera)}")


if __name__ == "__main__":
    main()
