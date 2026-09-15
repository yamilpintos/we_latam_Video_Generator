# h3pipeline

> El estado general del proyecto y el mapa de documentos están en
> [`../ESTADO-PROYECTO.md`](../ESTADO-PROYECTO.md). Acá está **cómo se usa** el
> módulo.

De una idea a un video generado con **MiniMax H3**, en GPU alquilada por hora.

Es un **módulo**, no un programa. La app llama a estas funciones; el
`python -m h3pipeline` es una conveniencia para trabajar a mano.

Los dos flujos son el mismo pipeline con distinta **estructura** y **formato**:

| | short | largo |
|---|---|---|
| Formato | 9:16 · 768×1344 | 16:9 · 1344×768 |
| Duración | 23, 60 o 90 s | 5 a 8 min |
| Voz | ninguna de H3; en off, de ElevenLabs | diálogo dentro del plano + narración |
| Cortes | de 1,5 a 7 s, con `usa` | de 5 a 15 s, el plano entero |
| Estructura | `short-23` · `short` · `short-90` | `estructuras/largo.json` |
| Ejemplo | [`ejemplos/profundidad/`](../ejemplos/profundidad/) | [`ejemplos/aladino/`](../ejemplos/aladino/) |

Las estructuras son **la ley**, y salen de
[`Estructuras_Contenido_Alta_Retencion_2026.docx`](../Estructuras_Contenido_Alta_Retencion_2026.docx)
— ver [«La ley de retención»](#la-ley-de-retención-2026) más abajo.

---

## La Mesa de Armado

```bash
python -m h3pipeline.web     # escribe h3pipeline/web/mesa.html
```

Una página para el paso 1: elegís formato y estructura, cargás la idea, el
estilo y cómo se cuenta el audio, y sale **la instrucción que se le pasa al
modelo** para que escriba los planos — con la ley de retención entera, el
esqueleto de huecos y el `proyecto.json` a completar.

Se genera **desde el módulo**: los tramos, los rangos de corte, los umbrales de
retención y el reparto de planos salen de `estructuras/*.json` al generar. Si
cambiás un tramo en el JSON, cambia en la página. Una copia escrita a mano se
desincroniza en una semana.

---

## El flujo, y por qué está en este orden

```
1. estructura   qué tiene que pasar en cada segundo, ANTES de escribir un plano
        │       (short: los primeros 3 s son un evento llamativo; de 3 a 5,5 la
        │        promesa; … · largo: apertura fría, planteo, detonante, …)
        ▼  brief()
2. proyecto.json   estilo, reparto, locaciones y la lista de planos
        │
        ▼  construir()
3. storyboard.json ──► frames  ── nano banana, EN TU MÁQUINA, GPU apagada
        │              se revisa entero acá: un encuadre malo se ve en un PNG
        │              de 22 segundos, no tras 7 min de generación cobrando
        ▼
4. planos.json ──► empaquetar ──► ZIP ──► Vast ──► setup.sh · lanzar.sh
        │                                          runner.py, una placa cada N planos
        ▼
5. montaje  ──►  MP4 + SRT
        │
        ▼  en paralelo, desde el paso 2: la capa de voz
   voz.py   densidad y emoción de cada línea, contra su ventana
   tts.py   eleven_v3, varias redacciones, gana la que mejor entra
   doblaje  si hay que reemplazar las voces que H3 inventó
```

El paso 3 antes del 4 es la mitad del ahorro. El paso 1 antes del 2 es lo que
evita escribir doce planos que no cuentan nada.

---

## Uso desde la app

```python
from h3pipeline import Proyecto, empaquetar, frames, montaje, vast, costos

p = Proyecto.cargar("mis-videos/profundidad/proyecto.json")

print(p.brief())              # la estructura escrita, para redactar los planos
p.escribir()                  # storyboard.json + planos.json + brief.md + voz
for a in p.validar(): print(a)  # avisos: tramos sin cubrir, cortes largos, saltos de eje

sb, doc = p.construir()
frames.generar_storyboard(sb, p.raiz / "assets", p.raiz)   # los fotogramas

print(costos.estimar(doc["planos"]))                       # qué va a salir
ofertas = vast.buscar(planos=doc["planos"])                # dónde correrlo
print(vast.tabla(ofertas, doc["planos"]))

empaquetar.empaquetar(p)      # el ZIP para subir
# … generás en la máquina alquilada, bajás los clips …
montaje.recortar_y_concatenar(doc["planos"], "clips/", "final.mp4")
montaje.srt(doc["planos"], "final.srt")
```

Nada de esto escribe fuera de la carpeta del proyecto, ni alquila nada solo:
`vast.crear()` y `vast.destruir()` piden `confirmar=True` explícito.

### Por línea de comandos

```bash
python -m h3pipeline estructuras                    # qué estructuras hay
python -m h3pipeline brief   <proyecto.json>        # el documento de dirección
python -m h3pipeline construir <proyecto.json>      # storyboard.json + planos.json
python -m h3pipeline frames  <proyecto.json>        # los primeros fotogramas
python -m h3pipeline costo   <proyecto.json>        # qué va a salir
python -m h3pipeline gpu     <proyecto.json>        # dónde correrlo, por costo total
python -m h3pipeline empaquetar <proyecto.json>     # el ZIP para subir
python -m h3pipeline voz     <proyecto.json>        # densidad y emoción de cada línea
python -m h3pipeline montar  <proyecto.json> clips/ # el MP4 final, acá
python -m h3pipeline alquilar <proyecto.json> <id>  # ALQUILA y sube el ZIP · cobra
python -m h3pipeline instancias                     # qué tenés prendido (¡y cobrando!)
python -m h3pipeline destruir <id> --si             # borra y deja de cobrar
```

### Alquilar, de punta a punta

```bash
python -m h3pipeline empaquetar mi-video/proyecto.json   # el ZIP
python -m h3pipeline gpu        mi-video/proyecto.json   # elegís un id de la tabla
python -m h3pipeline alquilar   mi-video/proyecto.json 43166506 --si
```

`alquilar` crea la instancia, espera a que pase de *loading* a *running*, sube el
ZIP por scp y te imprime los comandos que faltan. **Sin `--si` no hace nada**:
muestra el costo estimado y sale.

Requisitos, y son los que hoy no están puestos:

1. **`VAST_API_KEY` en el `.env`.** Buscar ofertas es público; alquilar no.
   Se saca en cloud.vast.ai/account/ → API Keys.
2. **Tu clave pública SSH cargada en Vast** (misma página → SSH Keys). Sin eso
   el `scp` falla y hay que subir el ZIP por Jupyter a mano.

Después, dentro de la máquina:

```bash
cd /workspace/refs && unzip -o mi-video-para-vast.zip
sed -i 's/
$//' /workspace/refs/*.sh /workspace/refs/*.py
bash /workspace/refs/setup.sh          # ~59 GB, 5-30 min según el enlace
PASOS=8 bash /workspace/refs/lanzar.sh
python /root/runner.py --montar
```

Y cuando bajaste todo:

```bash
python -m h3pipeline destruir <id> --si
```

> **Todo esto corrió de verdad** el 28 de agosto de 2026, de punta a punta: 12
> planos generados en 4× RTX 5090, bajados y montados. En el camino aparecieron
> nueve problemas que nadie tenía documentados —desde una imagen que arranca sin
> servicios hasta un workflow que se arma con los valores corridos—. Todos están
> arreglados en el módulo y explicados con su síntoma en **[VAST.md](VAST.md)**,
> y resumidos en la pestaña «Trampas de Vast» de la Mesa de Armado.

---

## La estructura: la entrada de dirección

Un tramo dice qué tiene que pasar en un rango de segundos. No es documentación:
**entra en el prompt del fotograma**. El `prompt_frame` de cada tramo se inyecta
como `NARRATIVE INTENT OF THIS FRAME`, así que "los primeros 3 segundos necesitan
un evento llamativo" llega hasta el dibujo en vez de quedarse en un documento.

```json
{
  "id": "HOOK", "nombre": "Gancho", "desde": 0, "hasta": 3,
  "objetivo": "Un evento llamativo YA en el primer fotograma…",
  "exige": ["El primer fotograma funciona como miniatura…", "…"],
  "corte_min": 1.5, "corte_max": 3.0,
  "tamanos": ["PP", "PD"],
  "prompt_frame": "This is the very first frame of a vertical short-form video…",
  "planos_min": 1
}
```

`desde`/`hasta` en segundos, o `desde_pct`/`hasta_pct` como fracción de la
duración objetivo — así la misma estructura sirve para 5 y para 8 minutos
(`Estructura.con_duracion(480)`).

Después de escribir los planos, `validar()` chequea contra el mismo JSON:
tramos sin planos, cortes fuera de rango, tamaños que no corresponden, duración
total, saltos de eje, y diálogos con más de un personaje. Son **avisos**: la
estructura es una guía y el director decide, pero lo que se aparta queda escrito.

Los límites de `short.json` no son teoría: son los cortes de PROFUNDIDAD, el
short de 60 s que está terminado y funciona.

Para una estructura propia: copiá un JSON a `estructuras/`, o pasá el dict
directo en `"estructura"` del proyecto.

---

## La ley de retención 2026

Las cuatro estructuras implementan
[`Estructuras_Contenido_Alta_Retencion_2026.docx`](../Estructuras_Contenido_Alta_Retencion_2026.docx).
Lo que manda la distribución en 2026 es **el porcentaje del video que se
completa**, no los likes ni los seguidores: un clip corto con alta finalización
supera sistemáticamente a uno largo con baja retención.

### Elegir la duración

No hay una sola. La duración es una decisión de objetivo, y el módulo trae una
estructura por cada una:

| estructura | dura | retención objetivo | para qué | plataformas |
|---|---|---|---|---|
| `short-23` | 23 s | **65 %** | alcance puro, descubrimiento entre no seguidores | Reels, TikTok, Shorts |
| `short` | 60 s | **50 %** | el compromiso multiplataforma — **el default** | las tres |
| `short-90` | 90 s | **45 %** | guardados, comunidad, explicar algo | TikTok, Reels |
| `largo` | 5-8 min | **50 %** | YouTube | YouTube |

El umbral **sube cuanto más corto es el video**: a menos compromiso de tiempo,
más finalización se exige para empujarlo. Y hay una tensión real entre
plataformas que 60 s resuelve: YouTube Shorts corta en 60, TikTok premia 60-90
por tiempo de visualización, Reels necesita menos de 90 para Explorar.

`short-23` implementa la **regla 3/8/12**: tres segundos de gancho, ocho de
desarrollo, doce de cierre.

### Lo que la ley exige en todos

- **Ventana crítica de 1 a 3 s.** No cambia con la duración: si el espectador no
  percibe el valor de inmediato, desliza.
- **Triple refuerzo del gancho:** lo visual, lo auditivo y el **texto en
  pantalla** dicen lo mismo en esos 3 s.
- **Anteponer el resultado concreto**, no la promesa genérica: «esta landing
  convierte al 14 %», no «hoy te enseño cómo».
- **Interrupción de patrón** cada 8-12 s en shorts, cada 75 s en el largo. Un
  corte **no** cuenta —en un short todo son cortes— sino un cambio de régimen:
  luz nueva, sonido que entra o desaparece, ritmo que cambia.
- **Loop de cierre:** el final conecta con el principio. El replay es de las
  señales más fuertes que hay, y una pregunta contestable en una frase dispara
  el comentario largo, que pesa hasta diez veces más que un emoji.

En el largo se suma lo suyo: **loops de curiosidad abiertos** (anunciar algo que
se muestra después y cumplirlo), **re-enganche cada 60-90 s**, y **cero fricción
inicial** — nada de presentarse ni agradecer, se abre con el momento más fuerte.

### El texto en pantalla va en POST

Es la única parte de la ley que no se puede ejecutar como está escrita: los
modelos de imagen y de video **destrozan el texto**, y en un gancho eso es fatal.
Así que el texto se declara en el plano (`"texto"`) y sale como entregable de
montaje en `texto_en_pantalla.txt`, con sus tiempos:

```
   0.0 –   3.0 s  (S01)   A 80 metros, con las luces encendidas
   5.5 –   9.5 s  (S03)   -62 m
  32.0 –  38.0 s  (S08)   Vuelo 447
```

Nunca se le pide al generador. Es la misma razón por la que el contador de
profundidad de PROFUNDIDAD se puso en post y no en el prompt.

### Qué valida el módulo

- que cada tramo esté cubierto y los cortes entren en su rango;
- que **no haya huecos sin interrupción de patrón** más largos que el máximo;
- que donde el tramo pide texto en pantalla, algún plano lo traiga;
- que la duración entre en las plataformas declaradas (a 90 s ya no es un Short).

---

## Un plano, como lo escribe el director

```json
{
  "id": "S01", "tipo": "PP", "corta": 3.0,
  "funcion": "HOOK. Bucle abierto: la voz promete algo y no lo entrega.",
  "ve":    "EXTREME CLOSE UP on the curved glass port of a black diving mask…",
  "mueve": "The eyes flick left, then right, then lock forward. A slow blink…",
  "audio": "[Foley] slow heavy breathing through a rebreather, very close and dry."
}
```

- **`ve`** es lo que se ve **quieto** → va al dibujo del primer fotograma.
- **`mueve`** es lo que pasa **a partir** de ese fotograma → va al prompt de H3.
- **`corta`** es cuánto dura **en la línea de tiempo**. En el short el módulo
  genera de más (H3 no baja de 5,17 s) y anota el tramo en `usa`. En el largo el
  plano se usa entero.

Todo lo demás —el bloque de castellano, el «no inventes», la regla del humo, la
escala del tamaño de plano, el formato— lo pone el módulo. Ver [REGLAS.md](REGLAS.md).

---

## Qué máquina, y qué significa "segura"

`vast.buscar()` filtra tres cosas y ordena por una cuarta:

1. **Que corra.** 4 placas de 32 GB, fiabilidad ≥ 99,5 %, verificadas. Dos
   trampas que el filtro por gigas no ve: una **Tesla V100** tiene los mismos
   32 GB que una 5090 y es de 2017 sin bf16 (se descarta por nombre), y
   `deverified` es una máquina a la que Vast le **sacó** la verificación — el
   filtro `verified` de la consulta la deja pasar igual.
2. **Que no te lo corten.** Sólo `on-demand`, nunca interruptible.
3. **La licencia.** La MiniMax H3 Community License excluye **EE.UU., la UE, el
   Reino Unido y Corea del Sur** del despliegue local. Eso saca casi la mitad de
   la oferta; queda Taiwán, Japón, Canadá, Emiratos, Hong Kong.
4. **Ordena por costo total del trabajo, no por precio por hora.** Hay que bajar
   59 GB antes del primer plano. En una búsqueda real, la oferta de $2.138/h con
   1886 Mbps salió **más barata en total** que la de $1.761/h con 885.

> **Sobre "4× 4090 de 32 GB":** la RTX 4090 estándar tiene **24 GB**, no 32 —
> ahí no entra cómodo el GGUF Q5 de 23,9 GB con el encoder. La placa de 32 GB es
> la **RTX 5090**, que es la más común en Vast para esta búsqueda (18 de 60
> ofertas de 4 placas). El filtro va por **gigas y no por nombre**, así que si
> aparecen 4090 de 48 GB (existen, modificadas) también entran.

---

## Costos

`costos.py` calcula desde las mediciones reales de [`COSTOS-H3.md`](../COSTOS-H3.md),
no desde una regla de tres. El modelo es `1,2 min fijos + parte que crece con el
largo^1,68`, derivado de los dos puntos medidos a 8 pasos y turbo (10,1 s → 6,6 min
y 15,1 s → 11,8 min).

**Honestidad sobre el rango:** esos dos puntos son de 10 y 15 s, y la mitad de
los planos de un short dura menos de 7. Ahí esto **extrapola por debajo de lo
medido**. Por eso `runner.py` escribe `metricas.json` con el tiempo real de cada
plano y su duración al lado: con una corrida se reajusta la curva con 42 puntos
en vez de 2.

Contraste útil: para Aladino (42 planos, 5:09) el módulo estima **52 min y
$1.65**, y el rango documentado a mano era 45-56 min y $1.44-$1.77.

---

## La voz

H3 genera audio pero **no sostiene una voz entre clips** — no tiene voice ID.
La regla: *H3 genera lo que nace y muere dentro del plano; ElevenLabs, todo lo
que cruza el corte.* Por eso la voz es una capa aparte, y tiene su propio paso
obligatorio entre guion cerrado y sintetizar.

### `voz.py` — densidad y emoción

Dos cosas, las dos se resuelven **en el texto, no en el audio**:

- **Cuánto dura.** El español corre a ~17 caracteres por segundo. Debajo de 11
  cps la voz termina y los labios siguen; arriba de 22 no entra ni comprimiendo.
- **Cómo se dice.** El tag de entrega de v3 (`[whispers]`, `[sighs]`, …). Uno
  por línea, al principio, y **sólo en intensidad alta**: en intensidad media el
  tag corre el timbre lo justo para que el personaje suene a otra persona, y eso
  rompe lo único que ElevenLabs aporta.

La regla contraintuitiva: **si la línea es corta para su hueco se escribe más
texto, no se estira el audio.** Estirar tolera 1,08×; comprimir, 1,15×.

El módulo calcula la ventana solo, y distingue dos casos que no son lo mismo:

| | ventana | qué se exige |
|---|---|---|
| **con boca** (diálogo de un plano) | el plano, o `ventana_dialogo` si se declara | mínimo **y** máximo: quedarse corto se ve como labios moviéndose sin voz |
| **en off** (voz del short) | hasta que entra la línea siguiente | sólo el máximo — el silencio entre líneas es parte del guion |

```bash
python -m h3pipeline voz ejemplos/aladino/proyecto.json
```

En Aladino eso marca las **ocho líneas** por debajo de 11 cps: es el mismo
defecto que el doblaje encontró después de generar, detectado antes.

### `tts.py` — varias redacciones, gana la que mide mejor

La densidad sirve para estimar, pero a nivel toma el error llega al 30 %.
Escribir una redacción y esperar que entre es apostar. Se sintetizan dos o tres
y entra la de factor más cercano a 1,00; se cachea por hash del texto, así que
cambiar una no vuelve a pagar por las demás.

Es barato —19 líneas suman ~500 caracteres, el 0,1 % de la cuota— y elige mejor
que el criterio propio: en producción eligió sola `[yawns]` sobre `[sighs]`.

### `doblaje.py` — isocronía

Para reemplazar las voces que H3 inventa por voces fijas. **La ventana la define
la boca; el texto se escribe para esa ventana; el audio casi no se toca.**

- La ventana sale de la energía del stem de voz, no del ASR: el ASR agrupa en
  frases y esas frases se comen silencios enteros (una línea que daba 8,63 s
  tenía 5,24 s de habla).
- **Un solo factor por clip.** Alinear palabra por palabra suena entrecortado.
- Se estira en el dominio del tiempo, nunca remuestreando: remuestrear cambia el
  tono junto con la velocidad. Verificado en `prueba.py`: 0,0 % de desvío de F0.
- H3 **no sincroniza su propia boca con su propio audio** —mueve los labios
  hasta 0,85 s antes— y durante ese hueco la onda está en cero, así que no hay
  medición sobre el audio que lo encuentre. Se mide por ojo, una vez por plano,
  y se pasa a `aplicar_pre()`.

> **Ojo, hay dos copias por ahora.** `tools/doblaje/` tiene la corrida de
> Aladino, viva y a mitad de una tarea (medir el corrimiento de boca de 17
> planos). `doblaje.py` es la versión general, verificada contra ese mismo
> material: `medir()` y `bloques()` dan resultados idénticos. Se unifican cuando
> Aladino esté cerrado — anotado en [PENDIENTES.md](../PENDIENTES.md) §E0.

El método completo, con el porqué de cada número, está en
[ISOCRONIA.md](../ISOCRONIA.md) y [VOZ-EMOCION-V3.md](../VOZ-EMOCION-V3.md).

---

## Los archivos

| Archivo | Qué hace |
|---|---|
| `estructura.py` | los tramos, el brief y la validación |
| `estructuras/*.json` | short-60 y largo-narrativo |
| `proyecto.py` | la definición declarativa → storyboard.json + planos.json |
| `prompts.py` | los bloques que se repiten en todos los prompts, y por qué |
| `grilla.py` | `length = 17k+5`; de 5,17 a 15,08 s |
| `frames.py` | los primeros fotogramas (nano banana) y la normalización |
| `empaquetar.py` | el ZIP: dibujos normalizados + planos + los tres scripts |
| `montaje.py` | recortar, concatenar y el SRT, con ffmpeg local |
| `voz.py` | densidad y emoción de cada línea, **antes** de sintetizar |
| `tts.py` | eleven_v3: varias redacciones, gana la que mejor entra |
| `doblaje.py` | isocronía: ventana por energía, colocación, corrimiento de boca |
| `web.py` + `web/` | la Mesa de Armado: el formulario que produce el brief |
| `musica.py` | compone la pista del video con ElevenLabs Music |
| [`VAST.md`](VAST.md) | **el runbook de alquiler**: las nueve trampas con su síntoma |
| `costos.py` | qué va a salir, desde las mediciones |
| `vast.py` | buscar cómputo seguro, alquilar, destruir |
| `remoto/setup.sh` | instala H3 en la instancia (~59 GB, sólo FL2VA) |
| `remoto/lanzar.sh` | un ComfyUI por placa y reparte los planos |
| `remoto/runner.py` | el orquestador que corre allá; también monta y saca el SRT |

## Configuración

`.env` en la raíz del proyecto, o variables de entorno:

```
nanobanana=<clave de Gemini>      # los primeros fotogramas
VAST_API_KEY=<clave de Vast>      # sólo para alquilar; buscar es público
elevenlabs=<clave>                # la voz, fuera de este módulo
```

Si Avast está instalado, rompe los certificados SSL de Python y toda descarga
falla: el módulo usa `certs/ca-bundle-avast.pem` solo si existe.
