# Para seguir

Actualizado: **30 de agosto de 2026.** Éste es el archivo que se pega al empezar
una sesión nueva.

---

## El prompt

> Estoy haciendo videos generados con IA. El proyecto está en
> `c:\Users\Yamil\Desktop\youtube proyect`.
>
> **Leé `ESTADO-PROYECTO.md` antes de tocar nada.** Es el mapa: las dos mitades
> del proyecto (el pipeline `h3pipeline/` con su página web, y toda la operación
> en Vast.ai), qué está verificado con corridas reales, los números medidos y
> qué quedó abierto.
>
> Después, según lo que vayamos a hacer:
> - escribir o generar un video → `h3pipeline/README.md` y `h3pipeline/REGLAS.md`
> - alquilar una máquina → `h3pipeline/VAST.md`
> - estimar cuánto sale → `COSTOS-H3.md` §12
> - voz, doblaje o sincronía → `ISOCRONIA.md` y `VOZ-EMOCION-V3.md`
> - qué falta → `PENDIENTES.md`
>
> **Tres cosas que no hay que reaprender, porque ya se pagaron:**
> 1. Las once trampas de Vast están en `VAST.md`, todas implementadas. Si algo
>    falla al alquilar, el síntoma probablemente esté ahí.
> 2. Las 39 reglas de `REGLAS.md` salen de fracasos medidos, no de teoría. No
>    saques un bloque de prompt "porque parece redundante".
> 3. La máquina cobra por hora prendida. `python -m h3pipeline destruir <id> --si`
>    apenas bajaste los clips.
>
> Lo que quiero hacer ahora es: **[acá va lo tuyo]**

---

## Si no sabés qué pedir, esto es lo que más empuja

1. **Automatizar el reintento de cadenas** (E0.8 en `PENDIENTES.md`). Cuando un
   eslabón de una cadena falla por VRAM, la placa se queda parada el resto de la
   corrida y sigue cobrando: pasó, fueron 28 minutos. Es la única trampa abierta
   que cuesta plata en cada corrida y son pocas líneas en
   `remoto/runner.py:reparto()`.
2. **Un video largo entero con el módulo** (E0.9). Los dos videos hechos son
   shorts; el flujo largo está implementado y nunca corrió de punta a punta.
   Es la mitad del producto sin probar.
3. **Publicar los dos shorts y medir retención** (D4). Los tramos de la ley
   salen de un short que funcionó, no de datos. Hasta que no haya números, la
   estructura es una hipótesis bien fundada.

---

## Lo que ya está hecho, para no volver a empezarlo

- **El módulo** `h3pipeline/`: ~4.900 líneas, importable, con los dos flujos
  (short y largo), la estructura por tramos como entrada de dirección, voz,
  música, isocronía, montaje y alquiler de GPU.
- **La Mesa de Armado** (`python -m h3pipeline.web`): la página que arma la
  instrucción para el LLM a partir de la estructura elegida, con la pestaña de
  trampas de Vast.
- **Dos videos completos, hechos con GPU real:**
  - `mis-videos/78-sur/78 SUR - final.mp4` — 60 s, voz en off + música
  - `mis-videos/contramano/CONTRAMANO.mp4` — 59,5 s, diálogo con isocronía
    medida, voces por ID, música, y tres planos encadenados
- **La ley de retención 2026** implementada y validada por el módulo.
- **Los costos, medidos:** 0,67 a 0,81 min de GPU por segundo de video.

---

## Credenciales

- `.env` de la raíz → `elevenlabs`, `nanobanana`, `openai`, `vasia` (Vast).
- `Foton\dubai_v2\.env` → la cuenta de ElevenLabs **del doblaje de Aladino**. No
  cambiarla: las cuatro voces son clones `professional` que existen sólo ahí.

## Trampas del entorno

- **Avast rompe SSL en Python**: `SSL_CERT_FILE=certs/ca-bundle-avast.pem`.
- `python` resuelve al venv de DepthFlow, sin numpy — usar `/c/Python314/python`.
- Leer ffmpeg por tubería se cuelga en Windows: decodificar a archivo.
- `demucs` necesita el rodeo documentado (torchcodec roto, no existe `demucs.api`).
- **ngrok está bloqueado** por el antivirus: no se puede ni leer el ejecutable.
