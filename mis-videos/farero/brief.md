# EL FARERO — estructura por tramos

Formato **short** · duración objetivo **60 s** (± 3) · 8 tramos

Plataformas: YouTube Shorts, TikTok, Instagram Reels · **Retención objetivo: 50 %** — por debajo de eso la plataforma no lo empuja a más audiencia · Interrupción de patrón cada **12 s** como máximo

> LEY: Estructuras_Contenido_Alta_Retencion_2026.docx. Lo que manda la distribución en 2026 es el porcentaje del video que se completa, no los likes ni los seguidores. Un clip corto con alta finalización supera sistemáticamente a uno largo con baja retención.
> 60 s es el punto de compromiso entre plataformas: YouTube Shorts pide menos de 60, TikTok premia 60-90 por tiempo de visualización, y Reels necesita menos de 90 para aparecer en Explorar. Para un formato ultracorto de alcance está `short-23`; para educativo y guardados, `short-90`.
> Retención objetivo de este tramo de duración: 50 %. Por debajo de eso la plataforma no lo empuja a más audiencia. En menos de 30 s el umbral sube a 65 % (ver `short-23`).
> TRIPLE REFUERZO: el mensaje entra por lo visual, lo auditivo y el texto en pantalla a la vez. El texto va SIEMPRE como overlay en post, nunca pedido al generador: los modelos destrozan el texto y en un gancho eso es fatal.
> INTERRUPCIÓN DE PATRÓN cada 10-12 s como máximo: cambio de ritmo, plano, luz o sonido. Sin eso el cerebro predice y deja de mirar.
> H3 no genera menos de 5,17 s por plano y el gancho necesita cortes de 1,5 a 3 s: se genera de más y se usa sólo el tramo `usa`. En PROFUNDIDAD se generaron 74,8 s para usar 60.
> Ninguna voz sale de H3: la voz en off va encima, de ElevenLabs, y por eso queda idéntica en todas las líneas.
> Las caras humanas en primer plano son lo peor que le sale al modelo: taparlas o esquivarlas. Y elegir un entorno que perdone —agua turbia, humo, niebla, poca luz— donde los artefactos desaparecen.

## HOOK · Gancho · 0–3 s

La ventana crítica. Si el espectador no percibe el valor de inmediato, desliza. Se abre una brecha de información: algo que no se entiende de golpe o que no debería estar ahí, reforzado a la vez en imagen, sonido y texto.

Exige:
- El primer fotograma funciona como miniatura: legible en 0,3 s, un solo sujeto, contraste alto
- TRIPLE REFUERZO: lo visual, lo auditivo y el texto en pantalla dicen lo mismo en estos 3 s
- El texto en pantalla ANTEPONE EL RESULTADO CONCRETO, no la promesa genérica: «a ochenta metros había luz encendida», no «mirá lo que encontré»
- Movimiento fuerte desde el fotograma 1: nada de fundido, nada de establecer
- Un solo plano, corte de 1,5 a 3 s
- La voz en off arranca antes del segundo 1
- El texto va como overlay en post — NO se le pide al generador

_corte 1.5–3.0 s · tamaños PP/PD · **rompe el patrón** · audio: Un sonido concreto y cercano, no un ambiente. Lo que se oye en el primer segundo es el segundo gancho._

**Texto en pantalla** (overlay en post, NUNCA pedido al generador): El resultado concreto, en menos de 8 palabras. Es la mitad del gancho.

Para el fotograma (se inyecta en el prompt): `This is the very first frame of a vertical short-form video and must read instantly as a thumbnail: one clear subject, strong contrast, something visibly wrong or surprising already present in the frame. Leave the upper third relatively clear: an on-screen text overlay goes there in post.`

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| S01 | 0.0–3.0 | 3.0 s | PD | HOOK. La lámpara vieja, débil, parpadeando: cuarenta años y se está muriendo. |

## PROMESA · Promesa · 3–5.5 s

Interrumpido el scroll, se promete un resultado concreto. Decir en una imagen dónde estamos y qué está en juego, sin explicar. El corte rápido mantiene el pulso alto.

Exige:
- Cambio de tamaño de plano respecto del gancho: si fue cerrado, acá abierto
- Corte de 2 a 3,5 s — todavía más rápido que el resto del video
- La voz plantea la pregunta que el video va a responder, en concreto y no en genérico

_corte 2.0–3.5 s · tamaños PG/PGE/PM_

Para el fotograma (se inyecta en el prompt): `Establishing frame: the whole space and the scale of the subject within it are readable at a glance.`

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| S02 | 3.0–5.5 | 2.5 s | PGE | PROMESA. El faro entero en la tormenta y el farero diminuto entrando con la lámpara nueva. |

## PROGRESO · Barra de progreso · 5.5–14 s

Darle al ojo algo que seguir: un número que sube, un recorrido, una luz que se acerca. El espectador tiene que sentir que avanza. Y justo antes del hallazgo, un plano de tensión por ausencia: no pasa nada, y eso es lo que tensa.

Exige:
- 2 planos, cortes de 3 a 5 s
- Uno de los dos da una medida del avance (contador, profundidad, distancia)
- El otro es de tensión por ausencia: se busca y no se encuentra
- Cada plano cambia tamaño o ángulo respecto del anterior
- Los números que cambian van como gráfico en post, NO pedidos al modelo

_corte 3.0–5.0 s_

**Texto en pantalla** (overlay en post, NUNCA pedido al generador): El contador o la medida del avance, si el concepto lo tiene.

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| S03 | 5.5–9.7 | 4.2 s | PG | BARRA DE PROGRESO. La escalera caracol desde arriba: el ojo sigue la subida, el contador va en post. |
| S04 | 9.7–14.0 | 4.3 s | PD | TENSIÓN. Se le apaga la linterna a mitad de subida: cambio de régimen de luz y sonido. |

## REVELACION · Escalera de revelación · 14–32 s

De la nada a algo, en tres peldaños: aparece una forma, se revela su escala, y recién en el tercero se entiende qué es. Cada peldaño es una micro-tensión que se resuelve y abre la siguiente.

Exige:
- 3 planos, cortes de 4,5 a 7 s
- Un plano de escala: el sujeto diminuto contra algo enorme. El formato vertical juega a favor
- La revelación grande cae al final del tramo, no antes
- En el plano de la revelación, describir el objeto sin ambigüedad y decir qué NO tiene que parecer
- Al menos un cambio de ritmo dentro del tramo: son 18 s y el patrón se vuelve predecible

_corte 4.5–7.0 s · **rompe el patrón**_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| S05 | 14.0–19.5 | 5.5 s | PG | ESCALERA 1. Llega arriba: la sala y la lámpara casi muerta pulsando débil. |
| S06 | 19.5–25.5 | 6.0 s | PGE | ESCALERA 2 · ESCALA. La cúpula chiquita contra el mar negro enorme: lo que depende de esa lucecita. |
| S07 | 25.5–32.0 | 6.5 s | PD | ESCALERA 3. El cambio: sale la vieja humeando de calor, entra la nueva, pesada, justa. |

## GIRO · Interrupción de patrón · 32–38 s

Justo a la mitad, donde cae la retención: un cambio que rompe el patrón. Algo que no debería poder pasar.

Exige:
- Un solo plano, contundente
- Cambio visual fuerte: entra una luz de otro color, o una fuente de luz nueva
- El audio cambia con la imagen: aparece o desaparece un sonido

_corte 4.0–7.0 s · **rompe el patrón**_

**Texto en pantalla** (overlay en post, NUNCA pedido al generador): Opcional: si el giro necesita una palabra para leerse, va acá y son dos o tres.

Para el fotograma (se inyecta en el prompt): `A strong visual break from everything before it: a new colour of light, a new light source or an impossible detail, clearly visible in the frame.`

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| S08 | 32.0–38.1 | 6.1 s | PG | GIRO. La enciende y... NADA. La sala queda negra: desaparece la luz y desaparece el zumbido. |

## CONTACTO · Segunda escalada · 38–49 s

El sujeto interactúa con lo que encontró y sube la apuesta. Termina en el detalle imposible: el dato visual que vuelve inexplicable todo lo anterior.

Exige:
- 2 planos, cortes de 4 a 7 s
- El primero es contacto físico: una mano, un golpe, algo que se toca
- El segundo muestra el detalle imposible, y se sostiene lo suficiente para que se lea

_corte 4.0–7.0 s · **rompe el patrón**_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| S09 | 38.1–43.3 | 5.2 s | PD | CONTACTO. A ciegas, a puro tacto: la rosca medio punto más, iluminado sólo por los rayos. |
| S10 | 43.3–49.3 | 6.0 s | PP | EL DETALLE, sostenido: el filamento despierta — de un hilito naranja a un resplandor blanco. |

## PAGO · Pago · 49–54.5 s

La recompensa que se prometió en el segundo 3. La voz suelta el dato que reordena todo lo visto, y la imagen vuelve al sujeto para que se vea la reacción.

Exige:
- Volver al tamaño de plano del gancho: cierra el círculo visual
- Corte de 4 a 6,5 s
- La revelación la dice la voz; la imagen la sostiene, no la ilustra
- Entrega lo que el texto del gancho prometió, literalmente

_corte 4.0–6.5 s · tamaños PP/PD_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| S11 | 49.3–54.9 | 5.6 s | PD | EL PAGO. Vuelta al encuadre del gancho: la misma lámpara, ahora a plena potencia, y el haz arranca a girar. |

## BUCLE · Cierre en bucle · 54.5–60 s

No cerrar la historia: abrir una más grande en el último segundo. El final conecta con el principio, y el replay es de las señales más fuertes que hay. Y si además deja una pregunta que da ganas de contestar, el comentario largo pesa hasta diez veces más que un emoji.

Exige:
- Corte de 3 a 6 s
- Termina en negro, o en una imagen que empalma con el fotograma 1
- Sin texto de cierre, sin llamado a la acción hablado
- La última línea de voz deja la pregunta abierta, no la responde
- La pregunta tiene que ser contestable en una frase: es lo que dispara el comentario

_corte 3.0–6.0 s · **rompe el patrón**_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| S12 | 54.9–60.0 | 5.1 s | PGE | CIERRE EN BUCLE. El haz barre el mar de tormenta y a lo lejos pasan las lucecitas de un barco. Corte a negro. |

## Verificación

- Sin avisos: cada tramo tiene su plano y ningún corte se pasa.
