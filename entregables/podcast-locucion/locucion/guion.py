"""Del texto plano a la lista de líneas que se van a sintetizar, con sus pausas.

El texto NO se manda entero a ElevenLabs. Se parte en oraciones, cada oración
se sintetiza aparte y después se arman de nuevo con silencios exactos entre
medio. Suena mucho mejor y es la razón principal del ritmo de locución:

- Mandando el episodio entero, el modelo elige sus propias pausas y va
  perdiendo el pulso: arranca bien y a los dos minutos lee de corrido.
- Oración por oración, cada una entra con intención y la pausa la ponemos
  nosotros, siempre igual.
- Y si hay que corregir una frase, se resintetiza SÓLO esa (el caché es por
  hash del texto), en vez de pagar el episodio completo otra vez.

Además, partir en oraciones es lo que permite devolver una línea de tiempo:
qué se dice y en qué segundo. Sirve para subtítulos, capítulos y transcripción.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Partir en oraciones con lookbehinds se vuelve ilegible enseguida, y falla: el
# corte se evalúa DESPUÉS del punto, así que cada guarda tiene que incluir el
# punto, y aun así las iniciales y los horarios se escapan. Se hace en tres
# pasos, que se leen y se prueban de a uno:
#
#   1 · se tapan los puntos que NO terminan oración, con un carácter que no
#       aparece en ningún texto real;
#   2 · se corta por . ! ? … seguidos de espacio;
#   3 · se destapan.
_TAPA = "\x00"
# Sólo las que van seguidas de un nombre propio en mayúscula, que es cuando el
# corte se confundiría. «etc.» y «aprox.» NO están: casi siempre terminan
# oración, y si no, la regla de la minúscula de abajo las cubre.
ABREVIATURAS = ("Sr", "Sra", "Srta", "Dr", "Dra", "Lic", "Ing", "Prof", "Gral",
                "Av", "Bs", "Nro")
RE_ABREV = re.compile(r"\b(" + "|".join(ABREVIATURAS) + r")\.")
RE_LETRA = re.compile(r"\b([A-Za-zÁÉÍÓÚÑáéíóúñ])\.")   # «J. R. Tolkien», «9 a. m.»
RE_SIGLA = re.compile(r"\b([A-ZÁÉÍÓÚÑ]{1,3})\.(?=\s*[A-ZÁÉÍÓÚÑ]{1,3}\.)")   # EE. UU.
RE_DECIMAL = re.compile(r"(\d)\.(?=\d)")               # 3.14
# Y la regla que más casos resuelve sola: una oración nueva arranca en
# mayúscula, en número o en signo de apertura. Si lo que sigue al punto es
# minúscula, no era un final de oración («Pará... no entiendo»).
RE_CORTE = re.compile(r"(?<=[.!?…])[\"'»\)\]]*\s+"
                      r"(?=[«\"'\(\[¿¡]*[A-ZÁÉÍÓÚÑ0-9])")


def _tapar(t: str) -> str:
    for rx in (RE_SIGLA, RE_ABREV, RE_LETRA, RE_DECIMAL):
        t = rx.sub(lambda m: m.group(1) + _TAPA, t)
    return t


def _destapar(t: str) -> str:
    return t.replace(_TAPA, ".")


@dataclass
class Linea:
    texto: str
    parrafo: int
    t: float = 0.0            # segundo en que arranca, dentro del episodio
    dur: float = 0.0          # se completa al sintetizar


@dataclass
class Episodio:
    lineas: list[Linea] = field(default_factory=list)
    total: float = 0.0

    def srt(self) -> str:
        """El episodio como subtítulos, con los tiempos reales."""
        def t(s: float) -> str:
            h, r = divmod(max(0.0, s), 3600)
            m, s2 = divmod(r, 60)
            return f"{int(h):02d}:{int(m):02d}:{int(s2):02d},{int(round((s2 % 1) * 1000)):03d}"
        out = []
        for i, l in enumerate(self.lineas, 1):
            out.append(f"{i}\n{t(l.t)} --> {t(l.t + l.dur)}\n{l.texto}\n")
        return "\n".join(out)


def parrafos(texto: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", texto.strip()) if p.strip()]


def oraciones(parrafo: str) -> list[str]:
    limpio = " ".join(parrafo.split())
    partes = RE_CORTE.split(_tapar(limpio))
    ors = [_destapar(o).strip() for o in partes if _destapar(o).strip()]
    return ors or ([limpio] if limpio else [])


def partir(texto: str) -> list[Linea]:
    """El texto del episodio en líneas, sin tiempos todavía."""
    out = []
    for k, p in enumerate(parrafos(texto)):
        for o in oraciones(p):
            out.append(Linea(texto=o, parrafo=k))
    return out


def anclar(lineas: list[Linea], pausa_oracion: float, pausa_parrafo: float,
           arranque: float) -> Episodio:
    """Pone el `t` de cada línea a partir de su duración ya medida. Llamalo
    DESPUÉS de sintetizar, cuando cada `Linea.dur` tiene la duración real."""
    t = arranque
    for i, l in enumerate(lineas):
        l.t = round(t, 3)
        t += l.dur
        if i + 1 < len(lineas):
            cambia_parrafo = lineas[i + 1].parrafo != l.parrafo
            t += pausa_parrafo if cambia_parrafo else pausa_oracion
    return Episodio(lineas=lineas, total=round(t, 3))


def estimar(texto: str, cps: float, pausa_oracion: float, pausa_parrafo: float,
            arranque: float) -> float:
    """Cuánto va a durar, ANTES de sintetizar. Sirve para presupuestar y para
    avisarle al usuario. `cps` = caracteres por segundo de esa voz (ver
    `voces.py`); el error típico es del 10 % por episodio, más alto por línea
    suelta, porque la misma cantidad de caracteres dura distinto según las
    sílabas y cómo lo actúe el modelo."""
    ls = partir(texto)
    t = arranque
    for i, l in enumerate(ls):
        t += len(l.texto) / cps
        if i + 1 < len(ls):
            t += pausa_parrafo if ls[i + 1].parrafo != l.parrafo else pausa_oracion
    return round(t, 2)
