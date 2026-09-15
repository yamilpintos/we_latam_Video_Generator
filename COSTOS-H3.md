# Costos medidos de MiniMax H3

Mediciones reales, no estimaciones, salvo donde diga *(est)*.

**Máquina de referencia:** Vast.ai, 4× RTX 5090 (32 GB c/u), **$2.124/hr** = $0.0354 por minuto.
**Resolución:** 1344×768 (nativa, lado corto 768).
**Modelo:** `ref2va_pruned_fp8_scaled` (21 GB) + encoder `nvfp4_awq` (15.7 GB) + VAE video/audio.
**Fecha:** 17 de agosto de 2026.

Ojo con una distinción que cambia todo: la instancia cuesta $2.124/hr **por las cuatro GPUs juntas**.
ComfyUI usa una sola, así que hoy pagás cuatro y usás una. Las columnas "4 GPUs" asumen el paralelo
levantando cuatro ComfyUI, uno por placa — **todavía no implementado**.

---

## 1. Mediciones crudas

| Prueba | Duración | Resolución | Pasos | Turbo | Encoder | Tiempo/clip |
|---|---|---|---|---|---|---|
| `MiniMax_H3_00001` | 5 s | 864×480 | 20 | no | nvfp4 | 1.5 min |
| `EFRIT_TURBO` | 10 s | 1344×768 | 4 | sí | nvfp4 | **3.9 min** |
| `CADENA_A` / `_B` | 15 s | 1344×768 | 4 | sí | nvfp4 | **7.0 min** |
| `OCHO_1..3` | 10 s | 1344×768 | 8 | sí | nvfp4 | **6.6 min** |
| `BAZAR_1..3` | 10 s | 1344×768 | 20 | no | nvfp4 | **15.7 min** |
| `BAZAR_ENC_1..3` | 10 s | 1344×768 | 20 | no | int8 27 GB | **16.1 min** |
| `B_8PASOS_1..3` | 10 s | 1344×768 | 8 | sí | int8 27 GB | **9.8 min** |

**Con 2 imágenes de referencia** (`ref_image_size=match`), medido el 18 de agosto de 2026
sobre GGUF Q5_K_M sin podar. La fila de arriba de 8 pasos sin referencias dio 6.6 min:
las referencias cuestan **+48 % de tiempo**. Hay que contarlo, porque el proyecto real
usa referencias en todos los planos.

**El encoder grande casi no cuesta tiempo:** 16.1 min contra 15.7 con el `nvfp4` de 15.7 GB — un
2.5 % más. El encoder corre una sola vez por clip y después se descarga de VRAM; el 95 % del tiempo
se lo lleva el DiT. Así que si el `int8` de 27 GB mejora la fidelidad al prompt, **conviene siempre**:
es calidad prácticamente gratis. Queda pendiente comparar `BAZAR_COMPLETO` contra `BAZAR_ENC_COMPLETO`
a ojo — mismos prompts, mismas semillas, mismos 20 pasos, solo cambia el encoder.

**Modelo derivado** (10 s a 1344×768): `minutos = 0.81 + 0.742 × pasos`
Predijo 14.7 para los 20 pasos contra 15.7 medidos — 7 % de error.

**Factor de duración:** un clip de 15 s cuesta **1.79×** uno de 10 s. Menos que el cuadrático puro,
porque hay ~1.2 min de costo fijo por clip (cargar, decodificar los dos VAE, armar el MP4).

---

## 2. Por video individual

| Config | Tiempo | 1 GPU | 4 GPUs |
|---|---|---|---|
| 10 s · 4 pasos | 3.9 min | $0.138 | **$0.035** |
| 10 s · 8 pasos | 6.6 min | $0.234 | $0.058 |
| 10 s · 20 pasos | 15.7 min | $0.556 | $0.139 |
| 15 s · 4 pasos | 7.0 min | $0.248 | $0.062 |
| 15 s · 8 pasos | 11.8 min *(est)* | $0.418 | $0.104 |
| 15 s · 20 pasos | 28.1 min *(est)* | $0.995 | $0.249 |

---

## 3. Por 10 minutos de video terminado

600 segundos = 60 clips de 10 s, o 40 clips de 15 s.

| Config | 1 GPU | 4 GPUs | Costo (4 GPUs) |
|---|---|---|---|
| 10 s · 4 pasos | 3 h 54 | **59 min** | **$2.07** |
| 10 s · 8 pasos | 6 h 36 | 1 h 39 | $3.50 |
| 10 s · 20 pasos | 15 h 42 | 3 h 55 | $8.34 |
| 15 s · 4 pasos | 4 h 40 | 1 h 10 | $2.48 |
| 15 s · 8 pasos | 7 h 52 *(est)* | 1 h 58 | $4.18 |
| 15 s · 20 pasos | 18 h 44 *(est)* | 4 h 41 | $9.95 |

**Los clips de 10 s rinden más que los de 15 s**, incluso necesitando 60 en vez de 40:
el costo no escala lineal con la duración.

---

## 4. Por hora de producción (4 GPUs)

Una hora de instancia = 240 minutos de GPU repartidos en cuatro placas.

| Config | Clips/hora | Video/hora |
|---|---|---|
| 10 s · 4 pasos | **61** | **10.3 min** |
| 10 s · 8 pasos | 36 | 6.1 min |
| 10 s · 20 pasos | 15 | 2.5 min |
| 15 s · 4 pasos | 34 | 8.6 min |
| 15 s · 8 pasos | 20 *(est)* | 5.1 min |
| 15 s · 20 pasos | 8 *(est)* | 2.1 min |

Esto es **generación**, no producción. Contando que de cada 3-4 intentos uno queda,
para material *usable* multiplicá el costo por tres.

---

## 5. Contra la API

H3 por API cuesta **$0.073 – $0.13 por segundo** de video generado.

| | $/segundo | vs API |
|---|---|---|
| 4 pasos, 4 GPUs | $0.0035 | **21-37× más barato** |
| 8 pasos, 4 GPUs | $0.0058 | 13-22× |
| 20 pasos, 4 GPUs | $0.0139 | 5-9× |

Aun en la configuración más cara, la cuarta parte que la API. Y la diferencia de fondo:
la API cobra **por unidad de salida**, así que cada intento descartado cuesta; alquilando
la GPU se paga **por tiempo** y regenerar es gratis.

---

## 6. Palancas para abaratar, sin medir todavía

| Palanca | Ahorro estimado | Estado |
|---|---|---|
| Instancias *interruptible* en vez de *onDemand* | 2-3× | sin probar |
| Pasada de borrador barata → regenerar solo los buenos con la misma semilla | 2-3× efectivo | sin implementar |
| 1024×576 + escalado local (Topaz / Real-ESRGAN) | 1.75× | sin probar |
| Máquina más barata (había 4×5090 a $1.735) | 20 % | sin probar |

---

## 7. Palancas de calidad, sin medir todavía

El DiT está en la versión **más comprimida que existe**: podado *y* en fp8, 21 GB de 66.3 GB.
Es la palanca de calidad más grande que queda.

| Modelo (DiT) | Tamaño | ¿Entra en 32 GB? |
|---|---|---|
| `pruned_fp8_scaled` | 21.0 GB | sí — **el que se usó** |
| `int8_convrot` (sin podar) | 34.0 GB | al límite, quizá con offload |
| `pruned_bf16` | 40.2 GB | no |
| `bf16` (completo) | 66.3 GB | no — necesita placa de 96 GB |

| Encoder | Tamaño | |
|---|---|---|
| `nvfp4_awq` | 15.7 GB | usado en las mediciones 1-5 |
| `int8_convrot` | 27.1 GB | probándose en `BAZAR_ENC` |
| `bf16` | 51.5 GB | sin probar |

Otras dos sin medir: **`ref_image_size: "max"`** (el tooltip promete "best identity fidelity";
es la palanca clave para consistencia de personaje entre tomas) y **`MiniMaxH3SigmaShift`**
(`shift_video` 12.0 / `shift_audio` 3.0 por defecto, nunca tocados; es la palanca dedicada al audio).

---

## 8. Comparativa de modelos y configuraciones (18 de agosto de 2026)

Cinco corridas **en paralelo, una por GPU**, con los mismos prompts, las mismas semillas
y las mismas dos imágenes de referencia (princesa + palacio). Cada una cambia **una sola
variable**. Máquina: 4× RTX 5090, **$1.909/hr** = $0.0318 por minuto.

Cada corrida son 3 clips encadenados de 10 s a 1344×768 = 30 s de video.

| | Modelo | Pasos | Turbo | Referencias | min/clip | $/clip (4 GPUs) |
|---|---|---|---|---|---|---|
| **E_AUDIO** | GGUF Q5 | 8 | sí | match, `SHIFT_AUDIO=1.5` | **9.33** | **$0.074** |
| **B_8PASOS** | GGUF Q5 | 8 | sí | match | **9.83** | **$0.078** |
| **D_FP8** | fp8 podado | 20 | no | match | 18.13 | $0.144 |
| **A_20PASOS** | GGUF Q5 | 20 | no | match | 22.37 | $0.178 |
| **C_REFMAX** | GGUF Q5 | 20 | no | **max** | 24.20 | $0.192 |
| **F_MAXIMO** | GGUF Q6 | 20 | no | max | — | no corrió: disco lleno |

### Lo que se aprendió

**`ref_image_size=max` sale casi gratis: +8 %.** C contra A son 24.20 contra 22.37 minutos.
El tooltip del nodo advierte que puede ser "varias veces más lento" y resultó ser un 8 %.
Como es la palanca de fidelidad de identidad —la que decide si un personaje es el mismo
entre tomas—, **conviene dejarla en `max` siempre**.

**Los pasos son la palanca de costo dominante: 20 pasos cuestan 2.3× lo que 8.**
De $0.078 a $0.178 por clip. Es la decisión que más plata mueve en todo el proyecto.

**El GGUF sin podar cuesta +23 % de tiempo sobre el fp8 podado.** A contra D, a igualdad
de pasos, son 22.37 contra 18.13 minutos. Ese es el precio de correr el modelo completo:
hay que descomprimir los pesos en cada paso. Si la calidad lo justifica se paga solo.

**`SHIFT_AUDIO=1.5` no cuesta nada** (E contra B: 9.33 vs 9.83, dentro del ruido de medición).
Si mejora el audio, es gratis.

**Las referencias cuestan +48 %.** B con referencias dio 9.83 min contra los 6.6 medidos
el 17/8 sin ellas, a 8 pasos. El proyecto real las usa en todos los planos: hay que contarlo.

**Pista de los tamaños de archivo**, mismos 30 s cada uno: los de 8 pasos pesan **10.5 MB**
y los de 20 pasos **5 MB**. El compresor gasta más bits donde hay más detalle y movimiento,
así que sugiere que 20 pasos sin turbo salen *más suaves*, no más detallados — lo contrario
de lo esperado. Es una pista, no una conclusión: decide el ojo.

### El pescador (21 clips de 10 s) con cada configuración

| Config | 4 GPUs | Costo |
|---|---|---|
| 8 pasos + turbo | **52 min** | **$1.64** |
| 20 pasos, fp8 podado | 95 min | $3.03 |
| 20 pasos, GGUF | 117 min | $3.74 |
| 20 pasos + refs en max | 127 min | $4.04 |

### 10 minutos de video (60 clips de 10 s)

| Config | 4 GPUs | Costo |
|---|---|---|
| 8 pasos + turbo | 2 h 28 | **$4.69** |
| 20 pasos, GGUF | 5 h 36 | $10.68 |
| 20 pasos + refs en max | 6 h 03 | $11.55 |

### Pendiente

**F_MAXIMO** (GGUF Q6_K de 28.2 GB, el más grande que entra en 32 GB) no llegó a correr:
con Q5 + encoder + fp8 de respaldo + salidas, los 150 GB de disco se agotaron.
**Para la próxima instancia pedir 250 GB.**

El paralelo en 4 GPUs **quedó probado y funcionando**: cuatro ComfyUI, uno por placa,
con `CUDA_VISIBLE_DEVICES=<n>` y `--port 18188+n`, y el script apuntado con `PORT=`.
Cinco experimentos en el tiempo de uno.

---

## 9. El modelo completo bf16 (18 de agosto de 2026)

Máquina: **1× RTX PRO 6000, 96 GB, $1.17/hr** (Australia) = $0.0195 por minuto.
Modelo `minimax_h3_ref2va_bf16` de 66.3 GB + encoder `bf16` de 51.5 GB.
Mismos prompts (herrero, hiperrealista), misma semilla, 8 pasos, sin referencias.

| Modelo | Tamaño | min/clip | $/clip (1 GPU) |
|---|---|---|---|
| GGUF Q5_K_M | 23.9 GB | 6.6 | $0.210 en 5090 |
| **bf16 completo** | **66.3 GB** | **7.1** | **$0.138 en PRO 6000** |

**El modelo completo es solo 8 % más lento que el comprimido.** (21.4 min los tres clips: 7.3 · 7.3 · 6.8, promedio 7.1.) La estimación previa era
2-3× más lento y estuvo muy equivocada. El motivo: **el GGUF tiene que descomprimir los pesos
en cada paso de sampleo**, y ese costo se come casi toda la ventaja de mover menos bytes.
El bf16 los lee directo de VRAM.

**Consecuencia práctica:** si tenés una placa de 96 GB, **no hay razón para usar el GGUF**.
El modelo completo cuesta un 11 % más de tiempo y no perdés ningún parámetro ni precisión.

**Pico de memoria: 90.9 GB de 95.6.** El encoder bf16 (51.5 GB) y el DiT (66.3 GB) conviven
muy justos aunque ComfyUI los cargue por turnos. **En una placa de 80 GB no habría entrado**:
los 96 GB son necesarios de verdad, no un lujo.

### El matiz del costo

Por GPU suelta, el PRO 6000 con bf16 sale **más barato por clip** que un 5090 con Q5
($0.142 contra $0.210), porque la placa cuesta menos por hora aunque sea un poco más lenta.

Pero si el 5090 corre en una máquina de 4 y se usan las cuatro en paralelo, el costo por
clip se divide entre cuatro y baja a **$0.052** — tres veces más barato que el bf16 en una
sola placa. **El paralelismo pesa más que la elección de modelo.**

La configuración ideal sería 4× RTX PRO 6000, pero cuesta $5-7/hr.

---

## 10. Serie del bazar — una variable por vez (18 de agosto de 2026)

Misma escena (persecución del ladrón por el bazar, hiperrealista), mismos prompts,
mismas semillas, sin imágenes de referencia. Tres clips encadenados de 10 s.
Máquina: **1× RTX PRO 6000, 96 GB, Noruega, $1.688/hr** = $0.0281 por minuto.

| Modelo | Pasos | Turbo | min/clip | $/clip | $/min de video | $/hora de video |
|---|---|---|---|---|---|---|
| **bf16 completo** | **20** | no | **12.6** | **$0.354** | **$2.13** | **$127.5** |
| bf16 completo | 8 | sí | *pendiente* | | | |
| GGUF Q5 | 20 | no | *pendiente* | | | |
| GGUF Q5 | 8 | sí | *pendiente* | | | |

La estimación previa para el bf16 a 20 pasos era 16.3 min/clip (7.1 × 2.3, extrapolando
el factor de pasos medido con el Q5). El real fue **12.6**: el factor de pasos en bf16 es
**1.77×**, no 2.3×. Los pasos pesan menos en el modelo sin comprimir.

Ojo con una variable que viaja escondida: las corridas de 8 pasos llevan la **LoRA turbo
activada** (es su régimen) y las de 20 la llevan apagada. No es solo la cantidad de pasos
lo que cambia entre esas filas.

---

## 11. Pipeline de planos contra pipeline de escenas encadenadas (19 de agosto de 2026)

El cambio de arquitectura no era por costo, era por calidad — se buscaba sacarse de
encima las junturas visibles. Pero **también sale más barato**, y por dos motivos
distintos que conviene no mezclar.

### Motivo 1: no se desperdicia paralelismo

Encadenado, los 3 clips de una escena van **en serie**: el B necesita el último
fotograma del A. Las unidades repartibles eran 10 escenas para 4 placas, así que la
placa más cargada hacía 3 escenas = 9 clips seguidos, y en la última tanda había dos
placas al pedo.

Por planos, las unidades son 42 y ninguna espera a otra. El reparto sale parejo solo
(11/11/10/10) y no hay placa ociosa.

### Motivo 2: los planos cortos son baratos de más

Con los dos puntos medidos a 8 pasos, turbo, 1344×768:

| duración | min/clip | min por segundo |
|---|---|---|
| 10.1 s | 6.6 | 0.652 |
| 15.1 s | 11.8 | 0.784 |

El costo por segundo **sube** con la duración: la atención crece con el cuadrado del
largo de la secuencia. Ajustando una recta a esos dos puntos sale
`minutos = -4.02 + 1.049 × segundos`. La ordenada al origen negativa no significa nada
físico, es el ajuste diciendo que la cosa es superlineal.

Como la película de planos promedia 7.4 s por plano en vez de 10, cae del lado barato
de esa curva.

### La cuenta, para los mismos ~5 minutos de película

Recalculado desde la tabla 1, escalón por escalón, repartiendo por índice como hace el
runner y midiendo el tiempo de la placa que más tarda:

| | unidades | GPU total | pared con 4 placas | costo |
|---|---|---|---|---|
| 0. encadenado, refs en el clip 1 | 10 escenas | 230 min | 69 min | $2.20 |
| 1. + sin referencias | 10 escenas | 198 min | 59 min | $1.89 |
| 2. + planos independientes (30 de 10 s) | 30 planos | 198 min | 53 min | $1.68 |
| 3. + duraciones reales (42, de 5 a 15 s) | 42 planos | 155 a 201 min | **45 a 56 min** | **$1.44 a $1.77** |

**La mejora real es de entre 20 % y 35 %, no de tres veces.**

> **Corrección.** El `LEEME.txt` viejo decía «~2 h 30 y ~$4.80» para el método
> encadenado a 8 pasos, y yo repetí esa cifra al presentar el cambio. Es falsa:
> recalculada desde las mismas mediciones, la versión encadenada tarda **69 minutos y
> sale $2.20**. No pude reconstruir de dónde salían las 2 h 30 — no se derivan de la
> tabla 1 — así que la comparación honesta es 69 min contra 45-56, no 150 contra 45.

### De dónde sale cada minuto

**Escalón 1, sacar las referencias: −10 min, el pedazo más grande.** Las referencias
cuestan +48 % (medido: 9.8 min contra 6.6), y en el método encadenado las llevaba el
clip 1 de cada escena, o sea 10 de los 30 clips. Ahora ese trabajo lo hace nanobanana
al dibujar el storyboard, **en la máquina local y con la GPU alquilada apagada**. No se
eliminó trabajo: se movió a donde no cuesta tiempo de alquiler.

**Escalón 2, independizar los planos: −6 min, y es puro reparto.** Acá no se ahorra ni
un minuto de cómputo — los 198 min de GPU son idénticos antes y después. Lo único que
cambia es que había 10 unidades repartibles para 4 placas (3/3/2/2, con la última tanda
medio vacía) y ahora hay 30. Los 6 minutos son placa ociosa que desaparece.

**Escalón 3, duraciones reales: entre −8 y +3 min, y no lo sé todavía.** El ajuste
optimista dice que los planos cortos salen baratos de más porque la atención crece con
el cuadrado del largo; la regla conservadora dice que es un empate. Los dos puntos
medidos son de 10 y 15 s y acá la mitad de los planos dura menos de 7, así que esto es
extrapolación pura. Por eso el resultado es un rango.

### Y la descarga, que depende del host mucho más de lo que dije

`SOLO_FL=1` saca 47 GB (106 → 59). Lo que eso vale en dinero depende enteramente del
ancho de banda que te toque:

| enlace del host | 106 GB | 59 GB | ahorro | $ |
|---|---|---|---|---|
| 30 Mbps | 471 min | 262 min | 209 min | $6.65 |
| 250 Mbps | 57 min | 31 min | 25 min | $0.80 |
| 800 Mbps | 18 min | 10 min | 8 min | $0.25 |
| 2000 Mbps | 7 min | 4 min | 3 min | $0.10 |

> **Corrección.** Dije «media hora menos y casi $1». Eso solo vale si el host anda a
> unos 250 Mbps. A 800 son 8 minutos y $0.25.

Lo que sí queda claro de esta tabla es otra cosa, más importante que el flag: **en un
host lento la descarga cuesta más que generar la película entera.** Filtrar por ancho
de banda al alquilar pesa más que cualquier optimización del pipeline.

### Lo que esta estimación no sabe

Los dos puntos medidos son de 10 s y 15 s. La mitad de los planos de Aladino duran
menos de 7 s, o sea que **estoy extrapolando por debajo del rango medido**, que es
justo donde el ajuste de dos puntos es menos confiable — por eso el rango va de 45 a
56 min en vez de un número solo. Tampoco tiene en cuenta el costo fijo por plano
(codificar el prompt, escribir el MP4), que ahora se paga 42 veces en vez de 30.

Se resuelve solo: la primera corrida imprime el tiempo real de cada plano con su
duración al lado. Con eso se ajusta la curva con 42 puntos entre 5 y 15 s y esta
sección se reescribe con datos en vez de extrapolación.

### Además: la descarga baja a la mitad

Como todos los planos arrancan de su dibujo de storyboard, el pipeline usa **solo
FL2VA**. Ref2VA no se toca nunca, y su LoRA turbo tampoco.

El perfil `max` traía **dos** modelos Ref2VA, no uno: el GGUF Q5_K_M de 23.9 GB y el
`pruned_fp8` de 21 GB. `SOLO_FL=1` saca los dos.

| perfil | completo | con `SOLO_FL=1` | ahorro |
|---|---|---|---|
| max | 106 GB | ~59 GB | 46 GB |
| q6 | 93 GB | ~63 GB | 30 GB |

A 800 Mbps son unos **30 minutos** menos de máquina encendida esperando la descarga,
que a $1.909/h es casi $1 — comparable a lo que sale generar la película entera. Y es
gratis: es una variable de entorno.

### Y el storyboard no es gratis, pero casi

42 imágenes de nanobanana a unos 22 s cada una. Se hacen en la máquina local mientras
la GPU está apagada, así que **no cuestan tiempo de alquiler**. El gasto es la API de
imágenes, no la GPU.

Lo importante no es el precio sino el orden: el storyboard se revisa entero **antes**
de prender la máquina. Un plano mal encuadrado se descubre y se rehace mirando un PNG,
no después de siete minutos de generación con el reloj corriendo.

---

## 12. Primera corrida real medida — 78 SUR (28 de agosto de 2026)

**Doce planos de 5,2 a 7,3 s**, que es justo el rango donde todo lo anterior
extrapolaba a ciegas: los únicos dos puntos medidos eran de 10 y 15 s.

Máquina: **4× RTX 5090**, Alberta (Canadá), datacenter, $3.269/h.
768×1344 vertical · 8 pasos con turbo · GGUF Q5_K_M FL2VA · sin referencias.

| plano | segundos | min de GPU | min por segundo |
|---|---|---|---|
| S01 | 5.2 | 3.7 | 0.71 |
| S02 | 5.2 | 3.6 | 0.69 |
| S03 | 5.2 | 3.6 | 0.69 |
| S04 | 5.2 | 3.7 | 0.71 |
| S05 | 7.3 | 5.9 | 0.81 |
| S06 | 7.3 | 5.8 | 0.79 |
| S07 | 7.3 | 5.2 | 0.72 |
| S08 | 7.3 | 5.7 | 0.78 |
| S09 | 5.9 | 4.2 | 0.72 |
| S10 | 7.3 | 5.5 | 0.75 |
| S11 | 5.9 | 3.9 | 0.67 |
| S12 | 5.9 | 4.1 | 0.70 |

- **GPU total: 54.9 min** · pared con 4 placas: ~14 min
- **0,67 a 0,81 min de GPU por segundo de video** — el promedio es 0,73
- Costo de generación: **~$0.75**
- Descarga de los 59 GB: 2-5 min a 3230 Mbps

Los planos más largos cuestan más por segundo (0,81 a 7,3 s contra 0,69 a 5,2),
lo que **confirma la superlinealidad** que la tabla 11 suponía sin poder medir.

### Lo que no está en los minutos

De 12 planos, **2 fallaron por falta de VRAM** en el tercer clip de su placa: el
GGUF ocupa 23,9 GB de los 32 y la memoria se fragmenta. Se resolvieron
reiniciando ComfyUI y relanzando, y salieron a la primera. Hay que contar ese
reintento al presupuestar: son ~5 min más de máquina.

Y el total de la sesión fue **~$4**, no $0.75: el resto se fue en nueve
problemas de infraestructura, todos documentados en `h3pipeline/VAST.md` y ya
arreglados. La próxima corrida debería costar lo que dice la tabla.

---

## 13. Segunda serie real — EL DRON DEL VOLCÁN en 4× A100 PCIE (30 de agosto de 2026)

Primera corrida **entera desatendida** (`alquilar --si --generar` → `seguir` →
`bajar` → `destruir`, sin entrar por SSH) y **primeros puntos medidos en A100**.
Instancia 49303879, Japón, $4.416/h, enlace 4334 Mbps, 12 planos sueltos de
5,2 a 7,3 s, 768×1344, 8 pasos con turbo, 0 fallos, 0 reintentos.

| | teórico (estimador) | real |
|---|---|---|
| arranque hasta SSH utilizable | no se cuenta | **4,1 min** |
| min de GPU por segundo de video | 0,67-0,81 (curva 5090) | **0,82-0,91 · 0,86 prom.** |
| GPU total (12 planos, 66 s generados) | ~46 min | **~62 min** |
| costo | $0,94 | **~$2,4** (~33 min de pared con montaje y bajada) |

Dos lecciones para el estimador:

1. **La A100 rinde ~15 % menos por segundo que la 5090** en este trabajo
   (0,86 contra 0,74 de promedio). `costos.estimar()` usa la curva 5090 para
   cualquier placa: al comparar ofertas de familias distintas, el orden puede
   quedar mal por ese margen. Palanca: un factor por familia de GPU.
2. **El estimador no cuenta el overhead fijo**: ~4 min de arranque + ~2 de
   montaje y bajada. En un video corto eso es la mitad del costo real. Palanca:
   sumar una constante de ~6-8 min de máquina por sesión.

La regla de ordenar por costo total sigue valiendo — pero el "total" tiene que
incluir estas dos cosas para que el podio no mienta entre familias.

## Cómo sumar una medición

Correr, anotar el tiempo por clip en la tabla 1, y recalcular el resto:

```
$/clip (1 GPU)  = minutos × 0.0354
$/clip (4 GPUs) = minutos × 0.0354 / 4
clips/hora      = 240 / minutos
video/hora      = clips/hora × duración
```

Si cambia la máquina, cambia el `0.0354` — es `$/hora ÷ 60`.

## 14. Primer video 16:9 — LLUVIA EN LA VENTANA (10 de septiembre de 2026)

Video ambiente en bucle, sin voz: 12 planos de 5,17 s a **1344×768 apaisado**,
8 pasos con turbo, 4× RTX 5090 (Taiwán, instancia 50515495, $1,966/h, 890 Mbps).
Arranque 7,4 min; descarga de modelos ~13 min con setup; 12/12 sin fallos de
máquina, 0 reintentos por VRAM.

| | vertical 768×1344 (§12) | apaisado 1344×768 (esta corrida) |
|---|---|---|
| min de GPU por clip de 5,17 s | 3,6-3,7 | **4,0-5,0 · 4,7 típico** |
| min de GPU por segundo | 0,69-0,71 | **0,78-0,97 · 0,91 promedio** |

Mismos píxeles, misma máquina de referencia, ~30 % más lento. **Resuelto el
13/9:** en otra 4×5090 (Taiwán 47993623) los mismos 16:9 dieron **0,77 min/s**
en dos proyectos (24 clips): la lentitud era del host, no de la orientación.

Lo que no fue máquina: **7 de 12 clips inservibles por el contenido** (gente,
cactus, fuego, nubes de caricatura: lo que los bloques negativos del prompt
prohibían) y tres tandas de rehecho —7, 4 y 1 clips— con la instancia viva.
Detalle en `mis-videos/lofi-lluvia/NOTAS.md` y regla nueva `negativos: false`.

| | |
|---|---|
| GPU, corrida limpia teórica (12 clips) | ~$0,40 |
| GPU real, con 3 tandas de rehecho y QC entre tandas | **$2,70 a los 82 min** |
| imágenes (30 + 9 regeneraciones, Flash) | ~$1,50 |

La lección de costo: el rehecho por contenido costó 6× la generación. Se evita
con el prompt correcto ANTES de la primera tanda (`negativos: false` en escenas
quietas) y con encuadres que H3 sostiene (primeros planos de objeto, sin ventana
pegada, sin silla vacía frente a un escritorio).
