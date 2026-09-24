# Locución para podcast

Convierte un texto en un episodio narrado y masterizado, con la línea de tiempo
de cada frase (para subtítulos, capítulos o transcripción).

Este módulo es la parte de locución extraída de un pipeline de video que ya
está en producción. **Los valores de configuración no son preferencias: cada
uno se midió corrigiendo algo que sonaba mal.** El porqué de cada uno está
comentado en `locucion/config.py`; abajo está el resumen.

```
texto  →  partir en oraciones  →  una síntesis por oración  →  recortar
       →  pegar con silencios exactos  →  mezclar música  →  máster -14 LUFS
```

---

## Por qué suena a locutor y no a lector

Cuatro decisiones, en orden de impacto. Si tenés que quedarte con una, es la
primera.

### 1. Una síntesis por oración, no una por episodio

Mandando el texto entero, el modelo elige sus propias pausas y va perdiendo el
pulso: arranca bien y a los dos minutos lee de corrido. Oración por oración,
cada una entra con intención y **las pausas las ponemos nosotros, siempre
iguales**.

Ventaja secundaria, nada menor: corregir una frase resintetiza **sólo esa**
(el caché es por hash del texto), en vez de pagar el episodio entero de nuevo.

### 2. Los silencios, puestos a mano

| | segundos | qué hace |
|---|---|---|
| `ARRANQUE` | 0,40 | aire antes de la primera palabra |
| `PAUSA_ORACION` | 0,25 | entre oraciones |
| `PAUSA_PARRAFO` | 0,70 | entre párrafos: es la respiración que marca tema nuevo |

La diferencia entre 0,25 y 0,70 es lo que le da estructura al episodio. Sin
esa distinción, todo suena a un solo bloque.

### 3. El modelo y sus ajustes

```python
MODELO  = "eleven_v3"
AJUSTES = {"stability": 0.5, "similarity_boost": 0.8, "use_speaker_boost": True}
```

- **`eleven_v3`** es el que actúa: respeta las etiquetas de emoción y cambia la
  intención según la puntuación. Los modelos anteriores (`multilingual_v2`,
  `turbo`) leen parejo y suenan a lector.
- **`stability` 0,5** es el punto medido. Arriba de 0,6 se apaga la actuación;
  abajo de 0,4 se vuelve errática entre tomas de la misma voz.
- **`similarity_boost` 0,8** mantiene el timbre reconocible entre episodios.

### 4. El máster a −14 LUFS

`loudnorm=I=-14:TP=-1.0:LRA=11`, el estándar de YouTube y Spotify, aplicado
**una sola vez sobre la mezcla completa**. Masterizar línea por línea deja cada
una con un volumen distinto y el episodio suena a parches.

---

## Etiquetas de emoción

Van dentro del texto:

```
No sé qué decirte. [sighs] Tal vez tengas razón.
```

Las que el modelo interpreta de verdad están en `config.TAGS` y se sirven en
`GET /etiquetas`: `whispers`, `sighs`, `yawns`, `nervously`, `curious`,
`excited`, `surprised`, `angry`, `shouting`, `sad`, `laughs`.

**Trampa:** un texto que sea **sólo** una etiqueta lo rechaza la API con 400.
`[sighs]` necesita al menos una vocalización al lado. El módulo lo valida antes
de llamar.

---

## Voces

`locucion/voces.py` trae dos medidas en producción:

| alias | voz | cps | cómo suena |
|---|---|---|---|
| `pablo` | `JXKQ929SO0LLl7spbEAI` | 10,5 | argentino, grave y pausado |
| `kate` | `EYBbN7OENxAX5QX56IiW` | 16,7 | cercana, rápida |

**`cps` (caracteres por segundo) es lo único que hay que medir por voz**, y es
lo que permite estimar cuánto va a durar un episodio *antes* de gastar un
crédito. No es un detalle: el mismo texto dura **60 % más** con Pablo que con
Kate.

Para una voz nueva: `POST /voces/{id}/medir` (o `voces.medir_cps()`), guardás
el número, y las estimaciones aciertan dentro del 10 %.

---

## Instalación

Requiere **Python 3.10+** y **ffmpeg/ffprobe en el PATH**. El módulo `locucion`
no usa nada fuera de la librería estándar; `requirements.txt` es sólo para la API.

```bash
pip install -r requirements.txt
export ELEVENLABS_API_KEY=...
python test_guion.py          # las pruebas del partidor de oraciones
python ejemplo.py             # un episodio de punta a punta
uvicorn api:app --port 8080   # la API
```

---

## API

Los episodios largos **no se sintetizan dentro del request**: uno de 10 minutos
son ~90 llamadas a ElevenLabs y tarda varios minutos, lo que da timeout en
cualquier proxy. Se encolan y se consultan por id.

### Voces y configuración

| | |
|---|---|
| `GET /voces` | todas las de la cuenta; `cps: null` = sin medir |
| `GET /voces/{id}` | una sola |
| `POST /voces/{id}/medir` | mide el `cps` real (cuesta una síntesis corta) |
| `GET /etiquetas` | las etiquetas de emoción con cuándo usar cada una |

### Producir

| | |
|---|---|
| `POST /estimar` | duración y caracteres **sin sintetizar**; llamalo antes |
| `POST /locutar` | encola el episodio, devuelve un `id` |
| `GET /locutar/{id}` | estado y progreso (`hechas` / `total`) |
| `GET /locutar/{id}/audio` | el MP3 |
| `GET /locutar/{id}/srt` | los subtítulos con los tiempos reales |

`POST /locutar` acepta, además del `texto` y la `voz_id`, todos los parámetros
de arriba (`estabilidad`, `similitud`, `speaker_boost`, `pausa_oracion`,
`pausa_parrafo`, `arranque`, `masterizar`) y una `musica` opcional.

```bash
curl -X POST localhost:8080/locutar -H 'content-type: application/json' -d '{
  "texto": "Primera frase del episodio.\n\nSegundo párrafo.",
  "voz_id": "JXKQ929SO0LLl7spbEAI"
}'
```

Los párrafos se separan con **una línea en blanco**. Es lo único que el texto
de entrada necesita respetar.

---

## Música de fondo

Pasando `musica`, la pista **baja sola cuando entra la voz**
(`sidechaincompress`), no a volumen fijo: un volumen fijo tapa la voz en los
pasajes suaves o deja huecos en los fuertes. Los parámetros
(`threshold=0.02:ratio=16:attack=25:release=500`) están elegidos para que la
voz gane siempre y la música vuelva suave, sin bombear entre frase y frase.

---

## Lo que hay que saber antes de tocarlo

- **El partidor de oraciones es la pieza que más se rompe.** Tiene su propio
  test (`test_guion.py`, 11 casos). Une de más en vez de cortar de más, a
  propósito: una línea larga se sintetiza bien, una línea cortada al medio
  suena rota. Hay una limitación documentada («9 a. m. Se fue»).
- **El caché no tiene límite de tamaño.** En producción con muchos usuarios,
  ponerle una política de borrado.
- **Los trabajos viven en memoria** (`_trabajos` en `api.py`). Para más de un
  worker, hay que moverlos a Redis o a la base.
- **No hay control de cuota.** ElevenLabs cobra por caracteres; conviene contar
  los de `POST /estimar` contra el plan del usuario antes de encolar.
- **`eleven_v3` mete hasta 200 ms de silencio propio** al principio de cada
  clip. Ya se recorta por energía (`UMBRAL_SILENCIO_DB = -45 dBFS`), pero si
  alguna vez las pausas se descontrolan, mirar ahí primero.

---

## Archivos

```
locucion/
  config.py   toda la configuración medida, con el porqué de cada valor
  voces.py    catálogo, cps por voz y cómo medir una voz nueva
  tts.py      síntesis + caché + recorte de silencios de borde
  guion.py    texto → oraciones y párrafos → línea de tiempo
  audio.py    pegado con silencios, ducking de música, máster -14 LUFS
  __init__.py narrar(): el pipeline completo en una función
api.py        la API HTTP
ejemplo.py    un episodio de punta a punta, sin la API
test_guion.py pruebas del partidor de oraciones
```
