# ReMusical

> **Dentro de La Fábrica (26/9/2026).** Esta carpeta es la herramienta completa, tal como corría
> sola en el monorepo We-Latam_factory (`apps/remusical`). La Fábrica la importa desde
> `h3pipeline/app/remusical_mount.py` y la monta en **/remusical/**; no hay una copia adaptada,
> es este mismo código. Sigue andando sola con `python -m remusical.web` (:8765) para probarla
> aparte. Claves y rutas propias: `.env` acá (ver `.env.example`); la de ElevenLabs la toma del
> `.env` de La Fábrica si no está acá. Tests: `python -m tests.correr_todo` desde esta carpeta.

Reemplaza la música de un video por música nueva **del mismo estilo**, conservando la voz
y el ambiente originales. 100 % automático, con sensor de rechazo: si el resultado no
pasa las seis guardas, sale marcado `REVISAR` con el informe de qué falló.

```
video → mapa de música (AudioSet) → separar sólo esas regiones (BS-Roformer)
      → por región: describir estilo → 3 takes (Eleven Music) → elegir contra la original
      → montar con ducking → 6 guardas → MP4 + stems + informe
```

## Salida

Al lado de cada video, carpeta `re-musical/` con:

| archivo | qué es |
|---|---|
| `re-musical <nombre>.mp4` | el video con la música nueva (video copiado, sin recomprimir) |
| `<nombre> - voz.flac` | la voz original aislada |
| `<nombre> - musica original.flac` | la música que se quitó |
| `<nombre> - musica nueva.flac` | la música que se puso |
| `<nombre> - ambiente.flac` | sólo con `--completo`: viento, motor, pasos… |
| `<nombre> - informe.json` | regiones, estilo detectado, takes, guardas, créditos |

Por defecto los stems cubren **sólo las regiones con música** (±12 s); el resto es
silencio. `--completo` separa el archivo entero (12,5x tiempo real en CPU).

## Como módulo (para llamarlo desde tu `main`)

```python
from remusical import api

inf = api.procesar_video("C:/videos/a.mp4")                 # un video, acá
api.renivelar("C:/videos/re-musical", "C:/videos/a.mp4")    # corregir niveles de una entrega
api.tanda_local(manifiesto, workers=2)                      # varios videos, acá, en paralelo

api.vast_ofertas(gpus=4, tope_usd_h=0.6)                    # precios de máquinas VERIFICADAS ahora
api.tanda_vast(manifiesto, gpus=4, tope_usd_h=0.6, max_usd=50, max_horas=12)
api.vast_panico()                                           # destruir todas nuestras instancias
```

Nada imprime salvo lo que pases en `log`; nada lee `argv`; los errores son excepciones.
Tandas y Vast: `docs/VAST.md`.

## Uso local

```
cd Foton\ReMusical
python -m remusical "C:\ruta\video.mp4"            # uno
python -m remusical *.mp4 --takes 3                # varios
python -m remusical video.mp4 --completo           # stems completos
```

## Web con Google Drive

```
python web\app.py        →  http://localhost:8765
```

La persona conecta su Drive, navega carpeta por carpeta, elige uno o varios videos y
el resultado se sube a `re-musical/` **dentro de la carpeta donde estaban**.

Necesita `ReMusical/.env` con `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` (ver
`.env.example`; la página explica cómo crearlos si faltan). La key de ElevenLabs la
toma de `dubai_v2/.env` si no está en el entorno.

## Dos modos de la web (`REMUSICAL_MODO`)

| modo | qué corre acá | para qué |
|---|---|---|
| `local` (default) | todo: baja el video, procesa con el motor, sube | tu notebook |
| `replicate` | sólo la web; el trabajo va a un contenedor GPU en Replicate que baja de Drive, procesa y sube a Drive | Render Starter (512 MB) |

El contenedor es `cog.yaml` + `predict.py`; lo publica GitHub Actions. Ver
`docs/DESPLIEGUE.md`.

## Requisitos

- Python 3.14 con `transformers`, `torch`, `librosa`, `soundfile`, `scipy`, `fastapi`,
  `uvicorn`, `google-api-python-client`, `google-auth-oauthlib` (ver `requirements.txt`)
- Python 3.11 con `audio-separator` (lo usa `dubai_v2/_work/ab_scribe/sep_run.py`)
- `ffmpeg` (`dubai_v2/_bin/ffmpeg.exe`)

Rutas y umbrales: `remusical/config.py`.

## Cómo se genera la música (y cuánto cuesta)

**Un tema por estilo, un take bajo demanda.** Las pistas del video se agrupan por
familia de género (country/folk, rock, electrónica, clásica, funk, un ánimo…); se
genera **un tema por familia**, de hasta 240 s (`REMUSICAL_TEMA_MAX_S`), en paralelo, y
cada pista toma un **tramo distinto** de su tema. Intro y outro tienen tema propio. Es
lo que hace una banda sonora real —pocos temas que vuelven— y lo que baja el costo.

De cada tema se genera **un solo take**; sólo se pide otro si se descalifica (drone,
p(música) baja) o se parece poco al original (distancia > 0,45), hasta `--takes` (default 3).

| medido en "La ruta de la seda" (27 min, 25 min de música, 20 pistas) | |
|---|---|
| temas generados | 8 (9 generaciones: una pidió un 2º take) |
| minutos generados | 16,6 para 25,2 de música |
| **créditos ElevenLabs** | **16.600 = USD 3,03** (plan Scale) · USD 1,49 (Business) |
| antes, 3 takes por pista | 77.442 = USD 14,12 |
| guardas | 6/6 al primer intento |
| reloj con mapa y separación cacheados | 50 min en CPU |

Por hora de video al 80 % de música: **~USD 6,50** en Scale, **~USD 3,80** en Business
(GPU en Replicate incluida). El costo escala con los **minutos de música**, no con la
duración del video.

## Alcance

Validado sobre vlogs/documentales con música en las puntas. En ficción con score
continuo el mapa da "todo es música": correcto pero trivial. Si el material trae
stems de estudio, no hace falta detectar nada.
