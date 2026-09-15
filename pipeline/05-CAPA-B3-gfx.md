# Capa B3 — Planos gráficos

Los **5 segundos** que no salen de una imagen generada: diagramas, comparaciones, datos, mapas.
Se hacen a mano en el editor. Cuestan cero créditos y son los que hacen que una explicación se
entienda a la primera.

Opcional según el género: en ficción casi no aparecen; en documental técnico pueden ser el 20 %
de los planos.

---

# 1. Cuándo un plano va acá

Cuando lo que hay que comunicar es una **relación**, no una imagen:

- Una comparación numérica o de escala.
- Una trayectoria, un recorrido, una evolución en el tiempo.
- Un mecanismo: cómo una cosa causa otra.
- Una descomposición: algo que se separa en partes.
- Una enumeración con peso —las nueve causas, los cinco pasos.
- Un mapa o una ubicación.

**La prueba:** si al escribir el prompt de imagen te encontrás intentando que el generador dibuje
un esquema, es un GFX. Los generadores de imagen no dibujan diagramas: dibujan cosas que *parecen*
diagramas, con etiquetas ilegibles y flechas que no apuntan a nada.

---

# 2. Sistema de diseño

Uno solo para todos los gráficos del video, para que se lean como un mismo lenguaje y no como
plantillas sueltas.

| | Valor por defecto | Se ajusta a |
|---|---|---|
| Fondo | Negro puro | La paleta del STYLE TOKEN |
| Grano | El mismo del video, al 8 % | — |
| Trazo | Líneas finas, 2 px | — |
| Color principal | El acento frío de la paleta | Ej. verde fósforo `#4AE07A` |
| Color de énfasis | El acento cálido | Ej. ámbar `#E0A24A` |
| Color de error | Rojo apagado `#C7503C` | Solo cuando algo falla |
| Tipografía | Monoespaciada, en versalitas | — |
| Entrada | Barrido de izquierda a derecha, 0,4 s, ease-out | — |
| Salida | Fundido a negro de 0,3 s en el último medio segundo | — |

**El objetivo es que parezcan salidos de un instrumento de la época**, no de una plantilla de
After Effects. Nada de degradados, sombras paralelas ni iconos de stock.

---

# 3. Reglas

**Un solo dato por plano.** Cinco segundos alcanzan para una idea. Si el gráfico necesita dos,
son dos planos.

**Que respire.** La tentación es llenar el encuadre. Un número grande sobre negro con una línea
de texto chica debajo comunica más que un panel de información.

**El texto acá sí está permitido** —es la única capa donde lo está—, pero mínimo: una unidad, una
cifra, un rótulo de tres palabras. Todo lo demás lo dice la voz.

**Sincronía con la narración.** Un gráfico que aparece medio segundo después de que la voz nombró
el dato llega tarde. Cuando un GFX ilustra una palabra concreta, esa palabra manda: el plano se
coloca para que la palabra caiga adentro, no al lado.

**Ritmo interno.** Cinco segundos de un gráfico estático son eternos. Que algo aparezca, crezca o
se transforme entre el segundo 1 y el 4.

---

# 4. Plantilla por plano

````markdown
### <ID> · <IN> → <OUT> · 5 s · GFX
**Qué comunica:** <una línea. La relación, no el dibujo>
**Palabra que tiene que caer adentro:** «<...>» (aparece en <toma de voz> a las <timecode>)

**Descripción:**
<Qué aparece, en qué orden y con qué tiempos. Segundo a segundo si hace falta.>

**Colores:** <cuál es el principal, cuál el énfasis y por qué>
````

---

# 5. Ejemplo

````markdown
### S06-P05 · 03:11 → 03:16 · 5 s · GFX
**Qué comunica:** las dos unidades no son la misma, y el factor entre ellas
**Palabra que tiene que caer adentro:** «newton-segundo» (toma S06-T5, a las 03:12)

**Descripción:**
`lbf·s` se desvanece y en su lugar aparece `N·s`, con `newton-segundo` debajo en trazo fino.
Al segundo 2,5 entra entre ambos, en ámbar, una flecha con el rótulo `× 4,45`.
Nada más. Fondo negro.

**Colores:** las unidades en verde fósforo; la flecha y el factor en ámbar, porque es lo que
está mal.
````

Ese plano es el momento clave de su video: si se mueve, la voz dice "newton-segundo" sobre otra
imagen y el chiste visual se pierde.

---

# 6. Control de calidad

- [ ] Un solo dato por plano
- [ ] Algo se mueve o aparece entre el segundo 1 y el 4
- [ ] El texto es mínimo: una unidad, una cifra, un rótulo corto
- [ ] La paleta es la del video, no la de la plantilla
- [ ] El grano está aplicado, como en el resto de los planos
- [ ] Si ilustra una palabra concreta, la palabra cae adentro del plano
