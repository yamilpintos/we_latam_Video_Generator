# Informe: integración selectiva de ViMax

**Nada de esto está implementado.** Es el informe previo que pediste.

Fuente: `github.com/HKUDS/ViMax` · MIT · 11.802 estrellas · último push 2026-07-29.
Leí el árbol completo (203 entradas, 104 archivos de código) y el contenido de
`interfaces/shot_description.py`, `interfaces/camera.py`, `interfaces/scene.py`,
`agents/storyboard_artist.py` y `agents/camera_image_generator.py`.

---

## 1 · CURRENT PIPELINE

```
HISTORIA (texto libre)
   │
   ▼
CAPA 0 ── guion cronometrado + timeline maestro
   │      (grilla 10/5 · IDs SXX-PYY · timecode absoluto)
   │      artefactos: 01-guion.md, 02-timeline.md
   ├──► CAPA A  biblia visual: STYLE TOKEN + placas de referencia
   ├──► CAPA B  un prompt de imagen por plano
   ├──► CAPA C  movimiento: Veo 10 s / DepthFlow 5 s / GFX 5 s
   ├──► CAPA D  voz: timing.py → tts_block.py → retime.py → build_vo_track.py
   └──► CAPA E  sonido: sfx_plan.py → sfx_generate.py → mix.py
   │
   ▼
ENSAMBLE (editor)
```

Lo que encontré auditando el repositorio, y que importa para esta decisión:

**No tenemos agentes.** El pipeline son documentos markdown más scripts de Python
deterministas. La inteligencia narrativa la aporto yo en la conversación; no hay código que
decida nada creativo. Esto es central: ViMax es un framework de agentes LLM, y nosotros no
tenemos runtime de agentes ni lo necesitamos mientras el trabajo se haga conversando.

**No tenemos estructura de datos para planos.** El timeline es una tabla markdown. Las únicas
estructuras reales son `timing.py:BLOCKS` (voz, tuplas) y `shotlist-mco.csv` (movimiento,
tres columnas). **Este es el hueco más grande y es exactamente lo que ViMax sí tiene resuelto.**

**Continuidad: manual y por convención.** STYLE TOKEN idéntico en cada prompt, placas de
referencia que se adjuntan, y la regla de no encadenar imágenes. Funciona, pero no hay memoria
de estado entre planos: nada sabe dónde estaba la cámara en el plano anterior.

**Los prompts se escriben a mano, uno por plano.** No hay traducción automática de una intención
a un prompt. Y están acoplados al generador: el prompt de Veo lleva sus negativos y el de
ChatGPT su STYLE TOKEN. Cambiar de modelo obligaría a reescribir los 42.

**Modelos:** ChatGPT/GPT Image (manual, sin API), Veo 3 (manual), ElevenLabs (API: voz, SFX,
música), DepthFlow (local, sin API).

**Assets y metadatos:** convención de nombres por ID (`IMG_S03-P07.png`). No hay base de datos
ni índice.

---

## 2 · VIMAX RELEVANT ARCHITECTURE

Solo lo aplicable. Ignoro `novel2movie`, `idea2video`, extracción de personajes y todo el bloque
de guionista.

### `interfaces/` — las estructuras de datos

Modelos pydantic. Es la parte más reutilizable del repo.

- **`Camera`** — *el hallazgo importante.* Una cámara es una entidad con `idx`,
  `active_shot_idxs` (qué planos filma), `parent_cam_idx`, `parent_shot_idx`,
  `is_parent_fully_covers_child` y `missing_info`.
- **`ShotBriefDescription`** — `idx`, `is_last`, `cam_idx`, `visual_desc` (texto libre largo),
  `audio_desc`.
- **`Scene`** — `environment`, `characters[]`, `script` con nombres entre `<>`.

### `agents/storyboard_artist.py`

Escena → lista de planos. El prompt de sistema tiene una regla que nosotros no tenemos:

> *"When designing a new shot, first consider whether it can be filmed using an existing camera
> position. Introduce a new one only if the shot size, angle, and focus differ significantly."*

Es **economía de cámara**: no inventar un punto de vista nuevo por cada plano.

### `agents/camera_image_generator.py`

Construye un **árbol de cámaras**: identifica qué cámara padre *contiene* el contenido de cada
cámara hija. Después genera la imagen del padre —el plano más abierto— y la usa como
**referencia visual** para generar los planos hijos.

### Lo que NO aplica

`character_extractor`, `character_portraits_generator`, `scene_extractor`, `event_extractor`,
`screenwriter`, `novel_compressor`, `script_enhancer`: todo asume ficción con actores y diálogo.
Nuestro contenido es documental sin personajes. `agent_runtime/` es un loop de agente sobre
langchain que no necesitamos.

---

## 3 · COMPONENT MAPPING

| Concepto de ViMax | Nuestro equivalente | Acción |
|---|---|---|
| **Camera tree** (padre contiene hijo) | Ninguno. Nuestro experimento de máster→recortes llegó a la misma idea pero se topó con el techo de resolución | **Reimplementar** — es lo más valioso |
| Generación del hijo usando el padre como referencia | Ninguno. Nosotros recortábamos y escalábamos | **Reimplementar** — resuelve el límite de ×1,9 que medimos |
| Economía de cámara en el storyboard | Ninguno | **Reimplementar** — es una regla de prompt, no código |
| `ShotBriefDescription` | Fila de tabla markdown en `02-timeline.md` | **Adaptar** — nos falta estructura, pero la suya se queda corta |
| `Camera` (pydantic) | Ninguno | **Adaptar** — el modelo sirve casi tal cual |
| `Scene` | Sección de `01-guion.md` | **Ignorar** — la suya es centrada en personajes |
| `storyboard_artist` (agente LLM) | Yo, en la conversación | **Ignorar** — pagaríamos API por lo que ya hacemos |
| `agent_runtime/` (loop langchain) | Ninguno | **Ignorar** — dependencia pesada sin beneficio |
| `character_*`, `scene_extractor`, `screenwriter` | Capa 0 y Capa A | **Ignorar** — asumen ficción con actores |
| Continuidad por referencias | STYLE TOKEN + placas | **Reutilizar el nuestro**, reforzado con el árbol |
| `audio_desc` en el plano | Capa E completa, con timecodes y mezcla | **Ignorar** — el nuestro es mucho más fino |
| `pipelines/script2video_pipeline.py` | Nuestro pipeline de 5 capas | **Ignorar** |

---

## 4 · PROPOSED ARCHITECTURE

Un módulo nuevo, insertado entre la Capa 0 y las capas B/C. Todo lo demás intacto.

```
CAPA 0 · guion + timeline          ← sin cambios
   │
   ▼
┌─────────────────────────────────────────┐
│  CAPA P · PLANIFICACIÓN CINEMATOGRÁFICA │  ← NUEVO, desactivable
│                                         │
│   intención narrativa por plano         │
│   árbol de cámaras                      │
│   estado de continuidad                 │
│   ShotPlan (representación neutral)     │
└─────────────────────────────────────────┘
   │
   ▼
┌─────────────────────────────────────────┐
│  ADAPTADORES DE PROMPT                  │  ← NUEVO
│   ShotPlan → GPT Image                  │
│   ShotPlan → Veo 3                      │
│   ShotPlan → DepthFlow (acercar/alejar) │
└─────────────────────────────────────────┘
   │
   ▼
CAPAS B / C / D / E                ← sin cambios
```

Si el módulo se desactiva, las Capas B y C vuelven a escribirse a mano como hoy. No hay
acoplamiento en la otra dirección.

### La decisión de diseño que propongo, y por qué difiere de lo que planteaste

Vos proponías un `Shot` con ~25 campos (framing, focal length, lens character, negative space,
entry point of the eye…). **ViMax, que es el sistema de referencia, no hace eso**: su
`ShotBriefDescription` tiene cuatro campos y toda la cinematografía vive en un `visual_desc` de
texto libre.

Creo que tienen razón, por una razón práctica: los generadores de imagen no consumen campos,
consumen prosa. Un esquema de 25 campos que después se concatena en una frase agrega ceremonia
sin agregar control, y encima invita a rellenar campos que no aportan —el problema que vos mismo
señalaste con "no introducir parámetros técnicos arbitrarios".

Propongo un punto intermedio: **estructurar lo que se valida o se reutiliza, y dejar en prosa lo
que solo se concatena.**

```python
Shot:
    id                    # S06-P05
    duracion              # 5 | 10 — la grilla valida
    tipo                  # veo | still | gfx
    funcion_narrativa     # texto: QUÉ hace este plano en la historia
    razon                 # texto: POR QUÉ este encuadre y no otro
    camara_id             # referencia al árbol
    escala                # general | medio | detalle — se valida progresión
    sentido               # acercar | alejar | quieto — se valida alternancia
    sujeto                # a qué placa de la biblia apunta
    descripcion_visual    # PROSA. Lo que va al generador
    continuidad           # qué hereda del plano anterior
```

Los cinco primeros campos existen para **validar**: que la grilla cierre, que la escala progrese,
que el sentido alterne, que la cámara exista. `descripcion_visual` es prosa porque es lo único
que el modelo lee.

Y un campo que ViMax no tiene y para nosotros es obligatorio: **`funcion_narrativa`**. Sin él
volvemos a "beautiful cinematic shot".

### Tipos de plano para documental

El `escala` de ViMax asume actores. Nuestro catálogo tiene que incluir lo que ya usamos:
reconstrucción, entorno, macro/detalle, visualización técnica, diagrama, inserto de documento,
objeto, comparación de escala, visualización orbital. Los 12 planos GFX del video actual no
entran en ninguna categoría de ViMax.

---

## 5 · FILES TO CREATE

| Archivo | Qué haría |
|---|---|
| `pipeline/08-CAPA-P-planificacion.md` | La doctrina: función narrativa, árbol de cámaras, escalas, continuidad, catálogo documental |
| `tools/shotplan.py` | Los dataclasses `ScenePlan` / `Shot` / `Camera` + validaciones (grilla, alternancia, progresión de escala, cámara existente) |
| `tools/shotplan_mco.py` | Los datos del video actual, como `sfx_plan.py` para el sonido |
| `tools/prompt_adapters.py` | `ShotPlan` → prompt de GPT Image · → prompt de Veo · → técnica de DepthFlow |
| `tools/shotplan_check.py` | Validador con `--dry-run`, en la línea de `depthflow_batch.py` |

## 6 · FILES TO MODIFY

| Archivo | Razón | Riesgo |
|---|---|---|
| `pipeline/01-CAPA-0-guion.md` | Insertar la Capa P entre guion y timeline | bajo, es doc |
| `tools/depthflow_batch.py` | Leer el sentido desde el shot plan en vez del CSV, con el CSV como respaldo | bajo, ya está aislado |
| `README.md` | Documentar el módulo nuevo | nulo |
| `tools/shotlist-mco.csv` | Pasaría a ser salida del plan, no fuente | bajo |

**Nada de la Capa D ni de la Capa E se toca.** El audio está producido y no depende de esto.

## 7 · DEPENDENCIES

**Ninguna nueva.** Con la reimplementación propuesta alcanza `dataclasses` de la stdlib.

Si en cambio adaptáramos código de ViMax haría falta: `pydantic` (razonable), `langchain` +
`langchain-core` (pesado, arrastra el runtime de agentes), `tenacity` (trivial), `scenedetect`,
`moviepy`, `opencv-python` (los tres solo para su pipeline de video, que no usamos).

`langchain` es el acoplamiento que hay que evitar: entra por `storyboard_artist.py`, que es
justo el archivo que uno querría copiar.

## 8 · API IMPACT

**Cero APIs nuevas.** La planificación la hago yo en la conversación, igual que ahora.

ViMax ejecutado tal cual llamaría a un LLM por escena y por plano. Con 9 secuencias y 50 planos
serían ~60 llamadas por video, con su costo y su latencia, para producir un criterio que ya
estamos produciendo acá.

## 9 · COST IMPACT

| Escenario | Costo |
|---|---|
| Reimplementar (propuesto) | **0** |
| Adaptar código de ViMax | 0 en API, pero ~60 llamadas LLM por video si usamos sus agentes |
| Instalar ViMax completo | Además, sus generadores de imagen y video por API |

El árbol de cámaras **baja** el costo: menos generaciones de imagen por locación.

## 10 · RISKS

**El esquema puede volverse burocracia.** 25 campos por plano son 1.250 decisiones para un video
de 50 planos, la mayoría irrelevantes. Mitigación: estructurar solo lo que se valida.

**Rigidez creativa.** Un validador que exige alternancia de escala puede rechazar una decisión
correcta. Mitigación: que las validaciones adviertan, y solo fallen las duras — grilla y cámara
inexistente.

**El árbol de cámaras no está probado con GPT Image.** ViMax lo usa con sus propios generadores.
Que ChatGPT respete una imagen de referencia para generar un plano más cerrado **hay que
medirlo**, y es justo el experimento que quedó pendiente.

**Doble fuente de verdad transitoria.** Durante la migración, el timeline markdown y el shot plan
podrían divergir. Mitigación: el plan genera el markdown, no al revés — el patrón que ya usamos
con `sfx_plan.py` y `timing.py`.

**ViMax puede cambiar.** Push activo hace dos semanas. Si copiamos código quedamos atados a una
versión; si reimplementamos conceptos, no.

## 11 · RECOMMENDATION

**C, con una pizca de A: reimplementar la arquitectura, copiando solo la forma de dos modelos.**

Por qué no A (integrar directamente):
- ViMax asume ficción con actores y diálogo. Nuestro contenido es documental técnico sin
  personajes. Sus extractores de escena, personaje y evento no tienen a qué agarrarse.
- Su runtime es un loop de agentes langchain. Nosotros no tenemos runtime de LLM y el trabajo
  creativo pasa por esta conversación. Instalarlo sería pagar API por lo que ya hacemos.
- Su modelo de plano es **más pobre** que lo que necesitamos: sin función narrativa explícita y
  sin categorías documentales.

Por qué sí tomar de ViMax:
- **El árbol de cámaras es la mejor idea del repositorio** y ataca un problema que ya medimos.
  Nuestro experimento de máster→recortes llegó a la misma intuición y chocó con el techo de
  resolución: a ×3,38 la imagen es papilla. ViMax evita ese techo porque **no recorta**: genera
  el plano cerrado como imagen nueva usando el abierto como referencia. Resolución completa y
  continuidad heredada.
- La regla de economía de cámara es una línea de prompt y mejora la coherencia espacial gratis.
- Los modelos `Camera` y `ShotBriefDescription` son un buen punto de partida de forma.

De ViMax se copiaría, con aviso de copyright MIT, la **forma** de esos dos modelos pydantic.
Todo lo demás sería implementación propia inspirada en su arquitectura.

---

## Antes de implementar: un experimento de 30 minutos

Toda la propuesta descansa en un supuesto que **no está verificado**: que ChatGPT puede generar
un plano cerrado usando un plano abierto como referencia y mantener la continuidad.

Si funciona, el árbol de cámaras vale la pena y el módulo se justifica.
Si no funciona, nos queda el recorte con techo de ×1,9 y el módulo se reduce a disciplina
narrativa, que es mucho menos.

**La prueba:** generás una imagen de la sala de control en plano general. Después le pedís a
ChatGPT un primer plano de un monitor *de esa misma sala*, adjuntando el general como referencia.
Yo mido si la paleta, la luz y la arquitectura se conservan, comparando contra el recorte
equivalente.

Es un experimento barato y decide el diseño. Propongo hacerlo antes de escribir una línea.
