# Formatos medidos — leer antes de tocar una estructura

2 de septiembre de 2026.

Este archivo existe para una sola cosa: **cuando haya que definir o corregir una
estructura de `h3pipeline/estructuras/`, mirar acá primero.** Son los números
que salieron de medir videos reales —ajenos y nuestros—, no de razonar sobre
cómo debería ser.

Los análisis completos están en `jcfdlw/ANALISIS.md` y
`nothingwasfilmed/ANALISIS.md`.

---

## La tabla que decide

| | @jcfdlw · recap | @nothingwasfilmed · reel | nosotros hoy |
|---|---|---|---|
| duración | 3-8 min (medido: 3:01) | **20,73 s** | 60 s / 4 min |
| planos | 77 | **9** | 12 / 41 |
| **corte medio** | **2,36 s** | **2,30 s** | **5,0 / 5,7 s** |
| voz | en off continua, **22,7 cps** | **diálogo en cámara**, 15 líneas | en off, 16,7 cps |
| subtítulos | quemados, frase por frase | ninguno | quemados |
| música | **ninguna** | pulso grave sutil | sí, con ducking |
| ambiente | ninguno (imagen muda) | sí, protagonista | sí |
| cuadro | 3:4 con barras negras | 9:16 a sangre | 9:16 a sangre |
| dato de éxito | 48.300 vistas | 64.233 me gusta | **ninguno: no publicamos** |

## Lo único que las dos referencias tienen en común

**Cortan cada 2,3 segundos.** Un recap melodramático de tres minutos con voz en
off y un microthriller de veinte segundos con diálogo no se parecen en nada, y
sin embargo cortan al mismo ritmo. Dos mediciones independientes del mismo
número: eso ya no es el estilo de un autor, es lo que la plataforma premia.

**Nosotros cortamos a 5,0-5,7 s.** Menos de la mitad de rápido.

Y no es un descuido: es que **H3 no genera menos de 5,17 s por clip**. Cortar a
su ritmo significa generar de más y tirar la diferencia:

| ritmo de corte | generado para 60 s de video | se tira |
|---|---|---|
| 5,7 s (el nuestro hoy) | ~63 s | 5 % |
| 2,3 s (el de ellos) | ~135 s | **56 %** |

O sea: **cortar como ellos cuesta el doble de GPU**. Es una decisión de plata,
no de gusto, y hay que tomarla a ojos abiertos. En la réplica de @jcfdlw se
pagó: 412 s generados para 181 de línea.

## Las tres preguntas abiertas

1. **¿El ritmo de 2,3 s vale el doble de GPU?** No lo sabemos porque **nunca
   publicamos nada**. Es el pendiente más viejo del proyecto y ninguna
   estructura deja de ser hipótesis hasta que se mida retención real.
2. **¿Cómo rinde H3 con caras actuando y hablando?** De esto depende si el
   formato `reel-20` es viable. La réplica de @jcfdlw lo contesta sin costo
   extra.
3. **¿Alcanza la densidad de voz?** Kate corre a 16,7 cps naturales; @jcfdlw
   escribe para 22,7. Medido en la réplica: hace falta comprimir 1,234× de
   media, y aun al tope duro de 1,30× la voz termina 6,6 s tarde sobre 181.
   O aceleramos, o escribimos menos texto.

## Qué implica para cada estructura

| estructura | qué dice hoy | qué habría que revisar |
|---|---|---|
| `short-23` | cortes de 1,5 a 6 s | ya está en el rango de ellos. Nada que cambiar |
| `short-60` | cortes de 1,5 a 7 s | los tramos largos (REVELACION 4,5-7 s) van al doble del ritmo medido |
| `short-90` | — | sin revisar contra estas mediciones |
| `recap-240` | cortes de 5 a 6,1 s | **es el que más se aparta**: 5-6,1 contra los 2,36 medidos en el canal que copia |
| `largo-narrativo` | cortes hasta 6,1 s | idem, sin revisar |
| `reel-20` | **no existe todavía** | 9 tramos con los cortes de `nothingwasfilmed/ANALISIS.md` |

El caso de `recap-240` es el más incómodo y conviene decirlo claro: **la
estructura se escribió para imitar a @jcfdlw y corta al doble de lento que
@jcfdlw.** No está mal por eso —el techo de 6,1 s existe por VRAM medida, no por
capricho— pero es un apartamiento deliberado y no un descuido, y hay que
tratarlo como tal cuando se revise.

## Reglas que valen para cualquier formato, ya medidas

- **El texto en pantalla va siempre como overlay en post**, nunca pedido al
  generador: los modelos de imagen y video lo destrozan.
- **H3 no baja de 5,17 s.** Cualquier corte más corto se paga generando de más.
- **5,9 s entra siempre; 6,6 casi siempre; 7,3 es apuesta** (regla 38).
- **El audio de H3 sale clipeado** (+2,68 dBFS medido): masterizar a -14 LUFS
  siempre.
- **Los dibujos se revisan con la GPU apagada.** En la réplica, 13 de 79 se
  rehicieron; ninguno de esos errores se habría visto sin mirar los PNG.
