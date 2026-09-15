# Capa B — Generación de imágenes

Un prompt por plano, listo para pegar en el chat de PRODUCCIÓN. Todos los planos pasan por acá,
incluso los que después van a Veo 3: **la imagen es siempre el punto de partida.**

---

## 1. Anatomía del prompt de escena

Seis bloques, siempre en este orden. El orden importa: los generadores pesan más lo que va primero.

```
1. TIPO DE PLANO + ÁNGULO
2. SUJETO(S) — anclados a la ficha
3. ACCIÓN / POSE — un solo verbo, estado congelado
4. ENTORNO — locación + profundidad
5. LUZ + ATMÓSFERA
6. STYLE TOKEN
```

Ejemplo completo:

```
Plano medio, ligeramente contrapicado.
MARA (personaje de la hoja de referencia adjunta: mismo rostro, mismo pelo,
misma bufanda de lana roja deshilachada) de pie frente a la puerta de hierro del faro,
la mano derecha apoyada en la manija, la cabeza girada mirando por encima del hombro
hacia el mar. Expresión de alerta contenida.
Detrás de ella, la escalera de caracol se hunde en la oscuridad; en primer plano
desenfocado, el borde oxidado del marco.
Luz: única fuente cálida desde abajo a la izquierda, resto en penumbra azulada,
niebla marina densa.
ESTILO: <STYLE TOKEN>
```

---

## 2. Reglas de escritura

**Congelá un instante, no una secuencia.** El generador de imágenes no entiende "camina hacia la
puerta y la abre". Elegí el frame exacto: "la mano apoyada en la manija, el peso en el pie
adelantado".

**Un verbo por prompt.** Dos acciones producen dos poses fusionadas.

**Describí la profundidad en tres capas.** Primer plano / sujeto / fondo. Es lo que separa una
imagen plana de una cinematográfica — y es indispensable si el plano va a parallax 2.5D
(ver Capa C).

**Nombrá el tipo de plano con vocabulario de cine**, no con adjetivos:

| Término | Cuándo |
|---|---|
| Plano general / establishing | Abrir secuencia, mostrar escala |
| Plano entero | Cuerpo completo, acción física |
| Plano medio | Diálogo, reacción, la mayoría de los planos |
| Primer plano | Emoción, decisión, revelación |
| Plano detalle / inserto | Objeto clave, mano, ojo |
| Contrapicado | El sujeto domina, amenaza |
| Picado | El sujeto es vulnerable, pequeño |
| Cenital | Distancia emocional, diseño gráfico |
| Plano subjetivo (POV) | Inmersión, tensión |

**Máximo 2 personajes por imagen.** Tres o más y la consistencia se desmorona. Si la escena tiene
un grupo, resolvela con planos alternados o con siluetas de fondo sin identidad.

**Prohibido en el prompt:** texto en la imagen, carteles legibles, relojes con hora visible,
manos en primer plano haciendo gestos finos, multitudes con caras definidas. Todo eso sale mal.

---

## 3. Diferencia entre un plano `STILL` y uno `VEO`

Mismo formato de prompt, dos ajustes:

| | `STILL` | `VEO` |
|---|---|---|
| Composición | Puede llenar el encuadre | **Dejá aire en la dirección del movimiento** |
| Capas de profundidad | Obligatorias y bien separadas (para parallax) | Recomendadas |
| Pose | El frame definitivo | El **primer frame** de la acción: pie que empieza a levantarse, objeto que aún no cayó |
| Detalle de fondo | Cuanto más, mejor | Moderado — Veo distorsiona fondos muy cargados |

Para `VEO`, el prompt de imagen termina siempre con:

```
Momento inmediatamente anterior a la acción. Dejar espacio libre a la <izquierda/derecha/arriba>
para el movimiento.
```

---

## 4. Control de calidad — rechazá y regenerá si:

- El personaje no coincide con la ficha (cara, pelo, accesorio).
- Aparece texto o watermark.
- Hay manos con dedos de más — reencuadrá para sacarlas del plano.
- La paleta se fue del STYLE TOKEN.
- Para un `VEO`: el sujeto está pegado al borde en la dirección del movimiento.

Presupuestá **1.4 generaciones por plano** en el cálculo de tiempo y créditos.

---

## Formato de salida — `04-imagenes.md`

Una entrada por plano, en orden de timeline:

````markdown
### S01-P03 · 00:13 → 00:18 · 5 s · STILL
**Personajes:** MARA · **Locación:** FARO_EXT · **Referencias a adjuntar:** `REF_MARA.png`, `REF_LOC_FARO.png`

```
Plano medio, ligeramente contrapicado. MARA (personaje de la hoja de referencia adjunta:
mismo rostro, mismo pelo, misma bufanda de lana roja deshilachada) de pie frente a la
puerta de hierro del faro, la mano derecha apoyada en la manija, la cabeza girada mirando
por encima del hombro hacia el mar. Expresión de alerta contenida.
Detrás de ella, la escalera de caracol se hunde en la oscuridad; en primer plano
desenfocado, el borde oxidado del marco.
Luz: única fuente cálida desde abajo a la izquierda, resto en penumbra azulada, niebla
marina densa.
ESTILO: ilustración digital cinematográfica pintada a mano, paleta de azul petróleo, ocre
apagado y blanco hueso, iluminación lateral dura de fuente única, lente 35mm, profundidad
de campo media, grano fílmico sutil, contraste alto, sin texto, sin marcas de agua, sin
bordes, composición centrada con aire arriba y abajo, formato horizontal.
```

**Guardar como:** `IMG_S01-P03.png`
**Capas para parallax:** fondo = mar y niebla · medio = MARA y puerta · frente = marco oxidado
````
