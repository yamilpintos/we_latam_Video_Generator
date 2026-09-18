# La Fábrica · estado al 18 de septiembre de 2026

Punto de entrada para seguir la **web** en otra sesión. Se lee esto, después
`../../ESTADO-PROYECTO.md` (el mapa general), `../H3-OFICIAL.md` (cómo se le
habla a H3) y `../VAST.md` (las trampas del alquiler). El código de la web es
`h3pipeline/app/`; el pipeline que llama está un nivel arriba.

## Qué es

FastAPI + una sola página (`static/index.html` + `app.js` + `app.css`, router
por hash, portada con fondo 3D). Corre local con `arrancar-fabrica.bat`
(→ http://127.0.0.1:8787) y en **Render** con Docker (`Dockerfile`,
`render.yaml`, disco persistente en `/app/mis-videos`; variables en
`RENDER-VARIABLES.txt`, local y fuera de git). Repos: `origin` =
yamilpintos30-sy/We_latam_Factory (main + rama `hosting-y-musica` del
compañero) y `generator` = yamilpintos/we_latam_Video_Generator (el que
despliega Render). Cada `git push` a los dos.

Entrada: pantalla de login propia (`/login`; usuario `FABRICA_USUARIO`,
default `fabrica`; contraseña `FABRICA_PASSWORD`; cookie 30 días; `Salir`).

## Las puertas de la portada y qué hay detrás

| puerta | flujo | módulos | estado |
|---|---|---|---|
| **Series** (18/9, dentro de cada sección: Short, Largo y Music video tienen su «Nueva serie de…» con el formato fijo; `#/series/nueva/<formato>`, `#/serie/<slug>`) | la capa de producción en masa: ficha (estructura, voz, antología o serial, estilo) → **1** personajes por texto o imagen (GPT los describe; OpenAI dibuja la hoja `m_<id>`; se aprueba) y locaciones → **2** la idea general nombrándolos → personajes por texto o imagen (GPT los describe; OpenAI dibuja la hoja `m_<id>`; se aprueba) y locaciones → **plan** (GPT propone N capítulos; se aprueban/editan/descartan) → **guion** por capítulo (GPT, medido a la voz; se lee y aprueba) → **producir** (traducir con el **reparto fijo**, hojas copiadas, voz, dibujos, ZIP, cola; en music video compone la pista) → la cola genera Modo **narrado** (voz en off fija) o **actuado** (sin narrador: GPT escribe diálogo «NOMBRE: …», una línea ≤ 12 palabras por plano, un solo hablante por plano; el traductor la pone en `dialogo`/`habla`/`voz_desc`; el reescritor la baja a `(S1) … <d>[Spanish] …</d>` con la boca en sincronía; H3 genera la voz; el máster va por `montar`, sin ElevenLabs) | `series.py`, `serie_tarea.py`, `guionista.instruccion(reparto=, actuado=)` | **sin probar con API** (GPT/imágenes): CRUD, endpoints y guardas probados en seco. Vive en `mis-videos/_series/<slug>/` |
| **Short** | guion → `traducir` (GPT gpt-5.1, `guionista.py`) → proyecto → voz (ElevenLabs, densidad medida por voz) → dibujos (OpenAI por defecto; nano banana sin créditos) → máquina → clips → máster | `server.py`, `traducir.py`, `../guionista.py`, `../frames.py` | probado hasta el máster con proyectos anteriores; el corte a 15 s con 3-4 planos está armado |
| **Largo** | igual, estructura `recap`, primero el audio | ídem | implementado, nunca corrió de punta a punta |
| **Music video** | 1 música (biblioteca `mis-videos/_musica`, ElevenLabs Music: género, letra, hasta 30 min en piezas de 5 con fundido a silencio; o subir la propia) → 2 escena (`#/nuevo/loop`: una toma o varias del mismo lugar) → 3 máquina y clips → 4 video final (el loop se repite lo que dure la pista, sin recodificar) | `componer.py`, `musica.py`, `mis-videos/lofi-*/bucle.py` | 3 loops hechos (LLUVIA, KOI, INVERNADERO); piezas largas probadas sólo con tonos |
| **Libre** | imagen (subida entera o generada) → texto en castellano → reescritor → clip 5 a 15 s; barra de progreso, biblioteca, «otra versión» | `libre.py` | **probado con plata el 17/9**: dos clips de 15 s del mono terapeuta, 17,2 min cada uno en 5090 |
| **Editar** | video 2-15 s → «qué cambiar» (+ imagen de referencia, audio original) → reescritor de edición (Ref2VA, `<Video 1>`) → clip | `editar.py`, `../remoto/runner.py` (ref_video) | **sin probar en GPU**; prompt en seco validado. Fuente de prueba lista: turno `E0918085728` (mono, 5,17 s, sin subtítulos) |
| **Remasterizar** (18/9) | origen SD (subido, ruta en el servidor, o **link de Drive** que baja gdown como tarea con reanudación) → sondeo (idet, DAR, bitrate, audio) + hoja + avisos → opciones (rango, recorte VBI, bwdif) → **preparar** (ffmpeg local, gratis) → estimación con las A100 reales → **correr** (alquila 1×A100 80 GB con imagen propia, instala FlashVSR v1.1, infiere por trozos, codifica el 4K en la máquina, baja, destruye, QC) → UHD opcional local | `remaster.py`, `remasterizar.py`, `../remoto/remaster/` (`setup-flashvsr.sh`, `infer_trozos.py`, `post_remoto.sh`) | **el camino con plata no corrió desde la web**; lo local probado (30 s y el máster IMX de 22 GB). El modelo y la receta sí están medidos: `remasterizado/REMASTER-4K-HANDOFF.md` |

Transversales:

- **La máquina** (portada): busca una 4×5090 apta (verificada, fiab ≥ 0,995,
  ≥ 800 Mbps, ≤ $4/h, sin China), alquila, instala H3 (59 GB, barra real por
  `du`), muestra saldo y gasto, apaga. Estado en `mis-videos/_estado/`
  (persistente); si se pierde, `maquina.adoptar()` retoma la instancia viva.
  Antes de alquilar valida la clave SSH del servidor (`/api/maquina/diagnostico`).
- **La máquina del remaster** es OTRA: 1×A100 de 80 GB (con 40 no entra:
  62,5 GB pico), imagen `vastai/base-image:cuda-12.4.1…` vía
  `vast.crear_con_imagen` (replica `onstart: entrypoint.sh` del template),
  etiqueta `fabrica-remaster` (para que `maquina.adoptar()` no la confunda con
  la de H3), estado en `mis-videos/_estado/remaster.json`. Filtros: verificada,
  ≤ $1,30/h, fiab ≥ 0,98, ≥ 500 Mbps, fuera de China; la licencia de H3 no
  aplica (FlashVSR es Apache), así que entran EE.UU. y la UE. Se destruye sola
  al terminar o al fallar; si el 4K quedó hecho y la bajada falló, queda viva en
  estado `sin_bajar` con «bajar de nuevo» y «apagar».
- **La cola** (`cola.py`, `correr_cola.py`): varios proyectos seguidos
  encender → generar → bajar → apagar. **Nunca corrió con plata desde la app.**
- **El reescritor** (`../reescritor.py`): todo prompt de video pasa por GPT con
  la guía oficial de H3 y se valida (un shot, diálogo literal, sin negativos).
  En proyectos queda en `prompt_h3` por plano; `prompt_h3_manual: true` lo protege.
- **Tareas** (`tareas.py`): cada cosa lenta es un subproceso con log en
  `app/logs/`; `/api/tareas/{id}` para seguirlas y matarlas.

## Lo medido que manda

- Clip de 15,08 s en una 5090: **17,2 min**; de 5 s: ~4 min. Encendido a lista:
  11 min a 1,9 Gbps. Máquina: $2,8/h. Detalle en `../../COSTOS-H3.md` §15.
- Un clip > 6 s necesita la VRAM limpia: la app reinicia ComfyUI antes.
- Lo que tapa la boca no habla: el reescritor lo aparta antes de cada línea.
- **Remaster** (A100, FlashVSR Full, tiles grandes): **60 s de GPU por segundo
  de video** (1794 s los 30 s), instalación 770 s, $0,80-1,06/h → ≈ $52 por
  hora de película. El estimador (`remaster.estimar`) usa eso + 13 min fijos +
  1× para la codificación final; tope ×1,5. Bitrate del origen < 5 Mb/s =
  caras lejanas inventadas (302 kb/s vs. máster de 50 Mb/s, 17→18/9). El
  máster IMX 720×608 se recorta `704:576:12:32` (32 líneas de VBI arriba) y
  se desentrelaza con bwdif TFF antes del modelo. El 4K final se codifica EN
  la máquina (x264 crf 15 al tamaño de pantalla, p. ej. 2880×2160 para 4:3)
  porque la cruda ×4 de un capítulo pesa decenas de GB.

## Lo que falta, en orden

1. **Probar Editar en GPU** (clip corto, un cambio, sin subtítulos quemados).
   Puede quedarse sin memoria con video de referencia en 32 GB (#15738).
2. **La cola con plata**, mirándola por el log de la tarea.
3. **Una composición larga real** (10 min = 2 piezas) para oír el fundido.
4. Un short entero desde la web con el reescritor (guion → máster) y medir.
0. **Una serie de punta a punta con API** (~$1-3): crear, 2 personajes con hoja,
   planificar 5, un guion, producir un capítulo hasta la cola; mirar que el
   traductor respete el reparto (mismos ids/hojas, sin madres repetidas) y que
   las caras se sostengan entre capítulos. Después la cola con plata (punto 2).
5. **Remasterizar con plata desde la web**: los 30 s del máster (turno con la
   fuente ya preparada o uno nuevo con rango 0-30) → mirar que el estado, el
   avance (`escritos a/N`), la codificación en la máquina, la bajada y el QC
   funcionen; anotar `costo.real` y `factor_medido`. Estimado ~$0,70.
6. Remaster, después: A/B **Tiny vs Full** sobre los mismos 30 s (~$1; si no
   se nota, el capítulo baja de ~$42 a ~$6), tiles `(96,160)/(80,144)`,
   y trozos en paralelo entre K instancias para un capítulo entero.
7. Segundo tipo de máquina (48 GB: L40S / RTX 6000 Ada) para clips largos con
   referencias; hoy sólo 4×5090.
8. Pulir: nombre de usuario en el login (`FABRICA_USUARIO` en Render), ambient
   bajo la música en largos, audio de H3 a −14 LUFS en Libre/Editar al bajar.

## Arreglos del 18/9

- El estado local decía «lista» con una instancia que Vast ya no tenía (se
  apagó desde Render): `maquina.sincronizar()` y `/api/maquina` lo detectan y
  pasan a apagada sin inventar gasto (`maquina.desaparecida`). Lo mismo para la
  A100 (`remaster.sincronizar_maquina`).
- «Apta» excluía sólo Shanghái y una Zhejiang, CN pasaba: ahora
  `maquina.china_continental()` (todo «…, CN»; Hong Kong sigue) y una sola
  definición de apta para la portada y la tabla de ofertas.

## Trampas de este entorno de desarrollo

- El tool PowerShell falla (exit 9): procesos sueltos con un `.bat` vía
  `cmd.exe //c`. `python` = `C:\Python314\python -X utf8 -u`. ffmpeg en
  `.venv-depthflow/Scripts/ffmpeg.exe`, sin ffprobe (`montaje.duracion`).
- Render redespliega con cada push a `generator`; el estado de la máquina
  sobrevive porque está en el disco persistente, y si no, se readopta.
- En Windows `Path.home()` ignora `HOME`: para probar con un home falso usar
  `USERPROFILE`. `write_text` escribe CRLF: las claves SSH van con `newline="\n"`.
