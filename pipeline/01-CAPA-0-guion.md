# Capa 0 — Guion cronometrado

Es la capa madre. Produce el **timeline maestro** del que cuelgan todas las demás.

---

## Qué recibe

La historia en crudo: puede ser una sinopsis de tres líneas o un texto de dos páginas.

## Qué entrega

Dos artefactos:

1. **`01-guion.md`** — narración completa, dividida en secuencias, con conteo de palabras.
2. **`02-timeline.md`** — tabla maestra de planos con `IN` / `OUT` / `DUR` / tipo.

---

## Procedimiento

### Paso 1 — Estructura en 3 actos

| Acto | % del tiempo | En `TEST-5` (300 s) | Función |
|---|---|---|---|
| I — Planteo | 25 % | 0:00 – 1:15 | Gancho, mundo, personaje, deseo |
| II — Desarrollo | 55 % | 1:15 – 4:00 | Obstáculos escalando, punto de no retorno |
| III — Resolución | 20 % | 4:00 – 5:00 | Clímax, desenlace, cierre + gancho |

### Paso 2 — Secuencias, contadas en planos

Cortar cada acto en secuencias de **25–45 s**. Cada secuencia tiene:
- una locación dominante,
- un objetivo dramático de una frase,
- un cambio de estado entre su inicio y su final.

Si una secuencia no cambia nada, no es una secuencia: es relleno. Fusionala o cortala.

**Con la grilla 10/5, la duración no se elige: se calcula.** Decidís cuántos planos tiene la
secuencia y de qué tipo, y la duración sale sola:

```
duración_secuencia = 10 × (clips VEO) + 5 × (planos STILL y GFX)
```

Ejemplo: una secuencia de 1 VEO + 6 planos de 5 s dura `10 + 30 = 40 s`.

**Verificación global:** con la grilla 10/5 cualquier reparto cierra, porque toda duración es
múltiplo de 5. Solo hay que respetar el presupuesto de clips VEO del preset (10 para `TEST-5`,
15 para `FULL-8`), que es el parámetro de costo.

### Paso 3 — Escribir la narración

Presupuesto de palabras por secuencia = `duración_seg × 1.98`, con la duración ya fijada por el
paso anterior. El guion se escribe **contra la grilla**, no al revés.

Reglas de escritura para voz en off:
- Frases de **12–18 palabras**. Más largas se pierden al escuchar.
- Nada de subordinadas anidadas. Una idea por frase.
- Prohibido narrar lo que la imagen ya muestra. La voz agrega, no describe.
- Marcar las pausas dramáticas con `[…]` — cada una vale ~0.8 s y **cuenta contra el 15 % de respiro**,
  no contra el conteo de palabras.
- Cada 40–60 s, una frase corta de alta carga (≤ 6 palabras). Es lo que corta la monotonía.

### Paso 4 — Asignar tipo a cada plano

Solo hay tres, y el tipo determina la duración:

| Tipo | Duración | Cuándo |
|---|---|---|
| **VEO** | **10 s** | Movimiento real, cambio de estado, interacción, gancho, clímax |
| **STILL** | **5 s** | Todo lo demás que sea imagen |
| **GFX** | **5 s** | Datos, diagramas, comparaciones, cualquier cosa que se explique mejor dibujada |

Las reglas de asignación están en [03-CAPA-B1-veo.md](03-CAPA-B1-veo.md) §1 (cuándo va a Veo),
[04-CAPA-B2-movimiento.md](04-CAPA-B2-movimiento.md) §1 y [05-CAPA-B3-gfx.md](05-CAPA-B3-gfx.md) §1.

`GFX` es opcional según el género: en ficción casi no aparece; en documental técnico puede ser
el 20 % de los planos y es lo que hace que una explicación se entienda a la primera.

### Paso 5 — Verificación de cierre

Tres cuentas, y las tres tienen que dar exacto:

1. `suma(DUR) = duración del preset`
2. `clips VEO = el número del preset` (10 en `TEST-5`, 15 en `FULL-8`)
3. Ninguna duración distinta de 5 o 10

Si no cierra, el ajuste se hace **cambiando un plano de tipo**, no cambiando su duración:
convertir un STILL en VEO suma 5 s; convertir un VEO en STILL resta 5 s.

---

## Formato de salida — `02-timeline.md`

```markdown
## TIMELINE MAESTRO — <título> — TEST-5 — 300 s

| ID | IN | OUT | DUR | Tipo | Locación | Resumen del plano |
|---|---|---|---|---|---|---|
| S01-P01 | 00:00.0 | 00:10.0 | 10 | VEO | Faro, exterior noche | Ola rompe contra la roca, la luz del faro barre el encuadre |
| S01-P02 | 00:10.0 | 00:15.0 | 5 | STILL | Faro, exterior noche | Plano general del faro desde el mar, cielo cargado |
| ... |

**Cierre:** último OUT = 05:00.0 ✓ · Planos 50 ✓ · VEO 10 × 10 s + 40 × 5 s ✓ · sin duraciones fuera de grilla ✓
```

## Formato de salida — `01-guion.md`

```markdown
### S01 · 00:00 – 00:35 · Faro, exterior noche
**Objetivo:** presentar a Mara y el aislamiento del faro.
**Planos:** 1 VEO + 5 STILL = 10 + 25 = **35 s**
**Presupuesto:** 35 s × 1.98 = 69 palabras · **usadas: 68** ✓

> Nadie había encendido esa luz en once años. […]
> Mara subió los ciento cuarenta escalones sin saber que arriba
> la esperaba algo que no era la lámpara.
```
