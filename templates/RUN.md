# RUN — punto de entrada del pipeline

Copiá el bloque de abajo, completá los campos, pegá tu historia y mandámelo.

---

```
Ejecutá el pipeline de /pipeline sobre esta historia.

PRESET:        TEST-5            # TEST-5 (5:00) | FULL-8 (8:00)
IDIOMA:        español neutro    # o rioplatense
GÉNERO:        <terror psicológico / misterio / drama histórico / true crime / fantasía>
TONO:          <sombrío y contenido / épico / íntimo / inquietante>
ESTILO VISUAL: <ilustración cinematográfica / pintura mate / fotorrealista / cómic noir>
PALETA:        <3-4 colores, o "elegila vos">
PERSONAJES:    <cuántos hablan/aparecen, o "sacalos de la historia">
CLIPS VEO:     10                # debe ser múltiplo de 5. 10 = 80 s = 27% del tiempo
USAR GFX:      no                # sí en documental/divulgación, no en ficción
VOZ:           <masculina grave / femenina cálida / narrador neutro>

ENTREGÁ EN ORDEN, PARANDO EN CADA GATE:
  Gate 1 → Capa 0 (guion + timeline). Esperá mi OK.
  Gate 2 → Capa A (biblia de personajes). Esperá mi OK.
  Gate 3 → Capas B, C, D y E juntas.

HISTORIA:
<<<
(pegá acá tu historia — desde tres líneas hasta dos páginas)
>>>
```

---

## Qué recibís en cada gate

**Gate 1** — `output/<slug>/01-guion.md` + `02-timeline.md`
Leelo buscando: ¿el gancho de los primeros 15 s te agarra? ¿sobra alguna secuencia?
Si algo no cierra, es acá donde se arregla — después sale caro.

**Gate 2** — `output/<slug>/03-biblia.md`
Generás las 3–6 imágenes de ficha en ChatGPT. Iterá hasta que te gusten.
Recién cuando el personaje te convence, seguimos.

**Gate 3** — los cuatro documentos de producción (cifras de `TEST-5`):
- `04-imagenes.md` — un prompt por plano de imagen (10 para VEO + los STILL)
- `05-movimiento.md` — 10 prompts de Veo 3 de **8 s** + 44 recetas de plano de **5 s**
- `06-voz.md` — 9 bloques de texto con timecodes e hiperparámetros por bloque
- `07-sfx.md` — ambientes, música y ~40 spot effects anclados

---

## Orden de producción recomendado (Gate 3 en adelante)

Se puede paralelizar, pero si trabajás solo, este orden minimiza el retrabajo:

| # | Tarea | Tiempo estimado (TEST-5) |
|---|---|---|
| 1 | Grabar los 9 bloques de voz en ElevenLabs y medirlos | 45 min |
| 2 | *Si hay desvío > 3 s, avisame y ajusto el timeline antes de seguir* | — |
| 3 | Generar las imágenes en ChatGPT (~44 limpias, ~62 con reintentos) | 3–4 h |
| 4 | Mandar los 10 clips de Veo a generar (contá ~13 con reintentos) | 1 h + espera |
| 5 | Armar los planos de 5 s en CapCut, con presets por técnica | 2–3 h |
| 6 | Reunir ambientes, música y spot FX | 1.5 h |
| 7 | Ensamble y mezcla | 2–3 h |

**Total realista para el primer video de 5 min: 11–15 h.** A partir del tercero, con los presets
de 5 s y los overlays ya armados, baja a 6–8 h.

El paso 1 va primero justamente por el paso 2: si la voz real no coincide con lo presupuestado,
querés enterarte antes de generar 50 imágenes contra un timeline equivocado.
