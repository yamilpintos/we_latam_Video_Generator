# MiniMax H3 en RunPod

Cómo levantar un pod con ComfyUI y H3, generar los 10 planos desde tu PC con un
comando, y apagarlo.

Escrito el 2026-08-13. H3 salió con pesos abiertos el 3 de agosto, así que todo
esto es reciente: si algo no coincide, ganá vos y corregí el documento.

---

## Lo que vas a tener al final

Un pod que prendés en dos minutos, y desde acá:

```
python tools/h3_comfy.py --url https://TUPOD-8188.proxy.runpod.net --todos
```

Eso sube cada imagen semilla, le mete el prompt del plano, genera el clip de
10 segundos y lo baja a `output/mars-climate-orbiter/h3/`. Los diez, seguidos,
sin tocar ComfyUI.

## Lo que cuesta

| | |
|---|---|
| RTX 5090, Community Cloud | **0,69 US$/h** |
| RTX 5090, Secure Cloud | 0,99 US$/h |
| Network Volume | 0,07 US$/GB/mes — 100 GB = **7 US$/mes** |
| Primera sesión, con instalación | ~2 o 3 horas de pod ≈ **2 US$** |

El volumen **se cobra siempre**, con el pod prendido o apagado. Es el precio de
no volver a bajar 42 GB cada vez.

> **La trampa.** Se paga por hora prendida, no por clip generado. Un pod olvidado
> toda la noche son 12 × 0,69 = **8,28 US$**, más que todo el trabajo del día.
> Apagalo. Siempre.

---

## Paso 0 · Cuenta y crédito

[runpod.io](https://runpod.io) → cuenta con Google o GitHub → **Billing** →
cargá 10 US$. Alcanza para varios videos.

## Paso 1 · El Network Volume

**Storage → New Network Volume.** Pedí **100 GB**.

Los pesos son 42,47 GB, pero no alcanza con eso. HuggingFace puede escribir
primero en su caché y después copiar al destino: durante la descarga podés
necesitar el doble. Sumale ComfyUI con su entorno de Python (10-15 GB si la
plantilla lo instala en el volumen). Los mp4 de salida no cuentan: un clip de
10 s a 768p pesa ~10 MB.

Con 60 GB te arriesgás a quedarte sin lugar al 90% de bajar 42 giga. Los 2,80
US$/mes de diferencia valen no repetir eso.

Tres cosas más que conviene saber antes de apretar el botón:

- **Se monta en `/workspace`.** Todo lo que pongas ahí sobrevive al pod.
- **Queda atado a una región.** Elegí una donde haya 5090 disponibles, porque
  después los pods solo pueden salir de ese datacenter.
- **Se adjunta al crear el pod, nunca después.** Si te olvidás, hay que borrar el
  pod y rehacerlo. Perdés lo que hayas bajado.

Se puede agrandar más adelante, achicar no.

## Paso 2 · El pod

**Pods → Deploy.**

| Campo | Qué poner |
|---|---|
| GPU | **RTX 5090** (32 GB) |
| Tipo | Community Cloud — 0,69 US$/h |
| Plantilla | **ComfyUI** (la oficial de RunPod) |
| Network Volume | el del paso 1 — **acordate de adjuntarlo acá** |
| Puertos HTTP | 8188 |
| RAM de sistema | **mirá que tenga 96 GB o más** |

Lo de la RAM no es capricho: H3 entra y sale de la VRAM todo el tiempo y se
apoya en la memoria del host. Los reportes hablan de **75 a 93 GB de RAM de
sistema**. Con 64 GB podés tener el pod colgado a mitad de una generación.
De VRAM usa ~26 GB de pico, así que en los 32 de la 5090 entra, pero justo:
por eso el CUDA OOM aparece apenas subís la resolución.

Al desplegarse te da una URL del estilo
`https://abc123def-8188.proxy.runpod.net`. Esa es la que le vas a pasar al
script y la que abrís en el navegador para ver ComfyUI.

Si no hay 5090 libres en Community, o esperás o pagás Secure a 0,99.

## Paso 3 · Los pesos

Abrí la terminal del pod (botón **Connect → Web Terminal**).

Primero mirá qué hay en el repo, porque las rutas internas pueden tener prefijo:

```bash
pip install -q "huggingface_hub[cli]"
python -c "from huggingface_hub import list_repo_files; \
print('\n'.join(list_repo_files('Comfy-Org/MiniMax-H3')))"
```

Con las rutas a la vista, bajá los cuatro archivos. Estos son los de la
configuración cuantizada, que es la que entra en una 5090:

| Archivo | Va en | Pesa |
|---|---|---|
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | `models/diffusion_models/` | 20,97 GB |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `models/text_encoders/` | 15,69 GB |
| `minimax_h3_video_vae_fp16.safetensors` | `models/vae/` | 5,21 GB |
| `minimax_h3_audio_vae_fp32.safetensors` | `models/vae/` | 0,61 GB |

**42,47 GB en total.** El `fl2va` es el de texto-a-video e imagen-a-video, que es
el que te sirve. El `ref2va` es otro checkpoint aparte, para generación con
referencias: son 21 GB más y por ahora no lo necesitás.

Las otras variantes que existen, por si alguna vez hace falta:

| Variante | Pesa | Para qué |
|---|---|---|
| BF16 completo | 123,6 GB | precisión original, pide 4×H100 — no es para una 5090 |
| **INT8 podado** | **42,47 GB** | la de la tabla de arriba |
| NVFP4 | 31,7 GB | la más chica vista corriendo en una 5090 |
| + Ref2VA | +20,97 GB | generación con imágenes/video/audio de referencia |

```bash
CU=/workspace/ComfyUI          # verificá la ruta real: puede ser /workspace/comfyui
hf download Comfy-Org/MiniMax-H3 --include "*fl2va_pruned_int8_convrot*" \
   --local-dir $CU/models/diffusion_models
hf download Comfy-Org/MiniMax-H3 --include "*qwen3vl_32b*nvfp4_awq*" \
   --local-dir $CU/models/text_encoders
hf download Comfy-Org/MiniMax-H3 --include "*_vae_*" \
   --local-dir $CU/models/vae
```

Si el `--include` deja los archivos dentro de subcarpetas (`split_files/…`),
subilos un nivel: ComfyUI los busca sueltos en cada carpeta.

```bash
find $CU/models -name "*minimax*" -o -name "*qwen3vl*" | xargs ls -lh
```

## Paso 4 · Verificar ComfyUI

Los nodos de H3 existen desde **ComfyUI 0.30.0**. Si la plantilla del pod trae
una anterior, actualizala y reiniciá.

Abrí la URL del pod en el navegador y andá a **Template Library › Video**. Tienen
que aparecer tres plantillas de MiniMax H3: **I2V**, **T2V** y **R2V**. Si no
están, la versión es vieja.

La que te importa es **I2V** (image-to-video): tu pipeline parte siempre de una
imagen semilla.

## Paso 5 · La prueba de humo

Antes de cualquier otra cosa, que genere **algo**. Cargá la plantilla I2V, subile
una imagen cualquiera, y poné los parámetros chicos:

- resolución **864 × 480** (16:9 a 0,4 MP)
- **5 segundos**
- **20 pasos**

Dale Queue y esperá. **Cronometralo.** Referencias publicadas por otra gente,
para que sepas si estás en rango:

| Hardware | Config | Tiempo |
|---|---|---|
| RTX 3060 12 GB | 864×480, 124 frames, 20 pasos | < 9 min |
| RTX 4090 Laptop 16 GB | 960×540, 5 s, 20 pasos, con SageAttention | 182 s |
| RTX 5090 (NVFP4) | 864×480, 10,1 s, 10 pasos | 175 s |

Si tarda mucho más que eso, algo está mal: probablemente esté haciendo offload
contra disco.

## Paso 6 · La medición que importa

Esta es la razón de ser de la primera sesión, y la única forma de contestar la
pregunta que dejamos abierta. Generá **el mismo plano tres veces**, a
**1344 × 768** (16:9 nativo, 0,98 MP), cambiando **solo** la duración:

| # | Duración | Anotá |
|---|---|---|
| 1 | 5 s | segundos que tardó |
| 2 | 10 s | segundos que tardó |
| 3 | 15 s | segundos que tardó |

**Si el de 10 s tarda el doble que el de 5 s**, escala lineal y la cuenta que
hicimos vale: ~0,13 US$ por clip, y el pod le gana a la API por goleada.

**Si tarda mucho más del doble**, la atención escala peor que lineal —
que es lo normal en estos modelos— y hay que rehacer los números. Puede que
convenga generar de a 5 segundos y unir dos clips, o directamente que el pod no
valga la pena.

Pasame los tres números y recalculo.

## Paso 7 · Exportar el workflow

Con la plantilla I2V andando y ya configurada como te gusta, andá a
**Workflow › Export (API)**. Ojo: **Export (API)**, no *Save*. Son formatos
distintos y el script rechaza el equivocado.

Guardá ese JSON en tu PC como `tools/h3_workflow.json`.

Después, desde acá:

```
python tools/h3_comfy.py --nodos
```

Te lista los nodos del grafo con sus IDs. El script busca solo el nodo de H3 y
desde ahí sigue los cables hasta el prompt y la imagen, así que normalmente no
hay que configurar nada. Si se confunde, se lo decís a mano:

```
python tools/h3_comfy.py --url ... --id S01-P04 --nodo-prompt 6 --nodo-imagen 9
```

## Paso 8 · Generar

```bash
# primero uno solo, en chico, para ver que la cadena entera funciona
python tools/h3_comfy.py --url https://TUPOD-8188.proxy.runpod.net --id S01-P04 --prueba

# después los diez, en nativo
python tools/h3_comfy.py --url https://TUPOD-8188.proxy.runpod.net --todos
```

Los mp4 caen en `output/mars-climate-orbiter/h3/` como `VID_<id>.mp4`. Los que ya
existen se saltean, así que si se corta a mitad, volvés a correr el mismo comando
y sigue donde quedó.

Al final imprime cuántos minutos de pod consumió. Multiplicá por 0,69 y tenés lo
que gastaste.

## Paso 9 · Apagar

**Stop** deja de cobrar la GPU pero sigue cobrando el disco del pod.
**Terminate** lo borra del todo. Como los pesos están en el Network Volume,
podés terminar el pod tranquilo: el próximo lo levantás con el volumen y ya está
todo ahí.

---

## Dos cosas que te van a morder

**El clip sale un poco más largo del que pediste.** H3 alinea a una grilla de
frames: 5 segundos se vuelven ~124 frames, o sea 5,17 s reales. Tus 10 segundos
probablemente salgan ~10,1. Como tu timeline está clavado al segundo, hay que
recortar la cola en el editor. No es un error, es cómo funciona.

**Genera audio.** H3 saca video y audio estéreo de 32 kHz en la misma pasada. Vos
lo vas a silenciar igual, como ya hacías con Veo. El prompt del plan ya lleva el
cierre de «sin diálogo, sin voces, sin música», que ayuda a que no invente
voces, pero la pista viene igual.

## Errores conocidos

| Síntoma | Causa | Solución |
|---|---|---|
| No aparecen las plantillas | ComfyUI < 0.30.0 | Actualizar el core y reiniciar |
| El modelo no figura en el loader | Carpeta o nombre mal | Verificar rutas exactas y reiniciar |
| CUDA OOM al samplear | Resolución o duración de más | Volver a 0,4 MP y 5 s, y subir de a un parámetro |
| Se queda sin RAM de sistema | Presión de offload | Probar `--disable-pinned-memory` |
| Video sin audio | Falta el decode de audio | Los dos VAE tienen que llegar al nodo `CreateVideo` |
| R2V falla y T2V anda | Checkpoint equivocado | R2V usa `ref2va`, no `fl2va` |

## Si querés que vaya más rápido

**SageAttention** es lo más fácil: se instala una rueda que coincida con tu
PyTorch y CUDA, se mete el nodo *Patch Sage Attention KJ* entre `UNETLoader` y
`BasicGuider`, y ComfyUI estima el doble de velocidad. Hacé funcionar el flujo
básico primero.

**Sol Engine**, de NVIDIA, reporta 4,52× en una 5090 (1045 s → 231 s en 768p,
5 s, 50 pasos) sin destilar ni entrenar nada. Es lo que hacía cerrar la cuenta
cuando la calculamos. Todavía no vi a nadie de afuera confirmar que instale sin
pelea ni que aguante clips de 10 s: si lo probás, anotá qué pasó.

## Lo que sigue sin saberse

- Cuánto tarda **10 s a 1344×768 en una 5090**. Lo contesta el paso 6.
- Si el INT8 se nota en tu material: grano de 35 mm, movimiento de cámara lento,
  brillos especulares corriendo por el panel solar.
- Si Sol Engine anda con H3 en un pod, hoy.

No completes ninguno de los tres de memoria. Medilos.
