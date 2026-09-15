# Réplica de 7678030150944001310 (@jcfdlw) — benchmark interno

**No se publica.** El guion es de ellos. Esto existe para contestar una sola
pregunta: *¿puede nuestro pipeline producir lo mismo?* Se compara lado a lado
con el original y se tira.

Original: `referencias/jcfdlw/7678030150944001310.mp4` · 3:01 · 48.300 vistas ·
https://www.tiktok.com/@jcfdlw/video/7678030150944001310

## Qué se replica y qué no

| | |
|---|---|
| texto | **idéntico**, las 92 líneas del `.txt`, literal, sin tocar una coma |
| tiempos de cada toma | **idénticos**, medidos con ffmpeg (ver `MAPA-ORIGINAL.md`) |
| contenido de cada imagen | **el mismo**: mismo encuadre, misma gente, misma acción |
| las imágenes en sí | **lo único que cambia**: generadas por nosotros |
| voz | Kate, la nuestra — no se clona la de ellos |

## Los archivos

| | |
|---|---|
| `tomas.py` | el mapa medido: 77 tomas con inicio, fin, tamaño, locación y qué se ve |
| `mapa.py` → `MAPA-ORIGINAL.md` | el mapa legible, con la transcripción encima de cada toma |
| `armar.py` → `proyecto.json` | los 79 planos y las 92 líneas, generados desde el mapa |
| `desvio_voz.py` → `DESVIO-VOZ.md` | cuánto se pasa nuestra voz de la ventana de cada frase |
| `mezclar_replica.py` | el máster, para después de bajar los clips de Vast |

`proyecto.json` **no se edita a mano**: sale de `armar.py`. Si hay que corregir
una toma se corrige en `tomas.py` o en `armar.py` y se vuelve a generar, porque
el timing tiene que seguir siendo el del original al centésimo.

## Cómo se midió (nada de esto es estimado)

1. **Duración**: `181,40 s` en el `.mp4` limpio y en el `.full.mp4`. La última
   marca del `.txt` es 179,6 s, así que la transcripción corresponde a este
   archivo.
2. **Cortes**: detección de escenas de ffmpeg (`select=gt(scene,0.20)` sobre el
   cuadro real recortado). Da 104 tramos; los de menos de 0,5 s son destellos de
   transición y se suman a la toma anterior. Quedan **77 tomas, media 2,36 s**
   (mín 0,50 · máx 6,47).
3. **Contenido**: se extrajo el fotograma medio de cada una de las 77 tomas y se
   miraron todas, una por una, para anotar encuadre, quién está y qué pasa.
4. **Cuadro**: el video es 1080×1920 pero la imagen real es **1080×1440
   centrada**, con barras negras de 240 px arriba y abajo.
5. **Audio**: mono (L−R = 0,0004 RMS), con **45 silencios reales** de hasta
   0,8 s (16,7 s en total) y el piso cayendo a −62 dB. **No hay música ni
   ambiente**: es voz TTS sola sobre imagen muda.

## Los tres desvíos, y por qué

1. **9:16 a sangre contra su 3:4 con barras.** El módulo genera a la resolución
   nativa de H3 (768×1344) y el `aspecto` lo fija el formato. Copiar su
   letterbox obligaría a recortar un cuarto de alto o a tocar el módulo. Lo que
   se copia es **qué se ve** en cada toma, no las barras.
2. **Dos cortes agregados.** Las tomas 6 y 14 duran 6,47 s: no entran en la
   grilla de H3 con colchón suficiente (6,58 dejaría 0,11 s y 7,29 es apuesta,
   regla 38), así que cada una se parte en dos planos con un cambio de tamaño
   real. Son los **únicos dos cortes** que la réplica agrega a los 76 del
   original.
3. **La voz.** Ver abajo: es el hallazgo, no un defecto.

## El hallazgo: la voz no llega

El texto es fijo. Si una línea no entra en su ventana **no se reescribe** — se
mide el desvío, que es justamente lo que el benchmark tiene que decir.

| | |
|---|---|
| lo que dicen ellos | 3.739 caracteres en 181,3 s de ventana |
| hablando de verdad | 164,7 s (descontando los 16,7 s de silencio) → **22,7 cps** |
| lo mismo con Kate | **223,7 s** → 16,7 cps medidos |
| factor global | **1,234×** |
| líneas que entran sin tocar (≤1,15×) | **35 de 92** |
| líneas por encima del tope duro (1,30×) | **34** |

Comprimiendo cada línea hasta donde el proyecto permite:

| tope | dónde termina la voz | atraso máximo |
|---|---|---|
| 1,15× (tope blando) | 201,3 s | 19,9 s |
| **1,30× (tope duro)** | **188,0 s** | **6,6 s** |
| 1,50× (ya se oye deformada) | 182,4 s | 1,0 s |

Conclusión: **con Kate no se llega a su densidad.** Su voz es TTS acelerada
(22,7 cps hablando es imposible natural en castellano). Para igualarlos hay que
acelerar, y aun al tope duro la réplica termina 6,6 s más larga que el original.
Al montar se decide: estirar el último plano esos 6,6 s, o subir a 1,50×.

Esto vale también para nuestros videos propios: la regla 40 dice de escribir a
14-16 cps para Kate. Este canal escribe para 22,7. Si queremos su ritmo, o
aceleramos o escribimos menos.

## El otro hallazgo: cortan el triple de rápido que nosotros

| | tomas | duración | media por toma |
|---|---|---|---|
| ellos, este video | 77 | 3:01 | **2,36 s** |
| nosotros, EL LOCO DEL CARBÓN | 41 | 4:00 | 5,85 s |

Y H3 no baja de **5,17 s por clip**. O sea que para servir tomas de dos segundos
hay que generar cinco y tirar más de la mitad: **412 s generados para 181 s de
línea**. El costo de GPU de una réplica de tres minutos es el de un video propio
de siete.

## El control de los 79 dibujos

Se miraron **todos**, uno por uno, en tandas, contra el fotograma del original.
**Se rehicieron 13.** Los fallos no fueron aleatorios: son tres patrones, y cada
uno se arregló en el generador para que valga también para lo que se rehaga.

| patrón | qué pasaba | dónde | arreglo |
|---|---|---|---|
| el detalle se abre | un plano de detalle salía mostrando la cara que el original recorta | S15, S18, S65 | `REFUERZO_PD`: «este es un inserto de ese detalle y nada más; todo lo demás lo corta el borde del cuadro, la cara incluida» |
| la nuca se da vuelta | la persona de espaldas en primer término aparecía de frente o pasaba al fondo | S06b, S09, S41 | `REFUERZO_ESPALDA`, disparado sólo cuando la espalda es **de una persona** (matcheaba «the back of the display **case**» e inventaba una silueta) |
| la locación se escapa | la sillita del auto aparecía en un cuarto; la tienda se volvía una casa | S49, S51, S57, S66 | `REFUERZO_AUTO` por locación: «esto pasa DENTRO DEL AUTO EN MARCHA…» |

Los otros cuatro fueron de encuadre suelto (S14a salió vacía, S30 y S34 se
abrieron a plano entero, S62 con la silueta fantasma) y S72/S74, que se
reescribieron: el cuenco boca arriba del final es el remate del video y en dos
intentos no se leía, hasta describirlo como «cuatro cúpulas de porcelana y una
sola abierta».

Nada de esto se descubre generando video: se descubre mirando PNG con la GPU
apagada, que es el orden que ahorra la plata.

## Lo gastado — cuenta final (3/9/2026)

| rubro | | $ |
|---|---|---|
| GPU · instancia 1 (Shanghái) | 35 min colgada en `loading`, nunca generó | **0,96** |
| GPU · instancia 2 (Taiwán) | 185 min a $2,283/h | **7,05** |
| — de eso, generar los 79 | ~98 min | 3,73 |
| — rehacer 9 tras el QC | ~15 min | 0,57 |
| — S59 a 6,58 s: 4 intentos fallidos | ~20 min | 0,76 |
| — bajadas, QC, relanzamientos, cortes de red | ~52 min | 1,99 |
| imágenes | 112 llamadas a `gemini-2.5-flash-image` (de lista) | **4,37** |
| voz | 92 líneas, 3.739 caracteres en ElevenLabs | créditos del plan |
| **total** | | **≈ $12,40** |

Contra los ~$9 estimados al arrancar. Dónde se fue la diferencia, en orden:
la máquina que no arrancó ($0,96), el clip de 6,58 s que no entraba ($0,76), y
sobre todo **la máquina parada mientras se bajaba, se miraba y se relanzaba**
($1,99). Ese último es el precio de hacer QC con la instancia viva; la
alternativa (destruir sin mirar) costó un alquiler entero el 31/8.

Lecciones que van al módulo:
1. **No generar a 6,58 s.** Cinco planos largos: cuatro de 5,88 entraron; el de
   6,58 falló 4 de 5 veces. El techo práctico en 5090 con la placa caliente es
   5,9, no 6,6. Los cortes de más de 5,6 s se parten en dos.
2. **El selector tiene que recordar los hosts que colgaron.** La oferta de
   Shanghái reapareció con otro id apenas se destruyó la instancia.
3. **El QC de clips va con un reloj**: bajar, mirar y decidir en una pasada,
   no en tres. Cada ida y vuelta son ~$0,50 de máquina parada.

## La corrida en Vast (2-3/9/2026)

| | |
|---|---|
| primer intento | oferta más barata (Shanghái, $1,60/h): **nunca salió de `loading`** en 20 min. Destruida. ≈ $0,95 tirados |
| segundo intento | Taiwán a dedo (`47768544`, 4×5090, $2,283/h reales): lista en 3,4 min |
| generación | **79/79** · 315 min de GPU · **3,98 min por clip = 0,77 min/s** — la curva de EL LOCO DEL CARBÓN, exacta |
| fallos | S01 (5,88 s) cayó por VRAM y salió en el 2.º intento; ningún 5,17 falló |
| ruido | ninguno (detector de `bajar`) |

Lección nueva para el selector: **el costo total estimado no sabe si el host
va a arrancar.** La oferta de Shanghái ganaba por $0,60 y costó $0,95 en no
levantar; reapareció después con otro id. Falta que `alquilar` recuerde los
hosts que colgaron.

## El control de los 79 clips (QC antes de destruir)

`qc_clips.py` saca entrada / medio / **salida** del tramo usado de cada clip.
Se miraron los 79. **Pasan 70. Se rehacen 9** con la instancia viva (~$0,45),
que es 4 minutos por clip contra un alquiler entero si se hace después.

| clip | qué pasó | tipo de fallo |
|---|---|---|
| S11 | cambia de escena a mitad del tramo usado: del cole a un interior | deriva de locación |
| S48, S59 | la madre «entra al auto» por la ventanilla, geometría imposible | deriva espacial |
| S65 | la mano con la cámara se vuelve dos mujeres duplicadas | deriva de sujeto |
| S77 | la placa cósmica final tiene a la protagonista sentada delante | inserta personaje donde no hay |
| S49, S58, S64, S76 | salto interno, espejo que se vacía, vendedora cambiada, detalle que se abre | dudosos, se rehacen porque cuestan lo mismo |

**El patrón que no se rehace: H3 alucina subtítulos chinos quemados.** En 9
clips (S05, S06a, S06b, S07, S14a, S48, S64, S67, S72) aparece texto chino en
el tercio inferior que nadie pidió. Imita el estilo «drama corto chino» del
prompt: el modelo aprendió que ese género lleva subtítulos y los pone. Es
sistemático, así que no se corrige rehaciendo clips sueltos; para la próxima
va un negativo explícito en `cierre_video` («no subtitles, no captions, no
on-screen text») y queda documentado como límite del estilo.

Segundo patrón, menor: **los armarios se abren solos** (S22, S23). El `mueve`
decía que ella se queda quieta; H3 la hace abrir. Tolerable en cortes de 2,4 s.

## El máster (3/9/2026)

`REPLICA - final.mp4` · 181,4 s · 68,7 MB (y `REPLICA - final (movil).mp4` a
540×960, 14,5 MB, para mandar). Se armó con `mezclar_replica.py clips S59`:

| | |
|---|---|
| clips de H3 | 77 de 79 |
| S59 | **plan B sin GPU**: el dibujo nuevo (frontal al volante) con zoom lento de 5,6 s. A 6,58 s falló 4 veces por VRAM en este host |
| S77 | **imagen fija** `l_cosmos.png`: H3 metió a la protagonista en la placa cósmica dos veces seguidas |
| voz | 92 líneas comprimidas hasta 1,30×; 34 se pasaron y se dejaron correr; **termina 5,1 s después que el video**, y `mezclar` corta el audio en la duración del video: las últimas líneas quedan truncadas. Es el desvío medido, no un error de montaje |
| música / ambiente | ninguno, como el original |
| subtítulos | quemados con los tiempos reales de nuestra voz, no las marcas de ellos |

Lo que el ojo ve primero al compararlo con el original, en orden:
1. **Los subtítulos chinos alucinados** en 9 clips, debajo de los nuestros.
2. **La voz atrasada** en la segunda mitad, donde el atraso acumulado ya es de
   varios segundos.
3. Que la nena parece de 7 y no de 5, y que sale vestida en la bañera.
4. Que los armarios se abren solos.

Lo que el ojo NO ve: identidad de los tres personajes (sostenida en 77 clips),
el vestuario día/noche, las locaciones, el ritmo de corte. **Eso es lo que el
pipeline sí puede producir**, y es la respuesta del benchmark.

## Segunda corrida, limpia (3/9/2026)

Pedida por el usuario: máquina de calidad (no la más barata, ≤ $3,5/h), la
fórmula del reuso, y ninguno de los errores de la primera. Qué cambió:

| | primera corrida | segunda |
|---|---|---|
| máquina | la más barata (Shanghái): 20 min colgada | `47768544` Taiwán, 0,998, $2,148/h, elegida a dedo |
| clips a generar | 79, uno por toma | **61 fuentes**; 19 tomas reusan el clip de otra (`clip_de`) |
| segundos generados | 412 | **338** (−18 %) |
| techo por clip | 6,58 (falló 4 de 5) | **5,88**; lo que no entra se parte en dos (S12, S59) |
| timing | el del original al centésimo | **la imagen sigue a la voz** (`linea_de_tiempo.py`): 185,8 s |
| subtítulos alucinados | 9 clips | negativo explícito en `cierre_video` |
| placa final | generada (salió con gente) | imagen fija `PLACA` |
| imágenes nuevas | — | 1 (S12b); el resto reusa los dibujos ya revisados |
| QC | tres idas y vueltas | una pasada: bajar → mirar → destruir |

Por qué el reuso ahorra sólo 18 % y no 50 %: con un piso de 5,17 s y tomas
de 2,3 s, **un clip sirve a dos tomas, no a tres**, y 39 de los encuadres
aparecen una sola vez. El ahorro grande del reuso está en las imágenes (cero
nuevas) y en no volver a pagar los dibujos ya revisados.

El módulo ganó `clip_de` (en `proyecto.construir`, `empaquetar` y
`montaje.recortar_y_concatenar`): un plano que dice «usá el clip de tal otro,
de tal segundo a tal otro». Vale para cualquier video.

### Resultado de la segunda corrida

| | |
|---|---|
| máquina | `47768544` Taiwán, 4×5090, $2,283/h reales; lista en 1,3 min |
| fuentes | **58 de 61 generadas**; S01, S16 y S22 agotaron 3 pasadas y se cubren con sus clips de la primera corrida (largo suficiente, medido) |
| plan B sin GPU | **S15** (metió a una desconocida al volante) y **S72** (rótulos chinos) → dibujo con zoom |
| 5,17 s | 28 clips, **cero reintentos** |
| 5,88 s | 30 clips, 2 con reintento, 3 que no salieron tras 3 pasadas |
| ruido | 0 |
| **GPU** | **128 min → $4,86** |

Adónde se fueron los 128 minutos: ~65 de generación, ~25 de pasadas de
reintento sobre los largos, ~20 de bajada + QC, y ~18 en los que la corrida ya
había terminado y esta sesión no lo sabía (el proceso local se reinició dos
veces por los cortes de red y los vigías murieron con él).

**Lo que la segunda corrida enseña que la primera no:**

1. **5,88 tampoco es gratis.** 3 de 33 largos no salieron ni en tres pasadas y
   cada pasada fallida son 4 min de GPU. El largo *seguro* en 5090 caliente es
   **5,17**: cero fallos en 56 clips entre las dos corridas. Un plano que
   necesite más de 4,87 s de línea se parte, siempre.
2. **El negativo contra los subtítulos no funciona.** «NO subtitles, NO
   captions…» en el prompt de video y H3 los quemó igual (S05, S06a, S07, S14a,
   S17, S25, S48, S60, S72). El disparador es el ESTILO —«streaming short-drama
   series», «Chinese urban melodrama»— no la falta de un negativo. La próxima
   vez el estilo se describe sin nombrar el género de origen.
3. **El reuso ahorra imágenes, no tanto GPU**: 18 % menos segundos generados,
   pero cero imágenes nuevas y cero re-revisión de dibujos.
4. **La imagen que sigue a la voz funciona**: 185,8 s de línea, voz y cortes
   coinciden por construcción (`linea_de_tiempo.py`).
5. **Sesión local frágil = plata**: cada reinicio del proceso mata los vigías
   y la instancia sigue cobrando sin que nadie mire. Con la red inestable, la
   regla es corta: `alquilar` → `seguir` cada vez que se retoma → `bajar` →
   `destruir` en la misma sesión, sin dejar la máquina viva «para después».
