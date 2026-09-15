# 07 — Ensamble final

Orden de montaje. Seguirlo importa: montar el video antes que el audio te obliga a rehacer todo.

---

## Orden obligatorio

**1. Colocar la voz primero.**
Arrastrá los bloques `VO_*` a la pista A1, cada uno en su `IN`. Es la regla de oro y la razón de
todo el pipeline: la voz es la referencia temporal.

**2. Verificar el desvío acumulado.**
Sumá las duraciones reales de los bloques y comparalas con las presupuestadas.
- Desvío total < 3 s → corregí distribuyendo el sobrante en los beats sin narración.
- Desvío total > 3 s → hay que recorrer los timecodes. Corregí de atrás para adelante.

**3. Montar el video contra la voz.**
Cada plano en su `IN`, con la duración declarada. Los clips de Veo se recortan al `IN offset`
indicado en la Capa C. **Silenciá el audio de todos los clips de Veo.**

**4. Ambientes.**
Un loop por locación, extendido a todo el rango, con cross-fades de 0.8–1.5 s en los cambios.

**5. Spot FX.**
Uno por uno, en su ancla exacta. Escuchá con la voz puesta: si un efecto pisa una palabra clave,
bajalo 4 dB o corrélo 0.2 s.

**6. Música y ducking.**
Los cues por acto, con sus fades. Sidechain de A2 contra A1.

**7. Mezcla y master.**
−14 LUFS integrado, true peak −1 dBTP.

---

## Transiciones entre planos

| Situación | Transición |
|---|---|
| Corte dentro de una secuencia | **Corte seco.** Es el 85 % de los casos. |
| Cambio de secuencia, misma locación | Corte seco + cambio de escala de plano |
| Cambio de locación | Fundido a negro de 0.4 s, o corte seco con whoosh |
| Salto temporal | Fundido a negro de 0.8–1.2 s |
| Clímax | Corte seco con impacto sonoro |

**No uses** disolvencias cruzadas por defecto entre planos generados: mezclan dos estilos y se ve
turbio. Y nada de transiciones "de plantilla" (giros, barridos, glitch): abaratan el resultado
al instante.

---

## Corrección de color

Lo que unifica un video hecho de 50 imágenes generadas por separado:

1. Un **LUT único** sobre toda la timeline (una capa de ajuste arriba de todo).
2. Un **grano de película** al 8–12 % sobre toda la timeline.
3. Una **viñeta suave** al 15 %.

Los tres se aplican globalmente, nunca plano por plano. Es lo que hace que 50 imágenes distintas
se lean como un solo video. Si un plano se sale demasiado de la paleta, corregilo individualmente
*antes* de la capa de ajuste.

---

## Checklist de salida

- [ ] Último frame cae exactamente en la duración del preset
- [ ] Sin huecos negros entre planos
- [ ] Audio de todos los clips de Veo silenciado
- [ ] Ningún spot FX pisa una palabra clave de la narración
- [ ] Ambientes con cross-fade, ninguno cortado en seco
- [ ] Ducking activo: la música baja cuando entra la voz
- [ ] LUT + grano + viñeta sobre toda la timeline
- [ ] Loudness: −14 LUFS integrado, −1 dBTP
- [ ] Ninguna imagen tiene texto, watermark o dedos de más
- [ ] El personaje principal se ve igual en el plano 1 y en el plano 50
- [ ] Export: 1920×1080, 24 fps, H.264, ~16 Mbps, AAC 320 kbps
