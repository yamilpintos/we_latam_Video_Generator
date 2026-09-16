# -*- coding: utf-8 -*-
"""El mapa medido de «El amor es una danza peligrosa», episodio 1, como datos.

Réplica para la competencia del 14/9/2026: el original es de ReelShort, hecho
con Kling; la réplica se hace con MiniMax H3. Todo lo de acá sale de medir, no
de estimar:

- **tiempos**: `referencias/danza-peligrosa/tomas.json` (ffmpeg, escenas > 0,20,
  tramos < 0,5 s fundidos), más dos cortes que el detector no vio y se ubicaron
  con cuadros cada 0,2 s: 24,50 s dentro de la toma 14 y 90,90 s dentro de la 60.
- **encuadres**: mirando entrada/medio/salida de cada toma (hoja-01…11.jpg).
  Un encuadre es UNA posición de cámara; varias tomas del mismo encuadre salen
  de un solo clip de H3 con distinto `usa`.
- **líneas**: Whisper medium con tiempos por palabra (`transcripcion.json`). El
  `t0` es cuándo arranca la voz en el original; `en` es la línea en inglés que
  se escribe PARA esa ventana (el original de Kling se filmó en inglés).

La toma 14 (6,21 s) no entra en un clip de 5,17 con colchón: la parte después
del corte escondido se divide en PM y PP, el único corte que la réplica agrega.
"""

DURACION = 126.92

# id, desde, hasta, tamaño, locación, [personajes], encuadre, qué se ve (castellano)
TOMAS = [
    ("01", 0.00, 1.99, "PG", None, [], "E01", "pradera verde con vacas pastando, cielo azul"),
    ("02", 1.99, 3.99, "PD", "campo", ["hannah"], "E02", "piernas en medias y botas texanas caminando sobre el pasto"),
    ("03", 3.99, 5.99, "PD", "campo", ["hannah"], "E03", "torso: cuelga las puntas de ballet de la bolsa de lona"),
    ("04", 5.99, 9.20, "PM", "campo", ["hannah"], "E04", "Hannah camina hacia cámara al atardecer · placa HANNAH THATCHER"),
    ("05", 9.20, 10.70, "PA", "campo", ["hannah"], "E05", "contrapicado de Hannah contra el cielo blanco, ramas secas"),
    ("06", 10.70, 12.66, "PGE", None, [], "E06", "el tren celeste cruza el campo al atardecer, desde lo alto"),
    ("07", 12.66, 13.82, "PD", "cabina_ventana", ["hannah"], "E07", "se ata las puntas sentada en el sillón"),
    ("08", 13.82, 15.32, "PP", "cabina_ventana", ["hannah"], "E08", "Hannah sentada, ojos bajos"),
    ("09", 15.32, 16.41, "PD", "cabina_ventana", ["hannah"], "E09", "pies en punta sobre la alfombra roja, calentadores"),
    ("10", 16.41, 17.66, "PM", "cabina_ventana", ["hannah"], "E10", "contrapicado: brazo arriba, contraluz de ventana"),
    ("11", 17.66, 18.91, "PA", "cabina_ventana", ["hannah"], "E11", "estira sobre la pierna apoyada en la barra"),
    ("12", 18.91, 23.45, "PG", "cabina_ventana", ["hannah"], "E12", "la cabina entera: estira y hace un port de bras"),
    ("13", 23.45, 24.50, "PD", "cabina_ventana", ["hannah"], "E13", "la mano agarra el teléfono del alféizar"),
    ("14a", 24.50, 27.41, "PM", "cabina_ventana", ["hannah"], "E14a", "mira el teléfono, seria"),
    ("14b", 27.41, 30.32, "PP", "cabina_ventana", ["hannah"], "E14b", "mira el teléfono, más cerca"),
    ("15", 30.32, 31.07, "PD", "cabina_puerta", [], "E15", "la puerta de dos hojas se abre de golpe"),
    ("16", 31.07, 32.61, "PG", "cabina_puerta", ["jack_abrigo"], "E16", "Jack avanza con sombrero y sobretodo bajo las arañas"),
    ("17", 32.61, 34.07, "PP", "cabina_puerta", ["jack_abrigo"], "E17", "el ala del sombrero le tapa los ojos, sangre en el cuello"),
    ("18", 34.07, 35.24, "PM", "cabina_ventana", ["hannah"], "E18", "Hannah se da vuelta de la ventana, susto"),
    ("19", 35.24, 37.49, "PM", "cabina_puerta", ["jack_abrigo"], "E16", "Jack llega a cámara y levanta la vista · placa JACK"),
    ("20", 37.49, 38.61, "PM", "cabina_ventana", ["hannah"], "E18", "Hannah contra la ventana, boca abierta"),
    ("21", 38.61, 39.45, "PA", "cabina_puerta", ["jack_abrigo", "hannah"], "E21", "Jack se saca el sombrero; nuca de Hannah en primer término"),
    ("22", 39.45, 40.74, "PP", "cabina_ventana", ["hannah", "jack_abrigo"], "E22", "Hannah grita y la mano enguantada le tapa la boca"),
    ("23", 40.74, 43.28, "PP", "cabina_puerta", ["jack_abrigo", "hannah"], "E23", "Jack con sangre por encima del hombro de ella: «Shh»"),
    ("24", 43.28, 45.32, "PM", "cabina_ventana", ["jack_abrigo", "hannah"], "E24", "los dos contra la ventana, dedo en los labios de ella"),
    ("25", 45.32, 45.86, "PG", "cabina_ventana", ["jack_abrigo", "hannah"], "E25", "la cabina entera: él la acorrala contra la ventana"),
    ("26", 45.86, 46.57, "PD", "cabina_puerta", ["jack_abrigo"], "E26", "la mano enguantada gira el cerrojo de bronce"),
    ("27", 46.57, 48.07, "PM", "cabina_ventana", ["jack_abrigo", "hannah"], "E27", "los dos giran la cabeza hacia la puerta"),
    ("28", 48.07, 48.82, "PA", "cabina_puerta", ["jack_abrigo", "hannah"], "E28", "Jack de espaldas asoma por la cortina; ella fuera de foco"),
    ("29", 48.82, 50.32, "PG", "pasillo", ["pasajeros"], "E29", "pasillo holandés, pasajeros cruzan, un armado al fondo"),
    ("30", 50.32, 53.53, "PM", "pasillo", ["luka"], "E30", "Luka dispara el AK al techo · placa LUKA"),
    ("31", 53.53, 54.99, "PM", "vagon_blanco", ["matones"], "E31", "un matón con AK entra por una puerta blanca"),
    ("32", 54.99, 55.91, "PA", "pasillo", ["luka"], "E36", "Luka en el pasillo, holandés"),
    ("33", 55.91, 56.99, "PM", "pasillo", ["wady"], "E33", "Wady sonriente, pistola en alto · placa WADY"),
    ("34", 56.99, 58.16, "PM", "pasillo", ["pasajeros"], "E34", "pasajera con anteojos grita y huye por una puerta"),
    ("35", 58.16, 59.61, "PA", "vagon_blanco", ["matones"], "E35", "matones de espaldas revisan compartimentos"),
    ("36", 59.61, 60.11, "PA", "pasillo", ["luka"], "E36", "Luka apoyado en la pared del pasillo"),
    ("37", 60.11, 61.86, "PA", "pasillo", ["luka"], "E36", "Luka mira a cámara: «¿En dónde estás?»"),
    ("38", 61.86, 62.61, "PM", "cabina_puerta", ["jack_camisa"], "E38", "Jack de espaldas se saca el sobretodo: tiradores y cartuchera"),
    ("39", 62.61, 63.53, "PM", "cabina_ventana", ["hannah", "jack_camisa"], "E39", "Hannah por detrás del hombro de él, desconcertada"),
    ("40", 63.53, 64.49, "PA", "cabina_puerta", ["jack_camisa", "hannah"], "E40", "Jack gira hacia ella; nuca de ella en primer término"),
    ("41", 64.49, 65.03, "PG", "cabina_ventana", ["jack_camisa", "hannah"], "E41", "la cabina: la alza y ella lo rodea con las piernas"),
    ("42", 65.03, 65.61, "PD", "cabina_ventana", ["jack_camisa", "hannah"], "E42", "espalda de él con tiradores, brazos de ella al cuello"),
    ("43", 65.61, 67.70, "PM", "cabina_ventana", ["hannah", "jack_camisa"], "E43", "la baja; él saca el cuchillo; ella: «¿Qué…?»"),
    ("44", 67.70, 69.28, "PP", "cabina_ventana", ["jack_camisa", "hannah"], "E44", "Jack a tres cuartos, cuchillo en alto: «Shh, shh»"),
    ("45", 69.28, 70.41, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E45", "contrapicado de Hannah: la hoja sobre los labios"),
    ("46", 70.41, 71.78, "PM", "cabina_ventana", ["jack_camisa", "hannah"], "E46", "los dos de perfil cara a cara, cuchillo entre ellos: «Bien»"),
    ("47", 71.78, 73.41, "PP", "cabina_ventana", ["jack_camisa", "hannah"], "E47", "encuadre A: Jack a tres cuartos: «Ahora, gime para mí»"),
    ("48", 73.41, 74.61, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E48", "Hannah de perfil, la hoja delante de la boca"),
    ("49", 74.61, 75.61, "PP", "cabina_ventana", ["jack_camisa", "hannah"], "E49", "encuadre A: «O te corto…»"),
    ("50", 75.61, 76.91, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E48", "Hannah echa la cabeza atrás, la hoja bajo el mentón"),
    ("51", 76.91, 77.95, "PP", "cabina_ventana", ["jack_camisa", "hannah"], "E49", "encuadre A: «…tu lindo cuello»"),
    ("52", 77.95, 79.91, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E52", "encuadre B: Hannah llorando: «Pero no puedo»"),
    ("53", 79.91, 81.03, "PP", "cabina_ventana", ["jack_camisa", "hannah"], "E53", "encuadre A: «¿Cuántos años tienes?»"),
    ("54", 81.03, 82.41, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E54", "encuadre B: «22»"),
    ("55", 82.41, 84.53, "PP", "cabina_ventana", ["jack_camisa", "hannah"], "E55", "encuadre A, sonríe: «Entonces no te hagas la inocente»"),
    ("56", 84.53, 86.70, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E56", "encuadre B, callada, llorando"),
    ("57", 86.70, 88.16, "PM", "cabina_ventana", ["jack_camisa", "hannah"], "E46", "los dos de perfil, él mira hacia la puerta"),
    ("58", 88.16, 89.82, "PA", "vagon_blanco", ["luka", "pasajeros"], "E58", "por detrás de un pasajero pelado, Luka entra por la puerta"),
    ("59", 89.82, 90.90, "PM", "vagon_blanco", ["luka", "pasajeros"], "E59", "Luka empuja al pasajero, que levanta las manos"),
    ("60", 90.90, 91.82, "PG", "pasillo", ["matones", "pasajeros"], "E60", "pasillo holandés: los matones arrinconan pasajeros"),
    ("61", 91.82, 94.11, "PM", "vagon_blanco", ["luka", "wady"], "E61", "Luka furioso, Wady de espaldas: «¡No se escapará otra vez!»"),
    ("62", 94.11, 96.20, "PM", "vagon_blanco", ["wady"], "E62", "Wady asustado: «Jefe, él es la Víbora…»"),
    ("63", 96.20, 98.20, "PM", "vagon_blanco", ["luka", "wady"], "E63", "Luka escucha, Wady de espaldas"),
    ("64", 98.20, 101.11, "PM", "vagon_blanco", ["wady"], "E64", "Wady: «Mató a catorce de nuestros mejores hombres…»"),
    ("65", 101.11, 104.53, "PM", "vagon_blanco", ["luka", "wady"], "E65", "Luka lo agarra del saco: «¡50 millones…»"),
    ("66", 104.53, 106.36, "PM", "pasillo", ["matones"], "E66", "matón pelado con musculosa y AK en el pasillo"),
    ("67", 106.36, 106.99, "PM", "vagon_blanco", ["luka", "wady"], "E63", "Luka empuja a Wady"),
    ("68", 106.99, 107.99, "PA", "vagon_blanco", ["wady", "matones"], "E68", "Wady sale corriendo por la puerta: «¡Vamos, quítense!»"),
    ("69", 107.99, 109.61, "PG", "pasillo", ["matones", "wady"], "E69", "pasillo holandés: los matones corren hacia cámara"),
    ("70", 109.61, 110.99, "PM", "cabina_ventana", ["jack_camisa", "hannah"], "E70", "le baja la camisa del hombro: queda el tirante"),
    ("71", 110.99, 112.32, "PP", "cabina_ventana", ["jack_camisa", "hannah"], "E71", "encuadre A, él mira el hombro de ella"),
    ("72", 112.32, 114.32, "PD", "cabina_ventana", ["hannah", "jack_camisa"], "E72", "la hoja se desliza bajo el tirante"),
    ("73", 114.32, 115.78, "PP", "cabina_ventana", ["jack_camisa", "hannah"], "E73", "encuadre A: «…gimas…»"),
    ("74", 115.78, 116.91, "PM", "cabina_ventana", ["jack_camisa", "hannah"], "E74", "los dos de perfil, la agarra del hombro: «o te haré gemir»"),
    ("75", 116.91, 118.78, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E75", "encuadre B, asiente: «Okay, okay»"),
    ("76", 118.78, 120.61, "PM", "cabina_ventana", ["jack_camisa", "hannah"], "E74", "los dos de perfil, él mira la puerta"),
    # 15/9 (recast): el cuadro de E77 (a horcajadas) lo rechazan GPT y Gemini y no
    # se pudo rehacer con el reparto nuevo; la toma continúa el encuadre E74 (los
    # dos de perfil) para no meter a la actriz original en el medio. En la
    # versión «réplica exacta» era "E77".
    ("77", 120.61, 121.91, "PM", "cabina_ventana", ["jack_camisa", "hannah"], "E74", "ella sentada a horcajadas sobre él, de espaldas (recast: sigue E74)"),
    # 16/9: el inserto de la mano en la cadera daba una lectura sexual junto con el
    # «Ah!» final (el usuario no podía mandar el video así). Se reemplaza por el
    # plano de reacción de ella (E75). En la «réplica exacta» era "E78".
    ("78", 121.91, 122.95, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E75", "mano enguantada en la cadera (recast: reacción de ella, E75)"),
    ("79", 122.95, 123.74, "PA", "cabina_puerta", ["wady"], "E79", "Wady patea la puerta y atraviesa la cortina"),
    ("80", 123.74, 125.11, "PG", "cabina_puerta", ["wady", "matones"], "E80", "POV de la puerta: los armados apuntando"),
    ("81", 125.11, 126.92, "PP", "cabina_ventana", ["hannah", "jack_camisa"], "E81", "Hannah de perfil con la boca abierta: corte"),
]

# Líneas: quién, t0 del original, en qué toma(s) cae, en qué encuadre se ve la
# boca (None = fuera de campo o voz en off), castellano original, inglés.
# `en` se escribe para la ventana: la del original, medida.
LINEAS = [
    # ── voz en off (Hannah): sobre insertos, sin boca
    ("hannah", 2.14, 11.06, None,
     "Antes de morir, mi madre arregló mi matrimonio con Elliott Hargrove para asegurar mi futuro como bailarina de la Compañía de Ballet Hargrove.",
     "Before my mother died, she arranged my marriage to Elliott Hargrove, to secure my future as a dancer with the Hargrove Ballet Company."),
    ("hannah", 11.32, 22.88, None,
     "Contra su voluntad, mi padre y mi madrastra me enviaron a vivir a una granja en Indiana, pero nunca dejé de entrenar, esperando a casarme con Elliott y finalmente vivir el sueño que me robaron.",
     "Against her wishes, my father and stepmother shipped me off to a farm in Indiana. But I never stopped training, waiting to marry Elliott and finally live the dream they stole from me."),
    ("hannah", 24.30, 34.14, None,
     "Papá me quiere en Nueva York para romper mi compromiso, pero no dejaré que arruine mis sueños otra vez.",
     "Dad wants me in New York to break off my engagement. But I won't let him ruin my dreams again."),
    # ── diálogo
    ("hannah", 39.04, 40.72, "E22", "¡Oye! ¿Qué estás…?", "Hey! What are you—"),
    ("jack", 40.72, 41.30, "E23", "¡Shhh!", "Shh."),
    ("luka", 51.56, 53.92, "E30", "¡Que nadie se mueva!", "Nobody move!"),
    ("matones", 58.72, 59.40, None, "¡Víbora!", "Viper!"),
    ("luka", 60.32, 61.64, "E36", "¿En dónde estás?", "Where are you?"),
    ("hannah", 65.60, 67.00, "E43", "¿Qué…?", "What...?"),
    ("jack", 67.00, 68.00, "E44", "Shh, shh…", "Shh, shh..."),
    ("jack", 70.42, 70.90, "E46", "Bien.", "Good."),
    ("jack", 72.10, 73.84, "E47", "Ahora, gime para mí.", "Now moan for me."),
    ("jack", 75.32, 77.78, "E49", "O… te corto tu lindo cuello.", "Or... I cut that pretty throat."),
    ("hannah", 77.96, 80.16, "E52", "Pero no puedo, no sé cómo…", "But I can't... I don't know how..."),
    ("jack", 80.16, 81.04, "E53", "¿Cuántos años tienes?", "How old are you?"),
    ("hannah", 81.50, 82.14, "E54", "Veintidós.", "Twenty-two."),
    ("jack", 82.80, 85.10, "E55", "Entonces no te hagas la inocente.", "Then don't play innocent."),
    ("luka", 91.52, 93.90, "E61", "¡No! ¡Se escapará otra vez!", "No! He's not getting away again!"),
    ("wady", 93.90, 98.02, "E62", "Jefe, él es la Víbora, el asesino más letal del planeta.", "Boss, he's the Viper. The deadliest killer on the planet."),
    ("wady", 98.42, 101.36, "E64", "Mató a catorce de nuestros mejores hombres y no pudimos hacer nada.", "He took out fourteen of our best men and we couldn't do a thing."),
    ("luka", 101.56, 106.40, "E65", "Si no puedes hacerlo, ¡cincuenta millones para quien me traiga la cabeza de Víbora!", "If you can't do it, fifty million to whoever brings me the Viper's head!"),
    ("wady", 107.02, 109.50, "E68", "De acuerdo. ¡Vamos, quítense! ¡Vamos!", "Okay. Move! Out of the way! Go!"),
    ("jack", 113.52, 115.40, "E73", "Dije que… gimas…", "I said... moan..."),
    ("jack", 116.20, 117.26, "E74", "…o te haré gemir.", "...or I'll make you."),
    ("hannah", 118.68, 119.62, "E75", "Ok, ok.", "Okay, okay."),
    ("hannah", 124.58, 125.98, "E81", "¡Ah!", "Ah!"),
]

# Placas de nombre del original: van en post, en serif itálica (regla 20).
PLACAS = [
    (5.99, 9.20, "HANNAH THATCHER"),
    (35.24, 37.49, 'JACK "THE VIPER" HARGROVE'),
    (50.32, 53.53, "LUKA RIVALCHEK"),
    (55.91, 56.99, "WADY POLANSKI"),
]
