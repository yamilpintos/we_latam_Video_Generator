# Aladino y la lámpara maravillosa — estructura por tramos

Formato **largo** · duración objetivo **309 s** (± 20) · 9 tramos

Plataformas: YouTube · **Retención objetivo: 50 %** — por debajo de eso la plataforma no lo empuja a más audiencia · Interrupción de patrón cada **75 s** como máximo

> LEY: Estructuras_Contenido_Alta_Retención_2026.docx, sección 2.1. La caída más pronunciada de la curva ocurre en los primeros 30 s: el gancho decide si YouTube recomienda el video o no.
> Retención saludable por duración: 1-5 min -> 70-85 % (por debajo de 55 % hay un problema); 5-15 min -> 40-60 %, con 50 % en un video de 10 min como sólido; 15-30 min -> más de 40 % ya indica muy buena estructura. `retención_objetivo` de esta estructura es 50 %, que corresponde al rango 5-15 min.
> YouTube evalúa el TIEMPO DE VISUALIZACIÓN ABSOLUTO, no solo el porcentaje: un video de 10 min visto al 70 % puede superar a uno de 2 min visto entero. La duración se elige por la profundidad del tema, no por llegar a un número.
> LOOPS DE CURIOSIDAD ABIERTOS: anunciar algo que se muestra más adelante y cumplirlo. Es la técnica de mayor impacto documentado para el formato largo, y el módulo la chequea: cada loop que se abre tiene que cerrarse.
> RE-ENGANCHE cada 60-90 s: una revelación, una pregunta nueva o una imagen inesperada. Sin eso la curva cae parejo y no hay donde agarrarse.
> ELIMINAR LA FRICCIÓN INICIAL: nada de presentarse, agradecer ni de introducciones lentas. Se abre con el momento más interesante o con la conclusión contraintuitiva que se va a demostrar.
> Los tramos en fracción (`desde_pct`) se estiran solos: la misma estructura sirve para 5 y para 8 minutos (`Estructura.con_duración(480)`).
> H3 genera lo que nace y muere dentro del plano; ElevenLabs, todo lo que cruza el corte.
> Una sola voz por plano y como mucho doce palabras. El contraplano es otro plano.
> El tamaño de plano va en el dibujo Y en el prompt; y no se corta entre dos planos del mismo tamaño, locación y reparto.

## APERTURA · Apertura fría · 0–15.5 s

La imagen más fuerte del video, adelantada y sin contexto. NO presentarse, NO agradecer, NO explicar de que va: se abre con el momento más interesante o con la conclusión contraintuitiva que se va a demostrar. La caída más pronunciada de la curva esta en estos primeros 30 s.

Exige:
- Plano general o detalle, nunca un plano medio neutro
- Acción o imagen, no narración explicativa
- Corta antes del segundo 15
- Cero fricción: ni intro, ni saludo, ni logo, ni 'en el video de hoy'
- Abre un loop de curiosidad que el video promete cerrar

_corte 5.0–10.2 s · tamaños PGE/PG/PD · **rompe el patrón**_

Para el fotograma (se inyecta en el prompt): `The single strongest image of the whole film: high contrast, one readable subject, something happening that raises a question.`

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| P01 | 0.0–10.1 | 10.1 s | PG |  |
| P02 | 10.1–16.0 | 5.9 s | PM |  |

## PLANTEO · Planteo · 15.5–61.8 s

Quién, dónde, qué quiere y qué se lo impide. El protagonista en su mundo, en una acción que lo defina.

Exige:
- Cada personaje entra con un plano que lo presenta entero (PA o PG) antes de sus primeros planos
- Una locación por escena
- Establecer la regla del mundo que después se rompe
- Se declara que va a entregar el video, en concreto y no en genérico

_corte 5.0–10.2 s_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| P03 | 16.0–21.2 | 5.2 s | PD |  |
| P04 | 21.2–29.2 | 8.0 s | PG |  |
| P05 | 29.2–36.5 | 7.3 s | PM |  |
| P06 | 36.5–43.8 | 7.3 s | PG |  |
| P07 | 43.8–49.6 | 5.9 s | PP |  |
| P08 | 49.6–58.3 | 8.7 s | PM |  |
| P09 | 58.3–68.5 | 10.1 s | PGE |  |

## DETONANTE · Detonante · 61.8–92.7 s

El hecho que saca al protagonista de su rutina. Es una escena, no un plano, y termina en una decisión.

Exige:
- Cambio de locación o de luz respecto del planteo
- Diálogo: una sola voz por plano
- Termina en una decisión visible
- Re-enganche: acá cae la primera revelación o pregunta nueva

_corte 5.0–12.2 s · **rompe el patrón**_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| P10 | 68.5–74.3 | 5.9 s | PA |  |
| P11 | 74.3–80.2 | 5.9 s | PP |  |
| P12 | 80.2–88.2 | 8.0 s | PG |  |
| P13 | 88.2–95.5 | 7.3 s | PM |  |

## DESARROLLO · Desarrollo con re-enganches · 92.7–154.6 s

Escalada. Cada 60-90 s un elemento nuevo que cambia lo que el espectador cree que está viendo.

Exige:
- Un re-enganche cada 60-90 s: una revelación, una pregunta nueva o una imagen inesperada
- No más de dos planos seguidos del mismo tamaño
- Duración media de plano entre 7 y 9 s
- Un loop de curiosidad abierto que se cierra más adelante, anunciado explícitamente

_corte 5.0–15.1 s · **rompe el patrón**_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| P14 | 95.5–105.6 | 10.1 s | PG |  |
| P15 | 105.6–112.9 | 7.3 s | PM |  |
| P16 | 112.9–118.8 | 5.9 s | PD |  |
| P17 | 118.8–124.0 | 5.2 s | PP |  |
| P18 | 124.0–131.3 | 7.3 s | PG |  |
| P19 | 131.3–138.5 | 7.3 s | PP |  |
| P20 | 138.5–145.8 | 7.3 s | PP |  |
| P21 | 145.8–153.8 | 8.0 s | PG |  |
| P22 | 153.8–161.8 | 8.0 s | PM |  |

## PUNTO_MEDIO · Punto medio · 154.6–179.3 s

Giro: lo que parecía una cosa es otra. Cambia la meta o cambia el enemigo.

Exige:
- Una escena entera dedicada al giro
- Un plano de reacción (PP) del protagonista
- El audio marca el cambio: entra o se corta un ambiente
- Es el re-enganche más fuerte del video: va a la mitad exacta, donde la curva se aplana o cae

_corte 5.0–12.2 s · **rompe el patrón**_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| P23 | 161.8–167.0 | 5.2 s | PD |  |
| P24 | 167.0–175.0 | 8.0 s | PG |  |
| P25 | 175.0–183.7 | 8.7 s | PG |  |

## COMPLICACION · Complicación · 179.3–231.8 s

Todo se pone peor y el antagonista toma la delantera. Ritmo más rápido: planos más cortos que en el desarrollo.

Exige:
- Duración media de plano menor que en el desarrollo
- Un plano detalle (PD) que después paga en el clímax
- Ritmo más rápido: los cortes se acortan respecto del desarrollo

_corte 5.0–10.2 s · **rompe el patrón**_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| P26 | 183.7–191.0 | 7.3 s | PP |  |
| P27 | 191.0–201.1 | 10.1 s | PGE |  |
| P28 | 201.1–208.4 | 7.3 s | PA |  |
| P29 | 208.4–213.6 | 5.2 s | PP |  |
| P30 | 213.6–221.6 | 8.0 s | PG |  |
| P31 | 221.6–227.5 | 5.9 s | PM |  |
| P32 | 227.5–234.8 | 7.3 s | PP |  |

## CLIMAX · Clímax · 231.8–278.2 s

El enfrentamiento. La imagen de la apertura fría vuelve, ahora con contexto.

Exige:
- Reencuadrar la imagen de la apertura
- Los planos más cortos del video
- Diálogo mínimo: una línea que decide
- Se cierran todos los loops abiertos que queden

_corte 5.0–8.8 s · **rompe el patrón**_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| P33 | 234.8–242.0 | 7.3 s | PP |  |
| P34 | 242.0–250.0 | 8.0 s | PG |  |
| P35 | 250.0–257.3 | 7.3 s | PM |  |
| P36 | 257.3–265.3 | 8.0 s | PA |  |
| P37 | 265.3–271.2 | 5.9 s | PD |  |
| P38 | 271.2–278.5 | 7.3 s | PG |  |

## RESOLUCION · Resolución · 278.2–299.8 s

Qué quedó distinto. Un plano largo y quieto después de la tormenta.

Exige:
- Planos largos, de 8 a 15 s
- Volver a una locación del planteo, cambiada

_corte 7.9–15.1 s_

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| P39 | 278.5–286.5 | 8.0 s | PG |  |
| P40 | 286.5–293.8 | 7.3 s | PP |  |
| P41 | 293.8–299.0 | 5.2 s | PD |  |
| P42 | 299.0–309.1 | 10.1 s | PG |  |

## SALIDA · Salida · 299.8–309.1 s

Última imagen: una pregunta abierta o el eco de la primera. Es donde YouTube pone la pantalla final: dejar aire, sin diálogo.

Exige:
- Un solo plano
- Sin diálogo
- Deja 8-10 s de aire para la pantalla final
- Adelantar lo que viene después genera expectativa y mejora la retención ENTRE videos, no solo dentro de uno

_corte 7.9–15.1 s_

**Sin planos.**

## Verificación

- ⚠ P02 es PM y el tramo APERTURA sugiere PGE/PG/PD
- ⚠ P40 (RESOLUCION) corta a 7.3 s; el tramo pide al menos 7.9
- ⚠ P41 (RESOLUCION) corta a 5.2 s; el tramo pide al menos 7.9
- ⚠ el tramo SALIDA (299.8-309.1 s) tiene 0 plano(s) y pide al menos 1
