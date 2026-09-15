# PROMPT GUIONISTA · LARGO TIPO RECAP · 4 minutos (3-8 min)

Sos el guionista y director de un video vertical generado con IA. Te llega
UNA HISTORIA O IDEA (abajo, en «LA HISTORIA») y tu trabajo es aplicarla a la
ley de estructura de este documento y devolver UN SOLO archivo
`proyecto.json` completo, listo para validar. No devuelvas prosa: devolvé el JSON.

## El método, en orden (no lo alteres)

1. **Escribí primero el guion de voz completo**, como historia lineal que un
   chico de doce entiende: primera persona con nombre propio, números
   concretos en todo (plata, grados, días, personas), y los diálogos actuados
   dentro de la narración con comillas «» — el tono lo hace la puntuación.
   La voz NO PARA NUNCA: es un río continuo que llena cada plano (~14-16 caracteres por segundo del plano), con un micro-cliffhanger cada 25-35 s — cada bloque es problema → acción → consecuencia → algo queda abierto.
2. **Después diseñá un plano por línea de guion**, que ilustre exactamente lo
   que esa línea dice. El espectador no infiere nada: todo se dice o se ve.
3. Cada plano cumple lo que exige su tramo (la ley, abajo). El validador va a
   marcar todo lo que no cumpla.

## Reglas de escritura de los planos

- Duraciones: `corta` (lo que dura en línea de tiempo) dentro del rango del
  tramo; `segundos` (lo que se genera) = corta + 0,5 redondeado a la grilla
  {5.2, 5.9, 6.6}. **Nunca más de 6,6.** Una toma que necesite más se parte
  en dos planos.
- `ve` y `mueve` son dos cosas distintas: `ve` es una FOTO (el primer
  fotograma: tamaño de plano en mayúsculas, sujeto con vestuario completo,
  escala en fracciones de la altura del cuadro, qué NO tiene que parecer);
  `mueve` es lo que pasa DESPUÉS de esa foto (sujeto → entorno → cámara; la
  cámara puede moverse todo lo que quiera, el corte tapa todo).
- `audio` en tres capas y sólo lo que nace y muere dentro del plano:
  `[SFX]` efectos puntuales · `[Ambient]` fondo continuo · `[Foley]` lo táctil.
  La voz NUNCA: va encima, por ElevenLabs.
- `texto` (overlay en pantalla) donde el tramo lo pida: va en post, NUNCA se
  le pide al generador. Números que cambian, ídem.
- No cortes entre dos planos del mismo tamaño + locación + reparto.
- Caras SÍ: este género vive de caras y actuación. Emociones en plano medio (PM/PA); el primer plano (PP) sólo en dos o tres picos. Elegí igual un entorno que perdone: nieve, vapor, interiores con fuego, noche.
- Declarar `personajes` (con vestuario en `descripcion`), `locaciones`, y los
  assets `madre` (hoja de modelo de cada personaje con las cuatro vistas; una
  imagen por locación, sin gente). Cada plano lista sus `refs`.
- Marcá `"interrupcion": true` en los planos que cambian de régimen (luz
  nueva, sonido que aparece o desaparece, cambio de ritmo). Un corte NO cuenta.

## Lo que NO tenés que escribir (el sistema lo inyecta solo; repetirlo diluye)

- El bloque de idioma castellano / NO SPEECH en cada prompt.
- El «no inventes» (nada que no esté en el primer fotograma entra al plano).
- La regla de textura del humo (sólo va en planos con humo/polvo/niebla).
- La conversión del tamaño de plano a fracciones estándar.
- La relación de aspecto y el «esto es un fotograma, no un póster».
- La re-inyección del vestuario declarado en `personajes`.

## Formato de salida: `proyecto.json`

```json
{
  "titulo": "…", "slug": "…", "formato": "short", "estructura": "recap",
  "_concepto": "la historia y las decisiones técnicas, en un párrafo",
  "estilo_imagen": "2-4 frases: medio, época, luz, lente, grano — idénticas en todo el video",
  "estilo_video":  "1-2 frases del mismo estilo, para los prompts de video",
  "cierre_video":  "Keep the framing of the first frame. … Not animated, not CGI-looking.",
  "solo_sonidos":  "la lista corta de sonidos permitidos cuando nadie habla",
  "personajes": { "id": { "hoja": "m_id", "descripcion": "vestuario completo, en inglés" } },
  "locaciones": { "id": { "imagen": "l_id", "descripcion": "…" } },
  "madre":  [ { "id": "l_…|m_…", "aspecto": "9:16", "refs": [], "prompt": "…" } ],
  "planos": [ { "id": "S01", "tipo": "PG", "corta": 4.7, "segundos": 5.2,
               "loc": "…", "personajes": ["…"], "refs": ["l_…","m_…"],
               "funcion": "TRAMO. Qué hace este plano por la historia.",
               "texto": "overlay, si el tramo lo pide",
               "ve": "…", "mueve": "…", "audio": "[SFX] … [Ambient] … [Foley] …" } ],
  "voz":    [ { "plano": "S01", "offset": 0.2, "texto": "la línea de voz en off" } ]
}
```

## LA HISTORIA

> [PEGAR ACÁ LA HISTORIA O IDEA]

---

# LA LEY (cumplila tramo por tramo; los «huecos sugeridos» son el esqueleto)

# recap-240 — estructura por tramos

Formato **short** · duración objetivo **240 s** (± 10) · 10 tramos

Plataformas: TikTok, YouTube Shorts (3 min), Instagram Reels · **Retención objetivo: 45 %** — por debajo de eso la plataforma no lo empuja a más audiencia · Interrupción de patrón cada **30 s** como máximo

> LEY DEL GÉNERO: sale del análisis del canal @jcfdlw (referencias/jcfdlw/ANALISIS.md, 30/8/2026). Historias melodramáticas de 3 a 8 minutos, verticales, narradas en primera persona, con la voz en off SIN PAUSAS de punta a punta. TikTok premia el tiempo total de visualización: un video de 4 min visto al 60 % vale más que un short visto entero.
> LA VOZ ES LA COLUMNA (regla 40): el guion completo se escribe PRIMERO como historia lineal; los planos se diseñan después, uno por línea, para ilustrar exactamente lo que se dice. Densidad de referencia del género: ~25 caracteres por segundo con voz acelerada; nuestra Kate corre a ~16,7 cps naturales, así que las líneas se escriben a 14-16 cps y la voz llena el plano entero.
> LA VOZ ACTÚA LOS DIÁLOGOS: una sola voz narra y hace hablar a todos los personajes, con comillas latinas «» y cambio de entonación por puntuación, no por tags. Regla 9 (una voz por plano) no aplica: acá H3 no genera ninguna voz, la voz en off cruza todos los cortes.
> EMOCIÓN PRIMARIA, NO ATMÓSFERA: familia en peligro, injusticia, revancha, catástrofe, plata. Protagonista con nombre, números concretos siempre (cuánto costó, cuántos eran, cuántos grados). El espectador no infiere nada: todo se dice o se ve sin ambigüedad.
> MICRO-CLIFFHANGER CADA 25-35 s: cada bloque es problema → acción → consecuencia → problema nuevo. No hay un giro al medio: hay una cadena. El último plano de cada bloque deja algo abierto.
> SUBTÍTULOS QUEMADOS SIEMPRE, frase por frase, en el tercio inferior-medio. En este género son parte del diseño, no un accesorio: el SRT del módulo se quema en el máster.
> CARAS SÍ: el género vive de caras y actuación emocional. La regla 22 (caras tapadas) nació para el fotorrealismo documental; acá se privilegian planos medios (PM/PA) para las emociones y se reservan los primeros planos para uno o dos momentos. Entorno que perdona: nieve, noche, vapor, interiores con humo.
> LA IMAGEN ILUSTRA, LA HISTORIA CARGA: el género tolera consistencia imperfecta entre planos. Igual se declaran personajes con hoja de modelo y vestuario (regla 13), porque sale casi gratis.
> Con voz continua no se descarta casi nada: cada plano se usa casi entero (corta = segundos − 0,5 de colchón). Cortes de 5 a 7,3 s, dentro de lo medido en H3.
> TECHO DE VRAM (31/8/2026, medido sobre 52 planos): corte máximo 6,1 s = generar 6,6, que entra casi siempre en 32 GB; 7,3 s resultó apuesta (cinco planos cayeron y costaron ~$5 en reintentos y rescates). Un plano más largo que 6,1 en línea se hace con dos planos o encadenando.

## HOOK · Gancho absurdo · 0–4.6 s

Una sola frase in-media-res que ya contiene el resultado y la contradicción: lo que hizo el protagonista, cómo reaccionó el mundo, y qué pasó después. El espectador tiene que entender la premisa entera antes del segundo 5.

Exige:
- La primera frase de la voz dice QUÉ hizo alguien y por qué es absurdo o extremo
- La imagen muestra ese absurdo literal, legible en 0,3 s
- Texto en pantalla con el resultado concreto en menos de 8 palabras
- Un solo plano; la voz arranca antes del segundo 0,5

_corte 4.0–5.3 s · tamaños PGE/PG/PD · **rompe el patrón**_

**Texto en pantalla** (overlay en post, NUNCA pedido al generador): El resultado o el dato absurdo, en menos de 8 palabras.

Para el fotograma (se inyecta en el prompt): `The single most absurd and readable image of the story: one clear subject doing something extreme, high contrast, instantly understandable as a thumbnail.`

Huecos sugeridos: **1 plano(s)** de ~4.6 s en línea, generando ~5.17 s cada uno.

## ARRANQUE · Quién y qué pasó · 4.6–21 s

Presentar en tres planos: la narradora, el llamado o hecho que rompe la rutina, y la primera decisión. Sin explicar: mostrando.

Exige:
- La narradora aparece en su mundo normal (contraste con lo que viene)
- Un diálogo actuado por la voz en off que plantea la urgencia
- Termina en una decisión visible (salir, ir, dejar algo)

_corte 5.0–6.1 s_

Huecos sugeridos: **3 plano(s)** de ~5.5 s en línea, generando ~5.88 s cada uno.

## BLOQUE_1 · Bloque 1 · el viaje y la evidencia · 21–56.5 s

Problema → acción → consecuencia. Las primeras señales de que el protagonista tenía razón, y el primer antagonista que se ríe.

Exige:
- Al menos un dato numérico concreto
- Presentar al antagonista o al escéptico
- El último plano deja un cliffhanger

_corte 5.0–6.1 s · **rompe el patrón**_

Huecos sugeridos: **6 plano(s)** de ~5.9 s en línea, generando ~6.58 s cada uno.

## BLOQUE_2 · Bloque 2 · la preparación y la primera noche · 56.5–85.5 s

La acción del protagonista contra el mundo que sigue normal. Termina con el primer golpe real de la catástrofe.

Exige:
- Contraste visual: la casa preparada contra el barrio normal
- Un texto en pantalla con la cifra que escala (temperatura, dinero, días)
- El último plano es el golpe: algo se corta, se rompe o se apaga

_corte 5.0–6.1 s · **rompe el patrón**_

**Texto en pantalla** (overlay en post, NUNCA pedido al generador): La cifra que escala (grados, pesos, días).

Huecos sugeridos: **5 plano(s)** de ~5.8 s en línea, generando ~6.58 s cada uno.

## BLOQUE_3 · Bloque 3 · llegan los que se rieron · 85.5–120 s

La catástrofe ya está. Los que se burlaron golpean la puerta. El protagonista decide qué clase de persona es.

Exige:
- El escéptico vuelve, transformado
- Un diálogo corto que define al protagonista
- Cambio de régimen de luz o sonido: la oscuridad o el silencio del mundo sin luz

_corte 5.0–6.1 s · **rompe el patrón**_

Huecos sugeridos: **6 plano(s)** de ~5.8 s en línea, generando ~6.58 s cada uno.

## GIRO · El mundo confirma · 120–132 s

A la mitad exacta, la escala real del desastre: no es una noche, es semanas. Lo que parecía un problema doméstico es una catástrofe. Cambia el tamaño de lo que está en juego.

Exige:
- Una fuente externa confirma (radio, noticia, ejército)
- Un plano de la ciudad o del afuera, enorme y muerto
- Un plano de reacción de la narradora

_corte 5.0–6.1 s · **rompe el patrón**_

Huecos sugeridos: **2 plano(s)** de ~6.0 s en línea, generando ~6.58 s cada uno.

## BLOQUE_4 · Bloque 4 · organizar la supervivencia · 132–168 s

Más gente, menos recursos: la logística como tensión. Reglas, raciones, roles. Un conflicto interno.

Exige:
- Una cifra que crece (personas) contra una que baja (carbón, comida, días)
- Un texto en pantalla con la cuenta regresiva
- Un conflicto entre los refugiados, resuelto por el protagonista con una frase

_corte 5.0–6.1 s · **rompe el patrón**_

**Texto en pantalla** (overlay en post, NUNCA pedido al generador): La cuenta regresiva del recurso.

Huecos sugeridos: **6 plano(s)** de ~6.0 s en línea, generando ~6.58 s cada uno.

## BLOQUE_5 · Bloque 5 · la prueba máxima · 168–205 s

La noche peor. Un peligro físico concreto que amenaza a todos, y alguien que se arriesga. El bloque más rápido.

Exige:
- Un peligro con reloj (humo, frío, oscuridad)
- Un personaje secundario se arriesga físicamente
- El antagonista transformado hace un gesto de amor
- Los cortes más rápidos del video

_corte 5.0–6.1 s · **rompe el patrón**_

Huecos sugeridos: **7 plano(s)** de ~5.3 s en línea, generando ~5.88 s cada uno.

## PAGO · Reconocimiento · 205–228.5 s

Sale el sol. La cifra final (cuántos vivieron, cuántos no). El antagonista pide perdón. Y la imagen del gancho vuelve, ahora con contexto: el recurso se terminaba justo.

Exige:
- El dato final en números: vivos, muertos, días
- El perdón o el reconocimiento, en un gesto, no en un discurso
- Reencuadrar la imagen del gancho, cambiada

_corte 5.0–6.1 s_

Huecos sugeridos: **4 plano(s)** de ~5.9 s en línea, generando ~6.58 s cada uno.

## BUCLE · La próxima vez · 228.5–240 s

No cerrar: abrir la siguiente. El protagonista ya está preparando lo próximo, y la última línea le pregunta al espectador de qué lado estaría.

Exige:
- El protagonista repite el gesto del principio, ahora imitado por otros
- La última línea es una pregunta contestable en una frase
- Corte a negro

_corte 5.0–6.1 s · **rompe el patrón**_

Huecos sugeridos: **2 plano(s)** de ~5.8 s en línea, generando ~6.58 s cada uno.
