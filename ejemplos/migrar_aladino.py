"""Convierte el Aladino de `Proyecto_Aladino/armar_planos.py` a un proyecto.json.

Se corre una vez. Existe para no reescribir a mano 42 planos que ya estaban
bien, y para dejar el ejemplo del formato largo apoyado en material real y no
inventado.

    python ejemplos/migrar_aladino.py
"""
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
VIEJO = RAIZ / "Proyecto_Aladino"
DESTINO = pathlib.Path(__file__).resolve().parent / "aladino"

sys.path.insert(0, str(VIEJO))
import armar_planos as ap  # noqa: E402


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)

    planos = []
    for esc, seg, tam, loc, pers, ve, mov, aud, dia in ap.PLANOS:
        p = {"escena": esc, "segundos": seg, "tipo": tam, "loc": loc,
             "personajes": list(pers), "ve": ve, "mueve": mov, "audio": aud}
        if dia:
            p["dialogo"] = dia
        planos.append(p)

    # Los assets madre salen de los tres planes que ya existían: las hojas de
    # personaje (p_*), las hojas de modelo con las cuatro vistas (m_*) y las
    # locaciones sin gente (l_*). Se generan una vez y son la referencia de
    # todos los fotogramas.
    madre = []
    for archivo in ("assets.json", "modelos.json"):
        d = json.loads((VIEJO / archivo).read_text(encoding="utf-8"))
        madre += d["assets"]

    doc = {
        "titulo": "Aladino y la lámpara maravillosa",
        "slug": "aladino",
        "formato": "largo",
        "estructura": "largo",
        "duracion_objetivo": round(sum(ap.encajar(p["segundos"])[1] for p in planos), 1),
        "_nota": ("Migrado de Proyecto_Aladino/armar_planos.py, que produjo los 42 planos "
                  "de la primera corrida. Es el ejemplo del formato largo: 16:9, diálogo "
                  "dentro del plano, personajes con hoja de modelo."),
        "medio": "2D animated film",
        "estilo_imagen": ap.ESTILO,
        "refs_estilo": [
            "../../Imagenes de referencia/Princesa.png",
            "../../Imagenes de referencia/Palacio.png",
        ],
        "personajes": {k: {"hoja": v[0], "descripcion": v[1]} for k, v in ap.PERS.items()},
        "locaciones": {k: {"imagen": v[0], "descripcion": v[1]} for k, v in ap.LOC.items()},
        "madre": madre,
        "planos": planos,
    }

    salida = DESTINO / "proyecto.json"
    salida.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{salida}  ·  {len(planos)} planos  ·  {doc['duracion_objetivo']:.0f} s")

    # Los dibujos ya generados se copian tal cual: son 42 PNG que costaron su
    # tiempo de API y no hay ninguna razón para rehacerlos.
    origen = VIEJO / "assets"
    destino_assets = DESTINO / "assets"
    if origen.is_dir():
        destino_assets.mkdir(exist_ok=True)
        n = 0
        for f in origen.glob("*.png"):
            destino = destino_assets / f.name
            if not destino.exists():
                destino.write_bytes(f.read_bytes())
                n += 1
        print(f"{n} dibujos copiados a {destino_assets} "
              f"({len(list(destino_assets.glob('*.png')))} en total)")


if __name__ == "__main__":
    main()
