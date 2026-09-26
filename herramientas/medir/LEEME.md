# Medir un video con la misma vara

Las herramientas con las que se comparó «EL CAMIÓN DE MI PADRE», «LA SANGRE
ENCUENTRA EL CAMINO» y «LA PANADERÍA DE ELISA» contra los diez reels de
referencia de `mis-videos/referencia-fb/`. Todas corren con
`.venv-depthflow/Scripts/python` y usan OpenCV + ffmpeg; ninguna gasta API.

```bash
P=.venv-depthflow/Scripts/python

$P herramientas/medir/analizar_video.py <video.mp4> [salida.json]
# cortes, largo de cada plano, escala (cuán cerca está la cara), CUÁNTO SE
# MUEVE la imagen dentro del plano, y cuánto cambia el color entre planos.

$P herramientas/medir/encuadres.py <video.mp4> [más videos…]
# cuántos ENCUADRES distintos tiene y cuánto dura cada uno. Un corte entre dos
# imágenes casi iguales no cuenta: lo que importa es cuántas veces cambia de
# verdad lo que el espectador mira.

$P herramientas/medir/caras.py <carpeta de assets> <salida.jpg> [prefijo]
# recorta TODAS las caras de los dibujos y las pone en una tira, para ver de un
# vistazo cuánto deriva la identidad de un plano al otro.

$P herramientas/medir/muestreo.py <video.mp4> <prefijo> [seg] [cols] [filas]
# hoja de contacto por tiempo fijo, para mirar el video sin verlo entero.

$P herramientas/medir/contacto.py <medida.json> <video.mp4> <prefijo>
# hoja de contacto con UN cuadro por plano detectado.

$P herramientas/medir/junturas.py
# último cuadro de un clip contra el primero del siguiente, separando los que
# comparten dibujo de los que estrenan dibujo. (Tiene el proyecto fijo adentro:
# cambialo arriba.)
```

## Los números medidos, para comparar

| | s por encuadre | movimiento | palabras/min |
|---|---|---|---|
| Los diez reels de referencia | **43,9** | **4,13** | **151** |
| EL CAMIÓN DE MI PADRE (22/9) | 7,2 | 5,36 | 99 (narrado) |
| LA SANGRE ENCUENTRA EL CAMINO (22/9) | 35,6 | 2,15 | 135 |
| LA PANADERÍA DE ELISA (26/9) | 69,3 | **1,33** | — |

El usuario aceptó «LA SANGRE» («quedó increíble») y rechazó «LA PANADERÍA»
(«está como hablando a cámara, las conversaciones están lentísimas»). La
diferencia entre los dos no está en la identidad ni en la continuidad —las dos
mejoraron— sino en la columna del MOVIMIENTO, que se fue a la mitad.
