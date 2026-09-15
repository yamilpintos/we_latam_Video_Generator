# PROMPTS 02 — Imágenes para IMAGEN EN MOVIMIENTO (DepthFlow)

**Mars Climate Orbiter · 0:00 – 5:00 · 28 planos de 5 segundos**

Se generan en ChatGPT y se animan localmente con DepthFlow. **Sin créditos, sin marca de agua.**
Al final están los 12 planos gráficos, que no llevan imagen generada.

---

# PROMPT MAESTRO · ChatGPT

Primer mensaje del chat, junto con la imagen madre de la cámara y la placa de la nave.

```
Vas a generar imágenes que después se animan en 3D: un programa calcula el mapa de profundidad y
mueve una cámara virtual sobre ellas. No son ilustraciones planas. Eso implica:

1. TRES CAPAS DE PROFUNDIDAD CLARAS Y SEPARADAS: algo definido en primer plano, el sujeto en el
   medio, un fondo distinto detrás. Es lo que produce el paralaje. Una imagen con todo a la misma
   distancia se anima como una postal deslizándose.
2. AIRE ALREDEDOR DEL SUJETO. El movimiento por defecto es un acercamiento: si el sujeto ya llena
   el encuadre, no hay a dónde entrar.
3. NADA DE DETALLE FINO Y CRÍTICO PEGADO AL BORDE INFERIOR. Es la zona que más se desplaza y la
   que se estira.

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
Las personas van de espaldas, en silueta o con la cara fuera de foco.
COMPOSICIÓN: horizontal, con aire arriba y abajo porque se recorta a 16:9.
EN EL ESPACIO: luz solar dura y direccional sin difusión, sombras de borde definido, negro
absoluto sin niebla atmosférica, estrellas escasas y pequeñas.
```

# El movimiento

**Intensidad fija: 0,45.** Tres sentidos, y la regla es que **no se repite el sentido en planos
consecutivos**.

| | Cuándo | |
|---|---|---|
| **acercar** | El plano concentra: hay una cosa que mirar | `zoom` 1,00 → 0,865 |
| **alejar** | El plano amplía: contexto, escala, soledad | `zoom` 0,865 → 1,00 |
| **quieto** | El peso está en la voz, o el sujeto ya se mueve | Solo respira |

```bash
uv run tools/depthflow_batch.py --shotlist tools/shotlist-mco.csv \
    --images output/mars-climate-orbiter/img --out output/mars-climate-orbiter/mov --ssaa 2.0
```

Antes de renderizar, escalá las imágenes a **1920×1080**: ChatGPT entrega 1536 px de ancho.

---

# El árbol de cámaras

14 cámaras. Las **madres se generan primero** y sirven de referencia para sus hijos.
Verificá el elemento distintivo de cada madre antes de aprobarla.

| Cámara | Locación | Madre | Hijos |
|---|---|---|---|
| **A** | Sala de control JPL | `S01-P01` *(está en Veo)* | S01-P03, S02-P04 |
| **B** | La nave en el espacio | `S04-P01` | S01-P05*, S04-P06, S05-P01, S07-P01 |
| **C** | Detalle mecánico | `S05-P03` | S05-P06 |
| **D** | Marte desde órbita | `S04-P02` | S01-P05, S09-P04 |
| **E** | Oficina técnica de día | `S07-P05` | S06-P05, S06-P07, S07-P04 |
| **F** | Oficina de noche | `S08-P03` | S08-P02, S08-P04, S08-P05, S09-P01 |
| **G** | Sala de reuniones | `S03-P04` | S03-P01 |
| **H** | Antena DSN | `S06-P01` | — |
| **I** | Sala limpia | `S03-P05` | — |
| **K** | Superficie de Marte | `S04-P03` | — |
| **L** | Aula, pizarrón | `S02-P03` | — |
| **M** | Mesa de fórmica | `S02-P01` | — |
| **N** | Pasillo de oficinas | `S07-P07` | — |

*Las madres A, C y J viven en el archivo de Veo porque son planos de video. Generalas primero
igual: son referencia de esta capa.*

---

# S01 · Cold open

### S01-P03 · 00:15 → 00:20 · CÁMARA A · **alejar**
**Voz:** «Nadie en esa sala entiende todavía qué acaba de pasar» (00:18,3)
**Motivo:** el estado es colectivo — el plano tiene que abrirse sobre todos
`IMG_S01-P03.png` · adjuntar madre de A
```
Plano general de LA SALA desde una esquina alta. Ocho o nueve figuras de pie entre los
escritorios, todas quietas, de espaldas o de perfil borroso, mirando hacia las pantallas del
fondo. Nadie sentado. Postura de espera.
Primer plano: el respaldo de una silla vacía, desenfocado. Fondo: las pantallas de proyección.
Luz: fluorescentes fríos, resplandor azulado de las pantallas grandes.
```
**Capas:** frente = silla vacía · medio = las figuras · fondo = pantallas de proyección

### S01-P05 · 00:30 → 00:35 · CÁMARA D · **quieto**
**Voz:** «esa nave llevaba nueve meses viajando hacia un número equivocado» (00:28,8)
**Motivo:** la ausencia de la nave es el punto; cualquier movimiento la suavizaría
`IMG_S01-P05.png` · adjuntar madre de D
```
MARTE a media distancia, ocupando el tercio derecho del encuadre, con el terminador día-noche
cruzándolo. Dos tercios del cuadro son espacio vacío y negro a la izquierda. Ninguna nave a la
vista.
Luz solar dura desde la derecha. Estrellas escasas.
```
**Capas:** frente = ninguno · medio = Marte · fondo = campo estelar

---

# S02 · La versión famosa

### S02-P01 · 00:35 → 00:40 · CÁMARA M **(madre única)** · **acercar**
**Voz:** «Seguro escuchaste la explicación» (00:35,3)
**Motivo:** objeto — el documento es lo único que hay que mirar
```
Plano cenital cerrado sobre una mesa de fórmica gastada. Un periódico doblado, papel amarillento,
junto a una taza de café con marca de cerco y unos anteojos de montura fina. La página muestra una
fotografía borrosa de un cohete pero el texto es ilegible, fuera de foco.
Luz: lámpara de escritorio cálida desde la izquierda, resto en penumbra. Dejar espacio vacío en la
mitad inferior de la mesa.
```
**Capas:** frente = borde de la mesa desenfocado · medio = el diario · fondo = penumbra

### S02-P03 · 00:45 → 00:50 · CÁMARA L **(madre única)** · **alejar**
**Voz:** «Es la anécdota perfecta. Se cuenta en cada clase de ingeniería del mundo» (00:47,4)
**Motivo:** de la fórmula al aula — el plano amplía hacia el lugar común
```
Plano medio de un pizarrón verde de aula con ecuaciones y diagramas escritos en tiza blanca, a
medio borrar, con manchas de borrador. Una bandeja con tizas y un borrador de fieltro en el borde
inferior. Sin ninguna letra o número legible: solo el gesto de la escritura.
Luz: ventana lateral izquierda, luz de tarde entrando en diagonal, polvo de tiza suspendido.
```
**Capas:** frente = la bandeja con tizas · medio = el pizarrón · fondo = la pared

### S02-P04 · 00:50 → 00:55 · CÁMARA A · **quieto**
**Voz:** «Esa versión es cierta» (00:52,3) y el silencio que sigue
**Motivo:** es la frase más importante del bloque; el movimiento distraería
`IMG_S02-P04.png` · adjuntar madre de A
```
Plano general de LA SALA vacía y a oscuras. Sillas giradas en distintas direcciones, algunas
apartadas de los escritorios. Monitores apagados. Papeles y carpetas abandonados sobre las mesas.
Ninguna persona. La taza roja sigue en la tercera mesa de la fila izquierda.
Luz: solo las luces de emergencia verdes de las salidas y un resplandor tenue desde un pasillo
fuera de cuadro. Casi todo en penumbra.
```
**Capas:** frente = una silla girada · medio = las filas de escritorios · fondo = las pantallas apagadas

---

# S03 · La promesa

### S03-P01 · 01:05 → 01:10 · CÁMARA G · **acercar**
**Voz:** «La investigación oficial de la NASA no encontró una causa. Encontró nueve» (01:05,5)
**Motivo:** objeto clave de la historia
`IMG_S03-P01.png` · adjuntar madre de G
```
Plano cenital cerrado sobre la mesa de reuniones. Un informe grueso encuadernado con espiral y
tapa de cartulina lisa, cerrado, junto a un vaso de agua y un bolígrafo. La tapa no tiene texto
legible.
Luz: una única luminaria cenital que forma un óvalo de luz sobre el informe y deja los bordes de
la mesa en sombra.
```
**Capas:** frente = el borde de la mesa · medio = el informe · fondo = la sombra del salón

### S03-P04 · 01:25 → 01:30 · CÁMARA G **(madre)** · **alejar**
**Voz:** «Nadie entendió del todo que hacía falta» (01:26,8)
**Motivo:** la responsabilidad es colectiva — el plano se abre sobre la mesa entera
```
Plano general de una sala de reuniones institucional de 1999, desde el extremo de una mesa larga
de madera oscura. Siete u ocho personas sentadas a ambos lados, todas de espaldas a cámara o de
perfil borroso, inclinadas hacia adelante. Carpetas abiertas, vasos, un proyector de
transparencias apagado. EN EL EXTREMO CERCANO DE LA MESA, UN VASO DE AGUA VOLCADO sobre una
carpeta abierta.
Luz: fluorescentes cenitales duros, sin ventanas. Ambiente cerrado y tenso.
```
**Capas:** frente = el vaso volcado · medio = las personas · fondo = la pared y el proyector

### S03-P05 · 01:30 → 01:35 · CÁMARA I **(madre única)** · **quieto**
**Voz:** «hay que empezar por el principio» (01:29,8)
**Motivo:** placa contemplativa; la nave está inerte, en construcción
```
Plano medio en una sala limpia de ensamblaje aeroespacial. LA NAVE a medio construir sobre un
soporte de montaje metálico, con la manta térmica dorada parcialmente puesta y cableado a la
vista. Dos técnicos con traje blanco integral, gorro y mascarilla, de espaldas, trabajando sobre
ella. Andamios y carros de herramientas alrededor.
Luz: fluorescentes muy blancos y difusos desde el techo, sombras suaves, todo sobreexpuesto y
limpio.
```
**Capas:** frente = un carro de herramientas · medio = la nave y los técnicos · fondo = la pared de la sala limpia

---

# S04 · Qué era y cómo salió

### S04-P01 · 01:35 → 01:40 · CÁMARA B **(madre)** · **acercar**
**Voz:** «El Mars Climate Orbiter era un satélite meteorológico» (01:35,5)
**Motivo:** primera presentación del sujeto del video
```
LA NAVE en plano entero, vista de tres cuartos frontal, centrada y ocupando la mitad del encuadre,
con el panel solar único completamente desplegado hacia la izquierda. Fondo de campo estelar
profundo, sin planetas. EN EL COSTADO DEL CUERPO, UNA MANCHA DE HOLLÍN JUNTO A UNA DE LAS TOBERAS.
Luz solar dura desde la derecha, la manta térmica dorada devolviendo un brillo cálido, el panel
azul oscuro casi negro en la sombra.
```
**Capas:** frente = una tobera en primer término · medio = el cuerpo de la nave · fondo = campo estelar

### S04-P02 · 01:40 → 01:45 · CÁMARA D **(madre)** · **alejar**
**Voz:** «las tormentas de polvo, el vapor de agua, las estaciones» (01:41,5)
**Motivo:** escala planetaria
```
Vista orbital cercana de la superficie de MARTE, mirando hacia abajo en ángulo oblicuo. Una
llanura de tonos óxido con cráteres, y un frente de tormenta de polvo avanzando de derecha a
izquierda como una masa parda que borra el terreno bajo ella. La atmósfera visible como una capa
delgada y rosada en el horizonte curvo, arriba del encuadre. UN CRÁTER GRANDE CON EL BORDE
PARTIDO EN EL TERCIO IZQUIERDO.
Luz solar rasante desde la derecha, sombras largas de los bordes de cráter.
```
**Capas:** frente = el borde del cráter partido · medio = la tormenta · fondo = el horizonte curvo

### S04-P03 · 01:45 → 01:50 · CÁMARA D · **quieto**
**Voz:** «el vapor de agua, las estaciones» (dentro de 01:41,5 – 01:47,3)
**Motivo:** placa contemplativa mientras la voz enumera; el plano no compite
`IMG_S04-P03.png` · adjuntar madre de D
```
Vista orbital del casquete polar sur de MARTE: hielo blanco sucio con vetas de polvo rojizo, el
borde deshilachado donde el hielo se sublima. Sobre él, una capa fina de nubes de vapor de agua,
apenas visible, que sigue la curvatura del planeta. El horizonte curvo cruza el tercio superior.
Luz solar muy rasante desde la izquierda, que hace largas las sombras del relieve helado.
```
**Capas:** frente = el relieve del hielo · medio = la capa de nubes · fondo = el horizonte curvo

### S04-P04 · 01:50 → 01:55 · CÁMARA K **(madre única)** · **acercar**
**Voz:** «servir de antena repetidora para el Mars Polar Lander» (01:48,4 – 01:53,4)
**Motivo:** objeto: la otra nave, nombrada exactamente acá
```
Plano medio de un módulo de aterrizaje robótico posado sobre una llanura helada: cuerpo bajo
octogonal envuelto en aislante dorado, tres patas con almohadillas circulares, dos paneles solares
desplegados a los costados como alas, un brazo robótico plegado. Alrededor, hielo sucio mezclado
con polvo rojizo y grietas superficiales.
Luz: sol muy bajo en el horizonte, cielo pardo rosado, sombras larguísimas hacia la cámara.
```
**Capas:** frente = grietas del hielo · medio = el módulo · fondo = el horizonte

---

# S05 · Las ruedas y los empujones

### S05-P01 · 02:10 → 02:15 · CÁMARA B · **quieto**
**Voz:** «Una nave en el espacio tiene que controlar hacia dónde apunta» (02:10,4)
**Motivo:** la voz explica; el contraluz se sostiene solo
`IMG_S05-P01.png` · adjuntar madre de B
```
LA NAVE en plano medio, encuadre cerrado sobre el cuerpo principal y la base del panel solar, de
perfil. El panel se extiende hacia la derecha y sale del cuadro. Detrás, el Sol como una fuente
puntual muy brillante justo detrás del borde del panel, produciendo un destello contenido.
Luz: contraluz extremo, el frente de la nave casi en silueta, con un halo en el contorno.
```
**Capas:** frente = el borde del panel · medio = el cuerpo · fondo = el Sol y el negro

### S05-P03 · 02:25 → 02:30 · CÁMARA C **(madre)** · **acercar**
**Voz:** «esas ruedas se saturan. Se llenan de giro y dejan de servir» (02:22,5)
**Motivo:** detalle mecánico — inserto
```
Plano detalle macro de una rueda de reacción montada en su soporte estructural: carcasa cilíndrica
de aluminio mecanizado, tornillos de titanio, una etiqueta de aislante sin texto legible, un mazo
de cables trenzados saliendo por un conector circular. UNO DE LOS TORNILLOS TIENE LA CABEZA
RAYADA Y PINTADA DE ROJO.
Luz: lateral dura de una sola fuente, con el reverso en sombra. Profundidad de campo muy corta:
solo el conector está nítido.
```
**Capas:** frente = el mazo de cables · medio = la carcasa · fondo = la estructura desenfocada

### S05-P06 · 02:45 → 02:50 · CÁMARA C · **alejar**
**Voz:** «[serious] Casi» (02:48,6) — el remate del bloque
**Motivo:** después del golpe, el plano se abre y deja respirar
`IMG_S05-P06.png` · adjuntar madre de C
```
Primerísimo plano de la boca de una tobera de propulsor, ocupando el centro del encuadre. Metal
oscurecido por el calor, con tonos azulados y pardos de recocido, y un residuo de hollín en el
labio. Textura de mecanizado visible.
Luz: rasante desde abajo, que recorta el relieve del metal. Fondo completamente negro y
desenfocado.
```
**Capas:** frente = el labio de la tobera · medio = el cono · fondo = negro

---

# S06 · El archivo

### S06-P01 · 02:50 → 02:55 · CÁMARA H **(madre única)** · **acercar**
**Voz:** «Cada vez que pasaba, los datos viajaban a la Tierra» (02:50,5)
**Motivo:** objeto — la antena que recibe
```
Plano general nocturno de una antena parabólica gigante de espacio profundo en un desierto alto:
plato de más de treinta metros, estructura blanca de celosía metálica, contrapesos, torreta sobre
base circular de hormigón. Vista de perfil, el plato inclinado apuntando alto hacia la derecha.
Terreno árido con arbustos bajos en primer plano.
Luz: dos balizas rojas parpadeando en la estructura y un foco de sodio ámbar en la base; el resto
en silueta contra un cielo estrellado limpio.
```
**Capas:** frente = arbustos en silueta · medio = la antena · fondo = el cielo estrellado

### S06-P05 · 03:15 → 03:20 · CÁMARA E · **alejar**
**Voz:** «No es lo mismo. Una libra-fuerza son cuatro coma cuarenta y cinco newtons» (03:14,0)
**Motivo:** después de dos gráficos cerrados, el plano vuelve al mundo físico y se abre
`IMG_S06-P05.png` · adjuntar madre de E
```
Plano cerrado y ligeramente en ángulo de un monitor CRT de fósforo verde de finales de los
noventa. La pantalla muestra columnas de datos numéricos corriendo, borrosas y sin ningún número
legible: solo el patrón de filas y el resplandor verde. La carcasa beige enmarca el plano.
Luz: solo el fósforo verde de la pantalla, que ilumina el polvo del aire y el borde de la carcasa.
Todo lo demás en negro.
```
**Capas:** frente = el borde de la carcasa · medio = la pantalla · fondo = la oficina en negro

### S06-P07 · 03:25 → 03:30 · CÁMARA E · **quieto**
**Voz:** «Cada vez. Durante nueve meses» (03:25,7)
**Motivo:** la impresora ya tiene movimiento propio; la cámara no compite
`IMG_S06-P07.png` · adjuntar madre de E
```
Plano medio de una impresora matricial de los noventa sobre una mesa, expulsando papel continuo
plegado con perforaciones laterales. El papel se acumula en una pila irregular sobre el suelo.
Las hojas tienen líneas impresas pero ningún carácter legible.
Luz: fluorescente cenital de oficina, fría y plana, con una sombra dura de la impresora sobre la
mesa.
```
**Capas:** frente = la pila de papel en el suelo · medio = la impresora · fondo = la oficina

---

# S07 · Por qué se multiplicó

### S07-P02 · 03:35 → 03:40 · CÁMARA B · **acercar**
**Voz:** «tenía un panel solar enorme montado de un solo lado» (03:37,4 – 03:44,7)
**Motivo:** la asimetría del panel es la causa del accidente — hay que **verla**, y la voz la nombra justo acá
`IMG_S07-P02.png` · adjuntar madre de B
```
LA NAVE en plano entero, vista estrictamente de perfil y centrada, de modo que la asimetría sea
evidente: el cuerpo en el centro y el ÚNICO panel solar extendiéndose largo hacia un solo lado,
sin nada del otro. Encuadre limpio, sin planetas.
Luz solar frontal desde el lado del panel, que lo deja iluminado y el lado vacío en sombra.
```
**Capas:** frente = la punta del panel · medio = el cuerpo · fondo = negro

### S07-P04 · 03:50 → 03:55 · CÁMARA E · **alejar**
**Voz:** «Lo llamaban modo barbacoa. Se canceló» (hasta 03:53,3)
**Motivo:** de la decisión al lugar donde se tomó
`IMG_S07-P04.png` · adjuntar madre de E
```
Plano cenital cerrado sobre un único documento impreso apoyado en una mesa, ligeramente girado. En
el pie de la hoja se ve una firma manuscrita en tinta azul y la marca de un sello, pero el texto
del cuerpo está desenfocado e ilegible. Al lado, la tapa de un bolígrafo.
Luz: una fuente lateral baja que produce una sombra larga del papel sobre la mesa. Dejar la mitad
superior de la hoja vacía.
```
**Capas:** frente = la tapa del bolígrafo · medio = el documento · fondo = la mesa en sombra

### S07-P05 · 03:55 → 04:00 · CÁMARA E **(madre)** · **acercar**
**Voz:** «Nadie le avisó a navegación» (03:54,4) · «Ni una nota, ni un correo, ni una reunión» (03:57,0)
**Motivo:** es el golpe del bloque; entrar sobre las dos personas que no avisaron
```
Plano medio de dos personas de pie frente a una mesa de trabajo en una oficina de ingeniería de
los noventa, ambas de espaldas a cámara, inclinadas sobre un plano técnico grande desplegado. Una
señala un punto del plano con un bolígrafo. Alrededor, reglas, una calculadora científica,
carpetas apiladas. EN EL BORDE DE LA MESA, UNA TAZA BLANCA CON UNA GRIETA VISIBLE EN EL ASA.
Luz: lámpara de brazo articulado sobre el plano, cálida, y fluorescentes fríos al fondo. Los
planos técnicos no muestran texto legible.
```
**Capas:** frente = la taza agrietada · medio = las dos personas · fondo = la oficina

### S07-P07 · 04:05 → 04:10 · CÁMARA N **(madre única)** · **alejar**
**Voz:** cola del bloque, después de «diez y catorce veces más seguido»
**Motivo:** vacío institucional; el plano se abre sobre lo que quedó
```
Plano general de un pasillo largo de oficinas visto en perspectiva central, con puertas a ambos
lados y paneles de luz fluorescente en el techo. Casi todos los tramos están apagados; solo uno,
al fondo a la derecha, sigue encendido y deja un rectángulo de luz sobre el suelo.
Luz: ese único tramo encendido y las señales verdes de salida. Todo lo demás en penumbra azulada.
Noche.
```
**Capas:** frente = el marco de una puerta · medio = el pasillo · fondo = el tramo encendido

---

# S08 · Ya lo estaban viendo

### S08-P02 · 04:15 → 04:20 · CÁMARA F · **acercar**
**Voz:** «Y durante meses, nadie los vio» (04:18,3)
**Motivo:** objeto que mide el tiempo
`IMG_S08-P02.png` · adjuntar madre de F
```
Plano medio de un calendario de pared de oficina colgado junto a un tablón de corcho. La hoja del
mes está tachada día por día con cruces de bolígrafo azul, algunas superpuestas. El papel está
levemente ondulado. Los números no son legibles: se ven las cruces, no las fechas.
Luz: fluorescente lateral, fría, con una sombra dura del calendario sobre la pared.
```
**Capas:** frente = el borde del tablón · medio = el calendario · fondo = la pared

### S08-P03 · 04:20 → 04:25 · CÁMARA F **(madre)** · **alejar**
**Voz:** «[whispers] Aunque casi» (04:21,3) · «En abril del noventa y nueve…» (04:22,7)
**Motivo:** la soledad se lee abriendo
```
Plano general desde atrás de una persona sentada sola frente a tres monitores CRT en una oficina
por lo demás vacía y a oscuras. Solo se ve su espalda, la nuca y los hombros, en silueta contra el
resplandor de las pantallas. Escritorios vacíos a los lados. Es de noche. EN EL ESCRITORIO DE AL
LADO, UNA LÁMPARA DE BRAZO APAGADA Y DOBLADA HACIA ABAJO.
Luz: exclusivamente el resplandor verde y ámbar de los tres monitores, que recorta la silueta y
deja el resto de la sala en negro.
```
**Capas:** frente = el respaldo de una silla vacía · medio = la persona y los monitores · fondo = la sala en negro

### S08-P04 · 04:25 → 04:30 · CÁMARA F · **acercar**
**Voz:** «notó que los datos no cuadraban» (hasta 04:28,9)
**Motivo:** retrato. Entrar en el plano es entrar en la persona
`IMG_S08-P04.png` · adjuntar madre de F
```
Primer plano parcial de un rostro de perfil de tres cuartos, cortado por el encuadre, iluminado
únicamente por la luz de una pantalla desde abajo y de costado. Se ven la mandíbula, la mejilla y
un ojo entrecerrado con ojeras marcadas; la parte superior de la cabeza queda fuera de cuadro. La
mitad del rostro está en sombra profunda.
Luz: pantalla desde abajo a la izquierda, verde azulada, dura. Fondo negro absoluto.
```
**Capas:** frente = el borde desenfocado del monitor · medio = el rostro · fondo = negro

### S08-P05 · 04:30 → 04:35 · CÁMARA F · **quieto**
**Voz:** «Que las perturbaciones eran bastante más grandes» (04:29,9)
**Motivo:** el dato ya está marcado; el movimiento distraería de él
`IMG_S08-P05.png` · adjuntar madre de F
```
Plano cenital muy cerrado sobre una hoja de papel continuo impreso con filas de datos, sobre una
mesa. Una línea del listado está rodeada a mano con un círculo de bolígrafo azul, trazado dos
veces con insistencia. El resto de los caracteres está fuera de foco e ilegible; solo el círculo
está nítido.
Luz: lámpara de escritorio desde la derecha, luz cálida y concentrada, bordes de la hoja en
penumbra.
```
**Capas:** frente = el borde de la hoja · medio = el círculo azul · fondo = la mesa

---

# S09 · Invisible

### S09-P01 · 04:35 → 04:40 · CÁMARA F · **alejar**
**Voz:** «Lo investigaron. No encontraron por qué» (04:35,2)
**Motivo:** rendición: el cuerpo se abandona, el plano se abre
`IMG_S09-P01.png` · adjuntar madre de F
```
Plano medio de una persona recostada hacia atrás en una silla de oficina, con las manos cruzadas
detrás de la nuca y la cabeza girada hacia arriba mirando el techo. Vista de tres cuartos desde
atrás y de costado: la cara no se ve. Delante, el borde de un escritorio con monitores encendidos.
La lámpara de brazo apagada sigue doblada en el escritorio de al lado.
Luz: resplandor de pantalla desde abajo, un fluorescente lejano al fondo. Oficina de noche.
```
**Capas:** frente = el borde del escritorio · medio = la persona · fondo = la oficina vacía

### S09-P04 · 04:55 → 05:00 · CÁMARA D · **acercar**
**Voz:** «[somber] El error estaba a la vista. Y era invisible» (04:56,4) — el cierre
**Motivo:** el plano final entra sobre el planeta y deja el silencio
`IMG_S09-P04.png` · adjuntar madre de D
```
MARTE llenando el encuadre entero, sin espacio negro visible salvo una franja fina en la esquina.
El terminador día-noche cruza el cuadro en diagonal: la mitad izquierda iluminada con detalle de
cráteres y llanuras, la derecha hundiéndose en sombra total. El cráter de borde partido es visible
cerca del terminador.
Luz solar rasante desde la izquierda, que alarga las sombras de todo el relieve.
```
**Capas:** frente = el relieve del terminador · medio = la llanura iluminada · fondo = la sombra

---

# Los 12 planos gráficos

**No llevan imagen generada.** Son motion graphics a mano en el editor, de 5 s cada uno.
Sistema de diseño: fondo negro, trazo verde fósforo `#4AE07A`, énfasis ámbar `#E0A24A`,
tipografía monoespaciada, grano al 8 %.

| ID | IN → OUT | Voz encima | Qué aparece |
|---|---|---|---|
| S01-P02 | 00:10 → 00:15 | «una señal… se apaga» | Traza de osciloscopio que cae a línea plana en el segundo 2 |
| S02-P02 | 00:40 → 00:45 | «Metros contra pies» | Una regla en pulgadas y una en centímetros que se superponen mal |
| S03-P02 | 01:10 → 01:15 | «Una causa raíz, y ocho fallos» | Nueve líneas apareciendo; la primera en ámbar, las ocho en verde |
| S04-P06 | 02:05 → 02:10 | «Nueve meses y medio de viaje» | Trayectoria Type 2: Sol al centro, arco de más de 180° |
| S05-P05 | 02:40 → 02:45 | «Cada uno de esos disparos empujaba la nave un poquito» | Contador de desaturaciones acumulándose |
| **S06-P03** | **03:05 → 03:10** | **«El archivo escribía los números en libra-fuerza-segundo» (03:05,3)** | Solo `lbf·s`, grande, con `libra-fuerza-segundo` debajo |
| **S06-P04** | **03:10 → 03:15** | **«Navegación los leía como newton-segundo» (03:09,8)** | `lbf·s` se sustituye por `N·s`; al segundo 2,5 entra la flecha `× 4,45` |
| **S06-P06** | **03:20 → 03:25** | **«Donde el archivo decía diez, la realidad decía cuarenta y cuatro con cinco» (03:20,0)** | El `10` se estira y se transforma en `44,5` |
| S07-P01 | 03:30 → 03:35 | «Un solo disparo mal calculado no habría movido nada» | Una flecha diminuta empuja una trayectoria larga y no la desvía |
| S07-P06 | 04:00 → 04:05 | «diez y catorce veces más seguido» | Dos barras: «esperado» se detiene, «real» sigue subiendo · `× 10–14` |
| S08-P01 | 04:10 → 04:15 | «Miles de disparos. Todos en la misma dirección» | Cientos de flechas diminutas que se agrupan en una sola |
| S09-P03 | 04:50 → 04:55 | «Podían ver que algo empujaba. No podían ver cuánto» | Doppler: la componente radial se ilumina, la perpendicular se apaga |

**Los tres en negrita son sincronía dura.** `S06-P03`, `S06-P04` y `S06-P06` están colocados para
que la palabra caiga exactamente adentro. Si los movés, se rompe el momento clave del video.

---

# Verificación

| | |
|---|---|
| Imágenes a generar acá | **28** |
| Cámaras madre | 14 (3 viven en el archivo de Veo) |
| Reparto de sentido | 11 acercar · 10 alejar · 7 quieto |
| Sentido repetido en planos consecutivos | ninguno |
| Planos gráficos | 12, sin imagen |
| **Total del video** | 10 VEO + 28 DepthFlow + 12 GFX = **50 planos · 300 s** |
