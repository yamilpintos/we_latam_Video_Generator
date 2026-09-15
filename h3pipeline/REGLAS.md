# Las reglas, y qué costó aprender cada una

Todo lo de acá está implementado en el módulo: no hay que acordarse de ninguna
al escribir un plano. Está escrito para saber **por qué** el módulo hace lo que
hace, y para no sacar un bloque de prompt "porque parece redundante".

Reemplaza a `REGLAS-PLANOS.md` y a `REGLAS-ENCADENADO.md` de la raíz, que
quedan como historia.

---

## 1 · Planos independientes, no clips encadenados

Una escena no es una toma: es una serie de planos que se cortan entre sí.
Encadenar clips —cada uno arrancando en el último fotograma del anterior— para
fingir una toma continua peleaba contra el modelo.

| | encadenado | por planos |
|---|---|---|
| junturas | había que disimularlas | no existen, hay cortes |
| cámara | tenía que frenar antes de cada juntura | libre |
| identidad | el clip 3 estaba a 2 generaciones del dibujo | todos a 1 |
| un clip malo | arrastraba a los dos siguientes | se rehace solo |
| paralelismo | 10 unidades, 3 tandas | 42 unidades, parejo |
| modelos | Ref2VA + FL2VA (106 GB) | sólo FL2VA (59 GB) |

Y sale entre 20 % y 35 % más barato: 45-56 min contra 69.

## 2 · Máximo 15 segundos, mínimo 5,2 — y no es capricho

H3 acepta `length = 17k + 5` fotogramas a 24 fps y está entrenado entre 124 y
362. Eso es de **5,17 a 15,08 s**. Fuera de ahí no está roto: está adivinando.

`grilla.encajar()` acomoda cualquier duración al valor más cercano, y `validar()`
avisa si alguna se fue del rango.

Los planos cortos además salen **baratos de más**: el costo por segundo sube con
la duración, porque la atención crece con el cuadrado del largo de la secuencia.

## 3 · El mínimo de 5,2 s y el ritmo del short

Un short necesita cortes de 1,5 a 3 s al principio o pierde al espectador, y H3
no puede generar tan corto. La salida es **generar de más y usar sólo el mejor
pedazo**: cada plano lleva `usa` con el tramo que va a la línea de tiempo. En
PROFUNDIDAD se generan 74,8 s para usar 60.

Se declara `corta` (lo que dura en la línea) y el módulo calcula cuánto generar,
con medio segundo de colchón: el final de un clip de H3 suele derivar, así que
conviene tener de dónde recortar y no usar el último cuadro.

## 4 · El tamaño de plano va en el dibujo Y en el prompt

La regla que más caro salió. Si la escala está sólo en la imagen, H3 la
"corrige" al animar y los personajes salen gigantes. Si está sólo en el prompt,
el dibujo ya viene mal encuadrado.

## 5 · La escala se declara en fracciones de la altura del cuadro

`"pequeño"` o `"a lo lejos"` no significan nada operativo. Esto sí:

> his full height is about ONE SIXTH of the image height, and clearly SHORTER
> than the fountain is wide

Un número y una comparación contra algo que está en la imagen. Los seis tamaños
(`PGE PG PA PM PP PD`) tienen su fracción escrita en `prompts.TAMANIO`.

El `PM` necesitó además decir que el borde de abajo **corta**, y nombrar lo que
no tiene que estar: con "waist up" a secas, el generador dibujaba el personaje
entero siete veces de siete.

## 6 · El dibujo manda

Si el encuadre sale mal, **no se arregla con el prompt de video**: se regenera
el dibujo, se re-empaqueta y se relanza ese plano.

Es la ventaja grande del método. Un error de encuadre se ve en un PNG que costó
22 segundos, no después de siete minutos de generación con la máquina cobrando.
El storyboard entero se revisa **antes** de prender la GPU.

## 7 · La cámara puede moverse

Es la libertad que se ganó al dejar de encadenar, y hay que usarla. Travellings,
grúas, paneos, push-ins: no hay juntura, hay corte, y el corte tapa cualquier cosa.

## 8 · No cortar entre dos planos iguales

Cortar entre dos planos del mismo tamaño, en la misma locación y con la misma
gente da un brinco, no un corte. `validar()` lo chequea solo — está ahí porque
leyendo la lista a ojo se pasó uno.

Pide **locación declarada** a propósito: sin ella no se sabe si dos planos
generales seguidos son el mismo encuadre repetido o dos distancias muy distintas
del mismo hallazgo, que es lo normal en un short.

## 9 · Una sola voz por plano

Dos personajes alternando en diez segundos es pedirle demasiado al modelo. Una
línea, un personaje, unas doce palabras. Si hay que ir y volver, son dos planos
— que es exactamente como se filma un contraplano.

## 10 · El bloque de castellano va en TODOS los prompts

Hablen o no. Sin él, H3 mete murmullos, gritos de vendedor y chusmerío de fondo
**en inglés**, que fue lo que arruinó el audio de una versión entera.

No se pide silencio: se pide que **si alucina, alucine en castellano**.

## 11 · «No inventes»

H3 arranca clavado en el primer fotograma pero **deriva hacia el final del
plano**: aparecieron cactus saguaro en un desierto árabe, fuego alrededor de un
personaje, y en un primer plano se coló la cara de otro. 5 planos de 39 quedaron
inservibles por esto.

La duración no tiene nada que ver: la correlación entre largo del plano y deriva
fue −0,04, o sea ninguna.

## 12 · El humo, sólo donde hace falta

H3 dibuja humo y polvo como cúmulos redondos de caricatura, que chocan con
cualquier estilo. Hay que pedirle explícitamente la textura — pero **sólo en los
planos que lo necesitan**: cargar todos los prompts con restricciones que no
aplican diluye las que sí.

## 13 · El vestuario se describe en cada prompt, aunque esté en el dibujo

La hoja de modelo sostiene la cara. El texto sostiene la ropa. Sin la
descripción, la faja cambia de largo y los parches se mudan de lugar entre plano
y plano. Vive en un solo lugar (`personajes` del proyecto) y se inyecta sola.

## 14 · Hojas de modelo con vueltas, no vistas sueltas

Cada personaje con las cuatro vistas —frente, tres cuartos, perfil y espalda— en
una sola imagen. Es la práctica estándar de animación: le da al modelo los
ángulos resueltos en vez de que los invente cuando el plano pide un perfil.

## 15 · La relación de aspecto se pide por parámetro, no por texto

Describiéndola en el prompt, nano banana devolvió tres relaciones distintas en
una misma tanda de 42. Va por parámetro de la API **y** como refuerzo en el
texto, y aun así `empaquetar` normaliza al final: recorta al centro a la
resolución exacta de H3, porque un dibujo en otra relación entra aplastado y los
personajes salen gordos.

## 16 · Los subtítulos no necesitan Whisper

Como nosotros elegimos cuánto dura cada plano, el tiempo de cada línea es una
suma. El SRT se escribe con BOM (`utf-8-sig`): sin él, libass lo lee como
Latin-1 y destroza los acentos al quemarlos.

## 17 · Cortar y recodificar por separado, y recién después concatenar

Cortar con `-c copy` mueve el corte al keyframe más cercano, que puede estar a
un segundo — justo lo que arruina un ritmo pensado al décimo. Cuando no hay que
recortar (el largo), se concatena copiando el video pero **recodificando el
audio** a una sola pista continua: es lo que evita el chasquido en cada corte al
pegar decenas de pistas sueltas.

## 18 · La ley de retención 2026

Las estructuras salen de `Estructuras_Contenido_Alta_Retencion_2026.docx`.
Lo que manda la distribución es **el porcentaje del video que se completa**, no
los likes ni los seguidores.

**No hay una duración, hay tres**, y cada una tiene su umbral:

| | dura | retención objetivo | para qué |
|---|---|---|---|
| `short-23` | 23 s | 65 % | alcance, descubrimiento |
| `short` | 60 s | 50 % | multiplataforma, el default |
| `short-90` | 90 s | 45 % | guardados, comunidad |

El umbral **sube cuanto más corto es el video**. Y 60 s es el punto donde entra
en las tres plataformas: Shorts corta en 60, TikTok premia 60-90, Reels necesita
menos de 90 para Explorar.

Lo que exige en todos: ventana crítica de 1-3 s, triple refuerzo del gancho
(imagen + sonido + texto), anteponer el **resultado concreto** a la promesa
genérica, interrupción de patrón cada 8-12 s, y loop de cierre.

## 19 · Un corte no es una interrupción de patrón

En un short todo son cortes cada 3-6 s. Si un corte contara, la regla no diría
nada nunca.

Lo que cuenta es un **cambio de régimen**: entra una luz de otro color, aparece
o desaparece un sonido, cambia la velocidad del montaje, se rompe una
expectativa. Por eso lo marca el tramo, o el plano que lo hace a propósito.

## 20 · El texto en pantalla va en post, siempre

El triple refuerzo pide texto sobre la imagen en los primeros 3 s. Pero los
modelos de imagen y video **destrozan el texto**, y en un gancho eso es fatal.

Se declara en el plano (`"texto"`) y sale como entregable de montaje en
`texto_en_pantalla.txt`, con sus tiempos. **Nunca se le pide al generador.**

Es la misma razón por la que un contador de profundidad se pone en post: los
números que cambian son lo peor que le sale a un modelo de video.

## 21 · El audio de H3 viene clipeado

Medido sobre los doce clips de un short: el pico del audio que devuelve H3 está
en **+2,68 dBFS**, o sea por encima de cero. No es un defecto del montaje, viene
así del modelo.

Por eso la mezcla final se masteriza siempre con `loudnorm` a −14 LUFS y −1 dBTP,
que es el estándar de YouTube. Sin ese paso la distorsión llega al máster.

## 22 · Las caras humanas en primer plano son la debilidad del modelo

El valle inquietante mata la retención en un segundo. Taparlas (máscara, casco,
sombra, espaldas, manos) esquiva la debilidad más grande sin que se note. Y
elegir un entorno que perdone —agua turbia, humo, niebla, poca luz— es donde los
artefactos de generación desaparecen.

## 23 · Los números que cambian van en post, no en el prompt

Los generadores de video destrozan el texto en movimiento. Un contador que sube
se pone como gráfico encima, y además retiene mejor.

## 24 · La voz que cruza el corte no la hace H3

H3 no tiene voice ID: inventa una voz distinta en cada clip. La regla es **H3
genera lo que nace y muere dentro del plano; ElevenLabs, todo lo que cruza el
corte**. En el short eso es toda la voz, en off. En el largo, la narración.

Y si se puede, que no se vea la boca: con un regulador, un casco o de espaldas,
el modelo no tiene que sincronizar nada.

## 25 · La densidad manda, y se arregla en el texto

El español corre a ~17 caracteres por segundo. Debajo de 11 cps la voz termina y
los labios siguen; arriba de 22 no entra ni comprimiendo.

Los topes de deformación son mucho más chicos de lo que parece: **estirar
tolera 1,08×**, comprimir 1,15×. Ese 1,08 está medido en producción — *"una voz
aguda ralentizada más de 10 % suena masculina/pastosa aunque el pitch no
cambie"*, con tres voces femeninas distintas en la misma escena.

Consecuencia: **si la línea es corta para su hueco se escribe más texto.**
Regenerar sale casi gratis; deformar se escucha.

## 26 · Un tag de emoción cambia la voz, no sólo la intención

`[sad]` en intensidad media corre el timbre lo justo para que una línea suelta
en medio de un monólogo neutral suene a otra persona. Y eso rompe lo único que
ElevenLabs aporta al proyecto, que es sostener un personaje entre cortes.

Neutro por defecto. Un tag por línea como máximo, al principio, y sólo en
intensidad alta. Agotá la puntuación antes de meter un tag.

## 27 · Varias redacciones por línea, y gana la que mide mejor

La densidad estima, pero a nivel toma el error llega al 30 %. Dos o tres
redacciones, se sintetizan todas, entra la de factor más cercano a 1,00. En
producción eligió sola `[yawns]` sobre `[sighs]` y descartó un suspiro que se
comía el bloque entero.

## 28 · Al doblar, la ventana la define la boca

No el ASR: agrupa en frases y esas frases se comen silencios enteros — una línea
que el ASR daba como 8,63 s tenía 5,24 s de habla. Se mide por energía sobre el
stem de voz de demucs.

**Un solo factor de tiempo por clip**, nunca por palabra: doce palabras dan doce
cambios de escala independientes y suena entrecortado.

Y se estira en el dominio del tiempo, **nunca remuestreando**: remuestrear
cambia el tono junto con la velocidad y el personaje suena distinto en cada
línea.

## 29 · H3 no sincroniza su propia boca con su propio audio

Medido en dos planos: mueve los labios **0,70 s** y **0,85 s** antes de emitir
sonido. Durante ese hueco la onda está en cero, así que ninguna medición sobre
el audio puede encontrarlo — es la trampa que más tiempo hace perder, porque el
instinto dice que la respuesta está en la forma de onda.

**No intentes automatizarlo por diferencia entre fotogramas.** Está probado: la
región de mayor cambio resulta ser el humo o el resplandor, no la boca.

Se mide por ojo con una hoja de contacto a 10 fps, una vez por plano.

---

---

## Sobre la máquina

## 30 · El ancho de banda pesa más que el precio por hora

Hay que bajar 59 GB antes del primer plano. A 2000 Mbps son 4 minutos; a 30
Mbps, **262 minutos** de máquina encendida esperando — más caro que generar el
video entero. Por eso `vast.buscar()` ordena por **costo total del trabajo**.

## 31 · `SOLO_FL=1`: la mitad de la descarga, gratis

Todos los planos arrancan de su dibujo, así que sólo se usa FL2VA. Ref2VA no se
toca nunca. En el perfil `max` son 45 GB menos. Es el default del `setup.sh`.

## 32 · Los pasos son la palanca de costo dominante

20 pasos cuestan **2,3×** lo que 8. Es la decisión que más plata mueve.

Pista contraintuitiva, sin conclusión todavía: los clips de 8 pasos pesan el
doble que los de 20, lo que sugiere que 20 pasos sin turbo salen *más suaves*,
no más detallados. Decide el ojo.

## 33 · `ref_image_size=max` sale casi gratis

+8 % de tiempo, y es la palanca de fidelidad de identidad. Sólo aplica cuando se
usan imágenes de referencia, que este pipeline no usa: ese trabajo lo hace el
generador de imágenes al dibujar el storyboard, en la máquina local y con la GPU
alquilada apagada.

## 34 · Las trampas del entorno de Vast

- **Dos árboles de ComfyUI** (`/workspace/ComfyUI` y `/opt/workspace-internal/
  ComfyUI`). `find` suele encontrar el que no es: hay que preguntarle el
  directorio de trabajo **al proceso**, no al disco. Esa confusión costó una hora.
- **ComfyUI cachea el listado de modelos al arrancar.** Sin reiniciar, los
  loaders devuelven listas vacías y el `/prompt` se rechaza con
  `value_not_in_list`.
- **Un glob recursivo desde `/` tarda varios minutos** con 100 GB de modelos en
  el disco, y parece que el script murió.
- **El Upload de Jupyter aplasta las carpetas**: por eso se sube un ZIP.
- **Los saltos de línea de Windows rompen los `.sh`**: `sed -i 's/\r$//'` antes
  de nada.
- **Pedir 250 GB de disco.** Con 150 se llenó y una corrida no llegó a arrancar.

## 35 · La licencia excluye países

La MiniMax H3 Community License excluye **EE.UU., la UE, el Reino Unido y Corea
del Sur** del despliegue local. Mirá el país del host **antes** de alquilar;
`vast.buscar()` lo filtra solo.

## 36 · Una placa de 32 GB no es cualquier placa de 32 GB

Una **Tesla V100** tiene los mismos 32 GB que una RTX 5090 y es de 2017: sin
bf16 nativo, que es lo que piden las LoRAs turbo de H3. El filtro por gigas no
las distingue; `vast.py` las descarta por nombre.

Y `deverified` es una máquina a la que Vast le **sacó** la verificación. El
filtro `verified` de la consulta las deja pasar igual: hay que mirar el campo
`verification` en la respuesta.

## 37 · Apagarla

Se paga por hora prendida, no por clip generado. Un pod olvidado toda la noche
cuesta más que todo el trabajo del día.

- **STOP** apaga la GPU pero sigue cobrando el disco. Conviene si volvés en unos
  días: ahorra rebajar los 59 GB.
- **DESTROY** borra todo. **Bajate los archivos antes** — incluidos los planos
  sueltos y `metricas.json`.

## 38 · Con encadenado, 5,9 s por plano es el techo en 32 GB

La regla 1 dice que el default son planos sueltos. Cuando se elige encadenar a
propósito —una persecución, una maniobra que necesita inercia real— aparece un
límite que el plano suelto no tiene.

Un eslabón carga el GGUF de 23,9 GB **más** el último fotograma del anterior
como condicionamiento. Suelto, un plano de 7,3 s entra en 32 GB. Encadenado, no:
muere con out-of-memory en el **primer** eslabón, y reintentar no lo arregla
porque no es fragmentación, es que no entra.

**Una toma continua larga se hace con más eslabones cortos, no con eslabones
largos.** En CONTRAMANO, 18 segundos continuos salieron de tres eslabones.

**Y el "suelto sí llega a 7,3 s" tiene asterisco (31/8/2026):** en EL LOCO
DEL CARBÓN, con ComfyUI 0.34, de cinco planos sueltos de 7,3 s salieron tres
(S07, S33, S37) y **dos no entraron ni con el proceso recién arrancado** (S22 y
S30, nueve OOM entre los dos); a 6,6 s salieron. Los dos eran planos generales
exteriores con mucho detalle. Y en el **segundo host del mismo día, ni 6,6 era
seguro**: S04, S11, S17 y S34 cayeron a 6,6 incluso con proceso fresco y
salieron a 5,9 — la VRAM útil varía de host a host aunque el nombre de la
placa sea el mismo. Regla práctica escalonada: **5,9 s sale en cualquier
32 GB; 6,6 s sale casi siempre; 7,3 s es apuesta**. El costo de equivocarse
ya no es una corrida arruinada (el rescate acorta el sufrimiento), pero cada
plano que hay que bajar y rehacer son ~15 min de máquina tirados: ante la
duda, escribí el plano en 5,9-6,6 desde el principio.

Y el tope de la regla de identidad sigue: **máximo tres eslabones por cadena**.
Al cuarto la cara, la ropa y la luz ya derivaron demasiado del dibujo original.

## 39 · Una cadena rota deja una placa parada, y eso se paga

Un plano suelto que falla se rehace y no molesta a nadie. Un eslabón que falla
**bloquea todos los que vienen detrás**, y como `reparto()` manda la cadena
entera a una sola placa para no partirla, esa placa se queda sin trabajo el
resto de la corrida mientras sigue cobrando por hora.

Pasó: 28 minutos de una RTX 5090 sin hacer nada.

**El cabeza de cadena es el plano de mayor riesgo de la tanda.** Se genera
primero y se verifica antes de repartir el resto.

## 40 · El guion de voz se escribe PRIMERO, y los planos lo sirven

Aprendida con EL DRON DEL VOLCÁN (30/8/2026): se diseñaron los planos primero
y la voz se metió después en los huecos. Cuando una línea no entraba en su
ventana, se recortaba — y quedó críptica ("Un intento. El gancho, la ceniza,
el pulso."). Nunca se decía que el rescate lo hacía *otro* dron. El video salió
técnicamente bien **y no se entendía la historia**, que es el único defecto que
ningún máster arregla.

El método correcto, verificado el mismo día con EL FARERO:

1. **Primero la historia completa**, como narración lineal que un chico de doce
   entiende: quién, qué quiere, qué se le cruza, cómo termina. Cada dato que el
   espectador necesita se DICE (o se ve sin ambigüedad); nada queda para
   deducir.
2. **Cada plano se diseña para ilustrar su línea**, no al revés.
3. Si una línea no entra en su ventana, **se reescribe entera conservando el
   sentido** — recortarla hasta el fragmento poético es cambiarle el defecto de
   lugar.
4. La densidad se calcula con el ritmo **medido de la voz elegida**, no con los
   17 cps teóricos: Pablo corre a ~10,5 cps reales con sus pausas. Con eso,
   EL FARERO midió 12/12 líneas en rango a la primera síntesis; con los 17
   teóricos, EL DRON DEL VOLCÁN necesitó tres pasadas de reescritura.

Y la vara de simplicidad: **si la historia necesita que el espectador infiera
algo para entender el final, es demasiado compleja para 60 segundos.**

---

## Desde el repaso de la documentación oficial (14/9/2026)

El detalle, las fuentes y lo que falta probar: [H3-OFICIAL.md](H3-OFICIAL.md).

## 41 · El prompt va en el formato oficial de MiniMax

Instrucción de primer fotograma + `integrated_multimodal_description` +
`overall_soundscape` + `non_diegetic_music` (o las seis secciones de Ref2VA).
El README lo llama "critical to the quality"; el texto libre de las reglas
10-12 es el formato viejo. Armadores: `prompts.oficial_i2va` y `oficial_ref2va`.

## 42 · El primer fotograma se describe entero antes de la acción

Como el reescritor oficial: tamaño, personas con ropa y posición, lugar, luz;
recién después "Early in the clip…", "As the clip progresses…".

## 43 · Diálogo con ID y labios cerrados antes y después

`Jack (S1), <voz descripta>, says …: <d>[English] …</d> Exactly as his voice
stops, his lips close…`. Contra el balbuceo antes y después de la línea.

## 44 · Sin negativos y con la música en N/A

H3 no tiene prompt negativo (CFG destilada) y lo que se nombra se invoca. Si la
música va aparte, `non_diegetic_music: N/A`.

## 45 · La voz constante sale de Ref2VA con voz de referencia

Casting con FL2VA → recorte con `voz_ref.py` (32 kHz estéreo, 2-15 s, múltiplo
de 800 muestras) → todos los clips del personaje en Ref2VA con `<Audio 1>`.
Todo sale de MiniMax.

## 46 · En Ref2VA, los nombres de entrada exactos y el `audio_vae` conectado

`ref_images.ref_image_0`, `ref_audios.ref_audio_0`: un nombre mal escrito se
ignora sin error. Sin `audio_vae` la voz no condiciona nada.

## 47 · La LoRA turbo de 768p va a 8 pasos y shift 6/3

Se usaba la de 4 pasos a 8 pasos y shift 12. La tabla de lightx2v dice 6/3 para
las entrenadas a 768p.

## 48 · Replicar un video: un clip por encuadre y la boca manda el `usa`

Cortes con ffmpeg + mirar cada toma (el detector se salta cortes); Whisper por
palabra; `usa_ini = arranque_de_la_voz + (inicio_toma − t0_línea)`.

## 49 · Con GPT: el filtro frena poses de tono sexual, no la violencia

Cuchillo en el cuello y sangre pasan; a horcajadas, mano en la cadera, cabeza
atrás contra el cuello, no. Se reescribe como abrazo protector o susto.

## 50 · GPT abre los planos medios: rehacer forzado y, si no alcanza, recortar arriba

"Crop like a tight TV close two-shot… bottom edge cuts across the chests"; si
igual corta a la cintura, el 80 % superior de la imagen.

## 51 · La hoja de modelo arrastra su vestuario: el estado va escrito

Jack reaparecía con sombrero después de sacárselo. "BARE-HEADED with NO hat".

## 52 · Las referencias de entrada son lo más caro de cada imagen con GPT

~4.000 tokens por imagen con locación + hojas, contra 158-1.372 de salida. Y la
cuenta Tier 1 genera 5 imágenes por minuto: `--hilos 4` y reintento del 429.

## 53 · El formato viejo hace que H3 lea en voz alta la etiqueta de audio

Muestra A (14/9, clip MA01): con `[Speech] a man speaking low and slow` en el
prompt, la voz dijo «A man, screeching and slow, now moan for me». Con el
formato oficial (MA02 turbo, MA03 a 20 pasos) dijo sólo «Now moan for me». El
formato oficial no es opcional: el viejo mete texto de dirección en la boca.

## 54 · Nombrar ropa fuera de cuadro hace que H3 corte para mostrarla

Los dos castings de Hannah (primer plano, cuchillo en el cuello) describían
short, medias, polainas y zapatillas: en las dos semillas H3 cortó a mitad de
clip a un plano entero. En PP y PM se describe sólo lo que entra
(`oficial.solo_lo_visible`); los insertos no, porque el de las zapatillas
necesita las polainas. Misma familia que la 44 (lo que se nombra, se invoca):
«Her face never appears» se cambió por «the frame stays on this detail».

## 55 · Elegir voces sin oído: Whisper + pYIN + formantes

`casting.py` mide si dijo la frase (Whisper), F0 y SNR. La F0 sola engaña: Luka
gritando dio 340 Hz (rango de mujer). Los formantes lo resuelven — F3 de Luka
~2.330 Hz contra 2.515-2.770 de Hannah: tracto de hombre gritando agudo. Si el
personaje sólo grita (todas las líneas de Luka), la referencia gritada sirve.

## 56 · Repartir por pasos × segundos y con cola compartida

Por segundos a secas, el clip de 20 pasos (8,8 min) cayó en una placa con otro
más y una placa quedó quieta 4 min mientras otra seguía. `runner.costo()` pesa
`segundos × pasos / 8`, y con `COLA` (la pone `lanzar.sh`) cada placa, al
terminar lo suyo, reclama con `mkdir` atómico lo que las demás no empezaron.
`rescate.sh` hace `unset COLA`, si no encontraría todo reclamado.

## 57 · En Ref2VA, un segundo sujeto definido en un primer plano provoca un corte

Muestra B (14/9): en tres de cuatro primeros planos de Jack con Hannah apenas
como borde desenfocado, `<Subject 2> is Hannah…` hizo que H3 cortara a un plano
de ella a mitad de clip (MB01, MB03 a 20 pasos, MB04 con ancla del cuadro 0).
La misma toma en I2VA no cortaba. En PP y PD se define sólo al que habla, y el
`summary` termina con «a single continuous take on <Subject 1>». El ancla del
cuadro 0 (`guia0`) no lo evita; 20 pasos tampoco.
**Validado en la corrida del 14/9:** T49 (el encuadre que cortaba en MB01 y
MB04), T47, T23 y T46 se sostienen en Jack los 5 s enteros.

## 58 · Las placas suben a input/ con su puerto en el nombre

Cuatro runners subiendo el mismo `voz_jack.wav` con overwrite: uno leyó el
archivo a medio escribir («LoadAudio: Invalid data found»). `subir()` antepone
`p<puerto>_`.

## 59 · Con la subida lenta, JPEG q95 dentro de los .png

Desde la PC del usuario a Taiwán la subida anda en 100-180 KB/s: 118 MB son
~15 min. Los primeros fotogramas re-codificados a JPEG q95 (mismo nombre .png;
PIL detecta el formato por contenido) dejan el paquete en 32 MB. Y nunca
re-empaquetar el ZIP que se está subiendo: el remoto queda corrupto.
Bajar clips con `ssh … "tar cf - *.mp4" | tar xf -`, no uno por uno.

## 60 · Voz constante, medida: ECAPA de speechbrain

`speechbrain/spkrec-ecapa-voxceleb` (caché local; `LocalStrategy.COPY` en
Windows, audio con soundfile porque torchcodec no carga). Muestra B contra su
referencia: Hannah 0,75 (y 0,66 en off), Wady 0,64, Jack 0,28-0,50 (muy
parecidos entre sí, 0,61-0,87), Luka 0,41 gritando. Entre personajes ≤0,37.

## 61 · En líneas de una o dos palabras, la línea va al final del prompt

Corrida del 14/9: con «Shh.» y «Ah!» H3 llenó los segundos que sobraban leyendo
el texto que seguía a `</d>` («Exactly as his… Afterwards…» → «Exactly as his fed
heart of»). En líneas largas pasa menos y, cuando pasa, cae después del tramo
usado (T53, T55). Para ≤ 2 palabras, `oficial.descripcion_shot` dice primero
cámara, continuidad y lo que hace después, y cierra con «The sound is:
<d>[English] Shh.</d>» sin nada detrás.

## 62 · Validar los clips bajados contando cuadros, no por la duración

T11 llegó cortado a 21 de 124 cuadros (se cortó un `tar` por timeout) y ffprobe
igual informaba 5,17 s: la duración sale de la cabecera. Se descubrió al montar,
con la instancia ya destruida, y se salvó estirando la toma a ×0,70. `bajar_paralelo.sh`
ahora exige `nb_read_frames = 124`. Y antes de destruir: contar cuadros de todo.

## 63 · Montaje por cuadros y voz con la correspondencia de la toma que se ve

Recortar con `-t` redondea cada tramo hacia arriba: 82 tomas estiraron la imagen
0,9 s. Se corta con `-frames:v round(hasta·24) − round(desde·24)`. La voz de cada
línea se saca del clip de la boca con `t = inicio_toma + (t_clip − usa_ini)` de la
toma que MÁS se superpone con la línea (no la primera del encuadre), así la
sincronía labial sale por construcción aunque la ventana se haya corrido contra
el techo. `mis-videos/replica-danza/montar.py`.
