"""PROFUNDIDAD — Short vertical de 60 segundos.

Un buzo desciende y encuentra algo en el fondo que no deberia estar ahi.

POR QUE ESTE CONCEPTO Y NO OTRO
  Tres decisiones, y dos son tecnicas antes que creativas.

  1. La cara va tapada. Los primeros planos de caras humanas son lo peor que
     le sale a cualquier modelo de video: el valle inquietante mata la
     retencion en un segundo. Con mascara y regulador solo se ven los ojos.
     Esquivamos la debilidad mas grande del modelo sin que se note.

  2. El agua turbia perdona. Particulas en suspension, poco contraste, luz
     difusa. Es el entorno donde los artefactos de generacion desaparecen.
     Realismo barato de sostener.

  3. Todo el peso esta en el sonido, que es lo que H3 hace distinto: genera
     audio sincronizado con la imagen. Respiracion en el regulador, burbujas,
     crujido de metal, el silencio de la presion.

SIN DIALOGO SINCRONIZADO
  No hay [Speech] en ningun plano. La voz va en OFF, encima, hecha con
  ElevenLabs. Con el regulador puesto no se ve la boca, asi que no hace falta
  que el modelo sincronice nada — y de paso la voz queda igual en los seis
  planos donde habla, que es el problema que H3 no sabe resolver.
  El texto para grabar esta en voz_en_off.txt, que escribe este script.

EL MINIMO DE 5.2 SEGUNDOS
  H3 no puede generar planos mas cortos: 124 fotogramas es el piso de su
  rango entrenado. Pero un Short necesita cortes de 1.5 a 2.5 s al principio
  o pierde al espectador. La salida es generar de mas y usar solo el mejor
  pedazo en el montaje. Cada plano lleva anotado "usa" con el tramo que va a
  la linea de tiempo. Se genera 75 s para usar 60.
"""
import json
import pathlib

RAIZ = pathlib.Path(__file__).parent
GRILLA = [(17 * k + 5, (17 * k + 5) / 24) for k in range(7, 22)]


def encajar(seg):
    return min(GRILLA, key=lambda g: abs(g[1] - seg))


# ------------------------------------------------------------------- estilo
FOTO = ("Photorealistic cinematic underwater footage, shot on a full-frame "
        "camera with a fast wide lens. Heavy particulate suspended in the "
        "water catching the light. Volumetric beams. Deep teal-black water, "
        "cold. High ISO grain. Shallow depth of field. Vertical 9:16 frame.")

# El buzo se describe igual en los diez planos: es lo unico que sostiene que
# sea la misma persona, porque no hay hoja de modelo ni cara visible.
BUZO = ("a technical diver in a black drysuit with a yellow shoulder stripe, "
        "a full black mask with a curved glass port, a rebreather loop over "
        "the shoulders, and a wrist-mounted dive computer")


# ---------------------------------------------------------------- los planos
# (id, seg_generado, usa_desde, usa_hasta, que_se_ve, movimiento, audio, funcion)
PLANOS = [
    ("S01", 5.2, 0.0, 3.0,
     "EXTREME CLOSE UP on the curved glass port of a black diving mask filling "
     "the frame. Behind the glass, a pair of wide human eyes, lit from below "
     "by a cold torch. Condensation on the inside of the glass. Black water "
     "behind. No mouth visible, the rebreather loop crosses the bottom of frame.",
     "The eyes flick left, then right, then lock forward. A slow blink. The "
     "torch light on the glass brightens as something below comes closer.",
     "[Foley] slow heavy breathing through a rebreather, very close and dry. "
     "[Ambient] deep water pressure hum, almost silence.",
     "HOOK. Bucle abierto: la voz en off promete algo y no lo entrega."),

    ("S02", 5.2, 0.0, 2.5,
     "Looking straight UP from below at the surface of the sea, far above. The "
     "diver's silhouette hangs against a small pale disc of daylight. Shafts "
     "of light stab down through the dark and die before reaching the camera.",
     "The disc of daylight shrinks and dims as the diver descends toward "
     "camera. Bubbles rise past the lens in strings.",
     "[Foley] a burst of exhaled bubbles rushing upward past the ear. "
     "[Ambient] the surface noise fading out with depth.",
     "Descenso. El corte rapido mantiene el pulso alto."),

    ("S03", 5.2, 0.0, 4.0,
     "EXTREME CLOSE UP of a wrist-mounted dive computer strapped over a black "
     "drysuit sleeve, its screen glowing pale green. Water and particles drift "
     "across the glass. Behind the wrist, black water and a torch beam.",
     # Nada de pedirle digitos que cambien: los modelos de video destrozan el "
     # texto en movimiento, y este plano depende de que se lea. El contador de "
     # profundidad va como grafico en post, que ademas retiene mejor.
     "The wrist turns slowly toward camera as the diver keeps descending. "
     "Particles stream UPWARD past the lens, fast, selling the speed of the "
     "descent. The screen backlight flickers once. The torch beam behind "
     "swings across the dark.",
     "[Foley] the tick of a dive computer, breathing slower now. "
     "[SFX] a low creak of pressure on the suit.",
     "BARRA DE PROGRESO. El numero que sube le da al ojo algo que seguir."),

    ("S04", 5.2, 0.0, 4.5,
     "The beam of a powerful dive torch cutting into total blackness, seen "
     "from just behind the diver's shoulder. The beam is a solid cone of light "
     "full of drifting particles and reaches nothing. Empty black on all sides.",
     "The beam sweeps slowly left to right across the void and finds nothing. "
     "Particles stream through it. At the very end of the sweep the beam "
     "catches a hard edge far away and the diver stops it there.",
     "[Ambient] deep water hum, nothing else. [Foley] one slow breath in, held.",
     "TENSION POR AUSENCIA. Cuatro segundos de nada antes del hallazgo."),

    ("S05", 7.3, 0.0, 6.0,
     "The torch beam holding on a distant hard-edged shape in the black water. "
     "Something metallic, riveted and pale, too straight and too regular to be "
     "rock. Most of it is still lost in the dark. The diver is small at the "
     "bottom edge of frame, seen from behind.",
     "The diver swims slowly toward it and the shape resolves a little more "
     "with every metre. Two rows of small dark rectangles become visible along "
     "its side.",
     "[Foley] fins beating slowly, breathing quickening. [SFX] a distant "
     "groan of stressed metal.",
     "ESCALERA 1: de la nada a algo."),

    ("S06", 7.3, 0.0, 6.0,
     "Closer. A vast pale metal wall filling most of the vertical frame, "
     "riveted panels streaked with rust and marine growth, a line of round "
     "windows running up it. The torch light only reaches a fraction of it. "
     "The diver is TINY at the bottom of frame for scale.",
     "The camera cranes slowly upward along the metal wall, and it keeps "
     "going, and going, past the top of the frame. The diver stays tiny at the "
     "bottom.",
     "[SFX] the deep groan of a large metal structure settling. "
     "[Foley] breathing loud and fast now.",
     "ESCALERA 2: la escala. Que sea vertical juega a favor aca."),

    ("S07", 7.3, 0.0, 6.0,
     "Wide from a distance, low angle. UNMISTAKABLY A COMMERCIAL PASSENGER "
     "AIRLINER resting on the seabed and tilted at an angle: the cockpit nose "
     "and its row of angled windscreen panes clearly visible at the left, a "
     "long line of small round cabin windows running down the fuselage, and "
     "the tall vertical TAIL FIN rising up into the black at the right. One "
     "wing is broken off and half buried in silt beside it. This must read "
     "instantly as an aeroplane and never as a submarine or a pipe. The "
     "diver's single torch is a pinprick of light beside the nose, giving the "
     "scale.",
     "The diver's tiny light drifts from the nose along the row of cabin "
     "windows toward the tail, giving the scale away. Silt lifts off the "
     "seabed in slow clouds.",
     "[SFX] a long low resonance, like a struck bell underwater. "
     "[Ambient] pressure hum.",
     "LA REVELACION."),

    ("S08", 7.3, 0.0, 6.0,
     "A row of small round aircraft windows in the dark metal hull, seen close "
     "and slightly from below. WARM YELLOW LIGHT is coming out of every single "
     "one of them, cutting through the black water in solid beams.",
     "The camera drifts slowly along the lit windows. The warm light flickers "
     "once, all the windows at the same time, then steadies.",
     "[SFX] a faint electrical hum that should not exist down here. "
     "[Foley] the breathing stops for a beat.",
     "INTERRUPCION DE PATRON, justo a la mitad, donde cae la retencion."),

    ("S09", 5.9, 0.0, 5.0,
     "CLOSE. A black-gloved hand pressing flat against the thick glass of a "
     "lit aircraft window, seen from outside. Warm yellow light from inside "
     "spills around the fingers. Reflected in the glass, the curved port of "
     "the diving mask.",
     "The hand presses harder and wipes marine growth off the glass in one "
     "slow arc, clearing a view into the cabin. The reflection of the mask "
     "leans in closer.",
     "[Foley] a glove squeaking on wet glass, breathing held. "
     "[SFX] one dull knock from inside the hull.",
     "ESCALERA 3: el contacto. El golpe desde adentro es el gancho del tramo."),

    ("S10", 7.3, 0.0, 6.0,
     "The view through the cleared aircraft window into a lit cabin. Rows of "
     "dry passenger seats in warm yellow light. Every seatbelt is fastened "
     "across an empty seat. Overhead lockers closed. No water inside. No people.",
     "The camera pushes slowly toward the glass and further into the cabin. "
     "Nothing moves inside. Then, far down the aisle, one overhead reading "
     "light clicks on by itself.",
     "[SFX] the electrical hum, a single click of a switch. "
     "[Ambient] the muffled quiet of a dry room heard through glass.",
     "LO IMPOSIBLE. Seco por dentro es el detalle que lo vuelve inexplicable."),

    ("S11", 5.9, 0.0, 5.5,
     "EXTREME CLOSE UP on the diving mask again, the same curved glass port. "
     "The eyes behind it are lit warm yellow now from the window instead of "
     "cold. Wide. The reflection of the lit cabin curves across the glass.",
     "The eyes go wide and hold. Then they shift focus, from what is in front "
     "of the glass to something reflected in it, coming from above and behind.",
     "[Foley] one sharp breath in through the rebreather. [SFX] the hum "
     "dropping away to nothing.",
     "EL PAGO. La voz en off suelta el dato que reordena todo."),

    ("S12", 5.9, 0.0, 5.5,
     "Looking straight UP from the seabed into the black water above. Very far "
     "up, a single small cold light is descending through the dark, alone. It "
     "is the only thing in the frame besides black.",
     "The light above grows slowly larger as it descends toward camera. "
     "Nothing else moves. Frame goes to black before it arrives.",
     "[Foley] breathing, fast and shallow. [SFX] a low tone rising, then cut "
     "to complete silence.",
     "CIERRE EN BUCLE. No cerramos la historia: abrimos una mas grande en el "
     "ultimo segundo. Eso es lo que dispara el rewatch."),
]

# La voz en off, para grabar en ElevenLabs y montar encima. No la genera H3.
VOZ = [
    ("S01", 0.4, "A ochenta metros encontré algo que no debería estar ahí."),
    ("S03", 6.0, "Bajé solo. Nadie sabía que estaba ahí abajo."),
    ("S05", 14.5, "Al principio pensé que era un contenedor."),
    ("S07", 26.5, "No era un contenedor."),
    ("S08", 33.0, "Las luces estaban encendidas."),
    ("S10", 44.0, "Y adentro estaba seco."),
    ("S11", 49.5, "Ese vuelo desapareció hace once años."),
    ("S12", 55.5, "Yo fui el primero en bajar. No el último."),
]


def main():
    storyboard, planos, t = [], [], 0.0

    for sid, seg, ini, fin, ve, mov, aud, funcion in PLANOS:
        length, real = encajar(seg)
        usa = fin - ini

        storyboard.append({
            "id": f"sb_{sid}",
            "aspecto": "9:16",
            "refs": [],
            "prompt": "\n".join([
                FOTO,
                ve,
                f"THE DIVER, identical in every shot: {BUZO}." if "diver" in ve.lower()
                or "hand" in ve.lower() or "mask" in ve.lower() else "",
                "This is a single film frame: no text, no borders, no titles, "
                "no watermark.",
            ]).replace("\n\n", "\n"),
        })

        planos.append({
            "id": sid,
            "escena": "PROFUNDIDAD",
            "tipo": "SHORT",
            "loc": "fondo",
            "personajes": [],
            "length": length,
            "segundos": round(real, 3),
            "usa": [round(ini, 2), round(fin, 2)],
            "en_linea_de_tiempo": [round(t, 2), round(t + usa, 2)],
            "funcion": funcion,
            "first_frame": f"assets/sb_{sid}.png",
            "prompt": "\n".join([
                "Photorealistic cinematic underwater footage, vertical 9:16.",
                f"MOTION: {mov}",
                f"AUDIO: {aud}",
                "NO SPEECH. No voices, no words, no dialogue, no singing, no "
                "crowd chatter. The only sounds are the breathing apparatus, "
                "the water and the structure.",
                "Keep the framing of the first frame. Grainy, cold, "
                "photographic. Not animated, not illustrated, not CGI-looking.",
            ]),
            "dialogo": None,
        })
        t += usa

    (RAIZ / "storyboard.json").write_text(json.dumps(
        {"_comentario": "Vertical 9:16. El aspecto se pide por parametro de la "
                        "API y no por texto: describiendolo en el prompt, nano "
                        "banana devolvio tres relaciones distintas en una tanda.",
         "aspecto": "9:16", "assets": storyboard},
        ensure_ascii=False, indent=2), encoding="utf-8")

    (RAIZ / "planos.json").write_text(json.dumps(
        {"_comentario": "Se generan 75 s para usar 60. H3 no baja de 5.2 s por "
                        "plano y un Short necesita cortes de 1.5 a 2.5 s al "
                        "principio, asi que se recorta en el montaje. Cada "
                        "plano lleva 'usa' con el tramo que va a la linea.",
         "fps": 24, "ancho": 768, "alto": 1344, "planos": planos},
        ensure_ascii=False, indent=2), encoding="utf-8")

    L = ["PROFUNDIDAD — voz en off para ElevenLabs",
         "=" * 46, "",
         "No la genera H3: va grabada aparte y montada encima. Con el regulador",
         "puesto no se ve la boca, asi que no hace falta sincronizar nada, y de",
         "paso la voz queda igual en las ocho lineas.", "",
         "Tono: hombre, 30-40, contando algo que todavia lo perturba. Bajo,",
         "cercano, sin dramatizar. Las pausas hacen mas que las palabras.", ""]
    for sid, seg, txt in VOZ:
        L.append("  %5.1f s  (%s)   %s" % (seg, sid, txt))
    (RAIZ / "voz_en_off.txt").write_text("\n".join(L) + "\n", encoding="utf-8")

    gen = sum(p["segundos"] for p in planos)
    print("PROFUNDIDAD — %d planos" % len(planos))
    print("  se genera ........ %.1f s" % gen)
    print("  se usa ........... %.1f s" % t)
    print("  se descarta ...... %.1f s (%.0f%%)" % (gen - t, (gen - t) / gen * 100))
    print("  costo a 0.83 min/s con 4 placas: $%.2f\n"
          % (gen * 0.83 / 4 / 60 * (297.3 / 166.0)))
    print("  %-5s %-6s %-7s %s" % ("id", "gen", "linea", "funcion"))
    for p in planos:
        a, b = p["en_linea_de_tiempo"]
        print("  %-5s %5.1fs %5.1f-%-5.1f %s"
              % (p["id"], p["segundos"], a, b, p["funcion"][:52]))


if __name__ == "__main__":
    main()
