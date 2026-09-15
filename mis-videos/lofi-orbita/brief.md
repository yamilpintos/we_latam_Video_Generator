# INVERNADERO EN ORBITA — estructura por tramos

Formato **largo** · duración objetivo **62 s** (± 4) · 1 tramos

Plataformas: YouTube

> Un video AMBIENTE que se repite en bucle: música lo-fi encima, sin voz, sin subtítulos, sin texto. No cuenta una historia y no tiene gancho: la ley de retención 2026 no aplica, se mira de fondo.
> UN SOLO ESCENARIO. Todos los planos son encuadres distintos del mismo lugar, en la misma hora y con la misma luz. Nada entra ni sale del cuarto entre plano y plano.
> EL BUCLE SE CIERRA EN EL CORTE: el último plano corta al primero como cualquier otro corte del video. Para que ese corte no se distinga, el último y el primero tienen que ser de tamaño distinto (detalle → general), igual que cualquier par de planos consecutivos (regla 8).
> CÁMARA FIJA en todos los planos: sin paneo, sin zoom, sin push-in. Lo que se mueve es la escena, despacio: lluvia, vapor, una respiración, un disco que gira, hojas. Con cámara fija, cada corte es limpio y el bucle también.
> CLIPS DE 5,17 s Y NADA MÁS (regla 1 de la corrida limpia en VAST.md). En el máster del loop se usan 5,0 s de cada uno: la cola de un clip de H3 deriva.
> NADA DE GENTE. Las caras y las nucas que se dan vuelta son el fallo más caro del modelo (regla 22 y la réplica). Si hay un ser vivo es un animal dormido, con hoja de modelo.
> NADA DE TEXTO LEGIBLE en la escena: ni carteles, ni letras de neón, ni etiquetas, ni páginas escritas. El modelo lo destroza y en un bucle se ve sesenta veces por hora.
> Estirable: el tramo está en fracción, así que `duracion_objetivo` del proyecto puede ser 62 (12 clips), 77,5 (15) o 93 (18) sin tocar esta estructura.

## BUCLE · Bucle ambiente · 0–62 s

Encuadres del mismo lugar que aguanten mirarse sin que pase nada: cada plano tiene UNA cosa que se mueve despacio y todo lo demás quieto. La luz y la hora no cambian nunca.

Exige:
- Cámara fija: sin paneo, sin zoom, sin push-in
- Un solo elemento en movimiento lento por plano; el resto, quieto
- Misma luz y misma hora en todos los planos
- Ningún plano consecutivo repite tamaño con el mismo reparto, y el último tampoco repite el del primero: el bucle es un corte más
- Nada de gente, nada de texto legible

_corte 5.0–5.3 s_

Para el fotograma (se inyecta en el prompt): `A calm, perfectly still frame from a looping ambient video meant to be watched for a long time: balanced composition, nothing dramatic, no event, no story beat, no one in the room. Every element sits exactly where it sits in the reference location.`

| plano | en línea | corta | tipo | función |
|---|---|---|---|---|
| O01 | 0.0–5.2 | 5.2 s | PG | ARRANQUE DEL BUCLE. El módulo entero desde la escotilla: las bandejas bajo luz magenta y la Tierra en el ojo de buey. |
| O02 | 5.2–10.3 | 5.2 s | PD | La Tierra por el ojo de buey, de cerca: nubes que derivan, la línea fina de la atmósfera. |
| O03 | 10.3–15.5 | 5.2 s | PD | Hojas de tomate bajo la luz magenta, una gota en la punta de una hoja. |
| O04 | 15.5–20.7 | 5.2 s | PD | Una esfera de agua flotando en el aire, con la Tierra borrosa detrás. |
| O05 | 20.7–25.8 | 5.2 s | PG | La fila de bandejas bajo la luz magenta, con el ojo de buey y la Tierra al fondo. |
| O06 | 25.8–31.0 | 5.2 s | PD | Una planta de frutilla con una frutilla roja madura bajo la luz magenta. |
| O07 | 31.0–36.2 | 5.2 s | PD | La condensación por dentro del ojo de buey, la Tierra borrosa detrás. |
| O08 | 36.2–41.3 | 5.2 s | PD | El ventilador de la rejilla girando despacio, polvo flotando en la luz. |
| O09 | 41.3–46.5 | 5.2 s | PD | Raíces blancas en un tubo transparente con burbujas subiendo, luz magenta. |
| O10 | 46.5–51.7 | 5.2 s | PG | El ojo de buey grande con la Tierra, y en primer término las siluetas de las plantas a contraluz. |
| O11 | 51.7–56.8 | 5.2 s | PD | El manojo de hierbas secas colgando y la regadera metálica sujeta a la pared. |
| O12 | 56.8–62.0 | 5.2 s | PD | CIERRE DEL BUCLE. El lado nocturno de la Tierra por el ojo de buey: la línea del amanecer avanzando. Corta a O01. |

## Verificación

- Sin avisos: cada tramo tiene su plano y ningún corte se pasa.
