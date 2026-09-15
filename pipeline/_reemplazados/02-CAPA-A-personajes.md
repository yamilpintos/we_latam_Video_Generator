# Capa A — Biblia de personajes y consistencia visual

Esta capa existe por un solo motivo: que el protagonista del minuto 7 sea el mismo que el del
minuto 1. Es el punto donde más videos de IA se caen.

---

## 1. La regla que no se rompe

> **Nunca encadenes.** Cada imagen de escena se genera anclada a la **ficha original** del
> personaje. Jamás a la imagen anterior.

Encadenar (`P05` basada en `P04` basada en `P03`…) acumula deriva: cada generación introduce un
error pequeño y al plano 20 el personaje es otra persona. Anclar siempre a la ficha mantiene el
error acotado a una sola generación.

---

## 2. Los tres artefactos de consistencia

### 2.1 STYLE TOKEN

Un párrafo **idéntico, palabra por palabra**, que se pega al final de *todos* los prompts de imagen.
Define el look del video entero. Se escribe una vez y no se toca.

Plantilla:

```
ESTILO: <medio: ilustración digital cinematográfica / pintura mate / render fotorrealista>,
paleta <3-4 colores dominantes con nombre concreto>, iluminación <tipo y dirección>,
<lente equivalente: 35mm / 50mm / 85mm>, <profundidad de campo>, grano fílmico sutil,
contraste <alto/medio>, sin texto, sin marcas de agua, sin bordes,
composición centrada con aire arriba y abajo, formato horizontal.
```

Ejemplo real:

```
ESTILO: ilustración digital cinematográfica pintada a mano, paleta de azul petróleo,
ocre apagado y blanco hueso, iluminación lateral dura de fuente única, lente 35mm,
profundidad de campo media, grano fílmico sutil, contraste alto, sin texto,
sin marcas de agua, sin bordes, composición centrada con aire arriba y abajo,
formato horizontal.
```

### 2.2 Hoja de personaje (character sheet)

**Una sola imagen por personaje** que contiene varias vistas. Es el ancla de todo.

Prompt de ficha:

```
Hoja de referencia de personaje sobre fondo gris neutro liso, iluminación plana y uniforme.
Cuatro vistas del MISMO personaje alineadas horizontalmente:
(1) retrato de frente, (2) retrato de perfil, (3) retrato tres cuartos, (4) cuerpo entero de frente.

PERSONAJE — <NOMBRE>: <edad> años, <etnia/tono de piel>, <contextura y altura>,
pelo <color, largo, forma, cómo lo lleva>, ojos <color y forma>,
rasgos distintivos: <cicatriz / lunar / lentes / barba — máximo 2, muy específicos>,
expresión de base: <neutra reservada / alerta / cansada>.
VESTUARIO FIJO: <prenda superior con color y material>, <prenda inferior>, <calzado>,
<accesorio identificador que aparece en TODOS los planos>.

Sin texto, sin etiquetas, sin numeración en la imagen.
<STYLE TOKEN>
```

Reglas al escribir la ficha:
- **Máximo 2 rasgos distintivos**, pero hiperespecíficos. "Cicatriz vertical de 3 cm sobre la ceja
  izquierda" funciona; "cara interesante" no.
- **El vestuario es fijo para todo el video.** Un solo accesorio identificador (bufanda roja,
  reloj de bronce, campera de cuero gastada) resuelve más consistencia que diez adjetivos de cara.
- Si el personaje cambia de ropa en la historia, es **otra ficha**: `MARA-A` y `MARA-B`.

### 2.3 Placa de locación

Una imagen por locación recurrente, sin personajes, para fijar arquitectura, paleta y luz.
Se sube junto con las fichas.

```
Placa de referencia de locación, sin personas.
LOCACIÓN — <NOMBRE>: <descripción de 2-3 frases: arquitectura, materiales, época, estado de
conservación>. Momento del día: <hora concreta>. Clima: <...>. Fuente de luz principal: <...>.
<STYLE TOKEN>
```

---

## 3. Flujo operativo en ChatGPT

**Chat A — "FICHAS"** (uno por personaje, o uno para todos):
1. Generás la hoja de cada personaje y cada placa de locación.
2. Iterás hasta que te guste. Acá está permitido iterar todo lo que quieras.
3. **Descargás las imágenes finales.** Este chat después se abandona.

→ **Gate 2: aprobás las fichas antes de seguir.**

**Chat B — "PRODUCCIÓN"** (uno solo, para todas las escenas):
1. Primer mensaje: subís **todas** las fichas y placas + pegás el STYLE TOKEN + esta instrucción:

   > Estas son las hojas de referencia de los personajes y locaciones de un video. En los
   > próximos mensajes te voy a pedir escenas. En cada una, reproducí exactamente el personaje
   > indicado tal como aparece en su hoja de referencia: mismo rostro, mismo peinado, mismo
   > vestuario, mismo accesorio. Mantené el estilo visual que te doy, idéntico en todas.
   > Respondé solo con la imagen.

2. Después, un mensaje por plano con el prompt de la Capa B.
3. **Cada ~10 imágenes, volvés a subir las fichas** en el mensaje. El contexto se degrada y el
   personaje empieza a derivar; re-subir lo resetea.
4. Si un plano sale mal: **no pidas "corregilo"**. Volvé a mandar el prompt completo desde cero
   con la ficha adjunta. Corregir sobre una imagen derivada arrastra la deriva.

**Si un personaje deriva igual:** abrí un chat nuevo, subí solo la ficha de ese personaje y
generá ahí los planos donde aparece solo.

---

## 4. Nota sobre el filtro de contenido

El generador de ChatGPT rechaza violencia explícita, sangre, y a veces personajes menores en
situaciones de riesgo. Para historias oscuras, el pipeline escribe los prompts en **clave
cinematográfica indirecta**:

| En vez de | Escribí |
|---|---|
| "sangre en el piso" | "un charco oscuro reflejando la luz" |
| "le dispara" | "el fogonazo ilumina el pasillo, ella retrocede" |
| "cadáver" | "una figura inmóvil cubierta por una tela" |
| "cara golpeada" | "expresión demacrada, sombras marcadas bajo los ojos" |

Casi siempre queda **mejor** que la versión literal. El corte al negro y el SFX hacen el trabajo.

---

## Formato de salida — `03-biblia.md`

```markdown
## STYLE TOKEN
<el párrafo exacto, en bloque de código para copiar>

## PERSONAJES
### MARA — protagonista
**Prompt de ficha:** <bloque de código listo para pegar>
**Archivo:** `REF_MARA.png`
**Aparece en:** S01-P03, S01-P05, S02-P01 … (lista completa de IDs)
**Accesorio identificador:** bufanda de lana roja deshilachada

## LOCACIONES
### FARO
**Prompt de placa:** <bloque de código>
**Archivo:** `REF_LOC_FARO.png`
**Secuencias:** S01, S04, S09
```
