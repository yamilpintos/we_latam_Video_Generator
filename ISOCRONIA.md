# Isocronía — el método

Cómo hacer que una voz generada calce con una boca que ya está animada. Vale para
cualquier video de **MiniMax H3**, no sólo para el que se usó de prueba. La
implementación está en `tools/doblaje/`; acá está el porqué, que es lo que se reusa.

---

## La idea en una frase

**La ventana la define la boca. El texto se escribe para esa ventana. El audio casi no
se toca.**

Todo lo que sigue son consecuencias de esa frase. El error que costó más iteraciones fue
hacerlo al revés: escribir el texto libre y después deformar el audio para que entrara.

---

## Los seis pasos, en orden

### 1. Separar la voz del ambiente

Sin el stem de voz no se puede medir nada: sobre el audio mezclado de H3 hay ambiente
continuo y ninguna detección por energía lo separa. `demucs` deja `vocals.wav` para medir
y `ambiente.wav` como base de la mezcla, que además conserva pasos, agua y metal — lo
bueno que hace H3.

### 2. Medir la ventana sobre los bloques de habla, no sobre el ASR

El ASR agrupa en frases y **esas frases se comen silencios enteros**. Un caso medido: una
línea que el ASR daba como 8,63 s tenía sólo 5,24 s de habla, con 2,8 s de silencio al
final. El doblaje escrito para 8,63 s seguía sonando casi tres segundos después de que la
boca paraba.

La ventana sale de la energía del stem de voz:

- Huecos **menores a 0,25 s** se fusionan: son pausas entre palabras.
- Huecos **de 0,45 s o más** parten la línea: ahí la boca para de verdad.
- La línea abarca **todos** sus bloques, no el mayor: una frase puede llevar una pausa
  dramática adentro y sigue siendo una frase.

Cada parte del texto se ancla a su bloque. En la implementación se marca con `||`.

### 3. Corregir el desfase entre la boca y el audio del modelo

**H3 no sincroniza su propia boca con su propio audio.** Medido en dos planos: mueve los
labios **0,70 s** y **0,85 s** antes de emitir sonido.

Durante ese hueco **la onda está en cero**. Ninguna medición sobre el audio puede
encontrarlo — es la trampa que más tiempo hace perder, porque el instinto dice que la
respuesta está en la forma de onda.

Se mide por ojo, una vez por plano, con una hoja de contacto a 10 fps sobre la cara:

```bash
# 1) ubicar la cara
ffmpeg -i VIDEO.mp4 -ss <t> -vf "scale=960:-1,drawgrid=w=96:h=54:c=yellow@0.5" -frames:v 1 g.png
# 2) hoja de contacto de la boca
ffmpeg -i VIDEO.mp4 -vf "select='between(t,<ini>,<fin>)',fps=10,\
crop=iw*0.13:ih*0.16:iw*<x>:ih*<y>,scale=280:-1,tile=8x2" -frames:v 1 -vsync 0 boca.png
```

Se busca el primer fotograma con la boca abierta y se resta el arranque del audio. Ese
número va a la tabla de corrimientos por plano.

**No intentes automatizarlo por diferencia entre fotogramas.** Está probado: la región de
mayor cambio resulta ser el humo, el resplandor o la cámara, no la boca. Sobre un plano
con verdad de terreno la señal valía 21,4 justo donde la boca abre, contra 31,5
inmediatamente antes — no hay escalón que detectar.

### 4. Escribir el texto para la ventana

El español hablado corre a **~17 caracteres por segundo**.

| densidad | qué pasa | qué hacer |
|---|---|---|
| < 11 cps | la voz termina y los labios siguen | **alargar** el texto |
| 11 – 22 cps | entra | dejarla |
| > 22 cps | imposible: ninguna compresión lo arregla | **acortar** el texto |

### 5. Escribir varias redacciones y dejar que gane la que mide mejor

La densidad sirve para estimar, pero a nivel toma el error llega al 30 %: la misma
cantidad de caracteres dura distinto según las sílabas, la puntuación y cómo la actúe el
modelo. **Escribir una sola redacción y esperar que entre es apostar.**

Dos o tres redacciones por línea, se sintetizan todas, se mide la duración útil de cada
una contra la ventana y entra la de factor más cercano a 1,00. Cachear por hash del texto
para que cambiar una no vuelva a pagar por las otras.

Es barato —las diecinueve líneas de una película de cinco minutos suman ~500 caracteres,
el 0,1 % de una cuota— y elige mejor que el criterio propio. En la práctica eligió sola
`[yawns]` sobre `[sighs]`, y descartó un suspiro que se comía el bloque entero.

### 6. Tocar el audio lo mínimo

| operación | tope | por qué |
|---|---|---|
| comprimir | **1,15×** suave · 1,30× duro | se tolera bien |
| **ralentizar** | **1,08×** | más allá la voz se empasta |

Ese 1,08 está medido en producción por el motor de DubAI: *"una voz aguda ralentizada más
de 10 % suena masculina/pastosa aunque el pitch no cambie"* — les pasó con tres voces
femeninas distintas en la misma escena.

Además, siempre:

- **Un solo factor por clip.** Nada de deformar tramo por tramo.
- **Recortar el silencio de bordes.** El TTS mete hasta 200 ms al inicio y eso atrasa la
  voz respecto de los labios en todas las líneas. Sólo bordes: las pausas internas
  actuadas no se tocan.
- **Adelantar 0,10 s todas las líneas.** Entre llegar un pelo antes o un pelo tarde,
  antes: tarde se ve como boca moviéndose muda.
- **Estirar en el dominio del tiempo**, nunca remuestreando. Remuestrear cambia el tono
  junto con la velocidad y el personaje suena distinto en cada línea.

---

## Verificar antes de dar nada por bueno

Medir, sobre la mezcla final, **dónde arranca cada línea doblada contra dónde arranca el
habla del original**. Es la única prueba de que la colocación funciona, y separa dos
problemas que suenan igual:

- error dentro de ±0,1 s → la colocación está bien; lo que falta es el paso 3.
- error mayor o disperso → hay un bug en el motor.

En la implementación actual el error mediano es **−0,067 s** sobre 22 piezas, y ese
valor es el adelanto deliberado del paso 6.

---

## Lo que no funciona

**Alinear palabra por palabra.** Fue el primer diseño y suena entrecortado: una frase de
doce palabras termina con doce cambios de escala independientes más silencios
intercalados. No se arregla con parámetros. Un factor por clip.

**Rellenar el hueco estirando.** Si la línea es corta para su ventana, se escribe más
texto. Estirar dos veces es veinte veces la tolerancia medida.

**Un offset global.** El sesgo del ASR contra el ataque acústico real es de **+0,005 s**
sobre 78 palabras: no hay nada que corregir por ahí, y aplicarlo empeora todas las líneas
para arreglar ninguna.

**La diarización para repartir personajes.** El modelo cambia de voz sola, así que el
diarizador agrupa por timbre y mezcla personajes. El reparto se asigna por contenido y
escena, y **se verifica escuchando**.

**El guion original como referencia de tiempos.** Tiene lo que se pretendía decir, no lo
que el modelo dijo. Desfases de hasta 12,7 s medidos.

---

## De dónde salen los números

De `Foton\dubai_v2`, el motor de doblaje: `config/settings.py` (`SYNC_MAX_SLOW`,
`MAX_TIME_STRETCH`, `SYNC_LEAD`, `ISOCHRONY_MAX_CPS`), `src/pipeline/isochrony.py`
(reescritura por densidad) y `src/pipeline/sync.py` (colocación y recorte de bordes).
Sus comentarios traen la fecha y el caso que originó cada límite: eso vale más que la
constante.

Ver también [VOZ-EMOCION-V3.md](VOZ-EMOCION-V3.md) para el paso de emoción, y
[ESTADO-DOBLAJE.md](ESTADO-DOBLAJE.md) para el estado de la implementación.
