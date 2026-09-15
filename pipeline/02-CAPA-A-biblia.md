# Capa A — Biblia visual y árbol de cámaras

Todo lo que hay que fijar **antes** de pedir una sola imagen de escena. Si esta capa está mal,
las 40 imágenes siguientes están mal.

---

## 1. STYLE TOKEN

Un párrafo **idéntico, palabra por palabra**, que define el look del video entero. Se pega una
sola vez en el primer mensaje de cada chat de producción y después no hace falta repetirlo.

```
ESTILO PARA TODAS LAS IMÁGENES: <medio: fotografía cinematográfica documental / ilustración
digital pintada a mano / render fotorrealista>, <época o referencia>. <Textura: emulsión de
película 35 mm con grano visible / trazo de pincel / limpio digital>. Paleta de <tres o cuatro
colores con nombre concreto>. Iluminación <exclusivamente de fuentes visibles en el plano /
tres puntos / natural>. Lente <35 mm>, profundidad de campo <media>, <aberración cromática leve
en los bordes>. Contraste <medio-alto con negros levantados>.

PROHIBIDO EN TODAS: texto, letreros legibles, números en pantalla, logotipos, marcas de agua,
bordes o marcos. Nada de caras en primer plano identificables.

COMPOSICIÓN: horizontal, sujeto centrado, con aire arriba y abajo porque la imagen se recorta a
16:9 y se pierden las franjas superior e inferior.
```

Ejemplo real (Mars Climate Orbiter):

```
ESTILO PARA TODAS LAS IMÁGENES: fotografía cinematográfica documental, recreación de 1999.
Emulsión de película 35 mm con grano visible y halación suave en las luces. Paleta de ámbar
apagado, verde fósforo de monitor CRT y azul acero. Iluminación exclusivamente de fuentes
visibles en el plano, nada de luz de relleno inventada. Lente 35 mm, profundidad de campo media,
leve aberración cromática en los bordes. Contraste medio-alto con negros levantados, como un
positivo de la época.
PROHIBIDO EN TODAS: texto, letreros legibles, números en pantalla, logotipos, marcas de agua,
bordes o marcos. Nada de caras en primer plano identificables.
COMPOSICIÓN: horizontal, sujeto centrado, con aire arriba y abajo porque la imagen se recorta a
16:9 y se pierden las franjas superior e inferior.
```

---

## 2. El árbol de cámaras

> **Verificado.** ChatGPT respeta una imagen de referencia y mantiene la espacialidad al generar
> un plano más cerrado del mismo lugar. Esta es la base de toda la continuidad del pipeline.

### El problema que resuelve

Generar cada plano por separado da consistencia **de estilo** —todos siguen el STYLE TOKEN— pero
no consistencia **espacial**: la sala puede tener la puerta a la izquierda en un plano y a la
derecha en otro, aunque la paleta sea idéntica.

Recortar un plano general para sacar los cerrados sí da continuidad perfecta, pero se topa con la
resolución: **más de ×1,9 de ampliación y la imagen es papilla**. Medido.

El árbol resuelve los dos: el plano cerrado se **genera de nuevo**, a resolución completa, usando
el abierto como referencia visual.

### Qué es una cámara

Una cámara es **un lugar físico del espacio**, no un plano. Varios planos pueden filmarse desde
la misma cámara si comparten punto de vista y solo cambian de escala o encuadre.

```
LOCACIÓN: sala de control
├── CÁMARA A · pasillo central, altura del pecho, mirando al fondo
│   ├── A1  plano general de la sala          ← MADRE, se genera primero
│   ├── A2  plano medio de una fila de mesas
│   └── A3  detalle del monitor de la tercera mesa
└── CÁMARA B · a la altura del escritorio, detrás de un operador
    ├── B1  plano medio desde atrás           ← MADRE de esta rama
    └── B2  detalle de las manos sobre el teclado
```

### Regla de economía de cámara

**Antes de crear una cámara nueva, preguntá si el plano puede filmarse desde una existente.**
Una cámara nueva solo se justifica si cambian de verdad el punto de vista, el ángulo o el eje.
Cambiar solo la escala **no** justifica una cámara nueva: es un hijo.

Menos cámaras significa menos generaciones madre, más continuidad y un espacio que el espectador
puede reconstruir mentalmente.

Referencia sana: **1 o 2 cámaras por locación**. Si te salen cinco, casi seguro estás confundiendo
"plano distinto" con "lugar distinto".

### Orden de generación

1. **Las madres primero.** El plano más abierto de cada cámara. Se itera hasta que convenza.
2. **Los hijos después**, en un chat nuevo, adjuntando la madre de su cámara.
3. Si un hijo sale mal, se regenera **desde la madre**, nunca desde otro hijo. Encadenar
   acumula deriva.

### Prompt para una imagen madre

```
<STYLE TOKEN>

CÁMARA <A> · <descripción del punto de vista: dónde está la cámara, a qué altura, hacia dónde
mira>.

<Tipo de plano> de <LOCACIÓN>. <Descripción del espacio en tres capas: qué hay en primer plano,
qué en el medio, qué al fondo. Arquitectura, materiales, mobiliario, estado de conservación.>

<UN ELEMENTO DISTINTIVO Y LOCALIZADO — una taza roja en la tercera mesa, una grieta en la pared
del fondo, una lámpara caída. Sirve de ancla verificable para los hijos.>

Momento: <hora concreta>. Luz: <fuentes visibles y su dirección>.
```

**El elemento distintivo no es decorativo.** Es lo que te permite comprobar que un hijo salió del
mismo espacio: si la taza roja no está, la continuidad falló aunque el estilo coincida.

### Prompt para una imagen hija

Chat **nuevo**, con la madre adjunta. Que sea nuevo es a propósito: en el mismo chat el modelo
puede estar recordando el texto en vez de mirar la imagen.

```
La imagen adjunta es un fotograma de referencia de <LOCACIÓN>.

Generá <tipo de plano> del MISMO espacio, filmado desde el mismo lugar pero <con lente largo /
un paso más cerca / girando levemente>: <descripción del encuadre nuevo, nombrando el elemento
distintivo de la madre>.

CONTINUIDAD OBLIGATORIA con la imagen de referencia:
- misma paleta y mismo grano
- misma dirección y temperatura de la luz
- mismos materiales, mobiliario y nivel de desorden
- misma hora del día y mismo ambiente

No inventes un lugar distinto. Es el mismo, <más cerca / desde un poco más allá>.

PROHIBIDO: texto, números legibles, logotipos, marcas de agua, bordes.
COMPOSICIÓN: horizontal, con aire arriba y abajo.
```

---

## 3. Placas de sujeto

Además de las cámaras, hay que fijar los **sujetos que se repiten**: un vehículo, una nave, un
personaje. Se generan sobre fondo neutro y se adjuntan junto con la madre cuando el sujeto
aparece en el plano.

```
Hoja de referencia de <SUJETO> sobre fondo gris neutro liso, iluminación plana y uniforme.
Tres vistas del MISMO sujeto alineadas horizontalmente: frontal, lateral, tres cuartos.

<SUJETO> — <NOMBRE>: <descripción física detallada. Materiales, proporciones, color.
Máximo 2 rasgos distintivos, pero hiperespecíficos.>

Sin texto, sin etiquetas, sin numeración en la imagen.
<STYLE TOKEN>
```

**Para personas:** máximo 2 rasgos distintivos y **un accesorio identificador fijo** —una bufanda
roja, un reloj de bronce—. Un accesorio resuelve más consistencia que diez adjetivos de cara.
Si el personaje cambia de ropa, es otra placa: `MARA-A` y `MARA-B`.

**Para documental sin personajes:** las personas van de espaldas, en silueta o con la cara fuera
de foco. Elimina de raíz el problema de deriva facial y además es más honesto cuando se
representa a gente real.

---

## 4. Flujo completo en ChatGPT

| Paso | Chat | Qué se hace |
|---|---|---|
| 1 | **REFERENCIAS** | Generar las placas de sujeto. Iterar libremente. Descargar. |
| 2 | **REFERENCIAS** | Generar las **madres** de cada cámara. Verificar el elemento distintivo. Descargar. |
| — | | **Gate 2: se aprueban las madres antes de seguir.** |
| 3 | **un chat por cámara** | Adjuntar la madre + las placas de sujeto que apliquen. Pedir los hijos, uno por mensaje. |

Un chat por cámara, no uno para todo: mantiene el contexto limpio y evita que el modelo mezcle
espacios.

**Cada 10 imágenes, volvé a adjuntar la madre.** El contexto se degrada.

---

## 5. Nota sobre el filtro de contenido

ChatGPT rechaza violencia explícita, sangre y menores en riesgo. Para historias oscuras conviene
la clave cinematográfica indirecta, que además suele quedar mejor:

| En vez de | Escribí |
|---|---|
| "sangre en el piso" | "un charco oscuro reflejando la luz" |
| "le dispara" | "el fogonazo ilumina el pasillo, ella retrocede" |
| "cadáver" | "una figura inmóvil cubierta por una tela" |

---

## 6. Presupuesto

| Concepto | Cantidad para `TEST-5` |
|---|---|
| Placas de sujeto | 2–4 |
| Cámaras madre | 1–2 por locación · típicamente **5–8** |
| Imágenes hijas | el resto de los planos con imagen |
| **Total limpio** | ~45 |
| Con reintentos (× 1,4) | **~63 generaciones** |

El árbol **baja** el total frente a generar cada plano por separado, porque varios planos comparten
madre y los hijos salen a la primera con más frecuencia.
