# Mapa medido — «El amor es una danza peligrosa», episodio 1 (doblado)

Referencia del short de la Cobra en el tren (pedido del 14/9/2026). **Es un
episodio de ReelShort** (marca «R» en todo el cuadro): Hannah Thatcher, Jack
«The Viper» Hargrove, Elliott Hargrove, ballet. El guion del usuario es la
adaptación: Martina, Julián «la Cobra» Bianchi, Elías Bianchi, tango.

Nada de esto es estimado. Los cortes salen de ffmpeg (`select=gt(scene,0.20)`
→ `escenas.txt`), con los tramos de menos de 0,5 s sumados a la toma anterior
(`tomas.py` → `tomas.json`). El contenido de cada toma sale de mirar los tres
cuadros (entrada, medio y salida) en `hoja-01.jpg` … `hoja-11.jpg`. Los
diálogos salen de los subtítulos quemados del original, y los tiempos, de
Whisper (`transcripcion.txt`).

## La ficha

| | |
|---|---|
| archivo | `Video realshort/Episodio 1 - [doblado] El amor es una danza peligrosa.mp4` |
| duración | **126,92 s** |
| cuadro | 720×1280, 9:16 a sangre (sin barras), 24 fps |
| tomas | **81** · media **1,57 s** · mín 0,50 · máx 6,21 |
| audio | estéreo 44,1 kHz · **−11,9 LUFS** integrado · LRA 12,1 LU · pico **+2,08 dBFS** (clipeado, como H3) |
| música | **continua**: ni un silencio de 0,3 s por debajo de −30 dB en todo el episodio |
| subtítulos | quemados: blancos, negrita, sin caja, centrados en el tercio medio-inferior |
| placas de nombre | cuatro, en serif itálica blanca grande sobre la imagen, a la presentación de cada personaje |

Contra lo que ya medimos: @jcfdlw corta a 2,36 s; **este corta a 1,57 s**.
Nosotros, a 5,7 s.

## Los bloques dramáticos

| bloque | tomas | tiempo | qué pasa | cómo se cuenta |
|---|---|---|---|---|
| 1 · El pasado | 1-11 | 0,0-18,9 | vacas, botas, bolsa con puntas, tren por el campo, calentamiento en la cabina | **voz en off** de Hannah sobre montaje de 1-2 s; placa HANNAH THATCHER |
| 2 · La llamada | 12-14 | 18,9-30,3 | estira en la barra, el teléfono suena, lo mira | voz en off; la única toma larga del episodio (6,21 s) |
| 3 · Entra la Víbora | 15-24 | 30,3-45,3 | puerta, Jack de sombrero por el pasillo de lujo, ella se da vuelta, él le tapa la boca, «Shh» | placa JACK «THE VIPER» HARGROVE; primer diálogo |
| 4 · Cierra | 25-28 | 45,3-48,8 | la acorrala contra la ventana, **mano enguantada gira el cerrojo**, los dos miran la puerta | sin diálogo |
| 5 · Los matones | 29-37 | 48,8-61,9 | pasillo en **plano holandés**, Luka con AK, pasajeros que huyen, «¡Que nadie se mueva!», «¡Víbora!», «¿En dónde estás?» | placas LUKA RIVALCHEK y WADY POLANSKI |
| 6 · La levanta | 38-42 | 61,9-65,6 | se saca el saco (tiradores y cartuchera), «¿Qué?», **la alza a horcajadas** | |
| 7 · El cuchillo | 43-57 | 65,6-88,2 | «Shh», cuchillo en los labios, «Ahora, gime para mí», «O te corto tu lindo cuello», «Pero no puedo, no sé cómo», «¿Cuántos años tienes?», «22», «Entonces no te hagas la inocente» | **plano y contraplano** con dos encuadres que se alternan |
| 8 · La recompensa | 58-69 | 88,2-109,6 | Luka empuja a un pasajero, «¡No se escapará otra vez!», Wady: «es el asesino más letal, mató a catorce…», Luka: «¡50 millones para quien me traiga la cabeza de Víbora!», «De acuerdo», «¡Vamos, quítense!» | vagón blanco de día, cámara en mano |
| 9 · El tirante | 70-78 | 109,6-122,9 | le baja la camisa del hombro, **corta el tirante con el cuchillo**, «gimas o te haré gemir», «Okay, okay», se abrazan sentados, mano en la cadera | vuelve el plano y contraplano |
| 10 · La patada | 79-81 | 122,9-126,9 | Wady patea la cortina/puerta, entran seis armados apuntando, **ella de perfil con la boca abierta**: corte | cliffhanger en la cara |

## Las 81 tomas

Tamaños: PGE PG PA PM PP PD. «OTS» = por encima del hombro.

| # | desde | dura | tam | qué se ve | se dice |
|---|---|---|---|---|---|
| 01 | 0,00 | 1,99 | PG | pradera, vacas pastando, cielo azul | |
| 02 | 1,99 | 2,00 | PD | piernas en medias blancas y botas texanas bordadas caminando sobre pasto | «Antes de morir, mi madre arregló mi matrimonio» |
| 03 | 3,99 | 2,00 | PD | torso: leotardo rosa sucio, camisa de franela, cuelga las puntas de ballet de la bolsa | |
| 04 | 5,99 | 3,21 | PM | Hannah camina hacia cámara, atardecer, postes de luz; **placa HANNAH THATCHER** | «con Elliott Hargrove para asegurar mi futuro como bailarina de la Compañía de Ballet Hargrove» |
| 05 | 9,20 | 1,50 | PA | contrapicado de Hannah contra el cielo blanco, ramas secas | |
| 06 | 10,70 | 1,96 | PGE | tren celeste por el campo al atardecer, desde lo alto | «Contra su voluntad,» |
| 07 | 12,66 | 1,17 | PD | se ata las puntas sentada en el sillón de terciopelo de la cabina | «mi padre y mi madrastra» |
| 08 | 13,82 | 1,50 | PP | Hannah sentada, ojos bajos, cortina a rayas | «me enviaron a vivir a una granja en Indiana,» |
| 09 | 15,32 | 1,08 | PD | pies en punta sobre la alfombra roja, calentadores rosas, ventana | |
| 10 | 16,41 | 1,25 | PM | contrapicado: brazo arriba estirando, contraluz de ventana | «pero nunca dejé de entrenar,» |
| 11 | 17,66 | 1,25 | PM | estira sobre la pierna apoyada en la barra, cortina de encaje | |
| 12 | 18,91 | 4,54 | PG | la cabina entera: sillón mostaza, barra de bronce, dos ventanas; estira y hace un port de bras | «esperando a casarme con Elliott y finalmente vivir el sueño» |
| 13 | 23,45 | 0,67 | PD | la mano agarra el teléfono del alféizar | |
| 14 | 24,11 | 6,21 | PM | mira el teléfono, cara seria | «[papá llama] para romper mi compromiso, … que arruine mis sueños otra vez» |
| 15 | 30,32 | 0,75 | PD | puerta de madera de dos hojas: se abre de golpe hacia cámara | [disparos] |
| 16 | 31,07 | 1,54 | PG | Jack avanza por el salón-vagón de lujo: sombrero negro, sobretodo, arañas doradas, guirnaldas rojas | |
| 17 | 32,61 | 1,46 | PP | el sombrero le tapa los ojos, sangre en el cuello | |
| 18 | 34,07 | 1,17 | PM | Hannah se da vuelta de la ventana, susto | |
| 19 | 35,24 | 2,25 | PM→PP | Jack camina hacia cámara y levanta la vista; **placa JACK «THE VIPER» HARGROVE** | |
| 20 | 37,49 | 1,12 | PM | Hannah contra la ventana, boca abierta | «Oye, ¿qué estás…?» |
| 21 | 38,61 | 0,83 | PA OTS | Jack se saca el sombrero; nuca de Hannah en primer término | |
| 22 | 39,45 | 1,29 | PP | Hannah grita y **la mano enguantada le tapa la boca** | |
| 23 | 40,74 | 2,54 | PP OTS | Jack con sangre en la frente, sobre el hombro de ella | «Shh.» |
| 24 | 43,28 | 2,04 | PM | los dos contra la ventana, **dedo en los labios de ella** | |
| 25 | 45,32 | 0,54 | PG | la cabina entera: él la acorrala contra la ventana | |
| 26 | 45,86 | 0,71 | PD | mano enguantada gira el cerrojo de bronce | |
| 27 | 46,57 | 1,50 | PM | los dos giran la cabeza hacia la puerta | |
| 28 | 48,07 | 0,75 | PA OTS | Jack de espaldas asoma por la cortina; ella en primer término, fuera de foco | |
| 29 | 48,82 | 1,50 | PG | pasillo en plano holandés, pasajeros que cruzan fuera de foco, un armado al fondo | |
| 30 | 50,32 | 3,21 | PM | **Luka** en contrapicado holandés dispara el AK al techo (fogonazo); **placa LUKA RIVALCHEK** | «¡Que nadie se mueva!» |
| 31 | 53,53 | 1,46 | PM | matón con AK entra por una puerta blanca | |
| 32 | 54,99 | 0,92 | PA | Luka en el pasillo, holandés | |
| 33 | 55,91 | 1,08 | PM | **Wady**, rubio, sonriente, pistola en alto; **placa WADY POLANSKI** | |
| 34 | 56,99 | 1,17 | PM | pasajera con anteojos grita y huye por una puerta | |
| 35 | 58,16 | 1,46 | PA | matones de espaldas revisan compartimentos; uno pelado con tatuajes | «¡Víbora!» |
| 36 | 59,61 | 0,50 | PA | Luka apoyado en la pared del pasillo | |
| 37 | 60,11 | 1,75 | PA | Luka mira hacia cámara, holandés | «¿En dónde estás?» |
| 38 | 61,86 | 0,75 | PM | Jack de espaldas se saca el sobretodo: camisa blanca, tiradores y cartuchera | |
| 39 | 62,61 | 0,92 | PM OTS | Hannah por detrás del hombro de él, desconcertada | |
| 40 | 63,53 | 0,96 | PA OTS | Jack gira hacia ella | «¿Qué?» |
| 41 | 64,49 | 0,54 | PG | la cabina: **la alza, ella lo rodea con las piernas** | |
| 42 | 65,03 | 0,58 | PD | espalda de él, tiradores, brazos de ella en el cuello | |
| 43 | 65,61 | 2,08 | PM | la baja; él saca el cuchillo | «Shh, shh…» |
| 44 | 67,70 | 1,58 | PP | Jack de perfil a tres cuartos, cuchillo en alto | |
| 45 | 69,28 | 1,12 | PP | contrapicado de Hannah: la hoja negra sobre los labios | «Shh.» |
| 46 | 70,41 | 1,38 | PM | los dos de perfil, cara a cara, cuchillo entre los dos | «Bien.» |
| 47 | 71,78 | 1,62 | PP | **encuadre A**: Jack a tres cuartos, cortina a rayas detrás | «Ahora, gime para mí.» |
| 48 | 73,41 | 1,21 | PP | Hannah de perfil, la hoja delante de la boca | |
| 49 | 74,61 | 1,00 | PP | encuadre A | «O te corto tu lindo cuello.» |
| 50 | 75,61 | 1,29 | PP | Hannah echa la cabeza atrás, la hoja bajo el mentón | |
| 51 | 76,91 | 1,04 | PP | encuadre A | |
| 52 | 77,95 | 1,96 | PP | **encuadre B**: contrapicado de Hannah llorando, cuchillo en el cuello, techo de madera | «Pero no puedo. No… no sé cómo.» |
| 53 | 79,91 | 1,12 | PP | encuadre A | «¿Cuántos años tienes?» |
| 54 | 81,03 | 1,38 | PP | encuadre B | «22.» |
| 55 | 82,41 | 2,12 | PP | encuadre A, sonríe | «Entonces no te hagas la inocente.» |
| 56 | 84,53 | 2,17 | PP | encuadre B | |
| 57 | 86,70 | 1,46 | PM | los dos de perfil, él mira hacia la puerta | |
| 58 | 88,16 | 1,67 | PA OTS | por detrás de un pasajero pelado, Luka entra por la puerta | |
| 59 | 89,82 | 0,71 | PM | Luka empuja al pasajero, que levanta las manos | |
| 60 | 90,53 | 1,29 | PM→PG | Luka avanza; pasillo holandés con matones | «¡No se escapará otra vez!» |
| 61 | 91,82 | 2,29 | PM OTS | Luka furioso, Wady de espaldas en primer término; vagón blanco | |
| 62 | 94,11 | 2,08 | PM | Wady asustado | «Jefe, él es la Víbora, el asesino más letal» |
| 63 | 96,20 | 2,00 | PM OTS | Luka | |
| 64 | 98,20 | 2,92 | PM | Wady gesticula | «Mató a catorce de nuestros mejores hombres y no pudimos hacer nada…» |
| 65 | 101,11 | 3,42 | PM OTS | Luka lo agarra del saco | «Si no puedes hacerlo, ¡50 millones para quien me traiga…» |
| 66 | 104,53 | 1,83 | PM | matón pelado con musculosa y AK, tatuajes, en el pasillo | «…la cabeza de Víbora!» |
| 67 | 106,36 | 0,62 | PM OTS | Luka empuja a Wady | |
| 68 | 106,99 | 1,00 | PA | Wady sale corriendo por la puerta | «De acuerdo. ¡Vamos, quítense!» |
| 69 | 107,99 | 1,62 | PG | pasillo holandés: los matones corren hacia cámara | «¡Vamos!» |
| 70 | 109,61 | 1,38 | PM | le baja la camisa del hombro: queda el tirante del leotardo | |
| 71 | 110,99 | 1,33 | PP | encuadre A, él mira el hombro de ella | |
| 72 | 112,32 | 2,00 | PD | **el cuchillo corta el tirante** | |
| 73 | 114,32 | 1,46 | PP | encuadre A | «gimas o te haré gemir.» |
| 74 | 115,78 | 1,12 | PP | los dos de perfil, él la agarra del hombro | |
| 75 | 116,91 | 1,88 | PP | encuadre B, ella asiente | «Okay, okay.» |
| 76 | 118,78 | 1,83 | PP | los dos de perfil, él mira la puerta | |
| 77 | 120,61 | 1,29 | PA | ella sentada a horcajadas sobre él, de espaldas, él la abraza | |
| 78 | 121,91 | 1,04 | PD | mano enguantada en la cadera sobre el short de jean | |
| 79 | 122,95 | 0,79 | PA | Wady patea la puerta, borroso | [patada] |
| 80 | 123,74 | 1,38 | PG | POV de la puerta: seis armados apuntando, arañas doradas | |
| 81 | 125,11 | 1,81 | PP | ella de perfil con la boca abierta, él con la cara en su cuello | [corte] |

## La voz, medida (Whisper medium, tiempos por palabra)

| quién | línea | desde | dura | cps |
|---|---|---|---|---|
| Hannah, en off | «Antes de morir, mi madre arregló mi matrimonio… Ballet Hargrove.» | 2,14 | 8,92 | **15,7** |
| Hannah, en off | «Contra su voluntad… el sueño que me robaron.» | 11,32 | 11,56 | **16,6** |
| Hannah, en off | «Papá me quiere en Nueva York… otra vez.» | 24,30 | 9,84 | 10,5 (con pausa) |
| Hannah | «¡Oye! ¿Qué estás…?» | 39,04 | 1,68 | 11,3 |
| Jack | «¡Shhh!» | 40,72 | 0,58 | — |
| matón | «¡Cuidado! ¡Se mueve!» | 51,56 | 2,36 | 8,5 |
| Luka | «¡Víbora! ¿Dónde estás?» | 58,72 | 2,92 | 7,5 |
| Hannah | «¿Qué…?» | 65,60 | 1,40 | — |
| Jack | «Bien, ahora gime para mí.» | 70,42 | 3,42 | **7,3** |
| Jack | «O… te corto tu lindo cuello.» | 75,32 | 2,46 | 12,2 |
| Hannah | «Pero no puedo, no sé cómo…» | 77,96 | 2,20 | 12,7 |
| Jack | «¿Cuántos años tienes?» | 80,16 | 0,88 | 23,9 |
| Hannah | «Veintidós.» | 81,50 | 0,64 | 15,6 |
| Jack | «Entonces no te hagas la inocente.» | 82,80 | 2,30 | 14,3 |
| Luka | «¡No! ¡Se escapará otra vez!» | 91,52 | 2,38 | 11,3 |
| Wady | «Jefe, él es la Víbora, el asesino más letal del planeta.» | 93,90 | 4,12 | 13,6 |
| Wady | «Mató a catorce de nuestros mejores hombres y no pudimos hacer nada.» | 98,42 | 2,94 | **22,8** |
| Luka | «Si no puedes hacerlo, ¡cincuenta millones para quien me traiga la cabeza de Víbora!» | 101,56 | 4,84 | 17,1 |
| Wady | «De acuerdo. ¡Vamos, quítense! ¡Vamos!» | 107,02 | 2,48 | 14,9 |
| Jack | «Dije que… gimas… o te haré gemir.» | 113,52 | 3,74 | **9,9** |
| Hannah | «Ok, ok.» | 118,68 | 0,94 | — |
| Hannah | «¡Ah!» | 124,58 | 1,40 | — |

- **La voz en off corre a 15,7-16,6 cps: la velocidad de Kate** (16,7). En este
  formato sí llegamos, a diferencia de @jcfdlw (22,7).
- **El héroe habla lento** (7-12 cps, con pausas de susurro) y **los villanos,
  rápido** (13-23 cps, a los gritos). La velocidad es parte del personaje: se
  escribe así, no se deja al azar del TTS.
- De los 127 s hay ~30 s de voz en off, ~40 s de diálogo y el resto es acción
  con música.

## Lo que sirve para nuestro video

1. **El plano y contraplano se arma con dos encuadres.** Las tomas 47-56 (10
   tomas en 16,5 s) alternan sólo el encuadre A (Jack) y el B (Hannah en
   contrapicado). Para H3 eso es `clip_de`: **un clip de 5,17 s por encuadre**,
   del que se usan varios pedazos de ~1-2 s. La escena del cuchillo entera cabe
   en 4-5 clips.
2. **Una línea por toma, cortísima.** «Shh.» «Bien.» «22.» «Ahora, gime para
   mí.» Casi ninguna pasa de 2 s. Con boca en cámara eso le conviene a la
   isocronía: la ventana es chica y el error de densidad del 30 % son décimas.
3. **Las placas de nombre van en post**, en serif itálica, a la entrada de
   cada personaje (regla 20). Son cuatro y ordenan el reparto sin diálogo.
4. **El plano holandés es el lenguaje de los villanos.** Todo el pasillo de
   Luka va torcido; la cabina de Hannah, derecha. Se pide en el dibujo.
5. **Dos mundos de luz**: la cabina, cálida, de madera roja, con contraluz de
   ventana blanca y cortinas de encaje; el vagón de Luka, blanco, frío, de día.
   Es la interrupción de patrón que se ve sola al cortar.
6. **La música no para nunca** y el máster está fuerte (−11,9 LUFS).
   Nosotros vamos a −14: YouTube baja lo que está más fuerte.
7. **El final es una cara, no la puerta.** Corta en la boca abierta de ella con
   los armados entrando. El POV de los armados es la penúltima toma.
8. **La voz en off sólo existe en los primeros 30 s**, sobre montaje de
   insertos (botas, puntas, pies en punta) donde no se ve ninguna boca. Después
   todo es diálogo en cámara.
9. **Lo que no se copia**: el tirante cortado y el desnudo implícito (tomas
   70-78). No entran por nano banana ni por las políticas de las plataformas,
   y el guion del usuario funciona sin eso.
