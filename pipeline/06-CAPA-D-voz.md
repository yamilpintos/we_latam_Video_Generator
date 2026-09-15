# Capa D — Voz en off (ElevenLabs)

Entrega el texto exacto a grabar, partido en bloques, con el timecode donde entra cada uno.

> **Antes de generar nada, pasá por [VOZ-EMOCION-V3.md](../VOZ-EMOCION-V3.md).** Ahí está el
> paso obligatorio de emoción y densidad: cada línea se entrega con su tag de entrega de v3
> y con sus caracteres medidos contra la ventana. Una línea fuera del rango de 11 a 22
> caracteres por segundo no calza, y eso se arregla en el texto, no en el audio.

---

## 1. Por qué en bloques y no todo de una

Un archivo único de 5 minutos parece cómodo hasta que una frase sale mal en el minuto 4 y tenés
que regenerar todo, con un resultado ligeramente distinto que ya no calza.

**Un bloque por secuencia** (25–45 s). Si un bloque sale mal, regenerás 35 segundos.

---

## 2. Configuración

**Modelo:**
- *Eleven v3* — más expresivo, soporta audio tags. Recomendado para storytelling.
- *Multilingual v2* — más estable y predecible en tomas largas. Usalo si v3 te mete artefactos
  o cambia de tono entre bloques.

Elegí uno y **no lo cambies a mitad de video**: el timbre no es idéntico entre modelos.

**Settings de narración:**

| Parámetro | Valor | Nota |
|---|---|---|
| Stability | **45–55** | Más bajo = más emoción y más riesgo. Más alto = plano pero consistente. |
| Similarity | **75** | |
| Style exaggeration | **0–20** | Arriba de 30 empieza a inventar entonaciones. |
| Speaker boost | **On** | |
| Speed | **1.0** | Si cambiás esto, recalibrá la constante del Master Spec. |

**Seed:** si la interfaz te deja fijar seed, fijalo y anotalo. Da consistencia entre bloques.

---

## 3. Preparación del texto

**Puntuación = dirección de actuación.** ElevenLabs lee los signos, no las intenciones.

| Quiero | Escribo |
|---|---|
| Pausa corta | coma |
| Pausa media | punto |
| Pausa larga y dramática | punto y aparte, o `...` en línea propia |
| Énfasis | reescribir la frase para que la palabra clave quede al final |
| Duda | `—` guion largo |

**Números y siglas:** escribilos como se pronuncian. `1987` → "mil novecientos ochenta y siete".
`3 km` → "tres kilómetros". `FBI` → "efe be i".

**Nombres propios raros:** escribilos fonéticamente en el texto de ElevenLabs (el guion en pantalla
mantiene la grafía correcta).

**Audio tags (solo v3):** van en inglés, entre corchetes, antes de la frase que afectan.
Útiles: `[whispers]`, `[sighs]`, `[nervously]`, `[excited]`, `[curious]`.
Máximo uno cada 2–3 frases: sobreusados vuelven la narración caricaturesca.

---

## 4. Después de generar: la verificación

Para cada bloque:

1. Medí la duración real del archivo.
2. Comparala con el presupuesto del timeline.
3. Desvío tolerado: **± 1.5 s**.
4. Si se pasa:
   - **+1.5 a +4 s** → sacá palabras del texto y regenerá. Es lo primero que hay que intentar.
   - **> +4 s** → el guion está mal calibrado; avisá y se ajusta el timeline de esa secuencia.
   - **Nunca uses speed 1.05** para "hacerlo entrar". Se nota y se acumula.
5. Anotá la duración real en el documento. Al terminar todos los bloques, la suma real vs.
   presupuestada te dice si hay que correr el timeline.

**Anclaje de sincronía:** cada bloque arranca en un `IN` de plano, nunca en el medio de un plano.
Así, si un bloque queda 1 s corto, el silencio cae en un corte y no se nota.

---

## 5. Limpieza mínima

- Normalizar cada bloque a **−16 LUFS**.
- High-pass a 80 Hz (saca el retumbe).
- De-esser suave si la voz sisea.
- Recortar el silencio inicial y final a exactamente 0.15 s.

---

## Formato de salida — `06-voz.md`

````markdown
## BLOQUE S01 · IN 00:00 → OUT 00:36 · presupuesto 36 s · 71 palabras

**Composición de la secuencia:** 2 VEO + 4 planos de 5 s = `16 + 20 = 36 s`
**Cubre los planos:** S01-P01 … S01-P06
**Archivo:** `VO_S01_0000-0036.wav`
**Duración real medida:** _____ s · **Desvío:** _____

**Texto para pegar en ElevenLabs:**
```
Nadie había encendido esa luz en once años.

[curious] Mara subió los ciento cuarenta escalones sin saber que arriba la esperaba algo
que no era la lámpara.

...

La puerta estaba abierta.
```

**Reparto contra la imagen** (para verificar sincronía al montar):

| Plano | IN | Frase que debe estar sonando |
|---|---|---|
| S01-P01 | 00:00 | "Nadie había encendido esa luz…" |
| S01-P03 | 00:13 | "Mara subió los ciento cuarenta escalones…" |
| S01-P05 | 00:26 | *(silencio — beat de respiro)* |
| S01-P06 | 00:31 | "La puerta estaba abierta." |
````

El **reparto contra la imagen** es lo que hace que la capa de audio y la de video encajen sin que
las dos personas se hablen. Es la columna más importante del documento.
