# Estado · Video largo

Actualizado: 25 de agosto de 2026.

La voz manda sobre el montaje y el audio se construye aparte. **El generador cambió**: el
Mars Climate Orbiter se hizo con Veo, y el Pescador va con MiniMax H3, el mismo modelo del
short. Para el pipeline vertical ver [ESTADO-SHORT.md](ESTADO-SHORT.md).

---

## Las dos producciones

| | Mars Climate Orbiter | El pescador y el genio |
|---|---|---|
| Carpeta | `pipeline/` + `output/mars-climate-orbiter/` | `1001-noches/` |
| Formato | documental, sin personajes | cuento animado, con personajes |
| Duración | 5:00 producidos (de 8:00 previstos) | 8:00 previstos |
| Generador | Veo + DepthFlow + gráficos | **MiniMax H3**, todo |
| Planos | 50 · de 10 s y 5 s | ~48-60 · de 5,2 a 15,1 s |
| Diálogo | ninguno, solo narración | mucho; lip sync sin decidir |
| Estado | **terminado y montado** | **andamiaje escrito, sin guion** |

---

## 1 · Mars Climate Orbiter — terminado

`output/mars-climate-orbiter/MCO_5min.mp4` · 663 MB · 1920×1080 · 24 fps · **300,00 s
exactos** (7200 frames) · audio −14,3 LUFS.

| Capa | Estado |
|---|---|
| Guion y timeline, 50 planos | producido |
| Voz — 60 tomas, Sandmor, `eleven_v3` | producida |
| Sonido — 7 ambientes, 4 cues, 46 efectos, mezcla 4 pistas | producida |
| 10 clips de Veo | producidos |
| 28 planos DepthFlow | producidos |
| 12 planos gráficos | producidos |
| Montaje final | producido |

Hay una copia empaquetada en `ENTREGA-MCO-5min/`.

### Lo que quedó abierto

- **Minutos 5:00 a 8:00** — existen solo como esquema de seis secuencias. Nunca se
  escribieron.
- **Los clips de Veo se ven más blandos**: llegaron a 1280×720 y se escalaron a 1080p.
- **El audio es mono** y el pico real quedó en −0,4 dBFS por el sobreimpulso del AAC.
- **S04 arrastra 1,2 s de silencio** que no entra en ninguna pausa. Se arregla con unas
  tres palabras más de texto, no con más pausa.
- **Los timecodes de `pipeline/PROMPTS-04-VOZ.md` están vencidos** por décimas desde la
  última regeneración de voz.

---

## 2 · El pescador y el genio — arrancando

Todo el metraje sale de **MiniMax H3**, en GPU alquilada. La consistencia depende casi por
completo de las imágenes semilla y de las de referencia, y por eso la biblia de personajes
es la pieza central en vez de un anexo.

```
1001-noches/
├── VISUAL_BIBLE.md              estética operativa, derivada del prompt de Shahrazad
├── story-bible/
│   ├── characters/  shahrazad · pescador · genio
│   ├── locations/   cámara real · playa · lago del desierto
│   └── props/       vasija de cobre
└── ep01-pescador/
    ├── guion/fuente-original.md
    ├── pipeline/00-MASTER-SPEC.md
    ├── assets/voz-pruebas/      4 voces de prueba en inglés
    └── planning/ reviews/ locked/
```

### Decisiones cerradas

- **Sin grilla.** H3 acepta de 5,2 a 15,1 s por clip, así que cada plano dura lo que la
  escena necesita. La zona eficiente por costo está entre 8 y 11 s.
- **El guion pasa por el paso de emoción antes de sintetizar.** Cada diálogo se entrega con
  su tag de entrega de `eleven_v3` y su densidad medida contra la ventana — ver
  [VOZ-EMOCION-V3.md](VOZ-EMOCION-V3.md).
- **Toda la voz sale de ElevenLabs.** H3 no sostiene una voz entre clips —no hay voice ID—
  y la voz es lo que el oyente detecta al instante. La regla: H3 genera lo que nace y muere
  dentro del plano; ElevenLabs, todo lo que cruza el corte.
- **Shahrazad narra en pantalla** en ráfagas de 4-6 s, y su voz sigue en off sobre el
  cuento. Los tags `DIALOGUE_SYNC` / `VOICE_OVER` / `NARRATION` / `OFF_SCREEN` salen del
  guion en Fountain como `(V.O.)` y `(O.S.)`.
- **Nada se genera antes de bloquear la shot list.** Con H3 afloja, porque se paga por
  tiempo de máquina y regenerar es gratis; pero sigue valiendo por las horas de GPU.

### Lo que falta

1. Elegir las tres voces y medirles la tasa de palabras por segundo.
2. Un clip de prueba de lip sync en español, antes de escribir 56 planos alrededor.
3. El guion en Fountain con los tags.
4. Los tres agentes de dirección — director, auditor narrativo, auditor de cámara.
5. Las imágenes madre.

---

## El pipeline

```
historia → guion cronometrado → voz generada y MEDIDA → timeline congelado
                                                              ↓
        ┌──────────────┬──────────────┬──────────────┬────────────────┐
     imágenes        clips H3      audio diegético   voz/música   efectos
        └──────────────┴──────────────┴──────────────┴────────────────┘
                                     ↓
                        montaje por concatenación + mezcla
```

**La regla que sostiene todo:** el guion se escribe, se genera la voz y se mide el audio
real; recién con esos números se cortan los planos. Estimar por conteo de palabras alcanza
para planificar, pero a nivel toma el error llega al 30 %. Por eso existe `retime.py`.

Todo se ancla a un **ID de plano** (`S06-P05`) y a un **timecode absoluto**. Quien hace las
imágenes y quien hace el sonido no se hablan, y encajan.

### El módulo

Este flujo está empaquetado en [`h3pipeline/`](h3pipeline/), con Aladino migrado
como ejemplo en [`ejemplos/aladino/`](ejemplos/aladino/) — los 42 planos, 5:09,
reproducidos desde una definición declarativa. La estructura narrativa del formato
largo (apertura fría, planteo, detonante, desarrollo, punto medio, complicación,
clímax, resolución, salida) vive en
[`h3pipeline/estructuras/largo.json`](h3pipeline/estructuras/largo.json) y se
estira sola a la duración que pidas: la misma sirve para 5 y para 8 minutos.

```bash
python -m h3pipeline brief ejemplos/aladino/proyecto.json
python -m h3pipeline costo ejemplos/aladino/proyecto.json   # 52 min, $1.65
python -m h3pipeline gpu   ejemplos/aladino/proyecto.json   # dónde correrlo
```

### Herramientas

| Archivo | Qué hace |
|---|---|
| `tools/timing.py` | cronometra el guion contra la tasa medida de la voz |
| `tools/tts_block.py` | genera la voz en **una sola llamada** y la corta por timestamps |
| `tools/retime.py` | recalcula los IN contra la duración real del audio |
| `tools/build_vo_track.py` | arma la pista de voz continua |
| `tools/sfx_plan.py` · `sfx_generate.py` | planifica y genera ambientes y efectos |
| `tools/mix.py` | mezcla 4 pistas con ducking y limita a −14 LUFS |
| `tools/depthflow_scenes.py` | las tres escenas: acercar, alejar, quieto |
| `tools/depthflow_batch.py` | render en lote, **un subproceso por clip** |
| `tools/gfx_render.py` | los planos gráficos, frame a frame |
| `tools/preparar_assets.py` | mapea los assets crudos a IDs de plano |
| `tools/build_video.py` | normaliza los 50 planos y concatena por copia |

### Trampas ya pagadas

- **`eleven_v3` no acepta `previous_text`/`next_text`.** Generar toma por toma produce un
  reinicio prosódico audible en cada corte. Se genera el guion entero de una vez.
- **Cortar por silencios falla** — 24 de 60 cortes caían mal. Se corta por los timestamps
  por carácter que devuelve el endpoint `/with-timestamps`.
- **Repartir el sobrante proporcionalmente se desmadra.** Si la voz sale más corta, todos
  los silencios crecen. Hay topes por hueco y reparto por *waterfill*.
- **`zoom` en DepthFlow está invertido**: 0.75 acerca. Y barrer `isometric` se lee como
  turntable de producto, no como cine — queda fijo en 0.45.
- **DepthFlow agota la memoria de texturas** si se crean varias escenas en un proceso: al
  tercer render muere con `cannot create texture`. Un subproceso por clip.
