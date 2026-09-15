# Reglas del pipeline de planos

Reemplaza a `REGLAS-ENCADENADO.md`, que sigue valiendo si alguna vez hace falta
una toma continua larga de verdad, pero que ya no es el método por defecto.

El cambio de fondo: **una escena no es una toma, es una serie de planos que se
cortan entre sí.** Encadenar clips para fingir una toma continua de 30 segundos
peleaba contra el modelo. Cortar entre planos independientes juega a favor.

---

## Lo que se ganó al dejar de encadenar

| | encadenado | por planos |
|---|---|---|
| junturas | había que disimularlas | no existen, hay cortes |
| cámara | tenía que frenar antes de cada juntura | libre |
| identidad | el clip 3 estaba a 2 generaciones del dibujo | todos a 1 |
| un clip malo | arrastraba a los dos siguientes | se rehace solo |
| paralelismo | 10 unidades, 3 tandas | 42 unidades, parejo |
| modelos | Ref2VA + FL2VA | solo FL2VA |

---

## 1. Máximo 15 segundos, y no es capricho

H3 acepta `length = 17k + 5` fotogramas a 24 fps, y está entrenado más o menos
entre 124 y 362. Eso es de **5.2 a 15.1 segundos**. Fuera de ahí no está roto,
está adivinando.

`armar_planos.py` acomoda sola cualquier duración que pida el director al valor
más cercano de la grilla, y avisa si alguno se fue del rango.

Un plano promedio de la película dura 7.4 s. Está bien que sean cortos: los
planos cortos además salen **baratos de más**, porque el costo por segundo sube
con la duración (ver `COSTOS-H3.md` sección 11).

## 2. El tamaño de plano va en el dibujo Y en el prompt

Esta es la regla que más caro salió aprender. En la versión anterior los
personajes salían gigantes dentro del patio, y no era que uno fuera más alto que
otro: era que **los dos parecían titanes** en un espacio que debía tragárselos.

Si la escala está solo en la imagen, H3 la "corrige" por su cuenta al animar. Si
está solo en el prompt, el dibujo ya viene mal encuadrado. Tiene que estar en
los dos.

## 3. La escala se declara en fracciones de la altura del cuadro

`"pequeño"`, `"a lo lejos"` y `"empequeñecido por el palacio"` no significan nada
operativo. Esto sí:

> his full height is about ONE EIGHTH of the image height, and clearly SHORTER
> than the fountain is wide

Un número y una comparación contra algo que está en la imagen. Los seis tamaños
(`PGE PG PA PM PP PD`) tienen su fracción escrita en `TAMANIO`, dentro de
`armar_planos.py`.

## 4. El dibujo manda

Si el encuadre sale mal, **no se arregla con el prompt de video**. Se regenera el
dibujo con nanobanana, se sube de nuevo y se relanza el plano.

Es la ventaja grande del método: un error de encuadre se ve en un PNG que costó
22 segundos, no después de siete minutos de generación con la máquina cobrando.
El storyboard entero se revisa **antes** de prender la GPU.

## 5. La cámara puede moverse

Es la libertad que se ganó y hay que usarla. Antes cada clip tenía que terminar
con la cámara quieta y el personaje en pose sostenida, porque si no la juntura
pegaba un salto. Ahora no hay juntura: hay corte, y el corte tapa cualquier cosa.

Travellings, grúas, paneos, push-ins. Todo vale dentro de un plano.

## 6. No cortar entre dos planos iguales

Cortar entre dos planos del mismo tamaño, en la misma locación y con la misma
gente da un brinco, no un corte. Entre plano y plano tiene que cambiar el tamaño
o el ángulo.

`armar_planos.py` lo chequea sola y avisa. Está ahí porque leyendo la lista a
ojo se me pasó uno: E08 tenía tres planos medios seguidos, dos de ellos de la
princesa. Se arregló poniendo la pregunta y la respuesta en primer plano, que
además es donde van.

## 7. Una sola voz por plano

Dos personajes alternando en diez segundos es pedirle demasiado al modelo. Una
línea, un personaje, unas doce palabras. Si hay que ir y volver, son dos planos
— que es exactamente como se filma un contraplano.

## 8. El bloque de castellano va en TODOS los prompts

Hablen o no. Sin él, H3 mete murmullos, gritos de vendedor y chusmerío de fondo
**en inglés**, que fue lo que arruinó el audio de la versión anterior.

El bloque es explícito hasta la insistencia:

> SPOKEN LANGUAGE: SPANISH. Every voice, word, murmur, shout or crowd chatter
> heard in this shot is in Spanish. NEVER English. If any voice appears at all,
> it is Spanish.

No se pide silencio. Se pide que si alucina, alucine en castellano.

## 8b. Los IDs de hablante `(S1)` valen DENTRO del plano, no entre planos

Conviene dejarlo escrito porque se presta a confusión y ya nos costó una vuelta.

H3 acepta IDs de hablante estables —`(S1)`, `(S2)`— con la sintaxis
`(S1) [Spanish] "texto"`. Sirven para que el modelo no reparta una línea entre
dos bocas ni le invente un interlocutor al personaje. **Pero valen sólo dentro
de una generación.** El condicionamiento de voz sale del material de referencia
que va en *esa* llamada; no hay perfil de voz que se guarde ni se pueda invocar
en el clip siguiente.

O sea: **la premisa del proyecto sigue en pie.** H3 no sostiene un timbre entre
clips, y por eso toda la voz que cruza el corte va de ElevenLabs. Los `(S1)`
arreglan un problema distinto —el de dos voces mezcladas dentro de un mismo
plano—, no el de la identidad entre planos.

Hay además un
[bug abierto en el repo del modelo](https://github.com/MiniMax-AI/MiniMax-H3/issues/17):
en escenas con varios personajes el timbre de uno se filtra al otro, o una sola
voz se come a las dos. Reportado en Ref2VA —la variante que usamos— y reproducido
también en FL2VA. Sin respuesta de los mantenedores.

## 8c. Cerrar las vías de voz una por una, y llenar el hueco en positivo

H3 **rellena todo hueco de audio**. Si la línea dura dos segundos en un plano de
cinco, el modelo sintetiza algo para los tres restantes: murmullos, voces de
fondo, personajes que nadie pidió. Eso es exactamente el material que después
hay que doblar.

Pedir silencio no alcanza. Van tres cosas juntas, y las tres están en
`armar_planos.py`:

| qué | constante | cuándo |
|---|---|---|
| cerrar las voces ajenas | `SOLO_UNO` | planos con diálogo |
| cerrar todas las voces | `SIN_VOCES` | planos sin diálogo |
| declarar la música | `SIN_MUSICA` | siempre |

`NON-DIEGETIC MUSIC: N/A` se declara aunque no haya música: si el campo queda
vacío, el modelo a veces mete voces creyendo que son parte de una pista.

Y el hueco se llena **en positivo**. No basta con prohibir: hay que decirle que
ocupe la duración con el ambiente descrito —pasos, tela, agua, viento—, que es
lo que H3 hace bien.

## 8d. El diálogo se ancla en el tiempo

`(S1) starts speaking about one second into the shot and finishes before it
ends; the rest of the duration is the ambience above, with no speech.`

Sin anclaje la línea flota y el modelo rellena los bordes. Es literalmente lo
que pasó con el genio de Aladino: la boca se mueve 0,7 s antes de que empiece
el audio, y ese hueco no tiene nada que rescatar.

## 9. El vestuario se describe en cada prompt, aunque esté en el dibujo

La hoja de modelo sostiene la cara. El texto sostiene la ropa. Sin la
descripción, la faja cambia de largo y los parches se mudan de lugar entre
plano y plano.

Las descripciones viven en un solo lugar (`PERS`, en `armar_planos.py`) y se
inyectan solas en los 42 prompts. Cambiar el vestuario es cambiar una línea.

## 10. Hojas de modelo con vueltas, no vistas sueltas

Cada personaje tiene su `m_*.png` con las cuatro vistas — frente, tres cuartos,
perfil y espalda — en una sola imagen. Es la práctica estándar de animación:
le da al modelo los ángulos resueltos en vez de que los invente cuando el plano
pide un perfil o una espalda.

Se generan con `modelos.json` a partir de las hojas de una vista.

## 11. Los subtítulos no necesitan Whisper

En el pipeline encadenado había que alinear a la fuerza con Whisper porque no se
sabía en qué segundo caía cada línea. Ahora **nosotros elegimos la duración de
cada plano**, así que el tiempo de cada diálogo es una suma. `--montar` escribe
el SRT solo.

El archivo se escribe con BOM (`utf-8-sig`): sin él, libass lo lee como Latin-1
y destroza los acentos al quemar los subtítulos.

---

## Lo que todavía no está probado

Honestidad sobre el estado de esto: **la película por planos no se generó
todavía**. Lo que está verificado y lo que no:

**Verificado**
- Las hojas de modelo mantienen cara, vestuario y estilo entre las cuatro vistas.
- Un mismo personaje aguanta entre tamaños de plano distintos, incluido el primer
  plano, que es el caso difícil (prueba de cuatro tamaños contra la referencia).
- FL2VA con `first_frame` anda: es lo que movía los clips 2 y 3 del método viejo.
- El reparto en 4 GPUs corriendo en paralelo anda.

**Sin verificar**
- Si la identidad aguanta a lo largo de los 42 planos, no de cuatro.
- Si el corte entre planos generados por separado se siente como cine o como un
  rejunte. El estilo va a variar algo entre planos y todavía no sé cuánto.
- La estimación de costo extrapola por debajo del rango medido: los dos puntos
  que tengo son de 10 y 15 s, y la mitad de estos planos dura menos de 7 s.
- Si `[Speech]` con el bloque de castellano alcanza para que no se escape una
  palabra en inglés. Vale la pena pasarle Whisper a los 8 planos con voz y
  chequear.

Lo que sale de la primera corrida se anota acá y en `COSTOS-H3.md`.
