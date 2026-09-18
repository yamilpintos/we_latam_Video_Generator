# Remasterización SD → 4K con FlashVSR v1.1 en Vast.ai — traspaso para La Fábrica

Escrito el 18/9/2026 para la sesión que va a integrar la opción «Remasterizar» en la web
(`h3pipeline/app`, FastAPI). Todo lo de acá está **medido en dos corridas reales** (17 y 18/9);
lo que es estimación está marcado como tal. Los scripts que funcionaron viven en
`remasterizado/prueba-30s/` y se pueden importar o portar tal cual.

> **Integrado en La Fábrica el 18/9/2026.** La puerta «Remasterizar» de la portada
> (`h3pipeline/app/remaster.py`, `remasterizar.py`, vista `#/remaster`) implementa la
> propuesta de la sección 10: análisis local gratis (sondeo + idet + hoja + avisos),
> preparación con ffmpeg, estimación contra las A100 reales, corrida desatendida con
> imagen propia (`vast.crear_con_imagen`), codificación del 4K EN la máquina, bajada,
> destrucción y QC. Los scripts portados viven en `h3pipeline/remoto/remaster/`
> (`infer_trozos.py` ahora lee por ventana, para capítulos enteros). Estado y lo que
> falta: `h3pipeline/app/ESTADO-FABRICA.md`. Este documento queda como registro de
> las dos corridas y de los números.

---

## 1. Qué se logró

- Un clip de 30 s de *Chiquititas* (máster de emisión, 720×576 entrelazado) se llevó a 4K
  (2880×2160 en 4:3, y 3840×2160 con barras) con **FlashVSR v1.1 Full**, en una A100 de 80 GB
  alquilada en Vast. Resultado aprobado por el usuario («salió espectacular»).
- Entregables en `remasterizado/ENTREGA-19m16/`:
  `ORIGINAL_19m16_SD_704x576.mp4`, `REMASTER_19m16_4K_2880x2160.mp4`,
  `REMASTER_19m16_4K_UHD_3840x2160.mp4`.
- Costo de las dos noches: $1,05 + $0,94. Saldo en Vast al cierre: $0,18 (**hay que cargar**).

## 2. Decisión de modelo (investigación de ~250 fuentes, 17/9)

| Modelo | Por qué sí / no |
|---|---|
| **FlashVSR v1.1 Full** (OpenImagingLab, CVPR 2026, Apache 2.0, pesos públicos 6,95 GB) | Mejor en el benchmark real VideoLQ con protocolo único; su framework ganó NTIRE 2026 (única competencia con jueces humanos). Un solo paso, ×4 nativo. **Elegido.** |
| SeedVR2-3B (ByteDance, Apache 2.0) | El más famoso, pero último o anteúltimo en video real en las tablas de 2026, peor consistencia temporal, y ByteDance advierte que sobreafila 480p. Segunda opción. Nunca el 7B-sharp con DVD (amplifica ringing). |
| SwiftVR (jun 2026, Wan2.2-5B, Apache) | Mejores métricas en el paper y probado en 5090 por sus autores; sin validación externa. Candidato a A/B futuro. |
| Upscale-A-Video, KEEP, DicFace, RTN | Licencias no comerciales. Descartados. |

No existe SeedVR3 ni FlashVSR v2. Los restauradores de caras en video con licencia comercial y
pesos públicos todavía no existen (esperar DVFace).

**Lección clave del 17→18/9:** las deformaciones de caras lejanas que salieron la primera noche
eran culpa del **origen** (un MP4 de 302 kbps), no del modelo. Con el máster de 50 Mbps las caras
del fondo salen limpias. La web tiene que exigir o al menos advertir sobre la calidad del origen:
**bitrate bajo = caras inventadas**.

## 3. Números medidos

### Corrida 1 — 17/9, origen MP4 490×360 a 302 kbps, A100 SXM 80 GB (Chequia, $1,056/h)
- 753 cuadros → 1920×1408. Modelo (DiT): **88 s = 8,5 fps**. VAE sin tiling: OOM en 80 GB.
  Con tiling por defecto: **673 s en total**, 70 GB pico. Total con instalación: 65 min, $1,05.

### Corrida 2 — 18/9, origen MXF IMX 50 Mbps 704×576 (recortado), A100 PCIe 80 GB (Oklahoma, $0,873/h)
- 750 cuadros → 2816×2304, en 8 trozos de 125 cuadros con solape de 21.
- Por trozo: DiT ~35 s + VAE tileado (tiles grandes) ~2:40 → **~3,7 min por trozo**, 62,5 GB pico.
- Total inferencia: **1794 s para 30 s de video = 60× tiempo real**.
- Instalación desde cero: 770 s. Descarga del resultado (553 MB): 5,6 min.
- El VAE sin tiling **no funciona a 2816×2304 ni con 80 GB** (`RuntimeError: GET was unable to find an engine`, cuDNN).

### Costo por hora de película (a 4K, con lo medido hoy)
| Variante | Placa | GPU-h por hora de película | $/hora de película |
|---|---|---|---|
| Full, tiles grandes (medido) | A100 PCIe $0,87 | 60 | **~52** |
| Full con tiles más grandes aún (estimado) | A100 | 25-30 | 20-25 |
| **Tiny** (estimado por la relación 17/6,5 fps de los autores) | A100 | 8-10 | **6-9** |
| Tiny si entra en 32 GB (estimado) | RTX 5090 $0,47 | 8-10 | 3-4 |

El 88 % del tiempo de Full es la decodificación del VAE de Wan, no el modelo. **FlashVSR Tiny**
usa el mismo DiT con un decodificador liviano (`TCDecoder.ckpt`, ya incluido en los pesos):
esa es la palanca para bajar el costo ~7×. Falta el A/B de calidad sobre los mismos 30 s (~$1).
Fijo por sesión: ~$1 (instalación + descargas) — amortizarlo procesando varias cosas por alquiler.

## 4. Preparación del origen (local, ffmpeg de `.venv-depthflow`)

1. **Sondear**: resolución, `field_order`, DAR, bitrate, canales de audio. Detectar entrelazado con
   `-vf idet` sobre 5 s (si `TFF`/`BFF` domina, es entrelazado).
2. **Máster MXF IMX (D-10)**: 720×608 = 32 líneas de VBI arriba + 576 activas; blanking lateral
   ~12 px izquierda y ~8 derecha. Medido por perfil de luminancia por fila/columna. Recorte:
   `crop=704:576:12:32`. 704×576 ×4 = 2816×2304 = múltiplos exactos de 128 (el script oficial
   recorta a múltiplos de 128, así no pierde nada).
3. **Desentrelazar antes del modelo**: `bwdif=mode=send_frame:parity=tff:deint=all` (25p).
   Si fuera film telecinado NTSC, IVTC (TFM+TDecimate), no QTGMC. Nunca escalar entrelazado:
   el modelo fija el combing como detalle.
4. **Audio**: el MXF trae PCM de 8 canales; los dos primeros son el estéreo:
   `-af "pan=stereo|c0=c0|c1=c1" -c:a aac -b:a 256k`.
5. **Codificar el clip de entrada** con `libx264 -crf 8 -pix_fmt yuv422p` (conserva el 4:2:2;
   el modelo lee RGB vía imageio). 30 s ≈ 58 MB.
6. **Los tiempos entre versiones del mismo capítulo no coinciden**: el máster iba 0,8 s
   adelantado en el minuto 10 y 54,2 s atrasado en el minuto 19 (tandas). Ubicar fragmentos por
   coincidencia de cuadros, no por reloj: `buscar_offset.py <chico> <t> <mxf> <desde> <hasta>`
   (miniaturas 96×72 en gris, 5 muestras/s, error cuadrático normalizado; una coincidencia real da
   err ≈ 0,02-0,05, un no-match ≈ 0,7-1,0).
7. Un MXF **parcialmente descargado se lee bien** (cabecera al inicio): no hace falta esperar
   los 22 GB para cortar un fragmento. Descarga de Drive: `gdown --no-check-certificate --continue`
   (Avast rompe TLS; `--fuzzy` ya no existe en gdown 6).

## 5. La máquina en Vast

- **Placa**: A100 de 80 GB (SXM o PCIe). Con 40 GB no entra (pico 62,5 GB). H100: 2-3× más
  rápida pero $2,8/h → mismo costo por hora de película. 5090 (32 GB, $0,47/h): la
  Block-Sparse-Attention ya declara soporte sm_120 en su setup.py pero **no está probado en Linux**;
  memoria justa. Sólo tiene sentido con Tiny.
- **Imagen**: `vastai/base-image:cuda-12.4.1-cudnn-devel-ubuntu22.04-py311` (6,1 GB, trae nvcc
  12.4 = mismo CUDA que el torch pineado por el repo). Se crea con `image` propia **replicando el
  template oficial**: `onstart: "entrypoint.sh"`, `runtype: "jupyter_direc ssh_direc ssh_proxy"`,
  `env` con los puertos 1111/8080 y `PORTAL_CONFIG`. Cuerpo exacto en `nocturna.py:crear()`.
  (La trampa 2 de VAST.md era usar un `onstart` propio; con `entrypoint.sh` la imagen propia anda.)
- Disco 60 GB. Filtros de búsqueda: `verified`, `num_gpus=1`, `gpu_name in (A100 SXM4, A100 PCIE)`,
  `gpu_ram ≥ 70000`, `inet_down ≥ 500`, `reliability2 ≥ 0,98`, `dph_total ≤ 1,30`, fuera China.
- SSH directo: `POST /instances/{id}/ssh/` con la clave pública, luego `public_ipaddr` +
  `ports["22/tcp"]`. Lo hace `h3pipeline.vast.autorizar_clave` / `_ssh_args`. Arranca en ~1,5 min.
- **Python es `/venv/main/bin/python`**; `hf` y `huggingface-cli` están en `/venv/main/bin/`
  (no en PATH). `nvcc` en `/usr/local/cuda/bin`.

## 6. Instalación (receta que funciona: `setup-v2.sh`, 770 s)

```
git clone --depth 1 https://github.com/OpenImagingLab/FlashVSR
git clone --depth 1 https://github.com/mit-han-lab/Block-Sparse-Attention
pip install "huggingface_hub[hf_transfer]"
HF_HUB_ENABLE_HF_TRANSFER=1 /venv/main/bin/hf download JunhaoZhuang/FlashVSR-v1.1 \
    --local-dir FlashVSR/examples/WanVSR/FlashVSR-v1.1        # 6,95 GB, ~11 s a 5 Gbps
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
grep -v -i -E "^(torch|torchvision|torchaudio)" requirements.txt > req.txt && pip install -r req.txt
pip install modelscope "setuptools<80" packaging ninja
pip install -e . --no-deps --no-build-isolation
cd Block-Sparse-Attention && BLOCK_SPARSE_ATTN_CUDA_ARCHS=80 MAX_JOBS=64 NVCC_THREADS=4 python setup.py install
```

Trampas que costaron tiempo (todas resueltas en el script):
| Síntoma | Causa | Arreglo |
|---|---|---|
| `torch==2.6.0+cu124` no se encuentra | el setup.py de FlashVSR lee `requirements.txt` con ese pin | instalar torch cu124 exacto **antes**, y `pip install -e . --no-deps` |
| `No module named 'pkg_resources'` al `pip install -e .` | setuptools ≥ 80 en el build aislado | `setuptools<80` + `--no-build-isolation` |
| `No module named 'modelscope'` al importar diffsynth | no está en requirements | `pip install modelscope` |
| `hf: command not found` | binario fuera del PATH | `/venv/main/bin/hf` |
| `nvcc fatal: Unsupported gpu architecture 'compute_120'` | el setup.py de BSA compila 80;90;100;110;120 por defecto y nvcc 12.4 no conoce 120 | `BLOCK_SPARSE_ATTN_CUDA_ARCHS=80` (291 s con 128 núcleos) |
| `ImportError: libc10.so` al importar `block_sparse_attn` | se importó antes que torch | siempre `import torch` primero (diffsynth ya lo hace) |
| `RuntimeError: GET was unable to find an engine` en conv3d | VAE sin tiling a 2816×2304 | tiling (ver §7) |

## 7. Inferencia (`infer_trozos.py`, vive en `examples/WanVSR/` junto al script oficial)

- Importa `infer_flashvsr_v1.1_full.py` como módulo y reutiliza `init_pipeline`,
  `compute_scaled_and_target_dims`, `upscale_then_center_crop`, `largest_8n1_leq`, `tensor2video`.
- Lee **todos** los cuadros a RAM (30 s a 704×576 ≈ 0,9 GB; para un capítulo hay que leer por
  ventanas, no todo).
- **Trozos de 125 cuadros** (125 + 4 de relleno = 129 = 8n+1, condición del modelo) con
  **solape de 21** cuadros: el modelo es causal y arranca frío; la salida de los 21 primeros
  cuadros de cada trozo se descarta. El último trozo se rellena repitiendo el último cuadro y se
  recorta. Salida: exactamente N cuadros (verificado 750/750).
- Parámetros del modelo (los recomendados por los autores): `num_inference_steps=1`, `cfg_scale=1`,
  `sparse_ratio=2.0` (`topk_ratio = 2.0·768·1280/(H·W)`), `kv_ratio=3.0`, `local_range=11`
  (9 = más nítido, 11 = más estable), `color_fix=True`, `is_full_block=False`, `if_buffer=True`.
- **Decodificación del VAE**: `tiled=True` obligatorio a 4K. Modos, del más rápido al más seguro,
  con fallback automático ante `OutOfMemoryError` **y** `RuntimeError`:
  1. tiles grandes `tile_size=(80,128)`, `tile_stride=(60,96)` → 20 tiles, ~2,5× más rápido que
     el default, 62,5 GB pico con trozos de 125. **Usado.**
  2. tiles chicos `(60,104)/(30,52)` (default del pipeline) → 54 tiles con 50 % de solape.
  Unidades en latente (1/8 del píxel). Probar `(96,160)/(80,144)` → 12 tiles, todavía sin medir.
- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` siempre (la fragmentación costó 14 GB).
- Salida por imageio a `libx264 -crf 8 -preset medium` (553 MB por 30 s a 2816×2304). Para un
  capítulo, escribir por trozo a un archivo cada uno y concatenar con `-c copy`, o pasar a
  x265 10-bit. **Nunca PNG a disco** (2 h = 1,4-2 TB).
- Log con marcas parseables: `[entrada] …`, `[tiempo] modelo cargado…`, `[trozo k] … escritos a/N`,
  `[listo] ruta · MB · cuadros · total s`, y `Traceback` si falla. La web puede mostrar el avance
  a partir de `escritos a/N`.

## 8. Post-proceso local

```
# 4:3 a altura 4K + audio del clip de entrada (el modelo no devuelve audio)
ffmpeg -i salida.mp4 -i entrada.mp4 -filter_complex \
  "[0:v]scale=2880:2160:flags=lanczos,setsar=1,format=yuv420p[a]; \
   [0:v]scale=2880:2160:flags=lanczos,pad=3840:2160:480:0:black,setsar=1,format=yuv420p[b]" \
  -map "[a]" -map 1:a -c:v libx264 -preset slow -crf 14 -c:a copy -shortest -movflags +faststart 4K_43.mp4 \
  -map "[b]" -map 1:a -c:v libx264 -preset slow -crf 14 -c:a copy -shortest -movflags +faststart 4K_UHD.mp4
```
- Con origen 704×576 el ×4 da 2816×2304 y el paso a 2880×2160 es una corrección de aspecto
  (PAL tiene píxel no cuadrado), no un estirado. Con origen 490×360 sí hubo un Lanczos ×1,5.
- QC automático que sirvió: pares antes/después en 6-8 instantes (`hstack` del origen escalado con
  `neighbor` y la salida), más un recorte con zoom a las caras lejanas del plano más abierto. Es
  donde se ve cualquier invento del modelo.

## 9. Automatización (`nocturna.py`) y qué reusar de `h3pipeline.vast`

Flujo desatendido que corrió el 18/9: elegir oferta (preferida o la más barata que cumple) →
`PUT /asks/{id}/` → `autorizar_clave` → `esperar_lista(20 min)` → `subir` (setup, script, clip) →
`lanzar` setup y esperar `SETUP_OK|SETUP_FALLO` (límite 30 min) → `lanzar` inferencia y esperar
`[listo]|Traceback` (límite 80 min) → `scp` del resultado → `destruir` (en `finally`; si la bajada
falla deja la instancia viva para rescatarla a mano). Log en `nocturna.log`, estado en `estado.json`.

Reusar de `h3pipeline.vast`: `_pedir`, `autorizar_clave`, `esperar_lista`, `_ssh_args`, `subir`,
`lanzar` (setsid nohup con los tres descriptores redirigidos), `instancias`, `saldo`, `destruir`.
**No** reusar `ejecutar` para leer logs con barras de progreso: usa `text=True` y en Windows
revienta con cp1252; `nocturna.ssh()` decodifica utf-8 con `errors="replace"`.

Errores de esta corrida ya corregidos, para no repetir en la web:
1. `pkill -f '[i]nfer'` dentro de un ssh cuyo comando contenía «infer_trozos.py» se mató a sí
   mismo. Matar y lanzar en llamadas ssh **separadas** (regla 2 de `errores-de-proceso`).
2. `grep -E '[listo]|Traceback'`: «[listo]» es una clase de caracteres; el driver nunca vio el
   Traceback y habría esperado 80 min pagando. Marcadores con `grep -F -e … -e …`.
3. El fallback atrapaba sólo `OutOfMemoryError`; el VAE falla con `RuntimeError` de cuDNN.
4. Caracteres no ASCII (`━`, `…`) en comandos ssh o en prints: en Windows rompen el subprocess.
   `PYTHONIOENCODING=utf-8` y comandos ASCII.

## 10. Propuesta de integración en La Fábrica

Encaja en el patrón existente de `maquina` + `cola` (`/api/maquina/encender`, `/api/cola/*`,
`/api/vast/*`). Sugerencia mínima:

- **Nuevo tipo de tarea `remaster`** en la cola con: archivo origen (subida o ruta local), rango
  opcional (inicio/fin), variante (`full` / `tiny`), destino (2160p 4:3 / UHD con barras).
- **Análisis previo (local, gratis)**: sondeo del origen → devuelve resolución, entrelazado, DAR,
  bitrate y una **advertencia si el bitrate < ~5 Mbps a SD** («las caras lejanas se van a
  inventar»). Muestra 2-3 cuadros del origen.
- **Estimador de costo** (mostrarlo antes de encender): `segundos × factor × $/h ÷ 3600` con
  factor 60 (Full medido), 9 (Tiny estimado) más $1 fijo por sesión. Actualizar el factor con cada
  corrida real, como hace `COSTOS-H3`.
- **Máquina**: la actual de La Fábrica es 4×5090 para H3; el remaster necesita **1×A100 80 GB**
  (o 5090 sólo con Tiny, sin probar). Es otro perfil de `maquina`, con su propio setup
  (`setup-v2.sh`) y sin ComfyUI.
- **Avance**: parsear `escritos a/N` del log; taxímetro con el `dph_total` de la oferta.
- **Paralelismo**: los trozos son independientes → un capítulo se puede repartir entre K
  instancias (cada una con su rango de cuadros y su solape) y concatenar. Mismo costo, K× menos
  reloj.
- **QC**: generar los pares antes/después y el zoom a caras lejanas, y mostrarlos antes de
  ofrecer «bajar» o «destruir», como ya hace `bajar` con el detector de ruido de H3.
- **Regla dura**: destruir siempre al terminar o al fallar; nunca dejar instancias vivas entre
  sesiones (trampa histórica del proyecto).

## 11. Pendientes, en orden

1. **Cargar saldo** en Vast (quedan $0,18).
2. **A/B Tiny vs Full** sobre `entrada_mxf_19m16.mp4` (~$1, 30 min): si no se nota, el capítulo
   entero baja de ~$42 a ~$6. Script `infer_flashvsr_v1.1_tiny.py` / `…_tiny_long_video.py`
   del repo; portar `infer_trozos.py` a `FlashVSRTinyPipeline`.
3. Probar tiles `(96,160)/(80,144)` en Full (posible 2× extra).
4. Probar 5090 en Linux (compila BSA con `BLOCK_SPARSE_ATTN_CUDA_ARCHS=120` sobre imagen CUDA
   12.8; memoria con trozos de 53).
5. Capítulo entero: el máster completo (22,7 GB) quedó en `remasterizado/original/`
   (`CHIQUITITAS 2006 [001].mxf…`). Preparar por ventanas, no cargar 48 min a RAM.

## 12. Inventario de archivos

```
remasterizado/
  REMASTER-4K-HANDOFF.md          este documento
  ENTREGA-19m16/                  original 30 s + los dos 4K (lo que aprobó el usuario)
  original/                       máster MXF completo (descarga de Drive) + descarga.log
  prueba-30s/
    setup-v2.sh                   instalación completa, desatendida, con SETUP_OK/SETUP_FALLO
    setup-flashvsr.sh             versión 1 (histórica, con los tropiezos)
    infer_trozos.py               inferencia por trozos con solape y fallback de tiling  ← usar
    infer_prueba.py               inferencia de un solo bloque (sirve hasta ~1920×1408 con tiling)
    nocturna.py                   driver desatendido: alquilar→instalar→correr→bajar→destruir
    corrida.py                    driver manual por subcomandos (alquilar/log/correr/bajar/destruir/ssh)
    buscar_offset.py              ubicar un instante de una versión en otra por coincidencia de cuadros
    entrada_19m16_360p.mp4        origen pobre (302 kbps) de la corrida 1
    entrada_mxf_19m16.mp4         origen del máster, recortado y desentrelazado (corrida 2)
    salida_flashvsr_full.mp4      salida cruda corrida 1 (1920×1408)
    salida_mxf_flashvsr.mp4       salida cruda corrida 2 (2816×2304)
    Chiquititas_*.mp4             4K de ambas corridas
    qc/                           pares antes/después y zooms a caras (full_*, master_full_*, *_caras_lejanas)
    nocturna.log, estado.json     bitácora y estado de la última corrida
h3pipeline/vast.py                API de Vast reutilizable; VAST.md tiene las 18 trampas de alquiler
```

Memoria del proyecto relacionada: `remaster-sd-4k-modelo.md`, `vast-alquiler-trampas.md`,
`errores-de-proceso.md`, `solo-5090-al-alquilar.md` (política del usuario para H3; el remaster es
la excepción documentada porque exige 80 GB).
