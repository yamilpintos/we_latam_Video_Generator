"""
Plan de la Capa E: ambientes, música y efectos puntuales.

Fuente única de verdad. El documento 07-sfx.md y el generador sfx_generate.py
salen de acá, así que no pueden desincronizarse.

Arquitectura de pistas (ver pipeline/07-CAPA-E-sfx.md):
    A1  voz        -16 LUFS    manda
    A2  música     -26 / -18   ducking contra A1
    A3  ambiente   -34 / -28   nunca se corta en seco
    A4  spot FX    -22 / -10   anclados a frame exacto

Principio del ambiente: sigue la LOCACIÓN NARRATIVA, no la del plano. Los planos
espaciales dentro del cold open son insertos dentro de una escena de sala de
control, así que el room tone de la sala corre por debajo de todos. Cortar el
ambiente en cada plano es lo que hace que un video suene a diapositivas.
"""

# ── A3 · ambientes ────────────────────────────────────────────────────────────
# (id, in, out, nivel_dB, prompt)  ·  se cruzan con fade de 1,2 s
DRONE = ("DRONE_BASE", 0.0, 300.0, -36,
         "drone subgrave continuo y casi inaudible, 45 hercios, sin melodía ni ritmo, "
         "textura de vacío, estable, sin variación")

AMBIENTES = [
    ("AMB_SALA", 0.0, 65.0, -28,
     "room tone de sala de control de misión en los años noventa: aire acondicionado "
     "constante, zumbido grave de muchos monitores de tubo, un teclado lejano, "
     "murmullo apagado, sin voces distinguibles"),
    ("AMB_REUNION", 65.0, 95.0, -30,
     "room tone de sala de reuniones institucional cerrada: aire acondicionado suave, "
     "leve eco de espacio con moqueta, sin voces, sensación de encierro"),
    ("AMB_ESPACIO", 95.0, 170.0, -32,
     "ambiente de vacío espacial: subgrave profundo y hueco con una resonancia metálica "
     "muy lejana, sin viento, sin aire, sensación de inmensidad y ausencia"),
    ("AMB_OFICINA", 170.0, 250.0, -29,
     "room tone de oficina técnica de los años noventa durante el día: ventiladores de "
     "computadora, un fluorescente con zumbido leve, actividad lejana de papel, "
     "sin voces distinguibles"),
    ("AMB_NOCHE", 250.0, 275.0, -32,
     "room tone de oficina vacía de madrugada: solo el aire acondicionado y un zumbido "
     "eléctrico muy tenue, silencio pesado, sensación de soledad"),
    ("AMB_FINAL", 275.0, 300.0, -32,
     "ambiente de vacío espacial que se va abriendo: subgrave profundo con una cola "
     "de resonancia larga, sin ritmo, sensación de distancia infinita"),
]

# ── A2 · música ───────────────────────────────────────────────────────────────
# (id, in, out, fade_in, fade_out, nivel_dB, prompt)
MUSICA = [
    ("MUS_01", 2.0, 65.0, 3.0, 3.5, -26,
     "Documental cinematográfico, tono de misterio contenido. Drone grave en La menor con "
     "cello sostenido y un motivo simple de piano preparado que aparece cada tanto. "
     "Sin percusión, sin batería, sin melodía protagonista. Textura fría y espaciosa, "
     "deja aire para una voz en off."),
    ("MUS_02", 65.0, 170.0, 3.0, 3.0, -26,
     "Documental de investigación, tensión que crece muy despacio. Base de cuerdas graves "
     "sostenidas con un pulso rítmico sutil y regular que entra de a poco, como un reloj "
     "lejano. Capas que se van sumando sin llegar a clímax. Sin batería fuerte. "
     "Deja espacio en el medio para una voz."),
    ("MUS_03", 170.0, 250.0, 2.5, 3.0, -25,
     "Documental técnico, tensión sostenida e incómoda. Cuerdas en disonancia leve, un "
     "arpegio electrónico frío y repetitivo, pulso constante que no resuelve. Sensación "
     "de mecanismo funcionando mal. Sin percusión épica, sin coros."),
    ("MUS_04", 250.0, 296.0, 3.0, 0.0, -24,
     "Documental, cierre de acto con peso emocional. Cuerdas graves que crecen hacia un "
     "punto de máxima tensión y quedan suspendidas sin resolver. Un piano solo en las "
     "últimas notas. Sin percusión. Termina sin resolución armónica, dejando la frase abierta."),
]

# ── A4 · efectos puntuales ────────────────────────────────────────────────────
# (id, ancla_seg, duracion, nivel_dB, plano, prompt)
SPOTS = [
    # S01 · cold open (0-35)
    ("SFX_01",   0.3, 3.0, -24, "S01-P01", "sala de control: teclas de un teclado mecánico de los noventa, pocas y espaciadas, lejanas"),
    ("SFX_02",   3.2, 2.5, -20, "S01-P01", "zumbido eléctrico grave de un monitor de tubo que sube ligeramente de tono"),
    ("SFX_03",   8.0, 3.0, -16, "S01-P02", "tono continuo de telemetría, señal electrónica limpia y estable, como un monitor cardíaco"),
    ("SFX_04",  12.5, 1.4, -12, "S01-P02", "un tono electrónico continuo que se corta de golpe y deja un clic seco, luego nada"),
    ("SFX_05",  15.2, 2.5, -22, "S01-P03", "sala grande con gente inmóvil: solo aire acondicionado y una silla de oficina que cruje una vez"),
    ("SFX_06",  20.2, 2.5, -20, "S01-P04", "zumbido grave y hueco de estructura metálica en el vacío, muy tenue"),
    ("SFX_07",  27.0, 1.6, -14, "S01-P04", "impacto sordo y grave, corto, con una cola de resonancia larga"),
    # S02 · la versión famosa (35-65)
    ("SFX_08",  35.2, 1.6, -18, "S02-P01", "una hoja de periódico que se asienta sobre una mesa de fórmica"),
    ("SFX_09",  40.2, 2.2, -19, "S02-P02", "dos piezas metálicas finas deslizándose una sobre otra, con dos clics de tope"),
    ("SFX_10",  43.5, 0.9, -14, "S02-P02", "un clic metálico seco y desafinado, como una pieza que no encaja"),
    ("SFX_11",  45.3, 2.6, -18, "S02-P03", "tiza escribiendo sobre un pizarrón, dos trazos cortos y firmes"),
    ("SFX_12",  50.3, 2.0, -21, "S02-P04", "una puerta pesada que se cierra al final de un pasillo lejano, con eco"),
    ("SFX_13",  53.9, 1.5, -17, "S02-P04", "un monitor de tubo que se apaga: el chasquido de desmagnetización y el zumbido que decae"),
    # S03 · la promesa (65-95)
    ("SFX_14",  65.2, 1.4, -17, "S03-P01", "una carpeta gruesa de anillas que se apoya sobre una mesa de madera"),
    ("SFX_15",  70.2, 4.2, -18, "S03-P02", "nueve clics electrónicos cortos y secos, espaciados de forma regular, tono de terminal"),
    ("SFX_16",  85.2, 2.4, -23, "S03-P04", "murmullo de varias personas hablando bajo en una sala cerrada, que se apaga de golpe"),
    ("SFX_17",  90.2, 3.0, -20, "S03-P05", "siseo constante de aire filtrado a presión en una sala limpia, muy estéril"),
    # S04 · el lanzamiento (95-130)
    ("SFX_18", 100.2, 3.5, -21, "S04-P02", "viento marciano lejano y enrarecido, muy tenue, con partículas de polvo fino"),
    ("SFX_19", 105.2, 2.2, -20, "S04-P03", "hielo sucio crujiendo levemente por el frío, tics irregulares y secos"),
    ("SFX_20", 110.0, 3.0, -14, "S04-P04", "ignición de un motor de cohete grande: el estallido inicial y el rugido que crece"),
    ("SFX_21", 111.6, 7.5, -10, "S04-P04", "rugido masivo y grave de un cohete despegando, con crepitación de baja frecuencia"),
    ("SFX_22", 119.6, 1.2, -13, "S04-P06", "un rugido enorme que se corta abruptamente y deja un silencio con presión en los oídos"),
    ("SFX_23", 120.2, 2.8, -19, "S04-P05", "barrido electrónico ascendente que traza una línea, tono de instrumento científico"),
    # S05 · las ruedas (130-170)
    ("SFX_24", 135.1, 9.0, -17, "S05-P02", "zumbido agudo de un volante de inercia girando a alta velocidad, que sube de tono y se estabiliza"),
    ("SFX_25", 145.2, 3.5, -19, "S05-P03", "el mismo zumbido de volante pero más cerca y apagado, con una vibración mecánica grave"),
    ("SFX_26", 150.1, 9.0, -13, "S05-P04", "seis pulsos de gas comprimido muy cortos y secos, espaciados de forma irregular, en el vacío"),
    ("SFX_27", 160.2, 3.2, -20, "S05-P05", "dos tonos electrónicos opuestos, uno ascendente y otro descendente, superpuestos"),
    ("SFX_28", 165.2, 2.6, -19, "S05-P06", "metal caliente enfriándose: tics irregulares de contracción térmica"),
    # S06 · el archivo (170-210)
    ("SFX_29", 170.2, 3.5, -20, "S06-P01", "servomotor pesado ajustando la posición de una antena grande, con viento de noche detrás"),
    ("SFX_30", 185.1, 2.0, -17, "S06-P03", "tono de terminal antiguo que aparece con un cursor parpadeando"),
    ("SFX_31", 190.1, 2.4, -14, "S06-P04", "un tono electrónico que salta bruscamente a otra altura, más agudo, con un clic entre medio"),
    ("SFX_32", 195.2, 4.0, -19, "S06-P05", "datos corriendo en una pantalla de fósforo: clics rápidos y regulares de refresco"),
    ("SFX_33", 200.1, 1.6, -12, "S06-P06", "impacto sordo y grave, corto, como un sello que cae sobre metal"),
    ("SFX_34", 205.2, 4.2, -15, "S06-P07", "impresora matricial de los noventa imprimiendo en papel continuo, ruido característico"),
    # S07 · el panel (210-250)
    ("SFX_35", 215.1, 3.8, -21, "S07-P02", "siseo suave y continuo que crece muy despacio, como radiación o presión aumentando"),
    ("SFX_36", 232.6, 1.1, -11, "S07-P04", "un sello de goma golpeando con fuerza sobre una hoja de papel apoyada en madera"),
    ("SFX_37", 235.2, 3.0, -22, "S07-P05", "dos personas conversando en voz baja en una oficina, sin palabras distinguibles, y papel de plano que se mueve"),
    ("SFX_38", 240.1, 4.0, -18, "S07-P06", "dos tonos electrónicos ascendentes: uno se detiene en seco, el otro sigue subiendo sin parar"),
    ("SFX_39", 245.2, 3.4, -17, "S07-P07", "interruptores de luz fluorescente apagándose uno tras otro por un pasillo largo, con eco"),
    # S08 · ya lo veían (250-275)
    ("SFX_40", 250.1, 4.5, -18, "S08-P01", "muchos clics diminutos que se van acumulando y densificando hasta formar una masa sonora"),
    ("SFX_41", 255.2, 1.8, -17, "S08-P02", "un bolígrafo tachando con fuerza sobre papel, dos trazos cruzados"),
    ("SFX_42", 260.2, 3.0, -24, "S08-P03", "oficina vacía de madrugada: solo el aire acondicionado y el segundero de un reloj de pared"),
    ("SFX_43", 270.2, 2.0, -19, "S08-P05", "una hoja de papel continuo que se pasa y se alisa con la mano"),
    # S09 · invisible (275-300)
    ("SFX_44", 275.2, 1.8, -18, "S09-P01", "una silla de oficina que cruje al reclinarse hacia atrás"),
    ("SFX_45", 290.1, 3.2, -16, "S09-P03", "un tono electrónico que se descompone en dos: uno se mantiene y el otro se desvanece"),
    ("SFX_46", 295.0, 4.5, -19, "S09-P04", "subgrave que crece muy lentamente hacia el silencio, sin resolver"),
]

DUCK = {"reduccion_db": 6.0, "attack_ms": 10, "release_ms": 400, "ratio": 4.0}
MASTER = {"lufs": -14.0, "true_peak_dbtp": -1.0}
