# Proyecto de video generado con IA

> **Empezá por [ESTADO-PROYECTO.md](ESTADO-PROYECTO.md).** Es el mapa al día:
> las dos mitades del proyecto (el módulo `h3pipeline/` con su página, y la
> operación en Vast.ai), qué está verificado, los números medidos y qué falta.
> Este README quedó desactualizado en su segunda mitad — ver la advertencia de
> más abajo.

Dos líneas de producción con **stacks de video distintos**. No son el mismo pipeline con
otro encuadre: cambian el generador, la relación con el audio y la infraestructura.

| | [Video largo](ESTADO-LARGO.md) | [Short vertical](ESTADO-SHORT.md) |
|---|---|---|
| Generador | **MiniMax H3** · clips de 5,2 a 15,1 s | **MiniMax H3** · mismo modelo, formato vertical |
| Audio del modelo | capa diegética, por plano | capa diegética, por plano |
| Quién manda el montaje | la voz, medida antes de cortar | el ritmo del corte, ajustado al décimo |
| Relleno entre clips | DepthFlow (parallax) y gráficos | no hay: todo es H3 |
| Formato | 1920×1080 | 768×1344 vertical |
| Terminado | Mars Climate Orbiter, 5:00 | PROFUNDIDAD, 60 s |
| En curso | El pescador y el genio, 8:00 | — |

**Empezá por [ESTADO-LARGO.md](ESTADO-LARGO.md) o [ESTADO-SHORT.md](ESTADO-SHORT.md)**,
que tienen el estado real y las trampas ya pagadas de cada uno.

---

## El módulo: [`h3pipeline/`](h3pipeline/)

Los dos flujos, short y largo, empaquetados como **un módulo importable** — para
que la app los llame en vez de copiar y editar un script por video.

```python
from h3pipeline import Proyecto, empaquetar, frames, vast

p = Proyecto.cargar("ejemplos/profundidad/proyecto.json")
print(p.brief())          # qué tiene que pasar en cada segundo
p.escribir()              # storyboard.json + planos.json + voz_en_off.txt
empaquetar.empaquetar(p)  # el ZIP para subir a la GPU alquilada
```

Lo que agrega sobre los scripts sueltos:

- **Una entrada de estructura por formato.** `estructuras/short.json` y
  `largo.json` declaran qué tiene que pasar en cada tramo de segundos — el
  gancho de los primeros 3 s, la promesa, el giro del medio — y eso **entra en
  el prompt del primer fotograma**, no queda en un documento aparte.
- **Validación.** Tramos sin cubrir, cortes fuera de rango, saltos de eje,
  diálogos con dos personajes, duraciones fuera del rango entrenado de H3.
- **Busca dónde correrlo.** `vast.buscar()` filtra por VRAM, fiabilidad,
  verificación real, placas demasiado viejas y los países que excluye la
  licencia de H3 — y ordena por **costo total del trabajo**, no por precio por
  hora.
- **Estima antes de gastar**, desde las mediciones de [COSTOS-H3.md](COSTOS-H3.md).
- **La capa de voz de ElevenLabs**, que antes vivía sólo en documentos:
  `voz.py` mide la densidad de cada línea contra su ventana y revisa los tags de
  emoción **antes** de sintetizar; `tts.py` prueba varias redacciones y se queda
  con la que mejor entra; `doblaje.py` es el motor de isocronía, generalizado.
  Ver [ISOCRONIA.md](ISOCRONIA.md) y [VOZ-EMOCION-V3.md](VOZ-EMOCION-V3.md).

Los dos videos que ya existen están reescritos como ejemplos:
[`ejemplos/profundidad/`](ejemplos/profundidad/) (short, 60 s) y
[`ejemplos/aladino/`](ejemplos/aladino/) (largo, 42 planos, 5:09).

Detalle en [h3pipeline/README.md](h3pipeline/README.md) · las reglas y qué costó
aprender cada una, en [h3pipeline/REGLAS.md](h3pipeline/REGLAS.md).

Hay una tercera línea abierta: **[ESTADO-DOBLAJE.md](ESTADO-DOBLAJE.md)** — reemplazar las
voces que inventa H3, que cambian en cada clip, por voces fijas de ElevenLabs. Está a medio
camino, con el bug que lo rompe ya identificado y medido.

---

## Advertencia sobre lo que sigue

Todo lo de abajo describe el pipeline **del Mars Climate Orbiter**, que se hizo con Veo y
con grilla fija de 10/5. **Es historia, no el método vigente.** Se conserva porque ese video
está terminado y su documentación sirve para entenderlo, pero no lo tomes como referencia
para un video nuevo.

Para lo vigente: [ESTADO-LARGO.md](ESTADO-LARGO.md), y el spec del episodio en curso en
[1001-noches/ep01-pescador/pipeline/00-MASTER-SPEC.md](1001-noches/ep01-pescador/pipeline/00-MASTER-SPEC.md).

Qué cambió, en corto:

| | Mars Climate Orbiter (abajo) | vigente |
|---|---|---|
| Generador | Veo, clips de 10 s | **MiniMax H3**, de 5,2 a 15,1 s |
| Duración de plano | grilla fija 10/5 | la elige el director |
| Relleno | DepthFlow y gráficos | no hay, todo es H3 |
| Audio del clip | se descartaba | capa diegética, se usa |

---

# ARCHIVO · El pipeline del Mars Climate Orbiter

Sistema por capas para convertir **una historia en texto** en **instrucciones ejecutables**
para cuatro áreas de producción, ya sincronizadas entre sí por timecode.

| Capa | Herramienta |
|---|---|
| Imágenes | Generador de imágenes de ChatGPT (GPT Image) |
| Video (image-to-video) | **Veo 3** — clips de 10 s |
| Imágenes en movimiento | **DepthFlow** (local, open source, sin créditos) |
| Voz en off | ElevenLabs |
| **Emoción y densidad de los diálogos** | [VOZ-EMOCION-V3.md](VOZ-EMOCION-V3.md) — paso obligatorio antes de sintetizar |
| **Isocronía: voz contra boca ya animada** | [ISOCRONIA.md](ISOCRONIA.md) — el método, aplicable a cualquier video de H3 |
| Efectos de sonido | ElevenLabs SFX + librería (Freesound / Pixabay) |
| Ensamble | `tools/build_video.py` |

Sistema por capas para convertir **una historia en texto** en **instrucciones ejecutables**
para cuatro áreas de producción, ya sincronizadas entre sí por timecode.

| Capa | Herramienta |
|---|---|
| Imágenes | Generador de imágenes de ChatGPT (GPT Image) |
| Video (image-to-video) | **MiniMax H3** — GPU alquilada, clips de 5,2 a 15,1 s |
| Imágenes en movimiento | **DepthFlow** (local, open source, sin créditos) |
| Voz en off | ElevenLabs |
| Efectos de sonido | ElevenLabs SFX + librería (Freesound / Pixabay) |
| Ensamble | `tools/build_video.py` |

---

## Cómo se usa

1. Abrí [templates/RUN.md](templates/RUN.md), copiá el bloque, pegá tu historia y mandámelo.
2. Devuelvo **Capa 0: guion cronometrado**. → **Gate 1: lo aprobás o lo corregís.**
3. Devuelvo **Capa A: biblia visual** — STYLE TOKEN, árbol de cámaras y placas de sujeto.
3b. Devuelvo el **árbol de cámaras**. Generás las madres. → **Gate 2b: las aprobás.**
4. Con el timeline congelado, devuelvo de una vez las capas de producción:
   - `04-veo.md` — los planos de 10 s: imagen semilla + prompt de Veo
   - `05-movimiento.md` — los planos de 5 s: imagen + sentido de cámara
   - `06-gfx.md` — los planos gráficos
   - `07-voz.md` — texto exacto por toma, con timecode
   - `08-sfx.md` — cada efecto con segundo de inicio y duración
5. Producís cada capa por separado y ensamblás con [pipeline/08-ENSAMBLE.md](pipeline/08-ENSAMBLE.md).

Todo se ancla a un **ID de plano** (`S03-P07`) y a un **timecode absoluto**. Ese es el pegamento:
la persona que hace SFX y la que hace imágenes nunca hablan entre sí, pero encajan.

---

## Documentación

| Archivo | Qué define |
|---|---|
| [pipeline/00-MASTER-SPEC.md](pipeline/00-MASTER-SPEC.md) | Constantes, matemática del timeline, IDs, presupuestos por preset |
| [pipeline/01-CAPA-0-guion.md](pipeline/01-CAPA-0-guion.md) | Cómo se cronometra el guion |
| [pipeline/02-CAPA-A-biblia.md](pipeline/02-CAPA-A-biblia.md) | STYLE TOKEN, **árbol de cámaras** y placas de sujeto |
| [pipeline/03-CAPA-B1-veo.md](pipeline/03-CAPA-B1-veo.md) | Planos de **10 s**: imagen semilla + prompt de Veo 3 |
| [pipeline/04-CAPA-B2-movimiento.md](pipeline/04-CAPA-B2-movimiento.md) | Planos de **5 s**: imagen + DepthFlow, con el criterio acercar/alejar/quieto |
| [pipeline/05-CAPA-B3-gfx.md](pipeline/05-CAPA-B3-gfx.md) | Planos de **5 s** gráficos: diagramas y datos |
| [pipeline/06-CAPA-D-voz.md](pipeline/06-CAPA-D-voz.md) | ElevenLabs: bloques, settings, nombres de archivo |
| [pipeline/07-CAPA-E-sfx.md](pipeline/07-CAPA-E-sfx.md) | Cuatro pistas de audio, niveles, ducking |
| [pipeline/08-ENSAMBLE.md](pipeline/08-ENSAMBLE.md) | Orden de montaje y mezcla final |
| [output/ejemplo-36s/EJEMPLO.md](output/ejemplo-36s/EJEMPLO.md) | 36 segundos resueltos, para ver el formato de salida |

## El video en producción

Los prompts concretos de *Mars Climate Orbiter* (0:00 – 5:00) viven en `pipeline/`:

| Archivo | Qué contiene |
|---|---|
| [PROMPTS-00-GUION-Y-TIMELINE.md](pipeline/PROMPTS-00-GUION-Y-TIMELINE.md) | El guion y los 50 planos con IN/OUT. **La referencia que ata todo** |
| [PROMPTS-01-IMAGENES-PARA-VEO.md](pipeline/PROMPTS-01-IMAGENES-PARA-VEO.md) | 10 planos de 10 s: imagen semilla + prompt de Veo |
| [PROMPTS-02-IMAGENES-PARA-MOVIMIENTO.md](pipeline/PROMPTS-02-IMAGENES-PARA-MOVIMIENTO.md) | 28 planos de 5 s + los 12 gráficos |
| [PROMPTS-03-SONIDO.md](pipeline/PROMPTS-03-SONIDO.md) | 7 ambientes · 4 cues · 46 efectos |
| [PROMPTS-04-VOZ.md](pipeline/PROMPTS-04-VOZ.md) | Las 60 tomas con timecode. **Producida** |

## Herramientas

| Archivo | Qué hace |
|---|---|
| [tools/h3_plan.py](tools/h3_plan.py) | Los 10 planos de video: escena, movimiento y duración. Fuente única |
| [tools/h3_comfy.py](tools/h3_comfy.py) | Genera los clips en un ComfyUI remoto — el pod de RunPod. Ver [RUNPOD-H3.md](RUNPOD-H3.md) |
| [tools/h3_generate.py](tools/h3_generate.py) | Lo mismo pero por la API de Replicate. Valida el esquema y el costo antes de gastar |
| [tools/depthflow_scenes.py](tools/depthflow_scenes.py) | Nueve escenas de DepthFlow de 5 s, unidireccionales y con easing |
| [tools/depthflow_batch.py](tools/depthflow_batch.py) | Render en lote desde una shotlist CSV, con validación previa |
| [tools/shotlist-mco.csv](tools/shotlist-mco.csv) | Shotlist de ejemplo: los 32 planos STILL de Mars Climate Orbiter |
| [tools/timing.py](tools/timing.py) | Planifica los timecodes de voz contra el conteo de palabras. Se usa **antes** de generar |
| [tools/tts_block.py](tools/tts_block.py) | Genera cada bloque como **una** interpretación continua y lo corta en tomas por timestamps |
| [tools/tts_generate.py](tools/tts_generate.py) | Genera toma por toma. Descartado: v3 no admite contexto entre llamadas y se oye el empalme |
| [tools/retime.py](tools/retime.py) | Recalcula los timecodes contra la duración **real** de los MP3. Detecta solapes y desbordes |
| [tools/build_vo_track.py](tools/build_vo_track.py) | Arma las tomas en una sola pista de voz de 5 min, ya sincronizada. Sin ffmpeg |
| [tools/sfx_plan.py](tools/sfx_plan.py) | Plan de la Capa E: ambientes, música y 45 efectos. Fuente única del documento y del generador |
| [tools/sfx_generate.py](tools/sfx_generate.py) | Genera los 56 archivos de audio en ElevenLabs |
| [tools/mix.py](tools/mix.py) | Mezcla las 4 pistas con ducking real y masteriza a −14 LUFS (BS.1770-4) |

## Las dos reglas base

### El árbol de cámaras

Una cámara es **un lugar del espacio**, no un plano. Los planos se agrupan por punto de vista: se
genera primero el más abierto de cada cámara y ese se usa como referencia visual para generar los
cerrados. Da continuidad espacial sin el techo de resolución que tiene recortar. Detalle en
[02-CAPA-A §2](pipeline/02-CAPA-A-biblia.md).

### La grilla 10 / 5 — solo en el Mars Climate Orbiter

Todo plano dura **10 segundos si es un clip de Veo** o **5 segundos si es una imagen animada o un
gráfico**. Como los dos son múltiplos de 5, toda duración de secuencia lo es también, y el guion se
escribe contra la grilla. Detalle en [00-MASTER-SPEC §3](pipeline/00-MASTER-SPEC.md).

**Esta grilla era una restricción de Veo y no se aplica al Pescador.** MiniMax H3 acepta de 5,2 a
15,1 s por clip, así que cada plano dura lo que la escena necesita — ver
[el spec del Pescador](1001-noches/ep01-pescador/pipeline/00-MASTER-SPEC.md).
