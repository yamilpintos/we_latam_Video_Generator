# Prompt de investigación · infraestructura para MiniMax H3

Copiá el bloque y pegalo en una sesión nueva de Claude Code, en este mismo
proyecto. Devuelve `INFORME-H3-INFRA.md` en la raíz.

Escrito el 2026-08-13, cuando la decisión abierta era: seguir pagando H3 por
API en Replicate (0,08 US$/s en 768P) o desplegarlo en una GPU alquilada.

---

```
Necesito que investigues infraestructura para correr MiniMax H3 (modelo de video,
33B, pesos abiertos desde el 3 de agosto de 2026, repo MiniMaxAI/MiniMax-H3 en
HuggingFace) y que dejes el resultado en un archivo, no en el chat.

CONTEXTO
Produzco documentales de YouTube. Por video necesito 10 clips de 10 segundos a
768p mínimo, image-to-video: parto de una imagen semilla y el modelo la anima.
Hoy los pago en Replicate a 0,08 US$/s (0,80 US$ el clip, 8 US$ el video) y estoy
evaluando desplegarlo yo en una GPU alquilada. Trabajo en Windows y NO tengo GPU
NVIDIA local, así que todo sería sobre pods alquilados.

REGLA QUE MANDA SOBRE TODAS
No inventes ni extrapoles números. Si el dato que encontrás es de un clip de
5 segundos, decí que es de 5 segundos: NO lo multipliques por dos. Si no
encontrás algo, escribí "NO ENCONTRADO" y seguí. Un hueco honesto me sirve;
una estimación disfrazada de dato me hace perder plata.

Etiquetá cada dato con una de estas tres:
  [MEDIDO]   alguien lo corrió y publicó el número, con hardware y parámetros
  [VENDOR]   lo afirma quien vende el producto, sin verificación independiente
  [NO ENCONTRADO]
Y poné la URL de donde salió, con la fecha de publicación.

LO QUE TENGO QUE SABER

A · Velocidad real
 1. ¿Cuánto tarda un clip de 10 SEGUNDOS a 768p (1344x768) en una sola RTX 5090?
    Busco benchmarks de 10 s específicamente, no de 5 s.
 2. ¿El tiempo escala lineal con la duración o peor? En modelos de video la
    atención suele escalar peor que lineal. ¿Hay mediciones de 5 s vs 10 s vs
    15 s en el mismo hardware?
 3. Mismo dato para A100 80GB y H100, por si conviene una placa más grande.

B · Sol Engine (NVIDIA, nvlabs.github.io/Sana/Sol-Engine/)
 4. ¿Funciona con H3 hoy, o es una demo? ¿Qué hay que instalar y cuánto tarda?
 5. ¿Soporta clips de 10 s o solo los 5 s del benchmark publicado?
 6. ¿Alguien independiente reportó la calidad? Usa atención dispersa y caché
    entre pasos: quiero saber si se nota en movimiento de cámara lento, grano
    de película y brillos especulares.

C · Memoria
 7. VRAM y RAM de sistema reales para 768p, 10 s, en BF16 y en las versiones
    cuantizadas (NVFP4, INT8, FP8). ¿Entra en los 32 GB de una 5090 o necesita
    offload? Si necesita offload, cuánto más lento se vuelve.
 8. ¿Cuánta pérdida de calidad tiene cada cuantización? Buscá comparaciones
    lado a lado, no afirmaciones.

D · RunPod concreto
 9. ¿Existe plantilla oficial o comunitaria de ComfyUI con H3 ya instalado?
10. Disponibilidad real de RTX 5090 en Community Cloud: ¿se consigue o hay que
    esperar? Buscá quejas de usuarios de los últimos dos meses.
11. Cómo funciona el Network Volume: costo por GB, si se puede montar en pods
    distintos, si se cobra estando apagado, y qué pasa si el pod muere a mitad.
12. Problemas conocidos de RunPod con modelos de video grandes: hosts que se
    caen, discos lentos, límites de descarga.

E · Alternativas
13. Vast.ai: precio real de una 5090 y qué tan seguido se interrumpen los
    trabajos en hosts no verificados. Buscá experiencias, no el marketing.
14. ¿Hay algún proveedor que cobre por HORA DE GPU y ya tenga H3 desplegado,
    sin que yo tenga que instalarlo?
15. Reconfirmá los precios por segundo de video de H3 en: Replicate, MiniMax
    directo, fal.ai, Novita, SiliconFlow, WaveSpeed, Together, Atlas Cloud.
    ¿Hay alguno por debajo de 0,08 US$/s en 768p?

F · El modelo, para mi pipeline
16. ¿H3 acepta primer fotograma Y último fotograma a la vez? ¿Cuántas imágenes
    de referencia? Las uso para mantener continuidad entre planos.
17. Genera audio sincronizado. ¿Se puede desactivar, o hay que silenciarlo
    después? ¿Cobran igual?
18. Duraciones y resoluciones exactas que acepta. ¿10 s es un valor permitido
    o solo 4, 6, 8, 15?
19. Confirmá que los pesos abiertos llegan solo a 768p y que el 2K depende de
    componentes no liberados.

G · Licencia
20. Texto exacto de la cláusula de territorios del MiniMax H3 Community License.
    Estoy en Argentina. ¿Puedo usarlo comercialmente en YouTube monetizado?
21. ¿Pide atribución o marca de agua?

FORMATO DE SALIDA
Escribí todo en `INFORME-H3-INFRA.md`, en la raíz del proyecto, en castellano
rioplatense. Una sección por bloque (A a G), numerada igual que acá para que se
pueda cruzar. Cada dato con su etiqueta, su URL y su fecha.

Cerrá con dos secciones:
  "LO QUE NO PUDE AVERIGUAR" — la lista de huecos, sin rellenar
  "LO QUE HABRÍA QUE MEDIR" — qué experimento concreto contestaría cada hueco

No me des una recomendación. Quiero los datos; la decisión la tomo yo.
```

---

## Las dos preguntas que más pesan

**A2 — cómo escala el tiempo con la duración.** Toda la cuenta de RunPod que
manejamos asume que un clip de 10 s tarda el doble que uno de 5 s, y eso no está
respaldado por ninguna medición. En modelos de video la atención suele escalar
peor que lineal. Si son 15 minutos y no 7,7, el ahorro se parte al medio.

**F18 — si 10 s es una duración válida.** No toca la infraestructura, toca el
guion: si H3 solo acepta 4, 6, 8 o 15 segundos, la grilla 10/5 de
`pipeline/00-MASTER-SPEC.md` no cierra y hay que rehacer el timeline.
