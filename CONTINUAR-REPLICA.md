# Prompt para la próxima sesión: réplica exacta de un video de @jcfdlw

Copiá desde acá hasta el final y pegalo como primer mensaje:

---

Estoy haciendo videos generados con IA. El proyecto está en
c:\Users\Yamil\Desktop\youtube proyect

Antes de tocar nada, entrá en contexto en este orden:

1. **ESTADO-PROYECTO.md** — el mapa del proyecto entero.
2. **Tu memoria persistente** — en especial `errores-de-proceso` (mis nueve
   confusiones del 30-31/8 y la regla que evita cada una) y
   `vast-alquiler-trampas`. No repitas ninguna.
3. **referencias/jcfdlw/ANALISIS.md** — el canal al que apuntamos y el índice
   de los 9 videos descargados y transcriptos.
4. **mis-videos/loco-carbon/RECETA.md** — la receta completa del formato recap
   (ya produjo un video de 4 min de punta a punta).
5. **h3pipeline/VAST.md** (las 14 trampas) y **h3pipeline/REGLAS.md** (las 40
   reglas, sobre todo la 38: 5,9 s entra siempre, 6,6 casi siempre, 7,3 es
   apuesta; y la 40: el guion es la columna).

## La tarea: REPLICAR un video del canal, todo igual salvo las imágenes

**Video objetivo: `referencias/jcfdlw/7678030150944001310`** (el más corto de
la muestra; está el `.mp4` limpio 1080p, el `.full.mp4` con audio y el `.txt`
con la transcripción frase por frase con marcas de tiempo).

Es un **benchmark interno de capacidad**: queremos ver si nuestro pipeline
puede producir *lo mismo*. ⚠️ El guion es de ellos: la réplica NO se publica —
sirve para comparar lado a lado. Para publicar escribimos historias propias.

Réplica significa:

- **Mismo texto**: la transcripción del `.txt`, literal, como líneas de voz.
- **Misma voz que usamos nosotros** (Kate, la del recap) — no hace falta
  clonar la de ellos.
- **Mismas tomas con la misma duración**: mapeá los cortes del video original
  y respetá su timing. Único cambio permitido: cuantizar a nuestra grilla
  (clips generados de 5,2 / 5,9 / 6,6 — nunca más de 6,6; una toma de ellos
  más larga se parte en dos planos nuestros con continuidad).
- **Mismas imágenes en contenido** (qué se ve en cada toma: encuadre, quiénes,
  qué pasa) pero **generadas por nosotros** con nuestro estilo fotorrealista
  de drama — ése es el único reemplazo.
- **Subtítulos quemados** frase por frase, como ellos.

## El método (no lo improvises)

1. **Medí, no asumas**: duración real del `.mp4` con ffmpeg (ojo: el limpio y
   el `.full` pueden diferir — verificá cuál corresponde a la transcripción
   comparando la última marca de tiempo del `.txt`).
2. **Mapeá los cortes**: extraé fotogramas a 1 fps del `.mp4` limpio
   (ffmpeg → jpgs), miralos y anotá dónde corta cada toma y qué se ve
   (quiénes, tamaño de plano, acción). Con eso armás la lista de tomas con
   sus duraciones reales.
3. **Armá `mis-videos/replica-jcfdlw/proyecto.json`**: `estructura` puede ser
   `"recap"` reescalada con la duración real (la ley acepta
   `con_duracion`), pero acá manda el timing del original: usá `corta` =
   duración de cada toma de ellos (cuantizada) y las líneas de `voz` con los
   textos del `.txt` en sus tiempos (campo `t` directo o plano+offset).
4. **Validá TODO antes de gastar**: `construir` sin avisos, `voz --generar`
   con las líneas medidas (el texto es fijo: si una línea no entra en su
   ventana, NO la reescribas — dejá que la voz corra y anotá el desvío;
   es parte del benchmark).
5. **Imágenes con nano banana** (`frames --madre --motor nanobanana`):
   hojas de modelo de los personajes que identifiques + locaciones + un
   fotograma por toma copiando el contenido del original. Revisá los PNG
   uno por uno como siempre.
6. **Música**: si el original tiene música de fondo audible, componé un
   equivalente con `musica.componer` (duración exacta); si no, sin música.
7. `empaquetar` y **frená ahí**.

## La confirmación (obligatoria)

Cuando tengas TODO listo — proyecto validado, voces medidas, todos los
dibujos revisados, música si va, y el ZIP empaquetado — **avisame con un
resumen** (cuántas tomas, duración total, desvíos de voz anotados, costo
estimado con el overhead real de COSTOS-H3 §13-14) **y esperá mi confirmación
para mandarlo a Vast**. No alquiles nada sin mi OK explícito. Cuando confirme:
`alquilar --si --generar` (sólo 4×5090; si no hay, se espera), `seguir` con el
taxímetro, `bajar` (con su control de ruido), `destruir` sólo con los clips
verificados, y `mezclar`.
