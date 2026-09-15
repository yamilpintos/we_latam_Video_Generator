# Capa B2 — Planos de imagen animada · imagen + movimiento de cámara

Los planos de **5 segundos**. Una imagen en ChatGPT y un render local con DepthFlow. **Sin
créditos, sin marca de agua.** Son el 80 % del video.

Este documento es autosuficiente: arriba el prompt maestro, abajo el criterio y la plantilla.

---

# PROMPT MAESTRO · ChatGPT — imágenes para animar

Se pega **una sola vez** en el primer mensaje del chat, junto con la imagen madre de la cámara
y las placas de sujeto que apliquen.

```
Vas a generar imágenes que después se animan en 3D: un programa calcula el mapa de profundidad
y mueve una cámara virtual sobre ellas. No son ilustraciones planas.

Eso cambia dos cosas respecto de una imagen normal:

1. TRES CAPAS DE PROFUNDIDAD CLARAS Y SEPARADAS. Tiene que haber algo definido en primer plano,
   el sujeto en el medio, y un fondo distinto detrás. Es lo que produce el paralaje. Una imagen
   con todo a la misma distancia se anima como una postal deslizándose.

2. AIRE ALREDEDOR DEL SUJETO. El movimiento por defecto es un acercamiento: si el sujeto ya
   llena el encuadre, no hay a dónde entrar. Dejá margen.

Además: los bordes del encuadre son la zona frágil. Lo más cercano a la cámara es lo que más se
desplaza y lo que se estira si el movimiento es amplio. Evitá poner detalle fino y crítico
pegado al borde inferior.

Cuando mencione LA CÁMARA, reproducí exactamente el espacio de la imagen de referencia adjunta:
misma arquitectura, misma paleta, misma dirección y temperatura de luz, mismos materiales.
No inventes un lugar distinto.

Respondé solo con la imagen.

<STYLE TOKEN>
```

---

# 1. Cuándo un plano va acá

Todo lo que no cumpla las condiciones de Veo (Capa B1 §1):

- Paisaje, establishing, vista aérea.
- Retrato o primer plano contemplativo, sin acción.
- Detalle de objeto.
- Texto narrado expositivo que se sostiene sobre la misma idea.
- Transición atmosférica.

Un plano que dudás si va a Veo, va acá. Cuesta cero.

---

# 2. El criterio de movimiento

> **La cámara se mueve en la dirección en la que va la atención.**

| Sentido | Cuándo | Qué hace |
|---|---|---|
| **`acercar`** | El plano **concentra**: hay una cosa que mirar | `zoom` 1,00 → 0,865 · el foco se cierra |
| **`alejar`** | El plano **amplía**: importa el contexto, la escala o lo que implica | `zoom` 0,865 → 1,00 · el foco se abre |
| **`quieto`** | El peso está en la voz, o el sujeto ya se mueve solo | Solo respira |

**Intensidad fija: 0,45.** Calibrada mirando. Por encima de 0,7 el acercamiento empieza a costar
nitidez, y el problema no es el parámetro sino la resolución de la imagen de origen.

### Cómo decidir, leyendo el prompt de la imagen

→ **acercar** si el prompt dice *plano detalle*, *inserto*, *primer plano*, *primerísimo*,
*macro*, "un documento", "una pieza", "el rostro de". También la primera vez que aparece un
objeto que la historia va a usar.

→ **alejar** si dice *plano general*, *establishing*, *vista orbital*, *cenital*, "la sala
entera", "el paisaje". También en cierres de secuencia, y cuando el sujeto tiene que verse
pequeño: soledad, abandono, escala.

→ **quieto** si es una placa contemplativa, si el sujeto ya tiene movimiento propio —una
impresora imprimiendo, datos corriendo— o si encima suena la frase más importante del bloque.

### La regla que manda sobre el criterio

**No repetir el sentido en planos consecutivos.** Dos acercamientos seguidos y el video respira
en una sola dirección; el ojo detecta el patrón en menos de medio minuto. Cuando el criterio pide
el mismo sentido dos veces, el segundo pasa a `quieto`.

`depthflow_batch.py --dry-run` lo verifica y falla si pasa.

Reparto sano para 40 planos: **~16 acercar / ~16 alejar / ~8 quieto**.

---

# 3. Cómo se reparte el movimiento

Medido sobre imágenes reales. Los parámetros no se comportan igual:

| Parámetro | Qué es | ¿Desgarra? |
|---|---|---|
| `zoom` | Campo de visión. **Va al revés: 0,75 acerca, 1,30 aleja** | No, nunca |
| `center` | Paneo plano | No, nunca |
| `height` | Empuje en profundidad | **Sí** — estira el plano más cercano |
| `offset` | Paralaje lateral | **Sí**, y es el más visible: chorros horizontales |

**La magnitud la lleva `zoom`.** `height` entra en dosis mínima y es lo que diferencia esto de
escalar la imagen en el editor: el primer plano se abre más rápido que el fondo. `steady` alto
protege lo cercano.

Subir `height` u `offset` "para que se note más" es exactamente lo que rompe el primer plano.

---

# 4. DepthFlow

### Instalación

`moderngl` no tiene ruedas para Python 3.14 y falla al compilar. Hay que darle un intérprete
propio:

```bash
pip install uv
python -m uv venv --native-tls --python 3.12 .venv-depthflow
python -m uv pip install --native-tls --python .venv-depthflow depthflow truststore
```

El `--native-tls` no es opcional: sin él `uv` no confía en la CA del proxy y no baja el
intérprete.

**ffmpeg**, que DepthFlow necesita y no trae:

```bash
pip install imageio-ffmpeg
python -c "import imageio_ffmpeg, shutil; shutil.copy(imageio_ffmpeg.get_ffmpeg_exe(), '.venv-depthflow/Scripts/ffmpeg.exe')"
```

**Certificados:** la primera corrida baja el modelo de profundidad de HuggingFace con `requests`,
que usa el bundle de `certifi` y no el almacén de Windows. Con un proxy TLS falla aunque `curl`
funcione. Los scripts inyectan `truststore` antes de importar nada.

### Render en lote

```bash
# validar primero: técnicas, IDs, imágenes que faltan, sentidos repetidos
uv run tools/depthflow_batch.py --shotlist tools/shotlist.csv \
    --images output/<proyecto>/img --out output/<proyecto>/mov --dry-run

# render final
uv run tools/depthflow_batch.py --shotlist tools/shotlist.csv \
    --images output/<proyecto>/img --out output/<proyecto>/mov --ssaa 2.0
```

Salida: 1920×1080 a **24 fps**, los mismos de Veo 3, para que no haya conversión de framerate.

**Rendimiento medido**, sin GPU NVIDIA: 15–20 s por clip a 1080p con SSAA 2.0. Cuarenta planos
salen en unos 8 minutos.

### Dos trampas

**`inpaint.limit` no rellena los huecos: los pinta de verde**, para que los mandes a una
herramienta de inpainting externa. Si lo activás sin saberlo, el render sale con parches verdes.
Dejalo en cero.

**Barrer `isometric` durante el plano** cambia la proyección y se lee como plataforma giratoria
de producto, no como cámara. Queda fijo en 0,45.

### Antes de renderizar

Escalá las imágenes a **1920×1080**. ChatGPT entrega 1536 px de ancho y DepthFlow no inventa
resolución que no está.

---

# 5. Plantilla por plano

````markdown
### <ID> · <IN> → <OUT> · 5 s · CÁMARA <X> · **<acercar | alejar | quieto>**
**Imagen:** `IMG_<ID>.png` → **Clip:** `MOV_<ID>.mp4`
**Adjuntar al generar:** madre de la cámara `<X>` + placas de sujeto
**Motivo del sentido:** <una línea: por qué concentra, amplía o se queda quieto>

**Prompt de imagen (ChatGPT):**
```
<Tipo de plano y ángulo>. <Sujeto, anclado a su placa si corresponde>, <estado congelado:
un solo verbo>.
<Primer plano: qué hay más cerca de la cámara>. <Fondo: qué hay detrás y a qué distancia>.
Luz: <fuentes visibles y dirección>.
```

**Capas de profundidad:** fondo = `<...>` · medio = `<...>` · frente = `<...>`
````

El campo de capas no es adorno: es lo que hace que el paralaje funcione, y sirve de checklist al
revisar la imagen.

---

# 6. Control de calidad

Rechazá y regenerá si:

- El espacio no coincide con la madre de su cámara.
- Aparece texto, número legible o logotipo.
- **La imagen es plana**: no se distinguen tres distancias. Se va a animar como una postal.
- El sujeto llena el encuadre y el sentido asignado es `acercar`. No hay a dónde entrar.
- Hay detalle fino y crítico pegado al borde inferior — es la zona que se estira.

Después de renderizar, mirá los últimos fotogramas: si el primer plano se convirtió en chorros
horizontales, el movimiento fue demasiado para esa imagen. Bajá la intensidad de ese plano o
pasalo a `quieto`.
