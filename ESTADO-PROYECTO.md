# Estado del proyecto

Actualizado: **30 de agosto de 2026.** Este archivo es el mapa. Si venís de cero
o volvés después de un tiempo, se lee éste y nada más hasta saber a dónde vas.

El proyecto hace **videos generados con IA**, de punta a punta: de una idea a un
MP4 con voz, música y ambiente, generando el video con **MiniMax H3** en una GPU
alquilada por hora en **Vast.ai**.

Hay **dos mitades**, y conviene pensarlas separadas porque fallan por razones
distintas:

| | qué resuelve | dónde vive | estado |
|---|---|---|---|
| **A · Pipeline + web** | idea → storyboard → prompts → voz → montaje | `h3pipeline/` | funciona, dos videos hechos |
| **B · Vast** | conseguir la máquina, generar barato, no perder plata | `h3pipeline/vast.py`, `remoto/`, `VAST.md` | funciona, once trampas ya pagadas |

---

## Lo que está hecho y verificado

**Cuatro videos completos, de punta a punta, con GPU real.** No son demos: se
alquiló la máquina, se generó, se bajó, se montó y se apagó. El cuarto, **EL
LOCO DEL CARBÓN** (31/8, `mis-videos/loco-carbon/`), es el primero del formato
largo tipo recap (3:58, 41 planos, voz continua, subtítulos quemados,
estructura `recap`) y el que define el rumbo del canal — ver
`referencias/jcfdlw/ANALISIS.md` y `mis-videos/loco-carbon/RECETA.md`.

| | 78 SUR | CONTRAMANO | EL DRON DEL VOLCÁN |
|---|---|---|---|
| carpeta | `mis-videos/78-sur/` | `mis-videos/contramano/` | `mis-videos/dron-volcan/` |
| final | `78 SUR - final.mp4` | `CONTRAMANO.mp4` | `EL DRON DEL VOLCAN - final.mp4` |
| duración | 60,02 s | 59,52 s | 60,15 s |
| qué probó | el flujo entero por primera vez | encadenado + diálogo con isocronía | **la corrida desatendida** (30/8) y la primera serie A100 |
| audio | 8 líneas de voz en off + música | 5 diálogos con isocronía medida + música | 12 líneas de voz en off + música |
| planos encadenados | ninguno | 3 (dos cadenas) | ninguno |
| costo real | ~$4 | ~$5,20 | **~$2,7** (GPU ~$2,4 + imágenes ~$0,30) |
| generación pura | $0,75 | ~$0,85 | ~$1,7 (A100: 0,86 min/s, §13 de COSTOS) |

La diferencia entre el costo real y la generación pura **es el aprendizaje**:
máquinas mal alquiladas, cadenas rotas, reintentos. Está todo anotado para que
no se pague dos veces.

### Los números medidos que valen para presupuestar

- **0,67 a 0,81 minutos de GPU por segundo de video**, a 8 pasos con turbo,
  768×1344, en RTX 5090. Doce puntos reales entre 5,2 y 7,3 s por plano.
- Un short de 60 s ≈ **55 min de GPU**, ≈ 14 min de pared con 4 placas.
- La descarga de modelos son **59 GB** antes del primer plano: 2-5 min con buen
  enlace, **262 min** con uno malo. Por eso se ordena por costo total, no por
  $/h.
- Todo el detalle en `COSTOS-H3.md` §12. **Leerlo antes de estimar nada.**

---

## A · El pipeline y la web

`h3pipeline/` son ~4.900 líneas, **módulo importable, no programa**. La app
llama a las funciones; `python -m h3pipeline` es una conveniencia para trabajar
a mano.

### El flujo, en orden

```
idea  →  Mesa de Armado (web)  →  proyecto.json  →  construir  →  storyboard.json
      →  voz  →  frames (PNG, se revisan acá)  →  empaquetar (ZIP)
      →  [ Vast: gpu · alquilar · generar · bajar · destruir ]
      →  montar  →  voz + música + ambiente  →  MP4
```

El orden no es casual: **los dibujos se revisan con la GPU apagada.** Un
encuadre malo se ve en un PNG en dos segundos; verlo después de cuatro minutos
de generación cobrando, no.

### Las piezas

| archivo | qué hace |
|---|---|
| `estructura.py` + `estructuras/*.json` | **la ley**: los tramos por segundo, qué exige cada uno |
| `proyecto.py` | proyecto declarativo → storyboard + planos, con validación |
| `prompts.py` | arma el prompt de H3 con todos los bloques obligatorios |
| `frames.py` | los primeros fotogramas (nano banana / OpenAI) |
| `voz.py` | densidad y emoción: ~17 cps, tolerancias de estirado |
| `tts.py` | ElevenLabs v3, varias redacciones por línea, gana la que mide mejor |
| `doblaje.py` | isocronía: hacer calzar la voz con una boca ya animada |
| `musica.py` | ElevenLabs Music |
| `montaje.py` | recorte, concatenado, la mezcla de tres capas, subtítulos |
| `vast.py` | buscar, alquilar, subir, destruir |
| `remoto/` | lo que corre **dentro** de la máquina: `setup.sh`, `lanzar.sh`, `runner.py` |
| `web.py` + `web/` | la Mesa de Armado |
| `costos.py` | presupuesto antes de gastar |

### La ley de retención 2026

`Estructuras_Contenido_Alta_Retencion_2026.docx` manda para los shorts, y lo que
aplica se lleva al largo. Está implementado, no es documentación suelta: el
módulo **valida** contra los tramos y avisa cuando un plano no cumple lo que su
tramo exige.

Tres duraciones, cada una con su umbral:

| | para qué sirve | retención |
|---|---|---|
| `short-23` | alcance puro, regla 3/8/12 | 65 % |
| `short` | el estándar, entra en las tres plataformas | 50 % |
| `short-90` | guardados y comunidad, rinde en TikTok | 45 % |
| `largo` | narrativo, 5-8 min, re-enganche cada 60-90 s | — |

### La Mesa de Armado

```bash
python -m h3pipeline.web        # escribe h3pipeline/web/mesa.html
```

Elegís formato y estructura, cargás idea, estilo y cómo se cuenta el audio, y
sale **la instrucción que se le pasa al LLM** para que escriba los planos: la ley
entera, el esqueleto de huecos y el `proyecto.json` a completar. Tiene además la
pestaña **Trampas de Vast**.

Se genera **desde el módulo**, no a mano: si cambia un tramo en el JSON, cambia
en la página. Una copia escrita a mano se desincroniza en una semana.

### Las reglas del oficio

`h3pipeline/REGLAS.md` — **39 reglas, cada una con lo que costó aprenderla.** Es
el documento más denso del proyecto. Las que más cambian una decisión:

- **1** · planos sueltos por default, no encadenados (sale 20-35 % más barato y
  un clip malo no arrastra a los siguientes)
- **18** · la ley de retención
- **19** · un corte **no** es una interrupción de patrón
- **21** · el audio de H3 **viene clipeado** (+2,68 dBFS medido): masterizar
  siempre
- **24** · H3 hace lo que nace y muere dentro del plano; ElevenLabs, todo lo que
  cruza el corte
- **25** · la densidad manda y se arregla **en el texto**, no estirando el audio
- **28** · al doblar, la ventana la define **la boca**, no el ASR ni la onda
- **38 y 39** · encadenado: techo de 5,9 s por eslabón, y una cadena rota deja
  una placa parada

---

## B · Vast: la parte que cuesta plata

`h3pipeline/VAST.md` — **once trampas**, cada una con síntoma, causa y arreglo.
Todas están ya implementadas en el módulo; el documento existe para reconocer el
síntoma si vuelve con otra cara.

### El flujo que funciona

Desde el 30/8, **sin entrar a la máquina** (los comandos nuevos todavía no
corrieron contra una instancia real — la primera corrida los estrena):

```bash
python -m h3pipeline empaquetar mi-video/proyecto.json
python -m h3pipeline alquilar   mi-video/proyecto.json --si --generar
python -m h3pipeline seguir     mi-video/proyecto.json <iid>  # hasta que estén todos
python -m h3pipeline bajar      mi-video/proyecto.json <iid>  # monta si falta y baja
```

`alquilar` sin id elige sola la máquina más barata que cumple (4× ≥32 GB, por
costo total del trabajo, no $/h) y con `--generar` instala H3 y lanza todo.
Para elegir a mano: `gpu` y pasarle el id.

Y al terminar, **siempre**:

```bash
python -m h3pipeline destruir <iid> --si
```

El camino a mano por SSH sigue documentado en `VAST.md`, por si hay que
depurar adentro.

### Las cuatro que más duelen

1. **Alquilar con `template_hash_id`, nunca con `image` + `onstart` propio.** Un
   contenedor sin `entrypoint.sh` queda en `running` con todos los puertos
   cerrados y no sirve para nada.
2. **SSH directo, no el proxy.** Una API key de *team* no puede registrar claves
   de cuenta, así que el proxy nunca enruta. La clave se adjunta **a la
   instancia** y se entra por IP pública + puerto mapeado al 22.
3. **La máquina se elige por costo total del trabajo, no por $/h.** Hay que bajar
   59 GB antes del primer plano.
4. **Apagarla.** `destruir` apenas bajaste los clips. Es lo que más olvido
   genera y lo más caro de la lista.

### Qué máquina

**4 placas de ≥32 GB.** Y hay filtros que no son obvios:

- Una RTX 4090 de fábrica trae **24 GB**: la de 32 es la **5090**.
- Una Tesla V100 tiene los mismos 32 GB **y es de 2017**, sin bf16 nativo, que
  es lo que piden las LoRAs turbo. Se descarta por nombre.
- `deverified` es una máquina a la que Vast le **sacó** la verificación, y el
  filtro `verified` de la consulta la deja pasar igual.
- **La licencia de H3 excluye EE.UU., la UE, el Reino Unido y Corea del Sur.**
  Eso saca casi la mitad de la oferta.

Todo eso ya lo hace `vast.buscar()`; está acá para entender por qué descarta lo
que descarta.

### Pedir 250 GB de disco

Con 150 se llenó y una corrida no llegó a arrancar.

---

## Voz, música y doblaje

**La regla de oro:** H3 genera lo que nace y muere dentro del plano —viento,
motor, metal, estática—. Todo lo que **cruza el corte** —una voz, una música, un
ambiente continuo— sale de ElevenLabs. Verificado: los IDs de hablante `(S1)` /
`(S2)` de H3 valen dentro de un clip, **no entre clips**.

**La mezcla son tres capas** (`montaje.mezclar`), con ducking por
`sidechaincompress` disparado por la propia voz:

1. el audio de H3, agachado mientras alguien habla
2. la voz de ElevenLabs, arriba de todo, sin comprimir
3. la música, debajo y es la que más se corre

Y el máster va **siempre** a −14 LUFS / −1 dBTP. No es opcional: el audio de H3
sale clipeado.

### Isocronía

El método está en `ISOCRONIA.md` y el motor en `h3pipeline/doblaje.py`.
Lo esencial:

- **La ventana la define la boca**, medida sobre el stem de voz separado con
  demucs — no el ASR, no la onda cruda.
- **El texto se escribe para la ventana**, no al revés. Si la línea queda corta,
  se escribe más texto; no se estira el audio.
- Tolerancias: estirar hasta **1,08×**, comprimir hasta **1,15×** (1,30 duro).
- **A nivel toma el error de estimar por densidad llega al 30 %.** Por eso se
  sintetiza, se **mide**, y se ajusta por regla de tres. En CONTRAMANO hicieron
  falta tres pasadas.
- Antes de diseñar nada de doblaje: **leer el motor de DubAI** en
  `C:\Users\Yamil\Desktop\Foton\dubai_v2`. Sus constantes vienen de fracasos
  medidos en producción. Ya se perdieron iteraciones reinventando peor lo que
  ahí estaba resuelto.

---

## Credenciales y entorno

`.env` en la raíz: `elevenlabs`, `nanobanana`, `openai`, `vasia` (la de Vast).

Para el doblaje de Aladino, **otra cuenta**: `Foton\dubai_v2\.env`. No cambiarla:
las cuatro voces son clones `professional` que existen sólo ahí.

### Trampas de esta máquina

- **Avast rompe SSL en Python.** `SSL_CERT_FILE=certs/ca-bundle-avast.pem` o
  toda descarga falla. Ya lo hace `config.certificados()`.
- **`python` resuelve al venv de DepthFlow, sin numpy.** Usar
  `/c/Python314/python`.
- **Leer ffmpeg por tubería se cuelga en Windows**: decodificar a archivo.
- **`demucs` necesita el rodeo documentado**: `torchcodec` tiene la DLL rota (se
  lee con soundfile) y no existe `demucs.api` (se usa `pretrained` +
  `apply_model`).
- **Los `.sh` con saltos de línea de Windows rompen dentro de la máquina**:
  `sed -i 's/\r$//'` antes de nada.
- **Los heredocs de bash se comen las barras invertidas** si el delimitador no
  va entre comillas: para cualquier cosa con `\`, usar `<<'FIN'` o escribir el
  archivo con una herramienta de edición.
- **ngrok está bloqueado** por el antivirus: ni siquiera se puede leer el
  ejecutable. Para compartir la página hay que buscar otra vía.

---

## Lo que sigue

En orden de lo que más empuja el proyecto:

1. **Estrenar la corrida desatendida en una GPU real.** El 30/8 se escribieron
   `generar`/`seguir`/`bajar` y el reintento automático de cadenas (los
   eslabones van primero en su placa y el runner repasa lo fallado hasta tres
   pasadas). Cierra en código la trampa 11 — la única que costaba plata cada
   vez — pero **nada de eso tocó una instancia real todavía**.
2. **Medir retención de verdad.** Los tramos de `short.json` salen de un short
   que funcionó, no de datos. Hasta que no se publique y se mida, la ley es una
   hipótesis bien fundada.
3. **Un largo completo con el módulo.** Los dos videos hechos son shorts. El
   flujo largo está implementado y **nunca corrió de punta a punta**.
4. **Unificar el motor de doblaje.** Hay dos copias: `h3pipeline/doblaje.py` (la
   general) y `tools/doblaje/` (la corrida de Aladino, que sigue viva). Se
   unifican cuando Aladino cierre.
5. **`l_palacio` y `p_princesa` no son regenerables**: los PNG existen pero no
   están declarados en ningún plan.

El detalle completo, por área y con lo que bloquea a qué, está en
`PENDIENTES.md`.

---

## Mapa de documentos

**Empezar acá.** Después, según a dónde vayas:

| documento | cuándo |
|---|---|
| **La Fábrica** (`python -X utf8 -u -m h3pipeline.app` o doble clic en `h3pipeline/app/arrancar-fabrica.bat`) | **la web que corre el pipeline**: proyectos, dibujos con detector de barras, ofertas de Vast con costo estimado, alquiler con confirmación, taxímetro, QC con tiras, máster. 15/9/2026 |
| `MANUAL-DE-PRODUCCION.md` | **el método entero, por formato** (short, largo, música): flujo en orden, fallas y arreglos, números, contradicciones resueltas. 14/9/2026 |
| `h3pipeline/H3-OFICIAL.md` | **antes de escribir un prompt o usar voces**: el formato oficial de H3, la voz constante con Ref2VA, ComfyUI exacto, imágenes con GPT, replicar un video. Reglas 41-52. 14/9/2026 |
| `mis-videos/replica-danza/NOTAS.md` | la réplica para la competencia (contra Kling): decisiones, costos, estado |
| `h3pipeline/README.md` | cómo se usa el módulo, entradas de cada flujo |
| `ESTRUCTURA-POR-CAPAS.pdf` | **para entender el armado**: las 8 capas de un video, orden y costo por capa |
| `referencias/FORMATOS.md` | **antes de tocar una estructura**. Los ritmos de corte medidos |
| `h3pipeline/REGLAS.md` | **antes de escribir un plano**. Las 39 reglas |
| `h3pipeline/VAST.md` | **antes de alquilar**. Las once trampas |
| `COSTOS-H3.md` | **antes de estimar**. Los números medidos |
| `ISOCRONIA.md` | doblaje y sincronía |
| `VOZ-EMOCION-V3.md` | escribir diálogo para ElevenLabs v3 |
| `PENDIENTES.md` | qué quedó abierto |
| `ESTADO-SHORT.md` · `ESTADO-LARGO.md` · `ESTADO-DOBLAJE.md` | historia de cada línea de trabajo |

**Ojo con el `README.md` de la raíz:** todo lo que sigue al encabezado `ARCHIVO`
describe el pipeline viejo del Mars Climate Orbiter, hecho con Veo. **No es el
método vigente.** Lo mismo con `REGLAS-PLANOS.md` y `REGLAS-ENCADENADO.md` de la
raíz: quedaron como historia, los reemplaza `h3pipeline/REGLAS.md`.
