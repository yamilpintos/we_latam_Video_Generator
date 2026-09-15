# Paso a paso: de alquilar la máquina a bajarte la película

Todo lo que hay que hacer, en orden. Unos 55 minutos de máquina encendida y
alrededor de **$1.80**.

Lo único que subís es **`ALADINO-PARA-VAST.zip`** (74 MB), que está en la raíz
del proyecto. Adentro va todo: los scripts, la lista de planos y los 42 dibujos.

---

## 1. Alquilar la máquina

En [vast.ai](https://cloud.vast.ai) → **Search**, con estos filtros:

| filtro | valor | por qué |
|---|---|---|
| GPU | **4× RTX 5090** | 32 GB por placa, que es lo que pide el perfil `max` |
| Disk Space | **150 GB** | 59 GB de modelos + ComfyUI + los videos que salgan |
| Reliability | **≥ 99.5 %** | probamos varias por debajo y se caían solas |
| Internet Down | **≥ 800 Mbps** | mirá el punto de abajo, es el filtro que más plata mueve |
| tipo | **`datacenter`** | las de casa particular son las que dieron `OCI runtime create failed` |

**El ancho de banda es el filtro que más importa**, más que el precio por hora.
Hay que bajar 59 GB antes de generar nada:

| enlace | descarga | te cuesta |
|---|---|---|
| 2000 Mbps | 4 min | $0.10 |
| 800 Mbps | 10 min | $0.25 |
| 250 Mbps | 31 min | $0.80 |
| 30 Mbps | **262 min** | **$6.65** |

Una máquina barata con enlace lento sale **más cara que generar la película
entera**. Aquella de 30.7 Mbps que te tocó habría costado $6.65 solo en esperar.

> **Licencia.** La MiniMax H3 Community License excluye **Estados Unidos, la
> Unión Europea, el Reino Unido y Corea del Sur** del despliegue local. Mirá el
> país del host **antes** de alquilar, que Vast lo muestra en la ficha.

**Template:** elegí uno de **ComfyUI**. El instalador da por sentado que ComfyUI
ya está corriendo bajo supervisor.

Dale a **RENT**. Cuando pase de *loading* a **running**, abrí **Open** →
**Jupyter**.

---

## 2. Subir el ZIP

En Jupyter, botón **Upload** (arriba a la derecha) → elegí
`ALADINO-PARA-VAST.zip`. Tarda un par de minutos.

> Subimos un ZIP y no la carpeta suelta porque **el Upload de Jupyter aplasta
> las carpetas**: los 42 dibujos caerían sueltos en vez de quedar dentro de
> `assets/`. Eso ya nos pasó una vez.

Después abrí **Jupyter Terminal** (New → Terminal) y pegá:

```bash
mkdir -p /workspace/refs && cd /workspace/refs && unzip -o ~/ALADINO-PARA-VAST.zip
```

Si dice que no encuentra el archivo, buscalo:

```bash
find / -name "ALADINO-PARA-VAST.zip" 2>/dev/null
```

Y comprobá que llegó todo — tienen que ser **42**:

```bash
ls /workspace/refs/assets/*.png | wc -l
```

---

## 3. Instalar el modelo

```bash
sed -i 's/\r$//' /workspace/refs/*.sh /workspace/refs/*.py
SOLO_FL=1 PERFIL=max bash /workspace/refs/vast-setup-h3.sh
```

El `sed` es un seguro por si algo tocó los archivos en Windows: los saltos de
línea de Windows rompen los `.sh`. Los del ZIP ya vienen bien, así que
normalmente no hace nada.

`SOLO_FL=1` es lo que baja **59 GB en vez de 106**. El perfil `max` trae dos
modelos Ref2VA —el GGUF de 23.9 GB y el `pruned_fp8` de 21— que este pipeline
**no usa nunca**, porque cada plano arranca de su dibujo en vez de referencias.

Tarda entre 5 y 30 minutos según el enlace. Al terminar imprime una verificación
así, y las cinco líneas tienen que decir `OK`:

```
  OK UnetLoaderGGUF         ['MiniMax-H3-FL2VA-Q5_K_M.gguf']
  OK CLIPLoader             ['qwen3vl_32b_minimax_h3_int8_convrot.safetensors']
  OK VAELoader              [...]
```

Si alguna dice `!!` o sale vacía, el modelo no quedó cargado. Casi siempre es que
ComfyUI cacheó la lista de modelos al arrancar:

```bash
supervisorctl restart comfyui
```

Esperá un minuto y volvé a correr el instalador — saltea lo que ya bajó.

---

## 4. Generar la película

```bash
PASOS=8 bash /workspace/refs/lanzar.sh
```

Levanta un ComfyUI por placa (puertos 18188 a 18191) y reparte los 42 planos.
Antes de arrancar chequea que estén los 42 dibujos, así no descubrís que falta
uno después de media hora pagando.

**Unos 45 a 56 minutos.** Para seguirlo:

```bash
tail -n3 /root/gpu?.log                              # qué está haciendo cada placa
ls /workspace/ComfyUI/output/video/*.mp4 | wc -l      # cuántos van de 42
```

Si querés más calidad y no te importa pagar el doble:

```bash
PASOS=20 TURBO=0 bash /workspace/refs/lanzar.sh
```

---

## 5. Montar

Cuando las cuatro placas dicen `termino 11/11 planos`:

```bash
python /root/planos.py --montar
```

Corta los 42 planos en orden y escribe los subtítulos. Salen dos archivos en
`/workspace/ComfyUI/output/video/`:

- `PELICULA.mp4` — la película, 5:09
- `PELICULA.srt` — los 8 diálogos con sus tiempos

Los subtítulos no necesitan Whisper: como nosotros elegimos cuánto dura cada
plano, el tiempo de cada línea es una suma.

---

## 6. Bajarte el resultado

En el explorador de archivos de Jupyter, navegá a
`workspace/ComfyUI/output/video/`, tildá `PELICULA.mp4` y `PELICULA.srt`, y
**Download**.

Si el navegador se atraganta con el MP4, serví la carpeta y bajala del link:

```bash
cd /workspace/ComfyUI/output/video && python -m http.server 8080
```

Después abrilo por el puerto 8080 que Vast te expone en la ficha de la
instancia.

**Bajá también los planos sueltos** (`P01_*.mp4` … `P42_*.mp4`) si pensás
retocar algo en un editor: son las tomas por separado, sin cortar.

---

## 7. Dejar de pagar

Esto es lo que más olvido genera, así que va explícito.

| botón | qué hace | cuándo |
|---|---|---|
| **STOP** | apaga la GPU pero **te sigue cobrando el disco** | si vas a volver en unos días: te ahorra rebajar los 59 GB |
| **DESTROY** | borra todo, dejás de pagar del todo | cuando ya te bajaste la película |

**Bajate los archivos ANTES de dar Destroy.** No hay vuelta atrás.

Si vas a volver pronto, Stop conviene: el disco cuesta centavos por día y te
ahorra los 10-30 minutos de descarga la próxima vez.

---

## Si algo sale mal

**Un plano salió feo.** Se rehace solo, no arrastra a ninguno:

```bash
rm /workspace/ComfyUI/output/video/P17_*
python /root/planos.py --gpu 0 --total 1
```

**Se cortó a la mitad.** Volvé a lanzar y sigue donde quedó — cada plano se
guarda por separado y el script saltea lo que ya existe:

```bash
PASOS=8 bash /workspace/refs/lanzar.sh
```

**Lo que está mal es el ENCUADRE de un plano.** Eso no se arregla con el prompt
de video: se arregla el **dibujo**. Regenerás `sb_P17.png` acá en tu máquina con
nanobanana, lo subís, y relanzás ese plano.

**Una placa no responde.** Mirá su log:

```bash
cat /root/comfy1.log
```

Casi siempre es que se quedó sin VRAM. Corré con menos placas:

```bash
GPUS=2 bash /workspace/refs/lanzar.sh
```

**`value_not_in_list` al encolar.** ComfyUI no ve los modelos:
`supervisorctl restart comfyui`, esperá un minuto y relanzá.

**Los dibujos quedaron en otro lado.** El lanzador los busca al lado suyo, pero
podés forzarlo:

```bash
ASSETS=/donde/esten bash /workspace/refs/lanzar.sh
```

---

## Resumen: los seis comandos

```bash
# 1. descomprimir
mkdir -p /workspace/refs && cd /workspace/refs && unzip -o ~/ALADINO-PARA-VAST.zip

# 2. instalar (5 a 30 min)
sed -i 's/\r$//' /workspace/refs/*.sh /workspace/refs/*.py
SOLO_FL=1 PERFIL=max bash /workspace/refs/vast-setup-h3.sh

# 3. generar (45 a 56 min)
PASOS=8 bash /workspace/refs/lanzar.sh

# 4. montar
python /root/planos.py --montar

# 5. bajar PELICULA.mp4 por Jupyter, y recién ahí DESTROY
```
