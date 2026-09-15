# @nothingwasfilmed — el reel meta de 20 s

2 de septiembre de 2026. Referencia candidata, **todavía no producida**.

Fuente: `Analisis_Reel_y_Prompt_Maestro.pdf` (despiece del reel `DcrhA35sS0F`,
con los 42 fotogramas de muestreo en `mapa-42-fotogramas.png`). El PDF trae
además un **prompt maestro parametrizado** para producir uno original con las
mismas mecánicas — está en sus páginas 4 y 5 y no se transcribe acá para no
tener dos copias que se desincronicen.

## Los números

| | |
|---|---|
| duración | **20,73 s** (20,40 de imagen + 0,33 de negro final) |
| formato | vertical 9:16, 1080×1920, 30 fps, **a sangre** (sin barras) |
| planos | **9** |
| cortes | 1,30 · 3,13 · 4,80 · 7,60 · 10,30 · 13,20 · 14,93 · 17,57 · 20,40 |
| **corte medio** | **2,30 s** (mín 1,30 · máx 2,90) |
| diálogo | **15 líneas en 20 s**, con boca en cámara |
| subtítulos | ninguno |
| rendimiento | 64.233 me gusta, 5.132 comentarios |

## Los nueve planos

| tiempo | qué se ve | para qué |
|---|---|---|
| 0,00–1,30 | joven gritando bajo contraluz duro | golpe emocional en el fotograma 1 |
| 1,30–3,13 | mujer en cocina oscura mira el teléfono | contraste pánico/calma |
| 3,13–4,80 | inserto sobre el hombro del teléfono | prueba visual |
| 4,80–7,60 | primerísimo primer plano de ella | «ella ve algo que vos no» |
| 7,60–10,30 | plano medio, intercambio corto | micro-respuesta que abre otra duda |
| 10,30–13,20 | vuelta al primerísimo | autoridad antes de la revelación |
| 13,20–14,93 | inserto de claqueta golpeando la mesa | pattern interrupt · empieza el giro |
| 14,93–17,57 | plano general: aparece el equipo al fondo | se rompe la ficción |
| 17,57–20,40 | primer plano frontal, mirada a cámara | remate y puente al CTA |
| 20,40–20,73 | negro | golpe final y loop limpio |

## Lo que el PDF no subraya y es lo más importante

**La claqueta del plano 7 dice «NOTHING WAS FILMED»**, que es el nombre de la
cuenta. El «giro meta» no es un recurso publicitario genérico: es la firma de
**una cuenta de video con IA cuyo producto es la IA misma**. El remate del reel
es literalmente «nada de esto se filmó».

Para nosotros eso no es un truco prestado: es cierto. Es el único de los
formatos analizados donde **ser IA es la ventaja y no algo a disimular**.

## Las diez mecánicas, tal como las lista el PDF

1. No hay introducción: el conflicto empezó antes del fotograma 1.
2. Doble gancho: «¿qué peligro es este?» y a los 3 s «¿por qué ella no cree lo
   evidente?».
3. Información incompleta dosificada: cada respuesta produce una pregunta más
   precisa.
4. Contraste emocional: víctima desesperada contra protagonista casi inmóvil.
5. Cambio de escala en cada corte.
6. Diálogo comprimido: frases de 2 a 8 palabras, ningún parlamento explicativo.
7. Prueba concreta: no afirma que algo es falso, **señala un detalle
   observable**.
8. Giro meta: la historia se vuelve demostración de lo que se vende.
9. Autoridad dramatizada: resuelve el problema **antes** de explicar por qué
   sabe.
10. CTA fuera del cuerpo: el reel da curiosidad, el texto del posteo la cobra.

Y su condición de fracaso, que es la parte más útil: **si el producto aparece
antes del segundo 13, si el experto explica antes de demostrar, o si el primer
segundo necesita contexto, se pierde la mecánica.**

## Qué costaría hacerlo con nuestro pipeline

Los nueve cortes están todos por debajo del piso de H3 (5,17 s), así que se
genera de más y se recorta:

| | |
|---|---|
| generado | 9 × 5,17 = **46,5 s** para usar 20,7 |
| GPU | ~33 min → **~8 min de pared** en 4×5090 |
| imágenes | 9 fotogramas + ~4 madre |
| **total** | **menos de $1** — el video más barato que podríamos hacer |

## Los cuatro choques con lo que tenemos medido

1. **15 líneas de diálogo con boca en cámara en 20 s.** Es nuestra capacidad
   menos probada. CONTRAMANO tenía 5 diálogos y necesitó **tres pasadas** de
   isocronía. El propio PDF pone «labios desincronizados» entre sus negativos:
   sabe dónde se rompe.
2. **Pide texto dentro de la imagen** («claqueta con [MARCA] pequeño y
   legible»). Los generadores destrozan el texto: va como overlay en post,
   siempre. La claqueta se compone, no se pide.
3. **Dice «no usar subtítulos incrustados»**, y contradice nuestra ley de
   retención y lo medido en @jcfdlw, donde los subs quemados son parte del
   diseño. En un formato con diálogo sincronizado puede tener sentido, pero es
   una **excepción a declarar**, no algo a heredar sin pensar.
4. **«Continuidad estricta de rostro, ropa, cocina y miradas en los nueve
   planos»** es lo más caro que hacemos, y donde se van los reintentos.

Y un detalle de método: el único dato de rendimiento son **los me gusta**. Los
me gusta no son retención, y nuestra ley mide finalización.

## Qué falta para poder decidir

Este formato depende entero de una pregunta que todavía no está contestada:
**¿cómo rinde H3 con caras actuando y hablando?** La réplica de @jcfdlw
(79 planos con dos personajes en primer plano) la contesta sin costo extra,
porque ya está generándose. Si esas caras salen bien, `reel-20` es el próximo
video y sale por menos de un dólar. Si salen mal, este formato no es viable
todavía y el intento se ahorra.

Ver [`../FORMATOS.md`](../FORMATOS.md) para la comparación con los otros
formatos medidos.
