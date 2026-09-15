# INVERNADERO EN ÓRBITA — notas

11 de septiembre de 2026. Tercer loop ambiente, pedido junto con ESTANQUE DE KOI.
Mismo método y mismas lecciones que el koi. La única ventana da al espacio: la
Tierra girando, sin ciudad ni gente posible detrás.

## Dibujos

13 a la primera; se rehizo sólo O05, que vino con barras de letterbox gris
oscuro (luminancia 35) que el detector con umbral 12 no atrapó. De ahí el nuevo
criterio del detector: franja oscura Y uniforme (desvío ≤ 2).

## Estado

- [x] proyecto sin avisos, 12 planos O01-O12, 62,0 s
- [x] 13 PNG revisados, 0 barras
- [x] `lofi-orbita-para-vast.zip` (21,4 MB)
- [x] máquina: la misma instancia del koi (50952409), en cadena; destruida el 13/9 al terminar
- [x] generar: tres tandas (12 + 4 + 3); quedan O01 (t3), O03 (t2) y O05 fuera → 11 planos
- [x] `bucle.py`: «INVERNADERO EN ORBITA - loop.mp4» 55,0 s, −14,0 LUFS, empalme O12→O01 (qc/empalme.png)
- [ ] música del usuario: `bucle.py --musica <pista> --repite 10`

## Corrida (13/9/2026, instancia 50952409, la misma del koi)

Tanda 1: 12/12 sin fallos de máquina, 0,77 min/s, 0 reintentos. QC con tiras:

| clip | tanda 1 | tanda 2 | tanda 3 |
|---|---|---|---|
| O01 | ✗ luz magenta → blanca, destello | ✗ globos de luz flotando | sin motas, sólo la Tierra gira |
| O02 | ✓ | | |
| O03 | ✗ la luz se apaga a la mitad | ✗ cambia de tono | sólo la gota flota |
| O04 | ✓ | | |
| O05 | ✗ el ojo de buey se vuelve escotilla (mi texto decía «hatch») | ✗ se apaga progresivamente | sólo la Tierra gira |
| O06 | ✗ deriva de color | ✓ | |
| O07 | ✓ (la gota creció de más, coherente) | | |
| O08-O12 | ✓ | | |

**La lección del invernadero:** la iluminación artificial (luz de cultivo
magenta) es inestable para H3 en 5 s: vira de color, se apaga, o si se piden
«motas de polvo flotando» fabrica globos de luz. Declararla constante ayudó a
medias; lo que funciona es pedir UN solo movimiento y decir que todo lo demás,
luces incluidas, es una pintura quieta. Y nunca un texto de movimiento que
contradiga el dibujo (O05).

Tanda 3 (movimiento mínimo, sin motas): O01 vira rosa→amarillo en 1,5 s y se queda (se acepta), O03 chispas doradas (se usa la tanda 2), O05 se apaga otra vez (fuera). Si se rehace este video, los planos abiertos con luz de cultivo se dibujan con luz blanca neutra, no magenta.

## Gasto

Instancia 50952409, 71 min a $2,27/h: **$2,68** por los dos videos (koi + invernadero, 12 + 19 clips). Más ~$1,20 de imágenes (30 dibujos). Los tres intentos fallidos con hosts desverificadas quedan aparte (trampa 16).
