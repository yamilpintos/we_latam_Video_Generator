"""Prueba integral del módulo. No toca la red ni la GPU ni gasta un centavo.

    python -m h3pipeline.prueba

Comprueba tres cosas distintas:

  1. Que las constantes de H3 son las que son (la grilla de 17k+5, el rango
     entrenado) y que las dos estructuras cubren su duración sin huecos.
  2. Que los dos ejemplos **reproducen los videos que ya existen**: PROFUNDIDAD
     da 60,0 s con los mismos ocho tiempos de voz, y Aladino da 5:09.1 con sus
     42 planos. Si un cambio rompe eso, rompió el pipeline.
  3. Que la validación detecta lo que tiene que detectar — se le pasan casos
     malos a propósito.
"""
import json
import pathlib
import sys

from . import costos, grilla
from .estructura import Estructura
from .proyecto import Proyecto

RAIZ = pathlib.Path(__file__).resolve().parent.parent
fallos: list[str] = []


def chequeo(nombre, cond, detalle=""):
    print(f"  {'OK ' if cond else '!! '}{nombre}{'  ' + detalle if detalle else ''}")
    if not cond:
        fallos.append(nombre)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    print("== grilla")
    chequeo("mínimo 5.167 s", abs(grilla.MINIMO - 5.167) < 0.001, f"{grilla.MINIMO:.3f}")
    chequeo("máximo 15.083 s", abs(grilla.MAXIMO - 15.083) < 0.001, f"{grilla.MAXIMO:.3f}")
    chequeo("todo length = 17k+5", all((L - 5) % 17 == 0 for L, _ in grilla.GRILLA))

    print("\n== estructuras")
    TODAS = ("short-23", "short", "short-90", "largo")
    for n in TODAS:
        e = Estructura.cargar(n)
        chequeo(f"{n}: tramos sin huecos ni solapes",
                all(abs(a.hasta - b.desde) < 1e-6 for a, b in zip(e.tramos, e.tramos[1:])))
        chequeo(f"{n}: cubre hasta el final",
                abs(e.tramos[-1].hasta - e.duracion_objetivo) < 0.01)
    e = Estructura.cargar("largo").con_duracion(480)
    chequeo("largo se estira a 8 min", abs(e.tramos[-1].hasta - 480) < 0.5)

    # La ley de 2026: los umbrales de retención suben cuanto más corto es el
    # video, porque el algoritmo exige más finalización a menos compromiso.
    r = {n: Estructura.cargar(n).retencion_objetivo for n in TODAS}
    chequeo("toda estructura declara retención objetivo", all(r.values()), str(r))
    chequeo("el umbral baja al crecer la duración",
            r["short-23"] > r["short"] > r["short-90"],
            f"23s {r['short-23']:.0%} > 60s {r['short']:.0%} > 90s {r['short-90']:.0%}")
    chequeo("los shorts declaran plataforma",
            all(Estructura.cargar(n).plataformas for n in TODAS))
    # La ventana crítica es la misma sin importar la duración: 1-3 s.
    chequeo("los tres shorts abren con un gancho de 3 s como máximo",
            all(Estructura.cargar(n).tramos[0].corte_max <= 3.0
                for n in ("short-23", "short", "short-90")))
    chequeo("y el gancho rompe el patrón en los tres",
            all(Estructura.cargar(n).tramos[0].interrupcion
                for n in ("short-23", "short", "short-90")))
    chequeo("los tres piden texto en pantalla en el gancho (triple refuerzo)",
            all(Estructura.cargar(n).tramos[0].texto_pantalla
                for n in ("short-23", "short", "short-90")))
    chequeo("los tres cierran en bucle",
            all("bucle" in Estructura.cargar(n).tramos[-1].nombre.lower()
                or "cierre" in Estructura.cargar(n).tramos[-1].nombre.lower()
                for n in ("short-23", "short", "short-90")))

    print("\n== short: PROFUNDIDAD")
    p = Proyecto.cargar(RAIZ / "ejemplos/profundidad/proyecto.json")
    sb, doc = p.construir()
    planos = doc["planos"]
    lt = p.estructura_resuelta().linea_de_tiempo(planos)
    chequeo("dura 60,0 s exactos", abs(lt[-1][1] - 60.0) < 0.01, f"{lt[-1][1]}")
    chequeo("12 planos", len(planos) == 12)
    chequeo("vertical 768x1344", (doc["ancho"], doc["alto"]) == (768, 1344))
    chequeo("sin avisos", not p.validar(planos), "; ".join(p.validar(planos)))
    chequeo("todos en rango de H3", all(grilla.en_rango(x["length"]) for x in planos))
    chequeo("ningún usa excede lo generado",
            all(x["usa"][1] <= x["segundos"] + 1e-9 for x in planos))
    chequeo("cada tramo tiene plano",
            {x["tramo"] for x in planos} == {t.id for t in p.estructura_resuelta().tramos})
    chequeo("el objetivo del tramo entra al fotograma",
            "NARRATIVE INTENT" in sb["assets"][0]["prompt"])
    chequeo("ningún prompt de video pide voz",
            all("NO SPEECH" in x["prompt"] for x in planos))
    voz = [t for t, _, _ in p.guion_de_voz(planos)]
    chequeo("los ocho tiempos de voz del video original",
            voz == [0.4, 6.0, 14.5, 26.5, 33.0, 44.0, 49.5, 55.5], str(voz))

    print("\n== largo: Aladino")
    q = Proyecto.cargar(RAIZ / "ejemplos/aladino/proyecto.json")
    _sb2, doc2 = q.construir()
    pl2 = doc2["planos"]
    chequeo("42 planos", len(pl2) == 42)
    chequeo("dura 5:09.1", abs(sum(x["segundos"] for x in pl2) - 309.1) < 0.2)
    chequeo("apaisado 1344x768", (doc2["ancho"], doc2["alto"]) == (1344, 768))
    chequeo("sin usa: se usan enteros", not any(x.get("usa") for x in pl2))
    chequeo("castellano en todos los prompts",
            all("SPOKEN LANGUAGE: SPANISH" in x["prompt"] for x in pl2))
    chequeo("no-inventes en todos", all("DO NOT ADD ANYTHING" in x["prompt"] for x in pl2))
    chequeo("8 planos con diálogo", sum(1 for x in pl2 if x["dialogo"]) == 8)
    chequeo("vestuario inyectado donde hay gente",
            all("CHARACTERS, unchanged" in x["prompt"] for x in pl2 if x["personajes"]))
    n_humo = sum(1 for x in pl2 if "cartoon cumulus" in x["prompt"])
    chequeo("la regla del humo, sólo donde hace falta", 0 < n_humo < len(pl2), f"{n_humo} de 42")

    print("\n== costos")
    est = costos.estimar(pl2)
    # Contraste contra el rango que se calculó a mano en COSTOS-H3.md §11.
    chequeo("Aladino cae en el rango documentado (45-56 min)",
            45 <= est.minutos_pared <= 56, f"{est.minutos_pared:.0f} min")
    chequeo("y en el de costo ($1.44-$1.77)",
            1.40 <= est.costo_generacion <= 1.80, f"${est.costo_generacion:.2f}")
    chequeo("20 pasos cuesta 2.3x que 8",
            abs(costos.minutos_clip(10, 20) / costos.minutos_clip(10, 8) - 2.3) < 0.01)
    chequeo("un clip de 15 s cuesta ~1.8x uno de 10",
            1.7 < costos.minutos_clip(15.1) / costos.minutos_clip(10.1) < 1.9)

    print("\n== voz: densidad y emoción")
    from . import voz as V
    chequeo("los tags no cuentan como caracteres hablados",
            V.caracteres("[sighs] Hola") == len("Hola"))
    # Sacar un tag o un || deja huecos dobles; si no se colapsan, cada uno suma
    # un caracter fantasma al conteo.
    chequeo("el partidor || tampoco, y no deja espacios de más",
            V.caracteres("Una luz. || Ya la veo.") == len("Una luz. Ya la veo."))
    chequeo("sacar un tag no deja espacio doble",
            V.caracteres("[sighs] Mil anos.") == len("Mil anos."))
    chequeo("~17 cps es el centro", V.CPS_MIN < V.CPS < V.CPS_MAX)
    chequeo("estirar tolera menos que comprimir", V.MAX_LENTO < V.MAX_RAPIDO)
    # Sin boca en pantalla, quedarse corto no es un defecto: el silencio entre
    # líneas de voz en off es parte del guion.
    corta = "No era un contenedor."
    chequeo("en off, quedarse corto NO es defecto",
            V.Linea("x", corta, 6.5, tipo="off").veredicto == "entra")
    chequeo("con boca, quedarse corto SÍ lo es",
            V.Linea("x", corta, 6.5, tipo="boca").veredicto == "alargar")
    chequeo("una línea que no entra ni comprimiendo se detecta",
            V.Linea("x", "a" * 100, 2.0).veredicto == "acortar")
    chequeo("dos tags en una línea se avisan",
            any("se pelean" in a for a in V.Linea("x", "[sad][angry] Ya.", 3).avisos()))
    chequeo("un tag con intensidad media se avisa",
            any("timbre" in a for a in
                V.Linea("x", "[sad] Se fue para siempre y no vuelve.", 3,
                        intensidad=2).avisos()))
    chequeo("un texto que es sólo etiqueta se avisa (v3 lo rechaza con 400)",
            any("400" in a for a in V.Linea("x", "[sighs]", 3).avisos()))
    lp = p.lineas_de_voz(planos)
    chequeo("el short saca sus 8 líneas en off", len(lp) == 8 and
            all(x.tipo == "off" for x in lp))
    chequeo("y ninguna hay que reescribirla",
            all(x.veredicto == "entra" for x in lp))
    lq = q.lineas_de_voz(pl2)
    chequeo("el largo saca sus 8 diálogos con boca", len(lq) == 8 and
            all(x.tipo == "boca" for x in lq))
    # Coincide con lo medido a mano en el doblaje: 11 de 19 líneas por debajo.
    chequeo("y detecta que todas quedan cortas para su plano",
            all(x.veredicto == "alargar" for x in lq))

    print("\n== doblaje: isocronía")
    import tempfile
    import numpy as np
    from . import doblaje as DB

    def f0(x):
        """F0 por autocorrelación, en el rango de una voz humana."""
        x = x[:, 0] if x.ndim > 1 else x
        x = x - x.mean()
        c = np.correlate(x, x, "full")[len(x) - 1:]
        lo, hi = int(DB.SR / 400), int(DB.SR / 60)
        return DB.SR / (lo + int(np.argmax(c[lo:hi])))

    t = np.linspace(0, 3.0, int(DB.SR * 3.0), endpoint=False)
    señal = sum(np.sin(2 * np.pi * 120 * k * t) / k for k in (1, 2, 3, 4)).astype("float32")
    señal = np.stack([señal, señal], 1) * 0.3
    # El bug que hubo que corregir: deformar el eje de tiempo con interpolación
    # es varispeed — cambia el tono junto con la velocidad y el personaje suena
    # distinto en cada línea. La F0 pasaba de 102,8 a 120,6 Hz.
    with tempfile.TemporaryDirectory() as td:
        desvios, duraciones = [], []
        for factor in (0.87, 0.93, 1.08, 1.15, 1.30):
            obj = 3.0 / factor
            out = DB.estirar(señal, obj, pathlib.Path(td))
            desvios.append(abs(f0(out) - 120.0) / 120.0)
            duraciones.append(abs(len(out) / DB.SR - obj))
    chequeo("estirar NO mueve el tono", max(desvios) < 0.03,
            f"desvío máximo de F0 {max(desvios) * 100:.1f} %")
    chequeo("y da la duración pedida", max(duraciones) < 0.02)

    # Si la toma es más corta que la ventana no se estira a llenarla: lo que
    # falta se arregla en el texto, no en el audio.
    _a, f = DB.alinear(señal[:int(DB.SR * 2.0)], 3.0)
    chequeo("una toma corta no se estira más allá del tope",
            f >= 1.0 / V.MAX_LENTO - 1e-3, f"{f:.3f}×")
    # Cuando no entra en el presupuesto se comprime hasta el tope DURO, no el
    # suave: es preferible a pisar la línea siguiente.
    _a, f = DB.alinear(señal, 2.5)
    chequeo("una toma larga se comprime hasta el tope duro",
            f <= V.MAX_RAPIDO_DURO + 1e-9, f"{f:.3f}× (duro {V.MAX_RAPIDO_DURO})")

    # El corrimiento de boca extiende el primer tramo hacia atrás, no crea uno.
    v = DB.Ventana(10.0, 14.0, 3.5, [(10.0, 11.5), (12.5, 14.0)])
    v2 = DB.aplicar_pre(v, 0.70)
    chequeo("el corrimiento de boca extiende el primer tramo",
            len(v2.tramos) == 2 and abs(v2.tramos[0][0] - 9.30) < 1e-9
            and abs(v2.inicio - 9.30) < 1e-9)

    print("\n== la ley de retención 2026")
    ov = p.overlays(planos)
    chequeo("el gancho lleva texto en pantalla", ov and ov[0][0] == 0.0, str(ov[0][3]))
    chequeo("los overlays salen con su tiempo", len(ov) == 3)
    # Un corte NO cuenta como interrupción: si contara, con cortes cada 3-6 s la
    # regla no diría nada nunca.
    sin_marcas = [dict(x) for x in planos]
    for x in sin_marcas:
        x.pop("interrupcion", None)
    est_s = p.estructura_resuelta()
    solos = [a for a in est_s.validar(sin_marcas) if "interrupción" in a]
    chequeo("detecta un tramo largo sin romper el patrón", bool(solos),
            solos[0][:60] if solos else "")
    chequeo("y no avisa cuando sí lo rompe",
            not [a for a in est_s.validar(planos) if "interrupción" in a])
    # Sacar el texto del gancho tiene que disparar el aviso del triple refuerzo.
    sin_texto = [dict(x) for x in planos]
    for x in sin_texto:
        x.pop("texto", None)
    chequeo("detecta el gancho sin texto en pantalla",
            any("texto en pantalla" in a for a in est_s.validar(sin_texto)))

    print("\n== la validación detecta lo que tiene que detectar")
    malo = json.loads((RAIZ / "ejemplos/profundidad/proyecto.json").read_text(encoding="utf-8"))
    malo["planos"][0]["corta"] = 9.0        # un gancho de 9 s no es un gancho
    chequeo("gancho demasiado largo",
            any("HOOK" in a and "corta" in a for a in Proyecto.desde_dict(malo).validar()))
    malo2 = json.loads((RAIZ / "ejemplos/aladino/proyecto.json").read_text(encoding="utf-8"))
    malo2["planos"][7]["personajes"] = ["aladino", "mago"]
    chequeo("diálogo con dos personajes",
            any("una sola voz por plano" in a for a in Proyecto.desde_dict(malo2).validar()))

    print("\n" + ("TODO OK" if not fallos else f"{len(fallos)} FALLOS: {fallos}"))
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
