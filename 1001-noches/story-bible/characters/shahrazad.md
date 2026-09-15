---
type: character
title: "Shahrazad"
description: "La narradora de la serie. Cuenta el cuento en cámara y su voz continúa en off sobre la historia."
tags: [cast, narrador, fijo-de-serie]
timestamp: 2026-08-14
status: canon
imagen_madre: "ep01-pescador/assets/madre/MADRE_shahrazad.png"
sources:
  - "ep01-pescador/guion/pescador.fountain"
verified_against: "pendiente-git-init"
---

# Shahrazad

Personaje fijo de la serie: aparece en todos los episodios. No pertenece al cuento del
pescador — pertenece al marco que lo contiene.

## Resumen

Cuenta el cuento. Abre el episodio en cámara y lo cierra en cámara; entre medio su voz
sigue en off sobre la historia. Presencia adulta, digna, magnética. Inteligencia y peligro
al mismo tiempo: cuenta para seguir viva.

## Rasgos invariantes

Se citan **textuales** en todo prompt donde aparezca. No los reescribas por plano.

```
Shahrazad: young adult woman, refined and expressive face, deep dark eyes, olive-toned
skin, delicate but strong features, long dark wavy hair partially covered by a luxurious
veil, subtle gold jewelry. Costume: layered silk robes, embroidered fabrics, fine
ornamental details, deep indigo, burgundy, muted gold and warm ivory accents. Noble and
sophisticated, medieval Persian and Abbasid influence. Adult, dignified, magnetic — never
cartoonish, never childish.
```

## Imagen madre

Prompt de generación: el bloque `STYLE` de [VISUAL_BIBLE](../../VISUAL_BIBLE.md) §2,
seguido de los rasgos invariantes de arriba, seguido de:

```
COMPOSITION: medium full shot, standing near an open archway inside a vast royal chamber at
night, turning slightly toward camera, one hand softly raised as if beginning the first
sentence of a tale. Poised and theatrical posture, but natural. Foreground lamps or hanging
fabric slightly out of focus, Shahrazad clear in the middle ground, carved geometric
ornamentation and a faint moonlit city beyond for depth.
```

Es la **imagen de referencia de toda la serie**: si un plano contradice esta imagen, se
corrige el plano.

## Voz

Femenina, español, registro de cuentacuentos. De la librería de ElevenLabs — sin elegir
todavía. Su tasa de palabras por segundo debe medirse antes de escribir el guion.

Toda su voz sale de ElevenLabs, también en los planos donde se le ven los labios: H3 no
sostiene una voz entre clips. Si esos planos llevan sincronía labial se resuelve por
post-proceso. Ver la sección 5 de
[00-MASTER-SPEC](../../ep01-pescador/pipeline/00-MASTER-SPEC.md).

## Relaciones

- El sultán — le cuenta a él; no aparece en cuadro en este episodio.

## Aparece en

- [Guion del episodio 1](../../ep01-pescador/guion/pescador.fountain) — marco de apertura y
  de cierre.
- [Fuente original](../../ep01-pescador/guion/fuente-original.md) — no figura; es un
  agregado del marco de serie.
