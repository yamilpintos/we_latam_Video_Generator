# Paso de emoción — de guion cerrado a texto sintetizable

**Aplica a las tres líneas:** [video largo](ESTADO-LARGO.md), [short](ESTADO-SHORT.md) y
[doblaje](ESTADO-DOBLAJE.md). Todas sintetizan con **`eleven_v3`**.

Entre *guion aprobado* y *generar voz* hay un paso que antes no existía: **repasar el guion
línea por línea y entregar cada diálogo con su parámetro de emoción y su densidad medida
contra la ventana que le toca.** Nada se sintetiza sin pasar por acá.

Son dos cosas distintas y las dos se resuelven en el texto, no en el audio:

1. **Cómo se dice** — el tag de entrega de v3.
2. **Cuánto dura** — los caracteres que entran en la ventana.

---

> El método completo de sincronía está en [ISOCRONIA.md](ISOCRONIA.md). Acá está sólo la
> parte que toca al guion.

## 1. Cuánto dura: la densidad manda

El español hablado corre a **~17 caracteres por segundo**. Ese número no es opinable y es
lo que decide si una línea va a calzar.

| densidad | qué pasa | qué hacer |
|---|---|---|
| **< 11 cps** | la voz termina y los labios siguen moviéndose | **alargar** el texto |
| 11 – 22 cps | entra, con compresión o estirado leves | dejarla |
| **> 22 cps** | físicamente imposible: ninguna compresión lo arregla | **acortar** el texto |

**Los topes de deformación del audio son mucho más chicos de lo que parece:**

| operación | tope | por qué |
|---|---|---|
| comprimir (hablar más rápido) | **1,15×** suave · 1,30× duro | se tolera bien |
| **estirar (hablar más lento)** | **1,08×** | más allá de eso la voz se empasta |

Ese 1,08 está medido en producción por el motor de DubAI: *"una voz aguda ralentizada más
de 10 % suena masculina/pastosa aunque el pitch no cambie"*. Les pasó con tres voces
femeninas distintas en la misma apertura.

**La consecuencia práctica:** si la línea es corta para su ventana, **no se estira el audio
— se escribe más texto.** Y si es larga, no se acelera: se dice lo mismo con menos sílabas,
como en el doblaje clásico.

### Cómo se calcula la ventana

| línea | de dónde sale la ventana |
|---|---|
| **Largo** | el presupuesto de la secuencia en el timeline |
| **Short** | el tramo `usa` del plano donde entra la línea |
| **Doblaje** | el hueco real de H3: desde el ataque de la boca hasta que arranca la frase siguiente |

En el doblaje la ventana **no se negocia** — la fija la boca del personaje. Por eso ahí el
paso de densidad es obligatorio y no cosmético.

---

## 2. Cómo se dice: los tags de v3

`eleven_v3` entiende tags de entrega en corchetes dentro del texto. **No los pronuncia.**

| tag | cuándo |
|---|---|
| `[whispers]` | secreto, confidencia, miedo contenido |
| `[sighs]` | resignación, cansancio, antes de ceder |
| `[nervously]` | mentira, incomodidad, súplica |
| `[curious]` | pregunta genuina, descubrimiento |
| `[excited]` | euforia, hallazgo, urgencia positiva |
| `[surprised]` | sorpresa real, no reacción menor |
| `[angry]` | enojo sostenido |
| `[shouting]` | grito de verdad, con volumen |
| `[sad]` | duelo, pérdida — **sólo en intensidad alta** |

### Las reglas, y por qué

**Neutro por defecto.** La mayoría de las líneas no llevan tag. El tag es la excepción, no
el acompañamiento.

**Un tag por línea como máximo, al principio.** Dos tags en una línea se pelean.

**Intensidad baja o media no lleva tag.** Esta es la que más cuesta respetar y la que más
daño hace. DubAI lo midió: `[sad]` en intensidad media *"corría el timbre lo justo para que
una línea suelta en medio de un monólogo neutral sonara a otra persona"*. El tag no
sobreactúa la línea — **cambia la voz**, y eso rompe lo único que ElevenLabs aporta al
proyecto, que es sostener un personaje entre cortes.

**`[shouting]` sólo si la escena realmente lo pide.** Es el que más mueve el timbre.

**Coherencia por escena.** Dos líneas seguidas del mismo personaje en la misma escena no
deberían saltar de un tag a otro sin que pase algo en la historia.

**La puntuación sigue haciendo la mitad del trabajo.** Coma, punto, `...` y guion largo
dirigen el ritmo sin tocar el timbre. Agotá la puntuación antes de meter un tag.

---

## 3. Qué se entrega

Por cada línea de diálogo, una fila:

| campo | ejemplo |
|---|---|
| ID de plano | `S06-P05` |
| personaje | genio |
| voz (ID de ElevenLabs) | `t3eeeqhBjrUqcrPvDqUn` |
| ventana | 5,41 s |
| texto | `Mil años durmiendo y me despierta un muchacho con una lámpara sucia.` |
| caracteres | 68 |
| **cps** | **12,6** |
| emoción · intensidad | fastidio · 3 |
| **tag** | *(ninguno — intensidad 3)* |

La columna **cps** es la que se revisa antes de gastar un crédito. Si cae fuera de 11–22,
se reescribe la línea, no se ajusta después.

**Texto final que se pega en ElevenLabs** — el tag va pegado adelante:

```
[curious] ¿Y tú quién eres?
```

---

## 4. Después de sintetizar

1. Medir la duración real del archivo.
2. Comparar contra la ventana: el factor tiene que caer entre **0,93× y 1,15×**.
3. Fuera de ese rango, **se corrige el texto y se regenera** — no se fuerza el audio.
4. Recortar el silencio de bordes: v3 mete hasta **200 ms al inicio** de cada clip, y eso
   atrasa la voz respecto de los labios en todas las líneas. Sólo bordes: las pausas
   internas actuadas de v3 no se tocan.

Regenerar sale prácticamente gratis —las 19 líneas del doblaje de Aladino suman 433
caracteres, el 0,04 % de la cuota— así que **iterar el texto siempre es más barato que
deformar el audio.**

---

## De dónde salen estos números

El paso de densidad y los topes de deformación están tomados del motor de doblaje de
**DubAI** (`Foton\dubai_v2`), que los midió en producción sobre cientos de líneas:
`config/settings.py` (`SYNC_MAX_SLOW`, `MAX_TIME_STRETCH`, `ISOCHRONY_MAX_CPS`),
`src/pipeline/isochrony.py` (reescritura por densidad) y `src/pipeline/sync.py`
(colocación y recorte de bordes).

Su `isochrony.py` hace este mismo paso con un LLM y en dos direcciones: acorta las líneas
que no entran y **alarga las que dejan los labios moviéndose sin voz**. Acá el paso lo hace
el modelo al cerrar el guion, que es más barato: se escribe bien la primera vez en lugar de
corregir después.
