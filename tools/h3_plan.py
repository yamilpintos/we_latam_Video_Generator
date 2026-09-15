"""
Los 10 planos de movimiento de Mars Climate Orbiter, listos para MiniMax H3.

Fuente única: de acá salen tanto el generador (`h3_generate.py`) como cualquier
documento. Los textos son los de `pipeline/PROMPTS-01-IMAGENES-PARA-VEO.md`,
copiados textualmente. Los IDs y timecodes están contra
`pipeline/PROMPTS-00-GUION-Y-TIMELINE.md`, que es la referencia que manda:
el plano de S04 es **S04-P05** (01:55→02:05), no el S04-P04 que quedó escrito
en PROMPTS-01.

Cada plano guarda las dos mitades por separado:

    escena       lo que describía la imagen semilla — el espacio, la luz, el encuadre
    movimiento   lo que pasa durante los 10 segundos

Con imagen semilla se manda solo el `movimiento`: el encuadre y el estilo los
hereda de la imagen. Sin imagen (`--t2v`) se manda ESTILO + escena + movimiento,
porque no hay de dónde heredarlos.

**Duración: 10 s.** La grilla del proyecto pasó a 8/5 por el techo de Veo 3;
H3 llega a 15 s, así que vuelve a ser la 10/5 con la que está escrito el guion.
"""

from typing import NamedTuple


class Plano(NamedTuple):
    id: str
    ini: str
    out: str
    camara: str
    dur: int
    escena: str
    movimiento: str


# Va al final de todos los prompts. H3 genera audio nativo igual que Veo: sin
# esto mete voces inventadas en inglés. Silenciar igual la pista en el editor.
CIERRE = (
    "Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, "
    "la paleta y el grano de la imagen de origen sin alterarlos."
)

# Solo para text-to-video: sin imagen semilla no hay de dónde heredar el look.
# Es el bloque ESTILO del prompt maestro de PROMPTS-01.
ESTILO = """\
ESTILO: fotografía cinematográfica documental, recreación de 1999. Emulsión de película 35 mm con
grano visible y halación suave en las luces. Paleta de ámbar apagado, verde fósforo de monitor CRT
y azul acero. Iluminación exclusivamente de fuentes visibles en el plano, nada de luz de relleno
inventada. Lente 35 mm, profundidad de campo media, leve aberración cromática en los bordes.
Contraste medio-alto con negros levantados.
PROHIBIDO: texto, letreros legibles, números en pantalla, logotipos, marcas de agua, bordes.
EN EL ESPACIO: luz solar dura y direccional sin difusión, sombras de borde definido, negro absoluto
sin niebla atmosférica, estrellas escasas y pequeñas."""

# Las escenas dicen «LA NAVE»; sin semilla hay que decir cuál es.
NAVE = """\
LA NAVE es la Mars Climate Orbiter: cuerpo de caja con manta térmica dorada, UN SOLO panel solar
grande montado a un costado, antena parabólica blanca arriba."""


PLANOS = [
    Plano("S01-P01", "00:00", "00:10", "A", 10, """\
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
Luz: fluorescentes cenitales fríos mezclados con el resplandor verde de las pantallas. Madrugada.""", """\
La cámara avanza por el pasillo central entre las dos filas de escritorios, acercándose al
ingeniero del fondo. Él permanece completamente inmóvil. Una sola figura, a media distancia, gira
apenas la cabeza hacia las pantallas del fondo.
Cámara: dolly in continuo y sostenido, sin cortes, con una inestabilidad mínima de cámara en mano.
Entorno: el parpadeo tenue de los monitores sobre las superficies, polvo suspendido en el haz de
los fluorescentes.
Ritmo: el movimiento ya está en curso desde el primer fotograma. Avance constante. Alrededor del
segundo 5, la figura que gira la cabeza. Termina con la cámara detenida a media distancia del
ingeniero, en posición estable."""),

    Plano("S01-P04", "00:20", "00:30", "B", 10, """\
LA NAVE en el espacio, plano entero de tres cuartos, pequeña en el encuadre y desplazada al
tercio izquierdo, recortada contra MARTE que ocupa todo el fondo y está desenfocado. El panel
solar único hacia la derecha.
Luz solar dura desde la izquierda; la mitad de la nave en sombra profunda.""", """\
La nave gira muy lentamente sobre su propio eje, apenas unos grados, dejando que la luz del Sol
recorra el panel solar de un extremo al otro. No se desplaza: solo rota. Marte permanece inmóvil
y desenfocado al fondo.
Cámara: fija, sin movimiento.
Entorno: el brillo se desplaza sobre la manta térmica dorada a medida que la nave gira.
Ritmo: el giro ya está en curso desde el primer fotograma, constante y muy lento. Alrededor del
segundo 6 el panel alcanza su punto de máximo brillo. Termina en una posición estable."""),

    Plano("S02-P05", "00:55", "01:05", "B", 10, """\
LA NAVE en plano entero, de perfil, ocupando el centro izquierda del encuadre, sola contra el
vacío. Sin planetas ni referencias. El panel solar único extendido hacia arriba.
Luz solar rasante desde atrás: contraluz que recorta la silueta y deja la cara frontal en sombra.""", """\
La cámara se desplaza lateralmente pasando junto a la nave, que queda atrás y sale del encuadre
por la izquierda mientras la cámara sigue avanzando hacia el vacío. La nave no se mueve: es la
cámara la que la deja atrás.
Cámara: travelling lateral continuo hacia la derecha, velocidad constante.
Entorno: las estrellas del fondo se desplazan en paralaje, mucho más lento que la nave.
Ritmo: el movimiento ya está en curso desde el primer fotograma. La nave sale de cuadro alrededor
del segundo 6. Termina con el encuadre casi vacío y la cámara todavía en deriva suave."""),

    Plano("S03-P03", "01:15", "01:25", "B", 10, """\
LA NAVE en plano entero de tres cuartos, en el tercio izquierdo, con MARTE grande y nítido
ocupando el fondo derecho. La nave pasa cerca del limbo del planeta. Toberas apagadas, sin llama
ni escape.
Luz solar desde arriba a la derecha; la superficie de Marte rebota un tenue reflejo ocre sobre el
vientre de la nave.""", """\
La nave avanza despacio de izquierda a derecha frente al disco de Marte, sin encender motores.
Marte permanece fijo al fondo.
Cámara: arco lento alrededor de la nave, siguiéndola, revelando gradualmente el otro costado del
cuerpo y la cara oculta del panel solar.
Entorno: el reflejo ocre de Marte se desplaza sobre el vientre de la nave a medida que cambia el
ángulo.
Ritmo: el movimiento ya está en curso desde el primer fotograma. Un solo arco continuo, con el
punto de máxima revelación del costado oculto alrededor del segundo 6. Termina con la nave
centrada y estable."""),

    Plano("S04-P05", "01:55", "02:05", "J", 10, """\
Plano entero de un cohete Delta II en la plataforma de lanzamiento de noche, visto desde media
distancia y ligeramente contrapicado. El cohete apenas ha empezado a subir y todavía está a la
altura de la torre de servicio. Llama naranja intensa en la base, columna de humo blanco
abriéndose sobre la plataforma. Estructura metálica de la torre a la derecha. Un canal de agua en
primer plano refleja el naranja.
Luz: la propia llama ilumina toda la escena; el resto es noche cerrada.""", """\
El cohete asciende desde la plataforma ganando altura de forma continua, y hacia el final del
plano sale por la parte superior del encuadre. La llama se alarga bajo él. La columna de humo se
expande hacia los lados y hacia la cámara, cubriendo la base de la torre. La estructura de la
torre vibra levemente.
Cámara: tilt up lento siguiendo el ascenso, con vibración sutil de cámara en mano por la onda
sonora.
Entorno: el reflejo naranja en el agua se agita; el humo se ilumina desde dentro.
Ritmo: el ascenso ya está en curso desde el primer fotograma y acelera progresivamente, con el
momento de máxima energía alrededor del segundo 6. Termina con el cohete alto en el encuadre,
todavía en movimiento pero estable."""),

    Plano("S05-P02", "02:15", "02:25", "C", 10, """\
Plano detalle del interior de un compartimento de la nave: una rueda de reacción, un volante
metálico pesado montado en una carcasa cilíndrica de aluminio, con cableado naranja y conectores
alrededor. La rueda está quieta pero lista para girar. Paneles de aislante plateado al fondo,
tornillos y estructura visibles.
Luz: una lámpara de trabajo lateral, dura, que deja el fondo del compartimento en negro.""", """\
La rueda gira a alta velocidad dentro de su carcasa: el volante rota tan rápido que las marcas de
su superficie se difuminan en un borrón circular continuo. La carcasa y el cableado permanecen
completamente inmóviles.
Cámara: fija, encuadre cerrado.
Entorno: un reflejo de luz recorre el borde del volante en cada vuelta, produciendo un parpadeo
rápido y regular.
Ritmo: el giro ya está a plena velocidad desde el primer fotograma y se mantiene constante todo el
clip, sin arrancar ni frenar. Alrededor del segundo 6, una vibración mínima recorre la carcasa."""),

    Plano("S05-P04", "02:30", "02:40", "C", 10, """\
Plano detalle de una tobera de propulsor de control de actitud en el exterior de la nave: cono
metálico pequeño, del tamaño de un puño, montado sobre un bloque con líneas de combustible.
Alrededor, la superficie de manta térmica dorada arrugada. La tobera está apagada.
Luz solar rasante desde la izquierda que hace brillar el metal quemado del cono.""", """\
El propulsor dispara una serie de pulsos brevísimos: cinco o seis destellos secos y separados,
cada uno de una fracción de segundo, con un penacho de gas casi invisible que sale hacia la
derecha y se disipa de inmediato. Entre pulso y pulso, quietud total.
Cámara: fija, encuadre cerrado.
Entorno: en cada destello, la manta térmica dorada de alrededor se ilumina un instante.
Ritmo: el primer pulso ocurre en el primer segundo. Los siguientes están espaciados de forma
irregular, con dos seguidos alrededor del segundo 6. Termina con la tobera apagada y quieta."""),

    Plano("S06-P02", "02:55", "03:05", "B", 10, """\
Dos copias de LA NAVE superpuestas en el mismo encuadre, ambas en plano entero de tres cuartos y
ligeramente desplazadas una de otra, como una doble exposición. Una es sólida y nítida; la otra
es semitransparente y fantasmal, desplazada unos centímetros abajo y a la derecha. Fondo de campo
estelar.
Luz solar dura desde la izquierda sobre ambas.""", """\
Las dos copias se van separando lentamente: la semitransparente se desplaza hacia abajo y a la
derecha, alejándose de la sólida, hasta quedar claramente aparte al final del clip. Ambas
mantienen la misma orientación.
Cámara: fija, sin movimiento.
Entorno: el campo estelar permanece inmóvil.
Ritmo: la separación ya está en curso desde el primer fotograma, lenta y constante. Alrededor del
segundo 6 la distancia entre las dos se hace evidente. Termina con las dos naves visiblemente
distanciadas y quietas."""),

    Plano("S07-P03", "03:40", "03:50", "B", 10, """\
LA NAVE en plano entero de tres cuartos, centrada, con el panel solar único hacia la izquierda y
el Sol como fuente puntual brillante fuera de cuadro por la derecha. Sombras marcadas cruzando el
cuerpo de la nave.""", """\
La nave rota muy lentamente sobre su eje vertical mientras la luz del Sol barre el panel solar de
punta a punta. A medida que gira, el panel pasa de estar de canto a mostrar toda su superficie a
la luz, y las sombras cruzan el cuerpo.
Cámara: fija, la nave centrada.
Entorno: el brillo especular se desplaza a lo largo del panel; la manta térmica cambia de tono
según el ángulo.
Ritmo: la rotación ya está en curso desde el primer fotograma, muy lenta y constante. Alrededor
del segundo 6 el panel queda de frente al Sol y el destello es máximo. Termina con la nave
estable."""),

    Plano("S09-P02", "04:40", "04:50", "B", 10, """\
Plano espacial amplio: en el extremo izquierdo del encuadre, la Tierra pequeña y azul; en el
extremo derecho y muy lejos, LA NAVE, minúscula. Entre ambas, el vacío negro atravesando todo el
cuadro en horizontal.
Luz solar desde arriba. Composición deliberadamente vacía en el centro.""", """\
La cámara viaja en línea recta a través del vacío desde la Tierra hacia la nave, recorriendo la
distancia que las separa. La Tierra sale del encuadre por la izquierda al principio; la nave crece
muy poco al fondo, siempre lejana.
Cámara: travelling frontal continuo hacia la derecha, velocidad constante, sin rotación.
Entorno: las estrellas se desplazan en paralaje, las cercanas más rápido que las lejanas, dando
sensación de recorrer una distancia enorme.
Ritmo: el movimiento ya está en curso desde el primer fotograma. Alrededor del segundo 6 la Tierra
ya salió y solo queda vacío. Termina con la cámara todavía en tránsito, la nave apenas más grande
que al principio."""),
]


def prompt_i2v(p: Plano) -> str:
    """Con imagen semilla: solo el movimiento. El encuadre y el look los hereda."""
    return p.movimiento.strip() + "\n" + CIERRE


def prompt_t2v(p: Plano) -> str:
    """Sin imagen: hay que decirle el estilo, el espacio y recién después el movimiento."""
    partes = [ESTILO]
    if "LA NAVE" in p.escena:
        partes.append(NAVE)
    partes += ["ESCENA:\n" + p.escena.strip(), "MOVIMIENTO:\n" + p.movimiento.strip(), CIERRE]
    return "\n\n".join(partes)


def por_id(pid: str) -> Plano | None:
    return next((p for p in PLANOS if p.id == pid), None)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # consola cp1252
    print(f"{len(PLANOS)} planos · {sum(p.dur for p in PLANOS)} s de video")
    for p in PLANOS:
        print(f"  {p.id}  {p.ini}→{p.out}  cámara {p.camara}  {p.dur}s  "
              f"i2v {len(prompt_i2v(p)):4d} car · t2v {len(prompt_t2v(p)):4d} car")
