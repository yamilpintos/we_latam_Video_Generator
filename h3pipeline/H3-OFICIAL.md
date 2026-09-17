# H3 al máximo: el método oficial, las voces constantes y las imágenes con GPT

**14 de septiembre de 2026.** Lo aprendido armando la réplica de «El amor es una
danza peligrosa» (competencia contra un episodio hecho con Kling), escrito para
que lo use el pipeline y la web sin volver a descubrirlo. Cada punto dice de
dónde sale. Lo que dice **SIN PROBAR** no corrió todavía en una máquina real.

Documentos hermanos: `REGLAS.md` (reglas 41-52 resumen esto), `VAST.md`,
`../MANUAL-DE-PRODUCCION.md`, y las fuentes crudas del repaso en
`../models/MiniMax-H3/docs-extra/` (`PLAN-H3-AL-MAXIMO.md` + cuatro `RESUMEN-*.md`).
El registro con números de la réplica: `../mis-videos/replica-danza/NOTAS.md`.

---

## 1 · El prompt: el formato oficial, no texto libre

Hasta el 14/9 el módulo le mandaba a H3 texto libre (`MOTION:`, `AUDIO:`,
`SPOKEN LINE:` más bloques negativos). **No es el formato con que MiniMax
entrenó y evalúa el modelo.** El README oficial: el formato que produce su
reescritor H3-Context-IR es *"critical to the quality"*, y quien corre los pesos
abiertos tiene que escribirlo a mano siguiendo la guía
(`models/MiniMax-H3/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md` y `_ref_en.md`).

### 1.1 Plano con primer fotograma (FL2VA con una imagen = "I2VA")

```
For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.

integrated_multimodal_description: [Shot 1] Live-action, cinematic, <todo lo visible en el
primer fotograma: tamaño de plano, personas con ropa y posición, lugar, luz>. <la acción en el
tiempo: "Early in the clip…", "As the clip progresses…", "Throughout the remainder…">.
<cámara: tipo + amplitud + velocidad>.

overall_soundscape: <1-4 frases: ambiente, sonidos físicos, respiración; nunca el diálogo>

non_diegetic_music: N/A
```

- Armador: `prompts.oficial_i2va(descripcion, sonido, musica)`.
- **El primer fotograma se describe entero antes de la acción.** Los prompts de
  ejemplo del reescritor oficial tienen 380-730 palabras; los nuestros, 150-420.
- Cámara con el vocabulario de la guía: `Push In / Pull Out`, `Pan`, `Truck`,
  `Tilt`, `Pedestal`, `Arc Shot`, `Tracking Shot`, `Static Shot`,
  `Shake Slightly/Strongly`, `POV`, `Roll`, más `with small/large amplitude` y
  `at slow/fast speed`, en prosa.
- Varios planos dentro de un clip: `[Shot 2] At 00:03.500, the camera cuts to…`
  (el primero sin hora). Los IDs de hablante valen dentro del clip.

### 1.2 Diálogo

```
Then Jack (S1), a man in his early thirties, a deep, low, smooth baritone with a slight rasp,
General American accent, says low and slow: <d>[English] Now moan for me.</d> Exactly as his
voice stops, his lips close and his jaw stops moving; he does not speak again for the rest of the clip.
```

- ID estable `(S1)`, voz descripta la primera vez (edad, timbre, ritmo, acento).
- Dentro de `<d>` sólo la etiqueta de idioma y el texto literal.
- **Labios cerrados antes y después** ("For about the first second his lips stay
  completely closed…", "Exactly as his voice stops…"): es la mitigación que
  reporta la comunidad contra el balbuceo (issue #16155 de ComfyUI).
- Voz en off nativa: `says in an off-screen voiceover: <d>…</d> while her lips
  remain completely closed`.
- Diálogo que cruza un corte: `<scenetrans>`; cortado por el final: `<cutoff>`.

### 1.3 Lo que NO va

- **Listas de negativos.** Los pesos traen la CFG destilada: no hay prompt
  negativo, y en el positivo nombrar algo lo invoca (medido el 10/9 con cactus,
  fuego y gente). Se describe lo que sí pasa.
- **Música compuesta por H3** cuando la música va aparte: `non_diegetic_music: N/A`.
- **El nombre del género de origen** en el estilo (trae subtítulos quemados).
- Flechas, barras, signos `+` y collages de referencia: el modelo los dibuja
  (skills oficiales).

### 1.3 bis · El reescritor propio (17/9/2026): `reescritor.py`

Desde el 17/9 **ningún prompt llega a H3 escrito a mano ni en texto libre**.
`h3pipeline/reescritor.py` hace localmente lo que Context-IR hace en la API:
recibe un *pedido* (duración, formato, estilo, qué se ve en el primer fotograma
—y la imagen misma si ya existe, que GPT mira—, qué pasa, qué se oye, quién dice
qué y en qué idioma) y devuelve un prompt I2VA en el formato oficial, validado:

- la línea de instrucción exacta, los tres campos, un solo `[Shot 1]`;
- cada línea de diálogo **literal** dentro de `<d>[Spanish] …</d>`, un bloque
  por línea, el rótulo del hablante afuera («MONO: Cuéntame.» → `(S1) … <d>[Spanish] Cuéntame.</d>`);
  «(fuera de cuadro)» u «(off)» en el rótulo = `says in an off-screen voiceover`;
- boca visible y moviéndose en el que habla (lo que tapa la boca se aparta
  antes: lección del mono terapeuta, v1 muda con la lapicera en la boca);
- **sin negaciones** (más de dos → reintento), `non_diegetic_music: N/A`,
  largo acorde a la duración.

Si GPT falla dos veces, sale `plantilla()` (el formato oficial armado con los
campos tal cual): el piso es siempre formato oficial. Cuesta ~$0,01-0,03 por
plano (gpt-5.1, 1.700+600 tokens). Dónde corre:

| camino | cuándo |
|---|---|
| short / largo / music video | al traducir el guion (`app/traducir.py`) y otra vez al **empaquetar**, ya con el dibujo: `prompt_h3` + `prompt_h3_de` (huella del pedido) en cada plano; `"prompt_h3_manual": true` lo protege |
| Libre | al tocar «Armar prompt H3» (se ve y se edita) o solo, al generar, si el texto no viene en formato oficial |
| CLI | `python -m h3pipeline reescribir proyecto.json [--forzar] [--solo …]`; `empaquetar --sin-reescribir` lo saltea |

Medido el 17/9 con el short de la bicicleta (4 planos, 5,17 s): 4 de 4 válidos,
2 a la primera y 2 al segundo intento (largo); el mono de 15 s con 5 líneas, a
la primera, 729 palabras.

### 1.4 Context-IR y 2K (API paga, opcional)

- **Context-IR** reescribe un pedido libre al formato oficial. No es open source
  (sistema de varias etapas en servidores de MiniMax). Su salida se puede usar con
  H3 local. ~$0,90/M tokens de entrada y $3,60/M de salida: **$1-4 por 73 clips**.
- **Regenerate-2K** rehace un clip de 768p a 2K con el mismo contexto: $0,05 por
  segundo (~$19 por 377 s). El MP4 tiene que ir crudo, con audio, 24 fps.
  Modera: puede quitar sangre sin avisar.
- Ambos por platform.minimax.io; la API se puede usar desde Argentina.
- **Licencia, zona gris:** los pesos abiertos no permiten *mostrar* salidas en
  EE.UU., UE, Reino Unido ni Corea. Consultar si una competencia se juzga ahí.

## 2 · La voz: 100 % MiniMax y la misma en todos los clips

H3 genera la voz dentro de cada clip, pero **no recuerda voces entre clips**. La
solución oficial es el modelo **Ref2VA**, que acepta hasta 3 audios de
referencia de timbre (2-15 s cada uno). El flujo:

1. **Casting con FL2VA**: 2-3 clips de cada personaje diciendo una frase larga en
   su registro, con la voz descripta en el prompt. Se eligen escuchando.
2. **Recorte**: `python -m h3pipeline.voz_ref <clip.mp4> <ini> <fin> assets/voz_<quien>.wav`
   → 32 kHz estéreo, 2-15 s, largo múltiplo exacto de 800 muestras (bug #15970),
   pico bajo cero (el audio de H3 viene a +2,68 dBFS).
3. **Todos los clips que habla ese personaje en Ref2VA** con `<Picture 1>` =
   primer fotograma, `<Picture 2>` = su hoja, `<Audio 1>` = su voz.

Prompt Ref2VA: seis secciones en orden (`prompts.oficial_ref2va`):
`subject_definitions` (`<Picture 1> is the first frame of [Shot 1]…`,
`<Subject 1> is … as shown in <Picture 2>`, `<Audio 1> is the voice-timbre
reference for <Subject 1> (S1)`), `summary` con
`[keyframe completion + reference generation + audio reference]`,
`retention_analysis` (`fully_preserved`, `reference`), `detailed_description`
(estilo antes de `[Shot 1]`; en el diálogo `using the voice timbre referenced
from <Audio 1>`), `overall_soundscape`, `non_diegetic_music`.

**Riesgos reportados** (no medidos por nosotros): con voz de referencia el
personaje puede balbucear antes o después de la línea y correr los tiempos
(#16155, 2 de 5 bien con la mitigación); la voz de un personaje puede
contagiar a otro en el mismo clip (#15454); con referencias baja el largo seguro
y pasado el límite sale ruido con log de éxito (#15738). **SIN PROBAR** en 5090.

## 3 · ComfyUI: lo que hay que hacer exactamente (código fuente de los nodos)

| | FL2VA | Ref2VA |
|---|---|---|
| nodo | `MiniMaxH3ImageToVideo` (`first_frame`) | `MiniMaxH3ReferenceToVideo` |
| DiT (GGUF) | `MiniMax-H3-FL2VA-Q5_K_M.gguf` | `MiniMax-H3-Ref2VA-Q5_K_M.gguf` (23,9 GB) o `…-Pruned-Q5_K_M.gguf` (14,1 GB) |
| turbo | `minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16` · **8 pasos, shift 6/3** | `minimax_h3_ref2v_turbo_8step_v1.0_768p_comfyui_bf16` (sin documentar; shift 6 supuesto) |
| calidad completa | sin turbo, 20-25 pasos, `res_multistep`, shift 12/3 | ídem, scheduler `beta` o `normal` |

- **Entradas de Ref2VA en formato API: clave plana con punto e índice desde 0**:
  `"ref_images.ref_image_0"`, `"ref_images.ref_image_1"`, `"ref_audios.ref_audio_0"`.
  **Un nombre mal escrito se descarta SIN ERROR** y se genera como si no hubiera
  referencias (#15667). `ref_image_0` es `<Picture 1>`.
- **`audio_vae` conectado**: sin él la voz de referencia no condiciona nada.
- `LoadAudio` lee de `input/`; se sube por el mismo `/upload/image`.
- Ancla dura opcional: `MiniMaxH3AddGuide(frame_idx=0)` con la misma imagen,
  después del nodo de referencias (sin documentar en el cuadro 0: probar A/B).
- `ref_image_size=match` (el de entrenamiento de las turbo); `max` en agosto costó +8 %.
- Ids de la plantilla oficial `video_minimax_h3_r2v.json`: 119 VAE video,
  120 VAE audio, 124 BasicScheduler, 126 BasicGuider, 127 UNET, 128 CLIP,
  131 length, 136 nodo H3, 138 prompt.
- Largos válidos 17k+5 (124 = 5,17 s). El video es 768×1344 en 9:16 (exacto al
  lienzo oficial). Ref2VA con `auto` da 16:9: siempre aspecto explícito.
- Evitar `minimax_h3_ref2va_pruned_fp8_scaled` (metadatos rotos, #15567).
- **Error que tuvimos hasta el 14/9:** la LoRA turbo FL2VA de 4 pasos corría a
  8 pasos y shift 12; la tabla de lightx2v dice 768p = shift 6/3.

Todo implementado en `remoto/runner.py` (campos por plano: `modo`,
`refs_extra`, `voz_ref`, `guia0`, `pasos`, `turbo`, `shift_video`,
`shift_audio`, `scheduler`, `ref_image_size`) y `remoto/setup.sh` (baja Ref2VA
solo si `planos.json` tiene planos `ref2va`, o con `alquilar --ref2va`).

## 4 · Las imágenes con GPT (`gpt-image-2.5-sunburst`)

### 4.1 La prueba de motores (4 cuadros × 3 modelos, $1,25)

| | gpt-image-2 | gpt-image-2.5-flare | gpt-image-2.5-sunburst |
|---|---|---|---|
| aspecto | el más fotográfico | nítido con brillo "IA" | cinematográfico, cálido |
| consistencia con la hoja | media | la mejor | buena |
| tiempo (4 cuadros) | 255 s | 116 s | 241 s |
| tokens de salida | 13.720 | 9.604 | 13.720 |

Elegido por el usuario: **sunburst**. Script: `mis-videos/replica-danza/prueba-motores/prueba.py`.

### 4.2 Lo medido

- **Precio**: $8/M tokens de imagen de entrada, $30/M de salida, $5/M de texto
  (gpt-image-2, 2.5 flare y sunburst igual). **105 imágenes ≈ $6,76.**
- **Las referencias de entrada cuestan más que la salida**: ~4.000 tokens por
  imagen con locación + 1-2 hojas. Para ahorrar, mandar sólo lo necesario.
- **Tier 1: 5 imágenes por minuto** → 429 `rate_limit_exceeded`. Distinto de
  `insufficient_quota` (sin saldo). `frames.generar_openai` espera lo que dice
  la API y reintenta; con `--hilos 4`, 73 imágenes en ~20 min.
- **Salida 1024×1536 (2:3)**: al pasar a 9:16 se pierde ~14 % de los costados.
  Pedir sujeto centrado y nada importante en los bordes laterales.
- **Filtro de OpenAI: rechaza las poses de tono sexual, no la violencia.** Pasaron
  todos los planos con cuchillo en el cuello y sangre. Rechazó: sentada a
  horcajadas, mano apretando la cadera sobre el short, cabeza atrás con él hundido
  en el cuello, piernas alrededor de la cadera. Reescritos como abrazo protector,
  mano en la espalda sobre la camisa y susto hacia la puerta, pasaron.
- **GPT abre los planos**: pedidos de "medium shot" salen de cuerpo entero aun con
  refuerzos. Lo que funcionó: rehacer con "crop like a tight TV close two-shot…
  the bottom edge cuts across their chests" y, si igual corta a la cintura,
  **recortar el 80 % superior** de la imagen (≈ ×1,25, nítido a 768×1344).
- **Continuidad de vestuario entre planos**: la hoja de modelo arrastra lo que
  tiene (el sombrero de Jack aparecía después de habérselo sacado). Se escribe
  el estado explícito ("BARE-HEADED with NO hat").
- **Hojas aprobadas se reusan tal cual** como `m_*.png`; las variantes de
  vestuario se generan con la hoja aprobada como referencia (misma cara).
- **Revisión contra el original**: `revisar.py` pone cada encuadre al lado del
  cuadro medio de su toma original, recortado a 9:16 como lo recibe H3. De 73, en
  la primera tanda pasaron 55.

## 5 · Replicar un video existente toma por toma

1. **Cortes**: ffmpeg `select=gt(scene,0.20)`, fundir tramos < 0,5 s, y **mirar
   entrada/medio/salida de cada toma**: el detector se salta cortes (dos en este
   episodio), que se ubican con cuadros cada 0,2 s.
2. **Voz**: Whisper medium con tiempos **por palabra** (los subtítulos quemados
   del original van adelantados respecto de la voz). Así se sabe qué palabra cae
   en qué toma y si la boca se ve.
3. **Un clip por ENCUADRE, no por toma** (`clip_de`). Si la cámara vuelve al mismo
   encuadre, las tomas salen del mismo clip con otro `usa`, respetando el tiempo
   real entre ellas cuando entra en 4,87 s.
4. **En los clips que hablan, la boca manda el `usa`**:
   `usa_ini = ONSET + (inicio_toma − t0_de_la_línea)`, con el arranque de la voz
   pedido a ~1 s y medido después de generar (`ONSETS_MEDIDOS`).
5. **Las placas de nombre** (serif itálica en la presentación de cada personaje)
   van en post.
6. **Audio del original**: demucs separa voces (`vocals.wav`) de música+efectos
   (`ambiente.wav`). Medido: en tramos sin habla la pista de voces queda 9 dB
   debajo de la base; **jadeos, llantos y gritos sin palabras se van con las
   voces**, así que al mezclar faltan en la base.

Implementación de referencia: `mis-videos/replica-danza/` (`tomas.py`,
`armar.py`, `oficial.py`, `revisar.py`) y `referencias/danza-peligrosa/`
(`tomas.py`, `MAPA.md`, `transcripcion.json`).

## 6 · Cambios del módulo (14/9/2026)

| dónde | qué |
|---|---|
| `proyecto.py` | `"idioma"` ("es"/"en"); `prompt_h3` (prompt oficial tal cual); `dibujo` (reusar el primer fotograma de otro plano); pasan a `planos.json`: `modo`, `refs_extra`, `voz_ref`, `guia0`, `pasos`, `turbo`, `shift_video`, `shift_audio`, `scheduler`, `ref_image_size`; `validar` no marca salto de eje entre tomas del mismo clip; el aviso de 90 s sólo si se declara Reels |
| `prompts.py` | `IDIOMAS`; `oficial_i2va`, `oficial_ref2va` |
| `frames.py` | `modelo_openai`, `hilos`; espera y reintenta el 429; tokens al log; un error suelto no tira el lote |
| `voz_ref.py` | nuevo: la voz de referencia para Ref2VA |
| `empaquetar.py` | copia `refs_extra` y `voz_ref` al paquete |
| `remoto/runner.py` | modo Ref2VA, LoRAs 768p con su shift, parámetros por plano, orden por modo en cada placa |
| `remoto/setup.sh` | Ref2VA automático según `planos.json`; LoRAs de lightx2v; sale el fp8 roto |
| `vast.py` / CLI | `alquilar --ref2va`, `generar --ref2va`; `frames --modelo-openai --hilos` |

## 7 · Abierto

- **Todo el camino Ref2VA con voz corre por primera vez en la muestra** de la
  réplica (`armar.py --muestra A` y `--muestra B`).
- La turbo Ref2VA 8 pasos 768p no tiene especificación publicada.
- Si 20 pasos sin turbo se ven mejor que 8 con turbo (regla 32 sigue sin cerrar).
- Si el ancla `MiniMaxH3AddGuide` en el cuadro 0 mejora o empeora Ref2VA.
- Context-IR y Regenerate-2K no se probaron.
