"""Pruebas del partidor de oraciones, que es la pieza que más se rompe.

    python test_guion.py
"""
import sys

from locucion import guion

CASOS = [
    ("El Sr. Gómez me lo explicó en 1998. Después me fui.", 2),
    ("Costó 3.14 pesos. Nada más.", 2),
    ("J. R. Tolkien lo escribió. En 1937.", 2),
    ("¿Vos qué harías? Yo me quedaba. Él no.", 3),
    ("Una sola oración sin punto final", 1),
    ("Dijo: «no vuelvo más». Y se fue.", 2),
    ("Fue en EE. UU. Volvió en mayo.", 2),
    ("La Dra. Ruiz llegó tarde. Pidió disculpas. Nadie dijo nada.", 3),
    ("Pará... no entiendo. ¿Qué pasó?", 2),
    ("Tres cosas: pan, sal, etc. Después vemos.", 2),
    ("¡Basta! Me voy. No vuelvo.", 3),
]


# Lo que el partidor NO resuelve, a propósito. Une de más en vez de cortar de
# más: una línea larga se sintetiza bien igual, mientras que una línea cortada
# al medio suena rota. Si alguna vez molesta, la salida es poner el corte a
# mano con un doble salto de línea (queda como párrafo aparte).
LIMITACIONES = [
    ("Llegó a las 9 a. m. Se fue temprano.", 1,
     "«a. m.» seguido de mayúscula: ambiguo hasta para una persona"),
]


def main() -> int:
    malas = 0
    for texto, esperado in CASOS:
        ls = guion.partir(texto)
        ok = len(ls) == esperado
        malas += not ok
        print(("ok  " if ok else "MAL "), f"{len(ls)}/{esperado}",
              "|", " ~ ".join(l.texto for l in ls))

    print("\nlimitaciones conocidas (une de más, a propósito):")
    for texto, esperado, por_que in LIMITACIONES:
        ls = guion.partir(texto)
        ok = len(ls) == esperado
        malas += not ok
        print(("  ok  " if ok else "  MAL "), f"{len(ls)}/{esperado}", "|", por_que)

    # párrafos
    t = "Primera oración. Segunda.\n\nOtro párrafo acá."
    ls = guion.partir(t)
    assert [l.parrafo for l in ls] == [0, 0, 1], [l.parrafo for l in ls]

    # la línea de tiempo respeta las pausas
    for l in ls:
        l.dur = 1.0
    ep = guion.anclar(ls, pausa_oracion=0.25, pausa_parrafo=0.7, arranque=0.4)
    assert ep.lineas[0].t == 0.4
    assert ep.lineas[1].t == 1.65          # 0,4 + 1 + 0,25
    assert ep.lineas[2].t == 3.35          # + 1 + 0,7 (cambia de párrafo)
    assert ep.total == 4.35
    assert "00:00:00,400 --> 00:00:01,400" in ep.srt()
    print(f"\n{len(CASOS) - malas}/{len(CASOS)} casos de corte · tiempos y srt ok")
    return 1 if malas else 0


if __name__ == "__main__":
    sys.exit(main())
