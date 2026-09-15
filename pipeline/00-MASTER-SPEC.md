# 00 — MASTER SPEC

El contrato del pipeline. Todas las capas obedecen estas constantes.

---

## 1. Principio rector

> **El audio manda.** El guion se escribe y se cronometra primero. Los planos se cortan
> para que calcen contra la narración, nunca al revés.

Consecuencia práctica: una vez aprobada la Capa 0, **el timeline queda congelado**. Si después
se cambia una frase del guion, hay que recorrer los timecodes de las capas B/C/D/E. Por eso
existe el Gate 1.

---

## 2. Constantes de cronometraje

Narración en español, tono storytelling, ElevenLabs a velocidad 1.0:

| Constante | Valor | Nota |
|---|---|---|
| Velocidad de lectura | **140 palabras/min** = 2.33 pal/s | Storytelling con pausas. Lectura plana sería 160. |
| Densidad de voz | **85 %** del tiempo total | El 15 % restante son respiros y beats de solo imagen+SFX. |
| Palabras por segundo efectivas | **1.98** | 2.33 × 0.85 |

**Fórmula:** `palabras_de_guion = duración_segundos × 1.98`

Calibración obligatoria antes del primer video: generá 100 palabras de prueba en ElevenLabs
con la voz elegida y medí el archivo. Si te da 45 s en lugar de 43 s, ajustá la constante en
este archivo y todo el pipeline se recalibra solo.

---

## 3. La grilla fija 10 / 5

**Todo plano dura exactamente 5 o 10 segundos.**

| Tipo | Duración | Por qué |
|---|---|---|
| **VEO** — clip de Veo 3 | **10,0 s** | Es lo que entrega Veo por generación. Usar menos es tirar créditos. |
| **STILL** — imagen animada | **5,0 s** | Suficiente para que un movimiento se lea, corto para no aburrir. |
| **GFX** — motion graphics | **5,0 s** | Se alinea a la grilla. |

### Consecuencia 1 — toda duración es múltiplo de 5

`10a + 5b = 5(2a + b)`. Cualquier secuencia dura 5, 10, 15, 20, 25… No hay huecos en la escala,
a diferencia de la grilla anterior de 8/5, donde 6, 9, 11, 12, 14, 17, 19, 22 y 27 eran imposibles.

Y para el total: **cualquier número de clips Veo cierra**. Con 300 s, `2a + b = 60`. Antes el
número de clips tenía que ser múltiplo de 5; ahora no hay restricción.

Sigue valiendo el método invertido: se decide cuántos planos tiene la secuencia y de ahí sale su
duración y su presupuesto de palabras. Ver [01-CAPA-0-guion.md](01-CAPA-0-guion.md) §2.

### Consecuencia 2 — los clips de Veo ya no se recortan

Se usan los 10 s completos, así que:

- La acción tiene que **llenar los 10 segundos**, con movimiento ya en curso en el primer
  fotograma y una pose sostenida en el último.
- Un clip con medio segundo malo **no se salva recortando: se regenera**.
- Previsión de reintentos de Veo: **1,3×**.
- **10 segundos es mucho para un solo movimiento.** Un dolly que se agota en 4 s deja 6 s de
  relleno visible. Diseñá la acción con un acento alrededor del segundo 5–6, o partila en dos
  movimientos encadenados que no compitan.

### Consecuencia 3 — el gancho pierde el corte rápido

Con piso de 5 s no hay cortes de 4 s. Se compensa:

- El primer plano es **VEO de 10 s con movimiento interno fuerte**.
- **Nunca dos VEO seguidos al arranque**: 20 s sin corte es demasiado.
- El ritmo lo lleva el diseño sonoro: al menos 4 spot FX en los primeros 20 s.

---

## 4. Presets

### `TEST-5` — prueba de concepto, 5:00 (300 s)

| Parámetro | Valor |
|---|---|
| Palabras de narración | **~590** (±40) |
| Actos | 3 · **Secuencias** 9 |
| **Clips VEO** | **10** × 10 s = **100 s** (33 %) |
| **Planos de 5 s** (STILL + GFX) | **40** = **200 s** |
| Planos totales | **50** |
| Generaciones de Veo 3 | 10 × 1,3 = **~13** |
| Bloques de voz | 9, uno por secuencia |
| Loops de ambiente | 4–7 · Spot SFX 30–45 · Cues de música 4 |

### `FULL-8` — formato final, 8:00 (480 s)

| Parámetro | Valor |
|---|---|
| Palabras de narración | **~950** (±60) |
| Actos | 3 · **Secuencias** 14–15 |
| **Clips VEO** | **15** × 10 s = **150 s** (31 %) |
| **Planos de 5 s** | **66** = **330 s** |
| Planos totales | **81** |
| Generaciones de Veo 3 | 15 × 1,3 = **~20** |

> `TEST-5` es la primera mitad de `FULL-8`. La segunda (180 s) son **5 VEO + 26 planos de 5 s**.

El número de clips Veo es el parámetro de costo y ahora se elige libre. Por debajo del 20 % del
tiempo el video se siente estático; por encima del 40 % el costo se dispara sin que se note tanto.

---

## 5. Sistema de IDs

```
S03-P07
│   └── Plano 07 dentro de la secuencia
└────── Secuencia 03
```

- Las secuencias se numeran corrido a lo largo de todo el video (`S01` … `S09`), no por acto.
- Los planos se numeran desde `P01` dentro de cada secuencia.
- Un ID **nunca se reutiliza ni se renumera**. Si eliminás `S03-P05`, el hueco queda; si insertás
  uno, se llama `S03-P05b`. Renumerar rompe la referencia cruzada entre capas.

**Nombres de archivo** (obligatorio, todas las capas):

```
IMG_S03-P07.png              imagen base
VID_S03-P07.mp4              clip de Veo 3
MOV_S03-P07.mp4              still animado renderizado
VO_S03_0124-0158.wav         bloque de voz (secuencia + rango en segundos)
SFX_S03-P07_pasos.wav        spot effect
AMB_S03_bosque.wav           loop de ambiente
MUS_A2_tension.wav           cue de música por acto
```

---

## 6. Timecodes

- Formato: `MM:SS.d` — décimas de segundo. Ej. `01:24.0`. Con la grilla 10/5 todos los timecodes
  caen en múltiplos de 5 s, así que la décima siempre es `.0`.
- Todo timecode es **absoluto desde el frame 0 del video final**, nunca relativo a la secuencia.
- Todo plano declara `IN`, `OUT` y `DUR`. `OUT` de un plano = `IN` del siguiente. Sin huecos.
- El total de la última `OUT` debe igualar la duración del preset. Es la verificación de cierre.

---

## 7. Formato técnico

| Ítem | Valor |
|---|---|
| Resolución final | 1920 × 1080, 16:9 |
| FPS | 24 (cinematográfico) — Veo 3 entrega 24, no lo cambies |
| Imágenes de ChatGPT | 1536 × 1024 (horizontal), recortar a 16:9 → 1536 × 864, escalar a 1920 × 1080 |
| Planos con paneo lateral | Generar horizontal y usar el ancho completo como recorrido |
| Audio final | −14 LUFS integrado, true peak −1 dBTP (estándar YouTube) |

Nota sobre el recorte: GPT Image entrega 3:2, no 16:9. Componé sabiendo que **se pierde la franja
superior e inferior**. En el prompt pedí siempre "composición centrada, aire arriba y abajo".

---

## 8. Gates

| Gate | Qué se aprueba | Por qué existe |
|---|---|---|
| **1** | Capa 0 — guion cronometrado | Si el guion cambia después, hay que rehacer todos los timecodes. |
| **2** | Capa A — fichas de personaje generadas | Si el personaje no te gusta, se tiran 50 imágenes. Aprobalo con 3. |
| **3** | Capas B/C/D/E completas | Se generan juntas porque comparten el timeline congelado. |

---

## 9. Reglas de retención (YouTube)

Adaptadas a la grilla 10/5 — el corte rápido clásico ya no está disponible.

- **0:00–0:20** — el mejor plano del video va primero, y es un VEO de 10 s con movimiento
  interno fuerte. Después, planos de 5 s. **Nunca dos VEO seguidos al arranque**: 20 s sin corte
  es demasiado.
- **0:20–0:45** — planteo del conflicto, todo en planos de 5 s.
- **Cada ~90 s** — un "reset visual": cambio de locación, de paleta o de escala de plano.
- **Último 10 %** — cierre + gancho al siguiente video.
- **Compensación de ritmo:** como el montaje ya no puede acelerar, el ritmo lo lleva el diseño
  sonoro. En los primeros 20 s tiene que haber al menos 4 spot FX.
