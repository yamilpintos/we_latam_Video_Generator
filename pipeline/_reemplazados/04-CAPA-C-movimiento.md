# Capa C — Movimiento: Veo 3 y stills animados

Convierte las imágenes de la Capa B en metraje. Dos técnicas con costos muy distintos.

---

## 1. Reglas de asignación

### Va a **Veo 3** cuando se cumple al menos una:

- Hay **locomoción** del sujeto: camina, corre, cae, se da vuelta, pelea.
- Hay un **cambio de estado visible**: una puerta se abre, el fuego prende, el agua sube,
  algo se rompe.
- Hay **interacción entre dos personajes**.
- Es el **gancho** (primeros 15 s) o el **clímax** de un acto.
- Es un plano corto (≤ 4 s) que necesita energía.

### Va a **still animado** cuando:

- Es paisaje, establishing o vista aérea.
- Es un retrato o primer plano contemplativo, sin acción.
- El texto narrado es expositivo y se sostiene > 6 s sobre la misma idea.
- Es un detalle de objeto.
- Es una transición atmosférica: niebla, polvo, lluvia leve, brasas.

### Verificación de ratio

Contá los `VEO` y comparalos con el preset (30 % del tiempo de pantalla por defecto).
Si te pasaste, el primer candidato a degradar a still es siempre un plano de **exposición larga**;
el último, el gancho.

---

## 2. Veo 3 — image-to-video

**Restricciones:** clips de **10 segundos**, 16:9, 24 fps. Si la acción necesita más, se parte en
dos clips con continuidad (ver §2.3).

> **Se usan los 10 segundos completos, sin recortar.** Es el máximo por generación: usar menos
> es tirar créditos. Eso obliga a diseñar la acción para que llene el clip entero (§2.5).

### 2.1 Anatomía del prompt de movimiento

```
1. QUÉ HACE EL SUJETO — un movimiento, con inicio y final claros
2. QUÉ HACE LA CÁMARA — un solo movimiento
3. QUÉ SE MUEVE EN EL ENTORNO — elementos secundarios
4. RITMO — lento / continuo / con una aceleración
5. NEGATIVOS OBLIGATORIOS
```

Ejemplo:

```
La mujer de la bufanda roja gira lentamente la manija y empuja la puerta de hierro,
que cede hacia adentro; ella da un paso al interior y se detiene en el umbral.
Cámara: dolly in muy lento siguiéndola, sin cortes.
Entorno: la niebla se cuela por la puerta abierta, la bufanda ondea levemente por la
corriente de aire.
Ritmo: lento y sostenido, sin cambios bruscos.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo,
la paleta y el rostro de la imagen de origen sin alterarlos.
```

### 2.2 Los negativos no son opcionales

Terminá **todos** los prompts de Veo con:

```
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y
el rostro de la imagen de origen sin alterarlos.
```

Veo 3 genera audio nativo. Si no le pedís silencio, te mete voces inventadas en inglés que
chocan con tu voz en off. **En el editor, silenciá la pista de audio de todos los clips de Veo**
salvo que decidas conservar un ambiente puntual.

### 2.3 Movimientos de cámara — uno solo por clip

Todos duran 10 s, así que la elección es por efecto, no por duración:

| Movimiento | Efecto | Nota a 8 s |
|---|---|---|
| Dolly in lento | Acercamiento, tensión creciente | El más seguro, pero a 10 s conviene un acento a mitad |
| Dolly out | Revelación de contexto, soledad | Muy bueno para cerrar secuencia |
| Pan lateral | Recorrer un espacio | Necesita fondo con contenido o se ve vacío |
| Tilt up | Escala, imponencia | A 10 s se queda corto solo: combinalo con un sujeto que entre en cuadro |
| Handheld sutil | Realismo, inquietud | Se puede sumar a cualquiera de los otros |
| Cámara fija | Deja que la acción hable | **Solo si la acción llena los 10 s**, si no queda muerto |
| Orbit / arc | Presentación de sujeto | El que mejor justifica los 10 s completos |

Dos movimientos en un mismo clip (ej. "pan y después zoom") producen deriva y artefactos.

### 2.4 Acciones de más de 8 s

Partir en dos clips consecutivos:
- Clip A: imagen `IMG_S04-P02a`, la acción hasta la mitad.
- Clip B: **exportá el último frame del clip A** y usalo como imagen de entrada del clip B.
  Es la única forma de continuidad exacta.
- En el timeline quedan como `S04-P02a` y `S04-P02b`.

### 2.5 Cómo se diseña una acción de 10 segundos exactos

Como no se recorta nada, los dos extremos del clip son parte del plano:

- **Fotograma 1:** el movimiento **ya está en curso**. Nada de medio segundo de nave quieta antes
  de arrancar. En el prompt: *"El movimiento ya está en curso desde el primer fotograma."*
- **Fotograma final:** una **pose sostenida**, no un gesto a medio hacer. Si el clip termina con
  algo en el aire, el corte se siente arrancado. En el prompt: *"Termina en una posición estable
  y sostenida."*
- **En el medio:** un solo arco de acción con un momento de acento alrededor del segundo 5–6.
  Un movimiento que se agota en 4 s deja 6 s de relleno visible. Diez segundos es mucho: si el
  movimiento no tiene desarrollo interno, se nota.

**No se puede arreglar en edición.** Si el arranque o el cierre salieron mal, se regenera el clip.
Por eso la previsión de reintentos de Veo es **1,3×**, mayor que la de imágenes.

---

## 3. Stills animados — DepthFlow, todos de 5 segundos

Los planos de 5 s **no se hacen a mano en el editor**. Se renderizan con
[DepthFlow](https://github.com/BrokenSource/DepthFlow): open source, corre local, sin créditos y
sin marca de agua. Calcula un mapa de profundidad de la imagen y mueve una cámara virtual en 3D
sobre ella con shaders GLSL. No genera contenido nuevo — mueve el que ya está.

La diferencia con el Ken Burns clásico es real: el Ken Burns escala una imagen plana, DepthFlow
desplaza el punto de vista en un espacio con profundidad, así que el fondo y el primer plano se
mueven a distinta velocidad. Es parallax de verdad, no un zoom.

### 3.1 Instalación

DepthFlow necesita `moderngl`, que **no tiene ruedas para Python 3.14** y falla al compilar. Hay
que darle un intérprete propio:

```bash
pip install uv
python -m uv venv --native-tls --python 3.12 .venv-depthflow
python -m uv pip install --native-tls --python .venv-depthflow depthflow truststore
```

El `--native-tls` no es opcional acá: sin él `uv` no confía en la CA del proxy y no puede bajar
el intérprete.

**ffmpeg** hace falta y DepthFlow no lo trae. La forma más limpia de conseguirlo sin instalar
nada a nivel sistema:

```bash
pip install imageio-ffmpeg
python -c "import imageio_ffmpeg, shutil; shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), '.venv-depthflow/Scripts/ffmpeg.exe')"
```

**Certificados.** La primera corrida descarga el modelo de profundidad de HuggingFace usando
`requests`, que usa el bundle de `certifi` y no el almacén de Windows. Con un proxy TLS de por
medio falla con `SSLCertVerificationError` aunque `curl` funcione. Por eso los scripts inyectan
`truststore` antes de importar nada.

**Rendimiento medido** en esta máquina, sin GPU NVIDIA: 8 s a 1920×1080, 24 fps y SSAA 2.0 tardan
**entre 15 y 20 segundos** por clip. Los 32 planos de 5 s salen en unos 6 minutos.

### 3.1b El parámetro `inpaint` no rellena: marca

`state.inpaint.limit` **pinta de verde** los huecos que deja el desplazamiento, para que los
mandes a una herramienta de inpainting externa. No los rellena. Si lo activás sin saberlo, el
render sale con parches verdes. Dejalo en cero.

### 3.2 Tres sentidos, no nueve técnicas

**El criterio: la cámara se mueve en la dirección en la que va la atención.**

| Sentido | Cuándo | Qué hace |
|---|---|---|
| **`acercar`** | El plano **concentra**: hay una cosa que mirar | `zoom` 1,00 → 0,865 · el foco se cierra |
| **`alejar`** | El plano **amplía**: importa el contexto, la escala o lo que implica | `zoom` 0,865 → 1,00 · el foco se abre |
| **`quieto`** | El peso está en la voz, o el sujeto ya se mueve solo | Solo respira |

**Intensidad fija en 0,45.** Calibrada mirando. No la subas sin volver a mirar: por
encima de 0,7 el acercamiento empieza a costar nitidez, y el problema no es el
parámetro sino la resolución de la imagen de origen.

#### Cómo decidir, leyendo el prompt de la imagen

→ **acercar** si el prompt dice *plano detalle*, *inserto*, *primer plano*,
*primerísimo*, *macro*, "un documento", "una pieza", "el rostro de". También cuando
el plano presenta por primera vez un objeto que la historia va a usar.

→ **alejar** si dice *plano general*, *establishing*, *vista orbital*, *cenital*,
"la sala entera", "el paisaje". También en cierres de secuencia, y cuando el sujeto
tiene que verse pequeño: soledad, abandono, escala.

→ **quieto** si es una placa contemplativa, si el sujeto ya tiene movimiento propio
—una impresora imprimiendo, datos corriendo— o si encima suena la frase más
importante del bloque.

#### La regla que está por encima del criterio

**No repetir el sentido en planos consecutivos.** Dos acercamientos seguidos y el
video respira en una sola dirección. Cuando el criterio pide el mismo sentido dos
veces, el segundo pasa a `quieto`. `depthflow_batch.py --dry-run` lo verifica y falla
si pasa.

Reparto sano para 32 planos: **13 acercar / 13 alejar / 6 quieto**.

#### Los movimientos especiales

Grúa, travelling lateral y retirada amplia viven en
[`tools/depthflow_cine.py`](../tools/depthflow_cine.py). **No entran en el reparto
por defecto**: son excepciones que se eligen a mano cuando un plano concreto las
justifica. Un travelling en medio de una secuencia de acercamientos y alejamientos
llama la atención sobre sí mismo.

### 3.3 Render en lote

[`tools/depthflow_batch.py`](../tools/depthflow_batch.py) recorre una shotlist CSV
(`id,tecnica`), busca `IMG_<id>.png` y escribe `MOV_<id>.mp4` de 5,0 s a 1920×1080 y **24 fps**
—los mismos que Veo 3, para que no haya conversión de framerate en el montaje—.

```bash
uv run tools/depthflow_batch.py \
    --shotlist tools/shotlist-mco.csv \
    --images   output/mars-climate-orbiter/img \
    --out      output/mars-climate-orbiter/mov \
    --ssaa 2.0
```

Antes de renderizar, `--dry-run` valida la shotlist: técnicas inexistentes, IDs duplicados,
imágenes que faltan, y **la regla anti-monotonía** — si dos planos consecutivos usan la misma
técnica, falla y te lo dice.

Notas de calidad, de la doc oficial:
- **SSAA 2.0** para el export final (renderiza al doble y baja de escala). Es exactamente 4× de
  GPU. Con 1,5 alcanza para revisar.
- La calidad depende sobre todo de que el **mapa de profundidad relativa** sea bueno, no de la
  silueta. Imágenes con capas claras (primer plano / sujeto / fondo) rinden mucho mejor — que es
  justo lo que pide el prompt de la Capa B.
- Las imágenes de ChatGPT salen a 1536 px de ancho. Para 1080p conviene **escalarlas a 1920×1080
  antes** de pasarlas por DepthFlow, o vas a perder algo de nitidez.

### 3.4 Lo que DepthFlow no hace

Sigue haciendo falta el editor para:
- **Overlays atmosféricos** (lluvia, polvo, niebla, brasas) en modo *screen* al 25–40 %
- **Rack focus falso**, si lo querés
- Los planos **GFX**, que son motion graphics y no salen de una imagen

### 3.2 Regla anti-monotonía

Con la grilla fija esta regla pasa de recomendable a **obligatoria**: si todos los planos duran
lo mismo *y* se mueven en el mismo sentido, el ojo detecta el patrón en menos de 30 segundos.

### 3.3 Plantilla de 5 s en el editor

Armá **una sola vez** un preset por técnica (composición de 5 s con los keyframes ya puestos) y
después solo cambiás la imagen adentro. Es lo que baja el tiempo de la Capa C de 3 horas a 40
minutos a partir del segundo video.

---

## Formato de salida — `05-movimiento.md`

````markdown
### S01-P02 · 00:10.0 → 00:15.0 · **5 s · STILL** — Ken Burns push-in
**Origen:** `IMG_S01-P02.png` → **Salida:** `MOV_S01-P02.mp4`
- Escala 100 % → 110 %, centro de escala sobre el rostro de MARA (x 48 %, y 40 %)
- Ease in-out en toda la duración
- Overlay de niebla al 30 %, modo screen, deriva lenta hacia la derecha
- **Anterior fue pan lateral** ✓ (no se repite técnica)

---

### S01-P03 · 00:15.0 → 00:25.0 · **10 s · VEO 3** (se usan los 10 completos)
**Origen:** `IMG_S01-P03.png` → **Salida:** `VID_S01-P03.mp4`

```
La mujer de la bufanda roja gira la manija con las dos manos y empuja la puerta de hierro,
que cede hacia adentro con resistencia; ella da un paso al interior y se detiene en el
umbral, mirando hacia la oscuridad.
Cámara: dolly in muy lento y continuo siguiéndola, sin cortes.
Entorno: la niebla se cuela por la puerta abierta, la bufanda ondea por la corriente de aire.
Ritmo: el movimiento ya está en curso desde el primer fotograma. Un solo arco continuo, con
el momento de mayor esfuerzo alrededor de la mitad del clip. Termina en una posición estable
y sostenida, sin gestos a medio hacer.
Sin diálogo, sin voces, sin música, sin texto en pantalla. Mantener el estilo, la paleta y
el rostro de la imagen de origen sin alterarlos.
```

**En el editor:** silenciar la pista de audio del clip.
**Si el primer o el último fotograma salen mal:** regenerar. No se recorta.
````
