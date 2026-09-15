# Réplica de «El amor es una danza peligrosa», episodio 1 — registro

Competencia (pedido del 14/9/2026): replicar con MiniMax H3, lo más fiel posible,
un episodio de ReelShort hecho con Kling. El método general que salió de acá
está en `../../h3pipeline/H3-OFICIAL.md`; esto es el registro del proyecto, con
sus números.

## Decisiones del usuario

| fecha | decisión |
|---|---|
| 14/9 | réplica **completa** de 2:07, toma por toma (no una versión de 60 s) |
| 14/9 | **en inglés** (la competencia no exige idioma; el original de Kling se filmó en inglés y está doblado, así que en inglés hay sincronía labial real) |
| 14/9 | **la voz sale de MiniMax y es constante**: casting con H3 + Ref2VA con voz de referencia |
| 14/9 | imágenes con **gpt-image-2.5-sunburst** |
| 14/9 | prompts en el **formato oficial** escritos por nosotros (sin la API de Context-IR) |
| 14/9 | seis planos abiertos: rehacer, y después recortar desde arriba |

## El original, medido (`referencias/danza-peligrosa/MAPA.md`)

126,92 s · 720×1280 · 24 fps · 81 tomas, corte medio **1,57 s** (@jcfdlw corta a
2,36) · música continua · máster −11,9 LUFS, pico +2,08 dBFS · voz en off a
15,7-16,6 cps · héroe 7-12 cps, villanos 13-23 · 4 placas de nombre en serif
itálica · dos cortes que el detector no vio (24,50 s y 90,90 s).

## Cómo quedó armado

- `tomas.py`: 82 tomas (la 14 partida en PM + PP) en **73 encuadres**, y las 26
  líneas con su `t0`, en qué encuadre se ve la boca, el castellano y el inglés.
- `armar.py`: estilo, 7 personajes (Jack con dos vestuarios), 5 locaciones, los
  73 encuadres, `usa` alineado a la voz, placas, estructura de 6 bloques y la
  muestra (`--muestra A|B`).
- `oficial.py`: los prompts en formato oficial (cámara por encuadre, entrega de
  cada línea, casting, voz en off).
- `revisar.py`: hojas original vs nuestro (`revision/`).
- `audio-original/`: `vocals.wav` y `ambiente.wav` de demucs.

Avisos de `validar` que quedan a propósito (10): T02/T03 son dos insertos
seguidos como en el original, y nueve de "boca sin voz", que no aplican porque
H3 anima la boca con la misma línea que dice.

## Imágenes

| tanda | imágenes | costo |
|---|---|---|
| prueba de motores (3 modelos × 4) | 12 | $1,25 |
| biblioteca (7 hojas + 5 locaciones; 2 hojas reusadas de la prueba) | 10 | $0,21 |
| 73 encuadres, tanda 1 (69 OK, 4 bloqueados) | 69 | $3,80 |
| rehechos: 5 sombrero + 5 abiertos + 4 bloqueados | 14 | $1,04 |
| rehechos: 6 abiertos, otra vez (después recortados al 80 % superior) | 6 | $0,46 |
| **total** | **111** | **≈ $6,76** |

Revisión de la tanda 1: **55 de 69 pasaron**. Fallas: continuidad del sombrero
(T23, T24, T25, T27, T28), planos más abiertos que el original (T02, T43, T46,
T70, T74; y T24, T27 después), rechazos del filtro por pose (T41, T77, T78, T81).
Descartes en `_descartados/tanda1`, `tanda2`, `tanda3_sin_recorte`.

## Cuentas

- OpenAI: Tier 1 (5 imágenes/min). Saldo no consultable con la clave.
- ElevenLabs: el proyecto usa desde el 14/9 la clave …c114 (Growing Business,
  ~1,6 M caracteres, reinicia el 10/10); la vieja …e65d quedó comentada en el
  `.env`. Kate y Pablo existen en la cuenta nueva; la voz de 78 SUR no.
- Vast: $31,76 de crédito. El 14/9 a la noche había UNA sola 4×5090 (Shanghái,
  $2,67/h).

## La muestra (sin correr todavía)

- **A** (11 clips, FL2VA): T47 formato viejo / oficial turbo / oficial 20 pasos;
  casting de Jack, Hannah, Luka y Wady con semillas 101 y 202.
- **B** (8 clips, Ref2VA, necesita `assets/voz_<quien>.wav`): Jack en E49 y E55
  (¿misma voz?), E55 a 20 pasos, E49 con ancla del cuadro 0, Hannah, Luka, Wady,
  y la voz en off de Hannah sobre el inserto de las puntas.
- Alquilar con `--ref2va` para que la B corra en la misma instancia.

## Pendiente después de la muestra

- Medir el arranque real de la voz en cada clip que habla → `ONSETS_MEDIDOS`.
- Decidir cómo va la narración en off (clips de inserto con Ref2VA, o clips
  dedicados sólo para audio).
- Mezcla: base del original + audio de H3 (voces) + máster −14 LUFS, subtítulos
  en castellano quemados y placas.
- Comparación lado a lado con el original.
