"""El paso entre guion cerrado y sintetizar: densidad y emoción.

Nada se sintetiza sin pasar por acá. Son dos cosas distintas y las dos se
resuelven **en el texto, no en el audio**:

    cuánto dura   los caracteres que entran en la ventana
    cómo se dice  el tag de entrega de eleven_v3

La regla que cuesta aceptar: **si la línea es corta para su hueco, se escribe
más texto; no se estira el audio.** Estirar tolera 1,08×; comprimir, 1,15×.
Regenerar es prácticamente gratis —las 19 líneas de una película de cinco
minutos suman ~500 caracteres— así que iterar el texto siempre sale más barato
que deformar el audio.

De dónde salen los números: el motor de doblaje de DubAI (`Foton/dubai_v2`), que
los midió en producción sobre cientos de líneas. Ver `ISOCRONIA.md` y
`VOZ-EMOCION-V3.md` en la raíz del proyecto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# El español hablado corre a ~17 caracteres por segundo. No es opinable: es lo
# que decide si una línea calza.
CPS = 17.0
CPS_MIN = 11.0        # por debajo, la voz termina y los labios siguen
CPS_MAX = 22.0        # por encima, no entra ni comprimiendo

# Topes de deformación del audio, mucho más chicos de lo que parece.
MAX_LENTO = 1.08      # ralentizar: "una voz aguda estirada más de 10 % suena
                      # masculina/pastosa aunque el pitch no cambie" (DubAI, con
                      # tres voces femeninas distintas en la misma escena)
MAX_RAPIDO = 1.15     # comprimir suave
MAX_RAPIDO_DURO = 1.30

# Aire dentro del plano: el personaje tarda en arrancar a hablar y conviene
# cerrar antes del corte. Son los mismos márgenes con que se escribe el SRT.
AIRE_ENTRADA = 0.4
AIRE_SALIDA = 0.3

# Tags de entrega de eleven_v3. NO los pronuncia: los actúa.
TAGS = {
    "whispers": "secreto, confidencia, miedo contenido",
    "sighs": "resignación, cansancio, antes de ceder",
    "yawns": "sueño, aburrimiento, despertar",
    "nervously": "mentira, incomodidad, súplica",
    "curious": "pregunta genuina, descubrimiento",
    "excited": "euforia, hallazgo, urgencia positiva",
    "surprised": "sorpresa real, no reacción menor",
    "angry": "enojo sostenido",
    "shouting": "grito de verdad, con volumen",
    "sad": "duelo, pérdida — sólo en intensidad alta",
    "laughs": "risa",
}
RE_TAG = re.compile(r"\[([a-zA-Z_ ]+)\]")

# El `||` marca dónde la boca para: cada parte se ancla a su bloque de habla.
PARTIDOR = "||"


def limpiar(texto: str) -> str:
    """El texto que realmente se pronuncia. Los tags de v3 no se dicen, así que
    no cuentan para la densidad — contarlos infla el cps y hace reescribir
    líneas que estaban bien.

    Los espacios se colapsan al final: sacar un tag o un `||` deja huecos
    dobles, y cada uno sumaba un carácter fantasma al conteo."""
    return re.sub(r"\s+", " ", RE_TAG.sub("", texto).replace(PARTIDOR, " ")).strip()


def tags_de(texto: str) -> list[str]:
    return [t.strip().lower() for t in RE_TAG.findall(texto)]


def caracteres(texto: str) -> int:
    return len(limpiar(texto))


def densidad(texto: str, ventana: float) -> float:
    """Caracteres por segundo contra la ventana que le toca."""
    return caracteres(texto) / ventana if ventana > 0 else 999.0


def veredicto(cps_: float) -> str:
    if cps_ < CPS_MIN:
        return "alargar"
    if cps_ > CPS_MAX:
        return "acortar"
    return "entra"


def objetivo(ventana: float) -> tuple[int, int]:
    """Cuántos caracteres entran en esa ventana. Es lo que hay que darle a quien
    escribe la línea, en vez de pedirle que adivine."""
    return int(ventana * CPS_MIN), int(ventana * CPS_MAX)


def factor_previsto(texto: str, ventana: float) -> float:
    """Cuánto habría que deformar el audio si la línea durase lo que dice la
    densidad. >1 comprimir, <1 estirar."""
    return (caracteres(texto) / CPS) / ventana if ventana > 0 else 9.9


def factor_ok(factor: float) -> bool:
    return 1.0 / MAX_LENTO <= factor <= MAX_RAPIDO


@dataclass
class Linea:
    """Una línea de diálogo o de voz en off, con la ventana que le toca.

    `tipo` cambia qué se le exige, y la diferencia no es cosmética:

      "boca"  hay un personaje en pantalla moviendo los labios. La ventana **no
              se negocia**: la fija la boca. Se exige el mínimo Y el máximo,
              porque quedarse corto se ve como labios moviéndose sin voz.
      "off"   voz en off, nadie habla en pantalla. Sólo se exige el máximo: que
              no pise la línea siguiente. Quedarse corto no es un defecto — el
              silencio entre líneas es parte del guion.
    """
    id: str
    texto: str
    ventana: float
    tipo: str = "boca"              # "boca" | "off"
    personaje: str = ""
    voz_id: str = ""
    t: float | None = None          # dónde entra en la línea de tiempo
    plano: str = ""
    emocion: str = ""
    intensidad: int = 0
    variantes: list[str] = field(default_factory=list)
    # True cuando la ventana se dedujo del plano entero en vez de medirse. Es
    # una cota superior: hace avisar de más, nunca de menos.
    ventana_estimada: bool = False

    @property
    def caracteres(self) -> int:
        return caracteres(self.texto)

    @property
    def cps(self) -> float:
        return densidad(self.texto, self.ventana)

    @property
    def veredicto(self) -> str:
        v = veredicto(self.cps)
        # Sin boca en pantalla, quedarse corto no es un defecto.
        return "entra" if (v == "alargar" and self.tipo == "off") else v

    @property
    def tags(self) -> list[str]:
        return tags_de(self.texto)

    @property
    def partes(self) -> list[str]:
        return [x.strip() for x in self.texto.split(PARTIDOR)]

    def avisos(self) -> list[str]:
        """Todo lo que hay que arreglar ANTES de gastar un crédito."""
        out = []
        v = self.veredicto
        lo, hi = objetivo(self.ventana)
        if v == "acortar":
            out.append(f"{self.id}: {self.cps:.1f} cps en {self.ventana:.1f} s — no entra "
                       f"ni comprimiendo. Acortar a {hi} caracteres o menos "
                       f"(ahora {self.caracteres}).")
        elif v == "alargar":
            dura = self.caracteres / CPS
            sobra = self.ventana - dura
            if self.ventana_estimada:
                # La ventana se dedujo del plano entero, que es una cota
                # superior: puede que el resto del plano sea acción a propósito.
                out.append(f"{self.id}: la línea ocupa {dura:.1f} s de un plano de "
                           f"{self.ventana:.1f} s, así que {sobra:.1f} s el personaje no "
                           f"habla. Si eso es deliberado, declaralo con "
                           f"`ventana_dialogo`; si el plano es de alguien hablando, "
                           f"alargá el texto a {lo} caracteres (ahora {self.caracteres}). "
                           f"Al doblar, ese sobrante es boca muda.")
            else:
                out.append(f"{self.id}: {self.cps:.1f} cps — la línea llena {dura:.1f} s de "
                           f"una ventana de {self.ventana:.1f}, así que sobran {sobra:.1f} s "
                           f"de boca moviéndose sin voz. Alargar a {lo} caracteres o más "
                           f"(ahora {self.caracteres}); estirar el audio no lo arregla.")
        t = self.tags
        if len(t) > 1:
            out.append(f"{self.id}: {len(t)} tags en una línea ({', '.join(t)}); "
                       f"dos tags se pelean, va uno solo y al principio.")
        for x in t:
            if x not in TAGS:
                out.append(f"{self.id}: el tag [{x}] no es de los que entiende v3.")
        if t and self.intensidad and self.intensidad < 4:
            # El tag no sobreactúa la línea: cambia la voz. Y eso rompe lo único
            # que ElevenLabs aporta, que es sostener un personaje entre cortes.
            out.append(f"{self.id}: lleva [{t[0]}] con intensidad {self.intensidad}. "
                       f"En intensidad baja o media el tag corre el timbre y el "
                       f"personaje suena a otra persona: sacarlo.")
        if not limpiar(self.texto):
            # ElevenLabs rechaza con 400 un texto que sea sólo una etiqueta.
            out.append(f"{self.id}: el texto es sólo una etiqueta; v3 la rechaza con 400.")
        return out


def solapamientos(lineas: list[Linea]) -> list[str]:
    """Líneas que se pisan entre sí. Se mide contra la duración prevista por
    densidad, que alcanza para detectar el choque antes de sintetizar."""
    out = []
    conT = sorted([x for x in lineas if x.t is not None], key=lambda x: x.t)
    for a, b in zip(conT, conT[1:]):
        fin = a.t + a.caracteres / CPS
        if fin > b.t + 0.05:
            out.append(f"{a.id} termina cerca de {fin:.1f} s y {b.id} entra en "
                       f"{b.t:.1f}: se pisan por {fin - b.t:.1f} s.")
    return out


def revisar(lineas: list[Linea]) -> list[str]:
    avisos = []
    for x in lineas:
        avisos += x.avisos()
    # Coherencia por escena: dos líneas seguidas del mismo personaje no deberían
    # saltar de un tag a otro sin que pase algo en la historia.
    for a, b in zip(lineas, lineas[1:]):
        if a.personaje and a.personaje == b.personaje and a.tags and b.tags \
                and a.tags != b.tags:
            avisos.append(f"{a.id}→{b.id}: {a.personaje} salta de [{a.tags[0]}] a "
                          f"[{b.tags[0]}] entre dos líneas seguidas; "
                          f"¿pasa algo en la historia ahí?")
    return avisos


def tabla(lineas: list[Linea]) -> str:
    """El entregable: una fila por línea, con la columna que se revisa antes de
    gastar un crédito."""
    L = ["| id | personaje | ventana | texto | car. | cps | tag | veredicto |",
         "|---|---|---|---|---|---|---|---|"]
    for x in lineas:
        tag = f"`[{x.tags[0]}]`" if x.tags else "—"
        marca = {"entra": "entra", "alargar": "**alargar**", "acortar": "**acortar**"}[x.veredicto]
        L.append(f"| {x.id} | {x.personaje or '—'} | {x.ventana:.1f} s | "
                 f"{limpiar(x.texto)[:52]} | {x.caracteres} | **{x.cps:.1f}** | {tag} | {marca} |")
    fuera = [x for x in lineas if x.veredicto != "entra"]
    L += ["", f"{len(lineas)} líneas · {len(fuera)} para reescribir · "
              f"{sum(x.caracteres for x in lineas)} caracteres en total"]
    return "\n".join(L)


def para_elevenlabs(linea: Linea) -> str:
    """El texto tal cual se pega, con el tag pegado adelante."""
    return linea.texto.replace(PARTIDOR, " ").strip()
