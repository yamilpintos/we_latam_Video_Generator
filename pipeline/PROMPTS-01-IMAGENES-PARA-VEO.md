# PROMPTS 01 — Imágenes para VIDEO (Veo 3)

**Mars Climate Orbiter · 0:00 – 5:00 · 10 planos de 10 segundos**

Cada plano son dos generaciones: la **imagen semilla** en ChatGPT y el **clip** en Veo 3.
Los dos prompts están juntos en cada entrada.

---

# PROMPT MAESTRO · ChatGPT

Primer mensaje del chat, junto con la imagen madre de la cámara y la placa de la nave.

```
Vas a generar imágenes semilla para clips de video de 10 segundos. Cada imagen es el PRIMER
FOTOGRAMA de un movimiento que va a ocurrir después, no una foto terminada. Eso implica:

1. AIRE EN LA DIRECCIÓN DEL MOVIMIENTO. Si el sujeto va a avanzar hacia la derecha, tiene que
   haber espacio libre a su derecha. Un sujeto pegado al borde se sale de cuadro en el segundo 2.
2. EL INSTANTE ANTERIOR A LA ACCIÓN, no la acción. La mano apoyada en la manija, no la puerta
   abriéndose.
3. FONDO MODERADO. Veo distorsiona los fondos muy cargados de detalle fino.

Cuando mencione LA CÁMARA, reproducí exactamente el espacio de la imagen de referencia adjunta:
misma arquitectura, misma paleta, misma dirección y temperatura de luz, mismos materiales.
No inventes un lugar distinto.

Cuando mencione LA NAVE, reproducila exactamente como en su placa: cuerpo de caja con manta
térmica dorada, UN SOLO panel solar grande montado a un costado, antena parabólica blanca arriba.

Respondé solo con la imagen.

ESTILO PARA TODAS LAS IMÁGENES: fotografía cinematográfica documental, recreación de 1999.
Emulsión de película 35 mm con grano visible y halación suave en las luces. Paleta de ámbar
apagado, verde fósforo de monitor CRT y azul acero. Iluminación exclusivamente de fuentes
visibles en el plano, nada de luz de relleno inventada. Lente 35 mm, profundidad de campo media,
leve aberración cromática en los bordes. Contraste medio-alto con negros levantados.
PROHIBIDO: texto, letreros legibles, números en pantalla, logotipos, marcas de agua, bordes.
COMPOSICIÓN: horizontal, con aire arriba y abajo porque se recorta a 16:9.
EN EL ESPACIO: luz solar dura y direccional sin difusión, sombras de borde definido, negro
absoluto sin niebla atmosférica, estrellas escasas y pequeñas.
```

# PROMPT MAESTRO · Veo 3 — cierre obligatorio

Va al final de **todos** los prompts de video, textual:

```
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

Veo genera audio nativo: sin esto te mete voces inventadas en inglés. **Y en el editor, silenciá
la pista de audio de los 10 clips.**

---

# Los 10 planos

| # | ID | IN → OUT | Cámara | Qué pasa |
|---|---|---|---|---|
| 1 | S01-P01 | 00:00 → 00:10 | **A** madre | El gancho: la sala de control |
| 2 | S01-P04 | 00:20 → 00:30 | B | La nave girando contra Marte |
| 3 | S02-P05 | 00:55 → 01:05 | B | La cámara la deja atrás |
| 4 | S03-P03 | 01:15 → 01:25 | B | Pasa cerca de Marte, en arco |
| 5 | S04-P04 | 01:50 → 02:00 | **J** única | El despegue |
| 6 | S05-P02 | 02:15 → 02:25 | C | La rueda de reacción |
| 7 | S05-P04 | 02:30 → 02:40 | C | Los pulsos del propulsor |
| 8 | S06-P02 | 02:55 → 03:05 | B | Las dos naves se separan |
| 9 | S07-P03 | 03:40 → 03:50 | B | El Sol barre el panel |
| 10 | S09-P02 | 04:40 → 04:50 | B | El vacío entre la Tierra y la nave |

---

## 1 · S01-P01 · 00:00 → 00:10 · CÁMARA A **(madre)** · el gancho
**Voz encima:** «Veintitrés de septiembre…» (00:00,4) y «una señal que llega desde Marte se apaga» (00:08,8)
`IMG_S01-P01.png` → `VID_S01-P01.mp4`

> Esta imagen es la **madre de la cámara A**: se genera primero y sirve de referencia para
> `S01-P03` y `S02-P04`. Verificá el elemento distintivo antes de aprobarla.

**Imagen:**
```
Plano general de una sala de control de misión espacial en 1999, cámara a la altura del pecho en
el pasillo central, mirando hacia el fondo.
A ambos lados, dos filas largas de escritorios con monitores CRT voluminosos de carcasa beige,
teclados gruesos, teléfonos de cable y carpetas de anillas. En la TERCERA MESA DE LA FILA
IZQUIERDA hay una taza roja junto al monitor y una pila desordenada de papel continuo plegado.
Al fondo, una pared con tres pantallas de proyección grandes. Techo con paneles acústicos y
fluorescentes empotrados. Cables agrupados con bridas por el suelo. Alfombra industrial gris
azulada, gastada.
Al fondo del pasillo, un ingeniero de espaldas sentado frente a su monitor, inmóvil, los hombros
tensos. Otras figuras de espaldas o cortadas por el encuadre.
Luz: fluorescentes cenitales fríos mezclados con el resplandor verde de las pantallas. Madrugada.
Dejar espacio libre hacia el fondo para que la cámara avance.
```

**Video:**
```
La cámara avanza por el pasillo central entre las dos filas de escritorios, acercándose al
ingeniero del fondo. Él permanece completamente inmóvil. Una sola figura, a media distancia, gira
apenas la cabeza hacia las pantallas del fondo.
Cámara: dolly in continuo y sostenido, sin cortes, con una inestabilidad mínima de cámara en mano.
Entorno: el parpadeo tenue de los monitores sobre las superficies, polvo suspendido en el haz de
los fluorescentes.
Ritmo: el movimiento ya está en curso desde el primer fotograma. Avance constante. Alrededor del
segundo 5, la figura que gira la cabeza. Termina con la cámara detenida a media distancia del
ingeniero, en posición estable.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 2 · S01-P04 · 00:20 → 00:30 · CÁMARA B
**Voz encima:** «Veintiún minutos después tenía que reaparecer del otro lado de Marte» (00:22,1) · «No reapareció» (00:27,1)
`IMG_S01-P04.png` → `VID_S01-P04.mp4` · **adjuntar:** madre de B + placa de la nave

**Imagen:**
```
LA NAVE en el espacio, plano entero de tres cuartos, pequeña en el encuadre y desplazada al
tercio izquierdo, recortada contra MARTE que ocupa todo el fondo y está desenfocado. El panel
solar único hacia la derecha.
Luz solar dura desde la izquierda; la mitad de la nave en sombra profunda.
Momento inmediatamente anterior a la acción. Dejar aire alrededor de la nave.
```

**Video:**
```
La nave gira muy lentamente sobre su propio eje, apenas unos grados, dejando que la luz del Sol
recorra el panel solar de un extremo al otro. No se desplaza: solo rota. Marte permanece inmóvil
y desenfocado al fondo.
Cámara: fija, sin movimiento.
Entorno: el brillo se desplaza sobre la manta térmica dorada a medida que la nave gira.
Ritmo: el giro ya está en curso desde el primer fotograma, constante y muy lento. Alrededor del
segundo 6 el panel alcanza su punto de máximo brillo. Termina en una posición estable.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 3 · S02-P05 · 00:55 → 01:05 · CÁMARA B
**Voz encima:** «Y es la parte menos interesante» (00:55,3) · «Lo que lo derribó fue todo lo que no lo detuvo» (01:01,2)
`IMG_S02-P05.png` → `VID_S02-P05.mp4`

**Imagen:**
```
LA NAVE en plano entero, de perfil, ocupando el centro izquierda del encuadre, sola contra el
vacío. Sin planetas ni referencias. El panel solar único extendido hacia arriba.
Luz solar rasante desde atrás: contraluz que recorta la silueta y deja la cara frontal en sombra.
Momento inmediatamente anterior a la acción. Dejar espacio libre a la derecha.
```

**Video:**
```
La cámara se desplaza lateralmente pasando junto a la nave, que queda atrás y sale del encuadre
por la izquierda mientras la cámara sigue avanzando hacia el vacío. La nave no se mueve: es la
cámara la que la deja atrás.
Cámara: travelling lateral continuo hacia la derecha, velocidad constante.
Entorno: las estrellas del fondo se desplazan en paralaje, mucho más lento que la nave.
Ritmo: el movimiento ya está en curso desde el primer fotograma. La nave sale de cuadro alrededor
del segundo 6. Termina con el encuadre casi vacío y la cámara todavía en deriva suave.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 4 · S03-P03 · 01:15 → 01:25 · CÁMARA B
**Voz encima:** «existía una maniobra de emergencia que podía haber salvado la nave» (01:15,2) · «No se ejecutó» (01:21,9)
`IMG_S03-P03.png` → `VID_S03-P03.mp4`

**Imagen:**
```
LA NAVE en plano entero de tres cuartos, en el tercio izquierdo, con MARTE grande y nítido
ocupando el fondo derecho. La nave pasa cerca del limbo del planeta. Toberas apagadas, sin llama
ni escape.
Luz solar desde arriba a la derecha; la superficie de Marte rebota un tenue reflejo ocre sobre el
vientre de la nave.
Momento inmediatamente anterior a la acción. Dejar espacio libre a la izquierda.
```

**Video:**
```
La nave avanza despacio de izquierda a derecha frente al disco de Marte, sin encender motores.
Marte permanece fijo al fondo.
Cámara: arco lento alrededor de la nave, siguiéndola, revelando gradualmente el otro costado del
cuerpo y la cara oculta del panel solar.
Entorno: el reflejo ocre de Marte se desplaza sobre el vientre de la nave a medida que cambia el
ángulo.
Ritmo: el movimiento ya está en curso desde el primer fotograma. Un solo arco continuo, con el
punto de máxima revelación del costado oculto alrededor del segundo 6. Termina con la nave
centrada y estable.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 5 · S04-P04 · 01:50 → 02:00 · CÁMARA J **(única)** · el despegue
**Voz encima:** «Despegó el once de diciembre de mil novecientos noventa y ocho, desde Cabo Cañaveral» (01:54,5)
`IMG_S04-P04.png` → `VID_S04-P04.mp4`

**Imagen:**
```
Plano entero de un cohete Delta II en la plataforma de lanzamiento de noche, visto desde media
distancia y ligeramente contrapicado. El cohete apenas ha empezado a subir y todavía está a la
altura de la torre de servicio. Llama naranja intensa en la base, columna de humo blanco
abriéndose sobre la plataforma. Estructura metálica de la torre a la derecha. Un canal de agua en
primer plano refleja el naranja.
Luz: la propia llama ilumina toda la escena; el resto es noche cerrada.
Momento inmediatamente anterior a la acción. Dejar mucho espacio libre arriba.
```

**Video:**
```
El cohete asciende desde la plataforma ganando altura de forma continua, y hacia el final del
plano sale por la parte superior del encuadre. La llama se alarga bajo él. La columna de humo se
expande hacia los lados y hacia la cámara, cubriendo la base de la torre. La estructura de la
torre vibra levemente.
Cámara: tilt up lento siguiendo el ascenso, con vibración sutil de cámara en mano por la onda
sonora.
Entorno: el reflejo naranja en el agua se agita; el humo se ilumina desde dentro.
Ritmo: el ascenso ya está en curso desde el primer fotograma y acelera progresivamente, con el
momento de máxima energía alrededor del segundo 6. Termina con el cohete alto en el encuadre,
todavía en movimiento pero estable.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 6 · S05-P02 · 02:15 → 02:25 · CÁMARA C
**Voz encima:** «ruedas de reacción: volantes internos que giran y hacen rotar la nave» (02:14,3)
`IMG_S05-P02.png` → `VID_S05-P02.mp4` · **adjuntar:** madre de C (`S05-P03`)

**Imagen:**
```
Plano detalle del interior de un compartimento de la nave: una rueda de reacción, un volante
metálico pesado montado en una carcasa cilíndrica de aluminio, con cableado naranja y conectores
alrededor. La rueda está quieta pero lista para girar. Paneles de aislante plateado al fondo,
tornillos y estructura visibles.
Luz: una lámpara de trabajo lateral, dura, que deja el fondo del compartimento en negro.
Momento inmediatamente anterior a la acción. Encuadre cerrado y estable.
```

**Video:**
```
La rueda gira a alta velocidad dentro de su carcasa: el volante rota tan rápido que las marcas de
su superficie se difuminan en un borrón circular continuo. La carcasa y el cableado permanecen
completamente inmóviles.
Cámara: fija, encuadre cerrado.
Entorno: un reflejo de luz recorre el borde del volante en cada vuelta, produciendo un parpadeo
rápido y regular.
Ritmo: el giro ya está a plena velocidad desde el primer fotograma y se mantiene constante todo el
clip, sin arrancar ni frenar. Alrededor del segundo 6, una vibración mínima recorre la carcasa.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 7 · S05-P04 · 02:30 → 02:40 · CÁMARA C
**Voz encima:** «la nave encendía unos propulsores pequeñitos durante un instante» (02:30,2)
`IMG_S05-P04.png` → `VID_S05-P04.mp4` · **adjuntar:** madre de C

**Imagen:**
```
Plano detalle de una tobera de propulsor de control de actitud en el exterior de la nave: cono
metálico pequeño, del tamaño de un puño, montado sobre un bloque con líneas de combustible.
Alrededor, la superficie de manta térmica dorada arrugada. La tobera está apagada.
Luz solar rasante desde la izquierda que hace brillar el metal quemado del cono.
Momento inmediatamente anterior a la acción. Dejar espacio libre a la derecha para el escape.
```

**Video:**
```
El propulsor dispara una serie de pulsos brevísimos: cinco o seis destellos secos y separados,
cada uno de una fracción de segundo, con un penacho de gas casi invisible que sale hacia la
derecha y se disipa de inmediato. Entre pulso y pulso, quietud total.
Cámara: fija, encuadre cerrado.
Entorno: en cada destello, la manta térmica dorada de alrededor se ilumina un instante.
Ritmo: el primer pulso ocurre en el primer segundo. Los siguientes están espaciados de forma
irregular, con dos seguidos alrededor del segundo 6. Termina con la tobera apagada y quieta.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 8 · S06-P02 · 02:55 → 03:05 · CÁMARA B · la separación
**Voz encima:** «un programa llamado Small Forces calculaba cuánto había empujado ese disparo y lo guardaba en un archivo» (02:54,2)
`IMG_S06-P02.png` → `VID_S06-P02.mp4`

**Imagen:**
```
Dos copias de LA NAVE superpuestas en el mismo encuadre, ambas en plano entero de tres cuartos y
ligeramente desplazadas una de otra, como una doble exposición. Una es sólida y nítida; la otra
es semitransparente y fantasmal, desplazada unos centímetros abajo y a la derecha. Fondo de campo
estelar.
Luz solar dura desde la izquierda sobre ambas.
Momento inmediatamente anterior a la acción. Dejar espacio libre abajo a la derecha.
```

**Video:**
```
Las dos copias se van separando lentamente: la semitransparente se desplaza hacia abajo y a la
derecha, alejándose de la sólida, hasta quedar claramente aparte al final del clip. Ambas
mantienen la misma orientación.
Cámara: fija, sin movimiento.
Entorno: el campo estelar permanece inmóvil.
Ritmo: la separación ya está en curso desde el primer fotograma, lenta y constante. Alrededor del
segundo 6 la distancia entre las dos se hace evidente. Termina con las dos naves visiblemente
distanciadas y quietas.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 9 · S07-P03 · 03:40 → 03:50 · CÁMARA B · el panel y el Sol
**Voz encima:** «el Sol empujaba contra él sin parar» (03:37,4) · «girar la nave entera cada día» (03:45,8)
`IMG_S07-P03.png` → `VID_S07-P03.mp4`

**Imagen:**
```
LA NAVE en plano entero de tres cuartos, centrada, con el panel solar único hacia la izquierda y
el Sol como fuente puntual brillante fuera de cuadro por la derecha. Sombras marcadas cruzando el
cuerpo de la nave.
Momento inmediatamente anterior a la acción. Dejar aire alrededor de toda la nave para que pueda
rotar sin salirse del encuadre.
```

**Video:**
```
La nave rota muy lentamente sobre su eje vertical mientras la luz del Sol barre el panel solar de
punta a punta. A medida que gira, el panel pasa de estar de canto a mostrar toda su superficie a
la luz, y las sombras cruzan el cuerpo.
Cámara: fija, la nave centrada.
Entorno: el brillo especular se desplaza a lo largo del panel; la manta térmica cambia de tono
según el ángulo.
Ritmo: la rotación ya está en curso desde el primer fotograma, muy lenta y constante. Alrededor
del segundo 6 el panel queda de frente al Sol y el destello es máximo. Termina con la nave
estable.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

## 10 · S09-P02 · 04:40 → 04:50 · CÁMARA B · la línea invisible
**Voz encima:** «El empujón acumulado apuntaba casi perpendicular a la línea entre la Tierra y la nave» (04:40,9)
`IMG_S09-P02.png` → `VID_S09-P02.mp4`

**Imagen:**
```
Plano espacial amplio: en el extremo izquierdo del encuadre, la Tierra pequeña y azul; en el
extremo derecho y muy lejos, LA NAVE, minúscula. Entre ambas, el vacío negro atravesando todo el
cuadro en horizontal.
Luz solar desde arriba. Composición deliberadamente vacía en el centro.
Momento inmediatamente anterior a la acción. Dejar libre toda la franja central.
```

**Video:**
```
La cámara viaja en línea recta a través del vacío desde la Tierra hacia la nave, recorriendo la
distancia que las separa. La Tierra sale del encuadre por la izquierda al principio; la nave crece
muy poco al fondo, siempre lejana.
Cámara: travelling frontal continuo hacia la derecha, velocidad constante, sin rotación.
Entorno: las estrellas se desplazan en paralaje, las cercanas más rápido que las lejanas, dando
sensación de recorrer una distancia enorme.
Ritmo: el movimiento ya está en curso desde el primer fotograma. Alrededor del segundo 6 la Tierra
ya salió y solo queda vacío. Termina con la cámara todavía en tránsito, la nave apenas más grande
que al principio.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y el
grano de la imagen de origen sin alterarlos.
```

---

# Control de calidad

**Regenerá la imagen** si: la nave tiene dos paneles solares · aparece texto o un número legible ·
el espacio no coincide con la madre de su cámara · el sujeto está pegado al borde por el lado
hacia donde tiene que moverse.

**Regenerá el clip** si: el primer fotograma tiene medio segundo de quietud · el movimiento se
agota antes del segundo 7 · el último fotograma queda a medio gesto · la paleta derivó respecto
de la semilla.

Previsión de reintentos: **1,3×** → contá ~13 generaciones de Veo para estos 10 clips.
