# PROMPTS 00 — GUION Y TIMELINE

**Mars Climate Orbiter** · *El error de 4,45 que nadie vio durante nueve meses*
Preset `FULL-8` · **este documento cubre 0:00 – 5:00**, la mitad 1 de 2.

Es la referencia que ata todas las demás capas. Si algo acá cambia, cambian los cuatro archivos
de prompts y hay que recorrer el audio.

---

## La decisión narrativa

La historia tiene un problema para YouTube: **el dato más famoso es el menos interesante.** Todo
el mundo escuchó «la NASA perdió una sonda por confundir metros con pies». Abrir con eso hace que
el espectador sienta que ya sabe el final.

Así que el gancho es al revés: esa versión es cierta y es la parte aburrida. La promesa es que
hubo **nueve fallos, no uno**, y que existió una maniobra de emergencia que podía haber salvado la
nave. El espectador entiende el error técnico en el minuto 3 y a partir de ahí sufre viendo cómo
el sistema tiene cinco oportunidades de detectarlo y las pierde todas.

## Estructura

| | Rango | Función |
|---|---|---|
| **ACTO I** | 0:00 – 1:35 | Cold open, desmontar la versión famosa, prometer la real |
| **ACTO II** | 1:35 – 6:20 | La cadena: el error, por qué se multiplicó, por qué fue invisible |
| **ACTO III** | 6:20 – 8:00 | La llegada, el silencio, la reconstrucción, la lección |

---

## Presupuesto por secuencia

Grilla **10/5**: `duración = 10 × (clips VEO) + 5 × (planos de 5 s)`.
Voz medida sobre las 60 tomas reales de Sandmor: **2,57 palabras por segundo**.

| Sec | Composición | Dur | Palabras | Voz real | Densidad | Tema |
|---|---|---|---|---|---|---|
| S01 | 2 VEO + 3×5 | 35 s | 81 | 27.6 s | 79 % | Cold open: los 49 segundos |
| S02 | 1 VEO + 4×5 | 30 s | 73 | 23.8 s | 79 % | La versión famosa |
| S03 | 1 VEO + 4×5 | 30 s | 62 | 22.4 s | 75 % | La promesa |
| S04 | 1 VEO + 5×5 | 35 s | 72 | 25.9 s | 74 % | Qué era y cómo salió |
| S05 | 2 VEO + 4×5 | 40 s | 90 | 32.8 s | 82 % | Las ruedas y los empujones |
| S06 | 1 VEO + 6×5 | 40 s | 78 | 30.1 s | 75 % | El archivo |
| S07 | 1 VEO + 6×5 | 40 s | 85 | 29.8 s | 75 % | Por qué se multiplicó |
| S08 | 0 VEO + 5×5 | 25 s | 54 | 19.8 s | 79 % | Ya lo estaban viendo |
| S09 | 1 VEO + 3×5 | 25 s | 61 | 21.1 s | 85 % | Invisible · cliffhanger |
| | **10 VEO + 40×5** | **300 s** | **656** | **233.3 s** | **77.8 %** | |

Verificable con `python tools/retime.py --check`.

---

## Timeline maestro · 50 planos

| ID | IN | OUT | Dur | Tipo | Cámara | Plano |
|---|---|---|---|---|---|---|
| S01-P01 | 00:00 | 00:10 | 10 | **VEO** | A | Sala de control del JPL: la cámara avanza por el pasillo hacia el ingeniero inmóvil |
| S01-P02 | 00:10 | 00:15 | 5 | GFX | — | Traza de osciloscopio que cae a línea plana |
| S01-P03 | 00:15 | 00:20 | 5 | STILL | A | Plano general de la sala, todos de pie e inmóviles |
| S01-P04 | 00:20 | 00:30 | 10 | **VEO** | B | La nave girando lentamente contra el disco de Marte |
| S01-P05 | 00:30 | 00:35 | 5 | STILL | D | Marte a media distancia, sin nave a la vista |
| S02-P01 | 00:35 | 00:40 | 5 | STILL | M | Recorte de diario sobre una mesa de fórmica |
| S02-P02 | 00:40 | 00:45 | 5 | GFX | — | Una regla en pulgadas y una en centímetros que no encajan |
| S02-P03 | 00:45 | 00:50 | 5 | STILL | L | Pizarrón de aula con ecuaciones a medio borrar |
| S02-P04 | 00:50 | 00:55 | 5 | STILL | A | La sala de control vacía y a oscuras |
| S02-P05 | 00:55 | 01:05 | 10 | **VEO** | B | La cámara sobrepasa a la nave y la deja atrás |
| S03-P01 | 01:05 | 01:10 | 5 | STILL | G | Informe encuadernado sobre la mesa de reuniones |
| S03-P02 | 01:10 | 01:15 | 5 | GFX | — | Nueve líneas apareciendo; la primera en ámbar |
| S03-P03 | 01:15 | 01:25 | 10 | **VEO** | B | La nave pasa frente a Marte, cámara en arco |
| S03-P04 | 01:25 | 01:30 | 5 | STILL | G | Sala de reuniones: la mesa larga entera |
| S03-P05 | 01:30 | 01:35 | 5 | STILL | I | Sala limpia: la nave en construcción |
| S04-P01 | 01:35 | 01:40 | 5 | STILL | B | La nave completa con el panel solar desplegado |
| S04-P02 | 01:40 | 01:45 | 5 | STILL | D | Marte con una tormenta de polvo avanzando |
| S04-P03 | 01:45 | 01:50 | 5 | STILL | D | Casquete polar de Marte y nubes finas de vapor |
| S04-P04 | 01:50 | 01:55 | 5 | STILL | K | El Polar Lander sobre el hielo del polo sur |
| S04-P05 | 01:55 | 02:05 | 10 | **VEO** | J | Despegue nocturno del Delta II |
| S04-P06 | 02:05 | 02:10 | 5 | GFX | — | Trayectoria Type 2: arco de más de 180° alrededor del Sol |
| S05-P01 | 02:10 | 02:15 | 5 | STILL | B | La nave a contraluz, el panel recortado contra el Sol |
| S05-P02 | 02:15 | 02:25 | 10 | **VEO** | C | La rueda de reacción girando a alta velocidad |
| S05-P03 | 02:25 | 02:30 | 5 | STILL | C | Detalle macro de la rueda montada en su soporte |
| S05-P04 | 02:30 | 02:40 | 10 | **VEO** | C | El propulsor disparando pulsos secos |
| S05-P05 | 02:40 | 02:45 | 5 | GFX | — | Contador de desaturaciones acumulándose |
| S05-P06 | 02:45 | 02:50 | 5 | STILL | C | Primerísimo plano de la boquilla del propulsor |
| S06-P01 | 02:50 | 02:55 | 5 | STILL | H | La antena de la Deep Space Network de noche |
| S06-P02 | 02:55 | 03:05 | 10 | **VEO** | B | Dos naves superpuestas que se separan: la real y la calculada |
| S06-P03 | 03:05 | 03:10 | 5 | GFX | — | `lbf·s` — la unidad que escribía el archivo |
| S06-P04 | 03:10 | 03:15 | 5 | GFX | — | `N·s` y la flecha `× 4,45` — la unidad que leía navegación |
| S06-P05 | 03:15 | 03:20 | 5 | STILL | E | Pantalla CRT con columnas de datos corriendo |
| S06-P06 | 03:20 | 03:25 | 5 | GFX | — | El 10 se transforma en 44,5 |
| S06-P07 | 03:25 | 03:30 | 5 | STILL | E | Impresora matricial escupiendo papel continuo |
| S07-P01 | 03:30 | 03:35 | 5 | GFX | — | Una flecha diminuta que no logra desviar una trayectoria larga |
| S07-P02 | 03:35 | 03:40 | 5 | STILL | B | La nave de perfil: la asimetría del panel |
| S07-P03 | 03:40 | 03:50 | 10 | **VEO** | B | La nave rota y el Sol barre el panel de punta a punta |
| S07-P04 | 03:50 | 03:55 | 5 | STILL | E | Documento de decisión con firma, cenital |
| S07-P05 | 03:55 | 04:00 | 5 | STILL | E | Dos ingenieros discutiendo un plano técnico |
| S07-P06 | 04:00 | 04:05 | 5 | GFX | — | Dos barras: «esperado» se detiene, «real» sigue subiendo · × 10–14 |
| S07-P07 | 04:05 | 04:10 | 5 | STILL | N | Pasillo de oficinas con las luces apagándose |
| S08-P01 | 04:10 | 04:15 | 5 | GFX | — | Cientos de flechas diminutas que se agrupan en una sola |
| S08-P02 | 04:15 | 04:20 | 5 | STILL | F | Calendario de pared con los meses tachados |
| S08-P03 | 04:20 | 04:25 | 5 | STILL | F | El navegador solo frente a tres monitores |
| S08-P04 | 04:25 | 04:30 | 5 | STILL | F | Primer plano parcial de un rostro cansado |
| S08-P05 | 04:30 | 04:35 | 5 | STILL | F | Listado impreso con una línea marcada en birome |
| S09-P01 | 04:35 | 04:40 | 5 | STILL | F | El navegador recostado, mirando el techo |
| S09-P02 | 04:40 | 04:50 | 10 | **VEO** | B | La cámara viaja por la línea entre la Tierra y la nave |
| S09-P03 | 04:50 | 04:55 | 5 | GFX | — | Doppler: la componente radial se ilumina, la perpendicular se apaga |
| S09-P04 | 04:55 | 05:00 | 5 | STILL | D | Marte llenando el cuadro, el terminador en diagonal |

### Verificación

| | |
|---|---|
| Último OUT | **05:00** ✓ |
| Planos | **50** = 10 VEO + 28 DepthFlow + 12 GFX |
| Duraciones fuera de grilla | **0** — todas son 5 o 10 |
| `10×10 + 40×5` | `100 + 200 = 300` ✓ |
| Dos VEO seguidos al arranque | no ✓ |

---

## Dónde está cada cosa

| Capa | Archivo |
|---|---|
| Imágenes semilla + prompts de Veo | [PROMPTS-01-IMAGENES-PARA-VEO.md](PROMPTS-01-IMAGENES-PARA-VEO.md) |
| Imágenes para animar + los 12 gráficos | [PROMPTS-02-IMAGENES-PARA-MOVIMIENTO.md](PROMPTS-02-IMAGENES-PARA-MOVIMIENTO.md) |
| Ambientes, música y efectos | [PROMPTS-03-SONIDO.md](PROMPTS-03-SONIDO.md) |
| Las 60 tomas de voz | [PROMPTS-04-VOZ.md](PROMPTS-04-VOZ.md) |

---

## Precisiones que el guion respeta

Es lo que va a diferenciar este video en los comentarios:

1. **No son «libras por segundo».** Es libra-fuerza-segundo, `lbf·s`.
2. **La nave no funcionaba en imperial.** El cómputo a bordo era métrico y correcto. El error
   estaba en software **en Tierra**.
3. **No se le enviaron órdenes equivocadas.** La nave ejecutó todo bien; lo que estaba mal era la
   reconstrucción terrestre de dónde estaba.
4. **«Faster, Better, Cheaper» no es la causa raíz** según el informe oficial.
5. **El coste de 125 millones es una cifra floja.** No aparece en el guion. La defendible es la del
   press kit: 235,9 M USD para MCO + Polar Lander juntos.
6. **Nadie vio la destrucción.** El informe original deja abierto que la nave atravesara la
   atmósfera y saliera, ya inutilizada.

---

## Qué queda para 5:00 – 8:00

Sobre la misma grilla: **5 VEO + 26 planos de 5 s = 180 s**.

| Sec | Tema |
|---|---|
| S10 | El equipo de navegación no era el que construyó la nave |
| S11 | TCM-4 y la última semana: el periapsis cae de 226 a 150 km |
| S12 | **TCM-5**: la maniobra que podía salvarla y por qué no se ejecutó |
| S13 | Una hora antes: 110 km. El motor enciende a las 09:00:46 |
| S14 | Los 21 minutos de espera. No vuelve |
| S15 | 29 de septiembre: aparece el 4,45. El paso real fue a 57 km |
