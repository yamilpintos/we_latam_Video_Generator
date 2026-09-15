# Capa B1 — Planos de Veo 3 · imagen semilla + prompt de video

Los planos de **10 segundos**. Cada uno son dos generaciones: una imagen semilla en ChatGPT y un
clip en Veo 3 a partir de ella.

Este documento es autosuficiente: arriba están los dos prompts maestros, abajo la plantilla por
plano.

---

# PROMPT MAESTRO 1 · ChatGPT — imágenes semilla

Se pega **una sola vez** en el primer mensaje del chat, junto con la imagen madre de la cámara
y las placas de sujeto que apliquen.

```
Vas a generar imágenes semilla para clips de video de 10 segundos. Cada imagen es el PRIMER
FOTOGRAMA de un movimiento que va a ocurrir después, no una foto terminada.

Eso cambia tres cosas respecto de una imagen normal:

1. AIRE EN LA DIRECCIÓN DEL MOVIMIENTO. Si el sujeto va a avanzar hacia la derecha, tiene que
   haber espacio libre a su derecha. Si la cámara va a subir, espacio arriba. Un sujeto pegado
   al borde por el lado hacia donde se mueve produce un clip que se sale de cuadro en el
   segundo 2.

2. EL INSTANTE ANTERIOR A LA ACCIÓN, no la acción. La mano apoyada en la manija, no la puerta
   abriéndose. El pie adelantado con el peso ya desplazado, no el paso dado. El modelo de video
   necesita un punto de partida, no un punto medio.

3. FONDO MODERADO. Veo distorsiona los fondos muy cargados de detalle fino. Un fondo con
   estructura clara y sin barroquismo aguanta mucho mejor los 10 segundos.

Cuando mencione LA CÁMARA, reproducí exactamente el espacio de la imagen de referencia adjunta:
misma arquitectura, misma paleta, misma dirección y temperatura de luz, mismos materiales.
No inventes un lugar distinto.

Respondé solo con la imagen.

<STYLE TOKEN>
```

---

# PROMPT MAESTRO 2 · Veo 3 — bloque de cierre obligatorio

Va al final de **todos** los prompts de video, sin excepción.

```
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

**No es opcional.** Veo 3 genera audio nativo: si no le pedís silencio te mete voces inventadas
en inglés que chocan con la narración. Y en el editor, **silenciá la pista de audio de todos los
clips de Veo** salvo que decidas conservar un ambiente puntual.

---

# 1. Cuándo un plano va a Veo

Se cumple al menos una:

- Hay **locomoción** del sujeto: camina, cae, se da vuelta, despega.
- Hay un **cambio de estado visible**: una puerta se abre, el fuego prende, algo se rompe.
- Hay **interacción** entre dos sujetos.
- Es el **gancho** o el **clímax** de un acto.

Si no se cumple ninguna, el plano va a la Capa B2 y cuesta cero créditos.

**Presupuesto:** 10 clips en `TEST-5`, 15 en `FULL-8`. Es el parámetro de costo del pipeline.

---

# 2. Diseñar una acción de 10 segundos exactos

Se usan los 10 s completos. No se recorta: si el primer o el último fotograma salen mal, se
regenera. Previsión de reintentos: **1,3×**.

**Diez segundos es mucho para un solo movimiento.** Es el error más caro de esta capa: un dolly
que se agota en 4 s deja 6 s de relleno visible. La acción tiene que tener desarrollo interno.

| Momento | Qué tiene que pasar |
|---|---|
| **Fotograma 1** | El movimiento **ya está en curso**. Nada de medio segundo quieto antes de arrancar |
| **Segundos 1–4** | Desarrollo del arco principal, velocidad constante |
| **Segundos 5–6** | **Un acento**: la resistencia al empujar, el destello, el momento en que algo cede |
| **Segundos 7–9** | Resolución del arco |
| **Fotograma final** | Una **pose sostenida**, no un gesto a medio hacer. Si termina en el aire, el corte se siente arrancado |

Si la acción no da para diez segundos, hay dos salidas honestas: pasarla a la Capa B2, o partirla
en dos clips —el segundo arranca desde el último fotograma exportado del primero, que es la única
forma de continuidad exacta. En el timeline quedan como `S04-P02a` y `S04-P02b`.

---

# 3. Anatomía del prompt de Veo

Cinco bloques, siempre en este orden:

```
1. QUÉ HACE EL SUJETO      un movimiento, con inicio y final claros
2. QUÉ HACE LA CÁMARA      uno solo. Dos producen deriva y artefactos
3. QUÉ SE MUEVE ALREDEDOR  elementos secundarios que dan vida
4. RITMO                   dónde está el acento de los 10 segundos
5. NEGATIVOS               el bloque de cierre, textual
```

### Movimientos de cámara — uno por clip

| Movimiento | Efecto | A 10 s |
|---|---|---|
| Dolly in lento | Tensión creciente | El más seguro, pero necesita un acento a mitad |
| Dolly out | Revelación, soledad | Muy bueno para cerrar secuencia |
| Pan lateral | Recorrer un espacio | Necesita fondo con contenido o se ve vacío |
| Tilt up | Escala, imponencia | Se queda corto solo: combinalo con algo que entre en cuadro |
| Handheld sutil | Realismo, inquietud | Se puede sumar a cualquiera de los otros |
| Cámara fija | Deja que la acción hable | **Solo si la acción llena los 10 s** |
| Orbit / arco | Presentación de un sujeto | El que mejor justifica los 10 s completos |

---

# 4. Plantilla por plano

````markdown
### <ID> · <IN> → <OUT> · 10 s · CÁMARA <X>
**Semilla:** `IMG_<ID>.png` · **Clip:** `VID_<ID>.mp4`
**Adjuntar al generar la imagen:** madre de la cámara `<X>` + placas de sujeto

**Prompt de imagen (ChatGPT):**
```
<Tipo de plano y ángulo>. <Sujeto, anclado a su placa si corresponde>, <acción congelada en el
instante ANTERIOR: un solo verbo, un solo estado>.
<Entorno en tres capas: primer plano, sujeto, fondo>.
Luz: <fuentes visibles y dirección>.
Dejar espacio libre a <la derecha / arriba / la izquierda> para el movimiento.
```

**Prompt de video (Veo 3):**
```
<Qué hace el sujeto: un movimiento con inicio y final claros>.
Cámara: <un solo movimiento, continuo, sin cortes>.
Entorno: <qué se mueve alrededor>.
Ritmo: el movimiento ya está en curso desde el primer fotograma. <Descripción del arco, con el
acento alrededor del segundo 5 o 6>. Termina en una posición estable y sostenida, sin gestos a
medio hacer.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

**En el editor:** silenciar la pista de audio del clip.
````

---

# 5. Control de calidad

Rechazá y **regenerá la imagen** si:

- El sujeto no coincide con su placa.
- Aparece texto, un número legible o un logotipo.
- El espacio no coincide con la madre de su cámara — otra arquitectura, otra luz.
- **El sujeto está pegado al borde por el lado hacia donde tiene que moverse.**

Rechazá y **regenerá el clip** si:

- El primer fotograma tiene medio segundo de quietud.
- El movimiento se agota antes del segundo 7 y el resto es relleno.
- El último fotograma queda a medio gesto.
- La cara del sujeto o la paleta derivaron respecto de la semilla.

No se arregla en edición: los 10 segundos son el plano entero.
