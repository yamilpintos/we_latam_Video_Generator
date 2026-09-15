# Análisis del canal de referencia @jcfdlw (TikTok)

30 de agosto de 2026. Muestra: 9 videos descargados (los 1080p sin audio en
esta carpeta, los `.full` con audio para transcribir), 54 fotogramas, 2
transcripciones completas (~20.000 caracteres) y los metadatos de los últimos
20 videos del canal. Las transcripciones están en los `.txt`.

## Qué es el canal

**Recaps melodramáticos narrados en castellano** sobre recortes de dramas
chinos (y algunas escenas claramente generadas con IA, como el pozo de
serpientes del más visto). No es un canal de shorts: es **historia larga en
TikTok**.

| video | dura | vistas |
|---|---|---|
| el del pozo de serpientes | 4:43 | 247.500 |
| (el corto del muestreo) | 2:45 | 239.400 |
| el del búnker / ola de frío | 6:48 | 128.900 |
| promedio de los 20 últimos | **5:12** | ~68.000 |

## Los siete rasgos que definen el formato

1. **Duración 3-8 minutos.** Maximizan tiempo de visualización total, no
   porcentaje de finalización. Es exactamente nuestro formato `largo`, que
   está implementado y nunca corrió.

2. **Historias de emoción primaria**: familia en peligro, injusticia y
   revancha, catástrofe inminente, pobreza/riqueza. Protagonista en primera
   persona, con nombre propio. Nada de misterio atmosférico: los stakes son
   "mi familia se congela", no "algo no cuadra".

3. **La voz en off no para nunca.** Medido sobre las transcripciones: **25-27
   caracteres por segundo de video** — el doble y medio de nuestra densidad.
   Voz TTS rápida y enérgica, probablemente acelerada, que además **actúa los
   diálogos de todos los personajes** dentro de la narración (padre, hija,
   los siete "padrinos"). Narración y diálogo trenzados sin costura.

4. **Hiperespecificidad numérica constante**: toneladas de cemento, 300.000 de
   inversiones, 1,2 millones, fideos de 3 yuanes. Los números concretos hacen
   creíble el melodrama. (Esto ya lo teníamos como principio en el gancho —
   ellos lo usan TODO el tiempo.)

5. **Un micro-cliffhanger cada 15-30 segundos.** No hay "giro al medio": hay
   una cadena de problema → acción → consecuencia → problema nuevo. El gancho
   es in-media-res y absurdo en la primera frase (una gallina muerta que
   termina volteando el despacho del director; un búnker apocalíptico de cien
   plantas en el patio).

6. **Subtítulos quemados frase por frase, siempre**, centrados en el tercio
   inferior-medio. Son parte del diseño, no un accesorio.

7. **La imagen ilustra, la historia carga.** Mezclan recortes de dramas
   reales con escenas IA sin preocuparse por la consistencia perfecta entre
   planos. Caras en primer plano todo el tiempo, con actuación emocional.

## Qué no estamos haciendo nosotros

| ellos | nosotros hoy | qué cambiar |
|---|---|---|
| 3-8 min | shorts de 60 s | estrenar el formato `largo` (E0.9) con una historia de este género |
| personas + emoción primaria | conceptos atmosféricos (base polar, dron, faro) | historias de familia/injusticia/catástrofe en primera persona |
| VO continua a ~25 cps con diálogos actuados | 12 líneas con aire en 60 s (~10 cps) | guion río: narración + diálogos trenzados, voz rápida y enérgica (o leve aceleración), sin silencios |
| cliffhanger cada 15-30 s | un giro en la mitad | estructura serial de micro-tensiones |
| subs quemados siempre | SRT como entregable aparte | quemar subtítulos en el máster (`montaje.srt` ya lo genera; falta quemarlo) |
| caras y actuación | regla 22: caras tapadas | probar caras de H3 en PM/PG con estética "drama filmado"; la regla 22 nació para el fotorrealismo documental, acá el estándar visual es más blando |

## Tensiones con nuestras reglas (para decidir, no para borrar)

- **Regla 22 (caras)**: este género vive de caras. H3 rinde mejor en plano
  medio que en primer plano; habría que probar una tanda de caras actuando
  antes de comprometer un video entero.
- **Regla 9 (una voz por plano)**: acá la voz en off actúa todos los diálogos,
  así que no aplica — es una sola pista de ElevenLabs con cambios de
  entonación, o multivoz montada.
- **La ley de retención de 8 tramos** es de shorts; este formato pide la
  estructura serial de `largo` con re-enganche cada 60-90 s (ya prevista en
  `estructuras/largo.json`) pero con cliffhangers más densos (cada 20-30 s).

## El costo de entrar a este formato

Un video de 4 minutos con el pipeline actual: ~240 s × 0,74 min/s ≈ 3 h de
GPU ≈ 45 min de pared en 4×5090 ≈ **$1,3-2 de GPU** + ~45 planos de imágenes
(~$3 en calidad media de OpenAI). Total ~$5 por video de 4 minutos. El género
además perdona la consistencia visual, que es nuestra parte más cara de
conseguir.

## Índice de la muestra transcripta (9 videos, 31/8/2026)

| video (id) | dura | caracteres | frases | cps | vistas |
|---|---|---|---|---|---|
| 7678773607954173215 | 4:43 | 5762 | 149 | 20.4 | 247.500 |
| 7677638328505683231 | 6:48 | 9078 | 116 | 22.2 | 128.900 |
| 7678774704458485022 | 5:16 | 6656 | 197 | 21.0 | 89.500 |
| 7677270095994932510 | 6:28 | 8197 | 217 | 21.1 | 85.400 |
| 7676911684388211998 | 6:02 | 7562 | 185 | 20.9 | 82.300 |
| 7679139954408181023 | 7:02 | 8954 | 193 | 21.2 | 56.900 |
| 7678030150944001310 | 3:01 | 3830 | 92 | 21.1 | 48.300 |
| 7677271578907790622 | 6:37 | 8543 | 202 | 21.5 | 30.700 |
| 7679523495306448159 | 8:37 | 10816 | 266 | 20.9 | 18.100 |

Los `.txt` con marcas de tiempo por frase y los `.mp4` (1080p limpios y
`.full` con audio) están en esta carpeta. La densidad medida sobre la transcripción es ~21 cps constante en los 9
(la estimación inicial de 25-27 usaba las duraciones de metadata, que en
varios videos difieren del archivo con audio). Sigue siendo ~1,5-2x la
nuestra: la conclusión del formato no cambia.
