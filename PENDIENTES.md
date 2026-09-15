# Pendientes

Actualizado: 30 de agosto de 2026. Todo lo que quedó abierto, por área.
**BLOQUEA** = hasta que no se resuelva, lo que sigue no se puede hacer.

El mapa general del proyecto está en `ESTADO-PROYECTO.md`. Esto es el detalle
fino de lo abierto.

---

## A · Doblaje de Aladino — `ESTADO-DOBLAJE.md`

| # | Qué | Detalle |
|---|---|---|
| A1 | **BLOQUEA · El varispeed** | `tools/doblaje/alinear.py`, líneas 84-91. Remuestrea la onda y cambia el tono: F0 de 102,8 → 120,6 Hz, dispersión ×1,33. Reemplazar por estiramiento con preservación de tono. |
| A2 | Nivel de voz contra ambiente | **Sin verificar.** Puede haber un segundo problema debajo del primero. Sólo se puede juzgar de oído, después de A1. |
| A3 | *"Seguime."* en 0:53 | La escribí yo; el original ahí balbucea. **Sin aprobar.** |
| A4 | Los 10 tramos mudos | El balbuceo no se dobla y la boca se mueve en silencio. Vos marcaste 0:53; falta decidir si los otros nueve se dejan así. |
| A5 | *"Lámparas nuevas…"* queda corta | El original dura 8,63 s y ElevenLabs lo dice en 4,64. Ni con el tope de 1,45× llega: quedan 0,79 s de boca sin voz. Salida clásica: agregarle texto. |
| A6 | Nunca lo escuché | Toda mi verificación es numérica. Los números cierran y el resultado suena mal — eso ya pasó una vez. |
| A7 | No es una herramienta | Son scripts atados a Aladino. Si el flujo sirve, hay que parametrizarlo: vale para cualquier video de H3. |

---

## B · El pescador y el genio — `1001-noches/`

| # | Qué | Detalle |
|---|---|---|
| B1 | **BLOQUEA · Lip sync: camino A o B** | A = Shahrazad narra y actúa todo, sin sincronía labial. B = post-sincronía en el mismo pod. Define cómo se escribe el guion. Sección 5 del master spec. |
| B2 | **BLOQUEA · Elegir y medir las voces** | Ninguna elegida. Cada una necesita su tasa de palabras/segundo medida antes de escribir, porque `timing.py` calcula los timecodes contra esa cifra. Si el camino es A, es **una sola voz**. |
| B3 | `timing.py` indexa mal | `RATES` está indexado por modo de stability. Tiene que pasar a indexarse **por voz**. |
| B4 | El guion en Fountain | Con los tags `(V.O.)` / `(O.S.)`, de donde sale el ruteo. Depende de B1 y B2. |
| B5 | Los tres agentes de dirección | Director + auditor narrativo + auditor de cámara. Reportados y diseñados, **nunca creados**. Y falta tu autorización explícita para que yo lance subagentes. |
| B6 | Shot list bloqueada | Nada se genera antes. Depende de B4 y B5. |
| B7 | Imágenes madre | Personajes y localizaciones. Los prompts están escritos; las imágenes no existen. |
| B8 | El proyecto no es repo de git | El story-bible detecta cuándo una ficha quedó vencida usando SHAs de commit. **Sin `git init` eso no funciona** y es su mejor parte. |
| B9 | Los validadores de bybren | `validate-bible.js` y `check-bible-drift.js` necesitan Node y `npm install`. Sin instalar. |

---

## C · Mars Climate Orbiter — `ESTADO-LARGO.md`

Ese video está terminado. Lo que sigue son defectos conocidos, no bloqueos.

| # | Qué | Detalle |
|---|---|---|
| C1 | Faltan los minutos 5:00–8:00 | Existen sólo como esquema de seis secuencias. Nunca se escribieron. |
| C2 | S04 arrastra 1,2 s | Silencio que no entra en ninguna pausa. Se arregla con unas tres palabras más de texto, no con más pausa. |
| C3 | El audio es mono | Para YouTube conviene estéreo, con ancho en música y ambientes. |
| C4 | Pico real en −0,4 dBFS | Por encima del −1,0 dBTP del máster. Sobreimpulso del AAC; no clipea. |
| C5 | Los clips de Veo se ven blandos | Llegaron a 720p y se escalaron. Sólo se arregla regenerando o con un upscaler. |
| C6 | Timecodes vencidos | `pipeline/PROMPTS-04-VOZ.md` está desfasado por décimas desde la última regeneración de voz. |

---

## D · Short vertical — `ESTADO-SHORT.md`

| # | Qué | Detalle |
|---|---|---|
| ~~D1~~ | ~~Es uno solo~~ | **Resuelto.** `h3pipeline/` es la plantilla; PROFUNDIDAD migrado a `ejemplos/profundidad/proyecto.json`, reproduce el video al décimo. |
| ~~D3~~ | ~~La voz no está cronometrada~~ | **Resuelto el 29/8/2026 en CONTRAMANO.** Cinco líneas medidas contra el audio real, en tres pasadas: separar con demucs, medir la ventana de boca, escribir para esa ventana, sintetizar, **volver a medir** y ajustar por regla de tres. Factores finales 1,04× · 1,30× · 1,10× · 1,12× · 0,93×. |
| ~~D2~~ | ~~Los recortes se ajustan a ojo~~ | **Parcial.** El criterio está escrito en `h3pipeline/estructuras/short.json` (8 tramos con su rango de corte) y el módulo lo valida. Sigue sin haber medición de retención: los tramos salen de un short que funcionó, no de datos. |
| D4 | La ley de retención no está medida | Los tramos de `estructuras/short.json` salen de un short que funcionó, no de datos de retención. Hasta publicar y medir, es una hipótesis bien fundada. |

---

## E0 · El módulo `h3pipeline/`

Los dos flujos empaquetados como módulo importable, con la estructura por tramos
como entrada de dirección. Lo que **no** está verificado todavía:

| # | Qué | Detalle |
|---|---|---|
| ~~E0.1~~ | ~~Nunca corrió contra una GPU real~~ | **Resuelto el 28/8/2026.** Corrida completa de punta a punta: 12 planos generados en 4× RTX 5090, bajados y montados. El video es `mis-videos/78-sur/`. Aparecieron nueve problemas, todos arreglados y documentados en `h3pipeline/VAST.md`. |
| ~~E0.2~~ | ~~El alquiler por API, sin ejecutar~~ | **Resuelto.** `crear()`, `autorizar_clave()`, `esperar_lista()`, `subir()` y `destruir()` corrieron de verdad. Dos hallazgos: hay que alquilar con `template_hash_id` (no `image`+`onstart`) y entrar por **SSH directo**, porque el proxy no funciona con una API key de team. |
| ~~E0.3~~ | ~~La curva de costo extrapola~~ | **Medido.** 12 puntos entre 5,2 y 7,3 s: **0,67 a 0,81 min de GPU por segundo** de video, a 8 pasos con turbo. Es justo el rango que antes se extrapolaba a ciegas. Está en `mis-videos/78-sur/clips/metricas.json`. |
| E0.4 | `l_palacio` no es regenerable | El validador lo detectó: el PNG existe pero no está declarado en ningún plan, así que no hay forma de rehacerlo si cambia el estilo. Lo mismo con `p_princesa`. |
| E0.5 | **Dos copias del motor de doblaje** | `h3pipeline/doblaje.py` es la versión general y `tools/doblaje/` la corrida de Aladino, que sigue viva. Se unifican cuando Aladino esté cerrado. |
| ~~E0.6~~ | ~~La imagen de ComfyUI, corregida sin probar~~ | **Resuelto de otra forma.** No se fija imagen ni tag: se alquila con el template oficial y Vast resuelve el tag. Fijar uno a mano fue exactamente el error. |
| E0.7 | La VRAM queda justa | **Ejercitado el 31/8 en corrida real (41 planos).** El reintento con `/free` rescató S39 y S33; no alcanzó para S30 (6 fallos) ni S17 (3), que salieron a la primera con un ComfyUI recién arrancado en su placa. Por eso existe ahora `remoto/rescate.sh`: `lanzar.sh` lo deja esperando y, cuando los runners terminan, reinicia con VRAM limpia la placa de cada plano caído y lo rehace. Va en el ZIP. **Sin estrenar en modo automático** (hoy se hizo a mano); la próxima corrida lo prueba. |
| ~~E0.8~~ | ~~Una cadena rota deja una placa parada~~ | **Resuelto en código el 30/8/2026, sin verificar en corrida real.** `reparto()` pone los eslabones encadenados primero en su placa (el cabeza falla temprano, con sueltos por hacer de colchón) y el runner repasa lo fallado hasta tres pasadas liberando VRAM entre una y otra. Era la trampa 11 de `VAST.md`. La próxima corrida con cadenas lo estrena. |
| ~~E0.10~~ | ~~La corrida desatendida nunca corrió~~ | **Estrenada el 30/8/2026 con EL DRON DEL VOLCÁN**: `alquilar --si --generar` → `seguir` → `bajar` → `destruir`, de punta a punta sin entrar por SSH, 12/12 planos sin fallos en una 4× A100. Lo único que sigue sin ejercitarse en corrida real es la **repasada de fallados** (no falló nada) y el caso cadena (E0.8): este video era todo planos sueltos. |
| ~~E0.13~~ | ~~EL LOCO DEL CARBÓN — primer recap a lo @jcfdlw~~ | **GENERADO el 31/8/2026** en 4× RTX 5090 (instancia 49390690, Taiwán, $1,88/h): 41/41 clips, 0,77 min GPU/s (curva 5090 confirmada), 4 reintentos, 3 planos acortados por VRAM (S22 y S30 de 7,3 → 6,6 s; S17 de 6,6 → 5,9 s). La corrida destapó las trampas 12 y 13 de VAST.md (imagen vieja sin nodos H3, plantilla ausente) y dejó `rescate.sh`. Costo real de GPU del día: **~$10-11** (instancia 1 ~$3,6 + instancia 2 ~$7 rehaciendo los 11 clips de la placa defectuosa, con un host aún más justo de VRAM: S04 terminó en 5,2 s). Sin tropiezos habría sido ~$2. El rescate automático recuperó 10 de 11 solo; el detector de ruido quedó calibrado (umbral 22 KB). Falta: **escucharlo y verlo** — primer video con caras actuando y voz continua. |
| E0.12 | **EL FARERO listo para generar** | `mis-videos/farero/`: guion primero (regla 40), 12/12 voces en rango, música, 16 dibujos aprobados (7 OpenAI + 5 nano banana, empalman), ZIP empaquetado. Falta sólo: `alquilar --si --generar` cuando haya una 4× RTX 5090 (política: no alquilar otra), `seguir`, `bajar`, `destruir`, mezclar. Y el rumbo estratégico posterior está en `referencias/jcfdlw/ANALISIS.md`: el objetivo es el formato largo tipo recap, no el short. |
| E0.11 | El estimador no distingue familia de GPU ni overhead | Medido el 30/8: la A100 rinde 0,86 min/s contra 0,74 de la 5090 (~15 % menos), y el arranque + montaje + bajada suman ~6-8 min fijos que `costos.estimar()` no cuenta. En un short eso es la mitad del costo real ($2,4 contra $0,94 estimado). Detalle en `COSTOS-H3.md` §13. |
| E0.9 | El flujo LARGO nunca corrió entero | Los dos videos hechos son shorts. `estructuras/largo.json`, `montaje.concatenar()` y el reparto para decenas de planos están implementados y **sin probar de punta a punta**. |

## E · Infraestructura y H3

| # | Qué | Detalle |
|---|---|---|
| ~~E1~~ | ~~El paralelo en 4 GPUs no está en el pipeline~~ | **Resuelto.** `h3pipeline/remoto/lanzar.sh` levanta un ComfyUI por placa y reparte los planos por índice. Sin verificar en una corrida real desde el módulo. |
| E2 | `ref_image_size=max` decidido, sin aplicar | Cuesta +8 % y es *la* palanca de identidad entre tomas. Está en el spec; no se usó todavía. |
| E3 | F_MAXIMO nunca corrió | El GGUF Q6 de 28,2 GB, el más grande que entra en 32 GB. Se llenó el disco. **La próxima instancia hay que pedirla con 250 GB.** |
| E4 | 20 pasos: ¿más suave o más detallado? | Los clips de 20 pasos pesan la mitad que los de 8, lo que sugiere que salen más *suaves*. Es una pista, no una conclusión — decide el ojo, y cuesta 2,3×. |
| E5 | Network Volume vs Vast | RunPod a $7/mes evita rebajar 59 GB en cada arranque. **Sin verificar** si un volumen se monta en cuatro pods a la vez, que es lo que haría falta para el paralelo. |

---

## F · Decisiones que dependen de vos

| # | Qué |
|---|---|
| F1 | Lip sync del Pescador: camino A o B (= B1) |
| F2 | Autorización explícita para que yo lance subagentes |
| F3 | `git init` en el proyecto, para que funcione la detección de deriva |
| F4 | Si *"Seguime."* de 0:53 queda, se cambia o se saca |
| F5 | Qué hacer con la frase del mercader: estirar, agregar texto, o dejar |
| F6 | Si el módulo de dirección visual (ViMax + MovieAgent + Camera Artist) se construye o se archiva |

---

## El orden que yo seguiría

Si lo que empuja es **seguir haciendo videos**:

1. **E0.10 y E0.8** — estrenar la corrida desatendida y el reintento de
   cadenas en una corrida real. El código está; falta que toque una GPU.
2. **E0.9** — un largo entero con el módulo. Es la mitad del producto y nunca
   se probó de punta a punta.
3. **D4** — publicar y medir retención. Sin eso, la ley es una hipótesis.

Si lo que empuja es **cerrar Aladino**:

1. **A1** — es un cambio de una función y desbloquea todo el doblaje. *(Ojo: ya
   está resuelto en `h3pipeline/doblaje.py`, que estira sin tocar el tono —
   verificado con 0,0 % de desvío de F0. Puede ser sólo portarlo.)*
2. **A2 y A6** — escuchar de verdad antes de seguir construyendo encima.
3. **E0.5** — y ahí sí unificar las dos copias del motor.

Y dos que son un comando cada una: **B8** (`git init`, habilita la mitad del
valor del story-bible) y pedir **250 GB** de disco en la próxima instancia
(**E3**).
