# Desplegar La Fábrica (Render u otro host con Docker)

La web es `h3pipeline/app/`. Corre en cualquier lado con Docker: el `Dockerfile`
de la raíz trae Python 3.12, **ffmpeg** (corte y máster) y el **cliente SSH**
(hablar con la máquina de Vast). Los modelos de H3 no van en el servidor: viven
en la GPU alquilada. Lo que sí queda en el servidor son los proyectos y los
clips bajados, en `mis-videos/`: **montá un disco persistente ahí** o se pierden
en cada deploy.

## Variables de entorno

| variable | qué es | obligatoria |
|---|---|---|
| `FABRICA_PASSWORD` | contraseña de acceso (HTTP Basic, cualquier usuario). Sin ella, cualquiera con la URL puede alquilar GPU con tu cuenta | **sí, en cualquier servidor** |
| `OPENAI_API_KEY` | traducción de guiones (gpt-5.1) e imágenes (GPT) | sí |
| `ELEVENLABS_API_KEY` | voz y música | sí |
| `VAST_API_KEY` | buscar, alquilar, seguir y destruir máquinas | sí |
| `VAST_SSH_PRIVATE_KEY` | la clave privada `~/.ssh/id_ed25519` de tu PC, entera, con los saltos de línea (Render acepta multilínea). Es la que Vast conoce | sí |
| `VAST_SSH_PUBLIC_KEY` | el contenido de `~/.ssh/id_ed25519.pub` | sí |
| `nanobanana` | clave de Gemini para nano banana; opcional (hoy sin créditos; OpenAI es el default) | no |
| `FABRICA_HOST` | `0.0.0.0` en un servidor (el Dockerfile ya lo pone) | ya está |
| `PORT` | lo pone Render | ya está |

Nombres alternativos que el módulo también acepta: `vasia` / `VASTAI_API_KEY`
para Vast, `elevenlabs` para ElevenLabs, `openai` para OpenAI,
`GEMINI_API_KEY` para nano banana.

## Render, paso a paso

1. **New → Blueprint**, conectás el repo `we_latam_Video_Generator`. Render lee
   `render.yaml`: servicio web en Docker, disco de 20 GB en `/app/mis-videos`,
   y las variables de arriba marcadas como «sync: false» para que las cargues
   a mano en Environment.
2. Cargás las variables. La clave SSH privada: copiá el archivo completo
   (`-----BEGIN OPENSSH PRIVATE KEY-----` … `-----END …-----`).
3. Deploy. El chequeo de salud pega en `/api/estructuras`.
4. Entrás a la URL, el navegador pide usuario y contraseña: cualquier usuario,
   la contraseña es `FABRICA_PASSWORD`.

## Lo que hay que saber

- **Plan**: el servicio es liviano (no genera video: manda trabajo a Vast y
  baja los clips), pero **no puede dormirse** mientras haya una cola corriendo
  o una máquina encendida: los vigías viven en el proceso. Un plan que apaga
  el servicio por inactividad (el gratuito) corta la cola y deja la máquina de
  Vast cobrando sin que nadie la apague. Usá un plan que no duerma.
- **Disco**: los clips bajados pesan 1-2 MB cada uno; un video de un minuto
  son ~15 MB, un largo ~150 MB. 20 GB alcanzan para cientos.
- **Bajar los másters a tu PC**: desde la web, cada archivo del paso Máster se
  descarga con un clic.
- **El Teramont**: el mismo `Dockerfile` sirve. `docker build -t fabrica .` y
  `docker run -p 8787:8787 --env-file .env -v /ruta/mis-videos:/app/mis-videos fabrica`,
  con `FABRICA_PASSWORD` y las dos variables de SSH en el `.env`.
