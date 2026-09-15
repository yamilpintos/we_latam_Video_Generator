# MASTER SPEC · Episodio 1 — El pescador y el genio

Reglas de producción del episodio. Lo estético está en
[VISUAL_BIBLE](../../VISUAL_BIBLE.md); lo narrativo, en las fichas de
[story-bible](../../story-bible/). Acá va solo lo que decide **cómo se fabrica**.

> **Cambio del 25 de agosto de 2026 — se sale de Veo, se entra a MiniMax H3.**
> No es un reemplazo pieza por pieza: cambian la duración de los planos, la
> resolución, el modelo de costo y qué se hace con el audio. Este documento ya
> está reescrito sobre H3.

---

## 1. Duración de plano: ya no hay grilla

La grilla 10/5 era una restricción de Veo, que devolvía clips de largo fijo. **H3 no la
tiene.** Acepta `length = 17k + 5` fotogramas a 24 fps y está entrenado entre 124 y 362,
o sea **de 5,2 a 15,1 segundos**, a elección.

Consecuencia: **cada plano dura lo que la escena necesita.** No hay que estirar una idea
para llenar diez segundos ni partirla en dos porque no entra.

Dos límites que sí manda la máquina:

- **Máximo 15 s.** Fuera del rango entrenado el modelo no se rompe, pero se degrada.
- **Los planos de ~10 s rinden más por segundo.** Medido: 0,652 min de GPU por segundo de
  video a 10,1 s, contra 0,784 a 15,1 s. Y hay ~1,2 min de costo fijo por clip, así que los
  muy cortos también se encarecen por segundo. La zona eficiente está entre 8 y 11 s.

`armar_planos.py` redondea sola cualquier duración al valor válido más cercano.

## 2. Formato

| | |
|---|---|
| Resolución de generación | **1344×768** — la nativa de H3, lado corto 768 |
| Resolución de entrega | 1920×1080, escalado local |
| Cuadros por segundo | 24 |
| Duración del episodio | 480 s |
| Planos | los que decida el director; unos 48 a 60 según el promedio |

La relación de 1344×768 es 1,75 y la de 16:9 es 1,778. **No son iguales**: al llevarlo a
1920×1080 hay que recortar unos 24 px de alto o aceptar una deformación del 1,6 %. Se
recorta, y por eso se compone dejando aire arriba y abajo.

## 3. Reparto de planos: lo decide el director

Con Veo el reparto estaba determinado por aritmética: 40 clips de 10 s más 16 de 5 s daban
480 s y no había otro despeje. Con H3 esa cuenta desaparece. **El director elige cuántos
planos y de qué duración**, con una sola restricción: la suma da 480 s y ninguno pasa de 15.

Las nueve secciones siguen siendo el esqueleto y sus duraciones no cambian:

| Sección | Duración | | Sección | Duración |
|---|---|---|---|---|
| S01 El mar | 50 s | | S06 La trampa | 45 s |
| S02 La vasija | 55 s | | S07 El pacto | 60 s |
| S03 El genio | 50 s | | S08 El secreto | 45 s |
| S04 La condena | 65 s | | S09 El final | 50 s |
| S05 La duda | 60 s | | **Total** | **480 s** |

## 4. Audio: quién genera qué

La regla que ordena todo el capítulo de sonido:

> **H3 genera lo que nace y muere dentro del plano.
> ElevenLabs genera todo lo que cruza el corte.**

| Sale de H3, por plano | Sale de ElevenLabs, continuo |
|---|---|
| pasos, agua, burbujas, metal, tela | **voz** de todos los personajes |
| el golpe, el crujido, la respiración | **música**, por cues |
| el sonido puntual de la acción | **ambiente**, una cama por localización |
| | **efectos** que no dependen del plano |

**Por qué la voz no puede salir de H3.** No existe control de identidad de voz: no hay
voice ID ni referencia de audio, así que cada clip inventa una voz distinta. Y es lo peor
que se puede dejar suelto, porque la consistencia visual todavía se pelea con hojas de
modelo y referencias, mientras que la de voz no tiene ninguna palanca — y es la que el
oyente detecta al instante.

**Por qué la música tampoco.** Tiene que cruzar los cortes: es lo que hace que cincuenta
generaciones separadas suenen a una sola pieza. Generada por clip serían cincuenta
fragmentos sin relación, y los cortes sonarían a zapping.

**Y una consecuencia para la mezcla:** como el audio de H3 es por clip, el nivel y el tono
de sala saltan entre plano y plano. La cama de ambiente continua no es decoración, es lo
que tapa esa juntura.

### El bloque de idioma va en TODOS los prompts

Hablen o no. Sin él, H3 mete murmullos, gritos y chusmerío de fondo **en inglés** — ya
arruinó el audio de una versión anterior del proyecto. No se pide silencio, porque alucina
igual: se pide que si alucina, alucine en castellano.

```
SPOKEN LANGUAGE: SPANISH. Every voice, word, murmur, shout or crowd chatter
heard in this shot is in Spanish. NEVER English. If any voice appears at all,
it is Spanish.
```

## 5. Lip sync: decisión pendiente

Lo que **ya está decidido**: toda la voz sale de ElevenLabs. Lo que falta es si las bocas
se mueven en sincronía con ella. Quedan dos caminos vivos:

**A · Sin lip sync.** Shahrazad narra y actúa todos los diálogos, como una cuentacuentos.
Ningún plano lleva etiqueta de habla. Es lo más simple, lo más barato, y es fiel al
original: el cuento existe porque alguien lo está contando.

**B · Post-sincronía en el mismo pod.** H3 genera el plano y después un modelo de sincronía
labial —LatentSync o MuseTalk— mueve la boca contra el audio de ElevenLabs. El cambio a H3
abarató mucho esta opción: la GPU ya está alquilada y corriendo, así que es una etapa más en
la misma máquina, no infraestructura nueva.

**Descartado · el habla nativa de H3**, con la regla de una voz por plano. Sirve para un
personaje que habla en uno o dos planos sueltos. Acá el pescador y el genio discuten durante
seis secuencias: tendrían una voz distinta cada vez.

## 6. Voces

De la librería de ElevenLabs. **Ninguna elegida todavía**, y cada una necesita su tasa de
palabras por segundo medida antes de escribir el guion, porque `timing.py` calcula los
timecodes contra esa cifra.

| Personaje | Registro buscado | Voz | pal/s |
|---|---|---|---|
| Shahrazad | femenina, cuentacuentos, adulta | por elegir | por medir |
| El pescador | masculina, mayor, curtida | por elegir | por medir |
| El genio | masculina, grave, antigua | por elegir | por medir |

Si se toma el camino **A**, las tres las hace la misma actriz: Shahrazad cambiando de voz.
Eso deja una sola tasa que medir en vez de tres.

Cambio pendiente en el código: `RATES` en `tools/timing.py` está indexado por modo de
stability. Pasa a indexarse **por voz**.

## 7. Ajustes de generación

Medidos, no supuestos. Están en [COSTOS-H3.md](../../../COSTOS-H3.md).

| Ajuste | Valor | Por qué |
|---|---|---|
| `ref_image_size` | **`max`** | +8 % de tiempo nada más, y es *la* palanca de fidelidad de identidad entre tomas |
| Pasos | **8 con turbo** para borrador | los pasos son la palanca de costo dominante: 20 cuestan 2,3× lo que 8 |
| Imágenes de referencia | en todos los planos | cuestan +48 % de tiempo, hay que contarlo |
| Encoder | el grande, `int8` de 27 GB | cuesta 2,5 % más de tiempo: calidad casi gratis |
| `SHIFT_AUDIO` | probar en 1.5 | no cuesta nada y es la palanca dedicada al audio, nunca tocada |

Hay una pista sin resolver: los clips de 20 pasos pesan la mitad que los de 8, lo que
sugiere que salen **más suaves**, no más detallados. Es una pista, no una conclusión.
Decide el ojo, antes de pagar 2,3×.

## 8. Costo

48 clips de 10 s, **4 GPUs en paralelo** (probado y funcionando), máquina de $1,909/hr.

| Configuración | Generación | **Usable (×3)** | Reloj |
|---|---|---|---|
| 8 pasos + turbo, refs en `match` | $3,74 | **$11** | ~6 h |
| 20 pasos, fp8 podado | $6,90 | **$21** | ~12 h |
| 20 pasos + refs en `max` | $9,20 | **$28** | ~16 h |

El **×3 no es opcional**: de cada tres o cuatro intentos queda uno. El costo de generación
no es el costo de producción.

Y no se paga por unidad de salida sino por tiempo de máquina, así que **regenerar un plano
que salió mal es gratis**. Esa es la diferencia de fondo con una API.

## 9. Nada se genera antes del bloqueo

```
guion → DIRECTOR crea shot list → AUDITOR narrativo + AUDITOR de cámara
      → DIRECTOR resuelve → locked/SHOT_LIST_LOCKED.md → recién ahí se genera
```

- Los auditores **no escriben** sobre la shot list. Entregan observaciones en `reviews/`.
- El director resuelve. No se decide por mayoría.
- Prioridad ante desacuerdo: guion › biblia visual › continuidad › claridad narrativa ›
  lenguaje cinematográfico › estética › que el plano sea lindo.
- Tope de **dos rondas** por secuencia. Lo que no cierre queda para decisión humana.

Con H3 esta regla afloja un poco, porque regenerar es gratis. Pero no se cae: lo que cuesta
es el tiempo de máquina, y revisar cincuenta planos mal planificados.

## 10. Nombres de archivo

| Qué | Patrón |
|---|---|
| Plano | `S01-P01` … `S09-Pnn` |
| Imagen madre | `assets/madre/MADRE_<nombre>.png` |
| Primer fotograma | `assets/img/IMG_<ID>.png` |
| Clip de H3 | `assets/h3/VID_<ID>.mp4` |
| Toma de voz | `assets/voz/VO_<ID>_T<n>.wav` |

## 11. Estado

- [x] Esqueleto de carpetas
- [x] Biblia visual
- [x] Fichas: Shahrazad, pescador, genio, tres localizaciones, la vasija
- [x] Generador definido: MiniMax H3, duración variable
- [x] Reparto de audio: H3 dentro del plano, ElevenLabs cruzando el corte
- [ ] Decidir lip sync — camino A o B de la sección 5
- [ ] Elegir y medir las voces
- [ ] Guion en Fountain con los tags
- [ ] Los tres agentes de dirección
- [ ] Shot list bloqueada
- [ ] Imágenes madre generadas
