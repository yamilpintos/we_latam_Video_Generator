# Cómo sumar una herramienta a La Fábrica

Guía para quien trae una herramienta nueva a la web. Se lee en 10 minutos; el
ejemplo real de punta a punta es ReMusical (26/9/2026), y todos los archivos que
se nombran acá existen y se pueden abrir.

## Dónde está y cómo se despliega

| | |
|---|---|
| Web en producción | https://we-latam-video-generator.onrender.com (pantalla de login; usuario y contraseña los da Yamil) |
| Hosting | Render, servicio `la-fabrica`, Docker (`Dockerfile` + `render.yaml`), plan Starter, disco persistente de 20 GB en `/app/mis-videos` |
| Repo que despliega | `yamilpintos/we_latam_Video_Generator`, rama `main`. **Cada push a `main` redespliega Render solo.** |
| Repo espejo | `yamilpintos30-sy/We_latam_Factory` (mismo código; se pushea a los dos) |
| Local | `h3pipeline/app/arrancar-fabrica.bat` → http://127.0.0.1:8787 (sin contraseña si no está `FABRICA_PASSWORD`) |
| Claves | variables de entorno en el panel de Render, o `.env` en la raíz para local. **Nunca al repo.** Lista en `DEPLOY.md` |

Como el push despliega, se trabaja en una rama propia, se prueba local, y
recién ahí se mergea a `main`.

## Cómo está armada (lo mínimo para ubicarse)

- **Servidor**: FastAPI, un solo proceso, [`h3pipeline/app/server.py`](../h3pipeline/app/server.py).
  Cada endpoint llama a un módulo (`libre.py`, `editar.py`, `remaster.py`…) o
  lanza una tarea.
- **Front**: una sola página, [`static/index.html`](../h3pipeline/app/static/index.html) +
  [`static/app.js`](../h3pipeline/app/static/app.js) + `app.css`, router por hash
  (`#/libre`, `#/remaster`…). Las "puertas" de la portada son tarjetas en `app.js`.
- **Login**: un middleware en `server.py` protege TODO (páginas y APIs) con la
  cookie de sesión. Lo que cuelgues abajo queda protegido sin hacer nada.
- **Tareas largas**: [`tareas.py`](../h3pipeline/app/tareas.py) corre un
  subproceso y el front lo sigue por `/api/tareas/{id}` (log en vivo, botón parar).
- **Herramientas autocontenidas**: carpeta [`herramientas/`](../herramientas/).
  Cada una es un paquete Python independiente con su propia web.

## Dos maneras de entrar. Elegí una.

### A) Herramienta autocontenida, montada en `/<nombre>/`  (la de ReMusical)

Para una herramienta que **ya tiene su propia web** (o su propia lógica grande)
y no querés reescribirla dentro de `app.js`. La Fábrica la importa y la monta
bajo un prefijo; ella sigue siendo ella.

**El contrato que tiene que cumplir tu herramienta:**

1. Vive en `herramientas/<nombre>/` y adentro hay un paquete Python que expone
   una app **FastAPI** llamada `app` (por ejemplo `herramientas/<nombre>/<nombre>/web.py`
   con `app = FastAPI()`). Se tiene que poder correr sola con
   `python -m <nombre>.web`, así se prueba sin La Fábrica.
2. **URLs relativas.** Tu HTML y tu JS no pueden asumir que viven en `/`.
   `fetch("api/algo")` sí; `fetch("/api/algo")` no (eso es la API de La Fábrica).
   Si necesitás la URL absoluta (un callback de OAuth, por ejemplo), calculala
   del request: `str(req.base_url) + req.scope.get("root_path", "")`.
   Mirá `_callback_url` en `herramientas/remusical/remusical/web.py`.
3. **Nada pesado al importar.** Al importar tu `web.py` no se puede cargar
   torch, un modelo, ni abrir conexiones: eso va adentro del endpoint o del
   worker. El servidor de Render tiene 512 MB y arranca con todas las
   herramientas a la vez.
4. **Claves del entorno.** Leelas con `os.environ` (y, si querés, de un `.env`
   propio en `herramientas/<nombre>/.env`, que va al `.gitignore`). Documentalas
   en un `.env.example`.
5. **Sus dependencias en su `requirements.txt`**, y las que necesita la WEB
   (no el motor) también agregadas al `requirements.txt` de la raíz, que es el
   que instala el Dockerfile. Las del motor pesado (torch, etc.) no van a Render.
6. **Tests que no gasten**: sin llamar a APIs pagas ni alquilar nada. Un
   `python -m tests.correr_todo` que devuelva 0.

**Cablearla en La Fábrica (cuatro toques):**

1. Un módulo `h3pipeline/app/<nombre>_mount.py` que prepara el entorno, hace
   `sys.path.insert(0, "herramientas/<nombre>")`, importa `from <nombre> import web`
   y devuelve `web.app`, o el error si no pudo importar. Copiá
   [`remusical_mount.py`](../h3pipeline/app/remusical_mount.py): ya resuelve
   las claves compartidas (ElevenLabs), el `.env` propio y la caída limpia.
2. En `server.py`, debajo de `app.mount("/static", …)`:
   ```python
   MIA, MIA_ERROR = mia_mount.cargar()
   if MIA is not None:
       app.mount("/mia", MIA, name="mia")
   ```
   y un `GET /api/mia` que devuelva su estado (montada, qué le falta), como
   `remusical_estado()`. Si no se pudo importar, una ruta `/mia/` que explique
   qué instalar, en vez de tirar el servidor.
3. En `index.html`, un link en la barra: `<a href="/mia/">Mía</a>` (sin
   `data-r`: no es una vista del router, es otra página).
4. En `app.js`, una `div.puerta` más en la portada, con
   `onclick="location.href='/mia/'"`, un texto de dos líneas que diga qué hace
   y un `span.n` con su estado leído de `/api/mia`. Mirá `pintarReMusical()`.

Dentro de tu web, agregá un link «← La Fábrica» a `../` que se muestre sólo
cuando `location.pathname` no es `/` (así sola no aparece).

### B) Vista adentro de la página  (la de Libre, Editar, Remasterizar)

Para una herramienta chica que se siente parte de la misma app: un formulario,
una tabla, botones que lanzan tareas.

1. **Módulo** `h3pipeline/app/<nombre>.py` con la lógica pura (sin FastAPI
   adentro). Su estado en `mis-videos/_<nombre>/` (es el disco persistente de
   Render; lo que no esté ahí se pierde en cada deploy). Ejemplo corto:
   [`libre.py`](../h3pipeline/app/libre.py).
2. **Endpoints** en `server.py`, todos bajo `/api/<nombre>/…`, con `pydantic`
   para los cuerpos. Lo que tarda más de unos segundos no se hace en el
   request: se lanza con `tareas.lanzar("nombre visible", ["-m", "modulo", …], slug)`
   y se devuelve `{"tarea": t.a_dict()}`; el front lo sigue solo.
3. **Vista** en `app.js`: `ruta("/<nombre>", async () => { … $("#vista").innerHTML = … })`.
   Helpers que ya existen y hay que usar: `api(ruta, opts)` (fetch a `/api` con
   errores como excepción), `h()` (escapar HTML), `toast()`, `confirmar(titulo,
   cuerpo, etiqueta, fn)` (diálogo antes de algo caro), `seguirTarea(t, alTerminar)`.
4. **Link** en la barra con `data-r="/<nombre>"` y **puerta** en la portada con
   `location.hash='#/<nombre>'`.

## Reglas de la casa (las que cuestan plata o seguridad)

- **Nada que cobre corre sin `confirmar: true`** en el cuerpo del request, y en
  el front pasa por `confirmar(...)` con el costo estimado a la vista.
- **Lo que alquila, destruye.** Toda máquina alquilada (Vast) se apaga sola al
  terminar, al fallar y al pasar un tope. Mirá `remaster.py` o
  `herramientas/remusical/remusical/nube/provisionar.py`.
- **Secretos jamás al repo**: `.env`, `RENDER-VARIABLES.txt`, JSON de cuentas
  de servicio. El repo `we_latam_Video_Generator` es **público**.
- **Medios no van a git**: `*.mp4`, `*.wav`, `*.png`… están ignorados. Si tu
  herramienta necesita unos pocos archivos de demo, excepción explícita en
  `.gitignore` (como `!herramientas/remusical/remusical/static/demo/*.mp4`).
- **El proceso de Render es liviano**: orquesta, no procesa. El trabajo pesado
  va a una GPU alquilada o a la PC.
- **Consola de Windows**: `python -X utf8 -u`. Un `→` en un `print` sin eso
  tira el proceso. Los tests corren con `PYTHONUTF8=1`.

## Antes de mergear a `main` (checklist)

- [ ] `python -X utf8 -u -m h3pipeline.app 8799` arranca sin errores y la
      portada muestra la puerta nueva.
- [ ] La herramienta responde en su URL (`/<nombre>/` o `#/<nombre>`) y su
      `/api/<nombre>` dice qué le falta cuando no hay claves.
- [ ] Sin claves configuradas no se cae: avisa.
- [ ] `git diff --cached --name-only` no tiene `.env`, claves ni medios.
- [ ] Sus tests pasan y no gastaron nada.
- [ ] Una fila en la tabla de puertas de
      [`h3pipeline/app/ESTADO-FABRICA.md`](../h3pipeline/app/ESTADO-FABRICA.md)
      y sus variables en [`DEPLOY.md`](../DEPLOY.md).
- [ ] Rama propia → PR o merge a `main` → `git push generator main` y
      `git push origin main`. Render redespliega; revisar que arranque.

## El ejemplo completo: ReMusical

Commit `12e0a3a`. Tocó exactamente esto, y nada más del resto de La Fábrica:

| archivo | qué |
|---|---|
| `herramientas/remusical/` | la herramienta entera, copiada sin cambios de su repo de origen |
| `h3pipeline/app/remusical_mount.py` | entorno + import + estado (nuevo, 90 líneas) |
| `h3pipeline/app/server.py` | 4 líneas de mount, `GET /api/remusical`, la página de caída |
| `h3pipeline/app/static/index.html` | 1 link en la barra |
| `h3pipeline/app/static/app.js` | 1 puerta + `pintarReMusical()` |
| `requirements.txt`, `.gitignore`, `.dockerignore` | sus dependencias web, sus exclusiones |
| `ESTADO-FABRICA.md`, `DEPLOY.md` | la fila y las variables |
