# La Fábrica · estado al 17 de septiembre de 2026

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
| **Short** | guion → `traducir` (GPT gpt-5.1, `guionista.py`) → proyecto → voz (ElevenLabs, densidad medida por voz) → dibujos (OpenAI por defecto; nano banana sin créditos) → máquina → clips → máster | `server.py`, `traducir.py`, `../guionista.py`, `../frames.py` | probado hasta el máster con proyectos anteriores; el corte a 15 s con 3-4 planos está armado |
| **Largo** | igual, estructura `recap`, primero el audio | ídem | implementado, nunca corrió de punta a punta |
| **Music video** | 1 música (biblioteca `mis-videos/_musica`, ElevenLabs Music: género, letra, hasta 30 min en piezas de 5 con fundido a silencio; o subir la propia) → 2 escena (`#/nuevo/loop`: una toma o varias del mismo lugar) → 3 máquina y clips → 4 video final (el loop se repite lo que dure la pista, sin recodificar) | `componer.py`, `musica.py`, `mis-videos/lofi-*/bucle.py` | 3 loops hechos (LLUVIA, KOI, INVERNADERO); piezas largas probadas sólo con tonos |
| **Libre** | imagen (subida entera o generada) → texto en castellano → reescritor → clip 5 a 15 s; barra de progreso, biblioteca, «otra versión» | `libre.py` | **probado con plata el 17/9**: dos clips de 15 s del mono terapeuta, 17,2 min cada uno en 5090 |
| **Editar** | video 2-15 s → «qué cambiar» (+ imagen de referencia, audio original) → reescritor de edición (Ref2VA, `<Video 1>`) → clip | `editar.py`, `../remoto/runner.py` (ref_video) | **sin probar en GPU**; prompt en seco validado |

Transversales:

- **La máquina** (portada): busca una 4×5090 apta (verificada, fiab ≥ 0,995,
  ≥ 800 Mbps, ≤ $4/h, sin China), alquila, instala H3 (59 GB, barra real por
  `du`), muestra saldo y gasto, apaga. Estado en `mis-videos/_estado/`
  (persistente); si se pierde, `maquina.adoptar()` retoma la instancia viva.
  Antes de alquilar valida la clave SSH del servidor (`/api/maquina/diagnostico`).
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

## Lo que falta, en orden

1. **Probar Editar en GPU** (clip corto, un cambio, sin subtítulos quemados).
   Puede quedarse sin memoria con video de referencia en 32 GB (#15738).
2. **La cola con plata**, mirándola por el log de la tarea.
3. **Una composición larga real** (10 min = 2 piezas) para oír el fundido.
4. Un short entero desde la web con el reescritor (guion → máster) y medir.
5. Segundo tipo de máquina (48 GB: L40S / RTX 6000 Ada) para clips largos con
   referencias; hoy sólo 4×5090.
6. Pulir: nombre de usuario en el login (`FABRICA_USUARIO` en Render), ambient
   bajo la música en largos, audio de H3 a −14 LUFS en Libre/Editar al bajar.

## Trampas de este entorno de desarrollo

- El tool PowerShell falla (exit 9): procesos sueltos con un `.bat` vía
  `cmd.exe //c`. `python` = `C:\Python314\python -X utf8 -u`. ffmpeg en
  `.venv-depthflow/Scripts/ffmpeg.exe`, sin ffprobe (`montaje.duracion`).
- Render redespliega con cada push a `generator`; el estado de la máquina
  sobrevive porque está en el disco persistente, y si no, se readopta.
- En Windows `Path.home()` ignora `HOME`: para probar con un home falso usar
  `USERPROFILE`. `write_text` escribe CRLF: las claves SSH van con `newline="\n"`.
