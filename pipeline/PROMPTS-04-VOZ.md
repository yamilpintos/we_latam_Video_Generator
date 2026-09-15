# PROMPTS 04 — VOZ EN OFF

**Mars Climate Orbiter · 0:00 – 5:00 · PRODUCIDA**

Escuchá primero `output/mars-climate-orbiter/voz/VO_TRACK_FINAL.wav`: son los 5 minutos armados.
Las tomas sueltas duran entre 0,4 y 11 s y por separado no se entienden.

| | |
|---|---|
| Voz | **Sandmor — Latin Spanish Narrator** · `NNyuU2PGU4uwmrHysPYW` |
| Modelo | `eleven_v3` · **una sola generación para los 5 minutos**, cortada por timestamps |
| Tomas | **60** |
| Solapes / desbordes | **0 / 0** |

```bash
python tools/tts_block.py --single   # genera el guion entero de una vez y lo corta
python tools/retime.py --check       # recalcula los IN contra el audio real
python tools/build_vo_track.py       # arma la pista de 5 minutos
```

---

## Por qué una sola generación

Tres intentos, dos fallidos, y los tres dejaron una lección:

**Una llamada por toma.** `eleven_v3` **no acepta** `previous_text` / `next_text` — el API
responde *"not yet supported with the 'eleven_v3' model"*. Sin contexto, cada toma arranca con un
estado prosódico nuevo: empieza con otro tono y se acomoda a mitad de frase. Con 60 tomas eso son
59 reinicios y se oye como cambio de voz en cada corte.

**Cortar por silencios.** Generar el bloque entero y partirlo por «los N−1 silencios más largos»
falla: dentro de una toma con varias oraciones puede haber una pausa más larga que la del borde.
**24 de 60 cortes cayeron mal.**

**Cortar por timestamps.** El endpoint `/with-timestamps` devuelve el tiempo de cada carácter,
incluidos los saltos de línea que separan las tomas. El corte deja de ser una estimación.
El guion son 4.033 caracteres y v3 admite 5.000: entra completo en una llamada.
**Reinicios prosódicos: 0.**

## Sobre las pausas

`eleven_v3` **ignora los `<break time>`** — con 6 s de pausas pedidas dio 28,1 s, menos que los
30,0 s base. Las pausas no van en el texto: son huecos entre tomas que se colocan en el editor.

El reparto de silencios está topeado: pausa normal 1,10 s, pausa dramática 1,60 s, y la cola de
un bloque más la entrada del siguiente comparten un presupuesto de 1,5 s, porque el oyente escucha
la suma. Sin ese tope, cuando la voz sale más corta de lo previsto **todos** los silencios crecen.

---

## Las 60 tomas

Cada archivo se coloca **exactamente en su `IN`**. Los huecos son silencio real.


### S01 · 00:00 – 00:35 · 35 s · Natural

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 00:00,4 | `VO_S01_T1,wav` | 6,7 s | Veintitrés de septiembre de mil novecientos noventa y nueve. Nueve horas, cuatro minutos, cincuenta y dos segundos. |
| T2 | 00:08,8 | `VO_S01_T2,wav` | 3,7 s | En el control de la misión, una señal que llega desde Marte se apaga. |
| T3 | 00:13,3 | `VO_S01_T3,wav` | 4,2 s | No estaba previsto que se apagara todavía. Faltaban cuarenta y nueve segundos. |
| T4 | 00:18,3 | `VO_S01_T4,wav` | 3,0 s | Nadie en esa sala entiende todavía qué acaba de pasar. |
| T5 | 00:22,1 | `VO_S01_T5,wav` | 3,9 s | Veintiún minutos después tenía que reaparecer del otro lado de Marte. |
| T6 | 00:27,1 | `VO_S01_T6,wav` | 0,8 s | [somber] No reapareció. |
| T7 | 00:28,8 | `VO_S01_T7,wav` | 5,2 s | Nadie lo sabe aún, pero esa nave llevaba nueve meses viajando hacia un número equivocado. |

**Voz 27,6 s / 35 s = 79 %**

### S02 · 00:35 – 01:05 · 30 s · **Creative**

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 00:35,3 | `VO_S02_T1,wav` | 1,6 s | Seguro escuchaste la explicación. |
| T2 | 00:37,4 | `VO_S02_T2,wav` | 4,1 s | La NASA perdió una sonda porque unos usaban métrico y otros imperial. |
| T3 | 00:41,9 | `VO_S02_T3,wav` | 4,9 s | Metros contra pies. Un error de colegio, en la mejor agencia espacial del mundo. |
| T4 | 00:47,4 | `VO_S02_T4,wav` | 3,9 s | Es la anécdota perfecta. Se cuenta en cada clase de ingeniería del mundo. |
| T5 | 00:52,3 | `VO_S02_T5,wav` | 1,5 s | Esa versión es cierta. |
| T6 | 00:55,3 | `VO_S02_T6,wav` | 1,7 s | Y es la parte menos interesante. |
| T7 | 00:57,6 | `VO_S02_T7,wav` | 3,2 s | Porque ese error no derribó al Mars Climate Orbiter. |
| T8 | 01:01,2 | `VO_S02_T8,wav` | 3,0 s | [serious] Lo que lo derribó fue todo lo que no lo detuvo. |

**Voz 23,8 s / 30 s = 79 %**

### S03 · 01:05 – 01:35 · 30 s · Natural

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 01:05,5 | `VO_S03_T1,wav` | 4,7 s | La investigación oficial de la NASA no encontró una causa. Encontró nueve. |
| T2 | 01:11,3 | `VO_S03_T2,wav` | 2,8 s | Una causa raíz, y ocho fallos que contribuyeron. |
| T3 | 01:15,2 | `VO_S03_T3,wav` | 5,7 s | Y encontró algo peor: existía una maniobra de emergencia que podía haber salvado la nave. |
| T4 | 01:21,9 | `VO_S03_T4,wav` | 3,8 s | Estaba disponible. Se discutió. No se ejecutó. |
| T5 | 01:26,8 | `VO_S03_T5,wav` | 1,9 s | Nadie entendió del todo que hacía falta. |
| T6 | 01:29,8 | `VO_S03_T6,wav` | 3,6 s | Pero para entender cómo se llega ahí, hay que empezar por el principio. |

**Voz 22,4 s / 30 s = 75 %**

### S04 · 01:35 – 02:10 · 35 s · Natural

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 01:35,5 | `VO_S04_T1,wav` | 4,9 s | El Mars Climate Orbiter era un satélite meteorológico. Pero para otro planeta. |
| T2 | 01:41,5 | `VO_S04_T2,wav` | 5,9 s | [curious] Iba a vigilar el clima de Marte: las tormentas de polvo, el vapor de agua, las estaciones. |
| T3 | 01:48,4 | `VO_S04_T3,wav` | 4,9 s | Y tenía un segundo trabajo: servir de antena repetidora para el Mars Polar Lander. |
| T4 | 01:54,5 | `VO_S04_T4,wav` | 4,8 s | Despegó el once de diciembre de mil novecientos noventa y ocho, desde Cabo Cañaveral. |
| T5 | 02:00,3 | `VO_S04_T5,wav` | 3,8 s | Por delante: seiscientos sesenta y nueve millones de kilómetros. |
| T6 | 02:05,2 | `VO_S04_T6,wav` | 1,6 s | Nueve meses y medio de viaje. |

**Voz 25,9 s / 35 s = 74 %**

### S05 · 02:10 – 02:50 · 40 s · Natural

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 02:10,4 | `VO_S05_T1,wav` | 3,1 s | Una nave en el espacio tiene que controlar hacia dónde apunta. |
| T2 | 02:14,3 | `VO_S05_T2,wav` | 7,4 s | El Mars Climate Orbiter lo hacía con ruedas de reacción: volantes internos que giran y hacen rotar la nave sin gastar combustible. |
| T3 | 02:22,5 | `VO_S05_T3,wav` | 4,8 s | El problema es que esas ruedas se saturan. Se llenan de giro y dejan de servir. |
| T4 | 02:28,0 | `VO_S05_T4,wav` | 1,5 s | Y hay que descargarlas. |
| T5 | 02:30,2 | `VO_S05_T5,wav` | 8,6 s | Para descargarlas, la nave encendía unos propulsores pequeñitos durante un instante. En la NASA lo llamaban desaturación de momento angular. |
| T6 | 02:39,9 | `VO_S05_T6,wav` | 7,1 s | Cada uno de esos disparos empujaba la nave un poquito. Un empujón mínimo, casi ridículo. Milésimas. |
| T7 | 02:48,6 | `VO_S05_T7,wav` | 0,4 s | [serious] Casi. |

**Voz 32,8 s / 40 s = 82 %**

### S06 · 02:50 – 03:30 · 40 s · Natural

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 02:50,5 | `VO_S06_T1,wav` | 2,6 s | Cada vez que pasaba, los datos viajaban a la Tierra. |
| T2 | 02:54,2 | `VO_S06_T2,wav` | 7,0 s | Y en la Tierra, un programa llamado Small Forces calculaba cuánto había empujado ese disparo y lo guardaba en un archivo. |
| T3 | 03:02,3 | `VO_S06_T3,wav` | 1,8 s | Navegación leía ese archivo. |
| T4 | 03:05,3 | `VO_S06_T4,wav` | 3,4 s | El archivo escribía los números en libra-fuerza-segundo. |
| T5 | 03:09,8 | `VO_S06_T5,wav` | 3,1 s | Navegación los leía como newton-segundo. |
| T6 | 03:14,0 | `VO_S06_T6,wav` | 4,9 s | No es lo mismo. Una libra-fuerza son cuatro coma cuarenta y cinco newtons. |
| T7 | 03:20,0 | `VO_S06_T7,wav` | 4,6 s | Donde el archivo decía diez, la realidad decía cuarenta y cuatro con cinco. |
| T8 | 03:25,7 | `VO_S06_T8,wav` | 2,6 s | Cada vez. Durante nueve meses. |

**Voz 30,1 s / 40 s = 75 %**

### S07 · 03:30 – 04:10 · 40 s · Natural

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 03:30,5 | `VO_S07_T1,wav` | 1,7 s | Y acá está la verdadera trampa. |
| T2 | 03:33,3 | `VO_S07_T2,wav` | 3,0 s | Un solo disparo mal calculado no habría movido nada. |
| T3 | 03:37,4 | `VO_S07_T3,wav` | 7,3 s | Pero el Mars Climate Orbiter tenía un panel solar enorme montado de un solo lado, y el Sol empujaba contra él sin parar. |
| T4 | 03:45,8 | `VO_S07_T4,wav` | 7,5 s | Había un plan para compensarlo: girar la nave entera cada día. Lo llamaban modo barbacoa. Se canceló. |
| T5 | 03:54,4 | `VO_S07_T5,wav` | 1,5 s | [serious] Nadie le avisó a navegación. |
| T6 | 03:57,0 | `VO_S07_T6,wav` | 2,6 s | Ni una nota, ni un correo, ni una reunión. |
| T7 | 04:00,7 | `VO_S07_T7,wav` | 6,2 s | Las desaturaciones terminaron ocurriendo entre diez y catorce veces más seguido de lo que navegación esperaba. |

**Voz 29,8 s / 40 s = 75 %**

### S08 · 04:10 – 04:35 · 25 s · **Creative**

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 04:10,5 | `VO_S08_T1,wav` | 6,8 s | Miles de disparos. Miles de errores diminutos. Todos en la misma dirección, todos hacia abajo. |
| T2 | 04:18,3 | `VO_S08_T2,wav` | 2,0 s | Y durante meses, nadie los vio. |
| T3 | 04:21,3 | `VO_S08_T3,wav` | 0,7 s | [whispers] Aunque casi. |
| T4 | 04:22,7 | `VO_S08_T4,wav` | 6,1 s | En abril del noventa y nueve, cinco meses antes del desastre, navegación notó que los datos no cuadraban. |
| T5 | 04:29,9 | `VO_S08_T5,wav` | 4,2 s | Que las perturbaciones eran bastante más grandes de lo que decían los archivos. |

**Voz 19,8 s / 25 s = 79 %**

### S09 · 04:35 – 05:00 · 25 s · Natural

| Toma | IN | Archivo | Dur. | Texto |
|---|---|---|---|---|
| T1 | 04:35,2 | `VO_S09_T1,wav` | 2,6 s | Lo investigaron. No encontraron por qué. |
| T2 | 04:38,4 | `VO_S09_T2,wav` | 2,0 s | Y había un motivo casi cruel para eso. |
| T3 | 04:40,9 | `VO_S09_T3,wav` | 8,5 s | El empujón acumulado apuntaba casi perpendicular a la línea entre la Tierra y la nave. Justo la dirección que el radar Doppler peor mide. |
| T4 | 04:49,9 | `VO_S09_T4,wav` | 3,4 s | Podían ver que algo empujaba. No podían ver cuánto. |
| T5 | 04:53,8 | `VO_S09_T5,wav` | 1,6 s | Y eso los estaba bajando. |
| T6 | 04:56,4 | `VO_S09_T6,wav` | 2,9 s | [somber] El error estaba a la vista. Y era invisible. |

**Voz 21,1 s / 25 s = 85 %**

---

## Verificación

```
tomas       60
duración    300,0 s
voz real    233,3 s = 77.8 %
solapes     0
desbordes   0
```

## Post-proceso

- Normalizar cada toma a −16 LUFS
- High-pass a 80 Hz · de-esser suave
- Recortar el silencio de los bordes a 0,05 s. Con tomas de 1,3 s, medio segundo sobrante ya
  desplaza la sincronía. Si recortás, volvé a correr `retime.py`.
