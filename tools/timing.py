"""
Calcula los timecodes de cada toma de voz a partir del guion y la tasa medida
de la voz elegida. Emite la tabla markdown de la Capa D.

Por qué existe: la tasa de lectura depende de la voz Y del modo de stability
(Creative es ~15% más lento que Natural). Calcular 52 timecodes a mano contra
dos tasas distintas es una fuente de errores garantizada. Si cambiás de voz,
actualizás RATES y volvés a correr esto.

    python tools/timing.py            # imprime las tablas
    python tools/timing.py --check    # solo la verificación de cierre

Medición: generá un bloque, medí el MP3 y actualizá RATES.
"""

import argparse
import re
import sys


def nwords(text: str) -> int:
    """Cuenta palabras ignorando los tags de actuación [asi], que no se pronuncian."""
    return len(re.sub(r"\[[^\]]*\]", " ", text).split())

# palabras por segundo, medidas con la voz elegida
VOICE = "Sandmor (NNyuU2PGU4uwmrHysPYW)"
# Medidas sobre las 59 tomas reales de Sandmor (no sobre textos continuos:
# medir un bloque entero infla la cifra porque incluye las pausas de párrafo,
# que en este pipeline son huecos entre tomas, no audio).
# A nivel BLOQUE el error es ±5 %. A nivel TOMA llega a ±30 % — por eso existe
# retime.py, que recalcula los IN contra la duración real de cada MP3.
RATES = {
    "natural": 2.57,   # agregado real: 636 palabras / 247,4 s = 154,2 wpm
    "creative": 2.57,  # stability 0.0 NO es más lento; la diferencia era un artefacto
    "numeros": 2.60,   # texto cargado de cifras — medido sobre S01
}
DENSITY = 0.85  # fracción del bloque que es voz; el resto es silencio estructural

# (id, duración, modo, [(peso_de_pausa_previa, texto), ...])
# peso 0 = arranca en el IN del bloque. Pesos mayores = pausas más largas.

BLOCKS = [
    ("S01", 35, "numeros", [
        (0, "Veintitrés de septiembre de mil novecientos noventa y nueve. Nueve horas, cuatro minutos, cincuenta y dos segundos."),
        (3, "En el control de la misión, una señal que llega desde Marte se apaga."),
        (1, "No estaba previsto que se apagara todavía. Faltaban cuarenta y nueve segundos."),
        (1, "Nadie en esa sala entiende todavía qué acaba de pasar."),
        (1, "Veintiún minutos después tenía que reaparecer del otro lado de Marte."),
        (2, "[somber] No reapareció."),
        (2, "Nadie lo sabe aún, pero esa nave llevaba nueve meses viajando hacia un número equivocado."),
    ]),
    ("S02", 30, "creative", [
        (0, "Seguro escuchaste la explicación."),
        (1, "La NASA perdió una sonda porque unos usaban métrico y otros imperial."),
        (1, "Metros contra pies. Un error de colegio, en la mejor agencia espacial del mundo."),
        (1, "Es la anécdota perfecta. Se cuenta en cada clase de ingeniería del mundo."),
        (2, "Esa versión es cierta."),
        (3, "Y es la parte menos interesante."),
        (1, "Porque ese error no derribó al Mars Climate Orbiter."),
        (1, "[serious] Lo que lo derribó fue todo lo que no lo detuvo."),
    ]),
    ("S03", 30, "natural", [
        (0, "La investigación oficial de la NASA no encontró una causa. Encontró nueve."),
        (1, "Una causa raíz, y ocho fallos que contribuyeron."),
        (1, "Y encontró algo peor: existía una maniobra de emergencia que podía haber salvado la nave."),
        (2, "Estaba disponible. Se discutió. No se ejecutó."),
        (1, "Nadie entendió del todo que hacía falta."),
        (2, "Pero para entender cómo se llega ahí, hay que empezar por el principio."),
    ]),
    ("S04", 35, "natural", [
        (0, "El Mars Climate Orbiter era un satélite meteorológico. Pero para otro planeta."),
        (1, "[curious] Iba a vigilar el clima de Marte: las tormentas de polvo, el vapor de agua, las estaciones."),
        (1, "Y tenía un segundo trabajo: servir de antena repetidora para el Mars Polar Lander."),
        (1, "Despegó el once de diciembre de mil novecientos noventa y ocho, desde Cabo Cañaveral."),
        (1, "Por delante: seiscientos sesenta y nueve millones de kilómetros."),
        (1, "Nueve meses y medio de viaje."),
    ]),
    ("S05", 40, "natural", [
        (0, "Una nave en el espacio tiene que controlar hacia dónde apunta."),
        (1, "El Mars Climate Orbiter lo hacía con ruedas de reacción: volantes internos que giran y hacen rotar la nave sin gastar combustible."),
        (1, "El problema es que esas ruedas se saturan. Se llenan de giro y dejan de servir."),
        (1, "Y hay que descargarlas."),
        (1, "Para descargarlas, la nave encendía unos propulsores pequeñitos durante un instante. En la NASA lo llamaban desaturación de momento angular."),
        (2, "Cada uno de esos disparos empujaba la nave un poquito. Un empujón mínimo, casi ridículo. Milésimas."),
        (3, "[serious] Casi."),
    ]),
    ("S06", 40, "natural", [
        (0, "Cada vez que pasaba, los datos viajaban a la Tierra."),
        (1, "Y en la Tierra, un programa llamado Small Forces calculaba cuánto había empujado ese disparo y lo guardaba en un archivo."),
        (1, "Navegación leía ese archivo."),
        (1, "El archivo escribía los números en libra-fuerza-segundo."),
        (1, "Navegación los leía como newton-segundo."),
        (2, "No es lo mismo. Una libra-fuerza son cuatro coma cuarenta y cinco newtons."),
        (1, "Donde el archivo decía diez, la realidad decía cuarenta y cuatro con cinco."),
        (1, "Cada vez. Durante nueve meses."),
    ]),
    ("S07", 40, "natural", [
        (0, "Y acá está la verdadera trampa."),
        (1, "Un solo disparo mal calculado no habría movido nada."),
        (1, "Pero el Mars Climate Orbiter tenía un panel solar enorme montado de un solo lado, y el Sol empujaba contra él sin parar."),
        (1, "Había un plan para compensarlo: girar la nave entera cada día. Lo llamaban modo barbacoa. Se canceló."),
        (2, "[serious] Nadie le avisó a navegación."),
        (1, "Ni una nota, ni un correo, ni una reunión."),
        (2, "Las desaturaciones terminaron ocurriendo entre diez y catorce veces más seguido de lo que navegación esperaba."),
    ]),
    ("S08", 25, "creative", [
        (0, "Miles de disparos. Miles de errores diminutos. Todos en la misma dirección, todos hacia abajo."),
        (1, "Y durante meses, nadie los vio."),
        (1, "[whispers] Aunque casi."),
        (1, "En abril del noventa y nueve, cinco meses antes del desastre, navegación notó que los datos no cuadraban."),
        (1, "Que las perturbaciones eran bastante más grandes de lo que decían los archivos."),
    ]),
    ("S09", 25, "natural", [
        (0, "Lo investigaron. No encontraron por qué."),
        (1, "Y había un motivo casi cruel para eso."),
        (1, "El empujón acumulado apuntaba casi perpendicular a la línea entre la Tierra y la nave. Justo la dirección que el radar Doppler peor mide."),
        (1, "Podían ver que algo empujaba. No podían ver cuánto."),
        (1, "Y eso los estaba bajando."),
        (2, "[somber] El error estaba a la vista. Y era invisible."),
    ]),
]


def tc(seconds: float) -> str:
    return f"{int(seconds)//60:02d}:{seconds % 60:04.1f}".replace(".", ",")


def compute():
    out, cursor, totals = [], 0.0, {"voice": 0.0, "words": 0, "takes": 0}
    for bid, dur, mode, takes in BLOCKS:
        rate = RATES[mode]
        durs = [nwords(t) / rate for _, t in takes]
        voice = sum(durs)
        weights = sum(w for w, _ in takes) + 1  # +1 = cola al final del bloque
        slack = dur - voice
        unit = slack / weights if weights else 0.0

        rows, t = [], cursor
        for (w, text), d in zip(takes, durs):
            t += w * unit
            rows.append((tc(t), text, nwords(text), d))
            t += d
        tail = cursor + dur - t

        out.append({"id": bid, "dur": dur, "mode": mode, "rate": rate,
                    "rows": rows, "voice": voice, "slack": slack, "tail": tail})
        totals["voice"] += voice
        totals["words"] += sum(r[2] for r in rows)
        totals["takes"] += len(rows)
        cursor += dur
    return out, cursor, totals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", help="escribe la salida a un archivo UTF-8")
    args = ap.parse_args()
    if args.out:
        sys.stdout = open(args.out, "w", encoding="utf-8")
    blocks, total, totals = compute()

    if not args.check:
        for b in blocks:
            print(f"\n### BLOQUE {b['id']} · {b['dur']} s · "
                  f"stability {'0.0 Creative' if b['mode']=='creative' else '0.5 Natural'} "
                  f"· {b['rate']} pal/s")
            print("\n| Toma | IN | Texto | Pal. | Prev. | Real |")
            print("|---|---|---|---|---|---|")
            for i, (t, text, w, d) in enumerate(b["rows"], 1):
                print(f"| T{i} | {t} | {text} | {w} | {d:.1f} s | |")
            print(f"\n**Voz {b['voice']:.1f} s / {b['dur']} s = "
                  f"{b['voice']/b['dur']*100:.0f} %** · cola de silencio {b['tail']:.1f} s")

    print("\n" + "=" * 60)
    print(f"Voz: {VOICE}")
    print(f"Bloques: {len(blocks)} · Tomas: {totals['takes']} · Palabras: {totals['words']}")
    print(f"Duración total: {total:.0f} s (objetivo 300)"
          f"  {'OK' if abs(total-300) < 0.01 else 'ERROR'}")
    print(f"Voz efectiva: {totals['voice']:.1f} s = {totals['voice']/total*100:.1f} % "
          f"(objetivo {DENSITY*100:.0f} %)")
    print(f"Silencio estructural: {total - totals['voice']:.1f} s")
    bad = [b['id'] for b in blocks if b['slack'] < 0]
    print(f"Bloques que no entran: {bad or 'ninguno'}")
    print(f"Caracteres facturables: ~{sum(len(t) for _,_,_,tk in BLOCKS for _,t in tk)}")


if __name__ == "__main__":
    main()
