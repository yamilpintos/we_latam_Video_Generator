# PROMPTS 03 — SONIDO

**Mars Climate Orbiter · 0:00 – 5:00**

Ambientes, música y efectos, en tres listas separadas. Todo se genera con ElevenLabs y se mezcla
localmente.

```bash
python tools/sfx_generate.py --all    # genera los archivos
python tools/mix.py                   # mezcla y masteriza
```

Fuente de los datos: [`tools/sfx_plan.py`](../tools/sfx_plan.py). El documento y el generador
leen de ahí, así que no pueden divergir.

---

# Las cuatro pistas

| Pista | Contenido | Nivel medido |
|---|---|---|
| **A1** | Voz | −16,0 LUFS |
| **A2** | Música, con ducking disparado por A1 | −30,6 LUFS |
| **A3** | Ambiente | −30,0 LUFS |
| **A4** | Efectos puntuales | −24,1 LUFS |

**Master:** −14,0 LUFS integrado · pico −1,0 dBFS · **ducking medido 6,0 dB** sobre la voz.

### El ambiente sigue la locación narrativa, no la del plano

Es la decisión que más cambia el resultado. El cold open alterna cada 5–10 segundos entre la sala
de control, el espacio y Marte. Si el ambiente cambiara en cada corte sonaría a diapositivas.
Pero esa secuencia **es una escena en la sala de control**: los planos espaciales son insertos.
Así que el room tone de la sala corre por debajo de los 65 segundos completos.

**Seis regiones de ambiente para 50 planos**, con cross-fade de 1,2 s en cada cambio. Y por
debajo de todo, un drone continuo que nunca se corta: es lo que evita que un cross-fade caiga
sobre silencio.

---

# A3 · AMBIENTES

Loops de 22 s que se repiten con cross-fade. No se cortan en cada plano.

| ID | IN | OUT | Nivel | Prompt |
|---|---|---|---|---|
| `DRONE_BASE` | 00:00,0 | 05:00,0 | -36 dB | drone subgrave continuo y casi inaudible, 45 hercios, sin melodía ni ritmo, textura de vacío, estable, sin variación |
| `AMB_SALA` | 00:00,0 | 01:05,0 | -28 dB | room tone de sala de control de misión en los años noventa: aire acondicionado constante, zumbido grave de muchos monitores de tubo, un teclado lejano, murmullo apagado, sin voces distinguibles |
| `AMB_REUNION` | 01:05,0 | 01:35,0 | -30 dB | room tone de sala de reuniones institucional cerrada: aire acondicionado suave, leve eco de espacio con moqueta, sin voces, sensación de encierro |
| `AMB_ESPACIO` | 01:35,0 | 02:50,0 | -32 dB | ambiente de vacío espacial: subgrave profundo y hueco con una resonancia metálica muy lejana, sin viento, sin aire, sensación de inmensidad y ausencia |
| `AMB_OFICINA` | 02:50,0 | 04:10,0 | -29 dB | room tone de oficina técnica de los años noventa durante el día: ventiladores de computadora, un fluorescente con zumbido leve, actividad lejana de papel, sin voces distinguibles |
| `AMB_NOCHE` | 04:10,0 | 04:35,0 | -32 dB | room tone de oficina vacía de madrugada: solo el aire acondicionado y un zumbido eléctrico muy tenue, silencio pesado, sensación de soledad |
| `AMB_FINAL` | 04:35,0 | 05:00,0 | -32 dB | ambiente de vacío espacial que se va abriendo: subgrave profundo con una cola de resonancia larga, sin ritmo, sensación de distancia infinita |

`DRONE_BASE` corre los 300 s por debajo de todo. Los otros seis se cruzan entre sí.


---

# A2 · MÚSICA

Un cue por bloque narrativo. Todos los prompts piden explícitamente *sin percusión* y
*deja aire para una voz en off*: sin eso la música pelea con la narración.

| ID | IN | OUT | Fade in/out | Nivel | Prompt |
|---|---|---|---|---|---|
| `MUS_01` | 00:02,0 | 01:05,0 | 3.0s / 3.5s | -26 dB | Documental cinematográfico, tono de misterio contenido. Drone grave en La menor con cello sostenido y un motivo simple de piano preparado que aparece cada tanto. Sin percusión, sin batería, sin melodía protagonista. Textura fría y espaciosa, deja aire para una voz en off. |
| `MUS_02` | 01:05,0 | 02:50,0 | 3.0s / 3.0s | -26 dB | Documental de investigación, tensión que crece muy despacio. Base de cuerdas graves sostenidas con un pulso rítmico sutil y regular que entra de a poco, como un reloj lejano. Capas que se van sumando sin llegar a clímax. Sin batería fuerte. Deja espacio en el medio para una voz. |
| `MUS_03` | 02:50,0 | 04:10,0 | 2.5s / 3.0s | -25 dB | Documental técnico, tensión sostenida e incómoda. Cuerdas en disonancia leve, un arpegio electrónico frío y repetitivo, pulso constante que no resuelve. Sensación de mecanismo funcionando mal. Sin percusión épica, sin coros. |
| `MUS_04` | 04:10,0 | 04:56,0 | 3.0s / 0.0s | -24 dB | Documental, cierre de acto con peso emocional. Cuerdas graves que crecen hacia un punto de máxima tensión y quedan suspendidas sin resolver. Un piano solo en las últimas notas. Sin percusión. Termina sin resolución armónica, dejando la frase abierta. |

**MUS_04 no tiene fade out.** Corta en seco a las 04:56, justo antes de «El error estaba
a la vista. Y era invisible». El silencio repentino hace que la frase pese el doble.


---

# A4 · EFECTOS PUNTUALES (46)

Densidad: **9.2 por minuto**. El ancla es el segundo exacto del ataque,
no el inicio del plano.

| ID | Ancla | Plano | Dur | Nivel | Prompt |
|---|---|---|---|---|---|
| `SFX_01` | 00:00,3 | S01-P01 | 3.0s | -24 dB | sala de control: teclas de un teclado mecánico de los noventa, pocas y espaciadas, lejanas |
| `SFX_02` | 00:03,2 | S01-P01 | 2.5s | -20 dB | zumbido eléctrico grave de un monitor de tubo que sube ligeramente de tono |
| `SFX_03` | 00:08,0 | S01-P02 | 3.0s | -16 dB | tono continuo de telemetría, señal electrónica limpia y estable, como un monitor cardíaco |
| `SFX_04` | 00:12,5 | S01-P02 | 1.4s | -12 dB | un tono electrónico continuo que se corta de golpe y deja un clic seco, luego nada |
| `SFX_05` | 00:15,2 | S01-P03 | 2.5s | -22 dB | sala grande con gente inmóvil: solo aire acondicionado y una silla de oficina que cruje una vez |
| `SFX_06` | 00:20,2 | S01-P04 | 2.5s | -20 dB | zumbido grave y hueco de estructura metálica en el vacío, muy tenue |
| `SFX_07` | 00:27,0 | S01-P04 | 1.6s | -14 dB | impacto sordo y grave, corto, con una cola de resonancia larga |
| `SFX_08` | 00:35,2 | S02-P01 | 1.6s | -18 dB | una hoja de periódico que se asienta sobre una mesa de fórmica |
| `SFX_09` | 00:40,2 | S02-P02 | 2.2s | -19 dB | dos piezas metálicas finas deslizándose una sobre otra, con dos clics de tope |
| `SFX_10` | 00:43,5 | S02-P02 | 0.9s | -14 dB | un clic metálico seco y desafinado, como una pieza que no encaja |
| `SFX_11` | 00:45,3 | S02-P03 | 2.6s | -18 dB | tiza escribiendo sobre un pizarrón, dos trazos cortos y firmes |
| `SFX_12` | 00:50,3 | S02-P04 | 2.0s | -21 dB | una puerta pesada que se cierra al final de un pasillo lejano, con eco |
| `SFX_13` | 00:53,9 | S02-P04 | 1.5s | -17 dB | un monitor de tubo que se apaga: el chasquido de desmagnetización y el zumbido que decae |
| `SFX_14` | 01:05,2 | S03-P01 | 1.4s | -17 dB | una carpeta gruesa de anillas que se apoya sobre una mesa de madera |
| `SFX_15` | 01:10,2 | S03-P02 | 4.2s | -18 dB | nueve clics electrónicos cortos y secos, espaciados de forma regular, tono de terminal |
| `SFX_16` | 01:25,2 | S03-P04 | 2.4s | -23 dB | murmullo de varias personas hablando bajo en una sala cerrada, que se apaga de golpe |
| `SFX_17` | 01:30,2 | S03-P05 | 3.0s | -20 dB | siseo constante de aire filtrado a presión en una sala limpia, muy estéril |
| `SFX_18` | 01:40,2 | S04-P02 | 3.5s | -21 dB | viento marciano lejano y enrarecido, muy tenue, con partículas de polvo fino |
| `SFX_19` | 01:45,2 | S04-P03 | 2.2s | -20 dB | hielo sucio crujiendo levemente por el frío, tics irregulares y secos |
| `SFX_20` | 01:50,0 | S04-P04 | 3.0s | -14 dB | ignición de un motor de cohete grande: el estallido inicial y el rugido que crece |
| `SFX_21` | 01:51,6 | S04-P04 | 7.5s | -10 dB | rugido masivo y grave de un cohete despegando, con crepitación de baja frecuencia |
| `SFX_22` | 01:59,6 | S04-P06 | 1.2s | -13 dB | un rugido enorme que se corta abruptamente y deja un silencio con presión en los oídos |
| `SFX_23` | 02:00,2 | S04-P05 | 2.8s | -19 dB | barrido electrónico ascendente que traza una línea, tono de instrumento científico |
| `SFX_24` | 02:15,1 | S05-P02 | 9.0s | -17 dB | zumbido agudo de un volante de inercia girando a alta velocidad, que sube de tono y se estabiliza |
| `SFX_25` | 02:25,2 | S05-P03 | 3.5s | -19 dB | el mismo zumbido de volante pero más cerca y apagado, con una vibración mecánica grave |
| `SFX_26` | 02:30,1 | S05-P04 | 9.0s | -13 dB | seis pulsos de gas comprimido muy cortos y secos, espaciados de forma irregular, en el vacío |
| `SFX_27` | 02:40,2 | S05-P05 | 3.2s | -20 dB | dos tonos electrónicos opuestos, uno ascendente y otro descendente, superpuestos |
| `SFX_28` | 02:45,2 | S05-P06 | 2.6s | -19 dB | metal caliente enfriándose: tics irregulares de contracción térmica |
| `SFX_29` | 02:50,2 | S06-P01 | 3.5s | -20 dB | servomotor pesado ajustando la posición de una antena grande, con viento de noche detrás |
| `SFX_30` | 03:05,1 | S06-P03 | 2.0s | -17 dB | tono de terminal antiguo que aparece con un cursor parpadeando |
| `SFX_31` | 03:10,1 | S06-P04 | 2.4s | -14 dB | un tono electrónico que salta bruscamente a otra altura, más agudo, con un clic entre medio |
| `SFX_32` | 03:15,2 | S06-P05 | 4.0s | -19 dB | datos corriendo en una pantalla de fósforo: clics rápidos y regulares de refresco |
| `SFX_33` | 03:20,1 | S06-P06 | 1.6s | -12 dB | impacto sordo y grave, corto, como un sello que cae sobre metal |
| `SFX_34` | 03:25,2 | S06-P07 | 4.2s | -15 dB | impresora matricial de los noventa imprimiendo en papel continuo, ruido característico |
| `SFX_35` | 03:35,1 | S07-P02 | 3.8s | -21 dB | siseo suave y continuo que crece muy despacio, como radiación o presión aumentando |
| `SFX_36` | 03:52,6 | S07-P04 | 1.1s | -11 dB | un sello de goma golpeando con fuerza sobre una hoja de papel apoyada en madera |
| `SFX_37` | 03:55,2 | S07-P05 | 3.0s | -22 dB | dos personas conversando en voz baja en una oficina, sin palabras distinguibles, y papel de plano que se mueve |
| `SFX_38` | 04:00,1 | S07-P06 | 4.0s | -18 dB | dos tonos electrónicos ascendentes: uno se detiene en seco, el otro sigue subiendo sin parar |
| `SFX_39` | 04:05,2 | S07-P07 | 3.4s | -17 dB | interruptores de luz fluorescente apagándose uno tras otro por un pasillo largo, con eco |
| `SFX_40` | 04:10,1 | S08-P01 | 4.5s | -18 dB | muchos clics diminutos que se van acumulando y densificando hasta formar una masa sonora |
| `SFX_41` | 04:15,2 | S08-P02 | 1.8s | -17 dB | un bolígrafo tachando con fuerza sobre papel, dos trazos cruzados |
| `SFX_42` | 04:20,2 | S08-P03 | 3.0s | -24 dB | oficina vacía de madrugada: solo el aire acondicionado y el segundero de un reloj de pared |
| `SFX_43` | 04:30,2 | S08-P05 | 2.0s | -19 dB | una hoja de papel continuo que se pasa y se alisa con la mano |
| `SFX_44` | 04:35,2 | S09-P01 | 1.8s | -18 dB | una silla de oficina que cruje al reclinarse hacia atrás |
| `SFX_45` | 04:50,1 | S09-P03 | 3.2s | -16 dB | un tono electrónico que se descompone en dos: uno se mantiene y el otro se desvanece |
| `SFX_46` | 04:55,0 | S09-P04 | 4.5s | -19 dB | subgrave que crece muy lentamente hacia el silencio, sin resolver |

---

# Momentos que dependen del sonido

| Timecode | Qué pasa |
|---|---|
| **00:12,5** | `SFX_04` — el tono de telemetría se corta en seco. Es la pérdida de la nave, y la voz no lo dice: lo dice el sonido |
| **01:50 – 02:00** | `SFX_20` + `SFX_21` — el despegue. El único momento con energía real de la primera mitad |
| **01:59,6** | `SFX_22` — el rugido se corta al pasar al espacio. El contraste hace el trabajo |
| **03:10,1** | `SFX_31` — el tono salta de altura justo cuando la voz dice «newton-segundo». Refuerza el gráfico `S06-P04` |
| **03:52,6** | `SFX_36` — el sello de goma cae sobre «Se canceló» |
| **04:56** | La música corta antes de «El error estaba a la vista. Y era invisible» |

---

# Verificación

```
ambientes   6 regiones + drone continuo · sin huecos
música      4 cues
efectos     46 · 9,2 por minuto
mezcla      300,0 s · -14,0 LUFS · pico -1,0 dBFS
ducking     6,0 dB medio sobre la voz
```

# Archivos

| Qué | Dónde |
|---|---|
| **Mezcla final** | `output/mars-climate-orbiter/audio/MIX_COMPLETO.wav` |
| Stems por pista | `audio/STEM_A1_voz.wav` … `STEM_A4_efectos.wav` |
| Fuentes | `audio/AMB_*.mp3`, `MUS_0*.mp3`, `SFX_*.mp3` |

Los stems sirven para rebalancear en el editor sin regenerar nada.
