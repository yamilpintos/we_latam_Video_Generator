# Doblaje

Doblás videos de tu Google Drive a otro idioma. Conectás Drive, navegás carpeta por
carpeta, elegís uno o varios videos, el motor, el idioma y la fuerza de clonado, ves el
costo en créditos ANTES de confirmar, y el resultado se sube a una carpeta `doblaje/`
dentro de la carpeta donde estaba cada video.

Dos motores:

| Motor | Estado | Qué hace |
|---|---|---|
| **ElevenLabs Dubbing v2** | anda | Transcribe, traduce y sintetiza con la voz clonada del actor. Salida: sólo audio; esta app lo pega sobre el video original. |
| **Motor propio** | todavía no está subido | La cadena propia (ASR → traducción → clones con casting). Aparece en la web, deshabilitado, hasta que se suba. |

## Lo que aprendimos a los golpes (y esta app ya trae puesto)

- **`cloning_strength` es la perilla que importa.** Va de 0 a 10; el valor por defecto de
  ElevenLabs es 7 y con ése el modelo **copia el audio original** en los segmentos
  difíciles (susurros, rezos, gritos): quedan en el idioma de origen. Con 1, once videos
  salieron limpios. La SDK de Python **no expone** el parámetro; acá se manda por HTTP.
- **Regenerar es gratis pero acá no hace falta**: el cobro es una sola vez, por segundo de
  fuente, al crear el idioma. Medido: 13.245 créditos/min en la cuenta paga.
- **Cada video se verifica solo**, comparando el audio doblado contra el original,
  segmento por segmento (pasa-banda de voz + correlación con desfasaje). Si queda algo en
  el idioma de origen, el trabajo termina en **REVISAR** con los timecodes.
- **Los archivos grandes se comprimen antes de subir** (1,8 GB → 84 MB, mismo cobro), y el
  audio final se pega sobre el original en calidad plena.

## Correr sola

```
cd apps/doblaje
pip install -r requirements.txt
cp .env.example .env        # completar GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / ELEVENLABS_API_KEY
python -m doblaje.web       # → http://localhost:8790
```

Montada en el portal: `python portal/app.py` → `http://localhost:8000/doblaje/`.

## Qué necesita

- **Google OAuth** (una vez): Google Cloud → habilitar Drive API → pantalla de
  consentimiento (externo, tu mail como usuario de prueba) → ID de cliente OAuth,
  aplicación web, URI de redirección `http://localhost:8790/auth/callback`.
- **`ELEVENLABS_API_KEY`**. Si no está en `.env`, se toma de `dubai_v2/.env`. Una segunda
  cuenta opcional en `ELEVENLABS_API_KEY_ALT` (aparece un selector).
- **ffmpeg** (`FFMPEG` en `.env`, o `dubai_v2/_bin/ffmpeg.exe`, o `~/ffmpeg/*/bin`, o el PATH).
- **numpy**, sólo para la verificación acústica; sin numpy la app dobla igual y avisa
  que no verificó.

El procesamiento corre en la máquina que sirve la web (baja de Drive, sube a ElevenLabs,
pega el audio, verifica, sube a Drive). No hay GPU de por medio: el trabajo pesado lo
hace ElevenLabs.

## Guardas de gasto

- Estimación a la vista antes de confirmar, contra el saldo real de la cuenta.
- No arranca si el saldo no alcanza para lo que se pidió.
- Tope de trabajos simultáneos (ElevenLabs admite 3 por cuenta) y por día.
- No manda dos veces el mismo video mientras uno está en curso.
- Un video de más de 180 min no entra (límite de ElevenLabs).

### Control de créditos (26-sep, `doblaje/creditos.py`) — la web y los scripts de la PC, la misma política

- **Libro mayor** `_trabajo/ledger_creditos.jsonl`: cada proyecto e idioma que se crea pasa por `Cuenta` y queda
  anotado con saldo antes/después, cobro medido, quién lo pidió (web o `cli:<script>`) y para qué.
- **Tope por trabajo** (`DOBLAJE_MAX_CR_POR_TRABAJO`, 1,2 M ≈ 90 min), **tope por día** (`DOBLAJE_MAX_CR_POR_DIA`,
  2 M, contando lo que está en curso) y **reserva** (`DOBLAJE_RESERVA_CR`, 50.000) que el saldo nunca toca.
- El saldo se **vuelve a chequear justo antes de crear el proyecto** (otra sesión puede haber gastado con la misma
  clave): si no pasa, el trabajo queda **frenado**, sin cobrar.
- **Cobro medido contra estimado**: si supera la tolerancia (`DOBLAJE_TOLERANCIA_COBRO`, 25 %), se **pausa todo el
  gasto** hasta que una persona lo reanude (panel «Gasto y GPU» → Reanudar, o `python saldo.py --reanudar`).
- `python saldo.py`: saldo de cada clave, gasto de hoy, topes, pausa y GPU viva. **Leerlo antes de gastar desde un chat.**

## Nivelación por pistas en la GPU de vast — automática (26-sep, `doblaje/gpu_vast.py`)

Separar voz y fondo en CPU tarda ~15 min por minuto de película (80 min ≈ 20 h). En una RTX 4090 de vast, minutos.
Con `VAST_API_KEY` y la clave ssh (`VAST_SSH_KEY`, o `~/.ssh/id_ed25519` en la PC) **la app se ocupa sola**:

1. cuando un trabajo llega a «separando», si no hay GPU nuestra viva la **alquila** (la oferta más barata ≤
   `DOBLAJE_GPU_MAX_USD_H`, probando varias porque la más barata se la llevan) y la **instala** (torch CUDA +
   audio-separator 0.44.3 + pesos; ≈6-10 min, una vez por instancia);
2. sube el wav por SFTP, corre `sep_app.py` allá (el MISMO criterio de checkpoint que el separador sellado del motor),
   baja `vocals_clean.wav` + `music_effects.wav`, borra el audio allá;
3. mientras tanto, ya subió a Drive una versión **provisoria por mezcla** (`_PROVISORIO_mezcla.mp4`); la de pistas
   la reemplaza al terminar (`DOBLAJE_PROVISORIO=0` lo apaga);
4. un **vigilante** la destruye cuando queda ociosa `DOBLAJE_GPU_OCIO_MIN` (10 min), a las `DOBLAJE_GPU_MAX_HORAS`
   (6 h) o al terminar el proceso que la alquiló; pasado `DOBLAJE_GPU_USD_TOPE_DIA` (USD 6) no alquila más y el
   trabajo cae al modo mezcla y lo dice. Al arrancar, la web **adopta** una instancia nuestra que haya quedado viva.
5. **Sólo se destruye la instancia con la etiqueta `doblaje-app`** (o nuestro id). Las demás de la cuenta no se tocan.

`DOBLAJE_GPU=auto` (alquila sola) · `manual` (sólo usa la que prendés en el panel «Gasto y GPU») · `off`.
El panel muestra fase, USD/h, horas, USD de hoy, y botones **Prender ahora** / **Apagar**.

Desde la PC, `doblar_pelicula.py` usa el mismo mecanismo (`--sep vast`, el default); `--sep local` / `--sep mezcla`
no alquilan nada. `preparar_vast.py` + `DOBLAJE_SEP_REMOTO=vast` (la instancia de `dubai_v2/docker`) siguen como
camino viejo.

Pruebas, sin prender nada ni gastar: `python -m tests.test_gpu_vast`, `python -m tests.test_creditos`,
`python -m tests.test_sep_vast`. ★ Las pruebas corren con `DOBLAJE_GPU=off` (`tests/__init__.py`): el 26-sep una
prueba que llamó a `media.separar` con las credenciales de la PC alquiló una 4090 real (USD 0,03, destruida a mano).
