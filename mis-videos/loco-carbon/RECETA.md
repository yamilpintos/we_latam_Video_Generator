# Receta: una historia larga a lo @jcfdlw, de punta a punta

Escrita el 30 de agosto de 2026 sobre EL LOCO DEL CARBÓN, el primer video de
este género. Sirve para replicar cualquier historia de 3 a 8 minutos. El
análisis del canal de referencia está en `referencias/jcfdlw/ANALISIS.md`; la
ley del género, en `h3pipeline/estructuras/recap.json`.

## 0 · Antes de escribir: el género en una frase

Melodrama en primera persona, con nombre propio y números concretos, contado
por una voz que **no para nunca** y actúa los diálogos, con un cliffhanger cada
25-35 segundos y subtítulos quemados frase por frase. La imagen ilustra; la
historia carga.

## 1 · El guion primero (regla 40)

1. Elegir la emoción primaria: familia en peligro, injusticia y revancha,
   catástrofe, plata. Un protagonista con nombre, un escéptico que se burla.
2. Escribir la **primera frase**: qué hizo alguien, por qué es absurdo, y qué
   pasó después. Si esa frase no engancha sola, la historia no sirve.
3. Escribir la narración completa como historia lineal: ~41 líneas para 4
   minutos, una por plano, **a 14-16 caracteres por segundo** para la voz de
   Kate (16,7 cps medidos). Cada bloque de 30 s: problema → acción →
   consecuencia → algo queda abierto.
4. Diálogos con comillas latinas «» dentro de la narración; la misma voz los
   actúa por puntuación. Sin tags de v3 salvo un pico.
5. Números en todo: grados, pesos, días, personas. Nada que el espectador tenga
   que inferir.

## 2 · Los planos al servicio del guion

Cada plano ilustra su línea. `corta` = `segundos` − 0,5 (se usa casi todo el
clip). Alternar tamaños; caras en PM/PA, un PP sólo en los picos. Un `texto`
en pantalla por bloque con la cifra que escala. Declarar `interrupcion: true`
donde cambia la luz o el sonido de régimen (corte de luz, amanecer, tormenta).

```bash
python -m h3pipeline construir mis-videos/<slug>/proyecto.json   # 0 avisos o se corrige
```

## 3 · La voz, medida

```bash
python -m h3pipeline voz mis-videos/<slug>/proyecto.json --generar
```

Toda línea que pase de 1,15× se **reescribe entera** conservando el dato.
Nunca se recorta hasta dejarla críptica (lo que pasó en EL DRON DEL VOLCÁN).

## 4 · Los dibujos

Hojas de modelo de todos los personajes (vestuario descripto, se inyecta solo)
+ una imagen por locación + los ~41 fotogramas. Con nano banana (~$0,13 y ~2,5
min por imagen; OpenAI en alta sale $0,25 y pierde el 14 % del cuadro):

```bash
python -m h3pipeline frames mis-videos/<slug>/proyecto.json --madre --motor nanobanana
```

Se revisan **todos** los PNG antes de empaquetar: escala, continuidad con la
acción del plano (el gancho no puede estar ya enganchado si el plano es
engancharlo), identidad de los personajes. Los malos se borran y se
regeneran con el prompt corregido; `frames` saltea los que existen.

## 5 · Música

240 s de una pasada con `musica.componer(240, tono)`. El tono se describe por
función dramática, no por género.

## 6 · Empaquetar, generar, bajar, destruir

```bash
python -m h3pipeline empaquetar mis-videos/<slug>/proyecto.json
python -m h3pipeline alquilar   mis-videos/<slug>/proyecto.json --si --generar   # sólo 4×5090
python -m h3pipeline seguir     mis-videos/<slug>/proyecto.json <iid>
python -m h3pipeline bajar      mis-videos/<slug>/proyecto.json <iid>
python -m h3pipeline destruir   <iid> --si
```

Costo esperado de un video de 4 min: ~45 min de pared en 4×5090, ~$2-2,5 de
GPU con el overhead real (COSTOS-H3 §13), más ~$6,5 de imágenes en nano
banana. **~$9 el video.**

## 7 · El máster, con subtítulos quemados

```bash
python -m h3pipeline mezclar mis-videos/<slug>/proyecto.json mis-videos/<slug>/clips
```

Hace todo: corte, voz (la caché de `voz --generar`, sin volver a pagar),
música con ducking, máster a −14 LUFS, y el SRT de la voz en off con los
**tiempos medidos** quemado en el tercio inferior-medio. Sale
`<TÍTULO> - final.mp4` y una versión sin subtítulos al lado.

## Lo que todavía no está medido

- Cómo rinde H3 con **caras actuando** en plano medio. Es la apuesta del
  género y la regla 22 decía lo contrario. Este video lo va a decir.
- Si Kate a 16,7 cps alcanza la sensación de "voz que no para" o hace falta
  acelerar el audio 1,10× (dentro del tope de compresión de 1,15).
- La retención real. Hasta que no se publique, la estructura `recap` es una
  hipótesis calcada de un canal que funciona.
