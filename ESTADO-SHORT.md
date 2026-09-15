# Estado · Short vertical

Actualizado: 25 de agosto de 2026.

Stack **MiniMax H3**: el modelo genera video y audio a la vez, en una GPU alquilada por
hora. El audio está sincronizado **dentro de cada clip**, no entre clips, y no sostiene una
voz por personaje: por eso toda la voz va de ElevenLabs encima. El largo usa ahora el mismo
generador — ver [ESTADO-LARGO.md](ESTADO-LARGO.md).

---

## Qué está hecho

**PROFUNDIDAD** — `Proyecto_Short/PROFUNDIDAD_60s.mp4` · 768×1344 vertical (9:16) · 24 fps
· **60,02 s** · audio estéreo. **Terminado.**

Un buzo desciende y encuentra en el fondo algo que no debería estar ahí.

| Pieza | Estado |
|---|---|
| Concepto y guion, 12 planos | producido |
| 12 primeros fotogramas (storyboard) | producidos, en `assets/` |
| 12 clips generados con H3 | producidos |
| Voz en off, 8 líneas, ElevenLabs | producida |
| Montaje con recortes al décimo | producido |

---

## Por qué este concepto y no otro

Tres decisiones, y dos son técnicas antes que creativas. Vale la pena conservarlas porque
son generalizables a cualquier short con este stack:

1. **La cara va tapada.** Los primeros planos de caras humanas son lo peor que le sale a
   cualquier modelo de video: el valle inquietante mata la retención en un segundo. Con
   máscara y regulador solo se ven los ojos. Se esquiva la debilidad más grande del modelo
   sin que se note.
2. **El agua turbia perdona.** Partículas en suspensión, poco contraste, luz difusa: es el
   entorno donde los artefactos de generación desaparecen. Realismo barato de sostener.
3. **Todo el peso está en el sonido**, que es lo que H3 hace distinto. Respiración en el
   regulador, burbujas, crujido de metal, el silencio de la presión.

**El guion pasa por el paso de emoción antes de sintetizar** — cada línea con su tag de
entrega de `eleven_v3` y su densidad medida. Ver [VOZ-EMOCION-V3.md](VOZ-EMOCION-V3.md).

Y una cuarta, sobre la voz: **no hay diálogo sincronizado**. Ningún plano lleva `[Speech]`.
La voz va en off, hecha con ElevenLabs, encima. Con el regulador puesto no se ve la boca,
así que no hace falta que el modelo sincronice nada — y de paso la voz queda idéntica en
las ocho líneas, que es justamente lo que H3 no sabe resolver.

---

## El pipeline

```
concepto → planos.json (12) → storyboard.json → primeros fotogramas (nano banana)
                                                          ↓
                           H3 en ComfyUI, GPU alquilada: 12 clips de 5,2 s con audio
                                                          ↓
                     cortar.py: recorta cada clip a su tramo `usa` y concatena
                                                          ↓
                              voz en off de ElevenLabs montada encima
```

### El truco del mínimo de 5,2 segundos

H3 no puede generar planos más cortos: **124 fotogramas es el piso de su rango entrenado**.
Pero un short necesita cortes de 1,5 a 2,5 s al principio o pierde al espectador.

La salida es generar de más y usar solo el mejor pedazo. Cada plano lleva anotado `usa` con
el tramo que va a la línea de tiempo. **Se generan 74,8 s para usar 60.**

Para cambiar el ritmo se editan los `usa` en `planos.json` y se vuelve a correr `cortar.py`.

### Dos detalles de montaje que costaron

- **Cada clip se recorta y recodifica por separado**, y recién después se concatena. Cortar
  con `-c copy` no sirve: el corte cae en un fotograma cualquiera y ffmpeg lo mueve al
  keyframe más cercano, que puede estar a un segundo — justo lo que arruina un ritmo
  pensado al décimo.
- **El 9:16 se pide por parámetro de la API, no por texto.** Describiéndolo en el prompt,
  nano banana devolvió tres relaciones distintas en una misma tanda.

---

## Herramientas

| Archivo | Qué hace |
|---|---|
| `Proyecto_Short/armar_short.py` | escribe `planos.json`, `storyboard.json` y `voz_en_off.txt` |
| `Proyecto_Short/cortar.py` | recorta cada clip a su tramo y concatena |
| `tools/nanobanana.py` | genera los primeros fotogramas |
| `tools/h3_plan.py` · `h3_generate.py` · `h3_comfy.py` | planifica y ejecuta H3 sobre ComfyUI |
| `cine/` | paquete del pipeline H3: guion, comfy, frames, montaje, render, alineación |

## Infraestructura

H3 no corre local: va en GPU alquilada por hora, que sale más barato que pagar por unidad
de salida.

| Documento | Qué cubre |
|---|---|
| [PASO-A-PASO.md](PASO-A-PASO.md) | de alquilar la máquina a bajarte el video, ~55 min y ~$1.80 |
| [RUNPOD-H3.md](RUNPOD-H3.md) | el pod de RunPod |
| [COSTOS-H3.md](COSTOS-H3.md) | costos medidos — **leerlo antes de estimar** |
| [PRUEBAS-H3/](PRUEBAS-H3/) | 10 clips comparando pasos y cuantización, + 2 de Veo como referencia |

**El ancho de banda importa más que el precio por hora.** Hay que bajar 59 GB de modelos
antes de generar nada: a 2000 Mbps son 4 minutos y $0.10; a 30 Mbps son 262 minutos y
$6.65. Una máquina barata con enlace lento sale más cara que generar el video entero.

---

## La ley: `Estructuras_Contenido_Alta_Retencion_2026.docx`

Desde el 28 de agosto de 2026, **ese documento manda** sobre cómo se estructura un
short. Está implementado en `h3pipeline/estructuras/` y el módulo lo valida: entra la
idea, se estructura según la ley, y lo que se aparta queda escrito.

**No hay una duración, hay tres**, y cada una con su umbral de retención:

| estructura | dura | retención objetivo | para qué | plataformas |
|---|---|---|---|---|
| `short-23` | 23 s | **65 %** | alcance puro, descubrimiento | Reels, TikTok, Shorts |
| `short` | 60 s | **50 %** | multiplataforma — **el default** | las tres |
| `short-90` | 90 s | **45 %** | guardados, comunidad, explicar | TikTok, Reels |

El umbral sube cuanto más corto es el video. Y 60 s es el punto donde entra en las
tres: Shorts corta en 60, TikTok premia 60-90 por tiempo de visualización, Reels
necesita menos de 90 para Explorar.

Lo que la ley exige en todos, y el módulo chequea:

- **Ventana crítica de 1 a 3 s.** No cambia con la duración.
- **Triple refuerzo del gancho:** imagen, sonido y **texto en pantalla**, los tres.
- **Anteponer el resultado concreto**, no la promesa genérica.
- **Interrupción de patrón cada 8-12 s.** Un corte no cuenta: cuenta un cambio de
  régimen (luz, sonido, ritmo).
- **Loop de cierre**, y una pregunta contestable en una frase — el comentario largo
  pesa hasta diez veces más que un emoji.

**El texto en pantalla va en POST.** Es la única parte que no se puede ejecutar como
está escrita: los modelos destrozan el texto. Se declara en el plano y sale como
entregable en `texto_en_pantalla.txt`, con sus tiempos.

```bash
python -m h3pipeline estructuras                                   # las cuatro
python -m h3pipeline brief ejemplos/profundidad/proyecto.json      # los tramos
python -m h3pipeline construir ejemplos/profundidad/proyecto.json  # + validación
```

## La plantilla — resuelto en `h3pipeline/`

Lo que era un script por concepto ahora es un módulo. PROFUNDIDAD está reescrito como
definición declarativa en [`ejemplos/profundidad/proyecto.json`](ejemplos/profundidad/proyecto.json),
y reproduce el video existente al décimo: los mismos 12 planos, los mismos cortes y los
mismos ocho tiempos de voz. Para un short nuevo se copia esa carpeta y se cambian el
estilo, el sujeto y los planos.

**El criterio de los `usa` ya está escrito**, en
[`h3pipeline/estructuras/short.json`](h3pipeline/estructuras/short.json): ocho tramos con
su objetivo, lo que exige cada uno y su rango de corte. No son límites teóricos — son los
cortes de PROFUNDIDAD, que es lo único medido que hay. El módulo valida los planos contra
eso, avisa lo que se aparta, y mete el objetivo de cada tramo **dentro del prompt del
primer fotograma**.

```bash
python -m h3pipeline brief ejemplos/profundidad/proyecto.json      # los ocho tramos
python -m h3pipeline construir ejemplos/profundidad/proyecto.json  # storyboard + planos
```

## Lo que falta

- **Ningún short se midió contra su propio umbral.** La ley fija 65 / 50 / 45 % según
  duración, pero no hay una sola gráfica de retención propia para contrastar. Hasta
  que la haya, los umbrales son la referencia del informe, no un resultado nuestro.
- **Las fuentes del informe son secundarias.** Son agencias y blogs de 2026, no la
  documentación oficial de las plataformas ni datos del canal. El propio documento
  advierte que las cifras varían por nicho y son orientativas.
- **`short-23` y `short-90` no se produjeron nunca.** Sólo `short` tiene un video
  detrás (PROFUNDIDAD). Las otras dos están derivadas del informe, sin corrida.
- **El desperdicio de generación crece al acortar.** Con cortes de 1,5-3 s y un mínimo
  de 5,17 s por clip, `short-23` genera ~29 s para usar 23 (26 % descartado) y en el
  gancho se tira más de la mitad del plano.
- **La voz en off no está cronometrada contra el audio real**, como sí lo está en el
  pipeline largo. Los tiempos de `voz_en_off.txt` son objetivos, no medidos.
