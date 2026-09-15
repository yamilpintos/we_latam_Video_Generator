# LLUVIA EN LA VENTANA — notas de la corrida

10 de septiembre de 2026. Primer video ambiente en bucle del proyecto: 16:9,
sin voz, sin texto, para una pista lo-fi. Diseño discutido y cerrado con el
usuario antes de generar nada (ver `CONTINUAR-LOFI.md` en la raíz).

## Decisiones

| punto | decisión | por qué |
|---|---|---|
| formato | `largo`, 1344×768 → máster 1920×1080 | YouTube de escritorio/tele; mismo costo que vertical |
| escena | el cuarto de estudio con la ventana de lluvia, sin persona | la persona de espaldas es el fallo caro documentado (la nuca que se da vuelta) |
| loop | 12 planos sueltos de 5,17 s; el corte P12→P01 es un corte más | H3 no acepta fotograma final; la cadena deriva y ocupa una sola placa; el ping-pong invierte la lluvia |
| estructura | `estructuras/loop.json` (nueva): un tramo, corte 5,0-5,3, sin interrupciones ni texto | `largo` es narrativa de 300 s y no valida un cuarto quieto |
| máster | `bucle.py` propio | `montaje.mezclar` exige voz y funde la música al entrar |
| música | pista del usuario hecha en ElevenLabs; segmento de la duración exacta cerrado con un cruce de 2 s | ver el docstring de `bucle.py` |

## Lo que enseñaron los dibujos (tres tandas, ~$1,10)

1. **nano banana en 16:9 con estilo «film» pinta letterbox**: 10 de 14 salieron
   con barras negras de 88 px arriba y abajo. La locación madre salió así y los
   fotogramas la copiaron como referencia. Arreglo: `barras.py` las detecta y
   las recorta; al estilo se le agrega «fills the ENTIRE 16:9 canvas… no
   letterbox»; con eso la segunda tanda salió 14/14 limpia.
2. **Con la locación como referencia, nano banana reproduce SU encuadre** e
   ignora el ángulo pedido: tres generales «de costado / desde el piso / hacia
   el alféizar» salieron los tres de frente, y uno inventó un segundo tocadiscos.
   Arreglo: para un ángulo distinto, `loc: null` y `refs: []` (sin imagen de
   locación) describiendo el cuarto en el texto; el estilo sostiene la paleta.
3. **La escala de `PG` habla de «figures… normal-sized people»** aunque no haya
   nadie. No metió gente esta vez porque `ve` lo dice tres veces; queda como
   riesgo conocido para escenas vacías.
4. Detalles que funcionan a la primera: lluvia en el vidrio, taza con vapor,
   vinilo, plantas, escritorio desde arriba, auriculares, sillón, piso con la
   luz de la ventana. Lo que falla: pedir el mismo ambiente desde otro punto de
   vista con la referencia puesta.

## Estado

- [x] `proyecto.json` → `construir` sin avisos (12 planos, 62,0 s)
- [x] madre + 12 fotogramas revisados uno por uno, 0 barras
- [x] `lofi-lluvia-para-vast.zip` (20,8 MB)
- [ ] pista de música del usuario (falta la ruta)
- [x] Vast: instancia 50515495 (4×5090 Taiwán, $1,97/h); 12/12 en 4 tandas (12 + 7 + 4 + 1)
- [x] `bucle.py` sin música: «LLUVIA EN LA VENTANA - loop.mp4» 58,0 s, empalme verificado en «loop x3»
- [ ] `bucle.py --musica <pista> --repite 10` cuando el usuario ponga la pista
- [ ] gasto real

## Lo que enseñaron los clips (instancia 50515495, Taiwán, $1,97/h)

Primera tanda, 12/12 sin fallos de máquina, ~4,8 min por clip, 0 reintentos.
Control con tiras de 10 cuadros (`fps=2`), no sólo entrada/medio/salida:

| clip | tanda 1 | qué pasó | arreglo |
|---|---|---|---|
| P01 | ✗ | la ventana pasa de noche a día 3 s | positivo + semilla → ✗ entra una silla sola deslizándose → dibujar la silla |
| P02 | ✓ | | |
| P03 | ✗ | hombre y familia en la ventana, cactus, fuego | positivo + semilla → ✓ |
| P04 | ✓ | | |
| P05 | ✓ | | |
| P06 | ✗ | un viejo en la ventana, vapor en nubes | positivo + semilla → ✓ |
| P07 | ✓ | | |
| P08 | ✗ | cactus y fuego en el alféizar | ✗ abandona el encuadre, letras en la etiqueta → redibujar sin ventana |
| P09 | ✗ | abandona el dibujo del piso en el cuadro 1 | reemplazar por segundo plano del gato → ✓ |
| P10 | ✓ | | |
| P11 | ✗ | una familia entra al cuarto | positivo → ✗ entra una chica y se sienta → redibujar como detalle del cuaderno |
| P12 | ✗ | manos sosteniendo los auriculares, mujer en la ventana | positivo → ✗ la lluvia chorrea adentro → redibujar sin ventana |

**Las tres causas**, en orden de peso:
1. Los bloques negativos fijos del prompt (`NO_INVENTES`, `HUMO`, `IDIOMA`, la
   escala con «figures / people / a pair of hands») inducen lo que prohíben en
   una escena donde nada de eso es natural. → `negativos: false` (nuevo en el
   módulo) y audios en positivo.
2. Encuadres con espacio de cuarto + silla vacía + ventana: H3 sienta a alguien.
   Y ventana pegada a los objetos: la lluvia entra. → primeros planos de objeto
   sin ventana o con la ventana muy fuera de foco.
3. Dibujos abstractos (el piso con la luz): los abandona desde el cuadro 1.

## Tandas 3 y 4, y el máster

- Tanda 3 (P01 con silla dibujada, P08 macro, P11 cuaderno, P12 auriculares sin
  ventana): pasan P01, P11 y P12. P08 vuelve a irse a un macro con letras.
- Tanda 4 (P08 como macro de surcos y púa, sin etiqueta): los primeros 3,0 s
  perfectos, después la luz vira a azul. Se usa `recortes.json` → P08 [0, 3.0].
- **Máster**: 12 planos, 58,0 s, 1920×1080, corte P12→P01 limpio (mirado en
  `qc/final_check.png`). loudnorm en dos pasadas: −16,0 LUFS sólo con el
  ambiente (limitado por el pico); con la música encima va a −14.
- Métricas 16:9: 0,91 min de GPU por segundo (vertical: 0,69-0,71). COSTOS §14.
- Gasto real de máquina a los 82 min: **$2,70** (~$0,40 habría sido una corrida
  limpia). Imágenes: ~$1,50 (39 generaciones).
