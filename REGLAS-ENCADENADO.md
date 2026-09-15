# Reglas para encadenar clips en MiniMax H3

> **Este ya no es el metodo por defecto.** Ver [REGLAS-PLANOS.md](REGLAS-PLANOS.md).
>
> Encadenar clips para fingir una toma continua larga pelea contra el modelo:
> las junturas se ven, la camara tiene que frenar en cada una y la identidad se
> degrada porque el tercer clip esta a dos generaciones del dibujo. Aladino se
> rehizo como 42 planos independientes que se unen con cortes.
>
> Lo de abajo sigue valiendo si alguna vez hace falta una toma continua de
> verdad — un plano secuencia deliberado, por ejemplo. Para eso es util.


Cómo escribir prompts para que tres clips de 10 s se lean como **una sola toma
continua**, sin saltos ni incongruencias. Todo esto salió de romperlo primero.

## Cómo funciona el encadenado

El clip 1 usa **Ref2VA** (`MiniMaxH3ReferenceToVideo`) con las imágenes de referencia.
Los siguientes usan **FL2VA** (`MiniMaxH3ImageToVideo`) con `first_frame` = el último
fotograma del clip anterior, extraído con ffmpeg y subido por `/upload/image`.

Eso es lo que manda: **el clip siguiente arranca en el fotograma exacto donde terminó
el anterior.** Todas las reglas de abajo son consecuencia de eso.

---

## Las reglas

### 1. Cada clip tiene que terminar en una pose quieta y legible

Es la regla madre. Si el clip termina en pleno movimiento, el siguiente arranca de un
fotograma borroso o ambiguo y el modelo reinventa la escena.

Terminar con algo así:

> He HOLDS there, arm up, the steel glowing on the anvil, breathing hard.
> She grabs the saddle horn with both hands and STOPS, standing still beside the horse.
> He DROPS into a crouch behind the baskets, pressing his back to them, listening.

**Lo que rompió la primera vez:** la princesa corría *hacia* la cámara mientras esta
retrocedía. El clip terminaba con ella encima del lente o ya fuera de cuadro, y el
clip 2 no la encontraba donde la necesitaba.

### 2. No se puede cambiar el valor de plano entre clips

Plano general → primer plano es imposible. El clip 2 arranca en el fotograma del 1, así
que hereda su encuadre. Los tres clips son **la misma toma**: misma distancia, mismo
lente, misma altura de cámara.

Si querés cambiar de plano, eso es un corte — otra cadena, no la misma.

### 3. La cámara tiene que frenar en las junturas

Una cámara en pleno paneo o barrido al final del clip deja un fotograma con motion blur
que el siguiente no puede continuar. Que el movimiento **arranque y termine dentro** de
cada clip, no que lo atraviese.

Cámara fija (`locked-off`) es lo más seguro. Si hay movimiento, que desacelere hasta
parar antes del final.

### 4. El sujeto nunca sale de cuadro

Nada de "runs toward the camera" ni "exits frame left". Si al final del clip el sujeto
no está, el siguiente no tiene de dónde agarrarlo. Que corra **alejándose** de la
cámara, o que frene dentro del encuadre.

### 5. Cada prompt repite estilo, locación y personaje

El modelo no recuerda el prompt anterior. Hay que reafirmarlo entero:

> Hyperrealistic cinematic footage, anamorphic 35mm, **same forge, same locked-off
> framing, same firelight, same blacksmith**. Continue the shot seamlessly from this
> exact frame.

La frase `Continue the shot seamlessly from this exact frame` va literal en todos los
clips a partir del segundo.

### 6. Las referencias van solo en el clip 1

Los siguientes heredan todo del último fotograma, que es **más fuerte** que cualquier
imagen de referencia para mantener continuidad. Mandar referencias en los clips 2 y 3
además de gastar tiempo puede pelearse con el frame heredado.

### 7. En el prompt, las referencias se nombran `<Picture 1>`, `<Picture 2>`

Así es como H3 sabe cuál es cuál. Sale de la plantilla oficial de ComfyUI, cuyo ejemplo
dice *"Use `<Picture 2>` and `<Picture 1>` as reference frames"*.

> The young princess from **\<Picture 1\>** stands in the great palace courtyard from
> **\<Picture 2\>**, beside the lit fountain.

El orden es el de las variables `REF1`, `REF2`, … del script.

Y arrancar pidiendo que respete el estilo, si no devuelve fotorrealismo aunque las
referencias sean dibujos:

> Match the exact art style, palette and character design of \<Picture 1\> and \<Picture 2\>.

---

## Reglas de audio (no son de encadenado pero se olvidan igual)

### 8. El audio va en el mismo prompt

H3 no tiene entrada separada para audio. Los tags van adentro del texto:

```
[Foley] Hammer on hot steel, ringing anvil, sparks crackling.
[Ambient] Fire, room tone.
[SFX] One enormous guttural roar peaking mid-shot, long reverb tail.
```

### 9. Siempre `NO MUSIC, no speech, no text on screen`

Sin eso, H3 inventa música y voces en inglés que después pelean con la mezcla. La música
la pone el editor y las voces van por ElevenLabs.

### 10. Menos elementos de audio, mejor

Tres bloques con seis cosas cada uno en 10 segundos es demasiado. Dos o tres elementos
claros rinden más:

```
[Foley] Wood splintering, fabric tearing. [Ambient] Shouting behind.
```

### 11. Si hay `[Speech]`, va en el idioma final

Si el video se dobla al castellano, el `[Speech]` tiene que estar **en castellano**. Si
H3 habla en inglés y ElevenLabs en castellano, el lip-sync no coincide y la alineación
forzada de la Fase 4 no encuentra **ninguna** palabra en común: cero warp markers.

Y al revés: si un clip tiene `texto_dialogo_limpio` pero el prompt de audio no tiene tag
`[Speech]`, el personaje no mueve la boca y no hay nada contra qué alinear.

---

## Plantilla de tres clips

```
CLIP 1 — establece
  <estilo> <locación> <personaje desde <Picture 1>>
  Acción que arranca y termina en POSE QUIETA A.
  Cámara fija o que desacelera hasta parar.

CLIP 2 — desarrolla
  <mismo estilo, misma locación, mismo personaje>
  Continue the shot seamlessly from this exact frame.
  Sale de POSE QUIETA A, hace la acción, termina en POSE QUIETA B.

CLIP 3 — resuelve
  <mismo estilo, misma locación, mismo personaje>
  Continue the shot seamlessly from this exact frame.
  Sale de POSE QUIETA B. Acá sí puede terminar en movimiento:
  es el último, no hay que entregarle el frame a nadie.
```

## Ejemplos que funcionaron

`scripts/` y `Imagenes de referencia/` guardan los prompts de:

- **El herrero** (hiperrealista, cámara fija): aviva el fuego y levanta el martillo →
  forja a martillazos y apoya el martillo → templa en agua y levanta la hoja.
- **El bazar** (hiperrealista, cámara que sigue y frena): corre y se agazapa detrás de
  unos canastos → salta el puesto de especias y frena contra la pared → sube a la azotea
  y salta el callejón.
- **La princesa** (animación 2D, con referencias, cámara fija): corre alejándose hacia
  el arco → llega al caballo y frena con la mano en la montura → monta y galopa afuera.
