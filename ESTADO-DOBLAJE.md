# Estado · Doblaje de video generado con H3

Actualizado: 28 de agosto de 2026.

Reemplazar las voces que inventa H3 —que cambian en cada clip— por voces fijas de
ElevenLabs, una por personaje, más música por escena. El material de prueba es
**Aladino** (`PELICULA.mp4`, 5:04), pero **el motor es general**: nada de lo que sigue
está atado a esa película salvo la tabla `F` y las dos entradas de `PRE`.

**Estado: usable, con un pendiente identificado y medido.** Video actual:
`Desktop\Aladino doblado\Aladino - doblado v13.mp4`.

---

## 1. Lo que está cerrado

**El tono ya no se mueve.** El alineador deformaba el eje de tiempo con `np.interp`, o
sea varispeed. Reemplazado por estiramiento en el dominio del tiempo. Medido tramo por
tramo, el desvío quedó en 0,0–1,5 %, que es ruido del medidor.

**La colocación es correcta.** Verificación punta a punta sobre las 22 piezas de la
mezcla final, comparando dónde arranca la voz doblada contra dónde arranca el habla de
H3: **error mediano −0,067 s**, veintiuna de veintidós dentro de 0,1 s. Ese −0,067 es el
`LEAD` deliberado. Si algo suena desincronizado, **no es la colocación**.

**Las líneas se parten donde la boca para.** H3 hace pausas largas en medio de una frase
—*"Ten cuidado"* son dos bloques separados por 1,27 s—. El texto se marca con `||` y cada
parte se ancla a su bloque.

**Los sonidos no verbales salen del original.** Risas, gruñidos y expresiones sin palabra
son lo que H3 hace bien: se recuperan enmascarando todo lo que Scribe transcribió. Son 7
tramos, 4,6 s.

---

## 2. El pendiente, y es uno solo

**H3 no sincroniza su propia boca con su propio audio.** Medido en dos planos:

| plano | la boca arranca | la voz de H3 arranca | desfase |
|---|---|---|---|
| genio, *"Mil años durmiendo"* | 176,54 | 177,24 | **0,70 s** |
| vendedor, *"Lámparas nuevas"* | 257,50 | 258,37 | **0,85 s** |

Durante ese hueco la onda **está en cero**: ninguna medición sobre el audio puede
encontrarlo. Se corrige a mano en la tabla `PRE` de `motor.py`, y **sólo esos dos planos
están medidos. Faltan diecisiete.** Ahí está la desincronización que todavía se escucha.

### Cómo se mide un plano (5 minutos cada uno)

```bash
ffmpeg -i PELICULA.mp4 -vf "select='between(t,<ini>,<fin>)',fps=10,\
crop=iw*0.13:ih*0.16:iw*<x>:ih*<y>,scale=280:-1,tile=8x2" -frames:v 1 -vsync 0 boca.png
```

Primero un fotograma completo con `drawgrid=w=96:h=54` para ubicar la cara y sacar `x`/`y`;
después la hoja de contacto a 10 fps. Se busca el primer fotograma con la boca abierta y
se resta el arranque del audio. El resultado va a `PRE`.

**No se puede automatizar con lo que probamos.** `boca.py` intenta detectarlo por la
región de mayor cambio entre fotogramas y falla: esa región resulta ser el humo y el
resplandor, no la boca. En el genio, donde hay verdad de terreno, la señal vale 21,4
contra 31,5 inmediatamente antes — no hay escalón. El archivo queda con el diagnóstico
escrito para que nadie lo reintente igual. Cuatro de sus "detecciones" daban exactamente
−1,33 s, que era el borde de la ventana: falsos positivos.

**La alternativa de fondo** es no perseguir la boca sino corregirla: MuseTalk o LatentSync
re-renderizan los labios para que calcen con la voz de ElevenLabs, corren en la GPU
alquilada y no cobran por unidad. Prueba pendiente sobre un plano.

---

> El método general, sin atarlo a esta película, está en [ISOCRONIA.md](ISOCRONIA.md).
> Lo que sigue es la implementación.

## 3. El motor

| archivo | qué hace |
|---|---|
| `ventana.py` | mide la ventana real sobre el stem de voz, por bloques de habla contigua |
| `seleccion.py` | sintetiza varias redacciones de la misma línea y elige la que mejor entra |
| `alinear.py` | un solo factor de tiempo por clip, recorte de bordes, estiramiento sin tocar el tono |
| `boca.py` | intento fallido de detectar la boca; se conserva por el diagnóstico |
| `motor.py` | tabla de líneas, mezcla y render |
| `separar.py` | demucs con los dos rodeos que hacen falta en esta máquina |

### Las constantes, y de dónde salen

Todas medidas en producción por el motor de doblaje de **DubAI** (`Foton\dubai_v2`),
no elegidas por nosotros:

| constante | valor | por qué |
|---|---|---|
| ralentizar | **1,08×** | *"una voz aguda ralentizada más de 10 % suena masculina/pastosa aunque el pitch no cambie"* — les pasó con tres voces femeninas |
| comprimir | 1,15× suave · 1,30× duro | se tolera mucho mejor que estirar |
| `LEAD` | 0,10 s | entre llegar un pelo antes o tarde, antes: tarde se ve como boca muda |
| `PARTIR` | 0,45 s | hueco interno que separa dos bloques de boca |
| densidad del español | ~17 cps | debajo de 11 los labios siguen sin voz; arriba de 22 no entra |

**El error grande que costó varias iteraciones:** yo estiraba hasta 2,2×, veinte veces la
tolerancia medida. Sonaba entrecortado y no se arreglaba con parámetros. La regla es al
revés de lo intuitivo: **si la línea es corta para su ventana, se escribe más texto, no
se estira el audio.**

### Cómo se escribe una línea

En la tabla `F` de `motor.py`, cada línea lleva **varias redacciones candidatas**. Se
sintetizan todas, se miden y entra la que da el factor más cercano a 1,00. Las variantes
se cachean por hash del texto, así que cambiar una no vuelve a pagar por las demás.

```python
(258.36, 266.99, "mago", ["¡Lámparas nuevas por lámparas viejas! ¡Cambio lo viejo! || No le cuesta nada, señora.",
                          "¡Lámparas nuevas por lámparas viejas, señora! || El cambio no cuesta nada."]),
```

El `||` marca dónde la boca para. Si una línea tiene bloques y el texto no está partido,
el motor **avisa** en vez de colocarlo mal en silencio.

El selector eligió solo, y mejor que yo: `[yawns]` sobre `[sighs]` para el genio (1,36×
contra 1,56×), *"¿Eh?"* sobre *"¿Ah?"*, y *"Mil años…"* sin suspiro cuando el suspiro se
comía el bloque entero.

Ver [VOZ-EMOCION-V3.md](VOZ-EMOCION-V3.md) para el paso de emoción y densidad.

---

## 4. Lo que no hay que reintentar

**El SRT de la película no sirve.** Tiene el guion pretendido, no lo que H3 dijo. Desfases
de hasta 12,7 s.

**La detección por energía no funciona sobre el audio mezclado de H3** — hay ambiente
continuo. Sí funciona sobre `vocals.wav`, el stem de demucs: es lo que usa `ventana.py`.

**La diarización no identifica personajes.** H3 cambia de voz sola, así que el diarizador
agrupa por timbre y mezcla personajes. El reparto se asigna a mano y **se verifica
escuchando**: la primera *"¿Y tú quién eres?"* estaba asignada a la princesa y la dice el
chico — salía con voz de mujer.

**Transcribir sin forzar idioma.** Con `language_code=es` el inglés sale machacado.

**No aplicar un offset global.** Medido: el sesgo de Scribe contra el ataque acústico real
es de **+0,005 s** sobre 78 palabras. No hay nada que corregir por ahí.

**No hay IDs de voz persistentes en H3.** Los `(S1)`/`(S2)` valen dentro de un clip, no
entre clips — ver `REGLAS-PLANOS.md` §8b. Por eso existe todo esto.

---

## 5. Reparto y música

| personaje | voz | id |
|---|---|---|
| mago | Ivan — anciano, sabio | `oqO5cdAzjE5Ik5xWIZRL` |
| aladino | Sebastián — adolescente | `p7cwnUviDFhhX9y8sG2Q` |
| genio | Salvatore — épico, grave | `t3eeeqhBjrUqcrPvDqUn` |
| princesa | Lizy — joven, sobria | `br0MPoLVxuslVxf61qHn` |

Las cuatro son clones `professional` y existen **sólo en la cuenta activa**
(`Foton\dubai_v2\.env`). Cambiar de cuenta rompe el reparto entero: en la otra las cuatro
responden "no disponible".

De 28 frases detectadas, 19 son diálogo. El resto es balbuceo en inglés y queda mudo.

Música: 5 cues por movimiento narrativo, ducking de −8,4 dB. Funciona y no hay que
rehacerlo.

```
M1 bazar   0:00–1:00   ·   M2 cueva  1:00–2:32   ·   M3 genio  2:32–3:32
M4 palacio 3:32–4:03   ·   M5 final  4:03–5:04
```

---

## 6. Costos y trampas

Las 19 líneas suman ~500 caracteres: probar tres variantes de cada una cuesta el **0,1 %**
de la cuota. **Iterar el texto siempre es más barato que deformar el audio.**

- `python` resuelve al venv de DepthFlow sin numpy — usar `/c/Python314/python`.
- Leer ffmpeg por tubería se cuelga en Windows: decodificar a archivo.
- Avast rompe SSL: `SSL_CERT_FILE=certs/ca-bundle-avast.pem` o toda llamada falla.
- ElevenLabs rechaza con 400 un texto que sea **sólo una etiqueta**: `[sighs]` necesita al
  menos una vocalización. El motor ya lo filtra.
- El ducking usaba `np.convolve` con núcleo de 12.000 sobre 14,6 millones de muestras:
  **55 minutos**. `uniform_filter1d` da lo mismo en 0,11 s. Ya corregido.

---

## 7. Dónde está todo

```
tools/doblaje/
├── motor.py, ventana.py, seleccion.py, alinear.py   el motor
├── boca.py                    intento fallido, con el diagnóstico
├── separar.py                 demucs
├── vocals.wav, ambiente.wav   stems (56 MB c/u)
├── scribe_auto.json           transcripción sin forzar idioma
├── voz4/                      tomas cacheadas por hash de texto
└── musica/M1..M5.mp3
```
