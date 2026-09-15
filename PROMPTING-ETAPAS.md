# Prompting por etapas — cómo llegamos a esos resultados

Sistema usado en producción (agosto 2026) para shorts de 60 s y videos largos
tipo recap de 3-8 min, generando con MiniMax H3 y voz de ElevenLabs. La idea
central: **el resultado no sale de un buen prompt — sale de seis etapas donde
cada una fija lo suyo y la siguiente no puede romperlo.** El prompt final se
ensambla solo a partir de piezas validadas.

```
LEY (estructura) → GUION DE VOZ → PLANOS → PROMPT DE IMAGEN → PROMPT DE VIDEO → VOZ MEDIDA
```

---

## Etapa 0 · La ley: estructura por tramos

Antes de escribir una palabra, un JSON dicta **qué tiene que pasar en cada
segundo** del video: tramos con inicio/fin, qué exige cada uno, rango de
duración de corte, tamaños de plano sugeridos y dónde van las interrupciones
de patrón. El guionista (humano o LLM) escribe CONTRA esa ley, y un validador
avisa cada plano que no cumple.

Ejemplo de tramo (gancho del formato recap):

```json
{
  "id": "HOOK", "desde": 0, "hasta": 4.6,
  "objetivo": "Una sola frase in-media-res que ya contiene el resultado y la
               contradicción. El espectador entiende la premisa antes del s 5.",
  "exige": [
    "La primera frase dice QUÉ hizo alguien y por qué es absurdo o extremo",
    "La imagen muestra ese absurdo literal, legible en 0,3 s",
    "Texto en pantalla con el resultado concreto en menos de 8 palabras",
    "Un solo plano; la voz arranca antes del segundo 0,5"
  ],
  "corte_min": 4.0, "corte_max": 5.3,
  "prompt_frame": "The single most absurd and readable image of the story:
                   one clear subject doing something extreme, high contrast,
                   instantly understandable as a thumbnail."
}
```

Las dos leyes que usamos:

| | short (60 s) | recap / largo (3-8 min) |
|---|---|---|
| tramos | 8: HOOK, PROMESA, PROGRESO, REVELACIÓN, GIRO, CONTACTO, PAGO, BUCLE | 10: HOOK, ARRANQUE, 5 BLOQUES serial (problema→acción→consecuencia→cliffhanger), GIRO, PAGO, BUCLE |
| tensión | un giro fuerte al medio | micro-cliffhanger cada 25-35 s |
| interrupción de patrón | cada 12 s máx (luz/sonido/ritmo, un corte NO cuenta) | cada 30 s máx |

## Etapa 1 · El guion de voz PRIMERO

La regla más cara de aprender: **la voz en off es la columna vertebral; los
planos la sirven, no al revés.** Se escribe la historia completa como
narración lineal que un chico de doce entiende, y recién después se diseña un
plano por línea.

- **Primera persona con nombre propio** y números concretos en todo (grados,
  plata, días, personas). Nada que el espectador tenga que inferir.
- **La misma voz actúa los diálogos** con comillas «» — el cambio de tono lo
  hace la puntuación, no las etiquetas.
- **Densidad calculada con el ritmo MEDIDO de la voz elegida**, no el teórico:
  se sintetiza una línea de prueba, se mide (ej.: nuestra narradora corre a
  ~16,7 caracteres/segundo fluida, ~11-14 con pausas) y se escribe cada línea
  para su ventana con ese número.
- En el recap la voz **no para nunca** (referencia del género: ~25 cps con voz
  acelerada); en el short respira entre líneas.

Ejemplo de arranque (recap): *"Mi padre vendió el taller y gastó todo en
carbón. Toda la cuadra se le rió."* → *"Tres días después, se cortó la luz en
toda la provincia."*

## Etapa 2 · Los planos al servicio del guion

Un plano por línea de guion, declarado como datos (no como prosa). Campos:

```json
{
  "id": "S01",
  "tipo": "PG",              // PGE PG PA PM PP PD — el tamaño es un dato
  "corta": 4.7,              // lo que dura en la línea de tiempo
  "segundos": 5.2,           // lo que se genera (corta + 0,5 de colchón)
  "loc": "casa", "personajes": ["ramon"],
  "refs": ["l_casa", "m_ramon"],       // locación madre + hoja de modelo
  "funcion": "HOOK. El absurdo literal: un hombre arriba de una montaña de carbón.",
  "texto": "gastó todo en carbón",     // overlay en post — NUNCA al generador
  "ve":    "…lo que hay en el PRIMER FOTOGRAMA…",
  "mueve": "…qué se mueve durante el plano…",
  "audio": "[SFX] … [Ambient] … [Foley] …"
}
```

Reglas duras de esta etapa:

1. **Duraciones: 5,2-6,6 s por clip** en placas de 32 GB (5,9 entra siempre;
   6,6 casi siempre; 7,3 es apuesta y la pagamos). Cortes más cortos que 5,2
   se logran generando de más y usando el tramo `usa`.
2. **La escala se declara en fracciones del cuadro**, nunca con adjetivos:
   *"his full height is about ONE SEVENTH of the image height, clearly smaller
   than the gas column is wide"*. Y va en el dibujo **y** en el prompt.
3. **El vestuario completo se repite en cada prompt** aunque esté en la hoja
   de modelo (la hoja sostiene la cara; el texto sostiene la ropa).
4. **Texto y números en pantalla van en post, siempre** — los generadores los
   destrozan y en un gancho eso es fatal.
5. No cortar entre dos planos del mismo tamaño + locación + reparto.
6. Caras: en el género recap sí (planos medios, PP sólo en los picos); en
   estética documental se tapan (cascos, antiparras, espaldas) y se elige un
   entorno que perdone (nieve, humo, niebla, noche).

## Etapa 3 · El prompt de imagen (primer fotograma)

Cada plano arranca de un dibujo que se genera y **se revisa con la GPU
apagada** — un encuadre malo se ve en un PNG de centavos, no tras 4 minutos
de GPU cobrando. Esqueleto (se ensambla solo):

```
[ESTILO GLOBAL — 2-4 frases, idénticas en TODOS los fotogramas del video:
 medio, época, luz, lente, grano]
[EL PLANO — el campo `ve`: tamaño en mayúsculas (WIDE SHOT / CLOSE UP…),
 sujeto con vestuario completo, escala en fracciones, y qué NO tiene que
 parecer cuando hay riesgo de ambigüedad]
NARRATIVE INTENT OF THIS FRAME: [el prompt_frame del tramo — lo inyecta la ley]
FORMAT: a TALL 9:16 vertical frame, clearly taller than wide. Never square,
never landscape.
This is a single film frame, not a poster: no text, no borders, no panel
divisions, no title, no watermark.
```

Más **imágenes de referencia adjuntas**: la hoja de modelo del personaje
(cuatro vistas en una imagen) y la imagen madre de la locación (sin gente).
Las referencias anclan identidad y paleta; el texto manda en encuadre y ropa.

## Etapa 4 · El prompt de video (H3)

Se ensambla automáticamente desde el plano. Esqueleto real:

```
[ESTILO DE VIDEO — 1-2 frases, idénticas en todos los planos, vertical 9:16]
MOTION: [el campo `mueve`: qué se mueve y en qué orden — sujeto, entorno,
cámara. La cámara puede moverse todo lo que quiera: el corte tapa todo]
AUDIO: [SFX] efectos puntuales. [Ambient] el fondo continuo. [Foley] lo táctil.
NO SPEECH. No voices, no words, no dialogue, no singing, no crowd chatter.
The only sounds are [la lista corta de sonidos permitidos del proyecto].
Keep the framing of the first frame. Grainy, cinematic, photographic.
Not animated, not illustrated, not CGI-looking, not a video game.
```

Ejemplo ensamblado de verdad (S01 de un recap):

```
Photorealistic prestige drama footage in a snowbound Argentine suburb during
an extreme cold wave, vertical 9:16. Natural, restrained movement.
MOTION: Ramón drives the shovel into the coal and throws a load down without
looking at the neighbours. One neighbour laughs and elbows the other, phone
still up. Snow drifts across the frame.
AUDIO: [Foley] a shovel biting into coal, coal rattling down. [Ambient] cold
wind, a distant dog. [SFX] a phone camera shutter sound.
NO SPEECH. No voices, no words, no dialogue, no singing, no crowd chatter.
The only sounds are the wind, the snow, the coal stove and the house.
Keep the framing of the first frame. Grainy, cinematic, photographic.
Not animated, not illustrated, not CGI-looking, not a video game.
```

Por qué cada bloque existe (todos salieron de fracasos):

- **El bloque de idioma/NO SPEECH va en TODOS los prompts**, hablen o no: sin
  él, el modelo mete murmullos y chusmerío en inglés de fondo. No se pide
  silencio: se acota qué puede sonar.
- **"Keep the framing of the first frame"** + "no inventes": el modelo arranca
  clavado al fotograma pero deriva hacia el final (aparecen objetos, caras,
  fuego). El cierre anti-CGI evita el look de videojuego.
- **El humo/polvo se pide con textura sólo en los planos que lo necesitan**
  ("fine, fibrous, wind-torn, never rounded cartoon puffs") — cargar todos los
  prompts con restricciones diluye las que importan.
- **La voz nunca la hace el generador de video** (inventa una voz distinta por
  clip): todo lo que cruza un corte —voz, música, ambiente continuo— va por
  ElevenLabs encima, en el montaje. H3 sólo genera lo que nace y muere dentro
  del plano.

## Etapa 5 · La voz, medida (ElevenLabs v3)

- **Neutro por defecto.** Máximo un tag de entrega por línea (`[whispers]`,
  `[surprised]`…), al principio, y sólo en picos de intensidad alta: un tag en
  intensidad media corre el timbre y el personaje suena a otra persona. La
  puntuación hace la mitad del trabajo.
- **Se sintetiza, se MIDE contra la ventana y se reescribe el texto** si el
  factor sale de 0,93×-1,15×. Nunca se estira el audio (estirar >1,08× se
  escucha); nunca se recorta una línea hasta dejarla críptica: se reescribe
  entera conservando el dato.
- v3 mete ~200 ms de silencio al inicio de cada clip: se recorta de bordes.
- Máster final: mezcla en 3 capas (audio del generador agachado por ducking,
  voz arriba, música abajo) a −14 LUFS / −1 dBTP.

---

## Resumen: qué hace cada etapa por el resultado

| etapa | fija | si se saltea |
|---|---|---|
| 0 · Ley | el ritmo y la retención | videos lindos que nadie termina |
| 1 · Guion primero | que la historia se entienda | imágenes lindas sin historia (nos pasó) |
| 2 · Planos como datos | validación automática, duraciones seguras | encuadres repetidos, clips que no entran en VRAM |
| 3 · Imagen revisable | identidad y encuadre baratos | errores descubiertos con la GPU cobrando |
| 4 · Video ensamblado | consistencia y anti-deriva | audio en inglés, humo de caricatura, CGI |
| 5 · Voz medida | sincronía y timbre estable | voces que cambian de persona entre líneas |

*Preparado por Yamil · agosto 2026 · v1*
