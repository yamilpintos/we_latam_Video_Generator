# Alquilar en Vast, sin tropezar

Todo lo que rompió las dos corridas reales —**78 SUR** el 28 de agosto de 2026 y
**CONTRAMANO** el 29—, con el síntoma exacto y el arreglo. Nada de esto estaba
documentado en ningún lado, y cada uno costó entre diez minutos y una instancia
entera.

**Todo está ya implementado en el módulo.** Esto es para entender por qué hace
lo que hace, y para reconocer el síntoma si vuelve a aparecer con otra cara.

Costó **~$9,20** aprenderlo entre las dos corridas. La generación en sí, $1,60.

---

## El flujo que funciona

Desde el 30/8 no hace falta entrar a la máquina: los pasos que antes se
tipeaban a mano por SSH —donde más se tropezó— son comandos. El flujo
desatendido corrió entero cuatro veces (30/8, 31/8, 2/9 y 3/9); las reglas que
salieron de esas corridas están al final de esta sección.

```bash
python -m h3pipeline empaquetar mi-video/proyecto.json
python -m h3pipeline alquilar   mi-video/proyecto.json --si --generar
python -m h3pipeline seguir     mi-video/proyecto.json <iid>   # hasta que estén todos
python -m h3pipeline bajar      mi-video/proyecto.json <iid>   # monta si falta y baja
python -m h3pipeline destruir   <iid> --si                     # SIEMPRE
```

`alquilar` **sin id elige sola la máquina**: la más barata que cumple lo que el
pipeline pide (4 placas de ≥32 GB — la 4090 trae 24, la de 32 es la 5090 —,
nada anterior a Ampere, verificada, país permitido por la licencia), ordenando
por **costo total del trabajo** (descarga de los 59 GB + generación), no por
$/h. Muestra el podio antes de cobrar, y sin `--si` sólo mira. Para elegir a
mano sigue estando `gpu` y pasarle el id.

`alquilar` hace, en orden: crea con el template oficial, **adjunta tu clave SSH
a la instancia**, espera a que el SSH conteste de verdad, y sube el ZIP. Con
`--generar` además deja la corrida entera andando sola (unzip + `sed` de los
saltos de línea + `setup.sh` + `lanzar.sh`, desatendido, log en
`/root/corrida.log`). `seguir` dice cuántos clips van, qué placa anda en qué, y
te recuerda cuánto está cobrando. `bajar` monta el MP4 en la máquina si falta y
baja clips, final, SRT y `metricas.json` a `mi-video/clips/`.

### La corrida limpia, en nueve reglas (3/9/2026)

Salen de las dos corridas de la réplica de @jcfdlw (`mis-videos/replica-jcfdlw/
NOTAS.md`), que costaron $12,40 y $4,86 por no cumplirlas todas.

1. **Clips de 5,17 s, y nada más.** 56 clips en dos corridas sin un reintento.
   5,88 pierde ~1 de 10 aun con tres pasadas (4 min de GPU por pasada fallida);
   6,58 falló 4 de 5. Lo que necesite más de 4,87 s de línea se parte en dos.
2. **La máquina se elige por fiabilidad, a dedo, con `gpu` + id.** La oferta
   más barata (Shanghái, $1,60/h) quedó 20 min en `loading` sin arrancar y
   costó $0,96 en nada; reapareció con otro id apenas se destruyó. Nunca la más
   barata, nunca un host que ya colgó, siempre 4×5090.
3. **Un clip por encuadre, no por toma** (`clip_de` en `proyecto.json`): las
   tomas que repiten encuadre reusan el clip de la primera con otro `usa`. Con
   piso 5,17 y tomas de 2,3 s, un clip sirve a dos tomas. Ahorra más imágenes
   que GPU (−18 % de segundos generados, cero dibujos nuevos).
4. **Las placas gráficas no se generan**: H3 metió a la protagonista en la
   placa cósmica dos veces. Se hacen como imagen fija en el montaje.
5. **«NO subtitles» en el prompt no frena los subtítulos alucinados.** H3 los
   quema porque el ESTILO nombra un género que los lleva («Chinese short-drama»).
   Describir el look sin nombrar el género de origen.
6. **QC de clips con reloj, en una pasada**: `bajar` → `qc_clips` (entrada /
   medio / salida de cada fuente) → decidir → `destruir`. Cada ida y vuelta con
   la máquina parada son ~$0,50. Lo que no salió va a plan B sin GPU (dibujo
   con zoom, o el clip de una corrida anterior si es lo bastante largo).
7. **Nada vivo entre sesiones.** Los vigías mueren con el proceso local (la red
   del usuario se corta); la instancia no. Al retomar: `instancias` primero,
   `seguir` después, y `destruir` en la misma sesión que bajó los clips.
8. **`python -X utf8 -u` para todo lo que escriba log** en Windows: sin `-u` el
   log queda bufferizado y ciego; sin `-X utf8` una «→» en `funcion` revienta
   el montaje en cp1252.
9. **La imagen sigue a la voz**, no al revés: cuando la voz medida no entra en
   la ventana del guion, el corte se mueve (`linea_de_tiempo.py` en la réplica).
   Antes de esto la voz terminaba 5 s tarde y las últimas frases se truncaban.

El camino a mano sigue existiendo (`generar` sin `--generar` en alquilar
imprime los comandos), por si hay que depurar algo adentro:

```bash
cd /workspace/refs && unzip -oq mi-video-para-vast.zip
sed -i 's/\r$//' *.sh *.py
bash setup.sh                        # ~59 GB · 2-5 min con buen enlace
PASOS=8 bash lanzar.sh               # ~4 min por clip, 4 en paralelo
python /root/runner.py --montar
```

---

## Las catorce trampas

### 1 · La API v0 de instancias está deprecada

**Síntoma:** `HTTP 410 · deprecated_endpoint · /api/v0/instances/ is deprecated`.

`/instances/` migró a **v1**, pero `/bundles/` **no existe** en v1 — la búsqueda
sigue en v0. En vez de fijar la versión por endpoint, `_pedir()` pide en v0 y,
si contesta 410, reintenta en v1 solo. Así sobrevive a la próxima migración.

### 2 · La imagen tiene que ser el template oficial, no `image` + `onstart`

**Síntoma:** la instancia queda en `running` con **todos los puertos cerrados**.
El proxy SSH acepta el TCP y cierra sin mandar banner. Jupyter tampoco responde.

Pasar `image` y un `onstart` propio te da un contenedor que arranca y no sirve
para nada. El template oficial trae `onstart: entrypoint.sh`, que es lo que
levanta sshd, Jupyter y supervisor, más un `env` con los puertos, el
`PROVISIONING_SCRIPT` que instala ComfyUI y `COMFYUI_ARGS=--port 18188`.

Se alquila con `template_hash_id` = `2188dfd3e0a0b83691bb468ddae0a4e5`
(el template «ComfyUI», 22.667 instancias creadas).

**Y el tag lo resuelve Vast** (`@vastai-automatic-tag`). Fijar uno a mano es cómo
terminás con `cuda-12.8-auto`, que existe pero es de enero de 2026 — anterior a
los nodos de H3, así que `runner.py` moriría con «no encontré la plantilla».

### 3 · El proxy SSH no sirve con una API key de team

**Síntoma:** `kex_exchange_identification: Connection closed by remote host`.
Cierra **antes de autenticar**, así que no es la clave.

Vast da dos caminos y no son equivalentes:

| | cómo | qué claves usa |
|---|---|---|
| proxy | `ssh_host` (sshN.vast.ai) + `ssh_port` | las de la **cuenta** |
| directo | la IP pública + el puerto mapeado al 22 | las de la **instancia** |

Una API key de *team* no puede registrar claves de cuenta
(`Team SSH keys are not supported. SSH keys can only be created in personal
context`), así que el proxy nunca va a enrutar. **El directo sí funciona.**

`_ssh_args()` prefiere el directo siempre: busca `ports["22/tcp"]` y usa
`public_ipaddr`.

### 4 · La clave SSH va adjunta a la instancia

`POST /api/v0/instances/{id}/ssh/` con `{"ssh_key": "ssh-ed25519 AAAA…"}`.

Eso sí lo permite una key de team, y es lo que habilita el SSH directo.
`vast.autorizar_clave()` lo hace solo dentro de `alquilar`.

### 5 · `python` no existe en el PATH

**Síntoma:** `setup.sh: line 153: python: command not found`, y la verificación
final del instalador no corre.

En la imagen de ComfyUI el intérprete está en **`/venv/main/bin/python`**, y un
shell no interactivo por SSH no trae el venv en el PATH.

Consecuencia peor: el `pip install gguf` del setup fue al intérprete equivocado,
así que **`UnetLoaderGGUF` no cargaba** y el modelo GGUF de 23,9 GB quedaba
inservible. Se arregla con:

```bash
/venv/main/bin/python -m pip install gguf
supervisorctl restart comfyui
```

`lanzar.sh` ahora antepone `/venv/main/bin` al PATH.

### 6 · El workflow se arma con los valores corridos

**Síntoma:** `HTTP 400 · prompt_outputs_failed_validation`, y en el detalle:
`124.denoise: Value 20.0 bigger than max of 1.0`.

`widgets_values` de la plantilla es una **lista posicional** que no dice a qué
campo va cada valor. Cuando un widget se convierte en entrada por cable —acá,
`steps` de `BasicScheduler`— la posición sigue ocupada y todo lo que viene
después se corre un lugar. El `20` que era de `steps` cayó en `denoise`.

`runner.sanear()` contrasta cada valor contra el rango que declara
`/object_info` y devuelve al default el que no entra. Es general: ataja el
próximo desfase, no sólo éste.

### 7 · Falta VRAM en los últimos clips

**Síntoma:** `Allocation on device 0 would exceed allowed memory (out of
memory). Currently allocated: 25.37 GiB · Device limit: 31.36 GiB`.

El GGUF Q5 ocupa 23,9 GB de los 32, y la memoria se fragmenta después de varios
clips seguidos. En la corrida real fallaron **2 de 12**, los dos en el tercer
clip de su placa.

No es un problema de configuración: se **reintenta con la VRAM limpia**. El
runner saltea los que ya existen, así que basta con reiniciar ComfyUI y volver
a lanzar. Los dos salieron a la primera.

**Medido el 31/8 con 41 planos (EL LOCO DEL CARBÓN):** el `/free` de ComfyUI
que usa `liberar_vram()` **no alcanza** cuando el OOM ya apareció: S30 (7,3 s)
falló seis veces seguidas con `/free` entre medio, y S17 (6,6 s) tres. Los dos
salieron a la primera con un **proceso de ComfyUI recién arrancado** en esa
placa. En cambio S39 y S33 sí se rescataron con el reintento simple. Regla:
el reintento con `/free` sirve para el OOM ocasional; el OOM que se repite
pide **matar y relanzar el proceso** de la placa. Eso hace `rescate.sh`, que
`lanzar.sh` deja esperando: cuando los runners terminan, reinicia la placa de
cada plano caído y lo rehace. De 41 planos, 4 necesitaron reintento y 2 de
esos necesitaron el proceso fresco; 0 quedaron sin hacer.

Si pasa seguido, las palancas son bajar la resolución o usar el `pruned_fp8` en
vez del GGUF. Y si un plano de 7,3 s no entra ni con proceso fresco (S22 y S30
el 31/8, nueve OOM), **se baja a 6,6 s**: se edita `segundos`/`corta` en el
proyecto, se sube el `planos.json` nuevo y se rehace. Ojo: al cambiar
duraciones **el reparto por carga se rebaraja** y un plano puede quedar sin
runner que lo reclame — `rescate.sh` termina con una pasada atrapa-todo
(`runner.py --gpu 0 --total 1`) justamente por eso.

### 8 · `nohup … &` cuelga la sesión SSH

**Síntoma:** el comando corre en la máquina pero el cliente ssh se queda colgado
hasta el timeout.

ssh no cierra la sesión mientras el proceso conserve stdout o stderr. Hay que
redirigir los tres descriptores y despegarlo con `setsid`:

```bash
setsid nohup bash -c '<comando>' > /root/tarea.log 2>&1 < /dev/null &
```

Es lo que hace `vast.lanzar()`.

### 9 · El `cd` no se hereda después de un `&`

**Síntoma:** `can't open file '/root/main.py': No such file or directory` al
levantar el segundo ComfyUI.

`cd X && cmd1 & cmd2` deja a `cmd2` en el directorio original. Cada uno necesita
su propio `cd`, entre paréntesis:

```bash
(cd /workspace/ComfyUI && CUDA_VISIBLE_DEVICES=3 python main.py --port 18191) &
```


### 10 · Un plano encadenado no entra en 7,3 s

**Síntoma:** el mismo out-of-memory de la trampa 7, pero **en el primer clip de
la cadena**, no en el tercero. Y no lo arregla reintentar.

Un plano encadenado carga **dos** cosas a la vez: el GGUF de 23,9 GB y el último
fotograma del plano anterior como condicionamiento. En 32 GB de VRAM eso cierra
el margen justo donde 78 SUR ya venía raspando.

**La regla, medida:** en 32 GB, **con encadenado no pasar de 5,9 s por plano**
(`length = 5*17+5 = 90`, o sea 5,17 s, es el escalón seguro). Suelto sí llega a
7,3 s. Si hace falta una toma continua más larga, se hace con **más eslabones
cortos**, no con eslabones largos.

### 11 · Un eslabón caído deja una placa parada el resto de la corrida

**Síntoma:** la corrida termina en 28 minutos más de lo previsto y una de las
cuatro placas figura sin trabajo casi todo ese tiempo. La factura sube y no hay
ningún error a la vista.

Los planos sueltos son independientes: si uno falla, se rehace y listo. Una
cadena **no**: S06 no puede empezar sin el último fotograma de S05. Cuando S05
murió por OOM, su placa se quedó sin nada que hacer —los otros planos ya estaban
repartidos— mientras seguía cobrando por hora.

Dos cosas lo evitan, y desde el 30/8 **las dos están en el runner** (sin
verificar todavía en una corrida real):

- **Los eslabones encadenados van primero en su placa.** `reparto()` ya
  repartía cadenas enteras por carga (greedy, la más larga primero) para que
  una cadena nunca se parta entre placas; ahora además las ordena al frente:
  si el cabeza —el plano de mayor riesgo de la tanda— falla, falla temprano,
  con los planos sueltos todavía por hacer para que la placa no pare.
- **El runner repasa lo que falló, hasta tres pasadas**, liberando la VRAM
  entre una y otra. Una cadena rota ya no espera a que alguien la vea: el
  cabeza reintenta primero y sus eslabones salen detrás, en orden. Si tras
  tres pasadas algo sigue caído, el runner sale con código 2 y lo lista.

### 12 · `lanzar.sh` arranca antes de que ComfyUI vuelva del reinicio

**Síntoma (31/8, EL LOCO DEL CARBÓN):** `corrida.log` termina en
`!! no encontré ComfyUI`, `seguir` muestra 0 clips durante 20 minutos, y la
máquina cobra. Justo antes, la verificación del `setup.sh` murió con
`Connection refused`.

`setup.sh` reinicia ComfyUI para que vea los modelos recién bajados y esperaba
**3 minutos** a que el puerto 18188 volviera. Con 59 GB de pesos nuevos el
primer arranque tarda más, así que la verificación corrió contra un puerto
cerrado y `lanzar.sh` —que le pregunta al proceso dónde vive ComfyUI— no
encontró ningún proceso. En la corrida desatendida nadie está mirando.

Arreglo, en los dos scripts: `setup.sh` espera hasta 10 minutos; `lanzar.sh`
espera a que el 18188 responda antes de buscar el proceso, recorre **todos** los
`main.py` (no el primero) y si igual no puede leer el cwd cae a las rutas
conocidas. Si vuelve a pasar con otra cara, el rescate a mano es:

```bash
export PATH=/venv/main/bin:$PATH && cd /workspace/refs && PASOS=8 GPUS=4 bash lanzar.sh
```

(desde acá: `vast.lanzar(inst, "<eso>", log="/root/corrida2.log")`).

### 13 · La imagen puede ser anterior a H3 aunque el tag lo resuelva Vast

**Síntoma (31/8, EL LOCO DEL CARBÓN):** los cuatro runners arrancan, imprimen
`!! no está en las rutas habituales, buscando en todo el disco…` y mueren; y
`/object_info` sólo lista `MinimaxTextToVideoNode`, `MinimaxImageToVideoNode`,
`MinimaxHailuoVideoNode` (los de la API de Hailuo). **No hay ningún
`MiniMaxH3…`**: el ComfyUI de la imagen era v0.7.0 del 30/12/2025, ocho meses
anterior a H3. Ayer la A100 con el mismo template tenía los nodos; el host de
hoy sirvió una imagen vieja. El tag automático no garantiza la fecha.

Y de yapa: el paquete de plantillas de esa imagen (0.7.64) **no trae**
`video_minimax_h3_r2v.json`, así que aunque hubiera nodos el runner no tendría
grafo. La plantilla sigue viva en el repo de Comfy:
`raw.githubusercontent.com/Comfy-Org/workflow_templates/main/templates/video_minimax_h3_r2v.json`,
con los mismos ids de nodo que espera `runner.py`.

**Arreglo, implementado en `setup.sh`:** después de encontrar ComfyUI pregunta
por `MiniMaxH3ImageToVideo`; si falta, hace `git fetch/reset` a master +
`pip install -r requirements.txt` (~2 min, torch no se toca) y actualiza
ComfyUI-GGUF. Y baja siempre la plantilla del repo a `/root/plantilla_h3.json`;
`lanzar.sh` la pasa por `PLANTILLA` si el paquete no la tiene. A mano fue:

```bash
cd /workspace/ComfyUI && git stash; git fetch --depth 1 origin master && git reset --hard FETCH_HEAD
pip install -r requirements.txt && supervisorctl restart comfyui
pkill -f '[m]ain.py --disable-auto-launch --port 1819'    # los ComfyUI 1-3 viejos, en memoria
PLANTILLA=/root/tpl_video_minimax_h3_r2v.json PASOS=8 GPUS=4 bash /workspace/refs/lanzar.sh
```

### 14 · Una placa defectuosa devuelve RUIDO, con el mismo tiempo y tamaño que un clip bueno

**Síntoma (31/8, EL LOCO DEL CARBÓN):** el máster arranca con estática de
colores. La placa 1 del host (máquina 137085 de Vast) generó **once clips de
ruido puro** — mismos minutos, mismo bitrate, ningún error en el log — y no se
vio hasta el control visual del máster, **con la instancia ya destruida**.
Rehacerlos costó otro alquiler.

Tres arreglos, todos implementados:

- **El runner chequea cada clip al salir** (`es_ruido()`: un fotograma de ruido
  no comprime — a 192 px y JPEG q5, ruido pesa ~25 KB y un clip bueno 4-15).
  Si detecta ruido borra el clip y **para esa placa** con código 3: es
  hardware, reintentar ahí es tirar plata. El rescate lo rehace en otra.
- **`bajar` escanea todos los clips bajados** antes de sugerir `destruir`, y si
  hay ruido lo dice y NO recomienda destruir.
- La regla de oro que esto deja: **el control de calidad va ANTES de
  `destruir`**, siempre. Destruir con clips sin mirar fue el error más caro
  del día.

**Trampa dentro de la trampa (dos veces el mismo día):** `pkill -f` mata al
propio script si el patrón aparece literal en su línea de comando. Pasó con
`pkill -f runner.py` desde una sesión ssh (la sesión contiene "runner.py") y
volvió a pasar con `pkill -f '[m]ain.py --disable-auto-launch --port 18189'`
en un script que **más abajo arrancaba** `python main.py --disable-auto-launch
--port 18189`: el texto literal del arranque estaba en el mismo `bash -c`, y
el script murió sin dejar log. Y una tercera vez con `pkill -f '[r]unner.py
--gpu 1 '` en el script que **relanzaba** `runner.py --gpu 1`. La regla que
cierra las tres: **matar y arrancar en llamadas ssh separadas** — un
`ejecutar()` que sólo mata, y después un `lanzar()` que sólo arranca. Dentro de
un mismo script, cualquier `pkill -f` es una ruleta.

---

## Lo que hay que mirar al elegir máquina

Ya está todo en `vast.buscar()`, pero conviene saber por qué:

- **4 placas de ≥32 GB.** La RTX 4090 de fábrica trae 24 GB: la de 32 es la
  **5090**. El filtro va por gigas, no por nombre.
- **Una Tesla V100 tiene los mismos 32 GB y es de 2017**, sin bf16 nativo, que
  es lo que piden las LoRAs turbo. Se descarta por nombre.
- **`deverified`** es una máquina a la que Vast le *sacó* la verificación, y el
  filtro `verified` de la consulta la deja pasar igual. Hay que mirar el campo
  `verification` de la respuesta.
- **La licencia de H3 excluye EE.UU., la UE, el Reino Unido y Corea del Sur.**
  Eso saca casi la mitad de la oferta.
- **Se ordena por costo total del trabajo, no por $/h.** Hay que bajar 59 GB
  antes del primer plano: una máquina de $3.20/h con 3230 Mbps puede salir más
  barata en total que una de $1.76/h con 893.

---

## Los números reales

### 78 SUR · 28/8 · planos sueltos

12 planos de 5,2 a 7,3 s · 768×1344 · 8 pasos con turbo · 4× RTX 5090.

| | |
|---|---|
| tiempo por clip | 3,6 a 5,9 min |
| **min de GPU por segundo de video** | **0,67 a 0,81** |
| GPU total | 54,9 min |
| pared con 4 placas | ~14 min |
| costo de generación | ~$0.75 |
| descarga de los 59 GB | 2-5 min a 3230 Mbps |

Son los primeros puntos medidos **entre 5 y 7 segundos**, que es justo donde la
curva de costo extrapolaba a ciegas.

### CONTRAMANO · 29/8 · con tres cadenas

12 planos · 768×1344 · 8 pasos con turbo · 4× RTX 5090. Dos cadenas de tres y
de dos eslabones (S05→S06→S07 y S09→S10).

| | |
|---|---|
| costo total | ~$5,20 |
| de eso, desperdicio por el OOM de S05 | ~28 min de una placa parada |
| líneas de diálogo con isocronía medida | 5 |
| factores finales | 1,04× · 1,30× · 1,10× · 1,12× · 0,93× |

**Lo caro no fue generar: fue la cadena rota.** Es de donde salen las trampas 10
y 11.

### 15 · Una oferta puede tener un precio absurdo, y el selector no mira el techo

**Síntoma (11/9/2026):** apareció una 4× RTX 5090 en Noruega, fiabilidad 0,997,
934 Mbps… a **$213,34/h**. Un cazador automático que elegía por fiabilidad la
intentó alquilar. Vast la rechazó por su propio máximo ($128/h de GPU), no por
nada nuestro. Con un precio erróneo de $50/h habría pasado.

**Regla:** todo alquiler automático lleva techo de `dph` (4 $/h para 4×5090;
las reales están entre 1,9 y 3,3). `vast.buscar()` ordena por costo total pero
no descarta por precio: el techo va en quien alquila.

### 16 · Una host «deverified» no arranca: tres de tres, 20 min cada una

**Síntoma (13/9/2026):** con cero 4×5090 verificadas en toda la oferta, se
probaron las tres desverificadas de mejor pinta (Taiwán 0,988 · Columbia
Británica 0,998 · Australia 0,995, todas con 800-900 Mbps). Las tres quedaron
en `created` los 20 minutos del plazo y se destruyeron sin haber arrancado.
La fiabilidad alta no predice nada cuando la verificación está retirada.

**Regla:** «deverified» es un no, aunque no haya otra cosa. Si no hay 5090
verificadas, se espera (el cazador `mis-videos/lofi-koi/cazar.py` consulta
cada minuto). Y si alguna vez se fuerza una, el plazo de arranque se acorta a
8 min: a esa altura una host sana ya está en `running`.

### 17 · Una host en China continental arranca bien y no puede bajar los modelos

**Síntoma (14/9/2026, máquina 138100, «Shanghai, CN», verificada, 0,997):** lista
en 4,1 min, pero `setup.sh` se queda en `>> diffusion_models/…` con el disco
quieto y ~7 KB/s de red. `git clone` de ComfyUI-GGUF muere con `Failed to
connect to github.com port 443`.

Medido desde la máquina: `huggingface.co` y `github.com` no responden;
`hf-mirror.com` contesta la API pero **redirige los archivos a
`cas-bridge.xethub.hf.co`, que también está bloqueado**; `pypi.org` anda;
**ModelScope tiene todo** (`Comfy-Org/MiniMax-H3` y `lightx2v/Minimax-h3-Turbo`,
LoRAs de 768p incluidas) pero da ~0,9 MB/s y corta los pedidos por rangos:
76 GB en más de 20 horas. Se destruyó a los 35 min ($1,70).

**Regla:** fuera China continental (Hong Kong sí tiene salida). El cazador de la
réplica la excluye por `geo` y además, apenas la máquina está lista, prueba
`curl https://huggingface.co/api/models/Comfy-Org/MiniMax-H3`; si no da 200, la
destruye antes de pagar una descarga que no avanza. `setup.sh` ahora cae solo al
espejo si huggingface.co no responde, y al perfil `int8p` (modelos oficiales de
Comfy-Org, sin nodo GGUF) si github.com no responde — útil sólo si el espejo
realmente entrega archivos.

**Y un error de `setup.sh` que salió en la misma corrida:** la verificación de
nodos de H3 se hacía aunque ComfyUI no hubiera arrancado todavía (la máquina
seguía bajando su portal), y lo tomaba por «faltan los nodos» e intentaba
actualizar ComfyUI. Ahora sólo actualiza si ComfyUI responde y los nodos faltan.

## La máquina compartida (16/9/2026)

Desde la Fábrica (`python -m h3pipeline.app`) la máquina es una cosa aparte
del proyecto: el botón «Buscar una 4×5090 y encender» de la portada elige la
oferta apta de mayor fiabilidad (o caza cada minuto si no hay), la alquila,
sube `remoto/*` e instala H3 una sola vez (`app/encender.py`). La portada
muestra la fase (buscando · arrancando · instalando X de 59 GB · lista), el
precio, los minutos, lo gastado y el **saldo de Vast** (`vast.saldo()`, de
`/users/current/`). Con la máquina lista, cada proyecto empaquetado se genera
en ella desde su paso Máquina («Generar en la máquina», `app/generar_en.py`:
aparta las salidas del anterior, sube el ZIP y corre sólo `lanzar.sh`). El
botón «Apagar» destruye la instancia y escribe el gasto final. El estado vive
en `app/maquina.json`. Sigue valiendo la regla 7: nada vivo entre sesiones.
