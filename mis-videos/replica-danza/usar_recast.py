"""Pone los cuadros del reparto nuevo (recast/) como primeros fotogramas y las
hojas del reparto (reparto-nuevo/) como hojas de modelo.

    /c/Python314/python -X utf8 mis-videos/replica-danza/usar_recast.py

Los cuadros del original que estaban en assets/ pasan a assets-original/ (son la
versión «réplica exacta» del 15/9 y se vuelven a usar si hace falta). Si a una
toma le falta el recast (bloqueada por el filtro), se deja el cuadro del original
y se avisa: ahí los actores serán los originales.
"""
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import tomas as T  # noqa: E402

HOJAS = {"m_hannah": "hannah-1", "m_jack_camisa": "jack-1", "m_jack_abrigo": "jack-1",
         "m_luka": "luka-1", "m_wady": "wady-1", "m_matones": "matones-1", "m_pasajeros": "pasajero-1"}


def main():
    resp = AQUI / "assets-original"
    if not resp.exists():
        resp.mkdir()
        for f in (AQUI / "assets").glob("*.png"):
            shutil.copy(f, resp / f.name)
        print(f"respaldo de {len(list(resp.glob('*.png')))} cuadros del original en assets-original/")
    # Cuadros que ningún generador acepta: se usa el recast de otra toma del mismo
    # encuadre nuevo (T81 arranca del primer plano de T75; T77 reusa el clip de E74).
    SUSTITUTO = {"T81": "T75"}
    # Insertos sin cara: GPT alucinó composición en 3 de 8 (T09 puso a la chica
    # entera con las piernas mal, T26 metió la cara de Jack en el cerrojo, T72
    # cambió el hombro por el perfil). Sin identidad que reemplazar, va el cuadro
    # del original tal cual (16/9).
    ORIGINAL = {"T09", "T26", "T72", "T78", "T79"}   # T79: la cortina → GPT puso a Wady de frente (CLIP 0,61)
    faltan = []
    for t in T.TOMAS:
        k = f"T{t[0]}"
        src = AQUI / "recast-gpt" / f"sb_{SUSTITUTO.get(k, k)}.png"   # 15/9: todo con GPT
        if k in ORIGINAL:
            shutil.copy(resp / f"sb_{k}.png", AQUI / "assets" / f"sb_{k}.png")
            continue
        if src.exists():
            shutil.copy(src, AQUI / "assets" / f"sb_{k}.png")
        else:
            shutil.copy(resp / f"sb_{k}.png", AQUI / "assets" / f"sb_{k}.png")
            faltan.append(k)
    for hoja, rep in HOJAS.items():
        shutil.copy(AQUI / "reparto-nuevo" / f"{rep}.png", AQUI / "assets" / f"{hoja}.png")
    print(f"{len(T.TOMAS) - len(faltan)} cuadros del reparto nuevo · {len(HOJAS)} hojas"
          + (f" · SIN recast (quedan con actores originales): {' '.join(faltan)}" if faltan else ""))


if __name__ == "__main__":
    main()
