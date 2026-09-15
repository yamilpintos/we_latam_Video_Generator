# Capa E — Efectos de sonido y música

Es la capa que más barato sube la calidad percibida y la que más se descuida. Un plano estático
con buen diseño sonoro se siente vivo; un clip de Veo perfecto en silencio se siente muerto.

---

## 1. Arquitectura: cuatro pistas

| Pista | Contenido | Nivel objetivo | Comportamiento |
|---|---|---|---|
| **A1 — Voz** | Narración de la Capa D | −16 LUFS | Manda. Todo lo demás se acomoda. |
| **A2 — Música** | 1 cue por acto | −26 LUFS bajo voz · −18 LUFS sin voz | Ducking automático contra A1 |
| **A3 — Ambiente** | 1 loop continuo por locación | −30 a −26 dB | Nunca se corta en seco; siempre cross-fade |
| **A4 — Spot FX** | Efectos puntuales | −20 a −12 dB | Anclados a un timecode exacto |

**Ducking (obligatorio):** sidechain compressor en A2, disparado por A1.
Ratio 4:1 · Threshold para −6 dB de reducción · Attack 10 ms · **Release 400 ms**.
El release largo es lo que evita el "bombeo" audible.

**Master:** −14 LUFS integrado, true peak −1 dBTP. Limitador al final de la cadena.

---

## 2. La regla del ambiente continuo

> El ambiente **no** se corta en cada plano. Se corta en cada **cambio de locación**.

Si la secuencia S01 entera transcurre en el faro, hay **un** loop de mar y viento que corre los
34 segundos completos, por debajo de todos los planos. Cortar el ambiente en cada corte de imagen
es el error que hace que un video suene a diapositivas.

Transición entre ambientes: cross-fade de **0.8–1.5 s**, superpuesto al corte de imagen.

---

## 3. Spot FX: densidad y anclaje

**Densidad objetivo:** 6–9 spot effects por minuto. Menos se siente vacío; más se siente saturado.

**Anclaje:** cada efecto declara el **timecode exacto de su ataque**, no del plano.
Si la puerta se abre en el segundo 2.3 del plano `S01-P04` (que empieza en 00:12.5), el efecto
va anclado a **00:14.8**, no a 00:12.5.

**Qué sonorizar, en orden de prioridad:**

1. **Todo cambio de estado visible.** Puerta, interruptor, vidrio, motor, cerradura.
2. **Toda locomoción visible.** Pasos con la superficie correcta (madera / grava / metal / agua).
3. **Los movimientos del propio personaje.** Roce de tela, respiración en primeros planos.
4. **Los cortes de alto impacto.** Un whoosh o un impacto sordo en un corte brusco vale más que
   cualquier transición visual.
5. **Refuerzos de la narración.** Si la voz dice "el reloj marcaba las tres", poné el reloj.

**Qué NO sonorizar:** los planos contemplativos donde la voz lleva todo el peso. El silencio
relativo es un recurso; usalo antes del clímax.

---

## 4. Música

Un cue por acto, más un cue de cierre. Para `TEST-5`: **4 cues**.

| Cue | Rango | Función | Descripción a buscar/generar |
|---|---|---|---|
| MUS_A1 | 00:00 – 01:15 | Establecer tono | Drone bajo + un motivo simple. Sin percusión marcada. |
| MUS_A2 | 01:15 – 03:20 | Tensión creciente | Pulso sutil que aparece de a poco, capas que se suman |
| MUS_A3 | 03:20 – 04:30 | Clímax | Toda la instrumentación, resolución armónica |
| MUS_A4 | 04:30 – 05:00 | Cierre | Reduce a un solo instrumento, cola larga |

**Regla de entrada y salida:** cada cue entra con fade de 2–3 s y sale con fade de 3–4 s.
Un cambio de música seco solo se justifica en un corte de impacto.

**Truco de cierre de acto:** cortar la música en seco 0.5 s antes de la frase más importante del
video. El silencio repentino hace que la frase pese el doble.

---

## 5. De dónde salen los sonidos

| Fuente | Para qué | Nota |
|---|---|---|
| **ElevenLabs SFX** (text-to-sound-effects) | Spot FX específicos que no encontrás | Ya lo tenés en la suscripción. Clips cortos, describí el material: "pasos sobre grava mojada, botas pesadas, cinco pasos" |
| **Freesound.org** | Ambientes y efectos comunes | Gratis. Verificá la licencia (CC0 es la segura) |
| **Pixabay Audio** | Música y ambientes | Gratis, sin atribución |
| **Epidemic / Artlist** | Música de calidad | Pago, pero resuelve el problema de monetización |

Para música: **verificá siempre la licencia para monetización en YouTube**. Un Content ID claim
te tumba los ingresos del video entero.

---

## Formato de salida — `07-sfx.md`

````markdown
## AMBIENTES (pista A3)

| ID | IN | OUT | Loop | Nivel | Descripción / prompt |
|---|---|---|---|---|---|
| AMB_01 | 00:00.0 | 01:12.0 | sí | −28 dB | Mar embravecido a media distancia, viento constante de costa, sin gaviotas |
| AMB_02 | 01:11.0 | 02:40.0 | sí | −30 dB | Interior de torre de piedra, room tone hueco con leve eco, viento filtrándose |

Cross-fade AMB_01 → AMB_02 entre 01:11.0 y 01:12.0 (1.0 s)

---

## MÚSICA (pista A2)

| ID | IN | OUT | Fade in | Fade out | Descripción |
|---|---|---|---|---|---|
| MUS_A1 | 00:02.0 | 01:18.0 | 3.0 s | 4.0 s | Drone en La menor, cello grave sostenido, sin percusión, tono de misterio contenido |

---

## SPOT FX (pista A4)

| ID | Ancla | Plano | Dur | Nivel | Descripción / prompt para ElevenLabs SFX |
|---|---|---|---|---|---|
| SFX_001 | 00:03.2 | S01-P01 | 1.8 s | −14 dB | Ola grande rompiendo contra roca, impacto seco y cola de espuma |
| SFX_002 | 00:08.4 | S01-P03 | 4.0 s | −18 dB | Pasos sobre escalón de metal oxidado, botas, seis pasos lentos con eco de torre |
| SFX_003 | 00:14.8 | S01-P04 | 2.2 s | −12 dB | Manija de hierro girando con óxido, seguida de puerta pesada abriéndose y chirrido |
| SFX_004 | 00:16.1 | S01-P04 | 3.0 s | −22 dB | Ráfaga de viento entrando por una abertura, silbido grave |

**Densidad:** 4 efectos en los primeros 20 s ✓ (objetivo 6–9/min)
````
