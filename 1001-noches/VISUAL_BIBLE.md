# VISUAL BIBLE · Las 1001 Noches

Fuente de verdad estética de la serie. Toda ficha de personaje, todo prompt de imagen y
todo prompt de H3 se apoyan en este documento. **Ningún revisor puede modificarlo**: si
un plano exige cambiar una regla de acá, se registra el cambio en `## Registro de cambios`
antes de generarlo.

Los documentos del pipeline están en español; **los bloques de prompt están en inglés**
porque es el idioma en que se validó la estética y en el que responden mejor GPT Image y
H3. No los traduzcas.

---

## 1. Origen

La estética viene de una prueba aprobada: el prompt de Shahrazad en la cámara real. Lo que
sigue es esa prueba destilada en reglas reutilizables. Cuando haya duda sobre un plano, la
imagen madre de Shahrazad manda.

## 2. El bloque de estilo

Se pega **literal** en todo prompt de imagen. No lo parafrasees entre planos: la variación
de redacción es la primera fuente de deriva estética.

```
STYLE: animated 3D painterly + 2D + illuminated manuscript. Stylized cinematic 3D as the
base, but with painterly surfaces, visible brush-like texture, soft pigment transitions,
and selected 2D embellishments. Integrate illuminated-manuscript aesthetics into the image
language: ornamental borders, miniature-painting sensibility in some details, hints of gold
leaf, delicate calligraphic flow in smoke and decorative motifs, refined handcrafted
quality. It must not look like generic CGI. It should feel like a living painted manuscript
brought into cinematic depth.

RENDERING: stylized 3D characters and environment, painterly textures on stone, fabric and
skin, soft brush-textured shading, elegant non-photorealistic rendering, with selective 2D
hand-drawn effects for smoke, lamp glow, drifting particles and ornamental magical accents.
Balance depth and atmosphere with graphic beauty.

LIGHTING: low-key cinematic lighting. Warm amber lamp or firelight on faces and costume,
cool moonlight entering softly from the side or background, gentle rim light separating the
silhouette from the darker surroundings. Nocturnal, intimate, poetic, slightly mysterious.

PALETTE: deep indigo, lapis blue, aged gold, dark burgundy, muted sand, warm amber
highlights, touches of ivory. Rich but controlled. Avoid oversaturation.

QUALITY: premium animated feature look, highly art-directed, visually original, suitable
for a young adult and adult audience, with the uniqueness of a prestige series image.

NEGATIVE: no Disney look, no cute childlike proportions, no exaggerated cartoon comedy, no
plastic-looking CGI, no generic fantasy princess look, no modern fashion elements, no
overly glossy surfaces, no empty minimalist space, no photorealism.
```

## 3. Regla de composición: todo plano en tres capas

El prompt original pide *strong sense of parallax and layered space*, y eso deja de ser
decoración cuando cada plano nace de una imagen fija. **H3 anima lo que la imagen ya trae
separado**: si el primer fotograma es una pared plana, el modelo no tiene de dónde sacar
profundidad y el movimiento sale chato o inventa cosas.

Por eso toda imagen se compone con tres capas explícitas:

| Capa | Qué va | Para qué |
|---|---|---|
| Primer término | lámpara, tela, roca, borde de vasija — **desenfocado** | le da al parallax su desplazamiento más fuerte |
| Término medio | el sujeto del plano, nítido | es lo que el ojo sigue |
| Fondo | arquitectura, mar, cielo, ciudad a la luz de la luna | da profundidad y no se mueve casi |

En el prompt se pide explícito: `foreground element slightly out of focus, clear middle
ground with the subject, deep background for parallax`.

Con H3 la regla vale para todos los planos: el modelo genera el movimiento a partir del
primer fotograma, y una imagen con capas le da profundidad real de dónde agarrarse.

## 4. Reglas de la serie

1. **Nocturno por defecto.** La serie transcurre de noche o en luz baja. El amanecer y el
   desierto del episodio 1 son las excepciones, y se resuelven con luz rasante y cielo
   todavía oscuro, no con mediodía.
2. **La luz tiene fuente visible o justificada.** Lámpara de aceite, brasa, luna, fuego.
   Nada de luz de relleno sin origen.
3. **El humo y la magia son 2D dibujados a mano.** Nunca simulación volumétrica. El humo
   del genio lleva flujo caligráfico: es letra, no vapor.
4. **El oro es acento, no material.** Pan de oro en detalles y bordes ornamentales. Ninguna
   superficie grande dorada ni brillante.
5. **Sin texto en imagen.** Ni cartelas, ni caligrafía legible, ni números. Los ornamentos
   caligráficos son abstractos.
6. **Encuadre 16:9 cinematográfico**, un único punto focal claro por plano.

## 5. Continuidad entre planos: el árbol de cámaras

Técnica validada en el piloto anterior y la razón de que los planos no se contradigan entre
sí. **Una cámara es un lugar, no un plano.**

1. Se genera primero el plano **más abierto** de cada espacio: es la *madre*.
2. Los planos más cerrados del mismo espacio se generan **pasando la madre como referencia
   visual**, a resolución completa, no recortándola.
3. Así el cierre comparte iluminación, materiales y disposición con el general, sin el techo
   de calidad que impone recortar y ampliar.

Las madres de espacio viven en `story-bible/locations/`. Las de personaje, en
`story-bible/characters/`.

## 6. Registro de cambios

Toda regla que cambie de un episodio a otro se anota acá, con fecha y motivo. Un cambio no
registrado es un error de continuidad.

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-08-14 | Documento inicial, derivado del prompt de Shahrazad aprobado | — |
| 2026-08-25 | El generador pasa de Veo a MiniMax H3 | costo por tiempo en vez de por clip; duración de plano variable |

---

*Metodología de biblia y detección de deriva adaptada de
[story-systems-template](https://github.com/bybren-llc/story-systems-template) (MIT,
Bybren LLC). Metodología de dirección visual adaptada de
[ViMax](https://github.com/HKUDS/ViMax) y del paper
[Camera Artist](https://arxiv.org/abs/2604.09195).*
