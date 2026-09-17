# MANUAL DE PRODUCCIÓN

**14 de septiembre de 2026.** Todo lo aprendido en un mes de hacer videos con IA,
ordenado para hacer **tres tipos de video**: el SHORT, el LARGO tipo recap y el
VIDEO PARA MÚSICA. Sale de cruzar 25 documentos, 6 carpetas de videos y 9
corridas reales en GPU; cada afirmación tiene su fuente al lado. Donde dos
documentos se contradecían, acá hay **una sola decisión**, marcada con ►.

> **Actualización del mismo 14/9, a la noche:** el repaso completo de la
> documentación oficial de H3 cambió cómo se escriben los prompts (formato
> oficial, sin negativos), cómo se sostiene una voz entre clips (Ref2VA con voz
> de referencia) y la configuración de la LoRA turbo (8 pasos, shift 6). Donde
> este manual diga otra cosa sobre prompts, voz o turbo, **manda
> `h3pipeline/H3-OFICIAL.md`**.

Lo que este manual **no** tiene, y hay que decirlo en la primera página: **ningún
video se publicó todavía**. Toda la ley de retención (65/50/45 %) y todos los
tramos son hipótesis bien fundadas en un informe de 2026 y en un short que
funcionó. Hasta que se publique y se mida, cada estructura es una apuesta.

---

## Índice

- **0 · Lo común a los tres formatos**: las 8 capas, el pipeline, el prompt, la
  imagen, la máquina, los números, los errores de proceso.
- **A · SHORT** (vertical, 15 a 90 s).
- **B · LARGO / RECAP** (vertical, 3 a 8 min, voz continua).
- **C · VIDEO PARA MÚSICA** (16:9, loop).
- **D · La hipótesis de los 15 segundos** (pedido del 14/9): cómo cambia cada
  formato.
- **E · Las contradicciones, resueltas.**
- **F · Lo que sigue abierto.**

---

# 0 · LO COMÚN A LOS TRES FORMATOS

## 0.1 Las ocho capas, de abajo hacia arriba

Cada capa existe sólo cuando la de abajo está cerrada. **Lo caro se hace último;
lo que se puede revisar gratis se revisa antes.** (`ESTRUCTURA-POR-CAPAS.pdf`)

| # | capa | herramienta | costo |
|---|---|---|---|
| 1 | guion + estructura | regla 40, `estructuras/*.json`, `construir` | $0 |
| 2 | imágenes: madre + primer fotograma por plano | nano banana Flash | ~$0,04 por imagen, ~$0,40 fijo de madres |
| 3 | clips de video | MiniMax H3 en 4×RTX 5090 (Vast) | ~$0,50 por minuto de video + ~$0,60 fijo por sesión |
| 4 | corte | ffmpeg: recorte por clip y concatenado | $0 |
| 5 | audio: voz, música, ambiente | ElevenLabs v3, ElevenLabs Music, el audio de H3 | créditos |
| 6 | subtítulos quemados | SRT con los tiempos medidos de la voz | $0 |
| 7 | texto en pantalla | overlay en post, nunca pedido al generador | $0 |
| 8 | máster y control | loudnorm −14 LUFS / −1 dBTP, control lado a lado | $0 |

**Total medido:** ≈ $0,90 por minuto de video a corte de 5,7 s; ≈ $2,05 a corte
de 2,3 s; más ≈ $1 fijo por video. Lo que no está en la tabla y sí en las
facturas: máquinas que no arrancan, clips fuera del largo seguro y la máquina
parada mientras se mira. En la réplica fueron $3,71 de $12,40.

## 0.2 El pipeline, comando por comando

| # | comando | entra → sale |
|---|---|---|
| 1 | `construir <proyecto.json>` | proyecto → `storyboard.json`, `planos.json`, `brief.md`; **avisos** (tramos sin cubrir, cortes fuera de rango, saltos de eje, línea de voz que no entra). Se corrige hasta **0 avisos** |
| 2 | `voz <proyecto.json>` (`--generar`) | líneas → cps y tag por línea; con `--generar`, los audios y su duración real |
| 3 | `frames <proyecto.json> --madre --motor nanobanana` | storyboard → un PNG por asset, **en local, con la GPU apagada** |
| 4 | `empaquetar <proyecto.json>` (`--solo` para rehacer) | dibujos normalizados + planos + scripts → ZIP |
| 5 | `gpu <proyecto.json>` | el podio de ofertas por **costo total del trabajo** |
| 6 | `alquilar <proyecto.json> <id> --si --generar` | crea la instancia, adjunta la clave SSH, sube el ZIP y deja todo andando |
| 7 | `seguir <proyecto.json> <iid>` | clips hechos, qué hace cada placa, taxímetro |
| 8 | `bajar <proyecto.json> <iid>` | clips + `metricas.json`; escanea ruido y **no recomienda destruir si hay** |
| 9 | QC con tiras de 10 cuadros por clip | decidir qué se rehace, **en una sola pasada** |
| 10 | `destruir <iid> --si` | **siempre, en la misma sesión** |
| 11 | `montar` / `mezclar` (o `bucle.py` para el loop) | corte, voz, música, subtítulos, máster |

## 0.3 Cómo se escribe un plano

> **Desde el 17/9/2026 el prompt de video no se escribe a mano.** Los campos de
> abajo (`ve`, `mueve`, `audio`, `dialogo`) son el *pedido*; el prompt que
> recibe H3 lo arma `h3pipeline/reescritor.py` (GPT con la guía oficial de
> MiniMax, validado: un solo shot, diálogo literal, sin negativos) al traducir
> el guion y al empaquetar, y queda en `prompt_h3` de cada plano. En Libre lo
> mismo, desde lo que el usuario escribe en castellano. Detalle en
> `h3pipeline/H3-OFICIAL.md` §1.3 bis.

- **`ve`** es la FOTO del primer fotograma: tamaño de plano en mayúsculas,
  vestuario completo, escala en fracciones del cuadro, qué NO tiene que
  parecer. Va al dibujo.
- **`mueve`** es lo que pasa a partir de ese fotograma: sujeto → entorno →
  cámara. Va a H3. **Describe exactamente lo que hay en el dibujo**: una
  contradicción dibujo-texto la resuelve H3 transformando la imagen (el ojo de
  buey que se volvió escotilla, INVERNADERO O05).
- **`audio`** en tres capas `[SFX]` `[Ambient]` `[Foley]`, y **sólo lo que nace y
  muere dentro del plano**. La voz, nunca.
- **`corta`** es lo que dura en la línea de tiempo; `segundos` lo que se
  genera. El módulo pone lo demás: castellano, escala, formato, humo, «no
  inventes» (o su versión positiva).
- **El tamaño de plano va en el dibujo Y en el prompt** (regla 4, la que más
  caro salió). **La escala en fracciones de la altura** (regla 5): «waist up» a
  secas dibujó el cuerpo entero siete de siete.
- **Texto y números que cambian van en post, siempre** (reglas 20 y 23).

### ► Los bloques negativos: cuándo sí y cuándo no

Medido el 10/9 (LLUVIA EN LA VENTANA): en una escena quieta y sin gente, los
bloques fijos «no cacti, no fire, no people», «NEVER cartoon puffs» y «at most a
pair of hands» **produjeron cactus, fuego, gente y manos en 7 de 12 clips**.
Nombrar algo lo invoca. Es la misma lección que «NO subtitles», que tampoco
frenó los subtítulos chinos.

- **Escenas con personajes y acción** (short, largo): los bloques quedan; ahí
  los negativos son topicales y el «no inventes» redujo la deriva.
- **Escenas quietas y vacías** (música, y cualquier plano de objeto):
  `"negativos": false` en el proyecto → bloque QUIETO positivo, audio en
  positivo («The only sounds are…»), escala neutralizada.
- **Nunca** nombrar el género de origen en el estilo («Chinese short-drama» trae
  subtítulos quemados). Se describe el look.

## 0.4 Lo que se sabe de la imagen (nano banana)

- **Flash** (`gemini-2.5-flash-image`, ~$0,04) para todos los fotogramas.
  **Pro** (~$0,13-0,24) sólo para hojas de modelo y locaciones si hace falta
  identidad. Hasta el 31/8 el módulo llamaba al Pro sin que nadie lo decidiera.
- El aspecto va **por parámetro** y `empaquetar` normaliza al centro (recorte
  inevitable de ~2 % en 16:9). OpenAI pierde el 14 % del ancho.
- **Letterbox pintado** (16:9 con estilo «film»): frase «fills the ENTIRE canvas,
  no letterbox» + `barras.py` (franja oscura Y uniforme: media < 40, desvío < 2).
- **La locación de referencia manda el encuadre**: para otro ángulo del mismo
  lugar, `loc: null` y `refs: []`, y el lugar descripto en texto.
- Hojas de modelo con las cuatro vistas; una imagen por locación **sin gente**;
  el vestuario se repite en cada prompt (la hoja sostiene la cara, el texto la
  ropa).
- **Se revisan TODOS los PNG antes de empaquetar.** En la réplica se rehicieron
  13 de 79; ninguno se habría visto sin mirarlos. Los tres patrones: el detalle
  que se abre y muestra la cara, la nuca que se da vuelta, la locación que se
  escapa. Cada uno tiene su refuerzo (`REFUERZO_PD`, `REFUERZO_ESPALDA`,
  `REFUERZO_AUTO` en la réplica).

## 0.5 Lo que se sabe de H3

- Genera **de 5,17 a 15,08 s** (grilla 17k+5 a 24 fps). ► **Se generan clips
  de 5,17 s y nada más**: 56 + 24 + 31 clips sin un reintento por VRAM. 5,88
  pierde 1 de 10; 6,58 falló 4 de 5; 7,3 es apuesta. Un corte que necesite más
  de 4,87 s de línea **se parte en dos**.
- **Planos sueltos, no encadenados**: 20-35 % más barato, paraleliza, un clip
  malo no arrastra. Encadenar sólo para una toma continua deliberada: techo 5,9
  s por eslabón, máximo 3 eslabones, el cabeza se genera y verifica primero.
- **Arranca clavado en el dibujo y deriva hacia el final**; la duración no
  influye (correlación −0,04). Por eso `usa` arranca siempre en 0 y se tira la
  cola.
- **Mete gente donde hay lugar para gente**: una silla vacía frente a un
  escritorio, una ventana con ciudad, una placa gráfica. Las placas van como
  imagen fija; los encuadres que invitan a alguien se cierran sobre un objeto.
- **La iluminación artificial de color deriva** en 5 s (luz magenta que vira a
  blanco o se apaga; «motas de polvo» que se vuelven globos de luz). Luz
  natural o cálida rinde mejor. Un solo movimiento por plano.
- **Un dibujo abstracto lo abandona desde el cuadro 1.**
- **Quema subtítulos** si el estilo nombra un género que los lleva.
- **El audio sale clipeado** (+2,68 dBFS): máster a −14 LUFS siempre.
- **No sincroniza su boca con su audio** (labios 0,70-0,85 s antes del sonido)
  y no tiene voice ID: toda voz que cruza un corte es de ElevenLabs.
- **Caras en primer plano**: la debilidad del modelo en el short (taparlas,
  entorno que perdona). En el recap se acepta a propósito porque el género vive
  de caras: PM/PA para emociones, PP en dos o tres picos.

## 0.6 La máquina

- **4 placas de 32 GB = 4× RTX 5090.** La 4090 tiene 24 GB, la V100 no tiene
  bf16, la A100 rinde 15 % menos y cuesta el doble. Dos 3090 no suman: cada clip
  corre entero en una placa.
- **Sólo hosts verificados.** ► «deverified» es un no aunque no haya otra cosa:
  tres de tres quedaron 20 min en `created` sin arrancar (13/9). Si no hay, se
  espera con `cazar.py` (consulta cada minuto, alquila sola, techo de $4/h
  porque apareció una a $213).
- Licencia de H3: fuera EE.UU., UE, Reino Unido y Corea del Sur. Quedan
  Taiwán, Japón, Canadá, Australia, Emiratos, Hong Kong.
- Ordenar por costo total (59 GB de descarga antes del primer clip), 250 GB de
  disco, fiabilidad ≥ 0,995, on-demand.
- Las **16 trampas** con síntoma y arreglo están en `h3pipeline/VAST.md`. Las
  nueve reglas de la corrida limpia, ahí mismo.
- **Nada vivo entre sesiones**: la red local se corta y la instancia sigue
  cobrando. `instancias` al retomar, `destruir` en la misma sesión que bajó.

## 0.7 Los números para presupuestar

| dato | valor |
|---|---|
| min de GPU por segundo de video, 4×5090, 8 pasos turbo, host sano | **0,73-0,77** (vertical y 16:9 por igual; un host lento dio 0,91) |
| minutos de video por hora de máquina | **~5** en generación pura; ~4 la primera hora |
| overhead fijo por sesión | arranque 4-7 min + descarga 5-13 min + bajada/QC 5-10 min |
| costo por minuto de video terminado | ≈ $0,45 de GPU si todo pasa; el rehecho por contenido costó 6× la generación en LLUVIA |
| imagen | $0,039 (Flash) |
| desperdicio de generación | 17-20 % en shorts de 60 s (medido en 4); 56 % si se corta a 2,3 s |
| voz | Kate 16,7 cps; Pablo 10,5; @jcfdlw escribe para 22,7 |
| deformación de voz | estirar ≤1,08×; comprimir ≤1,15× (1,30 duro); aceptación 0,93-1,15× |
| error de estimar por densidad a nivel toma | 30 % |

Costos reales de cada video: 78 SUR ~$4 · CONTRAMANO ~$5,20 · DRON ~$2,70 ·
LOCO DEL CARBÓN ~$10-11 (placa defectuosa) · RÉPLICA $12,40 y $4,86 · LLUVIA
$4,20 · KOI + INVERNADERO $3,90 los dos.

## 0.8 Los errores de proceso, y la regla que evita cada uno

1. **Planos primero y la voz después en los huecos** → el video no se entendía
   (DRON). → Regla 40: el guion de voz primero, medido con la voz elegida.
2. **Destruir sin mirar los clips** → once clips de ruido y otro alquiler. → QC
   antes de destruir, siempre.
3. **QC en tres idas y vueltas** → $1,99 de máquina parada. → Una pasada, con
   reloj.
4. **La oferta más barata** → Shanghái colgada, $0,96. → Por fiabilidad, a dedo.
5. **Forzar desverificadas** → tres colgadas. → No.
6. **Dejar la máquina viva «para después»** → 18 min cobrando sin que nadie
   mire. → Nada vivo entre sesiones.
7. **Clips de 6,58 s** → 4 de 5 fallidos. → 5,17 y nada más.
8. **Generar sin corregir el prompt** → 7 de 12 inservibles, tres tandas. →
   `negativos: false` y encuadres cerrados ANTES de la primera tanda.
9. **Rehacer clips para corregir un patrón sistemático** (subtítulos chinos) →
   volvieron. → Un patrón se corrige en el estilo, no clip por clip.
10. **Verificar sólo con números y nunca mirar ni escuchar.** → EL LOCO DEL
    CARBÓN sigue sin verse. Se mira antes de construir encima.
11. **Duplicar documentación a mano** → se desincroniza en una semana. → La
    página se genera desde el módulo y desde este manual.
12. **`pkill -f` que se mata a sí mismo**, `find` en vez de preguntarle al
    proceso, `python` sin `-X utf8 -u`, tags fijados a mano, ZIP por Jupyter:
    todos documentados en VAST.md, todos ya en el módulo.

---

# A · SHORT (vertical, 768×1344)

**Qué es.** Un video vertical de 15 a 90 s con voz en off, música y subtítulos,
para Shorts, TikTok y Reels. Cuatro hechos: PROFUNDIDAD (19/8, la base de la
ley), 78 SUR, CONTRAMANO, EL DRON DEL VOLCÁN; y EL FARERO escrito y empaquetado,
sin generar. **Desde el 31/8 el short dejó de ser el objetivo declarado del
canal** (el rumbo es el recap), pero es el formato más barato para probar ideas.

## A.1 El flujo, en orden

1. **Elegir la estructura** antes de escribir un plano: `short-23` (alcance,
   65 %), `short` (60 s, 50 %), `short-90` (guardados, 45 %). Y la nueva
   `short-15` de la sección D.
2. **El guion de voz completo, PRIMERO** (regla 40): una historia lineal que
   entiende un chico de doce, una línea por plano, presente, números concretos.
   Vara: si el espectador tiene que inferir algo para entender el final, es
   demasiado complejo.
3. **La densidad, con la voz elegida y medida**: Pablo corre a 10,5 cps, Kate a
   16,7. Escribir a los 17 teóricos costó tres pasadas en DRON; con el ritmo
   medido, FARERO dio 12/12 a la primera. Para voz en off sólo manda el máximo:
   el silencio entre líneas es parte del guion.
4. **Los planos, uno por línea**, para ilustrar lo que la línea dice. `corta` lo
   que pide el tramo; `segundos` 5,17. Marcar `interrupcion: true` donde cambia
   el régimen de luz o sonido (un corte no cuenta).
5. **`construir` hasta 0 avisos.**
6. **`voz --generar`**: se sintetiza, se mide, y lo que cae fuera de 0,93-1,15×
   **se reescribe entero**, nunca se estira. Tags de emoción: neutro por
   defecto, uno por línea como máximo.
7. **Dibujos** (`frames --madre`), todos revisados. Caras tapadas o de espaldas,
   entorno que perdona (agua, humo, niebla, poca luz).
8. **Música**: `musica.componer(duración, tono)` por función dramática.
9. **Empaquetar → máquina → generar → QC en una pasada → destruir.**
10. **`mezclar`**: corte por `usa` (arranca en 0 siempre), tres capas con
    ducking, −14 LUFS, SRT quemado, texto en pantalla como entregable.

## A.2 Lo que falló y cómo se arregló

| síntoma | causa | arreglo |
|---|---|---|
| el video salió bien y no se entendía la historia | planos primero, voz recortada en los huecos | regla 40 |
| tres pasadas de reescritura de voz | densidad calculada con 17 cps teóricos | la voz elegida, medida |
| tres pasadas de isocronía en 5 diálogos | error de densidad a nivel toma del 30 % | sintetizar, medir, ajustar por regla de tres; mejor: sin boca en cámara |
| una línea suena a otra persona | tag `[sad]` en intensidad media | neutro por defecto |
| voz distinta en cada clip | H3 no tiene voice ID | toda la voz en off, de ElevenLabs; que no se vea la boca |
| tres relaciones de aspecto en una tanda | aspecto pedido por texto | por parámetro + normalizar |
| caras en primer plano | debilidad del modelo | taparlas, entorno que perdona |
| cactus, fuego, cara ajena al final del plano | deriva de H3 | «no inventes» + usar la cabeza del clip |
| audio en inglés de fondo | faltaba el bloque de idioma | castellano en todos los prompts |
| personajes gigantes | escala sólo en la imagen | escala en dibujo Y prompt, en fracciones |
| brinco entre dos planos iguales | mismo tamaño, lugar y reparto | `validar()` lo detecta |
| OOM en el tercer clip de la placa | 23,9 GB de 32 y fragmentación | 5,17 s; `rescate.sh` si se repite |
| 28 min de placa parada | cadena rota (CONTRAMANO) | planos sueltos; si se encadena, el cabeza primero |
| once clips de ruido puro | placa defectuosa | detector de ruido + QC antes de destruir |
| el ritmo pensado al décimo se arruina | `-c copy` corta en el keyframe | recodificar cada clip y después concatenar |
| acentos rotos en subtítulos | SRT sin BOM | `utf-8-sig` |
| $4 por un short de $0,75 | nueve trampas de Vast | todas en el módulo |

## A.3 Números del short

- 12 planos para 60 s; se generan 72-75 s (17-20 % de descarte).
- Interrupción de patrón cada 12 s (8 en short-23); ventana crítica 1-3 s.
- Un short de 60 s ≈ 55 min de GPU ≈ 14 min de pared ≈ $0,75 de generación,
  $2,50-4 con overhead.
- Corte medio nuestro 5,0 s; la competencia 2,3 s.

## A.4 ► Lo que hay que corregir en la estructura

`short.json` pide cortes de hasta 7,0 s en REVELACIÓN, GIRO y CONTACTO, y la
regla vigente es 5,17 s de clip (≤ 4,87 de línea). **La estructura de 60 s no es
ejecutable tal como está** sin partir planos: pasa de 12 a ~16-18 planos, o se
acepta 1 de 10 reintentos generando a 5,88. Decisión pendiente en la sección D:
el short de 15 s no tiene este problema.

---

# B · LARGO / RECAP (vertical, 3 a 8 min, voz continua)

**Qué es.** El formato del canal de referencia @jcfdlw: recap melodramático de
3-8 min, voz en off continua a ritmo de TTS, subtítulos quemados frase por
frase, sin música ni ambiente, caras en pantalla. Hechos: EL LOCO DEL CARBÓN
(3:58, 41 planos) y la RÉPLICA de @jcfdlw (3:01, 79 tomas, dos corridas).
**Ninguno de los dos se miró entero todavía.**

## B.1 El flujo, en orden (la regla de oro: primero el audio, después el video)

1. **La ley**: `recap.json` (240 s, 10 tramos, retención 45 %, interrupción
   cada 30 s) o `largo.json` (300 s narrativo, nunca usado para producir).
2. **El guion de voz, PRIMERO, como historia lineal**: primera persona con
   nombre, números concretos, diálogos actuados dentro de la narración con
   comillas, **la voz no para nunca**, micro-cliffhanger cada 25-35 s. Una
   línea por plano, ~41 para 4 minutos.
3. **Escrito a la densidad medida de la voz**: Kate 16,7 cps → se escribe a
   14-16 caracteres por segundo de plano. El canal escribe para 22,7 (TTS
   acelerada): **con Kate no se llega**; o se acelera el audio o se escribe
   menos texto. ► Se escribe menos texto.
4. **Paso de emoción** antes de sintetizar: tag de entrega por línea, neutro
   por defecto; la columna cps se revisa antes de gastar un crédito.
5. **`voz --generar` y MEDIR**: factor 0,93-1,15× o se reescribe entera.
6. **Congelar la línea de tiempo con los números reales.** Recién con las
   duraciones medidas se cortan los planos. **La imagen sigue a la voz**: si
   una línea no entra, se mueve el corte (`linea_de_tiempo.py`), nunca se
   deforma el audio. Antes de esto la voz terminaba 5 s tarde y las últimas
   frases se truncaban.
7. **Un plano por línea**: `corta` = `segundos` − 0,5 (con voz continua se usa
   casi todo el clip). Un clip por **encuadre**, no por toma (`clip_de`): con
   piso 5,17 y tomas de 2,3 s un clip sirve a dos tomas.
8. **`construir` a 0 avisos.**
9. **Dibujos**: hojas de modelo con cuatro vistas, una imagen por locación,
   un fotograma por plano; todos revisados. Caras sí, en PM/PA; PP en dos o
   tres picos; entorno que perdona.
10. **Estilo sin nombrar el género de origen** (o quema subtítulos chinos).
11. **Máquina, generar, QC en una pasada con la instancia viva, destruir.**
    Plan B sin GPU para lo que no sale en tres pasadas: dibujo con zoom lento.
    Placas gráficas como imagen fija.
12. **`mezclar`**: corte, voz, máster −14 LUFS, SRT con los tiempos medidos,
    quemado en el tercio inferior-medio. Música opcional (la referencia no usa).

## B.2 Lo que falló y cómo se arregló

| síntoma | causa | arreglo |
|---|---|---|
| la voz termina 42 s después que el video | Kate 16,7 cps contra un texto para 22,7 | menos texto, o mover los cortes |
| últimas líneas truncadas en el máster | el mezclador cortaba el audio al largo del video | la imagen sigue a la voz |
| líneas crípticas | recortar en vez de reescribir | regla 40 |
| el personaje cambia de voz en cada línea (doblaje) | varispeed | estirar en dominio del tiempo, un factor por clip |
| el doblaje sigue 3 s después de la boca | ventana tomada del ASR | ventana por energía del stem de demucs |
| desincronía que no aparece en el audio | H3 mueve los labios 0,7-0,85 s antes del sonido | medir por ojo, una vez por plano; no automatizable |
| la nuca se da vuelta; el detalle muestra la cara | el generador completa | `REFUERZO_ESPALDA`, `REFUERZO_PD` |
| una mano se vuelve dos mujeres; la madre entra por la ventanilla | deriva de H3 | «no inventes»; rehacer con la instancia viva |
| subtítulos chinos en 9 clips, dos veces | el estilo nombra el género | describir el look sin nombrarlo |
| cadena rota, 28 min de placa parada | encadenado | sueltos; cabeza primero |
| 6,58 s falló 4 de 5; 5,88 pierde 1 de 10 | VRAM | 5,17 y se parte |
| la placa cósmica salió con la protagonista sentada, dos veces | H3 mete gente | placas como imagen fija |
| once clips de ruido | placa defectuosa | detector + QC antes de destruir |
| $12,40 contra $9 | máquina colgada, clip largo, tres QC | por fiabilidad; 5,17; una pasada |
| ~$10 por un video de $2 | imagen vieja sin nodos H3 + placa defectuosa | `setup.sh` verifica y actualiza |

## B.3 Números del recap

- @jcfdlw: 77 tomas en 3:01, corte medio 2,36 s, 22,7 cps hablando, sin
  música, 3:4 con barras dentro del 9:16, mono.
- Nosotros: 41 planos en 4:00, corte medio 5,85 s. Cortar como ellos cuesta el
  doble de GPU (412 s generados para 181 de línea; con reuso 338).
- 4 minutos ≈ 3 h de GPU ≈ 45 min de pared ≈ $2-2,5 de GPU + $1,50 de imágenes
  si sale limpio. Real: $4,86 la corrida limpia de la réplica.

## B.4 ► Decisiones tomadas

- El ritmo de corte a 5-6 s es un apartamiento **deliberado** de la referencia,
  por el piso de H3. Se mantiene hasta medir retención.
- `largo.json` permite cortes de hasta 15 s: **no revisado contra lo medido**;
  no se usa hasta corregirlo a 5,17.
- Antes de otro largo entero: **ver y escuchar EL LOCO DEL CARBÓN**, y hacer la
  muestra de 15 s de la sección D.

---

# C · VIDEO PARA MÚSICA (16:9, loop)

**Qué es.** Un solo escenario que se mira de fondo mientras suena una pista.
Sin voz, sin texto. El video se repite en bucle lo que dure la música. Hechos:
LLUVIA EN LA VENTANA (58 s, 10/9, cuatro tandas), ESTANQUE DE KOI (60 s, 13/9,
**12 de 12 a la primera**), INVERNADERO EN ÓRBITA (55 s, 13/9, tres tandas).

## C.1 El flujo, en orden

1. **Escena y encuadres antes que nada.** Un lugar, una hora, una luz. Se
   escribe la planta del lugar para que todos los dibujos coincidan. Cada
   encuadre tiene UN movimiento lento. El último y el primero de tamaño
   distinto: **el bucle se cierra en ese corte**, que es un corte más.
2. **`proyecto.json`**: `formato: largo`, `estructura: loop`,
   `negativos: false`, `segundos: 5.17`. Planos consecutivos no repiten tamaño
   con el mismo reparto (o `loc: null` + `refs` explícitas). `construir` a 0.
3. **Dibujos** con `barras.py` y revisión a ojo. Para otro ángulo del lugar,
   sin la locación de referencia.
4. **Máquina**: sólo 4×5090 verificada; `cazar.py` si no hay. Bajar por tandas
   de cuatro y controlar con tiras de 10 cuadros mientras se generan los demás.
5. **Rehechos** en la misma instancia con `empaquetar --solo`, apartando los
   clips viejos en la máquina, semilla nueva por plano.
6. **`destruir`** apenas están todos bajados y controlados.
7. **`bucle.py`**: corta 5,0 s de cada clip, escala a 1080p, ambiente de H3 a
   −18 dB, música cerrada con un cruce de 2 s, −14 LUFS en dos pasadas, y el
   «loop ×3» para mirar el empalme. `recortes.json` para usar sólo la parte
   buena de un clip u omitirlo.
8. **La música** entra como archivo: `bucle.py --musica <pista> --repite N`.

### El contrato con el módulo de música (a integrar)

- Entrada: un archivo de audio de duración arbitraria (mp3 o wav).
- `bucle.py --musica <pista> --largo-de-pista`: repite el loop (o los loops,
  ver D) hasta cubrir la pista, corta al largo exacto de la pista y funde el
  último segundo de video a negro con el final del audio. **Pendiente de
  implementar** (hoy existe `--repite N` con la música loopeada, no la música
  mandando).
- Salida: `<título> - <pista>.mp4`, 1920×1080, −14 LUFS.

## C.2 Lo que falló y cómo se arregló

| síntoma | causa | arreglo |
|---|---|---|
| gente en la ventana, cactus, fuego, nubes, manos (7 de 12) | los bloques negativos inducen lo que prohíben | `negativos: false`, audio en positivo |
| una chica entra y se sienta; una familia entra | silla vacía + escritorio + espacio de cuarto | encuadres cerrados de objeto; dibujar lo que H3 «quiere» (la silla) |
| la lluvia chorrea adentro | ventana pegada a los objetos | ventana fuera de foco o sin ventana |
| H3 abandona el dibujo en el cuadro 1 | dibujo abstracto (el piso con la luz) | dibujos figurativos |
| letras en la etiqueta del disco (4 intentos) | superficie escribible | macro sin etiqueta; `recortes.json` |
| la ventana pasa a día; la luz magenta vira o se apaga; globos de luz | luz artificial de color y «motas» inestables | un movimiento por plano, «todo lo demás es pintura quieta», sin motas; luz natural rinde mejor |
| el ojo de buey se vuelve escotilla | el texto decía «hatch» | el `mueve` describe el dibujo |
| letterbox en 10 de 14 dibujos | nano banana 16:9 + «film» | frase de lienzo completo + `barras.py` |
| tres generales salieron de frente | la referencia manda el encuadre | sin referencia para otro ángulo |
| máster a −18 LUFS | loudnorm de una pasada | dos pasadas |
| tres hosts desverificadas colgadas | desverificada = no arranca | sólo verificadas; cazador; techo de precio |

## C.3 Números

- 0,77 min de GPU por segundo (16:9 igual que vertical en un host sano).
- 12 clips ≈ 10 min de generación ≈ sesión de 25-35 min.
- Rendimiento por tanda: LLUVIA 5/12 → KOI 12/12 → INVERNADERO 8/12. El salto
  es el prompt positivo y los encuadres cerrados; el retroceso, la luz
  artificial de color.
- Costo: LLUVIA $2,70 + $1,50; KOI e INVERNADERO $2,68 + $1,20 los dos.

---

# D · LA HIPÓTESIS DE LOS 15 SEGUNDOS

**El pedido (14/9):** los videos tienen que durar 10-15 s, no un minuto; por
idea, dos o tres muestras de 10-15 s. Lo que eso cambia, formato por formato,
con la unidad de H3 en la mano: **un clip de 5,17 s, del que se usan ~4,9**.

## D.1 La unidad: tres clips

| duración objetivo | clips | línea útil | GPU (4×5090) | costo de GPU si pasa | imágenes |
|---|---|---|---|---|---|
| 10 s | 2 | 9,8 s | ~8 min de GPU, ~4 de pared | ~$0,15 | 2 + madres |
| 15 s | 3 | 14,7 s | ~12 min de GPU, ~4 de pared | ~$0,20 | 3 + madres |

Tres muestras de 15 s son **9 clips**: una sola ronda de cuatro placas más una
de cinco, unos 10 minutos de máquina. **Menos que un short de 60 s**, y con
tres apuestas en vez de una. El overhead fijo de la sesión (arranque, descarga,
QC) pesa más que la generación: conviene generar las muestras de varias ideas
en la misma sesión.

## D.2 Cómo queda cada formato

**SHORT de 15 s (`short-15`, estructura nueva).** Tres tramos y tres clips:
HOOK 0-3 (corte 1,5-3), DESARROLLO 3-10 (un plano de hasta 4,9 o dos), CIERRE
10-15 (el pago y el bucle: la última imagen empalma con la primera). Es la regla
3/8/12 de `short-23` comprimida. Sin el problema de A.4: ningún corte supera
4,87 s. Por idea, **tres variantes del gancho** con el mismo desarrollo, y se
publica la que mejor mida. Voz: dos o tres líneas, medidas con la voz elegida.

**LARGO.** La unidad no cambia (4 min son 41 planos). Lo que cambia es que
**antes del largo se hace la muestra**: tres planos del mismo guion (el gancho,
un plano de emoción con cara, un plano de acción) con la voz medida, en una
sesión de 10 minutos. Si la muestra no convence en estilo, cara y densidad, no
se generan los otros 38. Es la puerta que faltó en EL LOCO DEL CARBÓN.

**MÚSICA.** El loop pasa de 12 clips a **3 clips de 15 s**. Con una pista de 3
minutos, un loop de 15 s se repite 12 veces: se nota. Por eso la unidad es
**dos o tres loops de 15 s del mismo escenario** (por ejemplo: general,
detalle, otro detalle; después otro trío), que se alternan: un ciclo de 30-45 s
sin que ningún trío se vea dos veces seguidas. El cierre del bucle sigue siendo
un corte más. El módulo de música manda la duración total (C.1, el contrato).

## D.3 ► Qué hay que construir para probarlo

1. `estructuras/short-15.json` y `estructuras/loop-15.json` (15,5 s, un tramo).
2. `bucle.py --largo-de-pista` y soporte de **varios loops** (una lista de
   carpetas de clips que se alternan).
3. Una sesión de prueba con las tres cosas juntas: una muestra de short, una
   muestra de largo con voz, dos tríos de loop. Unos 20 clips, ~25 minutos de
   máquina, ~$1,50.

Nada de esto está hecho: **espera el OK.**

---

# E · LAS CONTRADICCIONES, RESUELTAS

| tema | versiones que conviven | ► lo que manda |
|---|---|---|
| largo del clip | 7,3 / 6,6 / 5,9 / 5,17 según el documento | **5,17 s**; ≤ 4,87 de línea; lo demás se parte. Propagar a `REGLAS.md` 38, `recap.json`, `PROMPT-GUIONISTA-*` |
| dónde va la voz en el flujo | README «en paralelo desde el paso 2»; regla 40 «primero» | **primero**, medida, antes de cortar planos |
| densidad de escritura | 17 teóricos / 14-16 / ~25 de la referencia | **la voz elegida, medida** (Kate 16,7; Pablo 10,5). La referencia: 20,6-22,7, no 25 |
| interrupción de patrón | 8-12 / 10-12 / 12 | **12 s** en short-60 y 90, **8** en short-23 (lo que valida el JSON) |
| caras | regla 22 «taparlas» vs recap «caras sí» | tapadas en el short; **sí en el recap**, PM/PA, PP en picos |
| una voz por plano (regla 9) | vigente en largo.json, anulada en recap | vale sólo donde H3 genera la voz; **en voz en off no aplica** |
| subtítulos quemados | obligatorios en recap; «no» en @nothingwasfilmed | **sí** en recap y short; la excepción se declara |
| bloques negativos | siempre / nunca | **con personajes sí; escenas quietas y de objeto no** (0.3) |
| costo por imagen | $0,13 / $0,04 | **$0,039** (Flash); el 0,13 era el Pro llamado por accidente |
| costo de un largo de 4 min | $5 / $9 / $12,40 | **$4,86 de GPU limpio + $1,50 de imágenes**; con tropiezos el doble |
| velocidad en 16:9 | 0,91 vs 0,77 | **igual que vertical**; el 0,91 era el host |
| `recap.json` declara `formato: short` | | correcto para el módulo (vertical); «largo» es el nombre del formato apaisado, no de la duración. Renombrar algún día |
| conteos | 39/40 reglas, 9/11/14/16 trampas | **40 reglas, 16 trampas**; los resúmenes estaban viejos |
| `ESTADO-SHORT.md` (25/8) | dice que la voz no está cronometrada | resuelto el 29/8; **el documento está vencido** |

---

# F · LO QUE SIGUE ABIERTO

1. **Publicar y medir.** Es el pendiente más viejo: ninguna estructura deja de
   ser hipótesis hasta que haya una gráfica de retención propia.
2. **Ver y escuchar EL LOCO DEL CARBÓN** y la réplica enteros.
3. **Corregir `short.json` y `largo.json`** al piso de 5,17 (A.4, B.4).
4. **El módulo de música** y `bucle.py --largo-de-pista` (C.1).
5. **Las estructuras de 15 s** (D.3).
6. **El estimador**: familia de GPU y overhead fijo (subestima 2× en shorts).
7. **`alquilar` que recuerde hosts que colgaron.**
8. **La muestra de 15 s como puerta de todo largo.**
9. **EL FARERO**: escrito, medido, empaquetado, sin generar.
10. Doblaje: el corrimiento de boca en 17 planos, MuseTalk/LatentSync, unificar
    los dos motores.
11. Documentos vencidos a retirar o marcar: `ESTADO-SHORT.md`, `PASO-A-PASO.md`,
    el `README.md` de la raíz (Veo), `REGLAS-PLANOS.md`, `REGLAS-ENCADENADO.md`.

---

## Fuentes

`ESTRUCTURA-POR-CAPAS.pdf` · `h3pipeline/REGLAS.md` (40) · `h3pipeline/VAST.md`
(16 trampas, 9 reglas) · `COSTOS-H3.md` §11-14 · `PENDIENTES.md` ·
`ESTADO-PROYECTO.md` · `ESTADO-SHORT.md` · `ESTADO-LARGO.md` · `ESTADO-DOBLAJE.md`
· `ISOCRONIA.md` · `VOZ-EMOCION-V3.md` · `PROMPT-GUIONISTA-SHORT.md` ·
`PROMPT-GUIONISTA-LARGO.md` · `PROMPTING-ETAPAS.md` · `referencias/FORMATOS.md` ·
`referencias/jcfdlw/ANALISIS.md` · `referencias/nothingwasfilmed/ANALISIS.md` ·
`mis-videos/*/NOTAS.md`, `RECETA.md`, `brief.md`, `proyecto.json`, `metricas.json`
· `h3pipeline/estructuras/*.json` · los docstrings de `h3pipeline/*.py`.
