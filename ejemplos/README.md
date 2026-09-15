# Ejemplos

Los dos videos que ya existen, reescritos como definiciones de proyecto para
[`h3pipeline`](../h3pipeline/). Sirven de plantilla: se copia la carpeta, se
cambian estilo, reparto y planos, y el resto del pipeline es idéntico.

| | [`profundidad/`](profundidad/) | [`aladino/`](aladino/) |
|---|---|---|
| Formato | short · 9:16 · 768×1344 | largo · 16:9 · 1344×768 |
| Duración | 60,0 s | 5:09.1 |
| Planos | 12, se generan 74,8 s para usar 60 | 42, se usan enteros |
| Voz | 8 líneas en off, ElevenLabs | 8 diálogos dentro del plano |
| Personajes | ninguno declarado, un sujeto constante | 5 con hoja de modelo |
| Original | `Proyecto_Short/` | `Proyecto_Aladino/` |

Los dos reproducen el video existente **al décimo**: PROFUNDIDAD da los mismos
doce cortes y los mismos ocho tiempos de voz; Aladino, los mismos 42 planos y
5:09.1. Eso es lo que chequea `python -m h3pipeline.prueba`, y es lo que
detectaría si un cambio en el módulo rompiera algo.

## Probar sin gastar nada

```bash
python -m h3pipeline brief      ejemplos/profundidad/proyecto.json
python -m h3pipeline construir  ejemplos/profundidad/proyecto.json
python -m h3pipeline costo      ejemplos/profundidad/proyecto.json
python -m h3pipeline gpu        ejemplos/profundidad/proyecto.json
python -m h3pipeline voz        ejemplos/aladino/proyecto.json
```

El último es el paso de voz. En Aladino marca las **ocho líneas** por debajo de
11 caracteres por segundo: cada una llena la mitad de su plano, así que al
doblar sobra boca moviéndose sin voz. Es el mismo defecto que el doblaje
encontró después de generar, detectado antes de gastar nada.

Con `--generar` sintetiza de verdad (gasta créditos). El reparto de voces de
Aladino está declarado en su `proyecto.json`, pero **esos clones existen sólo en
la cuenta de `Foton/dubai_v2`**: con otra clave las cuatro dan "no disponible".

Los dibujos ya están en `assets/`, así que `frames` no gasta API: dice "ya
existe" y saltea. `empaquetar` arma el ZIP para subir.

## Un proyecto nuevo

```bash
cp -r ejemplos/profundidad mis-videos/mi-short
rm mis-videos/mi-short/assets/*.png
# editá proyecto.json: titulo, slug, estilo_imagen, sujeto y los planos
python -m h3pipeline brief mis-videos/mi-short/proyecto.json   # qué pide cada tramo
python -m h3pipeline construir mis-videos/mi-short/proyecto.json
python -m h3pipeline frames mis-videos/mi-short/proyecto.json  # acá sí gasta API
```

El `brief` es lo primero a propósito: dice qué tiene que pasar en cada tramo
antes de escribir un solo plano, y ese texto es lo que se le pasa a quien
escriba los planos —persona o LLM— para que los redacte contra la estructura.

## Nota sobre `migrar_aladino.py`

Convierte `Proyecto_Aladino/armar_planos.py` a `aladino/proyecto.json`. Se corrió
una vez; está guardado por trazabilidad, no hace falta volver a ejecutarlo.

Al migrar, el validador encontró algo real: **`l_palacio` y `p_princesa` existen
como PNG pero no están declarados en ningún plan de generación**, así que no hay
forma de rehacerlos si cambia el estilo. Por eso `aladino` muestra ese aviso: es
un dato, no un error del módulo.
