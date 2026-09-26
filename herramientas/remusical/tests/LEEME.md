# Pruebas de ReMusical

**Ninguna gasta un peso.** No llaman a ElevenLabs, no alquilan una máquina en Vast, no
tocan Drive ni el bucket. Todo lo de afuera está reemplazado por dobles que hablan el
mismo dialecto que el servicio real. Se corren sin credenciales, en cualquier momento.

```
cd apps/remusical
python -m tests.correr_todo          # las 5, ~1 minuto
python -m tests.test_vast_falso      # una sola
```

| Prueba | Qué garantiza | Por qué existe |
|---|---|---|
| `test_vast_falso` | Levanta un Vast **falso** y verifica que el módulo elige la oferta **verificada** más barata (no la barata sin verificar, no la *deverified*), y que **destruye la máquina** al terminar, si no arranca, al pasar el tope, y con el botón de pánico. | Un modelo que queda corriendo cobra cada segundo. Esto ya fundió créditos una vez. |
| `test_selector_tandas` | El selector de la web: `/config` dice qué falta, `/preparar` lista episodios con el precio real del momento, la estimación es la fórmula medida, `/crear` lanza **sólo los episodios marcados** y los **topes de gasto llegan intactos**, `/cancelar` destruye la instancia. 18 comprobaciones. | Nada se lanza sin que el costo esté a la vista y los topes viajen enteros. |
| `test_drive_bucket` | La máquina baja de Drive con la **cuenta de servicio** (no el token del usuario), sube por **URL firmada** sin ninguna credencial, marca los archivos > 5 GB en vez de perderlos, y borra el video de la máquina al terminar. | Es el contrato de seguridad completo del camino Drive → Vast → bucket. |
| `test_takes_bajo_demanda` | Se genera **un** take; sólo se pide otro si el primero se descalifica o queda lejos de la original. | Bajó el costo por pieza un 21 % (medido). Si se rompe, se triplica la factura en silencio. |
| `test_guardas_replicate` | Las 8 guardas de gasto del camino Replicate. | Replicate está **parado**, pero el código sigue en el repo y se prueba igual. |

## Cómo están hechas

Cada prueba es un script con `check(condición, mensaje)` que imprime `OK`/`FALLA` y
termina con código 1 si algo falló. Sin framework, a propósito: se leen de arriba a
abajo y el mensaje de cada `check` dice qué se esperaba y qué salió.

Los dobles (`VastFalso`, `DriveFalso`, el Replicate falso) devuelven **la forma exacta de
los datos del servicio real**. Eso importa: `test_vast_falso` pasó durante días con un
falso que devolvía `verified: true` mientras la API real devuelve `verification: "verified"`.
El parser leía la clave equivocada y nunca hubiera encontrado una máquina. **Si un
doble miente sobre la forma de los datos, la prueba no guarda nada.** Cuando cambies un
doble, verificá la forma contra el servicio real primero.

## Trampa conocida

`vast.time` es el módulo `time` global. Parchear `sleep` con un lambda que llama a
`time.sleep` recursa infinito. Guardar el original antes.

## Qué NO está probado

- Nada contra Vast, Drive ni R2 **reales**: no hay credenciales en el entorno de prueba.
  La primera tanda real es la prueba de integración.
- El motor de audio (`mapa`, `separar`, `montar`, `guardas`) no tiene pruebas unitarias:
  se validó contra los dos entregables medidos (ver `docs/ARQUITECTURA.md`). Correrlo
  necesita los modelos y una máquina con RAM.
