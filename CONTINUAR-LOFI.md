Estoy haciendo videos generados con IA. El proyecto está en
c:\Users\Yamil\Desktop\youtube proyect

Antes de tocar nada, entrá en contexto en este orden:

1. ESTADO-PROYECTO.md — el mapa del proyecto.
2. Tu memoria persistente — en especial `proximo-video-lofi-loop` (este
   pedido, con los datos que ya condicionan el diseño), `errores-de-proceso`
   y `replica-jcfdlw-corrida`. No repitas ninguno de esos errores.
3. h3pipeline/VAST.md — el flujo de alquiler y, al final de «El flujo que
   funciona», las NUEVE REGLAS de la corrida limpia (clips de 5,17 s, máquina
   por fiabilidad a dedo, QC en una pasada, nada vivo entre sesiones).
4. ESTRUCTURA-POR-CAPAS.pdf — cómo se arma un video por capas.
5. COSTOS-H3.md §12-13 — los números medidos para estimar.

## La tarea: un video de 1 minuto que loopee, para música lo-fi

Quiero un video de ~60 s que se pueda repetir en bucle sin que se note el
corte, para ponerle una música relajante estilo lo-fi y subirlo a un canal.
Sin voz en off, sin subtítulos: sólo imagen y música.

**Primero se discute, después se ejecuta.** No generes nada ni alquiles nada
hasta que cerremos juntos estos puntos:

1. Formato: 16:9 para YouTube (formato `largo`, 1344×768) o vertical.
2. La escena: un solo escenario que aguante 60 s de mirarlo (qué se ve, qué se
   mueve despacio: lluvia, vapor, luz, hojas, una persona de espaldas…).
   Proponeme tres opciones con el gancho visual de cada una.
3. La técnica de loop: cuántos clips de 5,17 s hacen falta, cómo se cierra el
   bucle (el último fotograma vuelve al primero + cross-fade, o encadenado), y
   qué riesgo tiene cada opción.
4. La música: ElevenLabs Music (`musica.componer`, duración exacta) o una
   pista mía. Cómo se loopea el audio junto con la imagen.
5. Estimación de costo con el overhead real, y una alternativa gratis para
   prototipar en local si vale la pena (Wan 2.1 1.3B Fun-InP en mi placa).
6. Qué canal y qué formato de publicación (1 video de 1 min, o el mismo loop
   extendido a 10-60 min para un stream de estudio).

## Cuando lo cerremos

Con mi OK explícito, y sólo entonces:
- `proyecto.json` → `construir` sin avisos → `frames --madre --motor
  nanobanana` → revisás TODOS los PNG → `empaquetar`.
- Me mostrás resumen y costo estimado y esperás mi confirmación para Vast.
- `alquilar` con id elegido por fiabilidad (nunca la más barata, nunca
  Shanghái, sólo 4×5090), `seguir` con `-X utf8 -u`, `bajar`, QC de los
  clips en UNA pasada, `destruir` en la misma sesión, y recién después el
  máster con el loop verificado (mirar el empalme).
- Me pasás el gasto total real al cerrar.
